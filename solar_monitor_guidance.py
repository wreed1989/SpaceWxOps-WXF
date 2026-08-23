#!/usr/bin/env python3
"""Enrich a WXF forecast payload with SolarMonitor MCSTAT/MCEVOL guidance.

SolarMonitor publishes active-region probabilities for C+, M+, and X+ over a
24-hour period. This module extracts its regional M1+/X1+ MCSTAT and MCEVOL
values, preserves those regional values exactly, and writes a conservative
full-disk *dominant-region proxy* using the maximum regional probability.

The maximum is intentionally used instead of 1-product(1-p_i): SolarMonitor does
not publish a full-disk aggregate, and treating regional probabilities as
independent can create misleadingly large disk probabilities. Missing MCEVOL
values remain missing; MCSTAT is never substituted into the MCEVOL product.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import os
from typing import Any, Iterable, Mapping

import requests

UTC = dt.timezone.utc
DEFAULT_BASE_URL = "https://www.solarmonitor.org/forecast.php"
USER_AGENT = (
    "SpaceWxOps-WXF/1.0 (SolarMonitor forecast ingestion; "
    "research comparison guidance)"
)


class SolarMonitorError(RuntimeError):
    """Expected ingestion or parsing failure."""


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value).replace("\xa0", " ")).strip()


class _TableParser(HTMLParser):
    """Minimal dependency-free extractor that preserves nested HTML tables."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._stack: list[dict[str, Any]] = []

    @staticmethod
    def _finish_cell(context: dict[str, Any]) -> None:
        cell = context.get("cell")
        if cell is None:
            return
        if context.get("row") is None:
            context["row"] = []
        context["row"].append(_clean_text("".join(cell)))
        context["cell"] = None

    @classmethod
    def _finish_row(cls, context: dict[str, Any]) -> None:
        cls._finish_cell(context)
        row = context.get("row")
        if row:
            context["rows"].append(row)
        context["row"] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self._stack.append({"rows": [], "row": None, "cell": None})
            return
        if not self._stack:
            return
        context = self._stack[-1]
        if tag == "tr":
            self._finish_row(context)
            context["row"] = []
        elif tag in {"td", "th"}:
            if context.get("row") is None:
                context["row"] = []
            self._finish_cell(context)
            context["cell"] = []
        elif context.get("cell") is not None and tag in {"br", "p", "div"}:
            context["cell"].append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self._stack:
            return
        context = self._stack[-1]
        if tag in {"td", "th"}:
            self._finish_cell(context)
        elif tag == "tr":
            self._finish_row(context)
        elif tag == "table":
            self._finish_row(context)
            self.tables.append(context["rows"])
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._stack and self._stack[-1].get("cell") is not None:
            self._stack[-1]["cell"].append(data)


def parse_probability(value: Any) -> float | None:
    text = _clean_text(str(value or ""))
    if not text or text in {"-", "--", "...", "—", "–", "N/A", "NA"}:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    number = float(match.group(0))
    if not math.isfinite(number) or number < 0 or number > 100:
        return None
    return number


def canonical_noaa_region(value: Any) -> int | None:
    match = re.search(r"\d{4,6}", str(value or ""))
    if not match:
        return None
    number = int(match.group(0))
    if 1000 <= number <= 9999:
        number += 10000
    return number if number > 0 else None


def _table_score(table: list[list[str]]) -> int:
    text = " ".join(cell for row in table[:6] for cell in row).upper()
    score = 0
    for token, points in (
        ("NOAA", 4),
        ("MCEVOL", 6),
        ("MCSTAT", 6),
        ("SWPC", 3),
        ("M+", 2),
        ("X+", 2),
        ("MEAN", 1),
    ):
        if token in text:
            score += points
    score += sum(1 for row in table if row and canonical_noaa_region(row[0]) is not None)
    return score


def parse_solar_monitor_html(document: str) -> list[dict[str, Any]]:
    parser = _TableParser()
    parser.feed(document)
    if not parser.tables:
        raise SolarMonitorError("SolarMonitor response contained no HTML tables")

    # The current solarmonitor.org page renders the NOAA region numbers and the
    # C/M/X method values as four adjacent nested tables rather than one flat
    # table. Identify the three method tables first and align their data rows
    # with the nearest preceding NOAA-number table.
    method_tables: list[tuple[int, list[list[str]]]] = []
    for index, candidate in enumerate(parser.tables):
        header = " ".join(candidate[0] if candidate else []).upper()
        if "MCEVOL" in header and "MCSTAT" in header:
            method_tables.append((index, candidate))
    if len(method_tables) >= 3:
        first_method_index = method_tables[0][0]
        region_candidates: list[tuple[int, list[int]]] = []
        for index, candidate in enumerate(parser.tables[:first_method_index]):
            numbers = [
                number
                for row in candidate
                if row and (number := canonical_noaa_region(row[0])) is not None
            ]
            if numbers:
                region_candidates.append((index, numbers))
        if region_candidates:
            _, region_numbers = max(region_candidates, key=lambda item: (item[0], len(item[1])))
            c_table, m_table, x_table = [item[1] for item in method_tables[:3]]
            c_rows, m_rows, x_rows = c_table[1:], m_table[1:], x_table[1:]
            count = min(len(region_numbers), len(c_rows), len(m_rows), len(x_rows))
            regions: list[dict[str, Any]] = []
            for index in range(count):
                c_values = [parse_probability(value) for value in c_rows[index][:3]]
                m_values = [parse_probability(value) for value in m_rows[index][:3]]
                x_values = [parse_probability(value) for value in x_rows[index][:3]]
                while len(c_values) < 3:
                    c_values.append(None)
                while len(m_values) < 3:
                    m_values.append(None)
                while len(x_values) < 3:
                    x_values.append(None)
                regions.append(
                    {
                        "noaa_region": region_numbers[index],
                        "c1": {"mcevol": c_values[0], "mcstat": c_values[1], "swpc": c_values[2]},
                        "m1": {"mcevol": m_values[0], "mcstat": m_values[1], "swpc": m_values[2]},
                        "x1": {"mcevol": x_values[0], "mcstat": x_values[1], "swpc": x_values[2]},
                        "mean": {"c1": None, "m1": None, "x1": None},
                    }
                )
            if regions:
                return regions

    # Retain support for the older flat-table rendering.
    table = max(parser.tables, key=_table_score)
    if _table_score(table) < 12:
        raise SolarMonitorError("Could not identify the SolarMonitor flare-probability table")

    regions: list[dict[str, Any]] = []
    for cells in table:
        if not cells:
            continue
        region = canonical_noaa_region(cells[0])
        if region is None:
            continue

        # Current table: NOAA + 3 methods for C/M/X + 3 means = 13 cells.
        # Older/no-SWPC rendering: NOAA + 2 methods for C/M/X + 3 means = 10.
        if len(cells) >= 13:
            c_mcevol, c_mcstat, c_swpc = map(parse_probability, cells[1:4])
            m_mcevol, m_mcstat, m_swpc = map(parse_probability, cells[4:7])
            x_mcevol, x_mcstat, x_swpc = map(parse_probability, cells[7:10])
            means = [parse_probability(value) for value in cells[10:13]]
        elif len(cells) >= 10:
            c_mcevol, c_mcstat = map(parse_probability, cells[1:3])
            m_mcevol, m_mcstat = map(parse_probability, cells[3:5])
            x_mcevol, x_mcstat = map(parse_probability, cells[5:7])
            c_swpc = m_swpc = x_swpc = None
            means = [parse_probability(value) for value in cells[7:10]]
        else:
            continue

        regions.append(
            {
                "noaa_region": region,
                "c1": {"mcevol": c_mcevol, "mcstat": c_mcstat, "swpc": c_swpc},
                "m1": {"mcevol": m_mcevol, "mcstat": m_mcstat, "swpc": m_swpc},
                "x1": {"mcevol": x_mcevol, "mcstat": x_mcstat, "swpc": x_swpc},
                "mean": {"c1": means[0], "m1": means[1], "x1": means[2]},
            }
        )

    unique: dict[int, dict[str, Any]] = {}
    for row in regions:
        unique[int(row["noaa_region"])] = row
    result = [unique[key] for key in sorted(unique)]
    if not result:
        raise SolarMonitorError("SolarMonitor table contained no parseable NOAA-region rows")
    return result


def iso_z(value: dt.datetime) -> str:
    value = value.astimezone(UTC)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso_time(value: Any) -> dt.datetime:
    text = str(value or "").strip()
    if not text:
        raise SolarMonitorError("Forecast payload is missing valid_start")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise SolarMonitorError(f"Invalid ISO forecast time: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def solar_monitor_url(valid_start: dt.datetime, base_url: str = DEFAULT_BASE_URL) -> str:
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}date={valid_start:%Y%m%d}"


def fetch_solar_monitor(url: str, timeout: float = 60.0) -> tuple[str, str]:
    session = requests.Session()
    response = session.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SolarMonitorError(f"SolarMonitor request failed: {exc}") from exc
    if len(response.text) < 500:
        raise SolarMonitorError("SolarMonitor response was unexpectedly short")
    return response.text, response.url


def member(m1: float | None, x1: float | None, source: str) -> dict[str, Any] | None:
    if m1 is None and x1 is None:
        return None
    if m1 is not None and x1 is not None:
        x1 = min(x1, m1)
    return {
        "m1": m1,
        "x1": x1,
        "source": source,
        "quality": "published-comparison",
    }


def max_probability(values: Iterable[float | None]) -> float | None:
    finite = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return max(finite) if finite else None


def _payload_region_id(region: Mapping[str, Any]) -> int | None:
    return canonical_noaa_region(region.get("id") or region.get("label") or region.get("region"))


def enrich_payload(
    payload: dict[str, Any],
    solar_regions: list[dict[str, Any]],
    *,
    source_url: str,
    fetched_at: dt.datetime | None = None,
) -> dict[str, Any]:
    fetched_at = fetched_at or dt.datetime.now(tz=UTC)
    payload.setdefault("probability_scale", "percent")
    payload_regions = payload.setdefault("regions", [])
    if not isinstance(payload_regions, list):
        raise SolarMonitorError("Forecast payload regions must be a list")

    by_region: dict[int, dict[str, Any]] = {}
    full_disk: dict[str, Any] | None = None
    for row in payload_regions:
        if not isinstance(row, dict):
            continue
        if str(row.get("id", "")).lower() in {"full-disk", "fulldisk", "disk", "global"}:
            full_disk = row
            continue
        number = _payload_region_id(row)
        if number is not None:
            by_region[number] = row

    if full_disk is None:
        full_disk = {"id": "full-disk", "label": "Full Disk", "members": {}}
        payload_regions.insert(0, full_disk)
    full_disk.setdefault("members", {})

    regional_mcstat_m: list[float | None] = []
    regional_mcstat_x: list[float | None] = []
    regional_mcevol_m: list[float | None] = []
    regional_mcevol_x: list[float | None] = []

    for solar in solar_regions:
        number = int(solar["noaa_region"])
        target = by_region.get(number)
        if target is None:
            target = {
                "id": f"AR{number}",
                "label": f"AR {number}",
                "members": {},
            }
            payload_regions.append(target)
            by_region[number] = target
        members = target.setdefault("members", {})

        mcstat_m = solar["m1"]["mcstat"]
        mcstat_x = solar["x1"]["mcstat"]
        mcevol_m = solar["m1"]["mcevol"]
        mcevol_x = solar["x1"]["mcevol"]
        swpc_m = solar["m1"]["swpc"]
        swpc_x = solar["x1"]["swpc"]

        mcstat_member = member(mcstat_m, mcstat_x, "SolarMonitor MCSTAT regional forecast")
        mcevol_member = member(mcevol_m, mcevol_x, "SolarMonitor MCEVOL regional forecast")
        swpc_member = member(swpc_m, swpc_x, "SWPC regional forecast as displayed by SolarMonitor")
        if mcstat_member:
            members["mcstat"] = mcstat_member
        if mcevol_member:
            members["mcevol"] = mcevol_member
        else:
            members.pop("mcevol", None)
        if swpc_member:
            members["swpc"] = swpc_member

        regional_mcstat_m.append(mcstat_m)
        regional_mcstat_x.append(mcstat_x)

        regional_mcevol_m.append(mcevol_m)
        regional_mcevol_x.append(mcevol_x)

    full_mcstat = member(
        max_probability(regional_mcstat_m),
        max_probability(regional_mcstat_x),
        f"SolarMonitor MCSTAT dominant-region proxy (maximum of {len(solar_regions)} regional forecasts)",
    )
    full_mcevol = member(
        max_probability(regional_mcevol_m),
        max_probability(regional_mcevol_x),
        f"SolarMonitor MCEVOL dominant-region proxy (maximum of {len(solar_regions)} regional forecasts)",
    )
    if full_mcstat:
        full_disk["members"]["mcstat"] = full_mcstat
    if full_mcevol:
        full_disk["members"]["mcevol"] = full_mcevol

    valid_start = parse_iso_time(payload.get("valid_start"))
    payload["solar_monitor"] = {
        "source": "SolarMonitor",
        "source_url": source_url,
        "retrieved_at": iso_z(fetched_at),
        "valid_start": iso_z(valid_start),
        "valid_end": payload.get("valid_end"),
        "regional_forecasts": len(solar_regions),
        "full_disk_method": "maximum regional probability (dominant-region proxy)",
        "note": (
            "Regional MCSTAT/MCEVOL values are reproduced from SolarMonitor. "
            "SolarMonitor does not publish a full-disk aggregate in this table; "
            "the dashboard uses each method's maximum published regional probability "
            "to avoid an independence-union inflation. Missing values remain missing."
        ),
    }
    return payload


def atomic_write(path: Path, text: str) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def javascript_payload(payload: Mapping[str, Any]) -> str:
    return (
        "/* Generated automatically by the SpaceWxOps WXF workflow. */\n"
        "window.FLARE_GUIDANCE_PAYLOAD = "
        + json.dumps(payload, indent=2, ensure_ascii=False)
        + ";\n"
    )


def command_enrich(args: argparse.Namespace) -> int:
    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SolarMonitorError("Forecast payload root must be an object")
    valid_start = parse_iso_time(payload.get("valid_start"))
    url = args.url or solar_monitor_url(valid_start, args.base_url)
    document, final_url = fetch_solar_monitor(url, timeout=args.timeout)
    rows = parse_solar_monitor_html(document)
    enrich_payload(payload, rows, source_url=final_url)
    atomic_write(output_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    js_path = args.js_output.expanduser().resolve() if args.js_output else output_path.with_name("flare_guidance.js")
    atomic_write(js_path, javascript_payload(payload))
    print(
        f"SolarMonitor enrichment complete: {len(rows)} regions; "
        f"valid {payload['valid_start']} to {payload.get('valid_end')}"
    )
    return 0


def command_parse(args: argparse.Namespace) -> int:
    rows = parse_solar_monitor_html(args.html.read_text(encoding="utf-8", errors="replace"))
    print(json.dumps(rows, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add SolarMonitor MCSTAT/MCEVOL values to a WXF JSON payload")
    subparsers = parser.add_subparsers(dest="command", required=True)

    enrich = subparsers.add_parser("enrich", help="Fetch SolarMonitor and enrich an existing WXF payload")
    enrich.add_argument("--input", type=Path, required=True)
    enrich.add_argument("--output", type=Path, required=True)
    enrich.add_argument("--js-output", type=Path)
    enrich.add_argument("--base-url", default=DEFAULT_BASE_URL)
    enrich.add_argument("--url", help="Explicit SolarMonitor forecast URL; primarily for testing")
    enrich.add_argument("--timeout", type=float, default=60.0)
    enrich.set_defaults(func=command_enrich)

    parse = subparsers.add_parser("parse", help="Parse a saved SolarMonitor HTML page")
    parse.add_argument("--html", type=Path, required=True)
    parse.set_defaults(func=command_parse)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (SolarMonitorError, requests.RequestException, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
