#!/usr/bin/env python3
"""Strict external flare-guidance adapter for SpaceWxOps.

This module wraps ``external_flare_guidance.py`` and corrects two failure modes
seen during the first live CCMC pass:

1. A provider must positively match its own dataset name/title. Merely being a
   FULLDISK dataset is not sufficient.
2. M1+/X1+ values are identified from HAPI parameter metadata. Bare fields named
   ``M`` or ``X`` are not treated as probabilities unless the parameter metadata
   explicitly describes a flare probability.

Unavailable, stale, maintenance-mode, or unverified sources remain absent from
``members`` and therefore display ``--`` on the wall.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

import external_flare_guidance as legacy

UTC = dt.timezone.utc
SCRIPT_VERSION = "2.0.0"

# Only the sources explicitly requested for the wall. SIDC and Met Office have
# stable Scoreboard IDs. MagPy also has a known current ID. DAFFS and A-EFFort
# are accepted only when the current catalog positively identifies them.
PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        "key": "sidc",
        "label": "SIDC",
        "patterns": (r"\bsidc\b", r"royal observatory of belgium", r"sidc_operator"),
        "fallback_ids": ("SIDC_Operator_FULLDISK",),
    },
    {
        "key": "metoffice",
        "label": "Met Office",
        "patterns": (r"met office", r"moswoc", r"(?:^|[_-])mo(?:[_-])", r"mo_tot"),
        "fallback_ids": ("MO_TOT1_FULLDISK",),
    },
    {
        "key": "ccmc_magpy",
        "label": "CCMC MagPy",
        "patterns": (r"magpy",),
        "fallback_ids": ("MagPy_SHARP_HMI_CEA_FULLDISK",),
    },
    {
        "key": "ccmc_daffs",
        "label": "CCMC DAFFS",
        "patterns": (r"\bdaffs\b", r"discriminant analysis flare"),
        "fallback_ids": (),
    },
    {
        "key": "ccmc_aeffort",
        "label": "CCMC A-EFFort",
        "patterns": (r"a[-_ ]?effort", r"aeffort", r"athens effective solar flare"),
        "fallback_ids": (),
    },
)

CATALOG_SNAPSHOT: list[dict[str, Any]] = []


def normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def strict_provider_dataset(provider: Mapping[str, Any], catalog: list[dict[str, Any]]) -> str | None:
    """Select a dataset only after a provider-specific positive match."""
    available_ids = {str(item.get("id") or "").strip() for item in catalog}
    candidates: list[tuple[int, str]] = []
    for item in catalog:
        dataset_id = str(item.get("id") or "").strip()
        if not dataset_id or "FULLDISK" not in dataset_id.upper():
            continue
        haystack = f"{dataset_id} {item.get('title', '')} {item.get('description', '')}"
        matched = [
            pattern for pattern in provider.get("patterns", ())
            if re.search(pattern, haystack, flags=re.IGNORECASE)
        ]
        if not matched:
            continue
        score = 100 * len(matched)
        if dataset_id.upper().endswith("_FULLDISK"):
            score += 5
        if re.search(r"(?:v?3|0[._-]?37|1[._-]?0)", dataset_id, flags=re.IGNORECASE):
            score += 1
        candidates.append((score, dataset_id))
    if candidates:
        return sorted(candidates, key=lambda pair: (pair[0], pair[1]))[-1][1]
    for dataset_id in provider.get("fallback_ids", ()):
        if str(dataset_id) in available_ids:
            return str(dataset_id)
    return None


def capture_catalog(session: Any) -> tuple[list[dict[str, Any]], str]:
    catalog, url = ORIGINAL_FETCH_CATALOG(session)
    CATALOG_SNAPSHOT.clear()
    CATALOG_SNAPSHOT.extend(catalog)
    return catalog, url


def parameter_names(info: Mapping[str, Any]) -> list[str]:
    output: list[str] = []
    for item in info.get("parameters", []) if isinstance(info.get("parameters"), list) else []:
        if isinstance(item, Mapping):
            output.append(str(item.get("name") or item.get("id") or ""))
        else:
            output.append(str(item))
    return output


def parameter_metadata(info: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    parameters = info.get("parameters")
    if not isinstance(parameters, list):
        return output
    for item in parameters:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or item.get("id") or "").strip()
        if name:
            output[name] = dict(item)
    return output


def has_class_marker(text: str, letter: str) -> bool:
    text = str(text or "")
    if letter == "m":
        patterns = (
            r"\bm(?:1(?:\.0)?|1\+|\+|[- ]?class)?\b",
            r">=?\s*m(?:1(?:\.0)?)?",
            r"m1(?:\.0)?\+",
        )
    else:
        patterns = (
            r"\bx(?:1(?:\.0)?|1\+|\+|[- ]?class)?\b",
            r">=?\s*x(?:1(?:\.0)?)?",
            r"x1(?:\.0)?\+",
        )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def probability_parameter_score(metadata: Mapping[str, Any], letter: str) -> int:
    name = str(metadata.get("name") or metadata.get("id") or "")
    description = " ".join(
        str(metadata.get(key) or "")
        for key in ("description", "label", "title", "note")
    )
    units = str(metadata.get("units") or metadata.get("unit") or "")
    combined = f"{name} {description} {units}"
    normalized_name = normalize(name)
    class_ok = has_class_marker(combined, letter)
    probability_ok = bool(re.search(r"probab|forecast|chance|likelihood|rate", combined, flags=re.IGNORECASE))

    exact_names = {
        "m": {"m", "mprob", "mprobability", "probm", "probabilitym", "m1", "m1prob", "m1probability"},
        "x": {"x", "xprob", "xprobability", "probx", "probabilityx", "x1", "x1prob", "x1probability"},
    }[letter]

    # Bare M/X is accepted only when metadata says it is a probability.
    if normalized_name in {letter, f"{letter}1"} and not probability_ok:
        return -1
    if not class_ok and normalized_name not in exact_names:
        return -1
    if not probability_ok and "prob" not in normalized_name:
        return -1

    score = 0
    if normalized_name in exact_names:
        score += 100
    if "prob" in normalized_name:
        score += 60
    if probability_ok:
        score += 40
    if class_ok:
        score += 30
    if "%" in units or "percent" in units.lower():
        score += 10
    if normalize(metadata.get("type")) in {"double", "integer", "float"}:
        score += 2
    return score


def select_probability_parameter(info: Mapping[str, Any], letter: str) -> tuple[str, dict[str, Any]] | None:
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for name, metadata in parameter_metadata(info).items():
        score = probability_parameter_score(metadata, letter)
        if score >= 0:
            candidates.append((score, name, metadata))
    if not candidates:
        return None
    _, name, metadata = sorted(candidates, key=lambda item: (item[0], item[1]))[-1]
    return name, metadata


def convert_probability(value: Any, metadata: Mapping[str, Any]) -> float | None:
    if value is None:
        return None
    fill = metadata.get("fill")
    if fill is not None and str(value).strip() == str(fill).strip():
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(value))
        if not match:
            return None
        number = float(match.group(0))
    if not math.isfinite(number) or number < 0:
        return None
    units = str(metadata.get("units") or metadata.get("unit") or "").lower()
    if "%" in units or "percent" in units:
        percent = number
    elif number <= 1.000001:
        percent = number * 100.0
    elif number <= 100.000001:
        percent = number
    else:
        return None
    return round(max(0.0, min(100.0, percent)), 2)


def flatten_records(data: Mapping[str, Any], names: list[str]) -> list[dict[str, Any]]:
    rows = data.get("data")
    if not isinstance(rows, list):
        return []
    output: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            output.append(dict(row))
        elif isinstance(row, list):
            output.append({
                names[index] if index < len(names) else f"field_{index}": value
                for index, value in enumerate(row)
            })
    return output


def value_by_name(record: Mapping[str, Any], name: str | None) -> Any:
    if not name:
        return None
    if name in record:
        return record[name]
    target = normalize(name)
    for key, value in record.items():
        if normalize(key) == target:
            return value
    return None


def time_parameter_names(info: Mapping[str, Any]) -> tuple[str | None, str | None, str | None]:
    params = parameter_metadata(info)
    isotimes = [
        name for name, metadata in params.items()
        if normalize(metadata.get("type")) == "isotime"
    ]

    def choose(patterns: Iterable[str]) -> str | None:
        for name in isotimes:
            metadata = params[name]
            text = f"{name} {metadata.get('description', '')} {metadata.get('label', '')}"
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
                return name
        return None

    issue = choose((r"issue", r"forecast.*time", r"submission", r"created", r"^time$"))
    start = choose((r"start.*window", r"window.*start", r"valid.*start", r"begin"))
    end = choose((r"end.*window", r"window.*end", r"valid.*end", r"expire"))
    if issue is None and isotimes:
        issue = isotimes[0]
    return issue, start, end


def overlap_seconds(a_start: dt.datetime, a_end: dt.datetime, b_start: dt.datetime, b_end: dt.datetime) -> float:
    return max(0.0, (min(a_end, b_end) - max(a_start, b_start)).total_seconds())


def robust_fetch_ccmc_member(
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
        info, info_url = legacy.get_json(session, base + "/info", params={"id": dataset_id}, timeout=45)
        names = parameter_names(info)
        m_parameter = select_probability_parameter(info, "m")
        x_parameter = select_probability_parameter(info, "x")
        status.update({
            "info_url": info_url,
            "parameter_names": names,
            "m_parameter": m_parameter[0] if m_parameter else None,
            "x_parameter": x_parameter[0] if x_parameter else None,
        })
        if not m_parameter and not x_parameter:
            status["detail"] = "No M1+/X1+ probability parameters identified from HAPI metadata"
            return None, status

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
        records = flatten_records(data, names)
        status.update({"url": data_url, "records": len(records)})
        if not records:
            status["detail"] = "No records in query window"
            return None, status

        issue_name, start_name, end_name = time_parameter_names(info)
        candidates: list[tuple[tuple[float, float, float], dict[str, Any]]] = []
        for record in records:
            m1 = convert_probability(value_by_name(record, m_parameter[0]), m_parameter[1]) if m_parameter else None
            x1 = convert_probability(value_by_name(record, x_parameter[0]), x_parameter[1]) if x_parameter else None
            if m1 is None and x1 is None:
                continue
            issued = legacy.parse_time(value_by_name(record, issue_name))
            start = legacy.parse_time(value_by_name(record, start_name))
            end = legacy.parse_time(value_by_name(record, end_name))
            if start is None and issued is not None:
                start = issued
            if end is None and start is not None:
                end = start + dt.timedelta(hours=24)
            overlap = overlap_seconds(start, end, valid_start, valid_end) if start and end else 0.0
            future_penalty = max(0.0, (issued - issue_time).total_seconds()) if issued else 0.0
            issue_age = abs((issue_time - issued).total_seconds()) if issued else 1e12
            candidates.append(((overlap, -future_penalty, -issue_age), {
                "m1": m1,
                "x1": x1,
                "issued": issued,
                "start": start,
                "end": end,
                "record": record,
            }))

        if not candidates:
            status["detail"] = "Records existed, but no valid M1+/X1+ probabilities were present"
            return None, status
        selected = sorted(candidates, key=lambda item: item[0])[-1][1]
        issued = selected["issued"]
        start = selected["start"]
        end = selected["end"]
        if issued and issue_time - issued > dt.timedelta(hours=48):
            status["detail"] = f"Latest usable issue is stale ({legacy.iso_z(issued)})"
            return None, status
        if start and end and overlap_seconds(start, end, valid_start, valid_end) < 6 * 3600:
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
            note="Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using parameter metadata.",
            dataset_id=dataset_id,
        )
        status.update({
            "ok": result is not None,
            "issued": legacy.iso_z(issued),
            "valid_start": legacy.iso_z(start),
            "valid_end": legacy.iso_z(end),
            "m1": m1,
            "x1": x1,
            "selected_record": {
                str(key): value for key, value in selected["record"].items()
                if len(str(value)) < 160
            },
        })
        return result, status
    except Exception as exc:
        status["detail"] = f"{type(exc).__name__}: {exc}"
        return None, status


ORIGINAL_FETCH_CATALOG = legacy.fetch_ccmc_catalog
legacy.PROVIDERS = PROVIDERS
legacy.provider_dataset = strict_provider_dataset
legacy.fetch_ccmc_catalog = capture_catalog
legacy.fetch_ccmc_member = robust_fetch_ccmc_member


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add strictly verified SIDC, Met Office, FLARECAST, and CCMC flare guidance")
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
            for item in CATALOG_SNAPSHOT
        ]
        legacy.atomic_write(args.output, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        js_output = args.js_output or args.output.with_name("flare_guidance.js")
        legacy.atomic_write(js_output, legacy.javascript_payload(payload))
        available = sorted(legacy.full_disk_region(payload).get("members", {}).keys())
        print("Strict external guidance update complete; available members: " + ", ".join(available))
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
