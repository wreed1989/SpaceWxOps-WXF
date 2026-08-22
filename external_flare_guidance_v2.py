#!/usr/bin/env python3
"""Reliable current-source wrapper for SpaceWxOps external flare guidance.

Uses the existing source parsers for direct SIDC and FLARECAST, but replaces
CCMC dataset discovery and HAPI record mapping with stricter logic.  Only a
current forecast is written to the dashboard payload; stale/unavailable sources
remain diagnostic-only in ``external_sources``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence

import requests

import external_flare_guidance as legacy

UTC = dt.timezone.utc
SCRIPT_VERSION = "2.0.0"

PROVIDERS: tuple[dict[str, Any], ...] = (
    {"key": "sidc", "label": "SIDC", "patterns": (r"sidc",), "fallback": "SIDC_Operator_FULLDISK"},
    {"key": "metoffice", "label": "Met Office", "patterns": (r"met[ _-]*office", r"moswoc", r"^mo[_-]"), "fallback": "MO_TOT1_FULLDISK"},
    {"key": "ccmc_magpy", "label": "NASA MagPy", "patterns": (r"magpy",), "fallback": "MagPy_SHARP_HMI_CEA_FULLDISK"},
    {"key": "ccmc_daffs", "label": "NASA DAFFS", "patterns": (r"daffs", r"discriminant analysis flare"), "fallback": None},
    {"key": "ccmc_aeffort", "label": "NASA A-EFFort", "patterns": (r"a[-_ ]?effort", r"aeffort", r"effective connected magnetic", r"\bbeff\b"), "fallback": None},
)
EXTERNAL_KEYS = {"sidc", "metoffice", "flarecast", "ccmc_magpy", "ccmc_daffs", "ccmc_aeffort"}


def now_utc() -> dt.datetime:
    return dt.datetime.now(tz=UTC)


def normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def atomic_write(path: Path, text: str) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def provider_dataset(provider: Mapping[str, Any], catalog: Sequence[Mapping[str, Any]]) -> str | None:
    catalog_ids = {str(item.get("id") or "") for item in catalog}
    candidates: list[tuple[int, str]] = []
    for item in catalog:
        dataset_id = str(item.get("id") or "").strip()
        if not dataset_id or "FULLDISK" not in dataset_id.upper():
            continue
        haystack = f"{dataset_id} {item.get('title', '')}"
        matches = sum(1 for pattern in provider["patterns"] if re.search(pattern, haystack, re.I))
        if not matches:
            continue
        score = matches * 100 + (10 if dataset_id.upper().endswith("_FULLDISK") else 0)
        candidates.append((score, dataset_id))
    if candidates:
        return max(candidates)[1]
    fallback = provider.get("fallback")
    return str(fallback) if fallback and str(fallback) in catalog_ids else None


def info_names(info: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for item in info.get("parameters") or []:
        value = item.get("name") or item.get("id") if isinstance(item, Mapping) else item
        if value:
            result.append(str(value))
    return result


def response_records(data: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    names: list[str] = []
    for item in data.get("parameters") or []:
        value = item.get("name") or item.get("id") if isinstance(item, Mapping) else item
        if value:
            names.append(str(value))
    records: list[dict[str, Any]] = []
    for row in data.get("data") or []:
        if isinstance(row, Mapping):
            records.append(dict(row))
        elif isinstance(row, list):
            mapped_names = names if len(names) == len(row) else ["Time", "start_window", "end_window", "M", "X"]
            if len(mapped_names) != len(row):
                mapped_names = [f"field_{index}" for index in range(len(row))]
            records.append({mapped_names[index]: value for index, value in enumerate(row)})
    return records, names


def first(record: Mapping[str, Any], aliases: Iterable[str]) -> Any:
    lookup = {normalized(key): value for key, value in record.items()}
    for alias in aliases:
        key = normalized(alias)
        if key in lookup:
            return lookup[key]
    return None


def record_values(record: Mapping[str, Any]) -> tuple[dt.datetime | None, dt.datetime | None, dt.datetime | None, float | None, float | None]:
    issued = legacy.parse_time(first(record, ("Time", "issue_time", "timestamp", "date")))
    start = legacy.parse_time(first(record, ("start_window", "prediction_window_start", "valid_start", "start")))
    end = legacy.parse_time(first(record, ("end_window", "prediction_window_end", "valid_end", "end")))
    m1 = legacy.probability_percent(first(record, ("M", "M_prob", "M_probability", "probability_M", "M1", "M1+")))
    x1 = legacy.probability_percent(first(record, ("X", "X_prob", "X_probability", "probability_X", "X1", "X1+")))
    return issued, start, end, m1, x1


def overlap(a0: dt.datetime, a1: dt.datetime, b0: dt.datetime, b1: dt.datetime) -> float:
    return max(0.0, (min(a1, b1) - max(a0, b0)).total_seconds())


def choose_current(
    records: Sequence[Mapping[str, Any]],
    *,
    now: dt.datetime,
    target_start: dt.datetime,
    target_end: dt.datetime,
) -> tuple[dict[str, Any], dt.datetime | None, dt.datetime | None, dt.datetime | None, float | None, float | None] | None:
    ranked: list[tuple[tuple[float, float, float], tuple[Any, ...]]] = []
    for raw in records:
        issued, start, end, m1, x1 = record_values(raw)
        if m1 is None and x1 is None:
            continue
        if issued and (issued > now + dt.timedelta(hours=3) or now - issued > dt.timedelta(days=4)):
            continue
        if end and end < now - dt.timedelta(hours=1):
            continue
        if start and start > now + dt.timedelta(hours=12):
            continue
        current_overlap = overlap(start, end, now, now + dt.timedelta(hours=24)) if start and end else 0.0
        target_overlap = overlap(start, end, target_start, target_end) if start and end else 0.0
        recency = issued.timestamp() if issued else -1.0
        ranked.append(((current_overlap, target_overlap, recency), (dict(raw), issued, start, end, m1, x1)))
    return max(ranked, key=lambda item: item[0])[1] if ranked else None


def ccmc_member(
    session: requests.Session,
    *,
    base: str,
    dataset_id: str,
    label: str,
    now: dt.datetime,
    target_start: dt.datetime,
    target_end: dt.datetime,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    status: dict[str, Any] = {"ok": False, "dataset_id": dataset_id, "label": label}
    try:
        info, info_url = legacy.get_json(session, base + "/info", params={"id": dataset_id, "options": "fields.all"})
        requested = "start_window,end_window,M,X"
        data, data_url = legacy.get_json(
            session,
            base + "/data",
            params={
                "id": dataset_id,
                "time.min": (now - dt.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S.0"),
                "time.max": (now + dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.0"),
                "parameters": requested,
                "format": "json",
                "options": "fields.all",
            },
            timeout=60,
        )
        records, response_parameters = response_records(data)
        selected = choose_current(records, now=now, target_start=target_start, target_end=target_end)
        status.update(
            {
                "info_url": info_url,
                "url": data_url,
                "info_parameters": info_names(info),
                "requested_parameters": requested.split(","),
                "response_parameters": response_parameters,
                "records": len(records),
                "sample_record": records[-1] if records else None,
            }
        )
        if selected is None:
            newest = max((record_values(row)[0] for row in records if record_values(row)[0]), default=None)
            status["detail"] = f"No current valid M1+/X1+ record; newest issue={legacy.iso_z(newest)}"
            return None, status
        record, issued, start, end, m1, x1 = selected
        result = legacy.member(
            m1=m1,
            x1=x1,
            source=f"NASA/CCMC Flare Scoreboard · {label}",
            issued=issued,
            valid_start=start,
            valid_end=end,
            note="Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI service.",
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
                "selected_record": record,
            }
        )
        return result, status
    except Exception as exc:
        status["detail"] = f"{type(exc).__name__}: {exc}"
        return None, status


def sidc_current(result: Mapping[str, Any] | None, *, now: dt.datetime) -> bool:
    if not result:
        return False
    issued = legacy.parse_time(result.get("issued"))
    end = legacy.parse_time(result.get("valid_end"))
    return bool(issued and now - issued <= dt.timedelta(hours=60) and (end is None or end >= now - dt.timedelta(hours=1)))


def enrich(payload: dict[str, Any]) -> dict[str, Any]:
    now = now_utc()
    target_start = legacy.parse_time(payload.get("valid_start")) or now
    target_end = legacy.parse_time(payload.get("valid_end")) or target_start + dt.timedelta(hours=24)
    full = legacy.full_disk_region(payload)
    members = full.setdefault("members", {})
    for key in EXTERNAL_KEYS:
        members.pop(key, None)

    statuses: dict[str, Any] = {
        "generated_at": legacy.iso_z(now),
        "script_version": SCRIPT_VERSION,
        "target_valid_start": legacy.iso_z(target_start),
        "target_valid_end": legacy.iso_z(target_end),
    }
    session = legacy.session()

    sidc, sidc_status = legacy.fetch_sidc_direct(session, issue_time=now)
    statuses["sidc_direct"] = sidc_status
    if sidc_current(sidc, now=now):
        members["sidc"] = sidc

    try:
        catalog, catalog_url = legacy.fetch_ccmc_catalog(session)
        base = catalog_url.rsplit("/catalog", 1)[0]
        statuses["ccmc_catalog"] = {
            "ok": True,
            "url": catalog_url,
            "datasets": len(catalog),
            "catalog": [
                {"id": str(item.get("id") or ""), "title": str(item.get("title") or "")}
                for item in catalog
            ],
        }
        for provider in PROVIDERS:
            dataset_id = provider_dataset(provider, catalog)
            if dataset_id:
                result, status = ccmc_member(
                    session,
                    base=base,
                    dataset_id=dataset_id,
                    label=provider["label"],
                    now=now,
                    target_start=target_start,
                    target_end=target_end,
                )
            else:
                result = None
                status = {
                    "ok": False,
                    "label": provider["label"],
                    "dataset_id": None,
                    "detail": "No matching current full-disk dataset in CCMC catalog",
                }
            statuses[f"ccmc_{provider['key']}"] = status
            key = provider["key"]
            if result and (key != "sidc" or "sidc" not in members):
                members[key] = result
    except Exception as exc:
        statuses["ccmc_catalog"] = {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}

    flarecast, flarecast_status = legacy.fetch_flarecast(session, issue_time=now)
    statuses["flarecast"] = flarecast_status
    if flarecast:
        members["flarecast"] = flarecast

    payload["external_sources"] = statuses
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add current SIDC, Met Office, FLARECAST, and NASA/CCMC forecasts")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--js-output", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("payload root must be an object")
        payload = enrich(payload)
        atomic_write(args.output, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        js_path = args.js_output or args.output.with_name("flare_guidance.js")
        atomic_write(js_path, legacy.javascript_payload(payload))
        available = sorted(legacy.full_disk_region(payload).get("members", {}).keys())
        print("External flare guidance complete; available members: " + ", ".join(available))
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
