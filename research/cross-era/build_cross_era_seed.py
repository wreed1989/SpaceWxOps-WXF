#!/usr/bin/env python3
"""Build the auditable seed package for the WXF cross-era flare model.

The script intentionally stops before model fitting.  It materializes public
metadata/labels, normalizes region identifiers, records source provenance, and
publishes the feature/validation contracts that a later MDI/GONG/KPVT image
ingest must satisfy.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import openpyxl


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "wxf_cross_era"
NADC_XLSX = OUT / "nadc_allAR_v1.xlsx"
GOES_DIR = OUT / "goes_xrs_cycle23"
SRS_DIR = OUT / "noaa_srs_cycle23"

SRS_BASE = (
    "https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/"
    "daily_reports/solar_region_summaries"
)

SOURCES = [
    {
        "id": "nadc-mdi-hmi-ar",
        "name": "NADC homogeneous MDI/HMI active-region database",
        "coverage": "1996-05-05 to 2023-06-14",
        "cycles": "23, 24, part of 25",
        "branch": "Cross-era metadata/QC",
        "status": "materialized_audited",
        "role": "Polarity centroids, areas and signed flux; cross-instrument lineage check",
        "url": "https://nadc.china-vo.org/res/r101300/?lang=en",
        "local": "nadc_allAR_v1.xlsx",
    },
    {
        "id": "noaa-srs",
        "name": "NOAA/SWPC Solar Region Summary",
        "coverage": "1996-present",
        "cycles": "23, 24, 25",
        "branch": "All branches",
        "status": "cycle23_materialized_audited",
        "role": "NOAA region identity, location, area, McIntosh class, spot count and magnetic class",
        "url": "https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/solar_region_summaries/",
        "local": "noaa_cycle23_region_days.csv.gz",
    },
    {
        "id": "goes-xrs-cycle23",
        "name": "NOAA/NCEI GOES XRS flare reports",
        "coverage": "1996-01-01 to 2008-12-31 in local seed",
        "cycles": "23",
        "branch": "Label authority",
        "status": "cycle23_materialized_audited",
        "role": "M1+/X1+ event time, class, location and reported NOAA region",
        "url": "https://www.ngdc.noaa.gov/stp/space-weather/solar-data/solar-features/solar-flares/x-rays/goes/xrs/",
        "local": "goes_cycle23_events.csv.gz",
    },
    {
        "id": "mdi-mtarp",
        "name": "SOHO/MDI tracked active-region patches (M-TARP)",
        "coverage": "1996-2011",
        "cycles": "23, early 24",
        "branch": "WXF Cross-Era",
        "status": "adapter_registered_not_materialized",
        "role": "96-minute LOS magnetograms, intensitygrams, magnetic and sunspot masks",
        "url": "https://jsoc1.stanford.edu/data/mdi/mdi-tarp/",
        "series": ["mdi.Mtarp", "mdi.fd_M_96m_lev182", "mdi.fd_Ic_flat", "mdi.fd_spotmask"],
    },
    {
        "id": "smarp-sharp",
        "name": "Merged SMARP-SHARP parameters",
        "coverage": "1996-04-23 to 2026-01-06",
        "cycles": "23, 24, part of 25",
        "branch": "WXF Cross-Era",
        "status": "materialized_audited_trained_retrospective",
        "role": "4,653,499-row harmonized MDI/HMI magnetic-parameter expansion and cross-era baseline",
        "url": "https://sun.njit.edu/sharp-smarp.html",
        "local": "merged_smarp_sharp_v3c_19960423_20260106.csv",
    },
    {
        "id": "gong",
        "name": "NSO GONG full-disk magnetic and intensity archive",
        "coverage": "1995-present",
        "cycles": "23, 24, 25",
        "branch": "WXF Cross-Era",
        "status": "adapter_registered_not_materialized",
        "role": "Temporal gap filling and MDI/HMI overlap-transfer calibration",
        "url": "https://nso.edu/telescopes/nisp/gong/",
    },
    {
        "id": "kpvt",
        "name": "NSO Kitt Peak Vacuum Telescope archive",
        "coverage": "1974-02-01 to 2003",
        "cycles": "21, 22, part of 23",
        "branch": "WXF Historical LOS",
        "status": "registered_phase2",
        "role": "Second-cycle extension with longitudinal field and pseudo-continuum images",
        "url": "https://nso.edu/data/historical-archive/",
    },
    {
        "id": "solis-vsm",
        "name": "NSO SOLIS/VSM",
        "coverage": "2003 onward with product/version breaks",
        "cycles": "23, 24, 25",
        "branch": "Transfer calibration",
        "status": "registered_overlap_control",
        "role": "Independent bridge between MDI, GONG and HMI eras",
        "url": "https://nso.edu/data/historical-archive/",
    },
    {
        "id": "debrecen-dpd",
        "name": "Debrecen Photoheliographic Data",
        "coverage": "1974 onward",
        "cycles": "21 onward",
        "branch": "WXF Historical Prior",
        "status": "registered_phase2",
        "role": "Sunspot-group and individual-spot position, area and evolution",
        "url": "https://fenyi.solarobs.epss.hun-ren.hu/en/databases/DPD/",
    },
    {
        "id": "mcintosh-archive",
        "name": "NOAA/NCEI McIntosh Archive",
        "coverage": "1954-12 to 2025-01",
        "cycles": "19-24 complete; selected 25",
        "branch": "WXF Historical Prior",
        "status": "registered_phase2",
        "role": "PIL, filament, plage, sunspot and coronal-hole morphology context",
        "url": "https://www.ncei.noaa.gov/products/space-weather/legacy-data/solar-chromosphere",
    },
    {
        "id": "suryabench",
        "name": "NASA IMPACT SuryaBench",
        "coverage": "2010-05 to 2024-12",
        "cycles": "24, most of 25",
        "branch": "WXF-HMI",
        "status": "registered_modern_enrichment",
        "role": "Consistently processed AIA/HMI imagery for current-cycle validation",
        "url": "https://github.com/NASA-IMPACT/SuryaBench",
    },
    {
        "id": "flaredb",
        "name": "FlareDB",
        "coverage": "cycles 24-25",
        "cycles": "24, 25",
        "branch": "Event reconciliation",
        "status": "registered_modern_enrichment",
        "role": "Exact significant-flare mapping to NOAA region and HARP identifiers",
        "url": "https://www.nature.com/articles/s41597-026-06607-7",
    },
    {
        "id": "flarecast-archive",
        "name": "FLARECAST forecast archive",
        "coverage": "archive-dependent",
        "cycles": "primarily 24",
        "branch": "Benchmark only",
        "status": "registered_benchmark_only",
        "role": "Historical forecast comparison; never used as truth labels",
        "url": "https://api.flarecast.eu/archive.html",
    },
]

FEATURE_CONTRACT = {
    "schema_version": "1.0",
    "target_window_hours": 24,
    "targets": ["M1+", "X1+"],
    "identity_unit": "canonical NOAA active-region passage",
    "branches": {
        "wxf_hmi": {
            "coverage": "2010-present",
            "allowed": ["HMI vector SHARP", "HMI/AIA tracked imagery", "common LOS features", "morphology/history"],
            "forbidden": [],
        },
        "wxf_cross_era": {
            "coverage": "1974-present",
            "allowed": [
                "normalized unsigned LOS flux", "flux imbalance", "polarity separation",
                "polarity-centroid motion", "normalized PIL length", "normalized PIL gradient",
                "common-resolution Zernike moments", "sunspot area/count", "McIntosh/Hale class",
                "central-meridian distance", "6/12/24/48 h deltas", "prior flare counts/waiting time",
            ],
            "forbidden": ["HMI-only vector SHARP quantities", "unharmonized raw-pixel pooling"],
        },
        "wxf_historical_prior": {
            "coverage": "1954-present",
            "allowed": ["sunspot morphology", "area/count", "location", "evolution", "PIL context", "flare history"],
            "forbidden": ["claims of vector-field equivalence"],
        },
    },
    "harmonization": [
        "Reproject to a common heliographic grid and common physical pixel scale.",
        "Apply limb/foreshortening masks before feature extraction.",
        "Normalize flux and gradient features within instrument, then learn overlap mappings.",
        "Retain instrument and processing-version indicators in every case.",
        "Publish overlap residuals and per-instrument missingness; never mean-impute silently.",
    ],
}

VALIDATION_CONTRACT = {
    "schema_version": "1.0",
    "primary_split": {
        "development": "cycles 21-23",
        "calibration_threshold_selection": "cycle 24",
        "untouched_final_test": "cycle 25-to-date",
    },
    "required_secondary_tests": [
        "leave-one-instrument-out transfer test",
        "overlap-era paired-instrument residual test",
        "active-region-grouped bootstrap confidence intervals",
        "event-episode-grouped bootstrap confidence intervals",
        "disk-center versus limb reliability",
        "solar-maximum versus solar-minimum reliability",
    ],
    "required_metrics": ["Brier score", "Brier skill", "log loss", "reliability/ECE", "PR-AUC", "ROC-AUC", "TSS", "HSS", "POD", "FAR"],
    "comparators": ["climatology", "persistence", "MCSTAT", "MCEVOL", "SWPC", "FLARECAST when matched"],
    "hard_rules": [
        "No row-random split.",
        "All observations from one region passage stay in one fold.",
        "Every feature timestamp must precede issue time.",
        "Thresholds and calibration are selected without using the final cycle-25 test.",
        "Report every score separately by cycle and instrument before any pooled score.",
    ],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_noaa(raw: str, year: int) -> int | None:
    raw = raw.strip()
    if not raw.isdigit():
        return None
    value = int(raw)
    if year >= 2002 and value < 5000:
        return value + 10000
    return value


def audit_nadc() -> dict:
    workbook = openpyxl.load_workbook(NADC_XLSX, read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    header = [str(value) for value in next(sheet.values)]
    rows = [tuple(row) for row in sheet.values if any(value is not None for value in row)]
    # The first tuple above is the header because a fresh iterator is returned.
    rows = rows[1:]
    unique_keys = {(row[0], row[1]) for row in rows}
    missing = {header[index]: sum(row[index] is None for row in rows) for index in range(len(header))}
    csv_path = OUT / "nadc_allAR_v1.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
    return {
        "workbook_rows": len(rows),
        "unique_cr_label_records": len(unique_keys),
        "landing_page_advertised_rows": 2849,
        "advertised_vs_workbook_delta": len(rows) - 2849,
        "cr_start": min(int(row[0]) for row in rows),
        "cr_end": max(int(row[0]) for row in rows),
        "missing_by_column": missing,
        "xlsx_sha256": sha256(NADC_XLSX),
        "csv_sha256": sha256(csv_path),
    }


def parse_goes() -> dict:
    output_path = OUT / "goes_cycle23_events.csv.gz"
    class_counts: Counter[str] = Counter()
    region_counts: Counter[str] = Counter()
    rows = []
    for path in sorted(GOES_DIR.glob("goes-xrs-report_*.txt")):
        year = int(path.stem[-4:])
        for line in path.read_text(encoding="ascii", errors="replace").splitlines():
            if len(line) < 63 or line[59:60] not in "ABCMX":
                continue
            cls = line[59]
            magnitude_text = line[61:63].strip()
            try:
                magnitude = float(magnitude_text) / 10.0
            except ValueError:
                magnitude = None
            date_text = line[5:11]
            if not date_text.isdigit():
                continue
            date = f"{year:04d}-{int(date_text[2:4]):02d}-{int(date_text[4:6]):02d}"
            region_raw = line[81:86].strip() if len(line) > 81 else ""
            region = canonical_noaa(region_raw, year)
            class_counts[cls] += 1
            if region is not None:
                region_counts[cls] += 1
            rows.append({
                "date": date,
                "begin_ut": line[13:17].strip(),
                "peak_ut": line[23:27].strip(),
                "end_ut": line[18:22].strip(),
                "class": cls,
                "magnitude": magnitude,
                "goes_class": f"{cls}{magnitude:g}" if magnitude is not None else cls,
                "location_report": line[28:36].strip(),
                "noaa_region_report": region_raw,
                "canonical_noaa_region": region,
                "source_year": year,
            })
    with gzip.open(output_path, "wt", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {
        "events": len(rows),
        "class_counts": dict(sorted(class_counts.items())),
        "region_attributed_class_counts": dict(sorted(region_counts.items())),
        "m1_plus_events": class_counts["M"] + class_counts["X"],
        "x1_plus_events": class_counts["X"],
        "region_attributed_m1_plus_events": region_counts["M"] + region_counts["X"],
        "region_attributed_x1_plus_events": region_counts["X"],
        "year_start": 1996,
        "year_end": 2008,
        "output_sha256": sha256(output_path),
    }


def srs_url(day: dt.date) -> str:
    stamp = day.strftime("%Y%m%d")
    return f"{SRS_BASE}/{day.year:04d}/{day.month:02d}/{stamp}SRS.txt"


def fetch_srs_day(day: dt.date) -> tuple[dt.date, str | None, str | None]:
    path = SRS_DIR / str(day.year) / f"{day:%Y%m%d}SRS.txt"
    if path.exists() and path.stat().st_size > 80:
        return day, str(path), None
    request = urllib.request.Request(srs_url(day), headers={"User-Agent": "SpaceWxOps-WXF/3.8 dataset-audit"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = response.read()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            return day, str(path), None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == 0:
                time.sleep(0.15)
                continue
            return day, None, str(exc)
    return day, None, "unknown fetch error"


def download_srs() -> dict:
    start = dt.date(1996, 1, 1)
    end = dt.date(2008, 12, 31)
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += dt.timedelta(days=1)
    failures = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch_srs_day, day) for day in days]
        for future in as_completed(futures):
            day, _, error = future.result()
            if error:
                failures.append({"date": day.isoformat(), "error": error})
    return {"requested_days": len(days), "failed_days": failures}


SRS_ROW = re.compile(
    r"^\s*(?P<region>\d{4,5})\s+(?P<location>[NS]\d{2}[EW]\d{2})\s+"
    r"(?P<carrington>\d{3})\s+(?P<area>\d{4})\s+(?P<mcintosh>[A-Za-z]{3})\s+"
    r"(?P<extent>\d{2})\s+(?P<spots>\d{2,3})\s+(?P<magnetic>.+?)\s*$"
)


def parse_srs() -> dict:
    rows = []
    files = sorted(SRS_DIR.glob("20??/*.txt")) + sorted(SRS_DIR.glob("19??/*.txt"))
    for path in files:
        stamp = path.stem[:8]
        if not stamp.isdigit():
            continue
        year = int(stamp[:4])
        in_spotted_section = False
        for line in path.read_text(encoding="ascii", errors="replace").splitlines():
            normalized = line.upper()
            if normalized.startswith("I.") and "REGIONS WITH SUNSPOTS" in normalized:
                in_spotted_section = True
                continue
            if normalized.startswith("IA.") or normalized.startswith("II."):
                in_spotted_section = False
            if not in_spotted_section:
                continue
            match = SRS_ROW.match(line)
            if not match:
                continue
            values = match.groupdict()
            rows.append({
                "date": f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}",
                "noaa_region_report": values["region"],
                "canonical_noaa_region": canonical_noaa(values["region"], year),
                "location": values["location"],
                "carrington_longitude": int(values["carrington"]),
                "area_microhem": int(values["area"]),
                "mcintosh": values["mcintosh"],
                "longitudinal_extent_deg": int(values["extent"]),
                "spot_count": int(values["spots"]),
                "magnetic_class": values["magnetic"].strip(),
            })
    output_path = OUT / "noaa_cycle23_region_days.csv.gz"
    if rows:
        with gzip.open(output_path, "wt", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    unique_regions = {row["canonical_noaa_region"] for row in rows}
    days = {row["date"] for row in rows}
    expected_dates = []
    cursor = dt.date(1996, 1, 1)
    end = dt.date(2008, 12, 31)
    while cursor <= end:
        expected_dates.append(cursor)
        cursor += dt.timedelta(days=1)
    present_dates = {path.stem[:8] for path in files}
    missing_source_dates = [day.isoformat() for day in expected_dates if day.strftime("%Y%m%d") not in present_dates]
    return {
        "source_files": len(files),
        "expected_daily_files": len(expected_dates),
        "missing_source_dates": missing_source_dates,
        "source_file_completeness": len(files) / len(expected_dates),
        "region_days": len(rows),
        "unique_noaa_regions": len(unique_regions),
        "days_with_spotted_regions": len(days),
        "date_start": min(days) if days else None,
        "date_end": max(days) if days else None,
        "output_sha256": sha256(output_path) if output_path.exists() else None,
    }


def write_json(name: str, payload: object) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-srs", action="store_true", help="Fetch all daily 1996-2008 NOAA SRS files")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    download_report = download_srs() if args.download_srs else None
    audit = {
        "schema_version": "1.0",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "cross_era_baseline_trained_research_only",
        "nadc": audit_nadc(),
        "goes_cycle23": parse_goes(),
        "noaa_srs_cycle23": parse_srs(),
        "download_report": download_report,
        "model_readiness": {
            "labels_and_region_morphology": "materialized",
            "mdi_smarp_magnetic_features": "materialized_audited_trained_retrospective",
            "gong_transfer_features": "not_materialized",
            "kpvt_historical_features": "not_materialized",
            "forecast_probabilities_changed": False,
        },
    }
    training_report_path = OUT / "cross_era_training_report.json"
    if training_report_path.exists():
        training = json.loads(training_report_path.read_text(encoding="utf-8"))
        audit["cross_era_training"] = {
            "model_version": training.get("model_version"),
            "source_rows": training.get("source_audit", {}).get("rows"),
            "daily_cases": training.get("case_audit", {}).get("cases"),
            "feature_count": training.get("case_audit", {}).get("feature_count"),
            "M1+": training.get("M1+"),
            "X1+": training.get("X1+"),
            "report_sha256": sha256(training_report_path),
        }
    write_json("cross_era_audit.json", audit)
    write_json("source_registry.json", {"schema_version": "1.0", "sources": SOURCES})
    write_json("feature_contract.json", FEATURE_CONTRACT)
    write_json("validation_contract.json", VALIDATION_CONTRACT)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
