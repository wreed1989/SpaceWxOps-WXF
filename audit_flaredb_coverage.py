#!/usr/bin/env python3
"""Audit NJIT FlareDB against WXF labels and region-day forecast cases.

FlareDB is event-selected and contains no quiet controls, so this script never
appends its rows as negative-free training examples. It measures label coverage
and collapses repeated events from one region/valid day to the single forecast
case they represent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


COLUMNS = ["flare_class", "noaa_region", "start_time", "peak_time", "end_time", "harp", "longitude", "latitude"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_region(value: object) -> int | None:
    try:
        region = int(float(value))
    except (TypeError, ValueError):
        return None
    if region <= 0:
        return None
    return region % 10000 or region


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--goes-catalog", type=Path, required=True)
    parser.add_argument("--training-table", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    events = pd.read_csv(args.events, header=None, names=COLUMNS)
    events["start_time"] = pd.to_datetime(events["start_time"], format="mixed", errors="coerce", utc=True)
    events["region_norm"] = events["noaa_region"].map(normalized_region)
    events["is_x1"] = events["flare_class"].astype(str).str.upper().str.match(r"^X(?:[1-9]|\d{2,})(?:\.\d+)?$")
    events["valid_date"] = events["start_time"].dt.date
    events["issue_date"] = events["valid_date"].map(lambda value: value - pd.Timedelta(days=1) if pd.notna(value) else value)

    goes = pd.read_csv(args.goes_catalog, low_memory=False)
    goes["peak_time"] = pd.to_datetime(goes["peak_time"], errors="coerce", utc=True)
    goes["valid_date"] = goes["peak_time"].dt.date
    goes["region_norm"] = goes["active_region"].map(normalized_region)
    goes["is_x1"] = (
        goes["flare_class"].astype(str).str.upper().str.startswith("X")
        & (pd.to_numeric(goes["class_magnitude"], errors="coerce") >= 1)
    )
    goes_cases = set(zip(goes["valid_date"], goes["region_norm"], goes["is_x1"]))

    training = pd.read_csv(
        args.training_table,
        usecols=["ISSUE_DATE", "NOAA_REGION_NORM", "LABEL_M1", "LABEL_X1"],
        low_memory=False,
    )
    training["ISSUE_DATE"] = pd.to_datetime(training["ISSUE_DATE"], errors="coerce").dt.date
    training["NOAA_REGION_NORM"] = training["NOAA_REGION_NORM"].map(normalized_region)
    training_cases = set(zip(training["ISSUE_DATE"], training["NOAA_REGION_NORM"]))

    events["goes_label_found"] = [
        (day, region, bool(is_x)) in goes_cases
        for day, region, is_x in zip(events["valid_date"], events["region_norm"], events["is_x1"])
    ]
    events["wxf_precursor_case_found"] = [
        (day, region) in training_cases
        for day, region in zip(events["issue_date"], events["region_norm"])
    ]
    x_2024 = events[events["is_x1"] & (events["start_time"].dt.year == 2024)]
    unique_forecast_cases = events[["valid_date", "region_norm"]].dropna().drop_duplicates()

    report = {
        "schema_version": "1.0",
        "purpose": "positive-event label and precursor coverage audit; not direct training ingestion",
        "flaredb_repository": "https://github.com/Reasopprime/njit-flaredb/",
        "flaredb_article": "https://www.nature.com/articles/s41597-026-06607-7",
        "events_file": f"{args.events.name} (local audit input; not redistributed)",
        "events_source_url": "https://raw.githubusercontent.com/Reasopprime/njit-flaredb/main/Flare_event_list.csv",
        "events_file_sha256": sha256(args.events),
        "repository_event_rows": int(len(events)),
        "repository_x1_events": int(events["is_x1"].sum()),
        "repository_unique_regions": int(events["region_norm"].nunique()),
        "repository_unique_region_days": int(len(unique_forecast_cases)),
        "paper_reported_events": 151,
        "paper_reported_regions": 82,
        "paper_statement_2024_x_events": "more than 30",
        "repository_2024_x_events": int(len(x_2024)),
        "repository_2024_x_unique_regions": int(x_2024["region_norm"].nunique()),
        "repository_2024_x_unique_region_days": int(
            len(x_2024[["valid_date", "region_norm"]].drop_duplicates())
        ),
        "repository_2024_x_by_region": {
            str(int(region)): int(count)
            for region, count in x_2024.groupby("region_norm").size().sort_values(ascending=False).items()
        },
        "goes_exact_day_region_class_matches": int(events["goes_label_found"].sum()),
        "wxf_prior_day_precursor_cases": int(events["wxf_precursor_case_found"].sum()),
        "limitations": [
            "FlareDB selects M5+ and X events and supplies no quiet/control cases.",
            "Multiple flares from one active region on one valid day are one 24-hour forecast case.",
            "The repository event list is smaller than the version described by the 2026 paper.",
            "Event-centered sequences can overlap and must be grouped by active region during evaluation.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
