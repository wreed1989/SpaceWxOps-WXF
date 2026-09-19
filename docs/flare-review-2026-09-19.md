# Flare forecasting review — 19 September 2026

The review found a delivery failure, a reliability-bin bookkeeping error, and misleading display claims. It did not find evidence warranting an automatic replacement of the frozen classifiers.

## Corrected

- The daily flare workflow's SHARP fallback removed SWPC while its publication gate required a SWPC member. Runs on 18–19 September consequently failed; the external-only updater then rejected the expired envelope. The maintained enrichment adapter now refreshes SWPC independently. When SWPC itself fails, its source entry explicitly contains null probabilities and an error; independent providers can still publish. Missing probabilities are not zero.
- Retained magnetic guidance keeps its original valid window, including across repeated failed cycles. Expired members have visible labels and the header reports the publication failure. The downloadable HTML now embeds the latest published flare payload instead of a permanently dated fallback.
- Reliability-bin means and counts now use exactly the same membership. Ties no longer produce misleading bin weights. Both published Brier scores were reproduced, and the published dataset has zero NOAA-region overlap across training, calibration and test.
- Reliability diagrams scale to all actual bin frequencies; X-class frequencies previously clipped at 2% are visible. The summary shows event counts, Brier skill and its active-region-bootstrap 95% interval. Details explain the quantities without presenting them as percent accuracy.
- The forecast target is the next UTC calendar day, not the 24 hours immediately after issue. The full-disk product formula assumes independent components and has not been independently calibrated. Regional holdout scores do not validate that aggregate, morphology fallbacks or the design-weighted browser consensus.

## What the historical test supports

The 2025-02-08 through 2026-09-02 chronological test contains 1,467 region-days: 41 M1+ and 6 X1+ positives. M1+ Brier skill relative to training climatology is 32.5%, with a grouped 95% interval of 17.2–43.6%. X1+ is 7.6%, with an interval of −5.8–16.1%; additional skill is uncertain. These are tests of the training recipe. The deployed estimators were subsequently refit to all rows, and the holdout has already been inspected during development. A new model requires separately reserved chronological evidence.

Reproduction: `python scripts/audit_flare_verification.py` in the pinned flare runtime. This verifies the dataset checksum, split overlap and score reproduction, then updates reliability bins and audit metadata. It does not save new model weights.

## Next scientific improvements

1. Preserve as-issued NRT inputs and receipt times, match the exact valid window to outcomes, and compare on the same cases with SWPC, persistence and climatology. A definitive retrospectively corrected input is not necessarily what was available live.
2. Expand chronological, active-region-separated evaluation across solar-cycle activity levels. Report calibrated probabilities, event counts, availability and grouped uncertainty rather than ranking metrics alone.
3. Evaluate full-disk calibration separately, including unnumbered-source coverage and fallback behavior. Do not infer full-disk reliability from regional skill.
4. Prioritize sufficient X-class examples and independently evaluated recalibration before adding a more complex classifier. The current six positive holdout cases cannot support a confident improvement claim.

Primary references: [NOAA solar probabilities](https://services.swpc.noaa.gov/text/3-day-solar-geomag-predictions.txt), [All-Clear forecast-method comparison](https://arxiv.org/abs/1608.06319), [operational Met Office verification](https://arxiv.org/abs/1703.06754), and [McIntosh evolution and cycle-dependent calibration](https://arxiv.org/abs/1805.00919).

## Live-source check

At 22:25 UTC on 19 September, the latest accepted SHARP candidate was 18 September 09:36 UTC, 32.4 hours behind the nominal input target. The eight-hour quality gate correctly rejected it. This is an upstream availability limitation, not grounds to relax scientific quality. Independently, WXF's electron publication was withheld for incomplete recent particle coverage. The feed dropdown now exposes failures instead of a hard-coded healthy status.
