# SpaceWxOps WXF

Maintained source for the Operations Wall, its forecast publishers, and the evidence used to evaluate those forecasts.

## Open the dashboard

The canonical entry point is [SpaceWxOps_Coronal_Hole_HSS_Outlook.html](SpaceWxOps_Coronal_Hole_HSS_Outlook.html). `index.html` and the old dashboard URL redirect there. The dashboard retains its embedded dated snapshots and existing live-feed URLs. Local-only images or caches are not supplied by this source checkout.

## What stays in this repository

| Area | Required source and artifacts |
| --- | --- |
| Flare guidance | `sharp_mag_pipeline.py`, both frozen `sharp_mag_*.joblib` models, manifest/report, SWPC and external-provider adapters, `flare_guidance.json` / `.js`, and forecast history. The `fixed`, `strict_v3`, and `strict_v4` adapter files form an active dependency chain, not interchangeable old versions. |
| Solar Flare evidence | `flare/`, the SHARP baseline in `datasets/`, and the evidence publication workflow. The baseline table is read during live verification, not only during training. |
| Coronal Hole / HSS Outlook | `chhss/`, `chhss-data/`, backfill/publication scripts, and both live/backfill workflows. |
| Electron and proton models | `research/electron_fluence/` and `research/proton_forecast/` contain active runtime code despite their directory name. Keep all three electron model arrays and the numerical HUXt dependencies. |
| CME, imagery, and external delivery | `ops_refresh/`, `esa/`, the dashboard builders, JavaScript/CSS modules, and their publication workflows. |
| Validation and maintenance | Tests, model cards, compact provenance, and reproducible builders for the retained models. These prevent a smaller checkout from silently becoming a different forecast system. |

The October 3, 2026 cleanup removes unconnected cross-era/SDO/FlareDB experimental lanes, their large datasets, obsolete diagnostic output/workflows, and bulky offline electron report products. No dashboard, deployed model, live forecast product, or numerical inference code is changed. See [the retention and recovery record](docs/CONSOLIDATION.md).

## Automation

The formal flare issue is requested by `.github/workflows/wxf-daily.yml` at 21:20 UTC with later retry schedules. External guidance refresh/recovery runs separately. CH/HSS, desk products, ESA products, and Solar Flare evidence have their own maintained workflows. Their existing schedules and publication destinations are unchanged by cleanup.

Source is on `main`; published products also use dedicated delivery branches. Do not delete a branch merely because it lacks application source. Workflow publication guards and timestamp/quality gates remain authoritative.

## Verify a checkout

Use the Python versions and pinned environments in `.github/workflows/ci.yml`; flare inference and CH/HSS use separate environments.

```bash
# CH/HSS, particle, and repository-integrity checks (Python 3.12 environment)
python -m pip install -r requirements-chhss.txt
python -m unittest discover -s tests -v
node tests/test_dashboard.cjs

# Flare checks (separate Python 3.13 environment)
python -m pip install -r requirements-runtime-pinned.txt
python -m unittest -v test_sharp_mag_pipeline.py test_solar_monitor_guidance.py \
  test_external_flare_guidance_strict_v4.py test_external_source_audit.py \
  test_publication_guard.py
```

For a local flare issue after installing the frozen model runtime:

```bash
python sharp_mag_pipeline.py forecast --model-dir . \
  --output flare_guidance.json --js-output flare_guidance.js --issue-time cycle
```

`python embed_dashboard_data.py` refreshes embedded flare data; other dashboard builders and publisher-specific checks remain with their modules. Do not replace the canonical HTML with a build from an unrelated historical checkout.

## Methods and limits

WXF guidance remains research/shadow guidance; cleanup is not new scientific validation or operational qualification. Read [MODEL_CARD.md](MODEL_CARD.md), [the dataset inventory](DATASETS.md), [CH/HSS setup](CHHSS_Setup.md), [electron methods](research/electron_fluence/README.md), and [proton methods](research/proton_forecast/README.md).

Additional maintained references cover [solar products](docs/solar-products.md), [Monitor layouts](docs/monitor-layout.md), [particle products](docs/particle-forecasting-options.md), [radiation dose](docs/radiation-dose.md), and [ESA delivery](ESA_SOLAR_DELIVERY.md).

Removing files from the current tree makes source snapshots smaller. It does not remove their old Git objects or rewrite history. The complete pre-cleanup tree remains at commit `97e029c6840308112fc5b8a0b565210f13f0b8d7`.
