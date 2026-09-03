# Dataset inventory and provenance

Only compact, reproducible, legally redistributable artifacts are committed. The raw 4 GB SDOBenchmark ZIP, 1.2 GB merged SMARP–SHARP CSV, HMI/AIA FITS imagery, JSOC caches, and FlareDB movies are intentionally excluded. Their checksums, source registries, builders, and derived audit products are included instead.

## Live SHARP training lane

- `datasets/sharp_mag_training_table_v2.csv.gz`: 7,706 daily region cases with scalar SHARP values, 24-hour changes, causal flare history, M1+/X1+ labels, and engineered features.
- `datasets/sharp_mag_training_table_v2.csv.gz.metadata.json`: query contract, label rules, quality-filter counts, source hashes, and date coverage.
- `datasets/goes_region_flares_1995_2026.csv.gz`: compact region-attributed NOAA/NCEI M/X event catalog assembled from annual composite GOES reports.
- `datasets/goes_region_flares_1995_2026.csv.gz.manifest.json`: source-file hashes and coverage.
- `build_goes_region_catalog.py` and `sharp_mag_pipeline.py`: reproducible catalog, dataset, training, and inference code.

## Cross-era lane

- `datasets/noaa_cycle23_region_days.csv.gz` and `datasets/goes_cycle23_events.csv.gz`: compact cycle-23 morphology and event tables.
- `datasets/cross_era_daily_cases.csv.gz`: harmonized retrospective daily cases.
- `datasets/cross_era_cycle25_predictions.csv.gz`: untouched cycle-25 predictions.
- `research/cross-era/`: builders, feature/validation contracts, coefficients, metrics, and source registry.

The raw merged 4.65-million-row SMARP–SHARP CSV is excluded because normal GitHub repositories reject individual files over 100 MiB and the artifact is reproducible from the source registry.

## SDO temporal-image lane

- `datasets/sdobenchmark_case_manifest.csv.gz`: 9,222 case definitions and active-region-safe split metadata.
- `datasets/sdo_temporal_features.npz`: compact derived temporal image features; no source images.
- `datasets/sdo_temporal_test_predictions.csv.gz`: case-level holdout predictions.
- `research/sdo-temporal/`: audit/training code, model, coefficients, metrics, and implementation summary.

The user-supplied SDOBenchmark archive remains local. Its recorded SHA-256 is `99c79cf008027b5a086a752dc864b2722f4ea6e10df5a033ba2c3c2535ccad8c`.

## NJIT FlareDB

FlareDB provides standardized 32-hour HMI/AIA sequences around significant events. WXF audits its event list against NOAA labels and available pre-issue SHARP cases but does not redistribute or train directly on the positive-only archive. The repository event list audited on 2026-09-03 had 103 rows, while the 2026 paper describes 151 events from 82 regions; that version difference is retained in `research/flaredb/coverage_audit.json` rather than silently pooled.

## Integrity

Run `python build_dataset_manifest.py` after changing a compact dataset. Every tracked dataset's byte count and SHA-256 is recorded in `datasets/manifest.json`.
