#!/usr/bin/env python3
"""CCMC schema-aligned external flare-guidance adapter.

This wrapper builds on ``external_flare_guidance_fixed.py`` and corrects a
HAPI-specific schema mismatch. Some Flare Scoreboard ``/info`` responses list a
short provider schema, while ``/data`` returns the standardized Scoreboard
schema (C, M, CPlus, MPlus, X, uncertainties, bounds, and levels). The data rows
must be decoded with the parameter list returned by ``/data`` itself.

For the wall's M1+ column this adapter explicitly prefers ``MPlus`` over ``M``.
It accepts current, overlapping forecasts only; absent, stale, retired, or
unverified providers remain unavailable rather than being substituted.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

import external_flare_guidance as legacy
import external_flare_guidance_fixed as strict

SCRIPT_VERSION = "3.0.0"


def _normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def select_probability_parameter(
    schema: Mapping[str, Any], letter: str
) -> tuple[str, dict[str, Any]] | None:
    """Select M1+/X1+ fields from the standardized Scoreboard schema."""
    metadata = strict.parameter_metadata(schema)
    preferences = (
        ("mplus", "m1plus", "mplusprobability", "m1plusprobability", "m")
        if letter.lower() == "m"
        else ("xplus", "x1plus", "xplusprobability", "x1plusprobability", "x")
    )
    for preferred in preferences:
        for name, item in metadata.items():
            if _normalized(name) != preferred:
                continue
            units = str(item.get("units") or item.get("unit") or "").lower()
            item_type = _normalized(item.get("type"))
            if "probab" in units or item_type in {"double", "float", "integer"}:
                return name, item

    # Retain the stricter metadata scorer for non-standard but well-described
    # provider fields.
    return strict.select_probability_parameter(schema, letter)


def fetch_ccmc_member(
    session: Any,
    *,
    base: str,
    dataset_id: str,
    label: str,
    issue_time: dt.datetime,
    valid_start: dt.datetime,
    valid_end: dt.datetime,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    status: dict[str, Any] = {
        "dataset_id": dataset_id,
        "label": label,
        "ok": False,
        "parser": SCRIPT_VERSION,
    }
    try:
        info, info_url = legacy.get_json(
            session, base + "/info", params={"id": dataset_id}, timeout=45
        )

        query_min = issue_time - dt.timedelta(days=4)
        query_max = issue_time + dt.timedelta(days=1)
        data, data_url = legacy.get_json(
            session,
            base + "/data",
            params={
                "id": dataset_id,
                "time.min": query_min.strftime("%Y-%m-%dT%H:%M:%S.0"),
                "time.max": query_max.strftime("%Y-%m-%dT%H:%M:%S.0"),
                "format": "json",
                "options": "fields.all",
            },
            timeout=60,
        )

        data_parameters = data.get("parameters")
        schema: Mapping[str, Any]
        if isinstance(data_parameters, list) and data_parameters:
            schema = {"parameters": data_parameters}
            schema_source = "data"
        else:
            schema = info
            schema_source = "info"

        names = strict.parameter_names(schema)
        m_parameter = select_probability_parameter(schema, "m")
        x_parameter = select_probability_parameter(schema, "x")
        status.update(
            {
                "info_url": info_url,
                "url": data_url,
                "schema_source": schema_source,
                "parameter_names": names,
                "m_parameter": m_parameter[0] if m_parameter else None,
                "x_parameter": x_parameter[0] if x_parameter else None,
            }
        )
        if not m_parameter and not x_parameter:
            status["detail"] = (
                "No M1+/X1+ probability parameters identified from the HAPI schema"
            )
            return None, status

        records = strict.flatten_records(data, names)
        status["records"] = len(records)
        if not records:
            status["detail"] = "No records in query window"
            return None, status

        issue_name, start_name, end_name = strict.time_parameter_names(schema)
        candidates: list[tuple[tuple[float, float, float], dict[str, Any]]] = []
        for record in records:
            m1 = (
                strict.convert_probability(
                    strict.value_by_name(record, m_parameter[0]), m_parameter[1]
                )
                if m_parameter
                else None
            )
            x1 = (
                strict.convert_probability(
                    strict.value_by_name(record, x_parameter[0]), x_parameter[1]
                )
                if x_parameter
                else None
            )
            if m1 is None and x1 is None:
                continue

            issued = legacy.parse_time(strict.value_by_name(record, issue_name))
            start = legacy.parse_time(strict.value_by_name(record, start_name))
            end = legacy.parse_time(strict.value_by_name(record, end_name))
            if start is None and issued is not None:
                start = issued
            if end is None and start is not None:
                end = start + dt.timedelta(hours=24)

            overlap = (
                strict.overlap_seconds(start, end, valid_start, valid_end)
                if start and end
                else 0.0
            )
            future_penalty = (
                max(0.0, (issued - issue_time).total_seconds()) if issued else 0.0
            )
            issue_age = (
                abs((issue_time - issued).total_seconds()) if issued else 1e12
            )
            candidates.append(
                (
                    (overlap, -future_penalty, -issue_age),
                    {
                        "m1": m1,
                        "x1": x1,
                        "issued": issued,
                        "start": start,
                        "end": end,
                        "record": record,
                    },
                )
            )

        if not candidates:
            status["detail"] = (
                "Records existed, but no non-fill M1+/X1+ probabilities were present"
            )
            return None, status

        selected = sorted(candidates, key=lambda item: item[0])[-1][1]
        issued = selected["issued"]
        start = selected["start"]
        end = selected["end"]
        if issued and issue_time - issued > dt.timedelta(hours=48):
            status["detail"] = (
                f"Latest usable issue is stale ({legacy.iso_z(issued)})"
            )
            return None, status
        if (
            start
            and end
            and strict.overlap_seconds(start, end, valid_start, valid_end) < 6 * 3600
        ):
            status["detail"] = (
                "Forecast window does not meaningfully overlap target "
                f"({legacy.iso_z(start)} to {legacy.iso_z(end)})"
            )
            return None, status

        m1 = selected["m1"]
        x1 = selected["x1"]
        result = legacy.member(
            m1=m1,
            x1=x1,
            source=f"NASA/CCMC Flare Scoreboard · {label}",
            issued=issued,
            valid_start=start,
            valid_end=end,
            note=(
                "Probability reproduced from the NASA/CCMC Flare Scoreboard "
                "HAPI feed using the /data parameter schema."
            ),
            dataset_id=dataset_id,
        )
        status.update(
            {
                "ok": result is not None,
                "issued": legacy.iso_z(issued),
                "valid_start": legacy.iso_z(start),
                "valid_end": legacy.iso_z(end),
                "m1": m1,
                "x1": x1,
                "selected_record": {
                    str(key): value
                    for key, value in selected["record"].items()
                    if len(str(value)) < 160
                },
            }
        )
        return result, status
    except Exception as exc:
        status["detail"] = f"{type(exc).__name__}: {exc}"
        return None, status


# ``strict`` already installed provider-specific catalog matching and catalog
# capture into the legacy module. Replace only the HAPI record decoder.
legacy.fetch_ccmc_member = fetch_ccmc_member


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Add current SIDC, Met Office, FLARECAST, and NASA/CCMC guidance "
            "using schema-aligned HAPI parsing"
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--js-output", type=Path)
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("payload root must be an object")
        payload = legacy.enrich(payload)
        external = payload.setdefault("external_sources", {})
        external["strict_parser_version"] = SCRIPT_VERSION
        external["ccmc_catalog_entries"] = [
            {
                "id": item.get("id"),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
            }
            for item in strict.CATALOG_SNAPSHOT
        ]
        legacy.atomic_write(
            args.output, json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        )
        js_output = args.js_output or args.output.with_name("flare_guidance.js")
        legacy.atomic_write(js_output, legacy.javascript_payload(payload))
        available = sorted(legacy.full_disk_region(payload).get("members", {}).keys())
        print(
            "Schema-aligned external guidance update complete; available members: "
            + ", ".join(available)
        )
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
