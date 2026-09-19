# Coronal Hole / HSS Outlook

## Maintained implementation

The canonical dashboard is [`SpaceWxOps_Coronal_Hole_HSS_Outlook.html`](SpaceWxOps_Coronal_Hole_HSS_Outlook.html). It contains the flare operations desk and registered CH/HSS tools. `index.html` and the old `dashboard/SpaceWxOps_3.9_WXF_FullDisk_XModel_Standalone.html` URL redirect to it.

The maintained Python source lives in `chhss/`. Both live and historical workflows execute the source from the triggering commit, using `requirements-chhss.txt`. There is no embedded Python workflow or hidden checkout of an older implementation.

- `.github/workflows/chhss-live.yml`: hourly at minute 23; current AIA NRT and HMI acquisition, compact live products, and the dashboard feed.
- `.github/workflows/chhss-backfill-run.yml`: explicitly requested historical range, end date exclusive. Defaults to **2026-09-01 through 2026-09-08 exclusive** (September 1–7).
- `.github/workflows/ci.yml`: numerical/FITS, publication, browser contract, and existing flare regression tests.

Dispatching either acquisition workflow on a feature branch is an acceptance test: it uploads run evidence but cannot publish to `main` or create a release. Dispatch on `main` publishes after processing. Repository Actions must permit the workflow's `contents: write` token. No JSOC email is needed for the active direct-online path. Offline/tape records are explicitly rejected; automatic staged exports are not implemented.

## Local commands

Use Python 3.12 in a dedicated environment:

```sh
python3.12 -m venv .venv-chhss
. .venv-chhss/bin/activate
python -m pip install -r requirements-chhss.txt
python -m unittest discover -s tests -v
node tests/test_dashboard.cjs
python -m chhss.live --output product
python -m chhss.pipeline backfill --start 2026-09-01 --end 2026-09-08 --output results
```

A backfill can resume registered measurements already in `results/history/`; failed dates are retried on the next invocation. GitHub runs reuse downloaded source caches, but a new runner does not automatically restore a previous `results/history/`. Keep the same output directory when resuming locally. The workflow permits up to 93 days per run; begin with a small recent interval. A complete requested date ledger is not proof of complete scientific coverage.

To refresh the dashboard's **offline flare** snapshot, run `python embed_dashboard_data.py`. To build one downloadable HTML with the current CH/HSS publication embedded, run:

```sh
python scripts/build_dashboard.py --output dist/SpaceWxOps_Coronal_Hole_HSS_Outlook.html
```

Open that file in a modern browser. It validates the embedded snapshot, then refreshes from the public feed. Observation timestamps remain unchanged; expired observations are withheld. The canonical source HTML also works online without the embedded snapshot. Replace previously downloaded copies when updating the client; its version appears under Data connection → Connection & verification details.

AIA 171/193/211 FITS and signed HMI gauss are acquired by the worker, which decodes, quality-checks and WCS-registers them before publication. The browser does not need canvas access to third-party quicklook JPEGs for registered measurements. Its AIA diagnostics show the actual FITS URLs, observation times, quality flags and checksums. HMI ingestion and per-core polarity acceptance are separate: mixed/weak cores remain unknown, and degraded fields require temporal sign agreement.

The rolling 75-day OMNI refresh runs independently of AIA/HMI. Either failure retains that source's last-good product and fails the workflow visibly, while the successful source is still published. `status.json` records separate `measurement` and `recurrence` health. OMNI coverage includes valid-hour counts, the last available hour and all seven forecast days' T−27d daily means (at least 18 valid hours). The browser can read `recurrence.json` independently if the measurement envelope is rejected. This recent recurrence refresh does not launch an observation-history backfill.

## Published data contract

The dashboard reads `https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/main/chhss-data/feed.json` by default. Opening the standalone HTML on a work PC needs no Python installation. Network/CORS policies must allow the public data URL.

| Product | Meaning |
| --- | --- |
| `feed.json` | Bounded `chhss-feed-1` envelope: current pack, recurrence, source health, latest-period report, up to 90 case summaries and 200 paired/excluded rows. Total metrics are for the full labeled period. |
| `current.json` | Last-good `chhss-science-1` measurement. The binary mask and WCS labels use `runs-u8-v1`; the client decodes and verifies the SHA-256 and per-core counts. |
| `status.json` | Latest acquisition attempt, including failures and original source observation time. |
| `recurrence.json` | Recent gap-preserving OMNI2 hourly values, with original timestamps. |
| `history.json` | Compact case records and per-period progress/release links. Overlapping requests deduplicate case IDs. Export archive downloads this index and compact dataset, not raw rasters. |
| `backfill/<start>_<end>/` | Compact cases, full validation report, progress, truth provenance, source commit and durable archive manifest. |
| `live-ledger/` | Rolling 90-day compact forward-collected measurement record. These are measurements, not human-issued forecasts. |

`python -m chhss.publish --root chhss-data` rebuilds the interface after applying a run's products to the latest publication checkout. A failed acquisition retains the last-good observation without changing its timestamp; the dashboard withholds stale measurements after six hours. A missing recent validation report remains unavailable. Older scores are never presented as current-period verification.

## Evidence and retention

Full backfill evidence is zipped and uploaded to a unique GitHub release **before** compact records are committed. The workflow downloads the release asset again and compares bytes. `archive.json` records the asset URL, SHA-256, byte count, every member's checksum, date coverage, source commit, and successes/failures. The ZIP includes every acquired registered measurement, selected hourly OMNI truth, acquisition manifests, processing code, environment, compact cases, and validation report. A run with missing dates stays incomplete and fails its final acceptance check even though its available evidence is retained.

Live diagnostics have **30-day** Actions retention; backfill diagnostics have **90-day** retention. Caches and expiring Actions artifacts are not the durable backfill archive. Feature-branch test evidence must be promoted explicitly to a release if it is to be retained permanently. Select scientifically useful complete datasets or periods relevant to current operations; do not accumulate arbitrary old quarterly observation archives.

The unused partial 2024 observation archive was removed at the owner's request. Only its small, unchanged performance report remains in `docs/validation/2024-q1.json`. It documents that the area–speed diagnostic underperformed recurrence; it is not part of the current dashboard feed. Normal Git history remains recoverable and has not been rewritten.

## Scientific contract and limitations

The active frozen recipe is `chhss-euv-hmi-20260919.1`, restored from the implementation already used by successful live runs. It obtains co-timed AIA 171/193/211 numerical FITS and signed HMI LOS fields, uses same-record metadata, checks instrument/WCS/quality/time, rotates and reprojects to a common grid, and independently measures polarity per core and connected candidate. AIA channels may differ by at most five minutes; EUV/HMI by at most 30 minutes. The current NRT path verifies the informational AIA flag against its provider definition. Degraded HMI `NOCOSMICRAY` observations require temporal sign agreement. Unknown polarity stays unknown.

The EUV detector is a custom fixed-threshold candidate method, not CHIMERA or a validated manual catalogue. Polarity uses the labeled `B_LOS/mu` radial approximation, `mu >= 0.4`, and fixed QA thresholds. It is not a prediction of interplanetary Bz.

Historical predictions are retrospective reconstructions. The fixed diagnostic is `350 + 900 A`, with E/M/W lags of 6/4/2 days and abstention below 2% filling. Verification uses fixed UTC daily-mean OMNI speed with **at least 18 valid hours**, matched to the same statistic 27 days earlier. Missing target/baseline data are excluded, never scored as zero error. This is the actual active recipe; the retired setup document described a different unused implementation with a 20-hour threshold.

There is no automatic coefficient fitting, operational promotion, ICME screening, or source-family identification. All-events results and 34-day time-block uncertainty retain those limits. Successful acquisition does not establish forecast skill, onset/duration skill, geomagnetic-impact skill, or justify autonomous alerts.

## Acceptance

1. Require real AIA/HMI source URLs, checksums and observation timestamps in `current.json`; inspect `status.json` for stale/degraded/failure conditions.
2. Inspect registration and per-core signs. Mixed, weak and limb-excluded sources may correctly remain unknown.
3. For a recent backfill, inspect every requested date's result and target/recurrence coverage. OMNI archive lag can leave target dates unscored.
4. Check the labeled validation metrics and retained research status independently of acquisition success.
