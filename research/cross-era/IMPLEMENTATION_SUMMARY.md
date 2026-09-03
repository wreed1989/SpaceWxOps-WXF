# WXF cross-era expansion implementation

## Incorporated into SpaceWxOps 3.8

The solar-flare workspace now exposes a cross-era dataset expansion beneath
the reliability audit. It includes:

- A coverage timeline from the McIntosh archive through HMI/AIA.
- Separate `WXF-HMI`, `WXF Cross-Era`, and `WXF Historical Prior` branches.
- A source registry that distinguishes materialized data, registered adapters,
  phase-two archives, modern validation enrichment, and benchmark-only data.
- An instrument-safe feature contract prohibiting unharmonized raw-pixel
  pooling and HMI-only vector quantities in the historical branch.
- A frozen cycle split: cycles 21–23 development, cycle 24 calibration and
  threshold selection, and cycle 25-to-date final testing.
- Required leave-one-instrument-out, overlap-era, disk-position, solar-phase,
  active-region-grouped and event-grouped evaluation.
- A trained 29-input daily common-feature baseline using merged SMARP–SHARP
  magnetic parameters and region-attributed NOAA/NCEI GOES labels.

## Data materialized in this build

| Evidence | Audited result |
|---|---:|
| NOAA/SWPC cycle-23 daily SRS files | 4,720 / 4,749 (99.39%) |
| Parsed SRS region-days | 21,653 |
| Normalized NOAA region identifiers | 3,062 |
| NOAA/NCEI GOES XRS events, 1996–2008 | 23,416 |
| M1+ events | 1,569 |
| Region-attributed M1+ events | 1,256 |
| X1+ events | 126 |
| Region-attributed X1+ events | 111 |
| NADC workbook records | 2,951 |
| Missing values in NADC workbook | 0 |
| Merged SMARP–SHARP source rows | 4,653,499 |
| MDI / HMI source rows | 375,621 / 4,277,878 |
| Daily active-region cases | 40,637 |
| Cycle-23 development cases | 17,918 |
| Cycle-24 calibration cases | 12,316 |
| Cycle-25 untouched test cases | 10,403 |

## Cycle-25 test

| Target | Positive region-days | BSS | 95% AR bootstrap BSS | ROC-AUC | PR-AUC | ECE | TSS | FAR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1+ | 567 | 28.2% | 22.7% to 34.1% | 0.920 | 0.491 | 0.44 pp | 0.683 | 77.6% |
| X1+ | 51 | 1.5% | -18.1% to 14.5% | 0.954 | 0.135 | 0.29 pp | 0.730 | 95.8% |

The NADC landing page advertises 2,849 active regions, but its downloaded
workbook currently contains 2,951 unique Carrington-rotation/label records.
The +102 discrepancy is retained as a visible provenance warning.

## Deliberately not claimed

This build does not claim operational reliability. The merged MDI/SMARP →
HMI/SHARP baseline is trained, but cycle and instrument are partly confounded.
GONG transfer residuals and KPVT historical magnetic features are registered
but not yet materialized; matched SWPC probabilities are unavailable over the
full interval. The live WXF probabilities are unchanged. X1+ explicitly fails
promotion because its grouped Brier-skill interval crosses zero.
