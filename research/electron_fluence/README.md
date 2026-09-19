# WXF experimental rolling electron fluence — model card

**WXF-EF-0.1 predicts hourly >2 MeV electron flux at GOES-19's GEO location for the next 24 hours, then integrates each path into rolling preceding-24-hour fluence.** It is an experimental statistical forecast, not a calibrated spacecraft-failure forecast. It does not replace the separate SWPC REFM UTC-day product.

## Inputs and method

The model uses NASA CCMC/ISWA's archive of NOAA operational primary electron/proton and real-time solar-wind feeds. The coherent acquisition interval begins 7 April 2025 and extends through the current date; no unrelated 2024 event collection is required. Only samples explicitly identified as **GOES-19 electrons** are admitted. Earlier GOES-16 samples and later primary-spacecraft substitutions are rejected rather than silently cross-calibrated.

1. Five-minute >2 MeV electron boxcar averages become arithmetic hourly means, labelled at the completed hour's end. A complete hour requires all 12 accepted bins. Unknown or ≥10 pfu >10 MeV proton flux invalidates coincident electron bins as a conservative contamination screen. This screen does not prove the absence of every instrument artifact.
2. The preceding **seven days estimate the diurnal shape only**. A robust regression fits 24- and 12-hour harmonics with separate daily amplitude terms. Daily level changes cannot simply masquerade as the diurnal cycle. Every fit uses data available by its forecast origin.
3. A multi-output regression forest predicts changes from that diurnal reference for hours 1–24. Predictors include the last 1–72 hours of electron amplitude, variability and changes, plus lagged solar-wind speed, density, Bt, Bz, southward-field strength, proton dynamic pressure and rectified VBs coupling. These empirical drivers represent conditions associated with losses and delayed enhancement. They do not identify a specific physical loss mechanism.
4. Solar-wind statistics use completed hourly data and an additional hour of latency. At least 45 valid minute samples per hour are required. Pressure and rectified coupling are calculated at one-minute cadence **before** hourly averaging. Pressure excludes the alpha contribution. These are L1 measurements, not time-shifted OMNI observations; no future bow-shock values are supplied to the model.
5. The fixed forest has 192 trees, minimum leaf size 12, maximum depth 14 and random seed 1989. Targets are log(1 + flux) residuals from the recent diurnal reference. Back-transformed flux has a hard zero floor. No office percentage-growth method is present.
6. Whole, once-daily, held-out 24-hour error vectors generate **79 coherent flux paths**. Each is integrated separately; only then are the 5th, 50th and 95th percentiles calculated. Integrating pointwise flux quantiles would give the wrong fluence range because it loses temporal dependence.

At lead h, the integration retains the final 24−h observed hours and adds the first h forecast hours. Hourly means are multiplied by 3,600 seconds. Units are **electrons cm⁻² sr⁻¹** for fluence, and **electrons cm⁻² s⁻¹ sr⁻¹** for flux. No fixed UTC-day reset occurs. The initial rolling total, and any future window containing a missing observed hour, are unavailable. Later windows become available when that gap ages out; missing exposure is never replaced by zero. A gap in the last three completed hours withholds the forecast.

## Retrospective evaluation

The split dates and estimator settings were chosen before the first evaluation. Implementation corrections to missing-lag handling and minute-level pressure/coupling aggregation followed initial result inspection. Therefore this is a **development holdout**, not a pristine prospective validation. The frozen artifact has not been refit on calibration or test outcomes.

| Partition | Period | Eligible origins |
|---|---|---:|
| Training | April 2025–February 2026 | 1,395 |
| Error-range calibration | March–May 2026 | 590; 79 nonoverlapping 24-hour error paths |
| Evaluation | June–August 2026 | 456 |

Origins are sampled every three hours, with a 24-hour target embargo at partition boundaries. Test windows overlap and storm episodes span days; **456 origins are not 456 independent events**. Quality exclusions also mean results do not represent all hours or strong proton events. Full coverage and rejection counts are in [evaluation.json](evaluation.json).

| Forecast at +24 h | Mean absolute rolling-fluence error | RMS log error |
|---|---:|---:|
| WXF with solar-wind drivers | 1.673 × 10⁷ | 0.382 |
| Same estimator, electron predictors only | 1.763 × 10⁷ | 0.412 |
| Diurnal persistence | 1.810 × 10⁷ | 0.450 |
| Constant latest-hour flux | 2.089 × 10⁷ | 0.504 |

WXF's mean absolute error was **7.6% lower than diurnal persistence** in this cohort. This is a preliminary point estimate, not proof of improvement across all conditions. Adding solar-wind predictors reduced error by 5.1% versus the electron-only ablation. The nominal 90% empirical range covered **94.7%** of +24-hour outcomes. Its errors are pooled across regimes, so conditional coverage during a particular storm is not established. The range is not a distribution-free or guaranteed confidence interval.

At the office's original **1.1 × 10⁸ moderate** and **4.8 × 10⁸ severe** exposure criteria, the once-daily evaluation sample contained **7 moderate and 0 severe exceedances across 67 sampled days**. Adjacent days may belong to one episode. Severe-event skill is unestablished; threshold-exceedance probabilities are deliberately not displayed. Editing dashboard thresholds changes the plot styling, not these historical validation counts. The criteria screen possible internal-charging exposure; material shielding, orbit, design and charging time constants determine spacecraft response.

## What is and is not forecast

Storms can cause electron dropouts, while sustained high-speed wind can support later recovery and enhancement. The model learns lagged associations rather than imposing an automatic HSS or storm reduction. It **does not yet explicitly ingest future CME/HSS arrival predictions, predicted Kp or future Bz**. A new arrival unseen in recent L1 observations can invalidate the outlook. Forecasting future drivers needs archived **as-issued** forecasts; later observed Kp or solar wind cannot stand in for those forecasts without leaking future information.

The current SWPC three-day bulletin is displayed separately and recorded with each issue for development of a future forecast-conditioned model. It does not alter v0.1's values. REFM forecasts daily totals; they are not relabelled rolling totals or treated as hourly truth. No fair head-to-head REFM verification is claimed without aligned windows and historical issue records.

This product covers local GEO energetic electrons, not spatial belt geometry, LEO drag, low-energy surface charging, proton SEUs or orbit-specific dose. At high proton flux it may be unavailable precisely during a disturbed period. Out-of-training-range inputs are flagged. Input receipt times/revisions are not preserved in historical HAPI responses, so conservative delays reduce but do not eliminate operational-availability uncertainty.

## Operation and reproducibility

The Electron Forecast card defaults to **WXF · Rolling 24 h · Experimental** and retains **SWPC REFM · UTC day** in its selector. Flux and fluence share one resizable plot. Alert Settings → Electron Fluence controls rolling-fluence threshold styling; flux uses its own physical units and no fluence bands. Data older than two hours are labelled stale. Downloads embed a dated snapshot and fetch the newest hourly publication.

The existing hourly CH/HSS publication workflow also issues this frozen model. New forecasts and the contemporaneous SWPC bulletin are appended without overwriting older issues to `chhss-data/electron-forecast-history.jsonl`. Full input evidence is kept in the run artifact. Lead times are measured from the displayed data cutoff, not from file retrieval; future verification must require each valid time to follow the original issue time. This begins forward verification; there is no automatic retraining or assertion that forward validation has already passed.

```sh
python -m venv .venv-electron
.venv-electron/bin/pip install -r research/electron_fluence/requirements.txt
.venv-electron/bin/python research/electron_fluence/acquire.py --cache .electron-cache --start 2025-04-07 --stop 2026-09-20
.venv-electron/bin/python research/electron_fluence/model.py --cache .electron-cache --output work/electron-reproduction --fit
.venv-electron/bin/python -m unittest discover -s research/electron_fluence -p 'test_*.py' -v
.venv-electron/bin/python research/electron_fluence/refresh.py --cache .electron-current --output chhss-data/electron-fluence.json --evidence work/electron-evidence
node research/electron_fluence/test_dashboard.cjs
```

`--stop` is exclusive. An unfinished acquisition interval is refreshed rather than permanently cached. [input-manifest.json](input-manifest.json) records exact URLs, retrieval dates and hashes; archives may subsequently be revised. [model-manifest.json](model-manifest.json) records the frozen model checksum, training-code checksum and runtime. Runtime inference verifies the model checksum and loads numeric NPZ arrays with `allow_pickle=False`; scikit-learn is needed only for training. The numeric export matched the original estimator on 200 predictor vectors to floating-point precision. `dashboard.js` is mirrored into the standalone canonical HTML, with an equality test preventing drift.

## Scientific sources and checks

- [NOAA GOES electron product](https://www.swpc.noaa.gov/products/goes-electron-flux): local-time variation and energetic-proton contamination context.
- [NOAA MPS-HI L2 processing README](https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/goes16/l2/docs/GOES-R_SEISS_L2_MPS-HI.ReadMe.pdf): averaged-flux timing, telescope identity and quality information. On 17 September 2026, all 287 overlapping ISWA/operational electron bins matched exactly. The GOES-19 NCEI science-file telescope-4 integral channel also matched the operational feed. Aggregate one-second DQF counts were not mistaken for invalid five-minute flags.
- [NASA CCMC particle archive metadata](https://iswa.ccmc.gsfc.nasa.gov/hapi/info?id=goesp_part_flux_P5M), [solar-wind plasma](https://iswa.ccmc.gsfc.nasa.gov/hapi/info?id=swpc_rtsw_plasma_P1M), [magnetic field](https://iswa.ccmc.gsfc.nasa.gov/hapi/info?id=swpc_rtsw_mag_P1M).
- [Qian et al., hourly electron-flux forecasting](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2018SW002078): precedent for separating diurnal structure and evolving flux with solar-wind/geomagnetic information; WXF uses a different estimator and does not inherit that paper's skill scores.
- [NASA Van Allen Probes findings](https://www.nasa.gov/missions/van-allen-probes/nasas-van-allen-probes-revolutionize-view-of-radiation-belts/): storms can both remove and enhance radiation-belt electrons.
- [SWPC REFM description](https://www.swpc.noaa.gov/products/relativistic-electron-forecast-model): separate daily geosynchronous fluence guidance and model limitations.
