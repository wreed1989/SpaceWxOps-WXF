# WXF regional flare model card

## Current candidate

`sharp-mag-20260903-xstruct-history-v3` is a research/shadow model for next-UTC-day active-region and visible-disk probabilities of at least one M1+ or X1+ flare. It is not an operational replacement for NOAA/SWPC.

The model issues at 21:00 UTC from an 18:00 UTC HMI/SHARP snapshot. Magnetic inference is restricted to active-region centers within 50° of central meridian. Every fresh visible NOAA numbered region is still listed: regions without an accepted SHARP vector receive an explicitly labelled McIntosh or training-climatology coverage fallback.

## Architecture

- M1+ occurrence: regularized, class-balanced logistic regression over 18 scalar SHARP parameters, their 24-hour changes, disk position, and seven strictly pre-issue regional flare-history features. Probabilities are Platt-calibrated.
- X1+ occurrence: a separate, more strongly regularized logistic classifier trained directly on X1+ outcomes using the same magnetic state, 24-hour evolution, disk-position, and strictly causal flare-history evidence. It is calibrated independently from M1+.
- Nested constraint: the final X1+ value is capped at the M1+ probability, enforcing `P(X1+) <= P(M1+)` without forcing X1+ to be a fixed fraction of M1+.
- Full disk: each independent HARP/region probability is included once using `1 - product(1 - p_i)`. Shared multi-region HARPs are displayed for each numbered region but counted once. This is a coverage aggregate, not a separately trained full-disk classifier.

## Training data

- 7,706 quality-controlled SDO/HMI region-days from 2012-10-01 through 2026-09-02.
- 1,770 unique normalized NOAA regions.
- 285 M1+-positive region-days and 19 X1+-positive region-days.
- NOAA/NCEI GOES event labels; positively attributed regions are retained on days that also contain an unattributed major event, while only ambiguous negative controls are removed.
- Multi-region HARPs are excluded from model fitting to prevent one magnetic vector from being duplicated under several labels.

The published table is [datasets/sharp_mag_training_table_v2.csv.gz](datasets/sharp_mag_training_table_v2.csv.gz), with provenance in its adjacent metadata file and repository-wide checksums in [datasets/manifest.json](datasets/manifest.json).

## Untouched chronological holdout

The final block spans 2025-02-08 through 2026-09-02 and contains 1,467 region-days from 340 active regions. Seven-day purge gaps separate training, calibration, and test blocks.

| Target | Positive days | Brier score | Brier skill | AR-bootstrap BSS 95% interval | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|---:|
| M1+ | 41 | 0.01833 | 32.5% | 17.2% to 43.6% | 0.938 | 0.515 |
| X1+ | 6 | 0.00377 | 7.6% | -5.8% to 16.1% | 0.940 | 0.252 |
| X1+ old constant-severity reference | 6 | 0.00387 | 5.2% | -1.8% to 8.5% | 0.979 | 0.413 |

The direct magnetic/history X model reduces Brier score by 2.60% relative to the frozen constant X/M severity method on this holdout. The constant reference still ranks these six events better by ROC/PR-AUC, and the direct model's grouped confidence interval crosses zero. The improvement is therefore a calibration gain, not proof of operational superiority.

## FlareDB use

NJIT FlareDB is used as a positive-event sequence and label-coverage audit, and as a design reference for future HMI/AIA image modeling. It is not appended directly to the classifier: FlareDB selects only M5+ and X events, contains no quiet controls, and overlapping event-centered sequences from one region cannot be treated as independent forecast cases. See [research/flaredb/coverage_audit.json](research/flaredb/coverage_audit.json).

## Known limitations and promotion gates

- Only 19 eligible X-positive region-day cases survive the exact issue time, region attribution, geometry, and quality contract; cases remain clustered by active region, and only six occur in the untouched test block.
- The full-disk WXF value has no unnumbered/farside residual and is not separately calibrated.
- A shared HARP cannot provide truly independent probabilities for two NOAA regions; the UI marks those outputs as shared.
- Coverage fallbacks are not SHARP magnetic predictions.
- Promotion requires prospective shadow verification and paired scoring against archived SWPC, MCSTAT, MCEVOL, climatology, and persistence forecasts on identical windows.

The complete metrics and reliability bins are in [sharp_mag_training_report.json](sharp_mag_training_report.json); standardized coefficients and preprocessing statistics are in [sharp_mag_coefficients.csv](sharp_mag_coefficients.csv).
