# SpaceWxOps WXF flare forecasting

This repository contains the current research model, reproducible training data, daily forecast workflow, evidence branches, and standalone Operations Wall dashboard for M1+/X1+ solar-flare forecasting.

## Current output

The scheduled workflow publishes:

- NOAA/SWPC official whole-disk guidance first, with official numbered-region values when available.
- WXF full-disk M1+/X1+ probabilities with coverage metadata.
- A WXF value for every fresh visible NOAA numbered region.
- Independently calibrated magnetic/history M1+ and X1+ forecasts when a quality-controlled HMI/SHARP mapping is available.
- Explicitly labelled McIntosh or climatology coverage fallbacks where a trustworthy SHARP vector is not available.
- Independent SIDC, SolarMonitor, and NASA/CCMC comparisons only when their current products are verifiably available.

The current model is `sharp-mag-20260903-xstruct-history-v3`. X1+ is no longer a fixed percentage of M1+: it has its own strongly regularized and calibrated magnetic/history classifier, followed by the physical constraint `X1+ <= M1+`.

See [MODEL_CARD.md](MODEL_CARD.md) for architecture, validation, uncertainty, and limitations, and [DATASETS.md](DATASETS.md) for the complete data inventory.

## Daily automation

`.github/workflows/wxf-daily.yml` requests the formal 21Z issue at 21:20 UTC and retries at 22:20, 23:20, and 00:20 UTC. The lightweight external-guidance workflow refreshes comparison providers separately. Publication locking prevents simultaneous jobs from overwriting each other.

The inference run:

1. Retrieves the latest 18Z HMI SHARP NRT vectors and their prior-day values.
2. Expands shared multi-region HARPs for visibility while marking them as shared and counting each HARP once in the full-disk aggregate.
3. Adds strictly pre-issue regional flare history from SWPC edited events.
4. Produces calibrated M1+/X1+ probabilities and explicit fallback coverage.
5. Reads the official SWPC whole-disk forecast directly from the three-day product.
6. Writes `flare_guidance.json` and `flare_guidance.js`.

## Rebuild and train

Install the dependencies in `requirements-sharp-mag.txt`, then:

```bash
python build_goes_region_catalog.py \
  --source-dir /path/to/ncei/annual-goes-csvs \
  --output datasets/goes_region_flares_1995_2026.csv.gz

python sharp_mag_pipeline.py build-dataset \
  --work-dir ./sharp-mag-work \
  --output datasets/sharp_mag_training_table_v2.csv.gz \
  --start 2012-10-01 \
  --max-longitude 50 \
  --flare-csv datasets/goes_region_flares_1995_2026.csv.gz

python sharp_mag_pipeline.py train \
  --dataset datasets/sharp_mag_training_table_v2.csv.gz \
  --model-dir . \
  --model-version sharp-mag-20260903-xstruct-history-v3 \
  --max-longitude 50
```

For a current local forecast:

```bash
python sharp_mag_pipeline.py forecast \
  --model-dir . \
  --output flare_guidance.json \
  --js-output flare_guidance.js \
  --issue-time cycle
```

## Verification

```bash
python -m unittest -v \
  test_sharp_mag_pipeline.py \
  test_solar_monitor_guidance.py \
  test_external_flare_guidance_strict_v4.py \
  test_external_source_audit.py \
  test_publication_guard.py

python sharp_mag_pipeline.py self-test --output-dir /tmp/sharp-mag-self-test
python build_dataset_manifest.py
```

## Dashboard

The latest standalone dashboard is `dashboard/SpaceWxOps_3.9_WXF_FullDisk_XModel_Standalone.html`. It retains the active-region HMI continuum/magnetogram loop, displays SWPC first, distinguishes magnetic predictions from coverage fallbacks, and embeds the current forecast/model report for offline use. Run `embed_dashboard_data.py` after refreshing model artifacts and the forecast.

## Research status

This remains research/shadow guidance. M1+ has positive grouped holdout skill; X1+ improves Brier score over the former constant-severity method, but its active-region bootstrap interval still crosses zero because the untouched test contains only six X-positive region-days. Do not mark WXF operational until prospective shadow and matched SWPC/MCSTAT/MCEVOL verification gates pass.
