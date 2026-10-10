# Maintained dataset inventory

The runtime/verification checkout retains four SHARP/GOES artifacts plus `datasets/manifest.json`:

| Artifact | Why it remains |
| --- | --- |
| `datasets/sharp_mag_training_table_v2.csv.gz` | The 7,706-case scalar SHARP baseline is read by `flare/refresh_evidence.py` for live evidence generation and by the verification audit. It is not disposable training-only data. |
| `datasets/sharp_mag_training_table_v2.csv.gz.metadata.json` | Original query, quality, labeling, and source provenance for that baseline. |
| `datasets/goes_region_flares_1995_2026.csv.gz` | Compact region-attributed NOAA/NCEI event catalog for reproducible baseline construction. |
| `datasets/goes_region_flares_1995_2026.csv.gz.manifest.json` | Original source hashes and coverage for the catalog. |

These four retained files total **3,450,281 bytes** and are unchanged by cleanup. The manifest lists their exact bytes and SHA-256 checksums. `tests/test_repository_layout.py` checks both the file inventory and hashes. Regenerate the manifest with `python build_dataset_manifest.py` after an intentional dataset update.

Frozen deployment models are stored separately at the root and under `research/electron_fluence/` / `research/proton_forecast/`. Compact evaluation reports remain alongside those models. Published observations and as-issued histories in `chhss-data/` and `forecast_history.jsonl` are not removed.

## Retired offline experiments

The cross-era morphology experiment, SDO temporal-image experiment, and FlareDB coverage audit are not imported by the maintained publishers. Their source, provenance, and associated seven datasets have been removed from the current checkout, not erased from history.

The complete original inventory and scientific records remain in the [pre-cleanup snapshot](https://github.com/wreed1989/SpaceWxOps-WXF/tree/97e029c6840308112fc5b8a0b565210f13f0b8d7/datasets) and [original dataset documentation](https://github.com/wreed1989/SpaceWxOps-WXF/blob/97e029c6840308112fc5b8a0b565210f13f0b8d7/DATASETS.md). See [recovery instructions](docs/CONSOLIDATION.md) before intentionally restoring an offline research lane.

Raw FITS imagery, multi-gigabyte source archives, and acquisition caches remain excluded. Removing an unused lane does not establish that its scientific approach is invalid; it separates historical experiments from the code needed to operate and verify the maintained products.
