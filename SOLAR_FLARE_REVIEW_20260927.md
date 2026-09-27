# Solar Flare / WXF review — 2026-09-27

## Delivered integration

`flare/build_workspace.py` builds the reviewed complete standalone HTML with `flare/workspace.js`. Its base is **SpaceWxOps_Solar_Evidence.html**, SHA256 `db459baa888202fb94b62fdd0e46940c2f684cbd04cf98d6a5ba01f9baa89938`. It intentionally rejects the older repository-root HTML. The standalone review file is delivered separately; no legacy-root replacement is claimed.

Magnetic Connectivity is moved from Models to the product catalog and remains contextual evidence in the flare/coronal-hole workflows. Solar Flare Probability is renamed Solar Flare. Coronal Hole / HSS Outlook is renamed Coronal Hole / HSS; its scientific equations are unchanged.

One region selection drives Flare Guidance, the current-region locator, registered native-pixel HMI/AIA crops, NOAA/HARP identity, vector-field scalar data, event history and connectivity checks. The provider-window bar, workbench-launch button and requested explanatory excerpts are removed. WXF is pinned directly below SWPC on every table page. Empty, expired and future-issued forecasts are hidden; actual zero probabilities are retained. The unvalidated browser-generated consensus is removed. WXF means the published calibrated model, not a browser average. MCSTAT/MCEVOL remain provider forecasts.

## Passive feed and imagery

`Solar Flare Evidence` requests a refresh every four hours. It reads public NOAA, JSOC/NCEI and Helioviewer sources and publishes credential-free products on **flare-live**. It does not replace the existing daily WXF issue workflow or ESA collection. No new secrets are required.

Image IDs, source dimensions, FITS observation times and observer registration are verified. The source images are 4096 x 4096; region crops retain 896 x 896 native pixels. Seven actual four-hourly frames per channel were obtained in the initial verification for HMI continuum, HMI magnetogram and AIA 171. Region centers follow reported NOAA Carrington coordinates with each image's B0/L0 and disk geometry. This is rigid center tracking, not optical-flow tracking or automatic spot-boundary segmentation. Missing registration is rejected. Display-image brightness is not used to derive quantitative magnetic fields.

The generated-data branch retains one current snapshot, with a lease-checked update confined to **flare-live**, to avoid retaining unlimited high-resolution-image history. Source/main history is not rewritten. The complete updated evaluation table remains in every successful snapshot. Seven-day workflow artifacts retain verification material.

## Database and probabilities

The frozen model remains `sharp-mag-20260903-xstruct-history-v3`, with `operational: false`. The original development database has 7,706 region-days through issue date 2026-09-02; that total includes training, calibration and testing, not just fitting. The first verified update added 35 eligible completed-outcome cases: **7,741 total**, issue dates through **2026-09-25**, outcome labels through **2026-09-26**. The new cases contain no M1+/X1+ positives. No new rare-event skill or retraining is claimed.

`flare-live/database.csv.gz` and `database-status.json` contain the update and its provenance. The original CSV, joblib files and coefficients remain untouched. Source coverage is checked before adding completed labels. Revised archives do not reproduce all publication-time/near-real-time revisions; the appended check is retrospective, not a strict as-issued backtest.

WXF's numerical model has 45 engineered predictors: 18 magnetic state parameters, 18 changes, two position terms and seven prior-event-history terms. M1+ and X1+ are separately calibrated; X1+ is constrained below M1+. Full disk combines unique HARP/region components under an independence assumption. It is not independently calibrated and has no explicit unnumbered/farside residual. Missing magnetic coverage uses disclosed fallbacks.

The stored held-out report has 1,467 region-days, 41 M1+ positives and only six X1+ positives. M1+ Brier skill versus training climatology is 32.5% (reported region-bootstrap interval 17.2% to 43.6%). X1+ is 7.6%, with an interval crossing zero (-5.8% to 16.1%). These are existing developmental results, not scores for this new interface. The fitting/calibration X1+ subsets contain only six/seven positives. X-class probability reliability remains poorly constrained.

## Source roles and remaining core work

SIDC and A-EFFort provide published comparison guidance; NOAA/HARP identity, HMI/SHARP observations and Solar Demon/GOES event associations provide evidence. Provider agreement is not multiplied into WXF. Solar Demon estimates remain separate from GOES classes and are restricted to M1+; unique reciprocal region/time matches are required. Magnetic Connectivity supports source association, not intrinsic flare occurrence probability or measured photospheric polarity. CACTus remains CME evidence, not a circular future-flare predictor.

The new evidence stream reconciles duplicate satellite reports, but the root frozen WXF history parser is not silently replaced. Its start-time/class/region deduplication needs consistent training/live revision, including whether a final flare class was actually available at issue. Additional review is needed for QUALITY bit masks (the existing broad integer ceiling is not per-flag interpretation), HARP continuity across prior-day samples, the train/live shared-HARP population difference, and whole-disk/fallback calibration. Additional topology/emergence/EUV predictors require historical availability and incremental-skill validation, not arbitrary current-day weights.

## Validation boundaries

The release includes source-contract unit tests, asset/hash and decoded-dimension tests, captured-output browser integration, and live anonymous Chromium delivery checks. Complete-dashboard tests use captured real provider data in a separate isolated browser document. Neither mode proves access from a restricted workplace network or observational forecast skill. The known baseline Plotly startup warning is unchanged; complete HF/UHF/Global image exports are not regenerated in this pass.

Primary references: Helioviewer API https://api.helioviewer.org/docs/v2/api/index.html ; Solar Demon https://www.sidc.be/solardemon/ ; flare benchmarking https://arxiv.org/abs/1907.02905 and https://arxiv.org/abs/1907.02909 . Exact existing model metadata and metrics are in `sharp_mag_manifest.json` and `sharp_mag_training_report.json`.
