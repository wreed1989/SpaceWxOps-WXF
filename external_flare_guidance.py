#!/usr/bin/env python3
"""Add external flare-probability guidance to the SpaceWxOps WXF payload.

Sources:
- SIDC global forecast (direct official page, with CCMC Flare Scoreboard fallback)
- Met Office MOSWOC (NASA/CCMC Flare Scoreboard)
- FLARECAST (official XML archive/latest feed; values accepted only when current)
- NASA/CCMC Flare Scoreboard models: MagPy, DAFFS, and A-EFFort

The script never invents a probability. A source that is unavailable, stale, or
ambiguous is recorded in ``external_sources`` but omitted from the probability
members, causing the dashboard row to display ``--``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterable, Mapping
import xml.etree.ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UTC = dt.timezone.utc
SCRIPT_VERSION = "1.0.0"

CCMC_BASES = (
    "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi",
    "https://iswa.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi",
)
SIDC_URL = "https://www.sidc.be/WMO/FlareForecast.php"
FLARECAST_HOME = "https://api.flarecast.eu/"
FLARECAST_LATEST = "https://api.flarecast.eu/api/prediction/flarecast_latest.xml"

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
        "patterns": (r"met office", r"moswoc", r"^mo[_-]"),
        "fallback_ids": ("MO_TOT1_FULLDISK",),
    },
    {
        "key": "ccmc_magpy",
        "label": "CCMC MagPy",
        "patterns": (r"magpy",),
        "fallback_ids": (),
    },
    {
        "key": "ccmc_daffs",
        "label": "CCMC DAFFS",
        "patterns": (r"daffs", r"discriminant analysis flare"),
        "fallback_ids": (),
    },
    {
        "key": "ccmc_aeffort",
        "label": "CCMC A-EFFort",
        "patterns": (r"a[-_ ]?effort", r"athens effective solar flare"),
        "fallback_ids": (),
    },
)


class ExternalGuidanceError(RuntimeError):
    pass


def session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update(
        {
            "User-Agent": (
                f"SpaceWxOps-External-Flare-Guidance/{SCRIPT_VERSION} "
                "(research comparison display; contact repository owner)"
            ),
            "Accept": "application/json,text/html,application/xml,text/xml,*/*",
        }
    )
    return s


def parse_time(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan", "----", "-1"}:
        return None
    text = text.replace("/", "-")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    text = re.sub(r"\s+at\s+", "T", text, flags=re.IGNORECASE)
    text = text.replace(" UTC", "+00:00").replace(" UT", "+00:00")
    candidates = [text]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?", text):
        candidates.append(text + "+00:00")
    for candidate in candidates:
        try:
            parsed = dt.datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%dT%H%M%S", "%Y%m%d%H%M"):
        try:
            return dt.datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def iso_z(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def probability_percent(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace("%", "")
    if not text or text.lower() in {"none", "null", "nan", "----", "...", "-1"}:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    if not math.isfinite(number) or number < 0:
        return None
    if number <= 1.000001:
        number *= 100.0
    if number > 100.000001:
        return None
    return round(max(0.0, min(100.0, number)), 2)


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


def javascript_payload(payload: Mapping[str, Any]) -> str:
    return (
        "/* Generated automatically by the SpaceWxOps WXF workflow. */\n"
        "window.FLARE_GUIDANCE_PAYLOAD = "
        + json.dumps(payload, indent=2, ensure_ascii=False)
        + ";\n"
    )


def full_disk_region(payload: dict[str, Any]) -> dict[str, Any]:
    regions = payload.setdefault("regions", [])
    if not isinstance(regions, list):
        raise ExternalGuidanceError("payload.regions must be a list")
    for row in regions:
        if isinstance(row, dict) and str(row.get("id", "")).lower() == "full-disk":
            row.setdefault("members", {})
            return row
    row = {"id": "full-disk", "label": "Full Disk", "members": {}}
    regions.insert(0, row)
    return row


def member(
    *,
    m1: float | None,
    x1: float | None,
    source: str,
    issued: dt.datetime | None = None,
    valid_start: dt.datetime | None = None,
    valid_end: dt.datetime | None = None,
    quality: str = "published-comparison",
    note: str | None = None,
    dataset_id: str | None = None,
) -> dict[str, Any] | None:
    if m1 is None and x1 is None:
        return None
    if m1 is not None and x1 is not None:
        x1 = min(x1, m1)
    result: dict[str, Any] = {
        "m1": m1,
        "x1": x1,
        "source": source,
        "quality": quality,
    }
    if issued:
        result["issued"] = iso_z(issued)
    if valid_start:
        result["valid_start"] = iso_z(valid_start)
    if valid_end:
        result["valid_end"] = iso_z(valid_end)
    if note:
        result["note"] = note
    if dataset_id:
        result["dataset_id"] = dataset_id
    return result


def get_json(s: requests.Session, url: str, *, params: Mapping[str, Any] | None = None, timeout: float = 45) -> tuple[dict[str, Any], str]:
    response = s.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ExternalGuidanceError(f"Expected object from {response.url}")
    return data, response.url


def fetch_ccmc_catalog(s: requests.Session) -> tuple[list[dict[str, Any]], str]:
    errors: list[str] = []
    for base in CCMC_BASES:
        try:
            data, url = get_json(s, base + "/catalog")
            catalog = data.get("catalog")
            if isinstance(catalog, list) and catalog:
                return [row for row in catalog if isinstance(row, dict)], url
            errors.append(f"{base}: empty catalog")
        except Exception as exc:
            errors.append(f"{base}: {type(exc).__name__}: {exc}")
    raise ExternalGuidanceError("CCMC catalog unavailable: " + " | ".join(errors))


def provider_dataset(provider: Mapping[str, Any], catalog: list[dict[str, Any]]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for item in catalog:
        dataset_id = str(item.get("id") or "").strip()
        if not dataset_id or "FULLDISK" not in dataset_id.upper():
            continue
        haystack = f"{dataset_id} {item.get('title', '')}".lower()
        score = 0
        for pattern in provider.get("patterns", ()):
            if re.search(pattern, haystack, flags=re.IGNORECASE):
                score += 10
        if dataset_id.upper().endswith("_FULLDISK"):
            score += 2
        if re.search(r"(?:v?3|0[._-]?37|1[._-]?0)", dataset_id, flags=re.IGNORECASE):
            score += 1
        if score:
            candidates.append((score, dataset_id))
    if candidates:
        return sorted(candidates, key=lambda pair: (pair[0], pair[1]))[-1][1]
    for dataset_id in provider.get("fallback_ids", ()):
        return str(dataset_id)
    return None


def flatten_hapi_records(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    parameters = data.get("parameters")
    rows = data.get("data")
    if not isinstance(rows, list):
        return []
    names: list[str] = []
    if isinstance(parameters, list):
        for parameter in parameters:
            if isinstance(parameter, dict):
                names.append(str(parameter.get("name") or parameter.get("id") or ""))
            else:
                names.append(str(parameter))
    output: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            output.append(dict(row))
        elif isinstance(row, list):
            if not names:
                names = [f"field_{index}" for index in range(len(row))]
            output.append({names[index] if index < len(names) else f"field_{index}": value for index, value in enumerate(row)})
    return output


def normalized_map(record: Mapping[str, Any]) -> dict[str, Any]:
    return {re.sub(r"[^a-z0-9]+", "", str(key).lower()): value for key, value in record.items()}


def first_value(record: Mapping[str, Any], names: Iterable[str]) -> Any:
    normalized = normalized_map(record)
    for name in names:
        key = re.sub(r"[^a-z0-9]+", "", name.lower())
        if key in normalized:
            return normalized[key]
    return None


def hapi_record_times(record: Mapping[str, Any]) -> tuple[dt.datetime | None, dt.datetime | None, dt.datetime | None]:
    issued = parse_time(first_value(record, ("Time", "issue_time", "issuetime", "timestamp", "date")))
    start = parse_time(first_value(record, ("start_window", "startwindow", "prediction_window_start", "valid_start", "start")))
    end = parse_time(first_value(record, ("end_window", "endwindow", "prediction_window_end", "valid_end", "end")))
    if issued is None:
        for value in record.values():
            candidate = parse_time(value)
            if candidate:
                issued = candidate
                break
    return issued, start, end


def overlap_seconds(a_start: dt.datetime, a_end: dt.datetime, b_start: dt.datetime, b_end: dt.datetime) -> float:
    return max(0.0, (min(a_end, b_end) - max(a_start, b_start)).total_seconds())


def select_hapi_forecast(
    records: list[dict[str, Any]],
    *,
    issue_time: dt.datetime,
    valid_start: dt.datetime,
    valid_end: dt.datetime,
) -> tuple[dict[str, Any], dt.datetime | None, dt.datetime | None, dt.datetime | None] | None:
    candidates: list[tuple[tuple[float, float, float], dict[str, Any], dt.datetime | None, dt.datetime | None, dt.datetime | None]] = []
    for record in records:
        m1 = probability_percent(first_value(record, ("M", "M_prob", "Mprob", "probability_M", "m1")))
        x1 = probability_percent(first_value(record, ("X", "X_prob", "Xprob", "probability_X", "x1")))
        if m1 is None and x1 is None:
            continue
        issued, start, end = hapi_record_times(record)
        overlap = overlap_seconds(start, end, valid_start, valid_end) if start and end else 0.0
        issue_age = abs((issue_time - issued).total_seconds()) if issued else 1e12
        future_penalty = max(0.0, (issued - issue_time).total_seconds()) if issued else 0.0
        score = (overlap, -future_penalty, -issue_age)
        record_copy = dict(record)
        record_copy["__m1"] = m1
        record_copy["__x1"] = x1
        candidates.append((score, record_copy, issued, start, end))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[-1][1:]


def fetch_ccmc_member(
    s: requests.Session,
    *,
    base: str,
    dataset_id: str,
    label: str,
    issue_time: dt.datetime,
    valid_start: dt.datetime,
    valid_end: dt.datetime,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    query_min = issue_time - dt.timedelta(days=3)
    query_max = issue_time + dt.timedelta(days=1)
    params = {
        "id": dataset_id,
        "time.min": query_min.strftime("%Y-%m-%dT%H:%M:%S.0"),
        "time.max": query_max.strftime("%Y-%m-%dT%H:%M:%S.0"),
        "format": "json",
        "options": "fields.all",
    }
    status: dict[str, Any] = {"dataset_id": dataset_id, "label": label, "ok": False}
    try:
        data, url = get_json(s, base + "/data", params=params, timeout=60)
        records = flatten_hapi_records(data)
        selected = select_hapi_forecast(
            records,
            issue_time=issue_time,
            valid_start=valid_start,
            valid_end=valid_end,
        )
        status.update({"url": url, "records": len(records)})
        if not selected:
            status["detail"] = "No M/X probability record in query window"
            return None, status
        record, issued, start, end = selected
        m1 = record.pop("__m1", None)
        x1 = record.pop("__x1", None)
        if issued and issue_time - issued > dt.timedelta(days=3):
            status["detail"] = f"Latest issue is stale ({iso_z(issued)})"
            return None, status
        if start and end and overlap_seconds(start, end, valid_start, valid_end) < 6 * 3600:
            status["detail"] = f"Forecast window does not meaningfully overlap target ({iso_z(start)} to {iso_z(end)})"
            return None, status
        result = member(
            m1=m1,
            x1=x1,
            source=f"NASA/CCMC Flare Scoreboard · {label}",
            issued=issued,
            valid_start=start,
            valid_end=end,
            note="Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed.",
            dataset_id=dataset_id,
        )
        status.update(
            {
                "ok": result is not None,
                "issued": iso_z(issued),
                "valid_start": iso_z(start),
                "valid_end": iso_z(end),
                "m1": m1,
                "x1": x1,
            }
        )
        return result, status
    except Exception as exc:
        status["detail"] = f"{type(exc).__name__}: {exc}"
        return None, status


def parse_sidc_direct(document: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    text = re.sub(r"<[^>]+>", " ", document)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    issued_match = re.search(r"Issued\s*:\s*(\d{4}-\d{2}-\d{2})\s*(?:at)?\s*(\d{2}:\d{2}:\d{2})", text, flags=re.IGNORECASE)
    m_match = re.search(r"Forecast\s+for\s+M[- ]?type\s+flares\s*:\s*([0-9.]+\s*%?)", text, flags=re.IGNORECASE)
    x_match = re.search(r"Forecast\s+for\s+X[- ]?type\s+flares\s*:\s*([0-9.]+\s*%?)", text, flags=re.IGNORECASE)
    issued = parse_time(f"{issued_match.group(1)}T{issued_match.group(2)}") if issued_match else None
    m1 = probability_percent(m_match.group(1)) if m_match else None
    x1 = probability_percent(x_match.group(1)) if x_match else None
    result = member(
        m1=m1,
        x1=x1,
        source="SIDC 24-hour Global Flare Forecast",
        issued=issued,
        valid_start=issued,
        valid_end=issued + dt.timedelta(hours=24) if issued else None,
        note="Human-operator-moderated global forecast published by SIDC.",
    )
    return result, {"ok": result is not None, "issued": iso_z(issued), "m1": m1, "x1": x1, "url": SIDC_URL}


def fetch_sidc_direct(s: requests.Session, *, issue_time: dt.datetime) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    status: dict[str, Any] = {"ok": False, "url": SIDC_URL}
    try:
        response = s.get(SIDC_URL, timeout=45)
        response.raise_for_status()
        result, parsed = parse_sidc_direct(response.text)
        status.update(parsed)
        if result and result.get("issued"):
            issued = parse_time(result["issued"])
            if issued and issue_time - issued > dt.timedelta(hours=60):
                status.update({"ok": False, "detail": f"Direct SIDC forecast stale: {iso_z(issued)}"})
                return None, status
        return result, status
    except Exception as exc:
        status["detail"] = f"{type(exc).__name__}: {exc}"
        return None, status


def local_name(tag: str) -> str:
    return tag.split("}")[-1].split(":")[-1].lower()


def leaf_texts(element: ET.Element, *, max_depth: int = 4) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}

    def visit(node: ET.Element, depth: int) -> None:
        if depth > max_depth:
            return
        children = list(node)
        name = local_name(node.tag)
        text = (node.text or "").strip()
        if text and not children:
            result.setdefault(name, []).append(text)
        for attr, value in node.attrib.items():
            result.setdefault(local_name(attr), []).append(str(value))
        for child in children:
            visit(child, depth + 1)

    visit(element, 0)
    return result


def first_map_value(mapping: Mapping[str, list[str]], patterns: Iterable[str]) -> str | None:
    for pattern in patterns:
        regex = re.compile(pattern, flags=re.IGNORECASE)
        for key, values in mapping.items():
            if regex.search(key):
                for value in values:
                    if str(value).strip():
                        return str(value).strip()
    return None


def parse_flarecast_xml(xml_text: str, *, issue_time: dt.datetime) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    root = ET.fromstring(xml_text)
    candidates: list[dict[str, Any]] = []
    for element in root.iter():
        values = leaf_texts(element)
        if not values:
            continue
        flat_keys = " ".join(values)
        if not re.search(r"prob|forecast|prediction", flat_keys, flags=re.IGNORECASE):
            continue
        region_text = first_map_value(values, (r"noaa", r"active.*region", r"region.*number"))
        class_text = first_map_value(values, (r"flare.*class", r"goes.*class", r"threshold", r"class$"))
        generic_prob = first_map_value(values, (r"probability", r"prob$", r"prediction.*value"))
        m_text = first_map_value(values, (r"^m$", r"m.*prob", r"prob.*m"))
        x_text = first_map_value(values, (r"^x$", r"x.*prob", r"prob.*x"))
        m1 = probability_percent(m_text)
        x1 = probability_percent(x_text)
        if generic_prob is not None and class_text:
            p = probability_percent(generic_prob)
            if re.search(r"\bM", class_text, flags=re.IGNORECASE):
                m1 = p
            elif re.search(r"\bX", class_text, flags=re.IGNORECASE):
                x1 = p
        if m1 is None and x1 is None:
            continue
        issued = parse_time(first_map_value(values, (r"issue", r"forecast.*date", r"prediction.*time", r"created")))
        start = parse_time(first_map_value(values, (r"start", r"from", r"valid.*begin")))
        end = parse_time(first_map_value(values, (r"end", r"until", r"valid.*end")))
        region_match = re.search(r"\d{4,6}", region_text or "")
        region = int(region_match.group(0)) if region_match else None
        candidates.append({"region": region, "m1": m1, "x1": x1, "issued": issued, "start": start, "end": end})

    if not candidates:
        return None, {"ok": False, "detail": "XML contained no parseable current M/X probabilities", "candidate_count": 0}

    dated = [row for row in candidates if row.get("issued")]
    latest_issue = max((row["issued"] for row in dated), default=None)
    if latest_issue and issue_time - latest_issue > dt.timedelta(days=3):
        return None, {
            "ok": False,
            "detail": f"Latest FLARECAST XML forecast is stale ({iso_z(latest_issue)})",
            "candidate_count": len(candidates),
        }
    latest = [row for row in candidates if not latest_issue or row.get("issued") == latest_issue]
    m1 = max((row["m1"] for row in latest if row.get("m1") is not None), default=None)
    x1 = max((row["x1"] for row in latest if row.get("x1") is not None), default=None)
    start = min((row["start"] for row in latest if row.get("start")), default=latest_issue)
    end = max((row["end"] for row in latest if row.get("end")), default=(start + dt.timedelta(hours=24) if start else None))
    result = member(
        m1=m1,
        x1=x1,
        source="FLARECAST Random Forest forecast",
        issued=latest_issue,
        valid_start=start,
        valid_end=end,
        quality="experimental-published-comparison",
        note="Highest current regional probability from the official FLARECAST XML feed; omitted when the feed is stale or under maintenance.",
    )
    return result, {
        "ok": result is not None,
        "candidate_count": len(candidates),
        "issued": iso_z(latest_issue),
        "m1": m1,
        "x1": x1,
    }


def fetch_flarecast(s: requests.Session, *, issue_time: dt.datetime) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    status: dict[str, Any] = {"ok": False, "url": FLARECAST_LATEST}
    try:
        s.get(FLARECAST_HOME, timeout=30)
        response = s.get(FLARECAST_LATEST, timeout=60)
        status.update({"http_status": response.status_code, "content_length": len(response.content)})
        response.raise_for_status()
        result, parsed = parse_flarecast_xml(response.text, issue_time=issue_time)
        status.update(parsed)
        return result, status
    except Exception as exc:
        status["detail"] = f"{type(exc).__name__}: {exc}"
        return None, status


def enrich(payload: dict[str, Any]) -> dict[str, Any]:
    issue_time = parse_time(payload.get("issued")) or dt.datetime.now(tz=UTC)
    valid_start = parse_time(payload.get("valid_start")) or issue_time
    valid_end = parse_time(payload.get("valid_end")) or (valid_start + dt.timedelta(hours=24))
    full = full_disk_region(payload)
    members = full.setdefault("members", {})
    statuses: dict[str, Any] = {
        "generated_at": iso_z(dt.datetime.now(tz=UTC)),
        "script_version": SCRIPT_VERSION,
    }
    s = session()

    sidc_member, sidc_status = fetch_sidc_direct(s, issue_time=issue_time)
    statuses["sidc_direct"] = sidc_status
    if sidc_member:
        members["sidc"] = sidc_member

    try:
        catalog, catalog_url = fetch_ccmc_catalog(s)
        statuses["ccmc_catalog"] = {"ok": True, "url": catalog_url, "datasets": len(catalog)}
        base = catalog_url.rsplit("/catalog", 1)[0]
        for provider in PROVIDERS:
            dataset_id = provider_dataset(provider, catalog)
            provider_status: dict[str, Any] = {"ok": False, "label": provider["label"], "dataset_id": dataset_id}
            result = None
            if dataset_id:
                result, provider_status = fetch_ccmc_member(
                    s,
                    base=base,
                    dataset_id=dataset_id,
                    label=provider["label"],
                    issue_time=issue_time,
                    valid_start=valid_start,
                    valid_end=valid_end,
                )
            else:
                provider_status["detail"] = "No matching full-disk dataset in current CCMC catalog"
            statuses[f"ccmc_{provider['key']}"] = provider_status
            if result and (provider["key"] != "sidc" or "sidc" not in members):
                members[provider["key"]] = result
    except Exception as exc:
        statuses["ccmc_catalog"] = {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}

    flarecast_member, flarecast_status = fetch_flarecast(s, issue_time=issue_time)
    statuses["flarecast"] = flarecast_status
    if flarecast_member:
        members["flarecast"] = flarecast_member

    current_keys = {"sidc", "metoffice", "flarecast", "ccmc_magpy", "ccmc_daffs", "ccmc_aeffort"}
    for key in current_keys:
        relevant_statuses = [value for status_key, value in statuses.items() if status_key.endswith(key) or status_key == key or (key == "sidc" and status_key == "sidc_direct")]
        if key not in members:
            continue
        if key == "sidc" and sidc_member:
            continue
        if not any(isinstance(value, dict) and value.get("ok") for value in relevant_statuses):
            members.pop(key, None)

    payload["external_sources"] = statuses
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add current SIDC, Met Office, FLARECAST, and NASA/CCMC flare guidance")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--js-output", type=Path)
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ExternalGuidanceError("payload root must be an object")
        payload = enrich(payload)
        atomic_write(args.output, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        js_output = args.js_output or args.output.with_name("flare_guidance.js")
        atomic_write(js_output, javascript_payload(payload))
        available = sorted(full_disk_region(payload).get("members", {}).keys())
        print("External flare guidance update complete; available members: " + ", ".join(available))
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
