#!/usr/bin/env python3
"""Build one compact, region-attributed GOES flare catalog from NCEI CSVs.

The training pipeline accepts a single label file. NCEI publishes one composite
GOES XRS flare report per year, so this helper concatenates those files, removes
duplicate events, retains the source event identifiers, and writes an auditable
manifest beside the compressed catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_region(value: object, year: int) -> int | None:
    try:
        region = int(float(value))
    except (TypeError, ValueError):
        return None
    if region <= 0:
        return None
    if year >= 2002 and region < 5000:
        region += 10000
    return region


def build(source_dir: Path, output: Path) -> dict[str, object]:
    files = sorted(source_dir.glob("*.csv"))
    if not files:
        raise SystemExit(f"No CSV files found in {source_dir}")

    frames: list[pd.DataFrame] = []
    sources: list[dict[str, object]] = []
    for path in files:
        frame = pd.read_csv(path, low_memory=False)
        required = {"time", "flare_class", "active_region"}
        missing = required - set(frame.columns)
        if missing:
            raise SystemExit(f"{path.name} is missing {sorted(missing)}")
        selected = pd.DataFrame()
        selected["start_time"] = pd.to_datetime(
            frame.get("start_time", frame["time"]), errors="coerce", utc=True
        )
        selected["peak_time"] = pd.to_datetime(frame["time"], errors="coerce", utc=True)
        selected["flare_class"] = frame["flare_class"].astype("string").str.strip().str.upper()
        years = selected["peak_time"].dt.year.fillna(0).astype(int)
        selected["active_region"] = [
            normalize_region(value, int(year))
            for value, year in zip(frame["active_region"], years)
        ]
        selected["event_id_swpc"] = frame.get("event_id_swpc", "")
        selected["flare_id"] = frame.get("flare_id", "")
        selected["source_file"] = path.name
        frames.append(selected)
        sources.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "rows": int(len(frame)),
            }
        )

    catalog = pd.concat(frames, ignore_index=True)
    parsed = catalog["flare_class"].str.extract(r"^([ABCMX])(\d+(?:\.\d+)?)$")
    catalog["class_letter"] = parsed[0]
    catalog["class_magnitude"] = pd.to_numeric(parsed[1], errors="coerce")
    catalog = catalog[
        catalog["peak_time"].notna()
        & catalog["class_letter"].isin(["M", "X"])
        & catalog["class_magnitude"].notna()
    ].copy()
    catalog.sort_values(["peak_time", "active_region", "flare_class"], inplace=True)
    before_deduplication = len(catalog)
    catalog.drop_duplicates(
        ["peak_time", "flare_class", "active_region", "event_id_swpc"], inplace=True
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(output, index=False, compression="gzip")
    manifest = {
        "schema_version": "1.0",
        "source": "NOAA/NCEI composite GOES XRS flare reports",
        "source_url": (
            "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/"
            "goes/multi/l2/data/xrsf-l2-flrpt_science/csv/"
        ),
        "source_files": sources,
        "source_file_count": len(sources),
        "rows_before_deduplication": int(before_deduplication),
        "rows": int(len(catalog)),
        "region_attributed_rows": int(catalog["active_region"].notna().sum()),
        "x1_rows": int(
            ((catalog["class_letter"] == "X") & (catalog["class_magnitude"] >= 1)).sum()
        ),
        "date_start": str(catalog["peak_time"].min()),
        "date_end": str(catalog["peak_time"].max()),
        "output": output.name,
        "output_bytes": output.stat().st_size,
        "output_sha256": sha256(output),
    }
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source_dir, args.output), indent=2))


if __name__ == "__main__":
    main()
