#!/usr/bin/env python3
"""Train an auditable SDOBenchmark temporal-image baseline for WXF.

The model intentionally stays compact and reproducible.  It uses four frames
from magnetogram, continuum, AIA 131, and AIA 193 imagery; extracts physical
proxy/statistical features (including polarity-inversion-line and low-order
Zernike descriptors); fits one shared log peak-flux ridge model; and calibrates
M1+ and X1+ probabilities separately.  Model selection and calibration use only
active-region-disjoint subsets of the supplied training split.  The supplied
test split remains untouched until final scoring.
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
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, UnidentifiedImageError


CHANNELS = ("magnetogram", "continuum", "131", "193")
TIME_OFFSETS_MINUTES = (0, 420, 630, 710)
IMAGE_SIZE = 64
M1_FLUX = 1.0e-5
X1_FLUX = 1.0e-4
EPS = 1.0e-12
ZERNIKES = ((2, 0), (2, 2), (4, 0), (4, 2), (4, 4), (6, 0), (6, 2), (6, 4), (6, 6))
GENERAL_STATS = ("mean", "std", "q10", "median", "q90", "gradient", "entropy", "dark_fraction", "bright_fraction")


def stable_hash(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.rstrip("Z"))


def sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-values))


def zernike_radial(n: int, m: int, radius: np.ndarray) -> np.ndarray:
    output = np.zeros_like(radius, dtype=np.float64)
    for k in range((n - m) // 2 + 1):
        coefficient = ((-1) ** k * math.factorial(n - k)) / (
            math.factorial(k)
            * math.factorial((n + m) // 2 - k)
            * math.factorial((n - m) // 2 - k)
        )
        output += coefficient * radius ** (n - 2 * k)
    return output


def zernike_bases(size: int) -> list[np.ndarray]:
    coordinate = np.linspace(-1.0, 1.0, size, dtype=np.float64)
    xx, yy = np.meshgrid(coordinate, coordinate)
    radius = np.sqrt(xx * xx + yy * yy)
    theta = np.arctan2(yy, xx)
    disk = radius <= 1.0
    bases: list[np.ndarray] = []
    for n, m in ZERNIKES:
        radial = zernike_radial(n, m, radius)
        basis = radial * np.exp(-1j * m * theta)
        basis[~disk] = 0.0
        bases.append(basis)
    return bases


ZERNIKES_BASES = zernike_bases(IMAGE_SIZE)


def general_stats(array: np.ndarray) -> list[float]:
    q10, median, q90 = np.quantile(array, (0.1, 0.5, 0.9))
    dx = np.abs(np.diff(array, axis=1)).mean()
    dy = np.abs(np.diff(array, axis=0)).mean()
    histogram = np.histogram(array, bins=16, range=(0.0, 1.0))[0].astype(np.float64)
    probabilities = histogram / max(histogram.sum(), 1.0)
    entropy = float(-(probabilities[probabilities > 0] * np.log2(probabilities[probabilities > 0])).sum())
    return [
        float(array.mean()), float(array.std()), float(q10), float(median), float(q90),
        float((dx + dy) / 2.0), entropy, float((array < 0.10).mean()), float((array > 0.90).mean()),
    ]


def magnetogram_stats(array: np.ndarray) -> list[float]:
    polarity = array * 2.0 - 1.0
    absolute = np.abs(polarity)
    positive = float(np.clip(polarity, 0.0, None).sum())
    negative = float(np.clip(-polarity, 0.0, None).sum())
    total = positive + negative
    horizontal = (polarity[:, :-1] * polarity[:, 1:] < 0.0) & (
        np.maximum(absolute[:, :-1], absolute[:, 1:]) > 0.12
    )
    vertical = (polarity[:-1, :] * polarity[1:, :] < 0.0) & (
        np.maximum(absolute[:-1, :], absolute[1:, :]) > 0.12
    )
    pil_count = int(horizontal.sum() + vertical.sum())
    pil_strength_sum = float(np.abs(np.diff(polarity, axis=1))[horizontal].sum())
    pil_strength_sum += float(np.abs(np.diff(polarity, axis=0))[vertical].sum())
    centered = polarity - float(polarity.mean())
    zernike = [float(abs((centered * basis).sum()) / centered.size) for basis in ZERNIKES_BASES]
    return [
        float(absolute.mean()),
        float((absolute > 0.40).mean()),
        (positive - negative) / max(total, EPS),
        pil_count / float(horizontal.size + vertical.size),
        pil_strength_sum / max(pil_count, 1),
        *zernike,
    ]


def continuum_stats(array: np.ndarray) -> list[float]:
    median = float(np.median(array))
    threshold = max(0.0, median - 0.16)
    dark = array[array < threshold]
    return [float((array < threshold).mean()), float(median - dark.mean()) if dark.size else 0.0]


def feature_names() -> tuple[list[str], dict[str, list]]:
    per_channel = {
        "magnetogram": list(GENERAL_STATS) + [
            "unsigned_field", "strong_field_fraction", "flux_imbalance",
            "pil_fraction", "pil_strength",
            *[f"zernike_{n}_{m}" for n, m in ZERNIKES],
        ],
        "continuum": list(GENERAL_STATS) + ["spot_dark_fraction", "spot_contrast"],
        "131": list(GENERAL_STATS),
        "193": list(GENERAL_STATS),
    }
    names: list[str] = []
    for slot in range(4):
        for channel in CHANNELS:
            names.extend(f"t{slot}_{channel}_{name}" for name in per_channel[channel])
            names.append(f"t{slot}_{channel}_missing")
            names.append(f"t{slot}_{channel}_flagged")
    for channel in CHANNELS:
        names.extend(f"delta_{channel}_{name}" for name in per_channel[channel])
    return names, per_channel


FEATURE_NAMES, PER_CHANNEL = feature_names()


def image_features(image: Image.Image, channel: str) -> list[float]:
    grayscale = image.convert("L").resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR)
    array = np.asarray(grayscale, dtype=np.float64) / 255.0
    output = general_stats(array)
    if channel == "magnetogram":
        output.extend(magnetogram_stats(array))
    elif channel == "continuum":
        output.extend(continuum_stats(array))
    return output


def read_manifest(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        rows = []
        for raw in csv.DictReader(handle):
            rows.append(
                {
                    **raw,
                    "noaa_region": int(raw["noaa_region"]),
                    "input_start_dt": parse_iso(raw["input_start"]),
                    "peak_flux_value": float(raw["peak_flux"]),
                    "label_m1": int(raw["label_m1_plus"]),
                    "label_x1": int(raw["label_x1_plus"]),
                }
            )
    return rows


def build_image_index(archive: zipfile.ZipFile) -> dict[str, dict[str, list[tuple[dt.datetime, str]]]]:
    index: dict[str, dict[str, list[tuple[dt.datetime, str]]]] = defaultdict(lambda: defaultdict(list))
    for info in archive.infolist():
        if info.is_dir() or not info.filename.endswith(".jpg"):
            continue
        parts = info.filename.split("/")
        if len(parts) != 5:
            continue
        _, split, region, sample_name, filename = parts
        if "__" not in filename:
            continue
        stem = filename[:-4]
        timestamp_raw, channel = stem.split("__", 1)
        if channel not in CHANNELS:
            continue
        timestamp = dt.datetime.strptime(timestamp_raw, "%Y-%m-%dT%H%M%S")
        index[f"{region}_{sample_name}"][channel].append((timestamp, info.filename))
    return index


def nearest_member(entries: list[tuple[dt.datetime, str]], expected: dt.datetime) -> str | None:
    if not entries:
        return None
    difference, name = min((abs((timestamp - expected).total_seconds()), name) for timestamp, name in entries)
    return name if difference <= 15 * 60 else None


def extract_case_features(
    archive: zipfile.ZipFile,
    members: dict[str, list[tuple[dt.datetime, str]]],
    row: dict[str, object],
) -> tuple[list[float], int, int]:
    start = row["input_start_dt"]
    slots: list[dict[str, list[float]]] = []
    output: list[float] = []
    missing_count = 0
    flagged_count = 0
    for offset in TIME_OFFSETS_MINUTES:
        expected = start + dt.timedelta(minutes=offset)
        slot_features: dict[str, list[float]] = {}
        for channel in CHANNELS:
            member = nearest_member(members.get(channel, []), expected)
            values = [math.nan] * len(PER_CHANNEL[channel])
            missing = 1.0
            flagged = 0.0
            if member is not None:
                try:
                    with archive.open(member) as handle:
                        image = Image.open(handle)
                        description = str(image.getexif().get(270, ""))
                        if "flagged" in description.lower():
                            flagged = 1.0
                            flagged_count += 1
                        else:
                            values = image_features(image, channel)
                            missing = 0.0
                except (OSError, ValueError, UnidentifiedImageError):
                    missing = 1.0
            if missing:
                missing_count += 1
            output.extend(values)
            output.extend((missing, flagged))
            slot_features[channel] = values
        slots.append(slot_features)
    for channel in CHANNELS:
        first = np.asarray(slots[0][channel], dtype=np.float64)
        last = np.asarray(slots[-1][channel], dtype=np.float64)
        output.extend((last - first).tolist())
    if len(output) != len(FEATURE_NAMES):
        raise RuntimeError(f"Feature width mismatch: {len(output)} != {len(FEATURE_NAMES)}")
    return output, missing_count, flagged_count


def extract_features(archive_path: Path, rows: list[dict[str, object]], cache_path: Path) -> tuple[np.ndarray, dict[str, object]]:
    started = time.time()
    feature_rows: list[list[float]] = []
    missing_total = 0
    flagged_total = 0
    with zipfile.ZipFile(archive_path) as archive:
        index = build_image_index(archive)
        for position, row in enumerate(rows, start=1):
            features, missing, flagged = extract_case_features(archive, index.get(str(row["case_id"]), {}), row)
            feature_rows.append(features)
            missing_total += missing
            flagged_total += flagged
            if position % 250 == 0 or position == len(rows):
                elapsed = time.time() - started
                print(f"feature extraction {position}/{len(rows)} · {elapsed:.1f}s", flush=True)
    matrix = np.asarray(feature_rows, dtype=np.float32)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_path,
        features=matrix,
        feature_names=np.asarray(FEATURE_NAMES),
        case_ids=np.asarray([row["case_id"] for row in rows]),
    )
    metadata = {
        "cases": len(rows),
        "features": len(FEATURE_NAMES),
        "channels": CHANNELS,
        "time_offsets_minutes": TIME_OFFSETS_MINUTES,
        "image_size": IMAGE_SIZE,
        "missing_or_rejected_channel_frames": missing_total,
        "flagged_channel_frames_rejected": flagged_total,
        "elapsed_seconds": time.time() - started,
    }
    cache_path.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return matrix, metadata


def load_or_extract(archive_path: Path, rows: list[dict[str, object]], cache_path: Path) -> tuple[np.ndarray, dict[str, object]]:
    if cache_path.exists():
        payload = np.load(cache_path, allow_pickle=False)
        expected = np.asarray([row["case_id"] for row in rows])
        if payload["features"].shape[1] == len(FEATURE_NAMES) and np.array_equal(payload["case_ids"], expected):
            metadata_path = cache_path.with_suffix(".json")
            metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
            print(f"using cached feature matrix {cache_path}")
            return payload["features"].astype(np.float64), metadata
    return extract_features(archive_path, rows, cache_path)


def assign_development_splits(rows: list[dict[str, object]]) -> dict[int, str]:
    by_region: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row["source_split"] == "training":
            by_region[int(row["noaa_region"])].append(row)
    strata: dict[tuple[int, str], list[int]] = defaultdict(list)
    for region, region_rows in by_region.items():
        year = min(row["input_start_dt"].year for row in region_rows)
        level = "X" if any(row["label_x1"] for row in region_rows) else "M" if any(row["label_m1"] for row in region_rows) else "N"
        strata[(year, level)].append(region)
    assignment: dict[int, str] = {}
    for stratum, regions in strata.items():
        ordered = sorted(regions, key=lambda region: stable_hash(f"{stratum}-{region}"))
        for index, region in enumerate(ordered):
            fraction = (index + 0.5) / len(ordered)
            assignment[region] = "development" if fraction < 0.70 else "tuning" if fraction < 0.85 else "calibration"
    return assignment


def prepare_matrix(matrix: np.ndarray, fit_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    medians = np.nanmedian(matrix[fit_mask], axis=0)
    medians = np.where(np.isfinite(medians), medians, 0.0)
    imputed = np.where(np.isfinite(matrix), matrix, medians)
    means = imputed[fit_mask].mean(axis=0)
    scales = imputed[fit_mask].std(axis=0)
    scales = np.where(scales > 1.0e-8, scales, 1.0)
    return (imputed - means) / scales, medians, np.vstack((means, scales))


def region_weights(regions: np.ndarray, mask: np.ndarray) -> np.ndarray:
    counts = Counter(int(region) for region in regions[mask])
    weights = np.zeros(len(regions), dtype=np.float64)
    for index in np.flatnonzero(mask):
        weights[index] = 1.0 / counts[int(regions[index])]
    weights[mask] *= mask.sum() / max(weights[mask].sum(), EPS)
    return weights


def fit_ridge(features: np.ndarray, target: np.ndarray, weights: np.ndarray, mask: np.ndarray, alpha: float) -> tuple[float, np.ndarray]:
    x = features[mask]
    y = target[mask]
    w = weights[mask]
    design = np.column_stack((np.ones(len(x)), x))
    weighted = design * np.sqrt(w)[:, None]
    weighted_y = y * np.sqrt(w)
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    coefficient = np.linalg.solve(weighted.T @ weighted + penalty, weighted.T @ weighted_y)
    return float(coefficient[0]), coefficient[1:]


def platt_fit(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    labels = labels.astype(np.float64)
    if labels.sum() == 0 or labels.sum() == len(labels):
        return 0.0, math.log((labels.mean() + 0.5 / len(labels)) / (1.0 - labels.mean() + 0.5 / len(labels)))
    slope = 1.0 / max(float(scores.std()), 1.0e-6)
    intercept = math.log((labels.mean() + EPS) / (1.0 - labels.mean() + EPS)) - slope * float(scores.mean())
    design = np.column_stack((scores, np.ones(len(scores))))
    coefficient = np.array([slope, intercept], dtype=np.float64)
    for _ in range(100):
        probabilities = sigmoid(design @ coefficient)
        gradient = design.T @ (probabilities - labels)
        curvature = probabilities * (1.0 - probabilities)
        hessian = design.T @ (design * curvature[:, None]) + np.eye(2) * 1.0e-6
        step = np.linalg.solve(hessian, gradient)
        coefficient -= step
        if float(np.max(np.abs(step))) < 1.0e-8:
            break
    if coefficient[0] < 0:
        coefficient[0] = 0.0
        coefficient[1] = math.log((labels.mean() + EPS) / (1.0 - labels.mean() + EPS))
    return float(coefficient[0]), float(coefficient[1])


def roc_auc(labels: np.ndarray, probabilities: np.ndarray) -> float | None:
    positives = int(labels.sum())
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    order = np.argsort(probabilities, kind="mergesort")
    ranks = np.empty(len(labels), dtype=np.float64)
    sorted_values = probabilities[order]
    index = 0
    while index < len(labels):
        end = index + 1
        while end < len(labels) and sorted_values[end] == sorted_values[index]:
            end += 1
        ranks[order[index:end]] = (index + 1 + end) / 2.0
        index = end
    return float((ranks[labels == 1].sum() - positives * (positives + 1) / 2.0) / (positives * negatives))


def average_precision(labels: np.ndarray, probabilities: np.ndarray) -> float | None:
    positives = int(labels.sum())
    if positives == 0:
        return None
    order = np.argsort(-probabilities, kind="mergesort")
    ordered = labels[order]
    precision = np.cumsum(ordered) / np.arange(1, len(ordered) + 1)
    return float((precision * ordered).sum() / positives)


def threshold_scores(labels: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict[str, float | int | None]:
    predicted = probabilities >= threshold
    tp = int(((labels == 1) & predicted).sum())
    fp = int(((labels == 0) & predicted).sum())
    tn = int(((labels == 0) & ~predicted).sum())
    fn = int(((labels == 1) & ~predicted).sum())
    pod = tp / max(tp + fn, 1)
    far = fp / max(tp + fp, 1)
    specificity = tn / max(tn + fp, 1)
    tss = pod + specificity - 1.0
    denominator = (tp + fn) * (fn + tn) + (tp + fp) * (fp + tn)
    hss = 2.0 * (tp * tn - fp * fn) / denominator if denominator else None
    return {"threshold": threshold, "tp": tp, "fp": fp, "tn": tn, "fn": fn, "pod": pod, "far": far, "tss": tss, "hss": hss}


def choose_threshold(labels: np.ndarray, probabilities: np.ndarray) -> float:
    candidates = np.unique(np.quantile(probabilities, np.linspace(0.0, 1.0, 201)))
    return float(max(candidates, key=lambda threshold: (threshold_scores(labels, probabilities, float(threshold))["tss"], -threshold)))


def reliability(labels: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> list[dict[str, float | int]]:
    order = np.argsort(probabilities)
    output = []
    for indices in np.array_split(order, bins):
        if len(indices):
            output.append({"mean_forecast": float(probabilities[indices].mean()), "observed_frequency": float(labels[indices].mean()), "count": int(len(indices))})
    return output


def metrics(labels: np.ndarray, probabilities: np.ndarray, climatology: float, threshold: float) -> dict[str, object]:
    probabilities = np.clip(probabilities, EPS, 1.0 - EPS)
    brier = float(np.mean((probabilities - labels) ** 2))
    reference = float(np.mean((climatology - labels) ** 2))
    bins = reliability(labels, probabilities)
    ece = sum(row["count"] * abs(row["mean_forecast"] - row["observed_frequency"]) for row in bins) / len(labels)
    return {
        "samples": int(len(labels)),
        "positives": int(labels.sum()),
        "prevalence": float(labels.mean()),
        "brier_score": brier,
        "brier_skill_vs_training_climatology": 1.0 - brier / reference if reference else None,
        "log_loss": float(-np.mean(labels * np.log(probabilities) + (1 - labels) * np.log(1 - probabilities))),
        "roc_auc": roc_auc(labels, probabilities),
        "precision_recall_auc": average_precision(labels, probabilities),
        "expected_calibration_error": float(ece),
        "reliability": bins,
        "decision": threshold_scores(labels, probabilities, threshold),
    }


def bootstrap_intervals(
    labels: np.ndarray,
    probabilities: np.ndarray,
    regions: np.ndarray,
    climatology: float,
    iterations: int,
) -> dict[str, list[float] | int]:
    random = np.random.default_rng(20260903)
    unique = np.unique(regions)
    by_region = {region: np.flatnonzero(regions == region) for region in unique}
    values: dict[str, list[float]] = defaultdict(list)
    for _ in range(iterations):
        sampled = random.choice(unique, size=len(unique), replace=True)
        indices = np.concatenate([by_region[region] for region in sampled])
        y = labels[indices]
        p = probabilities[indices]
        if y.sum() == 0 or y.sum() == len(y):
            continue
        brier = float(np.mean((p - y) ** 2))
        reference = float(np.mean((climatology - y) ** 2))
        values["brier_skill"].append(1.0 - brier / reference if reference else math.nan)
        values["roc_auc"].append(float(roc_auc(y, p)))
        values["precision_recall_auc"].append(float(average_precision(y, p)))
    output: dict[str, list[float] | int] = {"iterations_requested": iterations, "iterations_valid": len(values["brier_skill"])}
    for name, series in values.items():
        finite = np.asarray([value for value in series if math.isfinite(value)])
        output[f"{name}_95_ci"] = [float(np.quantile(finite, 0.025)), float(np.quantile(finite, 0.975))] if len(finite) else []
    return output


def json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-iterations", type=int, default=500)
    parser.add_argument("--force-features", action="store_true")
    args = parser.parse_args()

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_manifest(args.manifest.expanduser().resolve())
    cache_path = output_dir / "sdo_temporal_features.npz"
    if args.force_features and cache_path.exists():
        cache_path.unlink()
    raw_features, feature_meta = load_or_extract(args.archive.expanduser().resolve(), rows, cache_path)

    regions = np.asarray([row["noaa_region"] for row in rows], dtype=int)
    peak_flux = np.asarray([row["peak_flux_value"] for row in rows], dtype=np.float64)
    target = np.log10(np.clip(peak_flux, 1.0e-9, 1.0e-3))
    labels_m = np.asarray([row["label_m1"] for row in rows], dtype=int)
    labels_x = np.asarray([row["label_x1"] for row in rows], dtype=int)
    source_train = np.asarray([row["source_split"] == "training" for row in rows])
    test_mask = ~source_train
    assignments = assign_development_splits(rows)
    development = np.asarray([source_train[index] and assignments.get(int(region)) == "development" for index, region in enumerate(regions)])
    tuning = np.asarray([source_train[index] and assignments.get(int(region)) == "tuning" for index, region in enumerate(regions)])
    calibration = np.asarray([source_train[index] and assignments.get(int(region)) == "calibration" for index, region in enumerate(regions)])
    fit_for_production = development | tuning

    features, medians, standardization = prepare_matrix(raw_features, fit_for_production)
    weights = region_weights(regions, source_train)
    alpha_candidates = (0.1, 1.0, 10.0, 100.0)
    tuning_results = []
    for alpha in alpha_candidates:
        intercept, coefficient = fit_ridge(features, target, weights, development, alpha)
        scores = intercept + features @ coefficient
        normalized_briers = []
        for labels in (labels_m, labels_x):
            slope, offset = platt_fit(scores[tuning], labels[tuning])
            probabilities = sigmoid(slope * scores[tuning] + offset)
            brier = float(np.mean((probabilities - labels[tuning]) ** 2))
            climatology = float(labels[development].mean())
            reference = float(np.mean((climatology - labels[tuning]) ** 2))
            normalized_briers.append(brier / max(reference, EPS))
        tuning_results.append({"alpha": alpha, "normalized_brier_objective": float(np.mean(normalized_briers))})
    selected_alpha = min(tuning_results, key=lambda item: item["normalized_brier_objective"])["alpha"]
    intercept, coefficient = fit_ridge(features, target, weights, fit_for_production, float(selected_alpha))
    scores = intercept + features @ coefficient

    target_reports: dict[str, object] = {}
    probabilities_by_target: dict[str, np.ndarray] = {}
    calibrators: dict[str, tuple[float, float]] = {}
    for name, labels in (("M1+", labels_m), ("X1+", labels_x)):
        slope, offset = platt_fit(scores[calibration], labels[calibration])
        probabilities = sigmoid(slope * scores + offset)
        probabilities_by_target[name] = probabilities
        calibrators[name] = (slope, offset)
    probabilities_by_target["X1+"] = np.minimum(probabilities_by_target["X1+"], probabilities_by_target["M1+"])

    for name, labels in (("M1+", labels_m), ("X1+", labels_x)):
        probabilities = probabilities_by_target[name]
        threshold = choose_threshold(labels[calibration], probabilities[calibration])
        climatology = float(labels[fit_for_production].mean())
        report = metrics(labels[test_mask], probabilities[test_mask], climatology, threshold)
        report.update(
            {
                "training_climatology": climatology,
                "calibrator": {"method": "Platt/logistic on active-region-disjoint calibration set", "slope": calibrators[name][0], "intercept": calibrators[name][1]},
                "calibration_samples": int(calibration.sum()),
                "calibration_positives": int(labels[calibration].sum()),
                "test_positive_episode_proxies_48h": len({row[f"label_{name[0].lower()}1_plus_episode_proxy"] for index, row in enumerate(rows) if test_mask[index] and row[f"label_{name[0].lower()}1_plus_episode_proxy"]}),
                "active_region_bootstrap": bootstrap_intervals(labels[test_mask], probabilities[test_mask], regions[test_mask], climatology, args.bootstrap_iterations),
            }
        )
        target_reports[name] = report

    predictions_path = output_dir / "sdo_temporal_test_predictions.csv.gz"
    with gzip.open(predictions_path, "wt", encoding="utf-8", newline="") as handle:
        columns = ["case_id", "noaa_region", "input_start", "target_end", "peak_flux", "label_m1_plus", "probability_m1_plus", "label_x1_plus", "probability_x1_plus"]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for index, row in enumerate(rows):
            if not test_mask[index]:
                continue
            writer.writerow(
                {
                    "case_id": row["case_id"], "noaa_region": row["noaa_region"],
                    "input_start": row["input_start"], "target_end": row["target_end"],
                    "peak_flux": row["peak_flux"], "label_m1_plus": labels_m[index],
                    "probability_m1_plus": probabilities_by_target["M1+"][index],
                    "label_x1_plus": labels_x[index], "probability_x1_plus": probabilities_by_target["X1+"][index],
                }
            )

    model_path = output_dir / "sdo_temporal_model.npz"
    np.savez_compressed(
        model_path,
        coefficient=coefficient,
        intercept=np.asarray(intercept),
        imputation_medians=medians,
        means=standardization[0],
        scales=standardization[1],
        feature_names=np.asarray(FEATURE_NAMES),
        m1_platt=np.asarray(calibrators["M1+"]),
        x1_platt=np.asarray(calibrators["X1+"]),
    )

    coefficient_path = output_dir / "sdo_temporal_coefficients.csv"
    ranked_coefficients = sorted(
        (
            {
                "feature": name,
                "standardized_coefficient": float(value),
                "absolute_coefficient": float(abs(value)),
                "missing_fraction": float(np.mean(~np.isfinite(raw_features[:, index]))),
            }
            for index, (name, value) in enumerate(zip(FEATURE_NAMES, coefficient))
        ),
        key=lambda item: item["absolute_coefficient"],
        reverse=True,
    )
    with coefficient_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ranked_coefficients[0]))
        writer.writeheader()
        writer.writerows(ranked_coefficients)

    split_summary = {}
    for name, mask in (("development", development), ("tuning", tuning), ("calibration", calibration), ("untouched_test", test_mask)):
        split_summary[name] = {
            "cases": int(mask.sum()), "active_regions": int(len(np.unique(regions[mask]))),
            "m1_plus_cases": int(labels_m[mask].sum()), "x1_plus_cases": int(labels_x[mask].sum()),
        }
    report = {
        "schema_version": "1.0",
        "model_version": "wxf-sdo-temporal-zernike-pil-v1",
        "research_only": True,
        "operational": False,
        "dataset": "FHNW-i4DS SDOBenchmark full image archive",
        "model": {
            "method": "region-balanced ridge regression of log10 peak flux with separately Platt-calibrated M1+/X1+ probabilities",
            "selected_ridge_alpha": selected_alpha,
            "tuning_candidates": tuning_results,
            "probability_nesting": "P(X1+) clipped to P(M1+)",
            "top_standardized_coefficients": ranked_coefficients[:24],
        },
        "features": {
            **feature_meta,
            "feature_count": len(FEATURE_NAMES),
            "families": ["image statistics", "continuum sunspot contrast", "magnetic PIL proxies", "low-order Zernike moments", "12-hour temporal deltas"],
            "feature_names": FEATURE_NAMES,
        },
        "splits": split_summary,
        "split_method": "NOAA-active-region-disjoint, year-and-event-stratified development/tuning/calibration; supplied SDOBenchmark test untouched",
        "M1+": target_reports["M1+"],
        "X1+": target_reports["X1+"],
        "artifacts": {"feature_matrix": str(cache_path), "model": str(model_path), "case_predictions": str(predictions_path), "coefficient_report": str(coefficient_path)},
        "limitations": [
            "Positive case counts include overlapping forecast windows and are not independent flare-event counts.",
            "The supplied test set is active-region-disjoint but spans the same years as training; it is not a future chronological holdout.",
            "JPEG-derived PIL and Zernike descriptors are lower-fidelity than definitive vector-field SHARP CEA features.",
            "No archived SWPC probabilities are available for these exact cases, so this report cannot claim improvement over SWPC.",
            "The archive ends in 2017 and must undergo current-cycle shadow validation before operational use.",
        ],
        "promotion_gates": {
            "matched_swpc_cases": "missing",
            "prospective_current_cycle_shadow": "missing",
            "exact_goes_event_ids": "missing; 48-hour region episode proxies published",
            "case_level_predictions": "published",
            "active_region_bootstrap_intervals": "published",
            "status": "research evidence only",
        },
    }
    report_path = output_dir / "sdo_temporal_training_report.json"
    report_path.write_text(json.dumps(json_safe(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), "model": str(model_path), "predictions": str(predictions_path), "selected_alpha": selected_alpha, "M1+": target_reports["M1+"], "X1+": target_reports["X1+"]}, indent=2, default=json_safe))


if __name__ == "__main__":
    main()
