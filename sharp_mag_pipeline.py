#!/usr/bin/env python3
"""
WXF research training and daily forecast pipeline.

Purpose
-------
Build a compact, scalar-parameter training table from SDO/HMI SHARP NRT
records, train calibrated M1+ and magnetic-structure-dependent X1+ models, and generate a
small ``flare_guidance.json`` file that the SpaceWxOps HTML dashboard already
knows how to ingest.

The operational daily path does NOT retrain the model.  Training/calibration is
performed locally and saved as joblib artifacts.  A scheduled 21Z ``forecast``
run only retrieves the latest SHARP keywords, loads the saved artifacts, and
writes the next-UTC-day probabilities.

This is research guidance.  Keep ``operational`` false until independent
backtesting and shadow verification demonstrate acceptable calibration and
skill for the intended mission.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime as dt
import hashlib
import importlib.metadata
import json
import logging
import math
import os
import re
import shutil
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence
from urllib.parse import urljoin

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import joblib
    import numpy as np
    import pandas as pd
    import requests
    from sklearn.base import clone
    from sklearn.calibration import calibration_curve
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
        log_loss,
        roc_auc_score,
    )
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except ImportError as exc:  # pragma: no cover - user-facing dependency check
    missing = getattr(exc, "name", "a required package")
    raise SystemExit(
        f"Missing dependency {missing!r}. Install requirements first:\n"
        "  python -m pip install -r requirements-sharp-mag.txt"
    ) from exc

try:
    from sklearn.model_selection import StratifiedGroupKFold
except ImportError:  # pragma: no cover - compatibility with older sklearn
    StratifiedGroupKFold = None  # type: ignore[assignment]


UTC = dt.timezone.utc
LOGGER = logging.getLogger("sharp_mag")

DEFAULT_HISTORICAL_SERIES = "hmi.sharp_cea_720s_nrt"
DEFAULT_LIVE_SERIES = "hmi.sharp_cea_720s_nrt"
DEFAULT_START_DATE = dt.date(2012, 10, 1)
DEFAULT_ISSUE_HOUR = 21
DEFAULT_INPUT_LAG_HOURS = 3
DEFAULT_MAX_LONGITUDE = 50.0
DEFAULT_MAX_OBS_VR = 3500.0
DEFAULT_MAX_QUALITY = 0xFFFFFFFF  # diagnostic-only by default; QUALITY is a bitmask
DEFAULT_MIN_FINITE_PARAMETERS = 12
DEFAULT_MAX_INPUT_AGE_HOURS = 8.0
DEFAULT_CHUNK_DAYS = 31
SCHEMA_VERSION = "5.0"
SCRIPT_VERSION = "2.0.0"

# Jeffreys' prior is retained only for the constant-severity reference scored
# beside the magnetic X1+ model. It is not used for production inference.
X1_SEVERITY_PRIOR_ALPHA = 0.5
X1_SEVERITY_PRIOR_BETA = 0.5

NCEI_FLARE_DIRECTORY = (
    "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/"
    "goes/multi/l2/data/xrsf-l2-flrpt_science/csv/"
)
NCEI_SOLAR_EVENT_REPORT_ROOT = (
    "https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/"
    "daily_reports/solar_event_reports"
)
SWPC_SOLAR_REGIONS_URL = "https://services.swpc.noaa.gov/json/solar_regions.json"
SWPC_EDITED_EVENTS_URL = "https://services.swpc.noaa.gov/json/edited_events.json"
SWPC_THREE_DAY_URL = "https://services.swpc.noaa.gov/text/3-day-solar-geomag-predictions.txt"

# Scalar SHARP parameters used in many flare-prediction studies.  These are
# keyword values, not FITS image segments, which keeps both training and live
# inference storage modest.
SHARP_PARAMETERS: tuple[str, ...] = (
    "USFLUX",
    "MEANGBT",
    "MEANJZH",
    "MEANPOT",
    "SHRGT45",
    "TOTUSJH",
    "MEANGBH",
    "MEANALP",
    "MEANGAM",
    "MEANGBZ",
    "MEANJZD",
    "TOTUSJZ",
    "SAVNCPP",
    "TOTPOT",
    "MEANSHR",
    "AREA_ACR",
    "R_VALUE",
    "ABSNJZH",
)

# A pre-specified reduced feature family for the rare-event severity stage.
# It concentrates capacity on free energy, current, flux, strong-gradient PIL,
# shear, and size rather than fitting every available scalar to the small X set.
X1_SEVERITY_PARAMETERS: tuple[str, ...] = (
    "R_VALUE",
    "TOTPOT",
    "TOTUSJH",
    "TOTUSJZ",
    "SAVNCPP",
    "USFLUX",
    "AREA_ACR",
    "SHRGT45",
    "MEANSHR",
    "ABSNJZH",
)

HISTORY_RAW_COLUMNS: tuple[str, ...] = (
    "PRIOR_M1_COUNT_24H",
    "PRIOR_M1_COUNT_7D",
    "PRIOR_M1_COUNT_30D",
    "PRIOR_X1_COUNT_7D",
    "PRIOR_X1_COUNT_30D",
    "HOURS_SINCE_M1",
    "HOURS_SINCE_X1",
)

# Bloomfield et al. (2012) 24-hour McIntosh-Poisson probabilities. This is a
# transparent coverage fallback for numbered regions without a trustworthy
# live SHARP mapping; it is never represented as a magnetic-model prediction.
LEGACY_MCSTAT_B12: dict[str, tuple[float, float]] = {
    "AXX": (1, 0), "BXO": (1, 0), "BXI": (6, 0),
    "HRX": (2, 0), "HSX": (3, 0), "HAX": (3, 0), "HHX": (9, 1), "HKX": (10, 0),
    "CRO": (2, 0), "CRI": (4, 0), "CSO": (3, 0), "CSI": (9, 1),
    "CAO": (3, 0), "CAI": (12, 0), "CHO": (6, 1), "CHI": (18, 0),
    "CKO": (13, 1), "CKI": (27, 4),
    "DRO": (6, 0), "DRI": (13, 2), "DSO": (7, 1), "DSI": (12, 0),
    "DSC": (30, 10), "DAO": (7, 0), "DAI": (18, 2), "DAC": (26, 2),
    "DHO": (14, 1), "DHI": (7, 0), "DHC": (28, 0), "DKO": (25, 3),
    "DKI": (33, 4), "DKC": (54, 9),
    "ESO": (11, 0), "ESI": (23, 2), "EAO": (14, 1), "EAI": (30, 1),
    "EAC": (39, 14), "EHO": (14, 0), "EHI": (47, 6), "EHC": (74, 0),
    "EKO": (22, 2), "EKI": (46, 7), "EKC": (85, 20),
    "FRI": (39, 0), "FSO": (31, 4), "FSI": (66, 0), "FAO": (19, 0),
    "FAI": (36, 3), "FHO": (5, 0), "FHI": (58, 0), "FHC": (55, 0),
    "FKO": (27, 1), "FKI": (66, 11), "FKC": (84, 27),
}

SHARP_METADATA_KEYS: tuple[str, ...] = (
    "T_REC",
    "HARPNUM",
    "NOAA_AR",
    "NOAA_ARS",
    "NOAA_NUM",
    "H_MERGE",
    "QUALITY",
    "OBS_VR",
    "LON_FWT",
    "LAT_FWT",
)

SHARP_QUERY_KEYS: tuple[str, ...] = SHARP_METADATA_KEYS + SHARP_PARAMETERS

DISPLAY_NAMES: dict[str, str] = {
    "USFLUX": "total unsigned flux",
    "MEANGBT": "mean total-field gradient",
    "MEANJZH": "mean current helicity",
    "MEANPOT": "mean free-energy density",
    "SHRGT45": "strong-shear area fraction",
    "TOTUSJH": "total unsigned current helicity",
    "MEANGBH": "mean horizontal-field gradient",
    "MEANALP": "mean force-free alpha",
    "MEANGAM": "mean field inclination",
    "MEANGBZ": "mean vertical-field gradient",
    "MEANJZD": "mean vertical-current density",
    "TOTUSJZ": "total unsigned vertical current",
    "SAVNCPP": "net current per polarity",
    "TOTPOT": "total free-energy proxy",
    "MEANSHR": "mean magnetic shear",
    "AREA_ACR": "active magnetic area",
    "R_VALUE": "strong-gradient PIL flux",
    "ABSNJZH": "absolute net current helicity",
    "ABS_LON_FWT": "distance from central meridian",
    "LAT_FWT_VALUE": "active-region latitude",
    "PRIOR_M1_COUNT_24H": "prior 24-hour M1+ activity",
    "PRIOR_M1_COUNT_7D": "prior 7-day M1+ activity",
    "PRIOR_M1_COUNT_30D": "prior 30-day M1+ activity",
    "PRIOR_X1_COUNT_7D": "prior 7-day X1+ activity",
    "PRIOR_X1_COUNT_30D": "prior 30-day X1+ activity",
    "HOURS_SINCE_M1": "time since the last M1+ flare",
    "HOURS_SINCE_X1": "time since the last X1+ flare",
}


@dataclasses.dataclass(frozen=True)
class ModelPaths:
    directory: Path
    m1: Path
    x1: Path
    manifest: Path
    report: Path

    @classmethod
    def from_directory(cls, directory: Path) -> "ModelPaths":
        directory = directory.expanduser().resolve()
        return cls(
            directory=directory,
            m1=directory / "sharp_mag_m1.joblib",
            x1=directory / "sharp_mag_x1.joblib",
            manifest=directory / "sharp_mag_manifest.json",
            report=directory / "sharp_mag_training_report.json",
        )


class PipelineError(RuntimeError):
    """Expected, actionable pipeline failure."""


def utc_now() -> dt.datetime:
    return dt.datetime.now(tz=UTC)


def iso_z(value: dt.datetime) -> str:
    value = ensure_utc(value)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected YYYY-MM-DD, received {value!r}") from exc


def parse_datetime_utc(value: str) -> dt.datetime:
    cleaned = value.strip()
    if cleaned.lower() == "now":
        return utc_now()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Expected an ISO-8601 UTC time such as 2026-08-22T21:00:00Z"
        ) from exc
    return ensure_utc(parsed)


def latest_cycle_time(now: dt.datetime, issue_hour: int) -> dt.datetime:
    """Return the most recent scheduled UTC cycle at ``issue_hour``."""
    now = ensure_utc(now)
    candidate = now.replace(hour=issue_hour, minute=0, second=0, microsecond=0)
    if now < candidate:
        candidate -= dt.timedelta(days=1)
    return candidate


def resolve_issue_time(value: str, issue_hour: int) -> dt.datetime:
    if value.lower() == "cycle":
        return latest_cycle_time(utc_now(), issue_hour)
    return parse_datetime_utc(value)


def next_utc_midnight(issue_time: dt.datetime) -> dt.datetime:
    issue_time = ensure_utc(issue_time)
    next_date = issue_time.date() + dt.timedelta(days=1)
    return dt.datetime.combine(next_date, dt.time(0), tzinfo=UTC)


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)sZ %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logging.Formatter.converter = time.gmtime


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def major_minor(version: str) -> tuple[int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)", str(version))
    return (int(match.group(1)), int(match.group(2))) if match else None


def exact_runtime_requirements() -> dict[str, str]:
    return {
        name: package_version(name)
        for name in ("numpy", "pandas", "requests", "scikit-learn", "joblib", "drms", "packaging")
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_default(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    raise TypeError(f"Cannot JSON-encode {type(value).__name__}")


def atomic_write_text(path: Path, text: str) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=False, default=json_default) + "\n")


def append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, separators=(",", ":"), default=json_default) + "\n")


def request_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=8, pool_maxsize=8)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                f"SpaceWxOps-WXF/{SCRIPT_VERSION} "
                "(research flare guidance; contact local system administrator)"
            )
        }
    )
    return session


def import_drms() -> Any:
    try:
        import drms  # type: ignore
    except ImportError as exc:
        raise PipelineError(
            "The drms package is required for JSOC SHARP queries. Install requirements-sharp-mag.txt."
        ) from exc
    return drms


def drms_time_string(value: dt.datetime) -> str:
    # JSOC examples conventionally request TAI.  At daily/12-minute cadence the
    # UTC-vs-TAI offset does not alter the intended 18Z nominal sample materially.
    value = ensure_utc(value)
    return value.strftime("%Y.%m.%d_%H:%M:%S_TAI")


def parse_t_rec(values: pd.Series) -> pd.Series:
    drms = import_drms()
    try:
        parsed = drms.to_datetime(values)
        result = pd.to_datetime(parsed, errors="coerce", utc=True)
        if result.notna().any():
            return result
    except Exception:
        LOGGER.debug("drms.to_datetime failed; using local T_REC parser", exc_info=True)

    cleaned = (
        values.astype("string")
        .str.replace("_TAI", "", regex=False)
        .str.replace("_UTC", "", regex=False)
    )
    result = pd.to_datetime(cleaned, format="%Y.%m.%d_%H:%M:%S", errors="coerce", utc=True)
    missing = result.isna()
    if missing.any():
        fallback = pd.to_datetime(cleaned[missing], errors="coerce", utc=True)
        result.loc[missing] = fallback
    return result


DRMS_KEY_CACHE: dict[str, dict[str, str]] = {}


def query_drms(record_set: str, keys: Sequence[str]) -> pd.DataFrame:
    drms = import_drms()
    LOGGER.info("JSOC query: %s", record_set)
    series = record_set.split("[", 1)[0]
    try:
        client = drms.Client()
        available = DRMS_KEY_CACHE.get(series)
        if available is None:
            available = {str(key).upper(): str(key) for key in client.keys(series)}
            DRMS_KEY_CACHE[series] = available
        selected = [available[str(key).upper()] for key in keys if str(key).upper() in available]
        required_missing = [
            key for key in ("T_REC", "HARPNUM") if key not in available
        ]
        if not ("NOAA_ARS" in available or "NOAA_AR" in available):
            required_missing.append("NOAA_ARS/NOAA_AR")
        if required_missing:
            raise PipelineError(
                f"JSOC series {series} is missing required keys: {', '.join(required_missing)}"
            )
        omitted = [str(key) for key in keys if str(key).upper() not in available]
        if omitted:
            LOGGER.warning("JSOC series %s lacks optional keys: %s", series, ", ".join(omitted))
        frame = client.query(record_set, key=",".join(selected))
    except PipelineError:
        raise
    except Exception as exc:
        raise PipelineError(f"JSOC query failed for {record_set}: {exc}") from exc
    if frame is None or not isinstance(frame, pd.DataFrame):
        raise PipelineError(f"JSOC returned no tabular result for {record_set}")
    if frame.empty:
        LOGGER.warning("JSOC query returned zero records: %s", record_set)
        return frame
    frame = frame.reset_index(drop=False)
    # Some DRMS versions return prime keys in the index and again as columns.
    frame = frame.loc[:, ~frame.columns.duplicated()].copy()
    frame.columns = [str(column).upper() for column in frame.columns]
    return frame


def date_chunks(start: dt.date, end: dt.date, chunk_days: int) -> Iterator[tuple[dt.date, dt.date]]:
    """Yield [start, end) date chunks."""
    cursor = start
    while cursor < end:
        next_cursor = min(end, cursor + dt.timedelta(days=chunk_days))
        yield cursor, next_cursor
        cursor = next_cursor
        
        
def date_range(start: dt.date, end: dt.date) -> Iterator[dt.date]:
    """Yield dates in the half-open interval [start, end)."""
    cursor = start
    while cursor < end:
        yield cursor
        cursor += dt.timedelta(days=1)


def historical_record_set(
    series: str,
    start: dt.date,
    end: dt.date,
    feature_hour: int,
) -> str:
    days = (end - start).days
    if days <= 0:
        raise PipelineError("Historical query end must be after start")
    start_time = dt.datetime.combine(start, dt.time(feature_hour), tzinfo=UTC)
    return f"{series}[][{drms_time_string(start_time)}/{days}d@1d]"


def live_record_set(series: str, start: dt.datetime, hours: int) -> str:
    return f"{series}[][{drms_time_string(start)}/{hours}h]"


def numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    values = frame[column]
    if column == "QUALITY":
        return values.map(parse_quality_value).astype("float64")
    return pd.to_numeric(values, errors="coerce")


def parse_quality_value(value: Any) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return math.nan
    text = str(value).strip()
    if not text:
        return math.nan
    try:
        return float(int(text, 0))
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return math.nan


def parse_noaa_regions(row: Mapping[str, Any]) -> list[int]:
    candidates: list[int] = []
    for key in ("NOAA_ARS", "NOAA_AR"):
        value = row.get(key)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue
        if str(value).strip().startswith("-"):
            continue
        for token in re.findall(r"\d{3,6}", str(value)):
            number = int(token)
            if number > 0:
                candidates.append(number)
    # Preserve order while removing duplicates and placeholder values.
    return list(dict.fromkeys(number for number in candidates if number not in {0, 9999}))
 

def normalize_region_for_flare_catalog(number: Any) -> int | None:
    if number is None or (isinstance(number, float) and math.isnan(number)):
        return None
    text = str(number).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    match = re.search(r"\d{1,6}", text)
    if not match:
        return None
    value = int(match.group(0))
    if value <= 0:
        return None
    if value < 10000:
        return value
    remainder = value % 10000
    return value if remainder == 0 else remainder


def canonical_noaa_region(number: Any) -> int | None:
    """Return the cycle-qualified NOAA number used by HMI/SolarMonitor."""
    normalized = normalize_region_for_flare_catalog(number)
    if normalized is None:
        return None
    return normalized + 10000 if normalized < 10000 else normalized


def clean_sharp_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    cleaned = frame.copy()
    for column in SHARP_PARAMETERS + ("HARPNUM", "NOAA_NUM", "H_MERGE", "QUALITY", "OBS_VR", "LON_FWT", "LAT_FWT"):
        cleaned[column] = numeric_series(cleaned, column)
    if "T_REC" not in cleaned:
        raise PipelineError("JSOC SHARP result is missing T_REC")
    cleaned["T_REC_UTC"] = parse_t_rec(cleaned["T_REC"])
    cleaned = cleaned[cleaned["T_REC_UTC"].notna()].copy()
    return cleaned


def expand_single_region_rows(
    frame: pd.DataFrame,
    *,
    include_multi_region_harps: bool,
) -> tuple[pd.DataFrame, dict[str, int]]:
    rows: list[dict[str, Any]] = []
    skipped_multi = 0
    skipped_unmapped = 0
    for record in frame.to_dict(orient="records"):
        regions = parse_noaa_regions(record)
        if not regions:
            skipped_unmapped += 1
            continue
        if len(regions) > 1 and not include_multi_region_harps:
            skipped_multi += 1
            continue
        for region in regions:
            expanded = dict(record)
            expanded["NOAA_REGION"] = region
            expanded["NOAA_REGION_NORM"] = normalize_region_for_flare_catalog(region)
            expanded["HARP_REGION_COUNT"] = len(regions)
            rows.append(expanded)
    result = pd.DataFrame(rows)
    return result, {
        "skipped_multi_region_harps": skipped_multi,
        "skipped_unmapped_harps": skipped_unmapped,
        "expanded_rows": len(rows),
    }


def apply_sharp_quality_filters(
    frame: pd.DataFrame,
    *,
    max_longitude: float,
    max_obs_vr: float,
    max_quality: int,
    min_finite_parameters: int = DEFAULT_MIN_FINITE_PARAMETERS,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply operationally useful SHARP QC without treating QUALITY as a scalar score.

    HMI QUALITY is a 32-bit bitmask.  Earlier versions of this pipeline used an
    integer ceiling as a hard filter, which rejected nearly all archived NRT SHARP
    records because many otherwise usable NRT observations carry higher-order flags.

    The default policy therefore keeps QUALITY as a diagnostic value and relies on
    geometry, HARP-merge, observer-velocity, NOAA mapping, and scalar-parameter
    completeness screening.  A user may still supply a smaller --max-quality value
    for sensitivity experiments, but that is NOT the default science filter.
    """
    if frame.empty:
        return frame.copy(), {"input": 0, "retained": 0}

    mask = pd.Series(True, index=frame.index)
    reasons: dict[str, Any] = {"input": len(frame)}

    lon = numeric_series(frame, "LON_FWT")
    lon_ok = lon.notna() & (lon.abs() <= max_longitude)
    reasons["rejected_longitude"] = int((~lon_ok).sum())
    mask &= lon_ok
    reasons["after_longitude"] = int(mask.sum())

    # QUALITY is a bitmask, not an ordinal severity score.  Keep it for audit/QC
    # diagnostics.  Only apply a numeric ceiling when the caller explicitly sets a
    # value below the 32-bit default.
    quality = numeric_series(frame, "QUALITY")
    quality_present = quality.notna()
    reasons["quality_missing"] = int((~quality_present).sum())
    quality_int = quality.fillna(0).astype('int64')
    qcounts = quality_int[mask & quality_present].value_counts().head(20)
    reasons["quality_top_values"] = {
        f"0x{int(k) & 0xFFFFFFFF:08X}": int(v) for k, v in qcounts.items()
    }
    if max_quality < 0xFFFFFFFF:
        quality_ok = quality.isna() | ((quality >= 0) & (quality <= max_quality))
        reasons["rejected_quality"] = int((mask & ~quality_ok).sum())
        mask &= quality_ok
    else:
        reasons["rejected_quality"] = 0
    reasons["after_quality"] = int(mask.sum())

    h_merge = numeric_series(frame, "H_MERGE")
    merge_ok = h_merge.isna() | (h_merge == 0)
    reasons["rejected_harp_merge"] = int((mask & ~merge_ok).sum())
    mask &= merge_ok
    reasons["after_harp_merge"] = int(mask.sum())

    obs_vr = numeric_series(frame, "OBS_VR")
    obs_vr_ok = obs_vr.isna() | (obs_vr.abs() < max_obs_vr)
    reasons["rejected_observer_velocity"] = int((mask & ~obs_vr_ok).sum())
    mask &= obs_vr_ok
    reasons["after_observer_velocity"] = int(mask.sum())

    harp = numeric_series(frame, "HARPNUM")
    mapped_ok = harp.notna() & frame["NOAA_REGION_NORM"].notna()
    reasons["rejected_missing_mapping"] = int((mask & ~mapped_ok).sum())
    mask &= mapped_ok
    reasons["after_mapping"] = int(mask.sum())

    # Require enough finite scalar SHARP indices to form a meaningful feature vector.
    parameter_frame = pd.DataFrame(
        {name: numeric_series(frame, name) for name in SHARP_PARAMETERS},
        index=frame.index,
    )
    finite_count = parameter_frame.notna().sum(axis=1)
    completeness_ok = finite_count >= int(min_finite_parameters)
    reasons["min_finite_parameters"] = int(min_finite_parameters)
    reasons["rejected_parameter_completeness"] = int((mask & ~completeness_ok).sum())
    mask &= completeness_ok
    reasons["after_parameter_completeness"] = int(mask.sum())

    result = frame.loc[mask].copy()
    result["SHARP_FINITE_PARAMETER_COUNT"] = finite_count.loc[result.index].astype(int)
    reasons["retained"] = len(result)
    return result, reasons


def choose_one_harp_per_region_day(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    ranked = frame.copy()
    ranked["AREA_ACR_RANK"] = numeric_series(ranked, "AREA_ACR").fillna(-np.inf)
    ranked = ranked.sort_values(
        ["ISSUE_DATE", "NOAA_REGION", "AREA_ACR_RANK", "T_REC_UTC"],
        ascending=[True, True, False, False],
    )
    ranked = ranked.drop_duplicates(["ISSUE_DATE", "NOAA_REGION"], keep="first")
    return ranked.drop(columns=["AREA_ACR_RANK"])


def discover_latest_flare_csv(session: requests.Session, directory_url: str) -> str:
    LOGGER.info("Discovering latest NOAA/NCEI GOES Flare Report CSV")
    try:
        response = session.get(directory_url, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise PipelineError(
            "Unable to list the NCEI GOES Flare Report directory. Use --flare-csv with a local CSV "
            "or --flare-csv-url with a known mission-length CSV URL."
        ) from exc

    names = re.findall(r'href=["\']([^"\']+\.csv)["\']', response.text, flags=re.IGNORECASE)
    mission = [name for name in names if "flrpt" in name.lower() and re.search(r"_s\d{8}_e\d{8}", name)]
    if not mission:
        raise PipelineError("No mission-length GOES Flare Report CSV was found in the NCEI directory")

    def sort_key(name: str) -> tuple[int, int, tuple[int, ...], str]:
        start_match = re.search(r"_s(\d{8})", name)
        end_match = re.search(r"_e(\d{8})", name)
        version_match = re.search(r"_v([0-9-]+)", name)
        start_value = int(start_match.group(1)) if start_match else 99999999
        end_value = int(end_match.group(1)) if end_match else 0
        try:
            start_date = dt.datetime.strptime(str(start_value), "%Y%m%d").date()
            end_date = dt.datetime.strptime(str(end_value), "%Y%m%d").date()
            span_days = (end_date - start_date).days
        except ValueError:
            span_days = 0
        version = tuple(int(part) for part in version_match.group(1).split("-") if part.isdigit()) if version_match else ()
        # Latest ending file first; for the same end date prefer the longest
        # mission-length span over a single-year aggregation.
        return end_value, span_days, version, name

    selected = sorted(mission, key=sort_key)[-1]
    return urljoin(directory_url, selected)


def download_file(session: requests.Session, url: str, destination: Path) -> Path:
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Downloading %s", url)
    try:
        with session.get(url, timeout=(30, 300), stream=True) as response:
            response.raise_for_status()
            fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, destination)
            except Exception:
                Path(temp_name).unlink(missing_ok=True)
                raise
    except requests.RequestException as exc:
        raise PipelineError(f"Unable to download {url}: {exc}") from exc
    return destination


def obtain_flare_csv(
    *,
    cache_dir: Path,
    flare_csv: Path | None,
    flare_csv_url: str | None,
    refresh: bool,
) -> tuple[Path, str]:
    if flare_csv is not None:
        source = flare_csv.expanduser().resolve()
        if not source.exists():
            raise PipelineError(f"Flare CSV does not exist: {source}")
        # Preserve reproducible provenance without publishing a developer's
        # absolute filesystem path in the dataset metadata.
        return source, f"local-file:{source.name}"

    session = request_session()
    url = flare_csv_url or discover_latest_flare_csv(session, NCEI_FLARE_DIRECTORY)
    name = Path(url.split("?", 1)[0]).name or "goes_flare_report.csv"
    destination = cache_dir.expanduser().resolve() / "flare_catalog" / name
    if refresh or not destination.exists():
        download_file(session, url, destination)
    else:
        LOGGER.info("Using cached flare report: %s", destination)
    return destination, url


EVENT_TIME_TOKEN = re.compile(r"^(?:[ABU])?(?:[01]\d|2[0-3])[0-5]\d$|^////$", re.IGNORECASE)
FLARE_CLASS_TOKEN = re.compile(r"^[ABCMX]\d+(?:\.\d+)?$", re.IGNORECASE)


def ncei_event_report_url(day: dt.date) -> str:
    return (
        f"{NCEI_SOLAR_EVENT_REPORT_ROOT}/{day.year}/{day.month:02d}/"
        f"{day:%Y%m%d}events.txt"
    )


def parse_event_time_token(token: str, report_date: dt.date) -> dt.datetime | None:
    token = str(token or "").strip().upper()
    if token == "////" or not EVENT_TIME_TOKEN.fullmatch(token):
        return None
    prefix = token[0] if token and token[0].isalpha() else ""
    digits = token[1:] if prefix else token
    hour, minute = int(digits[:2]), int(digits[2:])
    day = report_date - dt.timedelta(days=1) if prefix == "B" else report_date
    return dt.datetime.combine(day, dt.time(hour, minute), tzinfo=UTC)


def parse_ncei_solar_event_report(
    text: str, report_date: dt.date
) -> tuple[list[dict[str, Any]], int]:
    """Parse region-attributed M1+/X1+ XRA rows from one NOAA daily report.

    The daily Solar and Geophysical Event Report carries the NOAA region
    association that the GOES irradiance-only flare report does not.  An
    unattributed M/X event marks the day ambiguous for regional negative labels.
    """
    events: list[dict[str, Any]] = []
    unattributed = 0
    for raw_line in text.splitlines():
        if " XRA " not in f" {raw_line} ":
            continue
        tokens = raw_line.split()
        try:
            xra_index = next(i for i, token in enumerate(tokens) if token.upper() == "XRA")
        except StopIteration:
            continue
        class_index = next(
            (i for i in range(xra_index + 1, len(tokens)) if FLARE_CLASS_TOKEN.fullmatch(tokens[i])),
            None,
        )
        if class_index is None:
            continue
        flare_class = tokens[class_index].upper()
        parsed_class = re.match(r"^([A-Z])(\d+(?:\.\d+)?)$", flare_class)
        if not parsed_class:
            continue
        letter, coefficient_text = parsed_class.groups()
        coefficient = float(coefficient_text)
        is_m1 = (letter == "M" and coefficient >= 1.0) or (letter == "X" and coefficient >= 0.1)
        is_x1 = letter == "X" and coefficient >= 1.0
        if not (is_m1 or is_x1):
            continue

        time_tokens = [token for token in tokens[1:xra_index] if EVENT_TIME_TOKEN.fullmatch(token)]
        begin = parse_event_time_token(time_tokens[0], report_date) if time_tokens else None
        peak = parse_event_time_token(time_tokens[1], report_date) if len(time_tokens) > 1 else None
        event_time = peak or begin
        if event_time is None:
            continue

        region = None
        for token in reversed(tokens[class_index + 1 :]):
            if re.fullmatch(r"\d{3,6}", token):
                region = normalize_region_for_flare_catalog(token)
                if region is not None:
                    break
        if region is None:
            unattributed += 1
            continue
        events.append(
            {
                "start_time": iso_z(event_time),
                "flare_class": flare_class,
                "active_region": int(region),
                "source": "NOAA/NCEI Solar and Geophysical Event Report",
                "report_date": report_date.isoformat(),
            }
        )

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for event in events:
        unique[(event["start_time"], event["flare_class"], event["active_region"])] = event
    return list(unique.values()), unattributed


def fetch_ncei_event_day(
    day: dt.date,
    raw_cache_root: Path,
    refresh: bool,
) -> tuple[dt.date, str | None, str]:
    cache_path = raw_cache_root / f"{day.year}" / f"{day.month:02d}" / f"{day:%Y%m%d}events.txt"
    if cache_path.exists() and not refresh:
        return day, cache_path.read_text(encoding="utf-8", errors="replace"), "cached"
    session = request_session()
    try:
        response = session.get(ncei_event_report_url(day), timeout=40)
    except requests.RequestException as exc:
        return day, None, f"request error: {exc}"
    if response.status_code == 404:
        return day, None, "HTTP 404"
    if not response.ok:
        return day, None, f"HTTP {response.status_code}"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(cache_path, response.text)
    return day, response.text, "downloaded"


def obtain_ncei_region_flare_catalog(
    *,
    cache_dir: Path,
    valid_start: dt.date,
    valid_end_exclusive: dt.date,
    refresh: bool,
    workers: int,
) -> tuple[Path, Path, str]:
    catalog_root = cache_dir.expanduser().resolve() / "flare_catalog"
    catalog_root.mkdir(parents=True, exist_ok=True)
    catalog_path = catalog_root / (
        f"ncei_region_flares_{valid_start:%Y%m%d}_{valid_end_exclusive:%Y%m%d}.csv.gz"
    )
    coverage_path = catalog_root / (
        f"ncei_region_flares_{valid_start:%Y%m%d}_{valid_end_exclusive:%Y%m%d}.coverage.csv.gz"
    )
    if catalog_path.exists() and coverage_path.exists() and not refresh:
        LOGGER.info("Using cached NOAA/NCEI region flare catalog: %s", catalog_path.name)
        return catalog_path, coverage_path, NCEI_SOLAR_EVENT_REPORT_ROOT

    days = list(date_range(valid_start, valid_end_exclusive))
    raw_root = catalog_root / "daily_event_reports"
    events: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    LOGGER.info("Retrieving %d NOAA/NCEI daily solar event reports", len(days))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(fetch_ncei_event_day, day, raw_root, refresh): day for day in days
        }
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            day, text, detail = future.result()
            completed += 1
            if completed % 250 == 0 or completed == len(days):
                LOGGER.info("NCEI event reports: %d/%d", completed, len(days))
            if text is None:
                coverage.append(
                    {
                        "date": day.isoformat(),
                        "available": 0,
                        "ambiguous": 1,
                        "unattributed_major": 0,
                        "detail": detail,
                    }
                )
                continue
            parsed_events, unattributed = parse_ncei_solar_event_report(text, day)
            events.extend(parsed_events)
            coverage.append(
                {
                    "date": day.isoformat(),
                    "available": 1,
                    "ambiguous": int(unattributed > 0),
                    "unattributed_major": unattributed,
                    "detail": detail,
                }
            )

    event_columns = ["start_time", "flare_class", "active_region", "source", "report_date"]
    event_frame = pd.DataFrame(events, columns=event_columns)
    if not event_frame.empty:
        event_frame = event_frame.drop_duplicates(["start_time", "flare_class", "active_region"])
        event_frame = event_frame.sort_values(["start_time", "active_region"])
    coverage_frame = pd.DataFrame(coverage).sort_values("date")
    event_frame.to_csv(catalog_path, index=False, compression="gzip")
    coverage_frame.to_csv(coverage_path, index=False, compression="gzip")
    LOGGER.info(
        "Saved %d region-attributed M/X events; %d ambiguous days; %d unavailable reports",
        len(event_frame),
        int(coverage_frame["ambiguous"].sum()) if len(coverage_frame) else 0,
        int((coverage_frame["available"] == 0).sum()) if len(coverage_frame) else 0,
    )
    return catalog_path, coverage_path, NCEI_SOLAR_EVENT_REPORT_ROOT


def read_flare_coverage(
    path: Path | None,
    *,
    fallback_start: dt.date,
    fallback_end_exclusive: dt.date,
) -> pd.DataFrame:
    if path is None:
        # A user-supplied region-labeled CSV is treated as complete over the
        # requested range. This assumption is recorded in dataset metadata.
        return pd.DataFrame(
            {
                "date": list(date_range(fallback_start, fallback_end_exclusive)),
                "available": 1,
                "ambiguous": 0,
                "unattributed_major": 0,
                "detail": "custom catalog assumed complete",
            }
        )
    frame = pd.read_csv(path, low_memory=False)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    return frame[frame["date"].notna()].copy()


def normalize_flare_catalog(path: Path) -> pd.DataFrame:
    LOGGER.info("Reading flare labels: %s", path)
    try:
        frame = pd.read_csv(path, low_memory=False)
    except Exception as exc:
        raise PipelineError(f"Unable to read flare report CSV {path}: {exc}") from exc
    frame.columns = [str(column).strip().lower() for column in frame.columns]

    time_column = next((name for name in ("start_time", "time", "peak_time") if name in frame), None)
    class_column = next((name for name in ("flare_class", "class", "xray_class") if name in frame), None)
    region_column = next((name for name in ("active_region", "noaa_region", "region") if name in frame), None)
    if time_column is None or class_column is None:
        raise PipelineError(
            "Flare report CSV must contain start_time/time and flare_class columns; "
            f"received {sorted(frame.columns)}"
        )

    catalog = pd.DataFrame(index=frame.index)
    catalog["EVENT_TIME"] = pd.to_datetime(frame[time_column], errors="coerce", utc=True)
    catalog["FLARE_CLASS"] = frame[class_column].astype("string").str.strip().str.upper()
    catalog["NOAA_REGION_NORM"] = (
        frame[region_column].map(normalize_region_for_flare_catalog) if region_column else None
    )

    parsed = catalog["FLARE_CLASS"].str.extract(r"^\s*([A-Z])\s*([0-9]+(?:\.[0-9]+)?)")
    catalog["LETTER"] = parsed[0]
    catalog["COEFFICIENT"] = pd.to_numeric(parsed[1], errors="coerce")
    catalog["IS_M1_PLUS"] = (
        ((catalog["LETTER"] == "M") & (catalog["COEFFICIENT"] >= 1.0))
        | ((catalog["LETTER"] == "X") & (catalog["COEFFICIENT"] >= 0.1))
    )
    catalog["IS_X1_PLUS"] = (catalog["LETTER"] == "X") & (catalog["COEFFICIENT"] >= 1.0)
    catalog = catalog[catalog["EVENT_TIME"].notna() & (catalog["IS_M1_PLUS"] | catalog["IS_X1_PLUS"])].copy()
    catalog["VALID_DATE"] = catalog["EVENT_TIME"].dt.date
    return catalog


def add_causal_flare_history(
    feature_rows: pd.DataFrame, flare_catalog: pd.DataFrame
) -> pd.DataFrame:
    """Attach strictly pre-issue regional flare-history features."""
    output = feature_rows.copy()
    history = flare_catalog[
        flare_catalog["EVENT_TIME"].notna()
        & flare_catalog["NOAA_REGION_NORM"].notna()
    ].copy()
    grouped: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for region, group in history.groupby("NOAA_REGION_NORM"):
        m_times = (
            pd.to_datetime(group.loc[group["IS_M1_PLUS"], "EVENT_TIME"], utc=True)
            .astype("datetime64[ns, UTC]")
            .astype("int64")
            .sort_values()
            .to_numpy()
        )
        x_times = (
            pd.to_datetime(group.loc[group["IS_X1_PLUS"], "EVENT_TIME"], utc=True)
            .astype("datetime64[ns, UTC]")
            .astype("int64")
            .sort_values()
            .to_numpy()
        )
        grouped[int(region)] = (m_times, x_times)

    values = {column: [] for column in HISTORY_RAW_COLUMNS}
    hour_ns = 3600 * 1_000_000_000
    for row in output.itertuples(index=False):
        region = int(getattr(row, "NOAA_REGION_NORM"))
        issue = pd.Timestamp(getattr(row, "ISSUE_TIME"))
        if issue.tzinfo is None:
            issue = issue.tz_localize("UTC")
        else:
            issue = issue.tz_convert("UTC")
        issue_ns = int(issue.value)
        m_times, x_times = grouped.get(
            region, (np.array([], dtype=np.int64), np.array([], dtype=np.int64))
        )

        def count_prior(times: np.ndarray, hours: int) -> int:
            right = int(np.searchsorted(times, issue_ns, side="left"))
            left = int(np.searchsorted(times, issue_ns - hours * hour_ns, side="left"))
            return right - left

        def hours_since(times: np.ndarray) -> float:
            index = int(np.searchsorted(times, issue_ns, side="left")) - 1
            if index < 0:
                return 720.0
            return min(720.0, max(0.0, (issue_ns - int(times[index])) / hour_ns))

        values["PRIOR_M1_COUNT_24H"].append(count_prior(m_times, 24))
        values["PRIOR_M1_COUNT_7D"].append(count_prior(m_times, 24 * 7))
        values["PRIOR_M1_COUNT_30D"].append(count_prior(m_times, 24 * 30))
        values["PRIOR_X1_COUNT_7D"].append(count_prior(x_times, 24 * 7))
        values["PRIOR_X1_COUNT_30D"].append(count_prior(x_times, 24 * 30))
        values["HOURS_SINCE_M1"].append(hours_since(m_times))
        values["HOURS_SINCE_X1"].append(hours_since(x_times))

    for column, column_values in values.items():
        output[column] = column_values
    return output


def attach_flare_labels(
    feature_rows: pd.DataFrame,
    flare_catalog: pd.DataFrame,
    flare_coverage: pd.DataFrame,
    *,
    keep_ambiguous_days: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if feature_rows.empty:
        raise PipelineError("No SHARP feature rows remain before flare labeling")

    labeled = feature_rows.copy()
    labeled["VALID_DATE"] = labeled["ISSUE_DATE"].map(lambda value: value + dt.timedelta(days=1))

    events = flare_catalog.copy()
    positive_m = set(
        zip(
            events.loc[events["IS_M1_PLUS"] & events["NOAA_REGION_NORM"].notna(), "VALID_DATE"],
            events.loc[events["IS_M1_PLUS"] & events["NOAA_REGION_NORM"].notna(), "NOAA_REGION_NORM"].astype(int),
        )
    )
    positive_x = set(
        zip(
            events.loc[events["IS_X1_PLUS"] & events["NOAA_REGION_NORM"].notna(), "VALID_DATE"],
            events.loc[events["IS_X1_PLUS"] & events["NOAA_REGION_NORM"].notna(), "NOAA_REGION_NORM"].astype(int),
        )
    )
    catalog_ambiguous_dates = set(
        events.loc[events["IS_M1_PLUS"] & events["NOAA_REGION_NORM"].isna(), "VALID_DATE"].tolist()
    )
    coverage = flare_coverage.copy()
    coverage["date"] = pd.to_datetime(coverage["date"], errors="coerce").dt.date
    available_dates = set(coverage.loc[coverage["available"].astype(bool), "date"].tolist())
    coverage_ambiguous_dates = set(coverage.loc[coverage["ambiguous"].astype(bool), "date"].tolist())
    ambiguous_dates = catalog_ambiguous_dates | coverage_ambiguous_dates

    before_coverage = len(labeled)
    labeled = labeled[labeled["VALID_DATE"].isin(available_dates)].copy()
    pairs = list(zip(labeled["VALID_DATE"], labeled["NOAA_REGION_NORM"].astype(int)))
    labeled["LABEL_M1"] = [int(pair in positive_m) for pair in pairs]
    labeled["LABEL_X1"] = [int(pair in positive_x) for pair in pairs]
    before_ambiguous = len(labeled)
    if not keep_ambiguous_days and ambiguous_dates:
        # An unattributed major event makes other regions unsafe negatives, but
        # it does not erase a positively attributed region on the same day.
        ambiguous_negative = (
            labeled["VALID_DATE"].isin(ambiguous_dates)
            & (labeled["LABEL_M1"] == 0)
        )
        labeled = labeled[~ambiguous_negative].copy()

    stats = {
        "rows_before_label_coverage_filter": before_coverage,
        "rows_after_label_coverage_filter": before_ambiguous,
        "rows_after_ambiguous_day_filter": len(labeled),
        "available_label_days": len(available_dates),
        "ambiguous_major_flare_days": len(ambiguous_dates),
        "ambiguous_negative_rows_removed": before_ambiguous - len(labeled),
        "attributed_positive_rows_preserved_on_ambiguous_days": int(
            (
                labeled["VALID_DATE"].isin(ambiguous_dates)
                & (labeled["LABEL_M1"] == 1)
            ).sum()
        ),
        "m1_positive_rows": int(labeled["LABEL_M1"].sum()),
        "x1_positive_rows": int(labeled["LABEL_X1"].sum()),
        "m1_prevalence": float(labeled["LABEL_M1"].mean()) if len(labeled) else None,
        "x1_prevalence": float(labeled["LABEL_X1"].mean()) if len(labeled) else None,
    }
    return labeled, stats


def add_previous_day_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    sorted_frame = frame.sort_values(["NOAA_REGION", "ISSUE_TIME"]).copy()
    group = sorted_frame.groupby("NOAA_REGION", sort=False)
    previous_time = group["ISSUE_TIME"].shift(1)
    gap_hours = (sorted_frame["ISSUE_TIME"] - previous_time).dt.total_seconds() / 3600.0
    valid_previous = gap_hours.between(18.0, 36.0, inclusive="both")
    sorted_frame["PREVIOUS_GAP_HOURS"] = gap_hours
    for parameter in SHARP_PARAMETERS:
        previous = group[parameter].shift(1)
        sorted_frame[f"PREV_{parameter}"] = previous.where(valid_previous)
    return sorted_frame


def signed_log1p(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype("float64")
    return np.sign(numeric) * np.log1p(np.abs(numeric))


def engineered_feature_columns() -> list[str]:
    columns: list[str] = []
    for parameter in SHARP_PARAMETERS:
        columns.extend((f"{parameter}__LOG1P", f"{parameter}__DELTA24H"))
    columns.extend(("ABS_LON_FWT", "LAT_FWT_VALUE"))
    columns.extend(f"{column}__LOG1P" for column in HISTORY_RAW_COLUMNS)
    return columns


def x1_severity_feature_columns() -> list[str]:
    columns: list[str] = []
    for parameter in X1_SEVERITY_PARAMETERS:
        columns.extend((f"{parameter}__LOG1P", f"{parameter}__DELTA24H"))
    columns.extend(("ABS_LON_FWT", "LAT_FWT_VALUE"))
    columns.extend(f"{column}__LOG1P" for column in HISTORY_RAW_COLUMNS)
    return columns


def engineer_features(frame: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=frame.index)
    for parameter in SHARP_PARAMETERS:
        current = signed_log1p(frame.get(parameter, pd.Series(np.nan, index=frame.index)))
        previous = signed_log1p(frame.get(f"PREV_{parameter}", pd.Series(np.nan, index=frame.index)))
        features[f"{parameter}__LOG1P"] = current
        features[f"{parameter}__DELTA24H"] = current - previous
    features["ABS_LON_FWT"] = pd.to_numeric(frame.get("LON_FWT"), errors="coerce").abs()
    features["LAT_FWT_VALUE"] = pd.to_numeric(frame.get("LAT_FWT"), errors="coerce")
    for column in HISTORY_RAW_COLUMNS:
        raw = pd.to_numeric(
            frame.get(column, pd.Series(np.nan, index=frame.index)), errors="coerce"
        ).clip(lower=0)
        features[f"{column}__LOG1P"] = np.log1p(raw)
    return features[engineered_feature_columns()]


def historical_sharp_rows(
    *,
    start: dt.date,
    end: dt.date,
    issue_hour: int,
    input_lag_hours: int,
    series: str,
    cache_dir: Path,
    refresh_cache: bool,
    chunk_days: int,
    include_multi_region_harps: bool,
    max_longitude: float,
    max_obs_vr: float,
    max_quality: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if end <= start:
        raise PipelineError("--end must be later than --start")
    feature_hour = (issue_hour - input_lag_hours) % 24
    cache_root = cache_dir.expanduser().resolve() / "sharp_chunks"
    cache_root.mkdir(parents=True, exist_ok=True)
    collected: list[pd.DataFrame] = []
    aggregate: dict[str, int] = {
        "queried_rows": 0,
        "skipped_multi_region_harps": 0,
        "skipped_unmapped_harps": 0,
        "expanded_rows": 0,
        "quality_retained": 0,
    }

    for chunk_start, chunk_end in date_chunks(start, end, chunk_days):
        cache_name = (
            f"{series.replace('.', '_')}_{chunk_start:%Y%m%d}_{chunk_end:%Y%m%d}_"
            f"{feature_hour:02d}z.csv.gz"
        )
        cache_path = cache_root / cache_name
        if cache_path.exists() and not refresh_cache:
            LOGGER.info("Using cached raw SHARP chunk: %s", cache_path.name)
            raw = pd.read_csv(cache_path, low_memory=False)
            raw["T_REC_UTC"] = pd.to_datetime(raw["T_REC_UTC"], errors="coerce", utc=True)
        else:
            record_set = historical_record_set(series, chunk_start, chunk_end, feature_hour)
            raw = clean_sharp_frame(query_drms(record_set, SHARP_QUERY_KEYS))
            raw.to_csv(cache_path, index=False, compression="gzip")
        aggregate["queried_rows"] += len(raw)
        expanded, mapping_stats = expand_single_region_rows(
            raw, include_multi_region_harps=include_multi_region_harps
        )
        for key, value in mapping_stats.items():
            aggregate[key] = aggregate.get(key, 0) + int(value)
        chunk, quality_stats = apply_sharp_quality_filters(
            expanded,
            max_longitude=max_longitude,
            max_obs_vr=max_obs_vr,
            max_quality=max_quality,
        )
        aggregate["quality_retained"] += int(quality_stats.get("retained", 0))
        for stat_key, stat_value in quality_stats.items():
            if stat_key == "input":
                aggregate["quality_filter_input"] = aggregate.get("quality_filter_input", 0) + int(stat_value)
            elif stat_key == "quality_top_values" and isinstance(stat_value, dict):
                target = aggregate.setdefault("quality_top_values", {})
                for quality_hex, count in stat_value.items():
                    target[quality_hex] = int(target.get(quality_hex, 0)) + int(count)
            elif stat_key == "min_finite_parameters":
                # This is a configured threshold repeated for every archive chunk,
                # not a count to accumulate across the mission.
                aggregate[stat_key] = int(stat_value)
            elif stat_key != "retained":
                aggregate[stat_key] = aggregate.get(stat_key, 0) + int(stat_value)
        if chunk.empty:
            continue
        chunk["ISSUE_DATE"] = chunk["T_REC_UTC"].dt.date
        chunk["ISSUE_TIME"] = pd.to_datetime(
            chunk["ISSUE_DATE"].astype(str) + f" {issue_hour:02d}:00:00", utc=True
        )
        collected.append(chunk)

    if not collected:
        raise PipelineError("No usable SHARP records were returned for the requested historical period")
    combined = pd.concat(collected, ignore_index=True)
    combined = choose_one_harp_per_region_day(combined)
    combined = add_previous_day_columns(combined)
    aggregate["unique_region_days"] = len(combined)
    aggregate["date_start"] = str(combined["ISSUE_DATE"].min())
    aggregate["date_end"] = str(combined["ISSUE_DATE"].max())
    return combined, aggregate


def build_dataset(args: argparse.Namespace) -> Path:
    work_dir = args.work_dir.expanduser().resolve()
    cache_dir = args.cache_dir.expanduser().resolve() if args.cache_dir else work_dir / "cache"
    output = args.output.expanduser().resolve() if args.output else work_dir / "sharp_mag_training_table.csv.gz"
    output.parent.mkdir(parents=True, exist_ok=True)

    end = args.end or utc_now().date()
    rows, sharp_stats = historical_sharp_rows(
        start=args.start,
        end=end,
        issue_hour=args.issue_hour,
        input_lag_hours=args.input_lag_hours,
        series=args.series,
        cache_dir=cache_dir,
        refresh_cache=args.refresh_cache,
        chunk_days=args.chunk_days,
        include_multi_region_harps=args.include_multi_region_harps,
        max_longitude=args.max_longitude,
        max_obs_vr=args.max_obs_vr,
        max_quality=args.max_quality,
    )

    valid_label_start = args.start + dt.timedelta(days=1)
    valid_label_end = end + dt.timedelta(days=1)
    flare_coverage_path: Path | None = None
    if args.flare_csv is not None or args.flare_csv_url:
        flare_path, flare_source = obtain_flare_csv(
            cache_dir=cache_dir,
            flare_csv=args.flare_csv,
            flare_csv_url=args.flare_csv_url,
            refresh=args.refresh_flare_catalog,
        )
    else:
        flare_path, flare_coverage_path, flare_source = obtain_ncei_region_flare_catalog(
            cache_dir=cache_dir,
            valid_start=valid_label_start,
            valid_end_exclusive=valid_label_end,
            refresh=args.refresh_flare_catalog,
            workers=args.event_workers,
        )
    flare_catalog = normalize_flare_catalog(flare_path)
    rows = add_causal_flare_history(rows, flare_catalog)
    flare_coverage = read_flare_coverage(
        flare_coverage_path,
        fallback_start=valid_label_start,
        fallback_end_exclusive=valid_label_end,
    )
    labeled, label_stats = attach_flare_labels(
        rows,
        flare_catalog,
        flare_coverage,
        keep_ambiguous_days=args.keep_ambiguous_days,
    )
    if labeled.empty:
        raise PipelineError("Labeling removed all training rows")

    # Include engineered features in the compact table so retraining does not
    # require a second JSOC pass, while retaining scalar inputs for auditability.
    engineered = engineer_features(labeled)
    final = pd.concat([labeled.reset_index(drop=True), engineered.reset_index(drop=True)], axis=1)
    final.to_csv(output, index=False, compression="gzip")

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "created_at": iso_z(utc_now()),
        "script_version": SCRIPT_VERSION,
        "output": output.name,
        "sha256": sha256_file(output),
        "historical_series": args.series,
        "start": str(args.start),
        "end_exclusive": str(end),
        "issue_hour_utc": args.issue_hour,
        "input_lag_hours": args.input_lag_hours,
        "feature_sample_hour_utc": (args.issue_hour - args.input_lag_hours) % 24,
        "flare_catalog_source": flare_source,
        "flare_catalog_file": flare_path.name,
        "flare_catalog_sha256": sha256_file(flare_path),
        "flare_coverage_file": flare_coverage_path.name if flare_coverage_path else None,
        "flare_coverage_sha256": sha256_file(flare_coverage_path) if flare_coverage_path else None,
        "sharp_stats": sharp_stats,
        "label_stats": label_stats,
        "quality_filters": {
            "max_abs_longitude_deg": args.max_longitude,
            "max_abs_observer_velocity_m_s": args.max_obs_vr,
            "max_quality_integer": args.max_quality,
            "multi_region_harps_included": args.include_multi_region_harps,
            "ambiguous_major_flare_days_retained": args.keep_ambiguous_days,
        },
        "storage_note": (
            "This table contains compact scalar SHARP keyword rows and labels; no magnetogram FITS segments are stored."
        ),
    }
    atomic_write_json(output.with_suffix(output.suffix + ".metadata.json"), metadata)
    LOGGER.info("Training table written: %s (%d rows)", output, len(final))
    return output


def load_training_table(path: Path) -> pd.DataFrame:
    path = path.expanduser().resolve()
    if not path.exists():
        raise PipelineError(f"Training table not found: {path}")
    LOGGER.info("Loading training table: %s", path)
    frame = pd.read_csv(path, low_memory=False)
    if "ISSUE_TIME" not in frame:
        raise PipelineError("Training table is missing ISSUE_TIME")
    frame["ISSUE_TIME"] = pd.to_datetime(frame["ISSUE_TIME"], errors="coerce", utc=True)
    frame = frame[frame["ISSUE_TIME"].notna()].copy()
    return frame


def base_pipeline(c_value: float) -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    C=c_value,
                    class_weight="balanced",
                    max_iter=5000,
                    solver="lbfgs",
                    random_state=42,
                ),
            ),
        ]
    )


def probability_logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(clipped / (1 - clipped)).reshape(-1, 1)


def fit_platt_calibrator(probabilities: np.ndarray, labels: np.ndarray) -> LogisticRegression | None:
    labels = np.asarray(labels, dtype=int)
    if len(np.unique(labels)) < 2 or labels.sum() < 3 or (len(labels) - labels.sum()) < 3:
        return None
    calibrator = LogisticRegression(C=1e6, solver="lbfgs", max_iter=2000, random_state=42)
    calibrator.fit(probability_logit(probabilities), labels)
    return calibrator


def calibrated_predict(bundle: Mapping[str, Any], features: pd.DataFrame) -> np.ndarray:
    pipeline: Pipeline = bundle["pipeline"]
    raw = pipeline.predict_proba(features[bundle["feature_columns"]])[:, 1]
    calibrator = bundle.get("calibrator")
    if calibrator is None:
        return np.clip(raw, 0.0, 1.0)
    calibrated = calibrator.predict_proba(probability_logit(raw))[:, 1]
    return np.clip(calibrated, 0.0, 1.0)


def chronological_splits(frame: pd.DataFrame, purge_days: int = 7) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dates = np.array(sorted(pd.to_datetime(frame["ISSUE_TIME"], utc=True).dt.normalize().unique()))
    if len(dates) < 60:
        raise PipelineError("At least 60 distinct issue dates are required for chronological validation")
    train_end = max(1, int(len(dates) * 0.70))
    calibration_end = max(train_end + 1, int(len(dates) * 0.85))
    calibration_end = min(calibration_end, len(dates) - 1)
    normalized = pd.to_datetime(frame["ISSUE_TIME"], utc=True).dt.normalize()
    train_cutoff = pd.Timestamp(dates[train_end - 1])
    calibration_cutoff = pd.Timestamp(dates[calibration_end - 1])
    calibration_start = train_cutoff + pd.Timedelta(days=purge_days + 1)
    test_start = calibration_cutoff + pd.Timedelta(days=purge_days + 1)
    train = (normalized <= train_cutoff).to_numpy()
    calibration = ((normalized >= calibration_start) & (normalized <= calibration_cutoff)).to_numpy()
    test = (normalized >= test_start).to_numpy()
    if not train.any() or not calibration.any() or not test.any():
        raise PipelineError("Unable to construct purged train/calibration/test time blocks")
    return train, calibration, test


def metric_or_none(function: Any, *args: Any, **kwargs: Any) -> float | None:
    try:
        value = float(function(*args, **kwargs))
        return value if math.isfinite(value) else None
    except (ValueError, ZeroDivisionError):
        return None


def reliability_bins(labels: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> list[dict[str, Any]]:
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    if len(labels) == 0:
        return []
    try:
        observed, predicted = calibration_curve(labels, probabilities, n_bins=bins, strategy="quantile")
    except ValueError:
        return []
    result: list[dict[str, Any]] = []
    quantile_edges = np.quantile(probabilities, np.linspace(0, 1, len(predicted) + 1))
    for index, (p_mean, o_mean) in enumerate(zip(predicted, observed)):
        if index == len(predicted) - 1:
            count = int(((probabilities >= quantile_edges[index]) & (probabilities <= quantile_edges[index + 1])).sum())
        else:
            count = int(((probabilities >= quantile_edges[index]) & (probabilities < quantile_edges[index + 1])).sum())
        result.append(
            {"mean_forecast": float(p_mean), "observed_frequency": float(o_mean), "count": count}
        )
    return result


def evaluate_predictions(labels: np.ndarray, probabilities: np.ndarray, climatology: float) -> dict[str, Any]:
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    brier = metric_or_none(brier_score_loss, labels, probabilities)
    climatology_probabilities = np.full(len(labels), climatology, dtype=float)
    brier_reference = metric_or_none(brier_score_loss, labels, climatology_probabilities)
    brier_skill = None
    if brier is not None and brier_reference not in (None, 0.0):
        brier_skill = 1.0 - brier / brier_reference
    return {
        "samples": int(len(labels)),
        "positives": int(labels.sum()),
        "prevalence": float(labels.mean()) if len(labels) else None,
        "brier_score": brier,
        "brier_skill_vs_training_climatology": brier_skill,
        "log_loss": metric_or_none(log_loss, labels, probabilities, labels=[0, 1]),
        "roc_auc": metric_or_none(roc_auc_score, labels, probabilities),
        "precision_recall_auc": metric_or_none(average_precision_score, labels, probabilities),
        "reliability": reliability_bins(labels, probabilities),
    }


def grouped_bootstrap_brier_skill(
    labels: np.ndarray,
    probabilities: np.ndarray,
    groups: np.ndarray,
    climatology: float,
    *,
    draws: int = 500,
) -> dict[str, Any]:
    """Bootstrap whole active regions so repeated region-days stay clustered."""
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    groups = np.asarray(groups)
    unique = np.unique(groups)
    if len(labels) == 0 or len(unique) < 2:
        return {"draws": 0, "groups": int(len(unique)), "lower": None, "median": None, "upper": None}
    indices = {group: np.flatnonzero(groups == group) for group in unique}
    rng = np.random.default_rng(42)
    scores: list[float] = []
    for _ in range(draws):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        selected = np.concatenate([indices[group] for group in sampled])
        brier = brier_score_loss(labels[selected], probabilities[selected])
        reference = brier_score_loss(
            labels[selected], np.full(len(selected), climatology, dtype=float)
        )
        if reference > 0:
            scores.append(float(1.0 - brier / reference))
    if not scores:
        return {"draws": 0, "groups": int(len(unique)), "lower": None, "median": None, "upper": None}
    lower, median, upper = np.quantile(scores, [0.025, 0.5, 0.975])
    return {
        "draws": len(scores),
        "groups": int(len(unique)),
        "lower": float(lower),
        "median": float(median),
        "upper": float(upper),
    }


def oof_calibrator(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    labels: np.ndarray,
    groups: np.ndarray,
    c_value: float,
) -> tuple[LogisticRegression | None, dict[str, Any]]:
    positive = int(labels.sum())
    negative = int(len(labels) - positive)
    unique_groups = len(np.unique(groups))
    folds = min(5, positive, negative, unique_groups)
    if folds < 2:
        return None, {"method": "none", "reason": "insufficient class/group support"}

    if StratifiedGroupKFold is not None:
        splitter: Any = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=42)
        splits = splitter.split(features, labels, groups)
        method = "StratifiedGroupKFold"
    else:
        splitter = GroupKFold(n_splits=folds)
        splits = splitter.split(features, labels, groups)
        method = "GroupKFold"

    oof = np.full(len(labels), np.nan, dtype=float)
    for train_index, validation_index in splits:
        model = base_pipeline(c_value)
        model.fit(features.iloc[train_index], labels[train_index])
        oof[validation_index] = model.predict_proba(features.iloc[validation_index])[:, 1]
    valid = np.isfinite(oof)
    calibrator = fit_platt_calibrator(oof[valid], labels[valid])
    return calibrator, {
        "method": method,
        "folds": folds,
        "oof_samples": int(valid.sum()),
        "oof_positives": int(labels[valid].sum()),
    }


def train_one_threshold(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    *,
    label_column: str,
    threshold_name: str,
    c_value: float,
    min_positives: int,
    allow_small_sample: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    labels = pd.to_numeric(frame[label_column], errors="coerce").fillna(0).astype(int).to_numpy()
    positives = int(labels.sum())
    if positives < min_positives and not allow_small_sample:
        raise PipelineError(
            f"{threshold_name} has only {positives} positive samples; minimum is {min_positives}. "
            "Extend the period or use --allow-small-sample for testing only."
        )
    if len(np.unique(labels)) < 2:
        raise PipelineError(f"{threshold_name} labels contain only one class")

    train_mask, calibration_mask, test_mask = chronological_splits(frame)
    pipeline_eval = base_pipeline(c_value)
    pipeline_eval.fit(features.loc[train_mask], labels[train_mask])
    raw_cal = pipeline_eval.predict_proba(features.loc[calibration_mask])[:, 1]
    calibrator_eval = fit_platt_calibrator(raw_cal, labels[calibration_mask])
    eval_bundle = {
        "pipeline": pipeline_eval,
        "calibrator": calibrator_eval,
        "feature_columns": list(features.columns),
    }
    test_probabilities = calibrated_predict(eval_bundle, features.loc[test_mask])
    train_climatology = float(labels[train_mask].mean())
    evaluation = evaluate_predictions(labels[test_mask], test_probabilities, train_climatology)
    test_groups = (
        pd.to_numeric(frame.loc[test_mask, "NOAA_REGION"], errors="coerce")
        .fillna(-1)
        .astype(int)
        .to_numpy()
    )
    evaluation["active_region_bootstrap_brier_skill_95"] = grouped_bootstrap_brier_skill(
        labels[test_mask], test_probabilities, test_groups, train_climatology
    )
    evaluation.update(
        {
            "train_samples": int(train_mask.sum()),
            "train_positives": int(labels[train_mask].sum()),
            "calibration_samples": int(calibration_mask.sum()),
            "calibration_positives": int(labels[calibration_mask].sum()),
            "calibrator": "Platt/logistic" if calibrator_eval is not None else "identity",
            "test_start": iso_z(frame.loc[test_mask, "ISSUE_TIME"].min().to_pydatetime()),
            "test_end": iso_z(frame.loc[test_mask, "ISSUE_TIME"].max().to_pydatetime()),
        }
    )

    # Production model: fit the classifier to all available rows; fit its
    # calibration map using out-of-fold predictions grouped by active region.
    groups = pd.to_numeric(frame["NOAA_REGION"], errors="coerce").fillna(-1).astype(int).to_numpy()
    production_calibrator, calibration_meta = oof_calibrator(
        frame, features, labels, groups, c_value
    )
    production_pipeline = base_pipeline(c_value)
    production_pipeline.fit(features, labels)
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "script_version": SCRIPT_VERSION,
        "threshold": threshold_name,
        "pipeline": production_pipeline,
        "calibrator": production_calibrator,
        "feature_columns": list(features.columns),
        "raw_parameters": list(SHARP_PARAMETERS),
        "trained_at": iso_z(utc_now()),
        "training_samples": int(len(frame)),
        "training_positives": positives,
        "training_prevalence": float(labels.mean()),
        "calibration": calibration_meta,
    }
    return bundle, evaluation


def beta_binomial_summary(
    successes: int,
    trials: int,
    *,
    alpha: float = X1_SEVERITY_PRIOR_ALPHA,
    beta: float = X1_SEVERITY_PRIOR_BETA,
) -> dict[str, float | int]:
    """Return a transparent smoothed estimate for a binomial conditional rate."""
    successes = int(successes)
    trials = int(trials)
    if trials < 1:
        raise PipelineError("At least one M1+ event is required to estimate the X/M reference rate")
    if successes < 0 or successes > trials:
        raise PipelineError(
            f"Invalid nested-event counts: X1+ successes={successes}, M1+ trials={trials}"
        )
    posterior_a = successes + float(alpha)
    posterior_b = (trials - successes) + float(beta)
    posterior_total = posterior_a + posterior_b
    mean = posterior_a / posterior_total
    variance = (
        posterior_a
        * posterior_b
        / (posterior_total**2 * (posterior_total + 1.0))
    )
    std = math.sqrt(max(variance, 0.0))
    return {
        "successes": successes,
        "trials": trials,
        "prior_alpha": float(alpha),
        "prior_beta": float(beta),
        "posterior_alpha": posterior_a,
        "posterior_beta": posterior_b,
        "posterior_mean": mean,
        "approx_95_lower": max(0.0, mean - 1.96 * std),
        "approx_95_upper": min(1.0, mean + 1.96 * std),
    }


def x1_predict(
    m1_probabilities: np.ndarray,
    x1_bundle: Mapping[str, Any],
    features: pd.DataFrame,
) -> np.ndarray:
    """Return independently calibrated direct X1+ probabilities, nested beneath M1+."""
    method = str(x1_bundle.get("method", ""))
    m1 = np.clip(np.asarray(m1_probabilities, dtype=float), 0.0, 1.0)
    if method != "direct_magnetic_x1":
        raise PipelineError(
            f"Unsupported X1+ model method {method!r}; retrain with the current pipeline"
        )
    x1 = calibrated_predict(x1_bundle, features)
    if len(x1) != len(m1):
        raise PipelineError("X1+ predictions do not align with M1+ predictions")
    return np.minimum(np.clip(x1, 0.0, 1.0), m1)


def train_x1_structure(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    *,
    c_value: float,
    min_positives: int,
    allow_small_sample: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Train a direct, calibrated X1+ magnetic classifier with M1+ nesting."""
    labels_m1 = pd.to_numeric(frame["LABEL_M1"], errors="coerce").fillna(0).astype(int).to_numpy()
    labels_x1 = pd.to_numeric(frame["LABEL_X1"], errors="coerce").fillna(0).astype(int).to_numpy()
    if np.any(labels_x1 > labels_m1):
        raise PipelineError("LABEL_X1 must be nested within LABEL_M1 for every row")
    positives = int(labels_x1.sum())
    if positives < min_positives and not allow_small_sample:
        raise PipelineError(
            f"X1+ has only {positives} positive region-days; minimum is {min_positives}."
        )
    if len(np.unique(labels_x1)) < 2:
        raise PipelineError("X1+ labels contain only one class")

    train_mask, calibration_mask, test_mask = chronological_splits(frame)
    columns = list(features.columns)
    x_c = min(float(c_value), 0.1)

    # Reproduce the M1 development model so the untouched X probabilities can
    # be constrained to the same holdout M1 probabilities.
    m_pipeline = base_pipeline(c_value)
    m_pipeline.fit(features.loc[train_mask], labels_m1[train_mask])
    m_calibrator = fit_platt_calibrator(
        m_pipeline.predict_proba(features.loc[calibration_mask])[:, 1],
        labels_m1[calibration_mask],
    )
    m_test = calibrated_predict(
        {"pipeline": m_pipeline, "calibrator": m_calibrator, "feature_columns": columns},
        features.loc[test_mask],
    )

    x_pipeline = base_pipeline(x_c)
    x_pipeline.fit(features.loc[train_mask], labels_x1[train_mask])
    x_calibrator = fit_platt_calibrator(
        x_pipeline.predict_proba(features.loc[calibration_mask])[:, 1],
        labels_x1[calibration_mask],
    )
    eval_bundle = {
        "pipeline": x_pipeline,
        "calibrator": x_calibrator,
        "feature_columns": columns,
    }
    x_test = np.minimum(calibrated_predict(eval_bundle, features.loc[test_mask]), m_test)
    climatology = float(labels_x1[train_mask].mean())
    evaluation = evaluate_predictions(labels_x1[test_mask], x_test, climatology)
    test_groups = (
        pd.to_numeric(frame.loc[test_mask, "NOAA_REGION"], errors="coerce")
        .fillna(-1).astype(int).to_numpy()
    )
    evaluation["active_region_bootstrap_brier_skill_95"] = grouped_bootstrap_brier_skill(
        labels_x1[test_mask], x_test, test_groups, climatology
    )

    development_mask = train_mask | calibration_mask
    reference_summary = beta_binomial_summary(
        int(labels_x1[development_mask].sum()), int(labels_m1[development_mask].sum())
    )
    reference_test = m_test * float(reference_summary["posterior_mean"])
    reference_evaluation = evaluate_predictions(
        labels_x1[test_mask], reference_test, climatology
    )
    reference_evaluation["active_region_bootstrap_brier_skill_95"] = grouped_bootstrap_brier_skill(
        labels_x1[test_mask], reference_test, test_groups, climatology
    )
    brier_improvement = None
    if reference_evaluation.get("brier_score") not in (None, 0.0):
        brier_improvement = 1.0 - float(evaluation["brier_score"]) / float(reference_evaluation["brier_score"])
    evaluation.update(
        {
            "method": "direct_magnetic_x1",
            "description": (
                "Strongly regularized direct X1+ classifier over magnetic state, "
                "24-hour evolution, disk position, and causal regional flare history; "
                "calibrated separately and constrained to P(X1+) <= P(M1+)."
            ),
            "train_samples": int(train_mask.sum()),
            "train_x1_positives": int(labels_x1[train_mask].sum()),
            "calibration_samples": int(calibration_mask.sum()),
            "calibration_x1_positives": int(labels_x1[calibration_mask].sum()),
            "test_x1_positives": int(labels_x1[test_mask].sum()),
            "x1_c": x_c,
            "calibrator": "Platt/logistic" if x_calibrator is not None else "identity",
            "constant_severity_reference": reference_evaluation,
            "development_conditional_x_given_m": reference_summary,
            "brier_improvement_vs_constant_severity": brier_improvement,
            "test_start": iso_z(frame.loc[test_mask, "ISSUE_TIME"].min().to_pydatetime()),
            "test_end": iso_z(frame.loc[test_mask, "ISSUE_TIME"].max().to_pydatetime()),
        }
    )

    groups = pd.to_numeric(frame["NOAA_REGION"], errors="coerce").fillna(-1).astype(int).to_numpy()
    production_calibrator, calibration_meta = oof_calibrator(
        frame, features, labels_x1, groups, x_c
    )
    production_pipeline = base_pipeline(x_c)
    production_pipeline.fit(features, labels_x1)
    production_reference = beta_binomial_summary(int(labels_x1.sum()), int(labels_m1.sum()))
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "script_version": SCRIPT_VERSION,
        "threshold": "X1+",
        "method": "direct_magnetic_x1",
        "pipeline": production_pipeline,
        "calibrator": production_calibrator,
        "feature_columns": columns,
        "raw_parameters": list(SHARP_PARAMETERS) + list(HISTORY_RAW_COLUMNS),
        "calibration": calibration_meta,
        "constant_severity_reference": production_reference,
        "trained_at": iso_z(utc_now()),
        "training_samples": int(len(frame)),
        "training_x1_positives": positives,
        "training_prevalence": float(labels_x1.mean()),
        "note": "Direct rare-event classifier; independently calibrated and clipped beneath M1+.",
    }
    return bundle, evaluation


def _legacy_train_x1_hierarchy_reference(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    *,
    c_value: float,
    min_positives: int,
    allow_small_sample: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reproduce the retired pre-v3 conditional X1+ experiment.

    The magnetic classifier is trained for M1+.  X1+ is estimated as

        P(X1+) = P(M1+) * P(X1+ | M1+, magnetic state/evolution)

    This is retained only to make earlier research artifacts auditable; the
    current training path never calls it. The conditional stage is trained only
    on M1+-producing region-days and uses
    a pre-specified reduced set of energy/current/PIL/size features. A constant
    Beta-binomial severity ratio is scored as a reference, never used as the
    production forecast.
    """
    labels_m1 = (
        pd.to_numeric(frame["LABEL_M1"], errors="coerce")
        .fillna(0)
        .astype(int)
        .to_numpy()
    )
    labels_x1 = (
        pd.to_numeric(frame["LABEL_X1"], errors="coerce")
        .fillna(0)
        .astype(int)
        .to_numpy()
    )
    if np.any(labels_x1 > labels_m1):
        raise PipelineError("LABEL_X1 must be nested within LABEL_M1 for every row")

    total_x1 = int(labels_x1.sum())
    total_m1 = int(labels_m1.sum())
    if total_x1 < min_positives and not allow_small_sample:
        raise PipelineError(
            f"X1+ has only {total_x1} positive samples; the hierarchical layer "
            f"requires at least {min_positives}. Extend the archive before training."
        )
    if total_m1 < 1:
        raise PipelineError("No M1+ events are available for the X1+ hierarchy")

    severity_columns = x1_severity_feature_columns()
    severity_features = features[severity_columns]
    conditional_mask = labels_m1 == 1
    conditional_negatives = int(conditional_mask.sum() - total_x1)
    if conditional_negatives < 3:
        raise PipelineError(
            "X1+ magnetic severity training requires at least three M1+/non-X1 region-days"
        )

    train_mask, calibration_mask, test_mask = chronological_splits(frame)

    # Reproduce the M1+ development fit without touching the chronological holdout.
    m1_eval_pipeline = base_pipeline(c_value)
    m1_eval_pipeline.fit(features.loc[train_mask], labels_m1[train_mask])
    raw_cal = m1_eval_pipeline.predict_proba(features.loc[calibration_mask])[:, 1]
    m1_eval_calibrator = fit_platt_calibrator(
        raw_cal, labels_m1[calibration_mask]
    )
    eval_bundle = {
        "pipeline": m1_eval_pipeline,
        "calibrator": m1_eval_calibrator,
        "feature_columns": list(features.columns),
    }
    m1_test_probabilities = calibrated_predict(
        eval_bundle, features.loc[test_mask]
    )

    development_mask = train_mask | calibration_mask
    development_m1 = int(labels_m1[development_mask].sum())
    development_x1 = int(labels_x1[development_mask].sum())
    development_summary = beta_binomial_summary(
        development_x1, development_m1
    )
    # Empirical-Bayes shrinkage limits coefficient noise while still allowing
    # magnetic structure to change the X/M ratio. Twenty X-positive cases are
    # treated as the transition scale toward a fully dynamic severity stage.
    development_dynamic_weight = development_x1 / (development_x1 + 20.0)

    # Fit the severity model to M1+-positive development rows only. Calibration
    # also remains conditional and chronologically separated from the fit.
    severity_train_mask = train_mask & conditional_mask
    severity_calibration_mask = calibration_mask & conditional_mask
    if labels_x1[severity_train_mask].sum() < 3 or len(np.unique(labels_x1[severity_train_mask])) < 2:
        raise PipelineError("The chronological X1+ training block has insufficient class support")
    severity_c = min(float(c_value), 0.25)
    severity_eval_pipeline = base_pipeline(severity_c)
    severity_eval_pipeline.fit(
        severity_features.loc[severity_train_mask], labels_x1[severity_train_mask]
    )
    raw_severity_cal = severity_eval_pipeline.predict_proba(
        severity_features.loc[severity_calibration_mask]
    )[:, 1]
    severity_eval_calibrator = fit_platt_calibrator(
        raw_severity_cal, labels_x1[severity_calibration_mask]
    )
    severity_eval_bundle = {
        "pipeline": severity_eval_pipeline,
        "calibrator": severity_eval_calibrator,
        "feature_columns": severity_columns,
    }
    severity_test_probabilities = calibrated_predict(
        severity_eval_bundle, severity_features.loc[test_mask]
    )
    severity_test_probabilities = (
        float(development_summary["posterior_mean"])
        + development_dynamic_weight
        * (
            severity_test_probabilities
            - float(development_summary["posterior_mean"])
        )
    )
    x1_test_probabilities = np.minimum(
        m1_test_probabilities * severity_test_probabilities,
        m1_test_probabilities,
    )

    # Constant-severity reference from development data only.
    constant_test_probabilities = np.minimum(
        m1_test_probabilities * float(development_summary["posterior_mean"]),
        m1_test_probabilities,
    )

    x1_training_climatology = float(labels_x1[train_mask].mean())
    evaluation = evaluate_predictions(
        labels_x1[test_mask],
        x1_test_probabilities,
        x1_training_climatology,
    )
    x_test_groups = (
        pd.to_numeric(frame.loc[test_mask, "NOAA_REGION"], errors="coerce")
        .fillna(-1)
        .astype(int)
        .to_numpy()
    )
    evaluation["active_region_bootstrap_brier_skill_95"] = grouped_bootstrap_brier_skill(
        labels_x1[test_mask],
        x1_test_probabilities,
        x_test_groups,
        x1_training_climatology,
    )
    constant_evaluation = evaluate_predictions(
        labels_x1[test_mask],
        constant_test_probabilities,
        x1_training_climatology,
    )
    constant_evaluation["active_region_bootstrap_brier_skill_95"] = grouped_bootstrap_brier_skill(
        labels_x1[test_mask],
        constant_test_probabilities,
        x_test_groups,
        x1_training_climatology,
    )
    conditional_test_mask = test_mask & conditional_mask
    conditional_evaluation = evaluate_predictions(
        labels_x1[conditional_test_mask],
        calibrated_predict(
            severity_eval_bundle, severity_features.loc[conditional_test_mask]
        ),
        float(labels_x1[severity_train_mask].mean()),
    )
    conditional_evaluation["active_region_bootstrap_brier_skill_95"] = grouped_bootstrap_brier_skill(
        labels_x1[conditional_test_mask],
        calibrated_predict(
            severity_eval_bundle, severity_features.loc[conditional_test_mask]
        ),
        pd.to_numeric(frame.loc[conditional_test_mask, "NOAA_REGION"], errors="coerce")
        .fillna(-1)
        .astype(int)
        .to_numpy(),
        float(labels_x1[severity_train_mask].mean()),
    )
    dynamic_brier = evaluation.get("brier_score")
    constant_brier = constant_evaluation.get("brier_score")
    brier_improvement = None
    if dynamic_brier is not None and constant_brier not in (None, 0.0):
        brier_improvement = 1.0 - float(dynamic_brier) / float(constant_brier)
    evaluation.update(
        {
            "method": "hierarchical_magnetic_x_given_m",
            "description": (
                "Calibrated SHARP M1+ probability multiplied by a calibrated, "
                "regularized magnetic P(X1+ | M1+) severity classifier."
            ),
            "train_samples": int(train_mask.sum()),
            "train_x1_positives": int(labels_x1[train_mask].sum()),
            "calibration_samples": int(calibration_mask.sum()),
            "calibration_x1_positives": int(labels_x1[calibration_mask].sum()),
            "test_x1_positives": int(labels_x1[test_mask].sum()),
            "severity_feature_count": len(severity_columns),
            "severity_c": severity_c,
            "dynamic_weight": development_dynamic_weight,
            "severity_calibrator": (
                "Platt/logistic" if severity_eval_calibrator is not None else "identity"
            ),
            "conditional_test": conditional_evaluation,
            "constant_severity_reference": constant_evaluation,
            "brier_improvement_vs_constant_severity": brier_improvement,
            "development_conditional_x_given_m": development_summary,
            "test_start": iso_z(
                frame.loc[test_mask, "ISSUE_TIME"].min().to_pydatetime()
            ),
            "test_end": iso_z(
                frame.loc[test_mask, "ISSUE_TIME"].max().to_pydatetime()
            ),
        }
    )

    conditional_frame = frame.loc[conditional_mask].reset_index(drop=True)
    conditional_features = severity_features.loc[conditional_mask].reset_index(drop=True)
    conditional_labels = labels_x1[conditional_mask]
    conditional_groups = (
        pd.to_numeric(conditional_frame["NOAA_REGION"], errors="coerce")
        .fillna(-1)
        .astype(int)
        .to_numpy()
    )
    production_calibrator, calibration_meta = oof_calibrator(
        conditional_frame,
        conditional_features,
        conditional_labels,
        conditional_groups,
        severity_c,
    )
    production_pipeline = base_pipeline(severity_c)
    production_pipeline.fit(conditional_features, conditional_labels)
    production_summary = beta_binomial_summary(total_x1, total_m1)
    production_dynamic_weight = total_x1 / (total_x1 + 20.0)
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "script_version": SCRIPT_VERSION,
        "threshold": "X1+",
        "method": "hierarchical_magnetic_x_given_m",
        "pipeline": production_pipeline,
        "calibrator": production_calibrator,
        "feature_columns": severity_columns,
        "raw_parameters": list(X1_SEVERITY_PARAMETERS),
        "calibration": calibration_meta,
        "constant_severity_reference": production_summary,
        "dynamic_weight": production_dynamic_weight,
        "trained_at": iso_z(utc_now()),
        "training_samples": int(len(frame)),
        "training_m1_positives": total_m1,
        "training_x1_positives": total_x1,
        "training_m1_non_x1": conditional_negatives,
        "training_prevalence": float(labels_x1.mean()),
        "note": (
            "Nested rare-event classifier. It models X/M severity from a reduced, "
            "pre-specified magnetic feature set and is multiplied by calibrated M1+."
        ),
    }
    return bundle, evaluation


def model_version_from_inputs(dataset: Path, start: dt.datetime, suffix: str = "") -> str:
    digest = sha256_file(dataset)[:10]
    stamp = start.strftime("%Y%m%d")
    return f"sharp-mag-{stamp}-{digest}{suffix}"


def train_models(args: argparse.Namespace) -> ModelPaths:
    dataset = args.dataset.expanduser().resolve()
    frame = load_training_table(dataset)
    features = engineer_features(frame)
    # Recompute engineered features to keep historical and live code paths identical.
    feature_columns = engineered_feature_columns()
    if features[feature_columns].notna().sum().sum() == 0:
        raise PipelineError("All engineered SHARP features are missing")

    model_paths = ModelPaths.from_directory(args.model_dir)
    model_paths.directory.mkdir(parents=True, exist_ok=True)
    training_started = utc_now()
    model_version = (
        args.model_version
        or model_version_from_inputs(dataset, training_started)
    )

    # M1+ receives the full calibrated magnetic classifier.
    m1_bundle, m1_eval = train_one_threshold(
        frame,
        features,
        label_column="LABEL_M1",
        threshold_name="M1+",
        c_value=args.c_value,
        min_positives=args.min_m1_positives,
        allow_small_sample=args.allow_small_sample,
    )

    # X1+ receives its own strongly regularized magnetic/history classifier,
    # calibrated independently and constrained beneath the M1+ probability.
    x1_bundle, x1_eval = train_x1_structure(
        frame,
        features,
        c_value=args.c_value,
        min_positives=args.min_x1_positives,
        allow_small_sample=args.allow_small_sample,
    )

    common_metadata = {
        "model_version": model_version,
        "historical_series": args.historical_series,
        "live_series": args.live_series,
        "issue_hour_utc": args.issue_hour,
        "input_lag_hours": args.input_lag_hours,
        "max_abs_longitude_deg": args.max_longitude,
        "max_abs_observer_velocity_m_s": args.max_obs_vr,
        "max_quality_integer": args.max_quality,
        "dataset_sha256": sha256_file(dataset),
    }
    m1_bundle.update(common_metadata)
    x1_bundle.update(common_metadata)

    joblib.dump(m1_bundle, model_paths.m1, compress=3)
    joblib.dump(x1_bundle, model_paths.x1, compress=3)

    coefficient_rows: list[dict[str, Any]] = []
    for model_name, bundle in (("M1+", m1_bundle), ("X1+ direct", x1_bundle)):
        fitted: Pipeline = bundle["pipeline"]
        coefficients = fitted.named_steps["classifier"].coef_[0]
        medians = fitted.named_steps["imputer"].statistics_
        means = fitted.named_steps["scaler"].mean_
        scales = fitted.named_steps["scaler"].scale_
        for feature, coefficient, median, mean, scale in zip(
            bundle["feature_columns"], coefficients, medians, means, scales
        ):
            coefficient_rows.append(
                {
                    "model": model_name,
                    "feature": feature,
                    "standardized_coefficient": float(coefficient),
                    "absolute_coefficient": abs(float(coefficient)),
                    "imputation_median": float(median),
                    "training_mean_after_imputation": float(mean),
                    "training_scale": float(scale),
                }
            )
    coefficient_frame = pd.DataFrame(coefficient_rows).sort_values(
        ["model", "absolute_coefficient"], ascending=[True, False]
    )
    coefficient_path = model_paths.directory / "sharp_mag_coefficients.csv"
    coefficient_frame.to_csv(coefficient_path, index=False)

    report = {
        "schema_version": SCHEMA_VERSION,
        "script_version": SCRIPT_VERSION,
        "model_version": model_version,
        "research_only": True,
        "training_started": iso_z(training_started),
        "training_finished": iso_z(utc_now()),
        "dataset": dataset.name,
        "dataset_sha256": sha256_file(dataset),
        "samples": int(len(frame)),
        "date_start": iso_z(frame["ISSUE_TIME"].min().to_pydatetime()),
        "date_end": iso_z(frame["ISSUE_TIME"].max().to_pydatetime()),
        "features": feature_columns,
        "M1+": m1_eval,
        "X1+": x1_eval,
        "prediction_methods": {
            "M1+": "regularized logistic SHARP classifier with probability calibration",
            "X1+": (
                "strongly regularized direct magnetic/history X1+ classifier "
                "with independent calibration and P(X1+) <= P(M1+) constraint"
            ),
        },
        "artifacts": {
            "coefficients": coefficient_path.name,
            "coefficients_sha256": sha256_file(coefficient_path),
        },
        "validation_note": (
            "M1+ scores use a chronologically later untouched holdout block. "
            "The production M1+ classifier is refit to all rows and calibrated "
            "from out-of-fold predictions grouped by NOAA active region. "
            "X1+ holdout probabilities use a separately fitted direct magnetic/history "
            "stage; the constant X/M ratio is retained only "
            "as a scored reference."
        ),
    }
    atomic_write_json(model_paths.report, report)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "script_version": SCRIPT_VERSION,
        "model_version": model_version,
        "operational": False,
        "created_at": iso_z(utc_now()),
        "models": {
            "m1": {
                "file": model_paths.m1.name,
                "sha256": sha256_file(model_paths.m1),
                "method": "calibrated_sharp_classifier",
            },
            "x1": {
                "file": model_paths.x1.name,
                "sha256": sha256_file(model_paths.x1),
                "method": "direct_magnetic_x1",
            },
        },
        "coefficients": {
            "file": coefficient_path.name,
            "sha256": sha256_file(coefficient_path),
        },
        "training_report": model_paths.report.name,
        "training_dataset_sha256": sha256_file(dataset),
        "historical_series": args.historical_series,
        "live_series": args.live_series,
        "issue_hour_utc": args.issue_hour,
        "input_lag_hours": args.input_lag_hours,
        "valid_window": "next UTC calendar day 00:00-24:00Z",
        "quality_filters": {
            "max_abs_longitude_deg": args.max_longitude,
            "max_abs_observer_velocity_m_s": args.max_obs_vr,
            "max_quality_integer": args.max_quality,
            "max_live_input_age_hours": args.max_input_age_hours,
            "multi_region_harps_training": "excluded",
            "multi_region_harps_live": "expanded with shared-HARP disclosure",
        },
        "features": feature_columns,
        "x1_model": {
            "method": x1_bundle["method"],
            "features": x1_bundle["feature_columns"],
            "constant_severity_reference": x1_bundle["constant_severity_reference"],
        },
        "packages": {
            "python": sys.version.split()[0],
            **exact_runtime_requirements(),
        },
        "warning": (
            "Research model. M1+ is a calibrated SHARP classifier; X1+ is a "
            "calibrated direct magnetic/history rare-event classifier constrained beneath M1+. Do not mark operational until "
            "independent backtesting and shadow verification are complete."
        ),
    }
    runtime_requirements = (
        model_paths.directory / "requirements-runtime-pinned.txt"
    )
    pinned = exact_runtime_requirements()
    atomic_write_text(
        runtime_requirements,
        "\n".join(
            f"{name}=={version}"
            for name, version in pinned.items()
            if version != "not-installed"
        )
        + "\n",
    )
    manifest["runtime_requirements"] = runtime_requirements.name
    atomic_write_json(model_paths.manifest, manifest)
    LOGGER.info("Model artifacts written to %s", model_paths.directory)
    return model_paths


def load_models(model_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], ModelPaths]:
    paths = ModelPaths.from_directory(model_dir)
    for path in (paths.m1, paths.x1, paths.manifest):
        if not path.exists():
            raise PipelineError(f"Required model artifact is missing: {path}")
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    trained_sklearn = str(manifest.get("packages", {}).get("scikit-learn", ""))
    current_sklearn = package_version("scikit-learn")
    if major_minor(trained_sklearn) and major_minor(current_sklearn) != major_minor(trained_sklearn):
        raise PipelineError(
            "scikit-learn version mismatch: model was trained with "
            f"{trained_sklearn}, but this environment has {current_sklearn}. "
            "Install models/requirements-runtime-pinned.txt before running inference."
        )
    expected = manifest.get("models", {})
    for key, path in (("m1", paths.m1), ("x1", paths.x1)):
        expected_hash = expected.get(key, {}).get("sha256")
        if expected_hash and sha256_file(path) != expected_hash:
            raise PipelineError(f"Checksum mismatch for {path.name}; recopy or retrain the artifact")
    return joblib.load(paths.m1), joblib.load(paths.x1), manifest, paths


def latest_live_rows(
    *,
    series: str,
    issue_time: dt.datetime,
    input_lag_hours: int,
    query_hours: int,
    include_multi_region_harps: bool,
    max_longitude: float,
    max_obs_vr: float,
    max_quality: int,
    max_input_age_hours: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    target = ensure_utc(issue_time) - dt.timedelta(hours=input_lag_hours)
    query_start = target - dt.timedelta(hours=query_hours)
    raw = clean_sharp_frame(query_drms(live_record_set(series, query_start, query_hours + 1), SHARP_QUERY_KEYS))
    raw = raw[raw["T_REC_UTC"] <= pd.Timestamp(target)].copy()
    if raw.empty:
        raise PipelineError(f"No {series} records were available at or before {iso_z(target)}")

    # Select the latest record for each HARP and a preceding record near 24 h earlier.
    current_indices = raw.groupby("HARPNUM")["T_REC_UTC"].idxmax()
    current_raw = raw.loc[current_indices].copy()
    expanded_current, mapping_stats = expand_single_region_rows(
        current_raw, include_multi_region_harps=include_multi_region_harps
    )
    current, quality_stats = apply_sharp_quality_filters(
        expanded_current,
        max_longitude=max_longitude,
        max_obs_vr=max_obs_vr,
        max_quality=max_quality,
    )
    if current.empty:
        return current, {
            "target_time": iso_z(target),
            "raw_records": len(raw),
            "mapping": mapping_stats,
            "quality": quality_stats,
            "message": "No single-region SHARP records passed quality control",
        }

    # Freshness is measured against the nominal SHARP input target, not the
    # forecast issue time.  A perfectly on-target 18Z record for a 21Z issue
    # should therefore have zero target-age rather than being treated as 3 h old.
    current["TARGET_AGE_HOURS"] = (
        pd.Timestamp(target) - current["T_REC_UTC"]
    ).dt.total_seconds() / 3600.0
    current["DATA_AGE_HOURS"] = (
        pd.Timestamp(issue_time) - current["T_REC_UTC"]
    ).dt.total_seconds() / 3600.0
    freshest_target_age = float(current["TARGET_AGE_HOURS"].min()) if len(current) else math.nan
    freshest_issue_age = float(current["DATA_AGE_HOURS"].min()) if len(current) else math.nan
    latest_before_age_filter = current["T_REC_UTC"].max() if len(current) else pd.NaT
    current = current[current["TARGET_AGE_HOURS"] <= max_input_age_hours].copy()
    if current.empty:
        latest_text = (
            iso_z(latest_before_age_filter.to_pydatetime())
            if pd.notna(latest_before_age_filter) else "unknown"
        )
        return current, {
            "target_time": iso_z(target),
            "latest_candidate_record": latest_text,
            "freshest_target_age_hours": freshest_target_age,
            "freshest_issue_age_hours": freshest_issue_age,
            "raw_records": len(raw),
            "mapping": mapping_stats,
            "quality": quality_stats,
            "message": (
                f"All SHARP records exceeded {max_input_age_hours:g} h staleness relative to "
                f"the nominal input target {iso_z(target)}. Latest candidate was {latest_text} "
                f"({freshest_target_age:.1f} h behind target; {freshest_issue_age:.1f} h old at issue)."
            ),
        }

    current = current.sort_values(["NOAA_REGION", "AREA_ACR", "T_REC_UTC"], ascending=[True, False, False])
    current = current.drop_duplicates("NOAA_REGION", keep="first")

    prior_rows: list[dict[str, Any]] = []
    for current_record in current.to_dict(orient="records"):
        harp_number = current_record.get("HARPNUM")
        current_time = pd.Timestamp(current_record["T_REC_UTC"])
        candidates = raw[
            (raw["HARPNUM"] == harp_number)
            & (raw["T_REC_UTC"] <= current_time - pd.Timedelta(hours=18))
            & (raw["T_REC_UTC"] >= current_time - pd.Timedelta(hours=36))
        ]
        if candidates.empty:
            prior_rows.append({})
            continue
        prior_rows.append(candidates.loc[candidates["T_REC_UTC"].idxmax()].to_dict())

    for parameter in SHARP_PARAMETERS:
        current[f"PREV_{parameter}"] = [row.get(parameter, np.nan) for row in prior_rows]
    current["ISSUE_TIME"] = pd.Timestamp(issue_time)
    current["ISSUE_DATE"] = ensure_utc(issue_time).date()
    stats = {
        "target_time": iso_z(target),
        "latest_record": iso_z(current["T_REC_UTC"].max().to_pydatetime()),
        "oldest_retained_record": iso_z(current["T_REC_UTC"].min().to_pydatetime()),
        "raw_records": len(raw),
        "retained_regions": len(current),
        "mapping": mapping_stats,
        "quality": quality_stats,
    }
    return current, stats


def fetch_swpc_region_metadata() -> dict[int, dict[str, Any]]:
    session = request_session()
    try:
        response = session.get(SWPC_SOLAR_REGIONS_URL, timeout=30)
        response.raise_for_status()
        rows = response.json()
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("SWPC solar-region metadata unavailable: %s", exc)
        return {}
    if not isinstance(rows, list):
        return {}
    latest: dict[int, tuple[pd.Timestamp, dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        region = canonical_noaa_region(row.get("region"))
        if region is None:
            continue
        timestamp = pd.to_datetime(
            row.get("observation_time") or row.get("observed_date") or row.get("first_date"),
            errors="coerce",
            utc=True,
        )
        if pd.isna(timestamp):
            timestamp = pd.Timestamp.min.tz_localize("UTC")
        if region not in latest or timestamp > latest[region][0]:
            latest[region] = (timestamp, row)
    return {region: row for region, (_, row) in latest.items()}


def fetch_swpc_flare_history() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return the recent SWPC edited-event XRA catalog for causal live features."""
    columns = [
        "EVENT_TIME", "FLARE_CLASS", "NOAA_REGION_NORM", "IS_M1_PLUS", "IS_X1_PLUS"
    ]
    session = request_session()
    try:
        response = session.get(SWPC_EDITED_EVENTS_URL, timeout=30)
        response.raise_for_status()
        rows = response.json()
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("SWPC edited-event history unavailable: %s", exc)
        return pd.DataFrame(columns=columns), {"available": False, "message": str(exc)}
    events: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or str(row.get("type") or "").upper() != "XRA":
            continue
        flare_class = str(row.get("particulars1") or "").strip().upper()
        parsed = re.match(r"^([MX])(\d+(?:\.\d+)?)$", flare_class)
        region = normalize_region_for_flare_catalog(row.get("region"))
        event_time = pd.to_datetime(
            row.get("begin_datetime") or row.get("max_datetime"), errors="coerce", utc=True
        )
        if not parsed or region is None or pd.isna(event_time):
            continue
        letter, coefficient_text = parsed.groups()
        coefficient = float(coefficient_text)
        events.append(
            {
                "EVENT_TIME": event_time,
                "FLARE_CLASS": flare_class,
                "NOAA_REGION_NORM": region,
                "IS_M1_PLUS": bool(letter == "M" and coefficient >= 1.0) or letter == "X",
                "IS_X1_PLUS": bool(letter == "X" and coefficient >= 1.0),
            }
        )
    frame = pd.DataFrame(events, columns=columns)
    if not frame.empty:
        frame = frame.drop_duplicates(["EVENT_TIME", "FLARE_CLASS", "NOAA_REGION_NORM"])
        frame = frame.sort_values("EVENT_TIME")
    return frame, {
        "available": True,
        "source": SWPC_EDITED_EVENTS_URL,
        "events": int(len(frame)),
        "m1_plus_events": int(frame["IS_M1_PLUS"].sum()) if len(frame) else 0,
        "x1_plus_events": int(frame["IS_X1_PLUS"].sum()) if len(frame) else 0,
    }


def fetch_swpc_full_disk(valid_date: dt.date) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Read the official SWPC whole-disk M/X probability for one forecast day."""
    session = request_session()
    try:
        response = session.get(SWPC_THREE_DAY_URL, timeout=30)
        response.raise_for_status()
        text = response.text
    except requests.RequestException as exc:
        LOGGER.warning("SWPC three-day flare forecast unavailable: %s", exc)
        return None, {"available": False, "message": str(exc)}
    dates_match = re.search(r"^:Prediction_dates:\s+(.+)$", text, re.MULTILINE)
    m_match = re.search(r"^Class_M\s+([\d\s]+)$", text, re.MULTILINE)
    x_match = re.search(r"^Class_X\s+([\d\s]+)$", text, re.MULTILINE)
    issued_match = re.search(r"^:Issued:\s+(.+?)\s*$", text, re.MULTILINE)
    if not (dates_match and m_match and x_match):
        return None, {"available": False, "message": "required SWPC fields were not parsed"}
    date_tokens = re.findall(r"\d{4}\s+[A-Z][a-z]{2}\s+\d{1,2}", dates_match.group(1))
    dates = [dt.datetime.strptime(token, "%Y %b %d").date() for token in date_tokens]
    m_values = [float(value) for value in m_match.group(1).split()]
    x_values = [float(value) for value in x_match.group(1).split()]
    if valid_date not in dates:
        return None, {
            "available": False,
            "message": f"SWPC product does not cover {valid_date}",
            "covered_dates": [str(value) for value in dates],
        }
    index = dates.index(valid_date)
    if index >= len(m_values) or index >= len(x_values):
        return None, {"available": False, "message": "SWPC probability columns are incomplete"}
    member = {
        "m1": m_values[index],
        "x1": min(x_values[index], m_values[index]),
        "source": "NOAA/SWPC 3-day whole-disk flare forecast",
        "quality": "official-operational",
        "method": "official_swpc",
    }
    return member, {
        "available": True,
        "source": SWPC_THREE_DAY_URL,
        "issued": issued_match.group(1) if issued_match else None,
        "valid_date": str(valid_date),
    }


def swpc_region_member(metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    m1 = pd.to_numeric(metadata.get("m_flare_probability"), errors="coerce")
    x1 = pd.to_numeric(metadata.get("x_flare_probability"), errors="coerce")
    if pd.isna(m1) and pd.isna(x1):
        return None
    m_value = float(m1) if pd.notna(m1) else None
    x_value = float(x1) if pd.notna(x1) else None
    if m_value is not None and x_value is not None:
        x_value = min(x_value, m_value)
    return {
        "m1": m_value,
        "x1": x_value,
        "source": "NOAA/SWPC numbered-region flare forecast",
        "quality": "official-operational",
        "method": "official_swpc",
    }


def active_swpc_region_metadata(
    metadata: Mapping[int, Mapping[str, Any]], issue_time: dt.datetime
) -> dict[int, Mapping[str, Any]]:
    """Select the freshest visible numbered-region records for this cycle."""
    selected: dict[int, Mapping[str, Any]] = {}
    issue = pd.Timestamp(ensure_utc(issue_time))
    for region, row in metadata.items():
        observed = pd.to_datetime(
            row.get("observation_time") or row.get("observed_date"),
            errors="coerce",
            utc=True,
        )
        if pd.isna(observed) or abs((issue - observed).total_seconds()) > 36 * 3600:
            continue
        if str(row.get("status") or "").lower() == "d":
            continue
        longitude = pd.to_numeric(row.get("longitude"), errors="coerce")
        if pd.notna(longitude) and abs(float(longitude)) > 90:
            continue
        selected[int(region)] = row
    return selected


def morphology_fallback(
    metadata: Mapping[str, Any],
    m1_bundle: Mapping[str, Any],
    x1_bundle: Mapping[str, Any],
) -> tuple[float, float, str, list[str]]:
    """Return an honest current-state fallback when SHARP cannot be mapped."""
    mcintosh = str(metadata.get("spot_class") or "").strip().upper()
    lookup = LEGACY_MCSTAT_B12.get(mcintosh)
    if lookup is not None:
        m1 = float(lookup[0]) / 100.0
        x1 = min(float(lookup[1]) / 100.0, m1)
        return (
            m1,
            x1,
            "Bloomfield et al. (2012) McIntosh-Poisson coverage fallback",
            [
                f"McIntosh {mcintosh}",
                "No accepted live single-region SHARP vector",
            ],
        )
    m1 = float(m1_bundle.get("training_prevalence", 0.0) or 0.0)
    x1 = min(float(x1_bundle.get("training_prevalence", 0.0) or 0.0), m1)
    return (
        m1,
        x1,
        "WXF training-climatology coverage fallback",
        [
            "McIntosh class unavailable or absent from published table",
            "No accepted live single-region SHARP vector",
        ],
    )


def feature_contributions(bundle: Mapping[str, Any], features: pd.DataFrame) -> list[tuple[str, float, float]]:
    pipeline: Pipeline = bundle["pipeline"]
    columns: list[str] = list(bundle["feature_columns"])
    x = features[columns]
    imputed = pipeline.named_steps["imputer"].transform(x)
    scaled = pipeline.named_steps["scaler"].transform(imputed)
    coefficients = pipeline.named_steps["classifier"].coef_[0]
    contributions = scaled[0] * coefficients
    raw_values = x.iloc[0].to_numpy(dtype=float)
    order = np.argsort(np.abs(contributions))[::-1]
    return [(columns[index], float(contributions[index]), float(raw_values[index])) for index in order]


def driver_phrase(feature: str, contribution: float, raw_value: float) -> str:
    if feature.endswith("__DELTA24H"):
        parameter = feature.removesuffix("__DELTA24H")
        direction = "rising" if raw_value > 0 else "falling" if raw_value < 0 else "steady"
        return f"{direction} {DISPLAY_NAMES.get(parameter, parameter)}"
    if feature.endswith("__LOG1P"):
        parameter = feature.removesuffix("__LOG1P")
        level = "elevated" if contribution > 0 else "lower"
        return f"{level} {DISPLAY_NAMES.get(parameter, parameter)}"
    if feature == "ABS_LON_FWT":
        return "farther from disk center" if raw_value >= 40 else "nearer disk center"
    if feature == "LAT_FWT_VALUE":
        return "active-region latitude contribution"
    return DISPLAY_NAMES.get(feature, feature)


def top_drivers(
    m1_bundle: Mapping[str, Any],
    x1_bundle: Mapping[str, Any],
    features: pd.DataFrame,
    limit: int = 4,
) -> list[str]:
    """Explain both magnetic classifiers without treating coefficients as causality."""
    m_candidates: list[tuple[float, str]] = []
    for feature, contribution, raw_value in feature_contributions(
        m1_bundle, features
    )[: max(5, limit)]:
        phrase = driver_phrase(feature, contribution, raw_value)
        m_candidates.append((abs(contribution), f"M1+: {phrase}"))

    x_candidates: list[tuple[float, str]] = []
    for feature, contribution, raw_value in feature_contributions(
        x1_bundle, features
    )[: max(5, limit)]:
        phrase = driver_phrase(feature, contribution, raw_value)
        x_candidates.append((abs(contribution), f"X1+ direct: {phrase}"))

    output: list[str] = []
    m_slots = max(1, limit // 2)
    for _, phrase in sorted(m_candidates, reverse=True):
        if phrase not in output:
            output.append(phrase)
        if len(output) >= m_slots:
            break
    for _, phrase in sorted(x_candidates, reverse=True):
        if phrase not in output:
            output.append(phrase)
        if len(output) >= limit:
            break
    return output[:limit]


def combine_region_probabilities(values: Iterable[float]) -> float | None:
    probabilities = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not probabilities:
        return None
    survival = 1.0
    for probability in probabilities:
        survival *= 1.0 - min(max(probability, 0.0), 1.0)
    return min(max(1.0 - survival, 0.0), 1.0)


def percent(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(min(max(value, 0.0), 1.0) * 100.0, 1)


def create_forecast_payload(
    *,
    live_rows: pd.DataFrame,
    m1_bundle: Mapping[str, Any],
    x1_bundle: Mapping[str, Any],
    manifest: Mapping[str, Any],
    issue_time: dt.datetime,
    input_stats: Mapping[str, Any],
    operational: bool,
    region_metadata: Mapping[int, Mapping[str, Any]] | None = None,
    swpc_full_disk: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    valid_start = next_utc_midnight(issue_time)
    valid_end = valid_start + dt.timedelta(days=1)
    swpc_all = dict(region_metadata) if region_metadata is not None else fetch_swpc_region_metadata()
    swpc = active_swpc_region_metadata(swpc_all, issue_time)
    regions: list[dict[str, Any]] = []
    component_probabilities: dict[str, tuple[float, float]] = {}
    represented_regions: set[int] = set()
    sharp_region_count = 0
    shared_harp_region_count = 0
    fallback_region_count = 0

    if not live_rows.empty:
        features = engineer_features(live_rows)
        m1_probabilities = calibrated_predict(m1_bundle, features)
        x1_probabilities = x1_predict(
            m1_probabilities, x1_bundle, features
        )

        for position, (_, row) in enumerate(live_rows.reset_index(drop=True).iterrows()):
            region_number = canonical_noaa_region(row["NOAA_REGION"])
            if region_number is None:
                continue
            metadata = swpc.get(region_number, {})
            row_features = features.iloc[[position]]
            m1_probability = float(m1_probabilities[position])
            x1_probability = float(x1_probabilities[position])
            harp_number = int(row.get("HARPNUM", -1))
            component_probabilities.setdefault(
                f"HARP{harp_number}", (m1_probability, x1_probability)
            )
            represented_regions.add(region_number)
            sharp_region_count += 1
            location = str(metadata.get("location") or "").strip()
            mcintosh = str(metadata.get("spot_class") or "").strip().upper()
            data_age = float(row.get("DATA_AGE_HOURS", np.nan))
            harp_region_count = int(row.get("HARP_REGION_COUNT", 1) or 1)
            shared_harp = harp_region_count > 1
            if shared_harp:
                shared_harp_region_count += 1
            regions.append(
                {
                    "id": f"AR{region_number}",
                    "label": f"AR {region_number}",
                    "location": location,
                    "mcintosh": mcintosh,
                    "quality": {
                        "level": "research" if not operational else "operational",
                        "message": (
                            f"SHARP NRT record age {data_age:.1f} h; "
                            f"{'shared ' + str(harp_region_count) + '-region HARP' if shared_harp else 'single-region HARP'}; "
                            f"|LON_FWT|={abs(float(row['LON_FWT'])):.1f}°"
                        ),
                    },
                    "members": {
                        "sharpmag": {
                            "m1": percent(m1_probability),
                            "x1": percent(x1_probability),
                            "source": (
                                f"WXF {manifest.get('model_version', 'unknown')} "
                                "(independently calibrated magnetic M1/X1)"
                            ),
                            "quality": (
                                "research-shared-harp" if shared_harp
                                else "operational" if operational else "research"
                            ),
                            "method": "sharp_magnetic",
                            "component_id": f"HARP{harp_number}",
                        }
                    },
                    "drivers": top_drivers(m1_bundle, x1_bundle, row_features),
                }
            )
            official_region = swpc_region_member(metadata)
            if official_region is not None:
                regions[-1]["members"]["swpc"] = official_region

    # Every fresh visible numbered region gets a WXF value. Regions lacking an
    # accepted magnetic vector receive a distinctly labelled morphology or
    # climatology fallback instead of silently disappearing.
    for region_number, metadata in sorted(swpc.items()):
        if region_number in represented_regions:
            continue
        m1_probability, x1_probability, source, drivers = morphology_fallback(
            metadata, m1_bundle, x1_bundle
        )
        component_id = f"AR{region_number}-fallback"
        component_probabilities[component_id] = (m1_probability, x1_probability)
        fallback_region_count += 1
        location = str(metadata.get("location") or "").strip()
        mcintosh = str(metadata.get("spot_class") or "").strip().upper()
        regions.append(
            {
                "id": f"AR{region_number}",
                "label": f"AR {region_number}",
                "location": location,
                "mcintosh": mcintosh,
                "quality": {
                    "level": "fallback",
                    "message": (
                        "Numbered region is represented, but no accepted live SHARP "
                        "vector was available; this is not a SHARP magnetic inference."
                    ),
                },
                "members": {
                    "sharpmag": {
                        "m1": percent(m1_probability),
                        "x1": percent(x1_probability),
                        "source": source,
                        "quality": "research-coverage-fallback",
                        "method": "morphology_fallback",
                        "component_id": component_id,
                    }
                },
                "drivers": drivers,
            }
        )
        official_region = swpc_region_member(metadata)
        if official_region is not None:
            regions[-1]["members"]["swpc"] = official_region

    regions.sort(key=lambda item: int(re.sub(r"\D", "", str(item.get("id", "0"))) or 0))

    full_m1 = combine_region_probabilities(value[0] for value in component_probabilities.values())
    full_x1 = combine_region_probabilities(value[1] for value in component_probabilities.values())
    full_disk: dict[str, Any] = {
        "id": "full-disk",
        "label": "Full Disk",
        "quality": {
            "level": "research" if not operational else "operational",
            "message": (
                "Visible-disk WXF coverage aggregate. Accepted SHARP components and "
                "explicit morphology/climatology fallbacks are combined once per HARP/region."
            ),
        },
        "drivers": [
            f"{len(regions)} numbered active regions represented",
            f"{sharp_region_count} SHARP region values; {fallback_region_count} fallbacks",
            "Regional probabilities combined as 1 - product(1 - p_i)",
            "Shared HARPs counted once in the full-disk aggregate",
            "No unnumbered or farside residual term",
        ],
        "members": {},
    }
    if full_m1 is not None or full_x1 is not None:
        full_disk["members"]["sharpmag"] = {
            "m1": percent(full_m1),
            "x1": percent(min(full_x1 or 0.0, full_m1 or 1.0)),
            "source": f"WXF {manifest.get('model_version', 'unknown')} regional combination",
            "quality": "operational" if operational else "research",
            "method": "regional_union_with_explicit_fallbacks",
        }
    if swpc_full_disk is not None:
        full_disk["members"]["swpc"] = dict(swpc_full_disk)

    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": manifest.get("model_version"),
        "script_version": SCRIPT_VERSION,
        "operational": bool(operational),
        "probability_scale": "percent",
        "issued": iso_z(issue_time),
        "valid_start": iso_z(valid_start),
        "valid_end": iso_z(valid_end),
        "quality": {
            "level": "operational" if operational else "research",
            "message": (
                "Daily WXF inference from a saved calibrated M1+ model and "
                "an independently calibrated magnetic/history X1+ model. "
                "Research/shadow guidance unless "
                "explicitly validated and marked operational."
            ),
        },
        "input": {
            "series": manifest.get("live_series", DEFAULT_LIVE_SERIES),
            **dict(input_stats),
        },
        "wxf_full_disk": {
            "method": "union_of_unique_region_components",
            "formula": "1 - product(1 - regional probability)",
            "components": len(component_probabilities),
            "numbered_regions": len(regions),
            "sharp_regions": sharp_region_count,
            "shared_harp_region_values": shared_harp_region_count,
            "fallback_regions": fallback_region_count,
            "unnumbered_or_farside_residual": False,
            "note": (
                "Coverage aggregate, not a separately trained full-disk classifier. "
                "Shared HARP probabilities are included once."
            ),
        },
        "wxf_region_components": [
            {
                "component_id": component_id,
                "m1": probability_m1 * 100.0,
                "x1": probability_x1 * 100.0,
            }
            for component_id, (probability_m1, probability_x1)
            in sorted(component_probabilities.items())
        ],
        "regions": [full_disk, *regions],
    }


def flare_guidance_javascript(payload: Mapping[str, Any]) -> str:
    return (
        "/* Generated by sharp_mag_pipeline.py; replace at each formal 21Z cycle. */\n"
        "window.FLARE_GUIDANCE_PAYLOAD = "
        + json.dumps(payload, indent=2, sort_keys=False, default=json_default)
        + ";\n"
    )


def forecast(args: argparse.Namespace) -> Path:
    m1_bundle, x1_bundle, manifest, _ = load_models(args.model_dir)
    issue_time = resolve_issue_time(args.issue_time, args.issue_hour)
    input_lag_hours = int(manifest.get("input_lag_hours", args.input_lag_hours))
    live_series = args.live_series or str(manifest.get("live_series", DEFAULT_LIVE_SERIES))
    max_longitude = float(manifest.get("quality_filters", {}).get("max_abs_longitude_deg", args.max_longitude))
    max_obs_vr = float(
        manifest.get("quality_filters", {}).get("max_abs_observer_velocity_m_s", args.max_obs_vr)
    )
    max_quality = int(manifest.get("quality_filters", {}).get("max_quality_integer", args.max_quality))
    max_input_age = float(
        manifest.get("quality_filters", {}).get("max_live_input_age_hours", args.max_input_age_hours)
    )

    live_rows, input_stats = latest_live_rows(
        series=live_series,
        issue_time=issue_time,
        input_lag_hours=input_lag_hours,
        query_hours=args.query_hours,
        include_multi_region_harps=True,
        max_longitude=max_longitude,
        max_obs_vr=max_obs_vr,
        max_quality=max_quality,
        max_input_age_hours=max_input_age,
    )
    if live_rows.empty and not args.allow_empty:
        raise PipelineError(
            f"No live SHARP regions passed quality control: {input_stats.get('message', 'unknown reason')}. "
            "Use --allow-empty only if replacing the previous output with an explicit no-data payload is intended."
        )

    flare_history, history_stats = fetch_swpc_flare_history()
    live_rows = add_causal_flare_history(live_rows, flare_history)
    swpc_full_disk, swpc_stats = fetch_swpc_full_disk(next_utc_midnight(issue_time).date())
    input_stats = {
        **dict(input_stats),
        "flare_history": history_stats,
        "swpc_full_disk": swpc_stats,
    }

    payload = create_forecast_payload(
        live_rows=live_rows,
        m1_bundle=m1_bundle,
        x1_bundle=x1_bundle,
        manifest=manifest,
        issue_time=issue_time,
        input_stats=input_stats,
        operational=args.operational,
        swpc_full_disk=swpc_full_disk,
    )
    output = args.output.expanduser().resolve()
    atomic_write_json(output, payload)
    js_output = (
        args.js_output.expanduser().resolve()
        if args.js_output
        else output.with_name("flare_guidance.js")
    )
    atomic_write_text(js_output, flare_guidance_javascript(payload))
    if args.history:
        append_jsonl(args.history, payload)
    LOGGER.info("Forecast written: %s", output)
    LOGGER.info("Shared-folder payload written: %s", js_output)
    return output


def doctor(args: argparse.Namespace) -> None:
    report: dict[str, Any] = {
        "script_version": SCRIPT_VERSION,
        "python": sys.version,
        "packages": {
            name: package_version(name)
            for name in ("numpy", "pandas", "requests", "scikit-learn", "joblib", "drms", "packaging")
        },
        "network": {},
    }
    if args.network:
        try:
            session = request_session()
            response = session.get(SWPC_SOLAR_REGIONS_URL, timeout=20)
            response.raise_for_status()
            report["network"]["swpc"] = f"ok ({len(response.content)} bytes)"
        except Exception as exc:  # pragma: no cover - environment dependent
            report["network"]["swpc"] = f"failed: {exc}"
        try:
            sample = query_drms(
                f"{DEFAULT_LIVE_SERIES}[][2024.01.01_18:00:00_TAI/12m]",
                ("T_REC", "HARPNUM", "NOAA_ARS", "R_VALUE"),
            )
            report["network"]["jsoc"] = f"ok ({len(sample)} rows)"
        except Exception as exc:  # pragma: no cover - environment dependent
            report["network"]["jsoc"] = f"failed: {exc}"
    print(json.dumps(report, indent=2))


def synthetic_training_table(path: Path, days: int = 900, regions_per_day: int = 6) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    rows: list[dict[str, Any]] = []
    start = dt.datetime(2018, 1, 1, 21, tzinfo=UTC)
    previous: dict[int, dict[str, float]] = {}
    for day in range(days):
        issue = start + dt.timedelta(days=day)
        for region_index in range(regions_per_day):
            region = 12000 + (day // 10) * regions_per_day + region_index
            record: dict[str, Any] = {
                "ISSUE_TIME": issue,
                "ISSUE_DATE": issue.date(),
                "VALID_DATE": issue.date() + dt.timedelta(days=1),
                "NOAA_REGION": region,
                "NOAA_REGION_NORM": normalize_region_for_flare_catalog(region),
                "HARPNUM": region,
                "T_REC_UTC": issue - dt.timedelta(hours=3),
                "LON_FWT": rng.uniform(-55, 55),
                "LAT_FWT": rng.uniform(-30, 30),
                "QUALITY": 0,
                "OBS_VR": rng.normal(0, 1000),
            }
            latent = 0.0
            for parameter in SHARP_PARAMETERS:
                base = float(np.exp(rng.normal(4.0, 1.1)))
                if parameter in {"MEANALP", "MEANJZH", "MEANJZD"}:
                    base *= float(rng.choice([-1, 1]))
                record[parameter] = base
                record[f"PREV_{parameter}"] = previous.get(region, {}).get(parameter, base * rng.uniform(0.7, 1.3))
                if parameter in {"TOTUSJH", "TOTUSJZ", "R_VALUE", "USFLUX", "TOTPOT"}:
                    latent += math.log1p(abs(base)) * 0.075
            latent += rng.normal(-4.6, 0.9)
            p_m = 1 / (1 + math.exp(-latent))
            p_x = max(0.002, p_m * 0.12)
            m1_event = int(rng.random() < p_m)
            record["LABEL_M1"] = m1_event
            # X1+ is a strict subset of M1+ by definition.
            conditional_x_given_m = min(0.35, max(0.02, p_x / max(p_m, 1e-6)))
            record["LABEL_X1"] = int(
                bool(m1_event) and rng.random() < conditional_x_given_m
            )
            previous[region] = {parameter: float(record[parameter]) for parameter in SHARP_PARAMETERS}
            rows.append(record)
    frame = pd.DataFrame(rows)
    engineered = engineer_features(frame)
    final = pd.concat([frame.reset_index(drop=True), engineered.reset_index(drop=True)], axis=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(path, index=False, compression="gzip")
    return final


def self_test(args: argparse.Namespace) -> None:
    root = args.output_dir.expanduser().resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    dataset = root / "synthetic_training.csv.gz"
    frame = synthetic_training_table(dataset)
    train_args = argparse.Namespace(
        dataset=dataset,
        model_dir=root / "models",
        model_version="sharp-mag-self-test",
        c_value=1.0,
        min_m1_positives=10,
        min_x1_positives=5,
        allow_small_sample=True,
        historical_series=DEFAULT_HISTORICAL_SERIES,
        live_series=DEFAULT_LIVE_SERIES,
        issue_hour=DEFAULT_ISSUE_HOUR,
        input_lag_hours=DEFAULT_INPUT_LAG_HOURS,
        max_longitude=DEFAULT_MAX_LONGITUDE,
        max_obs_vr=DEFAULT_MAX_OBS_VR,
        max_quality=DEFAULT_MAX_QUALITY,
        max_input_age_hours=DEFAULT_MAX_INPUT_AGE_HOURS,
    )
    paths = train_models(train_args)
    m1, x1, manifest, _ = load_models(paths.directory)
    current = frame.sort_values("ISSUE_TIME").groupby("NOAA_REGION", as_index=False).tail(1).head(4).copy()
    current["DATA_AGE_HOURS"] = 3.0
    payload = create_forecast_payload(
        live_rows=current,
        m1_bundle=m1,
        x1_bundle=x1,
        manifest=manifest,
        issue_time=dt.datetime(2026, 8, 22, 21, tzinfo=UTC),
        input_stats={"self_test": True, "retained_regions": len(current)},
        operational=False,
        region_metadata={},
    )
    payload_path = root / "flare_guidance.self-test.json"
    js_payload_path = root / "flare_guidance.self-test.js"
    atomic_write_json(payload_path, payload)
    atomic_write_text(js_payload_path, flare_guidance_javascript(payload))
    checks = {
        "dataset_rows": len(frame),
        "m1_model_exists": paths.m1.exists(),
        "x1_model_exists": paths.x1.exists(),
        "manifest_exists": paths.manifest.exists(),
        "payload_exists": payload_path.exists(),
        "javascript_payload_exists": js_payload_path.exists(),
        "payload_regions": len(payload["regions"]),
        "x_not_greater_than_m": all(
            region.get("members", {}).get("sharpmag", {}).get("x1", 0)
            <= region.get("members", {}).get("sharpmag", {}).get("m1", 100)
            for region in payload["regions"]
            if region.get("members", {}).get("sharpmag")
        ),
    }
    atomic_write_json(root / "self_test_report.json", checks)
    if not all(value for key, value in checks.items() if key not in {"dataset_rows", "payload_regions"}):
        raise PipelineError(f"Self-test failed: {checks}")
    LOGGER.info("Self-test passed: %s", root)


def add_common_quality_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-longitude", type=float, default=DEFAULT_MAX_LONGITUDE, help="Maximum |LON_FWT| in degrees (default: 50)")
    parser.add_argument("--max-obs-vr", type=float, default=DEFAULT_MAX_OBS_VR, help="Maximum |OBS_VR| in m/s (default: 3500)")
    parser.add_argument("--max-quality", type=int, default=DEFAULT_MAX_QUALITY, help="Optional numeric QUALITY ceiling for sensitivity tests; default 0xFFFFFFFF means diagnostic-only")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train and run a daily SDO/HMI SHARP flare-probability model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Typical workflow:
              1. python sharp_mag_pipeline.py build-dataset --work-dir ./sharp-mag-work --end 2026-08-22
              2. python sharp_mag_pipeline.py train --dataset ./sharp-mag-work/sharp_mag_training_table.csv.gz --model-dir ./sharp-mag-work/models
              3. At about 21Z daily:
                 python sharp_mag_pipeline.py forecast --model-dir ./sharp-mag-work/models --output ./flare_guidance.json --history ./sharp_mag_forecast_history.jsonl
                 (This also writes flare_guidance.js for the shared-folder HTML.)
              4. Copy flare_guidance.js beside the HTML, or run forecast directly in that folder when Python is available at work.
            """
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-dataset", help="Download scalar SHARP keywords and build a labeled compact training table")
    build.add_argument("--work-dir", type=Path, default=Path("sharp-mag-work"))
    build.add_argument("--cache-dir", type=Path)
    build.add_argument("--output", type=Path)
    build.add_argument("--start", type=parse_date, default=DEFAULT_START_DATE)
    build.add_argument("--end", type=parse_date, help="Exclusive end date; default is today UTC")
    build.add_argument("--series", default=DEFAULT_HISTORICAL_SERIES)
    build.add_argument("--issue-hour", type=int, choices=range(24), default=DEFAULT_ISSUE_HOUR)
    build.add_argument("--input-lag-hours", type=int, default=DEFAULT_INPUT_LAG_HOURS)
    build.add_argument("--chunk-days", type=int, default=DEFAULT_CHUNK_DAYS)
    build.add_argument("--flare-csv", type=Path)
    build.add_argument("--flare-csv-url")
    build.add_argument("--refresh-cache", action="store_true")
    build.add_argument("--refresh-flare-catalog", action="store_true")
    build.add_argument("--event-workers", type=int, default=6, help="Parallel NOAA/NCEI daily-report downloads (default: 6)")
    build.add_argument("--include-multi-region-harps", action="store_true", help="Not recommended; duplicates one HARP across NOAA regions")
    build.add_argument("--keep-ambiguous-days", action="store_true", help="Keep days with an unattributed major flare as regional negatives")
    add_common_quality_arguments(build)

    train = subparsers.add_parser("train", help="Train independently calibrated M1+ and direct magnetic X1+ models")
    train.add_argument("--dataset", type=Path, required=True)
    train.add_argument("--model-dir", type=Path, required=True)
    train.add_argument("--model-version")
    train.add_argument("--c-value", type=float, default=1.0)
    train.add_argument("--min-m1-positives", type=int, default=50)
    train.add_argument("--min-x1-positives", type=int, default=15, help="Minimum X1+ region-days for the direct magnetic model (default: 15)")
    train.add_argument("--allow-small-sample", action="store_true")
    train.add_argument("--historical-series", default=DEFAULT_HISTORICAL_SERIES)
    train.add_argument("--live-series", default=DEFAULT_LIVE_SERIES)
    train.add_argument("--issue-hour", type=int, choices=range(24), default=DEFAULT_ISSUE_HOUR)
    train.add_argument("--input-lag-hours", type=int, default=DEFAULT_INPUT_LAG_HOURS)
    train.add_argument("--max-input-age-hours", type=float, default=DEFAULT_MAX_INPUT_AGE_HOURS)
    add_common_quality_arguments(train)

    forecast_parser = subparsers.add_parser("forecast", help="Run lightweight daily inference and write flare_guidance.json")
    forecast_parser.add_argument("--model-dir", type=Path, required=True)
    forecast_parser.add_argument("--output", type=Path, required=True)
    forecast_parser.add_argument("--js-output", type=Path, help="Same-folder JS payload; defaults to flare_guidance.js beside --output")
    forecast_parser.add_argument("--history", type=Path, help="Optional append-only compact JSONL forecast archive")
    forecast_parser.add_argument("--issue-time", default="cycle", help="'cycle' (latest scheduled hour), 'now', or ISO UTC time")
    forecast_parser.add_argument("--issue-hour", type=int, choices=range(24), default=DEFAULT_ISSUE_HOUR)
    forecast_parser.add_argument("--input-lag-hours", type=int, default=DEFAULT_INPUT_LAG_HOURS)
    forecast_parser.add_argument("--live-series")
    forecast_parser.add_argument("--query-hours", type=int, default=40)
    forecast_parser.add_argument("--max-input-age-hours", type=float, default=DEFAULT_MAX_INPUT_AGE_HOURS)
    forecast_parser.add_argument("--operational", action="store_true", help="Mark output operational only after local validation/approval")
    forecast_parser.add_argument("--allow-empty", action="store_true")
    add_common_quality_arguments(forecast_parser)

    doctor_parser = subparsers.add_parser("doctor", help="Report dependency versions and optionally test SWPC/JSOC access")
    doctor_parser.add_argument("--network", action="store_true")

    self_test_parser = subparsers.add_parser("self-test", help="Run an offline synthetic end-to-end validation")
    self_test_parser.add_argument("--output-dir", type=Path, default=Path("sharp-mag-self-test"))

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    try:
        if args.command == "build-dataset":
            build_dataset(args)
        elif args.command == "train":
            train_models(args)
        elif args.command == "forecast":
            forecast(args)
        elif args.command == "doctor":
            doctor(args)
        elif args.command == "self-test":
            self_test(args)
        else:  # pragma: no cover
            parser.error(f"Unknown command: {args.command}")
    except PipelineError as exc:
        LOGGER.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        LOGGER.error("Interrupted")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
