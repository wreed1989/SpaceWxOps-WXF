# WXF Dataset v2 implementation summary

## Delivered

The locally supplied FHNW-i4DS `SDOBenchmark-data-full.zip` archive is now an independent,
auditable WXF research lane.  It is not mixed into the current live SHARP
probability or the unvalidated browser consensus.

The build produced:

- A case manifest with explicit 12-hour input and 24-hour verification windows.
- NOAA active-region identity and a zero-overlap train/test check.
- M1+/X1+ labels derived from the benchmark's continuous peak-flux target.
- Image-availability and flagged-frame accounting.
- 48-hour within-region positive episode proxies so repeated windows are not
  presented as independent flares.
- A 292-feature temporal image matrix using four HMI magnetogram, HMI
  continuum, AIA 131, and AIA 193 observations per case.
- PIL proxies, low-order Zernike descriptors, sunspot contrast, coronal image
  statistics, missingness indicators, and 12-hour changes.
- A region-balanced shared log-peak-flux ridge model with separate Platt maps
  for M1+ and X1+ and the physical constraint `P(X1+) <= P(M1+)`.
- Case-level untouched-test predictions, coefficients, calibration bins,
  TSS/HSS/POD/FAR, and 500-draw active-region bootstrap intervals.

## Dataset audit

| Item | Result |
|---|---:|
| Cases | 9,222 |
| NOAA active regions | 1,182 |
| JPEG images | 364,910 |
| Complete 40-image cases | 8,310 |
| Cases with missing images | 912 |
| Train/test active-region overlap | 0 |
| M1+ windows | 690 |
| M1+ 48-hour region episode proxies | 165 |
| X1+ windows | 60 |
| X1+ 48-hour region episode proxies | 23 |

The episode values are clustering proxies, not catalog event counts.  Exact
GOES event IDs remain a required future join.

## Untouched supplied test

| Target | Positive windows | Episode proxies | BSS | AR-bootstrap BSS 95% CI | ROC-AUC | PR-AUC | ECE | TSS | FAR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M1+ | 176 | 30 | 29.2% | 12.5% to 40.3% | 0.852 | 0.598 | 8.64 pp | 0.505 | 63.5% |
| X1+ | 25 | 6 | 3.8% | -4.4% to 8.6% | 0.773 | 0.118 | 1.99 pp | 0.320 | 92.0% |

M1+ provides useful ranking and positive Brier skill, but the test prevalence
is much higher than development and the reliability curve shows systematic
underforecasting.  X1+ remains unreliable: its BSS interval includes zero and
the 25 windows represent only about six region-level episode proxies.

## How the supplied methods were used

- **SDOBenchmark/Kaggle:** four-frame case definition, active-region grouping,
  continuous peak-flux target, and missing-image handling.
- **Raboonik et al. / ApJ:** rotation-invariant low-order Zernike descriptors
  from magnetograms.
- **Jonas et al.:** joint photospheric and coronal image evidence with a shared
  peak-flux target.
- **FlareNet:** reusable, cached image-to-feature/model pipeline; the obsolete
  Python 2/TensorFlow stack was not imported.
- **FLARECAST:** verification vocabulary and the requirement to publish both
  probabilistic and threshold scores.

## Promotion gates still blocked

1. Join exact GOES flare event IDs and audit every unmatched M/X event.
2. Build a genuinely future, chronological Solar Cycle 25 test.
3. Archive SWPC probabilities for identical issue and verification windows.
4. Compare WXF, SWPC, MCSTAT, MCEVOL, climatology, and persistence on the same
   cases with paired active-region/event bootstrap intervals.
5. Replace JPEG PIL proxies with definitive vector-field SHARP CEA features for
   any production candidate.
6. Run a prospective shadow forecast before connecting this model to the live
   forecast table.

Until those gates pass, the wall labels this model **trained, retrospective,
research only** and does not use it in the operational probability.
