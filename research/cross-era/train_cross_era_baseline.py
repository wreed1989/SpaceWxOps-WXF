#!/usr/bin/env python3
"""Train an auditable daily WXF SMARP/SHARP cross-era baseline.

Features for calendar day D use only observations from D. Labels are
region-attributed NOAA/NCEI GOES flares on D+1. The model is developed on
cycle 23, calibrated and thresholded on cycle 24, and evaluated once on
cycle 25-to-date. This is retrospective research evidence, not a live model.
"""

from __future__ import annotations

import csv
import datetime as dt
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "wxf_cross_era"
MERGED = OUT / "merged_smarp_sharp_v3c_19960423_20260106.csv"
GOES_DIR = OUT / "goes_composite_1995_2026"
CASE_FILE = OUT / "cross_era_daily_cases.csv.gz"
PRED_FILE = OUT / "cross_era_cycle25_predictions.csv.gz"
REPORT_FILE = OUT / "cross_era_training_report.json"
COEF_FILE = OUT / "cross_era_coefficients.csv"

MAG_COLS = ["USFLUXL", "R_VALUE", "MEANGBL_GMM", "MEANGBZ", "USFLUXZ", "CMASKL"]
GEOM_COLS = ["LAT_FWT", "LON_FWT"]
NUMERIC_COLS = MAG_COLS + GEOM_COLS
USECOLS = ["DBINDEX", "T_OBS", "ARPNUM", "NOAA_AR", "CAR_ROT", "QUALITY"] + NUMERIC_COLS


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_noaa(value: object, year: int) -> int | None:
    try:
        region = int(float(value))
    except (TypeError, ValueError):
        return None
    if region <= 0:
        return None
    if year >= 2002 and region < 5000:
        region += 10000
    return region


def date_from_obs(series: pd.Series) -> pd.Series:
    text = series.astype(str)
    return text.str.slice(6, 10) + "-" + text.str.slice(0, 2) + "-" + text.str.slice(3, 5)


def aggregate_merged() -> tuple[pd.DataFrame, dict]:
    partials = []
    rows_by_instrument: Counter[str] = Counter()
    noaa_rows_by_instrument: Counter[str] = Counter()
    unique_patches = {"mdi": set(), "hmi": set()}
    missing = {instrument: Counter() for instrument in ("mdi", "hmi")}
    quality = {instrument: Counter() for instrument in ("mdi", "hmi")}
    date_min = None
    date_max = None
    total_rows = 0

    for chunk in pd.read_csv(MERGED, usecols=USECOLS, chunksize=250_000, low_memory=False):
        total_rows += len(chunk)
        chunk["instrument"] = chunk["DBINDEX"].str.slice(0, 3).str.lower()
        chunk["date"] = date_from_obs(chunk["T_OBS"])
        valid_dates = chunk["date"].str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)
        if valid_dates.any():
            local_min = chunk.loc[valid_dates, "date"].min()
            local_max = chunk.loc[valid_dates, "date"].max()
            date_min = local_min if date_min is None else min(date_min, local_min)
            date_max = local_max if date_max is None else max(date_max, local_max)
        for instrument, part in chunk.groupby("instrument", observed=True):
            if instrument not in unique_patches:
                continue
            rows_by_instrument[instrument] += len(part)
            unique_patches[instrument].update(pd.to_numeric(part["ARPNUM"], errors="coerce").dropna().astype(int).tolist())
            noaa_rows_by_instrument[instrument] += int((pd.to_numeric(part["NOAA_AR"], errors="coerce") > 0).sum())
            for column in NUMERIC_COLS:
                missing[instrument][column] += int(pd.to_numeric(part[column], errors="coerce").isna().sum())
            quality[instrument].update(pd.to_numeric(part["QUALITY"], errors="coerce").fillna(-1).astype(int).tolist())

        for column in ["NOAA_AR", "ARPNUM", "CAR_ROT", "QUALITY"] + NUMERIC_COLS:
            chunk[column] = pd.to_numeric(chunk[column], errors="coerce")
        filtered = chunk[
            valid_dates
            & chunk["instrument"].isin(["mdi", "hmi"])
            & (chunk["NOAA_AR"] > 0)
            & chunk["LON_FWT"].abs().le(65)
        ].copy()
        if filtered.empty:
            continue
        keys = ["date", "NOAA_AR", "instrument"]
        grouped = filtered.groupby(keys, observed=True)
        base = grouped.agg(source_rows=("DBINDEX", "size"), ar_patch=("ARPNUM", "first"), carrington_rotation=("CAR_ROT", "median"), quality_mode=("QUALITY", lambda values: values.mode().iat[0] if not values.mode().empty else np.nan)).reset_index()
        for column in NUMERIC_COLS:
            stats = grouped[column].agg(["sum", "count"]).reset_index().rename(columns={"sum": f"{column}_sum", "count": f"{column}_count"})
            base = base.merge(stats, on=keys, how="left", validate="one_to_one")
        partials.append(base)

    combined = pd.concat(partials, ignore_index=True)
    keys = ["date", "NOAA_AR", "instrument"]
    sum_columns = [f"{column}_sum" for column in NUMERIC_COLS]
    count_columns = [f"{column}_count" for column in NUMERIC_COLS]
    agg_spec = {column: "sum" for column in ["source_rows"] + sum_columns + count_columns}
    agg_spec.update({"ar_patch": "first", "carrington_rotation": "median", "quality_mode": "first"})
    daily = combined.groupby(keys, as_index=False, observed=True).agg(agg_spec)
    for column in NUMERIC_COLS:
        count = daily[f"{column}_count"].replace(0, np.nan)
        daily[column] = daily[f"{column}_sum"] / count
        daily[f"{column}_missing_fraction"] = 1.0 - daily[f"{column}_count"] / daily["source_rows"]
    daily.drop(columns=sum_columns + count_columns, inplace=True)
    daily["NOAA_AR"] = daily["NOAA_AR"].astype(int)
    daily["date"] = pd.to_datetime(daily["date"], format="%Y-%m-%d")

    overlap = daily.groupby(["date", "NOAA_AR"])["instrument"].nunique()
    overlap_pairs = int((overlap > 1).sum())
    daily["priority"] = daily["instrument"].map({"hmi": 0, "mdi": 1}).fillna(2)
    daily.sort_values(["date", "NOAA_AR", "priority", "source_rows"], ascending=[True, True, True, False], inplace=True)
    selected = daily.drop_duplicates(["date", "NOAA_AR"], keep="first").drop(columns="priority").reset_index(drop=True)

    audit = {
        "file": MERGED.name,
        "sha256": sha256(MERGED),
        "bytes": MERGED.stat().st_size,
        "rows": total_rows,
        "date_start": date_min,
        "date_end": date_max,
        "rows_by_instrument": dict(rows_by_instrument),
        "noaa_attributed_rows_by_instrument": dict(noaa_rows_by_instrument),
        "unique_patches_by_instrument": {key: len(value) for key, value in unique_patches.items()},
        "missing_by_instrument": {key: dict(value) for key, value in missing.items()},
        "top_quality_values_by_instrument": {key: value.most_common(8) for key, value in quality.items()},
        "daily_instrument_region_records_before_priority": len(daily),
        "overlap_region_days": overlap_pairs,
        "selected_region_days": len(selected),
        "selection_rule": "HMI preferred where HMI and MDI share the same NOAA-region/day; otherwise retain MDI",
        "limb_filter": "abs(LON_FWT) <= 65 degrees",
    }
    return selected, audit


def load_goes() -> tuple[pd.DataFrame, dict]:
    files = sorted(GOES_DIR.glob("*.csv"))
    frames = []
    for path in files:
        frame = pd.read_csv(path, usecols=["time", "start_time", "flare_id", "flare_class", "active_region", "event_id_swpc"], low_memory=False)
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
        frame["year"] = frame["time"].dt.year
        numeric_regions = pd.to_numeric(frame["active_region"], errors="coerce")
        wrapped = (frame["year"] >= 2002) & numeric_regions.lt(5000)
        frame["NOAA_AR"] = numeric_regions.where(~wrapped, numeric_regions + 10000)
        frame["class_letter"] = frame["flare_class"].astype(str).str.slice(0, 1).str.upper()
        frames.append(frame)
    events = pd.concat(frames, ignore_index=True)
    events = events[events["time"].notna() & events["class_letter"].isin(["A", "B", "C", "M", "X"])].copy()
    region_events = events[events["NOAA_AR"].notna()].copy()
    region_events["NOAA_AR"] = region_events["NOAA_AR"].astype(int)
    region_events["event_date"] = region_events["time"].dt.normalize()
    counts = region_events.groupby(["NOAA_AR", "event_date", "class_letter"]).size().unstack(fill_value=0).reset_index()
    for letter in ["A", "B", "C", "M", "X"]:
        if letter not in counts:
            counts[letter] = 0
    audit = {
        "files": len(files),
        "date_start": str(events["time"].min()),
        "date_end": str(events["time"].max()),
        "events": len(events),
        "region_attributed_events": len(region_events),
        "class_counts": events["class_letter"].value_counts().sort_index().to_dict(),
        "region_attributed_class_counts": region_events["class_letter"].value_counts().sort_index().to_dict(),
    }
    return counts[["NOAA_AR", "event_date", "C", "M", "X"]], audit


def signed_log1p(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return np.sign(numeric) * np.log1p(np.abs(numeric))


def build_cases(daily: pd.DataFrame, event_counts: pd.DataFrame) -> tuple[pd.DataFrame, list[str], dict]:
    cases = daily.copy()
    cases["forecast_date"] = cases["date"] + pd.Timedelta(days=1)
    labels = event_counts.rename(columns={"event_date": "forecast_date", "C": "target_C_events", "M": "target_M_events", "X": "target_X_events"})
    cases = cases.merge(labels, on=["NOAA_AR", "forecast_date"], how="left")
    for column in ["target_C_events", "target_M_events", "target_X_events"]:
        cases[column] = cases[column].fillna(0).astype(int)
    cases["target_m1"] = ((cases["target_M_events"] + cases["target_X_events"]) > 0).astype(int)
    cases["target_x1"] = (cases["target_X_events"] > 0).astype(int)

    history = event_counts.rename(columns={"event_date": "date", "C": "prior_C_1d", "M": "prior_M_1d", "X": "prior_X_1d"})
    cases = cases.merge(history, on=["NOAA_AR", "date"], how="left")
    for column in ["prior_C_1d", "prior_M_1d", "prior_X_1d"]:
        cases[column] = cases[column].fillna(0).astype(int)

    cases.sort_values(["NOAA_AR", "date"], inplace=True)
    feature_names = []
    for column in MAG_COLS:
        transformed = f"{column}_SLOG"
        cases[transformed] = signed_log1p(cases[column])
        feature_names.append(transformed)
    cases["LAT_FWT_VALUE"] = cases["LAT_FWT"]
    cases["ABS_LON_FWT"] = cases["LON_FWT"].abs()
    feature_names += ["LAT_FWT_VALUE", "ABS_LON_FWT"]

    prior_date = cases.groupby("NOAA_AR")["date"].shift(1)
    day_gap = (cases["date"] - prior_date).dt.days
    for column in [f"{name}_SLOG" for name in MAG_COLS] + ["LAT_FWT_VALUE"]:
        delta = cases.groupby("NOAA_AR")[column].diff()
        delta = delta.where(day_gap.eq(1))
        delta_name = f"{column}_DELTA24H"
        cases[delta_name] = delta
        feature_names.append(delta_name)
    feature_names += ["prior_C_1d", "prior_M_1d", "prior_X_1d"]

    last_mx = {}
    waiting = []
    for row in cases[["NOAA_AR", "date", "prior_M_1d", "prior_X_1d"]].itertuples(index=False):
        previous = last_mx.get(row.NOAA_AR)
        waiting.append((row.date - previous).days if previous is not None else np.nan)
        if row.prior_M_1d + row.prior_X_1d > 0:
            last_mx[row.NOAA_AR] = row.date
    cases["days_since_m1plus"] = np.minimum(pd.Series(waiting, index=cases.index), 90)
    feature_names.append("days_since_m1plus")

    for column in list(feature_names):
        missing_name = f"{column}_MISSING"
        if cases[column].isna().any():
            cases[missing_name] = cases[column].isna().astype(int)
            feature_names.append(missing_name)

    year = cases["forecast_date"].dt.year
    cases["cycle_split"] = np.select([year <= 2008, year <= 2019], ["development_cycle23", "calibration_cycle24"], default="test_cycle25")
    cases = cases[cases["forecast_date"] <= pd.Timestamp("2026-01-05")].copy()
    cases.to_csv(CASE_FILE, index=False, compression="gzip")
    audit = {
        "cases": len(cases),
        "active_regions": int(cases["NOAA_AR"].nunique()),
        "date_start": str(cases["date"].min().date()),
        "date_end": str(cases["date"].max().date()),
        "feature_count": len(feature_names),
        "splits": {},
    }
    for split, part in cases.groupby("cycle_split"):
        audit["splits"][split] = {
            "cases": len(part),
            "regions": int(part["NOAA_AR"].nunique()),
            "m1_positive_region_days": int(part["target_m1"].sum()),
            "x1_positive_region_days": int(part["target_x1"].sum()),
            "m1_events": int((part["target_M_events"] + part["target_X_events"]).sum()),
            "x1_events": int(part["target_X_events"].sum()),
            "instrument_rows": part["instrument"].value_counts().to_dict(),
        }
    return cases, feature_names, audit


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -35, 35)))


def fit_logistic(x: np.ndarray, y: np.ndarray, l2: float = 1.0, weights: np.ndarray | None = None, max_iter: int = 40) -> np.ndarray:
    design = np.column_stack([np.ones(len(x)), x])
    beta = np.zeros(design.shape[1])
    sample_weight = np.ones(len(x)) if weights is None else weights.astype(float)
    penalty = np.eye(design.shape[1]) * l2
    penalty[0, 0] = 0.0
    for _ in range(max_iter):
        probability = sigmoid(design @ beta)
        gradient = design.T @ ((probability - y) * sample_weight) + penalty @ beta
        curvature = probability * (1.0 - probability) * sample_weight
        hessian = (design.T * curvature) @ design + penalty + np.eye(design.shape[1]) * 1e-8
        step = np.linalg.solve(hessian, gradient)
        beta -= step
        if float(np.max(np.abs(step))) < 1e-7:
            break
    return beta


def predict_logistic(x: np.ndarray, beta: np.ndarray) -> np.ndarray:
    return sigmoid(np.column_stack([np.ones(len(x)), x]) @ beta)


def fit_platt(probability: np.ndarray, y: np.ndarray) -> np.ndarray:
    logits = np.log(np.clip(probability, 1e-7, 1 - 1e-7) / np.clip(1 - probability, 1e-7, 1))[:, None]
    return fit_logistic(logits, y, l2=0.01)


def apply_platt(probability: np.ndarray, beta: np.ndarray) -> np.ndarray:
    logits = np.log(np.clip(probability, 1e-7, 1 - 1e-7) / np.clip(1 - probability, 1e-7, 1))[:, None]
    return predict_logistic(logits, beta)


def roc_auc(y: np.ndarray, p: np.ndarray) -> float | None:
    positives = int(y.sum())
    negatives = len(y) - positives
    if not positives or not negatives:
        return None
    order = np.argsort(p)
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1)
    _, inverse, counts = np.unique(p, return_inverse=True, return_counts=True)
    sums = np.bincount(inverse, weights=ranks)
    average = sums / counts
    tied_ranks = average[inverse]
    return float((tied_ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def pr_auc(y: np.ndarray, p: np.ndarray) -> float | None:
    positives = int(y.sum())
    if not positives:
        return None
    order = np.argsort(-p, kind="mergesort")
    yy = y[order]
    tp = np.cumsum(yy)
    fp = np.cumsum(1 - yy)
    recall = tp / positives
    precision = tp / np.maximum(tp + fp, 1)
    recall = np.r_[0.0, recall]
    precision = np.r_[1.0, precision]
    return float(np.sum((recall[1:] - recall[:-1]) * precision[1:]))


def threshold_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict:
    pred = p >= threshold
    tp = int(np.sum(pred & (y == 1)))
    fp = int(np.sum(pred & (y == 0)))
    tn = int(np.sum(~pred & (y == 0)))
    fn = int(np.sum(~pred & (y == 1)))
    pod = tp / (tp + fn) if tp + fn else 0.0
    pofd = fp / (fp + tn) if fp + tn else 0.0
    far = fp / (tp + fp) if tp + fp else 0.0
    tss = pod - pofd
    denom = (tp + fn) * (fn + tn) + (tp + fp) * (fp + tn)
    hss = 2 * (tp * tn - fp * fn) / denom if denom else 0.0
    return {"threshold": float(threshold), "tp": tp, "fp": fp, "tn": tn, "fn": fn, "pod": pod, "far": far, "tss": tss, "hss": hss}


def best_threshold(y: np.ndarray, p: np.ndarray) -> dict:
    candidates = np.unique(np.quantile(p, np.linspace(0, 1, 301)))
    return max((threshold_metrics(y, p, value) for value in candidates), key=lambda row: (row["tss"], row["hss"]))


def reliability(y: np.ndarray, p: np.ndarray, bins: int = 10) -> tuple[list[dict], float]:
    order = np.argsort(p)
    groups = np.array_split(order, bins)
    rows = []
    for group in groups:
        if not len(group):
            continue
        rows.append({"mean_forecast": float(p[group].mean()), "observed_frequency": float(y[group].mean()), "count": int(len(group))})
    ece = sum(row["count"] * abs(row["mean_forecast"] - row["observed_frequency"]) for row in rows) / len(y)
    return rows, float(ece)


def metrics(y: np.ndarray, p: np.ndarray, climatology: float, threshold: float) -> dict:
    brier = float(np.mean((p - y) ** 2))
    baseline = float(np.mean((climatology - y) ** 2))
    rows, ece = reliability(y, p)
    return {
        "samples": len(y),
        "positives": int(y.sum()),
        "prevalence": float(y.mean()),
        "brier_score": brier,
        "brier_skill_vs_cycle24_climatology": 1 - brier / baseline if baseline else None,
        "log_loss": float(-np.mean(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1)))),
        "roc_auc": roc_auc(y, p),
        "precision_recall_auc": pr_auc(y, p),
        "expected_calibration_error": ece,
        "reliability": rows,
        **threshold_metrics(y, p, threshold),
    }


def bootstrap_bss(cases: pd.DataFrame, y_col: str, p_col: str, climatology: float, draws: int = 500) -> list[float]:
    groups = {region: index.to_numpy() for region, index in cases.groupby("NOAA_AR").groups.items()}
    regions = np.array(list(groups))
    rng = np.random.default_rng(3801)
    values = []
    y_all = cases[y_col].to_numpy(dtype=int)
    p_all = cases[p_col].to_numpy(dtype=float)
    for _ in range(draws):
        selected = rng.choice(regions, size=len(regions), replace=True)
        index = np.concatenate([groups[region] for region in selected])
        y = y_all[index]
        p = p_all[index]
        brier = np.mean((p - y) ** 2)
        baseline = np.mean((climatology - y) ** 2)
        if baseline > 0:
            values.append(float(1 - brier / baseline))
    return [float(value) for value in np.quantile(values, [0.025, 0.975])] if values else [None, None]


def train(cases: pd.DataFrame, feature_names: list[str], source_audit: dict, case_audit: dict, goes_audit: dict) -> dict:
    development = cases[cases["cycle_split"] == "development_cycle23"].copy().reset_index(drop=True)
    calibration = cases[cases["cycle_split"] == "calibration_cycle24"].copy().reset_index(drop=True)
    test = cases[cases["cycle_split"] == "test_cycle25"].copy().reset_index(drop=True)

    medians = development[feature_names].median(numeric_only=True).reindex(feature_names).fillna(0.0)
    x_dev_frame = development[feature_names].fillna(medians)
    means = x_dev_frame.mean()
    scales = x_dev_frame.std(ddof=0).replace(0, 1.0)

    def matrix(frame: pd.DataFrame) -> np.ndarray:
        return ((frame[feature_names].fillna(medians) - means) / scales).to_numpy(dtype=float)

    x_dev = matrix(development)
    x_cal = matrix(calibration)
    x_test = matrix(test)
    region_sizes = development["NOAA_AR"].value_counts()
    weights = development["NOAA_AR"].map(lambda region: 1.0 / region_sizes[region]).to_numpy()
    weights *= len(weights) / weights.sum()

    y_m_dev = development["target_m1"].to_numpy(dtype=int)
    y_m_cal = calibration["target_m1"].to_numpy(dtype=int)
    y_m_test = test["target_m1"].to_numpy(dtype=int)
    beta_m = fit_logistic(x_dev, y_m_dev, l2=3.0, weights=weights)
    raw_m_cal = predict_logistic(x_cal, beta_m)
    platt_m = fit_platt(raw_m_cal, y_m_cal)
    p_m_cal = apply_platt(raw_m_cal, platt_m)
    p_m_test = apply_platt(predict_logistic(x_test, beta_m), platt_m)

    severity_dev_mask = y_m_dev == 1
    severity_cal_mask = y_m_cal == 1
    y_x_given_m_dev = development.loc[severity_dev_mask, "target_x1"].to_numpy(dtype=int)
    y_x_given_m_cal = calibration.loc[severity_cal_mask, "target_x1"].to_numpy(dtype=int)
    severity_weights = weights[severity_dev_mask]
    beta_severity = fit_logistic(x_dev[severity_dev_mask], y_x_given_m_dev, l2=5.0, weights=severity_weights)
    raw_severity_cal = predict_logistic(x_cal[severity_cal_mask], beta_severity)
    platt_severity = fit_platt(raw_severity_cal, y_x_given_m_cal)
    p_severity_cal = apply_platt(predict_logistic(x_cal, beta_severity), platt_severity)
    p_severity_test = apply_platt(predict_logistic(x_test, beta_severity), platt_severity)
    p_x_cal = np.minimum(p_m_cal, p_m_cal * p_severity_cal)
    p_x_test = np.minimum(p_m_test, p_m_test * p_severity_test)

    threshold_m = best_threshold(y_m_cal, p_m_cal)
    threshold_x = best_threshold(calibration["target_x1"].to_numpy(dtype=int), p_x_cal)
    climatology_m = float(y_m_cal.mean())
    climatology_x = float(calibration["target_x1"].mean())
    test["p_m1"] = p_m_test
    test["p_x1"] = p_x_test

    result_m = metrics(y_m_test, p_m_test, climatology_m, threshold_m["threshold"])
    result_x = metrics(test["target_x1"].to_numpy(dtype=int), p_x_test, climatology_x, threshold_x["threshold"])
    result_m["brier_skill_ci"] = bootstrap_bss(test, "target_m1", "p_m1", climatology_m)
    result_x["brier_skill_ci"] = bootstrap_bss(test, "target_x1", "p_x1", climatology_x)
    result_m["calibration_threshold"] = threshold_m
    result_x["calibration_threshold"] = threshold_x

    prediction_columns = ["date", "forecast_date", "NOAA_AR", "instrument", "target_m1", "target_x1", "target_M_events", "target_X_events", "p_m1", "p_x1"]
    test[prediction_columns].to_csv(PRED_FILE, index=False, compression="gzip")

    coefficient_rows = []
    for target, beta in [("M1+", beta_m), ("X1+ given M1+", beta_severity)]:
        coefficient_rows.append({"target": target, "feature": "INTERCEPT", "coefficient": beta[0], "mean": "", "scale": ""})
        for index, feature in enumerate(feature_names, start=1):
            coefficient_rows.append({"target": target, "feature": feature, "coefficient": beta[index], "mean": means[feature], "scale": scales[feature]})
    with COEF_FILE.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(coefficient_rows[0]))
        writer.writeheader()
        writer.writerows(coefficient_rows)

    report = {
        "schema_version": "1.0",
        "model_version": "wxf-cross-era-smarp-sharp-daily-v1",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_only": True,
        "operational": False,
        "forecast_probabilities_changed": False,
        "target_definition": "Features from calendar day D; at least one region-attributed NOAA/NCEI GOES M1+/X1+ flare on D+1",
        "split_definition": "cycle 23 development (through 2008); cycle 24 calibration/threshold selection (2009-2019); cycle 25-to-date untouched test (2020-2026-01-05)",
        "feature_names": feature_names,
        "case_audit": case_audit,
        "source_audit": source_audit,
        "goes_audit": goes_audit,
        "cycle24_calibration_climatology": {"M1+": climatology_m, "X1+": climatology_x},
        "M1+": result_m,
        "X1+": result_x,
        "limitations": [
            "Cycle and instrument are partly confounded: development is dominated by MDI and final testing by HMI.",
            "Only GOES events carrying an active-region identifier can become regional positive labels.",
            "Daily aggregation is a retrospective baseline, not a replacement for issue-time 6/12-hour sequences.",
            "No matched historical SWPC probability table is available for this full interval.",
            "GONG/KPVT overlap calibration and a prospective shadow period remain outstanding.",
        ],
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    daily, source_audit = aggregate_merged()
    event_counts, goes_audit = load_goes()
    cases, feature_names, case_audit = build_cases(daily, event_counts)
    report = train(cases, feature_names, source_audit, case_audit, goes_audit)
    print(json.dumps({
        "model_version": report["model_version"],
        "source_rows": report["source_audit"]["rows"],
        "cases": report["case_audit"]["cases"],
        "splits": report["case_audit"]["splits"],
        "M1+": {key: report["M1+"][key] for key in ["samples", "positives", "brier_score", "brier_skill_vs_cycle24_climatology", "brier_skill_ci", "roc_auc", "precision_recall_auc", "expected_calibration_error", "tss", "far"]},
        "X1+": {key: report["X1+"][key] for key in ["samples", "positives", "brier_score", "brier_skill_vs_cycle24_climatology", "brier_skill_ci", "roc_auc", "precision_recall_auc", "expected_calibration_error", "tss", "far"]},
    }, indent=2))


if __name__ == "__main__":
    main()
