#!/usr/bin/env python3
"""Build an auditable, active-region-safe manifest for SDOBenchmark.

The downloaded archive is read in place; images are not extracted.  The output
manifest makes the forecast window, NOAA active-region identity, target labels,
image availability, and positive-episode proxy explicit so downstream training
cannot silently random-split repeated observations of the same region.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


CHANNELS = ("131", "1700", "171", "193", "211", "304", "335", "94", "continuum", "magnetogram")
M1_FLUX = 1.0e-5
X1_FLUX = 1.0e-4
TIME_OFFSETS_HOURS = (0.0, 7.0, 10.5, 11.0 + 50.0 / 60.0)
IMAGE_RE = re.compile(r"(?P<time>\d{4}-\d{2}-\d{2}T\d{6})__(?P<channel>[^./]+)\.jpg$")


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value[:19])


def iso(value: dt.datetime) -> str:
    return value.replace(microsecond=0).isoformat() + "Z"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_metadata(archive: zipfile.ZipFile, split: str) -> list[dict[str, object]]:
    member = f"SDOBenchmark-data-full/{split}/meta_data.csv"
    with archive.open(member) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"))
        rows: list[dict[str, object]] = []
        for source in reader:
            region, sample_name = source["id"].split("_", 1)
            input_start = parse_time(source["start"])
            input_end = parse_time(source["end"])
            peak_flux = float(source["peak_flux"])
            rows.append(
                {
                    "case_id": source["id"],
                    "sample_name": sample_name,
                    "source_split": split,
                    "noaa_region": int(region),
                    "input_start": input_start,
                    "input_end": input_end,
                    "target_start": input_end,
                    "target_end": input_end + dt.timedelta(hours=24),
                    "peak_flux": peak_flux,
                    "label_c1_plus": int(peak_flux >= 1.0e-6),
                    "label_m1_plus": int(peak_flux >= M1_FLUX),
                    "label_x1_plus": int(peak_flux >= X1_FLUX),
                }
            )
    return rows


def image_inventory(archive: zipfile.ZipFile) -> tuple[dict[str, Counter[str]], int]:
    by_case: dict[str, Counter[str]] = defaultdict(Counter)
    image_count = 0
    for info in archive.infolist():
        if info.is_dir() or not info.filename.endswith(".jpg"):
            continue
        parts = info.filename.split("/")
        if len(parts) != 5 or parts[0] != "SDOBenchmark-data-full":
            continue
        split, region, sample_name, filename = parts[1:]
        match = IMAGE_RE.match(filename)
        if not match:
            continue
        channel = match.group("channel")
        case_id = f"{region}_{sample_name}"
        by_case[case_id][channel] += 1
        image_count += 1
    return by_case, image_count


def attach_episode_proxies(rows: list[dict[str, object]], label: str, max_gap_hours: float = 48.0) -> int:
    by_region: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if int(row[label]):
            by_region[int(row["noaa_region"])].append(row)
    episode_count = 0
    for region, region_rows in by_region.items():
        previous_end: dt.datetime | None = None
        episode_index = 0
        for row in sorted(region_rows, key=lambda item: item["target_start"]):
            start = row["target_start"]
            if previous_end is None or (start - previous_end).total_seconds() > max_gap_hours * 3600:
                episode_count += 1
                episode_index += 1
            row[f"{label}_episode_proxy"] = f"AR{region}-{label.upper()}-{episode_index:03d}"
            previous_end = max(previous_end or row["target_end"], row["target_end"])
    for row in rows:
        row.setdefault(f"{label}_episode_proxy", "")
    return episode_count


def summarize_split(rows: list[dict[str, object]]) -> dict[str, object]:
    regions = {int(row["noaa_region"]) for row in rows}
    years = Counter(row["target_start"].year for row in rows)
    return {
        "cases": len(rows),
        "unique_active_regions": len(regions),
        "date_start": iso(min(row["input_start"] for row in rows)),
        "date_end": iso(max(row["target_end"] for row in rows)),
        "c1_plus_cases": sum(int(row["label_c1_plus"]) for row in rows),
        "m1_plus_cases": sum(int(row["label_m1_plus"]) for row in rows),
        "x1_plus_cases": sum(int(row["label_x1_plus"]) for row in rows),
        "m1_plus_prevalence": sum(int(row["label_m1_plus"]) for row in rows) / len(rows),
        "x1_plus_prevalence": sum(int(row["label_x1_plus"]) for row in rows) / len(rows),
        "cases_by_target_year": dict(sorted(years.items())),
    }


def write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "case_id", "source_split", "noaa_region", "input_start", "input_end",
        "target_start", "target_end", "peak_flux", "label_c1_plus",
        "label_m1_plus", "label_x1_plus", "label_m1_plus_episode_proxy",
        "label_x1_plus_episode_proxy", "image_count", "complete_40_images",
    ] + [f"images_{channel}" for channel in CHANNELS]
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{key: row.get(key, "") for key in columns},
                    "input_start": iso(row["input_start"]),
                    "input_end": iso(row["input_end"]),
                    "target_start": iso(row["target_start"]),
                    "target_end": iso(row["target_end"]),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    archive_path = args.archive.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path) as archive:
        training = read_metadata(archive, "training")
        test = read_metadata(archive, "test")
        inventory, archive_images = image_inventory(archive)

    rows = training + test
    unknown_cases = sorted(set(inventory) - {str(row["case_id"]) for row in rows})
    missing_case_directories = 0
    channel_totals: Counter[str] = Counter()
    complete_cases = 0
    for row in rows:
        counts = inventory.get(str(row["case_id"]), Counter())
        row["image_count"] = sum(counts.values())
        row["complete_40_images"] = int(all(counts[channel] >= 4 for channel in CHANNELS))
        complete_cases += int(row["complete_40_images"])
        missing_case_directories += int(not counts)
        for channel in CHANNELS:
            row[f"images_{channel}"] = counts[channel]
            channel_totals[channel] += counts[channel]

    m_episodes = attach_episode_proxies(rows, "label_m1_plus")
    x_episodes = attach_episode_proxies(rows, "label_x1_plus")
    train_regions = {int(row["noaa_region"]) for row in training}
    test_regions = {int(row["noaa_region"]) for row in test}
    overlap = sorted(train_regions & test_regions)

    manifest_path = output_dir / "sdobenchmark_case_manifest.csv.gz"
    write_manifest(manifest_path, rows)
    report = {
        "schema_version": "1.0",
        "dataset": "FHNW-i4DS SDOBenchmark full image archive",
        "research_only": True,
        "source_archive": str(archive_path),
        "source_archive_bytes": archive_path.stat().st_size,
        "source_archive_sha256": sha256(archive_path),
        "forecast_definition": {
            "input_window_hours": 12,
            "image_time_offsets_hours": TIME_OFFSETS_HOURS,
            "verification_window_hours": 24,
            "continuous_target": "maximum GOES X-ray peak flux in the verification window",
            "m1_plus_threshold_w_m2": M1_FLUX,
            "x1_plus_threshold_w_m2": X1_FLUX,
        },
        "training": summarize_split(training),
        "test": summarize_split(test),
        "combined": summarize_split(rows),
        "independence_audit": {
            "active_region_split": True,
            "train_test_region_overlap_count": len(overlap),
            "train_test_region_overlap": overlap,
            "m1_positive_episode_proxies_48h": m_episodes,
            "x1_positive_episode_proxies_48h": x_episodes,
            "episode_proxy_warning": "A 48-hour within-region cluster is not a catalog event ID and must not be reported as an independent flare count.",
        },
        "image_inventory": {
            "archive_jpeg_images": archive_images,
            "cases_with_all_40_expected_images": complete_cases,
            "cases_with_missing_images": len(rows) - complete_cases,
            "cases_without_image_directory": missing_case_directories,
            "unknown_image_directories": len(unknown_cases),
            "images_by_channel": dict(channel_totals),
        },
        "artifacts": {
            "case_manifest": str(manifest_path),
            "case_manifest_sha256": sha256(manifest_path),
        },
        "guardrails": [
            "Never random-split rows; group by NOAA active region and flare episode.",
            "Do not treat repeated forecast windows around one flare as independent positive events.",
            "Do not use the supplied test set for architecture, feature, threshold, or calibration selection.",
            "Keep natural event prevalence in calibration and test data.",
            "Do not merge SDOBenchmark probabilities with live WXF until forecast-window and source-domain alignment are validated.",
        ],
    }
    report_path = output_dir / "sdobenchmark_audit.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), "manifest": str(manifest_path), "summary": report["combined"], "overlap": len(overlap)}, indent=2))


if __name__ == "__main__":
    main()
