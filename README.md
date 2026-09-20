# SpaceWxOps WXF flare forecasting

This repository contains the current research model, reproducible training data, daily forecast workflows, and one maintained standalone Operations Wall dashboard for M1+/X1+ solar-flare forecasting.

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

## Experimental proton outlook and current data relays

The Models → SEP / Proton selection now includes [WXF SEP 0.1](research/proton_forecast/README.md), a calibrated flare-triggered empirical baseline with a chronological 2010–2026 hindcast. It estimates fixed-window probabilities for the requested P10 ≥10 / >40 pfu and P50 ≥10 pfu events. Its low detection rate and inconclusive P50 skill are shown in the interface; it is not an operationally validated replacement for published guidance. UMASEP / REleASE remains selectable.

The existing hourly science publication also provides dated [SOLAR-1 STIS](https://www.swpc.noaa.gov/products/solar-wind) ion measurements and [GFZ Hp60/ap60](https://kp.gfz.de/en/hp30-hp60/data). STIS is primary when its operational quality is accepted and the last valid measurement is no older than 90 minutes; otherwise the dashboard uses ACE EPAM and labels the fallback. STIS measurements have one-minute cadence but this relay publishes hourly. The observation time remains visible. GFZ one-hour ap60 bars are labelled separately from the three-hour Ap fallback.

The standalone build embeds these dated snapshots, then refreshes the published relays. Solar imagery indices/playback refresh every 15 minutes. High Flyer shows Northern/Southern Hemisphere NAIRAS maxima at 20 km in mSv/h; stale readings cannot trigger alerts. The Product Catalog consolidates duplicate observation/timeline/recurrence entries while migrating old saved selections. SWPC has a full-width timeline without its former Context inspector.

The September 19 Actions review found a Stanford connection timeout and an expired flare base in an external refresh. JSOC GET retries are now bounded but more tolerant; the external-refresh script can recover a newer, still-valid publication before enrichment. If no trustworthy current data exists, the workflow still fails visibly and retains dated last-good data. Failure notification preferences are unchanged.

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

The canonical dashboard is [`SpaceWxOps_Coronal_Hole_HSS_Outlook.html`](SpaceWxOps_Coronal_Hole_HSS_Outlook.html). It contains the active-region HMI loop, SWPC/WXF comparisons, and registered coronal-hole/HSS tools. The old dashboard path redirects here. Run `python embed_dashboard_data.py` to update its offline flare payload and model report.

The Solar Cycle catalog product plots NOAA's full observed and predicted monthly
indices. **CME | Solar Wind** contains published SWPC ENLIL and Reading HUXt
products plus a clearly marked PyCAT placeholder. The CH detector now screens
dark components for cool-corona contrast and reports magnetic support separately.
See [solar product methods and controls](docs/solar-products.md).

CH/HSS acquisition and historical verification use the maintained `chhss/` package. See [CHHSS_Setup.md](CHHSS_Setup.md) for the current feed contract, September 2026 acceptance range, reproducible commands, and evidence retention. Full recent backfill datasets live in versioned release assets; compact products and checksummed manifests stay in Git.

See [docs/CONSOLIDATION.md](docs/CONSOLIDATION.md) for the dependency inventory and retirement decisions.

## Research status

This remains research/shadow guidance. M1+ has positive grouped holdout skill; X1+ improves Brier score over the former constant-severity method, but its active-region bootstrap interval still crosses zero because the untouched test contains only six X-positive region-days. Do not mark WXF operational until prospective shadow and matched SWPC/MCSTAT/MCEVOL verification gates pass.

### Monitor layout and particle forecasts

The [Monitor layout guide](docs/monitor-layout.md) explains selection, removal,
resizing and saved views. [Particle products and future options](docs/particle-forecasting-options.md)
describes the connected UMASEP, HESPERIA REleASE and SWPC REFM feeds.
[NAIRAS radiation dose](docs/radiation-dose.md) documents the configurable 20 km
effective-dose nowcast in the Alert card and forecast-only Models visibility.
The [iSWA input review and WXF SEP design](docs/iswa-inputs-and-sep-design.md)
identifies current numeric feeds and a scientifically testable event-triggered model.
