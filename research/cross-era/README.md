# WXF cross-era dataset seed

This directory is the auditable implementation of the first WXF cross-era
baseline. It does **not** change the live forecast probabilities.

## Materialized now

- `nadc_allAR_v1.xlsx`: source workbook downloaded from the NADC homogeneous
  MDI/HMI active-region database.
- `nadc_allAR_v1.csv`: lossless tabular conversion used by later joins.
- `goes_xrs_cycle23/`: annual NOAA/NCEI GOES XRS reports for 1996–2008.
- `goes_cycle23_events.csv.gz`: parsed GOES event table with M/X class,
  location and normalized NOAA-region identifiers.
- `noaa_srs_cycle23/`: daily NOAA/SWPC Solar Region Summary source files for
  1996–2008.
- `noaa_cycle23_region_days.csv.gz`: parsed sunspot morphology and location
  table for cycle 23.
- `merged_smarp_sharp_v3c_19960423_20260106.csv`: 1.15 GB merged MDI/SMARP
  and HMI/SHARP time series downloaded from IDSEAR.
- `goes_composite_1995_2026/`: 32 annual NOAA/NCEI composite XRS flare
  reports used for region-attributed cycle-held-out labels.
- `cross_era_daily_cases.csv.gz`: 40,637 daily active-region forecast cases.
- `cross_era_cycle25_predictions.csv.gz`: untouched cycle-25 case
  probabilities and labels.
- `cross_era_training_report.json` and `cross_era_coefficients.csv`: full
  model lineage, source audit, split counts, reliability bins, scores,
  thresholds, coefficients and grouped confidence intervals.

## Contracts

- `source_registry.json`: each recommended database, its branch, role,
  coverage, URL and honest ingestion status.
- `feature_contract.json`: features that may be shared across instruments and
  the HMI-only quantities that must not leak into the historical branch.
- `validation_contract.json`: cycle-held-out and instrument-held-out tests,
  metrics, comparators and non-negotiable split rules.
- `cross_era_audit.json`: hashes, source counts, label counts, quality flags
  and model-readiness status.

## Training design

The daily baseline uses cycle 23 for development, cycle 24 only for
probability calibration and threshold selection, and cycle 25-to-date as the
untouched test. M1+ has positive grouped Brier skill on cycle 25. X1+ remains
failed because its grouped Brier-skill interval crosses zero and its selected
threshold has an unacceptable false-alarm ratio.

GONG overlap-transfer features, KPVT cycles 21–22, matched historical SWPC
probabilities and a prospective shadow period remain outstanding. Until those
gates pass, the dashboard keeps this trained branch retrospective and isolated
from the live forecast.

Rebuild with:

```bash
python research/cross-era/build_cross_era_seed.py --download-srs
```

Retrain the cross-era baseline with:

```bash
python research/cross-era/train_cross_era_baseline.py
```
