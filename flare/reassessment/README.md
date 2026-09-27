# WXF historical reassessment and Solar Flare UI

Review date: 2026-09-27 UTC. This release does not replace the live WXF coefficients.

## The user's concern was justified

The major flares were in the catalog, but the historical magnetic-data selection excluded most of them. The six X-positive days in the old test were not a count of all X flares available during this cycle.

Fresh NOAA/NCEI 2023–2025 annual composites contain 10,463 all-class flare records: 1,579 M-class events and 83 X-class events (1,662 cumulative M1+). These M/X totals agree with the existing major-event catalog. There was no general X-class string-parsing failure.

| Year | M-class events | X-class events | Old retained M1+ region-days | Old retained X1+ region-days |
|---|---:|---:|---:|---:|
| 2023 | 357 | 13 | 49 | 0 |
| 2024 | 884 | 52 | 67 | 7 |
| 2025 | 338 | 18 | 23 | 1 |

M-class excludes X; M1+ includes X. Multiple events can produce one positive forecast day. Of 83 X events, 81 have NOAA identities and occupy 72 distinct peak-date region-days. Only eight X-positive forecast days, representing ten individual X events, survived in the old training table. The model labels by onset-date windows; peak-date and onset-date aggregation are not interchangeable around midnight.

## Event-by-event selection trace

These are mutually exclusive first-failure reasons in the original selection order. A shared patch may also fail a later cut.

| Outcome | M1+ events | X1+ events |
|---|---:|---:|
| Retained region-day | 247 | 10 |
| Shared HARP excluded | 706 | 42 |
| No contemporaneous NOAA mapping | 332 | 21 |
| Outside ±50° longitude | 166 | 4 |
| No nominal-time NRT observations | 76 | 4 |
| No reported NOAA region | 134 | 2 |
| HARP merge flag | 1 | 0 |
| Total | 1,662 | 83 |

There is no unexplained remainder. Every event and exclusion is in the delivered event_attrition_traced.csv.

HARP 9997 represented AR13664 alone through May 5, 2024. On May 6 it became a shared AR13664/13668 patch. The old single-region rule excluded it despite available central-disk measurements. Its unsigned flux increased from about 4.21e22 Mx on May 5 to 1.12e23 Mx on May 9. Changing membership/masks mean this is not by itself a stable-footprint emergence estimate.

## Frozen recipe reproduction

The original chronological model recipe was reconstructed from its frozen inputs. Both Brier scores reproduced within 3e-11.

| Metric | M1+ | X1+ |
|---|---:|---:|
| Test region-days | 1,467 | 1,467 |
| Positive days | 41 | 6 |
| Brier score | 0.0183339122 | 0.0037704430 |
| Brier skill vs training frequency | +32.5% | +7.6% |
| 2,000-region bootstrap 95% interval | +15.4% to +44.9% | -6.3% to +16.2% |
| ROC AUC | 0.938 | 0.940 |
| Average precision | 0.515 | 0.252 |

Test period: 2025-02-08 through 2026-09-02, 340 NOAA groups. Fit/calibration/test sizes are 4,778/1,404/1,467 with seven-day gaps and zero NOAA-group overlap.

The production classifiers were later refit on the entire development table. These scores evaluate the recipe, not independent performance of those final fitted objects. They do not validate fallbacks or the independent-component full-disk aggregate. The live model remains sharp-mag-20260903-xstruct-history-v3 with operational=false.

## Rebuilt shared-patch experiment

Real captures: 159 monthly NRT SHARP files, 14 annual composite flare files, 35,239 raw magnetic snapshots, 8,852 curated patch-days. A definitive May-2024 comparison file is not pooled with NRT training data.

Each HARP/day is retained once. The target is a flare starting during the next UTC calendar day from any NOAA member mapped at issue. Issue time is 21 UTC; nominal 18 TAI measurements are converted correctly within the supported 2012–2025 scope.

Ambiguous simultaneous mappings of a NOAA source to multiple patches are excluded rather than duplicated. Previous measurements require consistent HARP identity, membership and cadence and are generated before label censoring. Final flare classes enter history only after peak/end precede issue; publication latency is not fully reconstructed. Negatives on days with unassigned M1+ events are censored, changing the evaluated population.

| Partition | Years | Patch-days | M1+ | X1+ | Connected groups |
|---|---|---:|---:|---:|---:|
| Fit | 2012–2019 | 3,313 | 135 | 9 | 676 |
| Calibrate | 2020–2022 | 1,672 | 60 | 2 | 305 |
| Evaluate | 2023–2025 | 3,833 | 369 | 33 | 677 |

Seven-day gaps and connected NOAA/HARP purging give zero group overlap. Model forms and regularization were fixed, not searched on these evaluation cases. However, 2023–2025 motivated the audit, so this is not a preregistered untouched final test.

| Predictors, same evaluation sample | M1+ Brier skill | X1+ Brier skill |
|---|---:|---:|
| History | 29.5% | 1.2% |
| Magnetic state | 26.6% | 2.7% |
| State + daily evolution | 26.7% | 1.8% |
| Combined | 34.0% | 2.6% |

Combined M1+: Brier 0.05944255; reference 0.09008402; grouped BSS95 27.8–39.4%; ROC AUC 0.912; AP 0.567. Combined X1+: Brier about 0.00834; grouped BSS95 1.4–3.7%; ROC AUC about 0.932; AP about 0.122. A separate 27-day-block resampling gives BSS95 28.0–39.1% and 1.3–3.8%, respectively.

The combined predictors improve M1+ Brier error over history alone by 0.004109 (paired group-bootstrap95 0.001660–0.006832). The daily-evolution addition versus magnetic state alone gives only 0.000077 (interval -0.000442–0.000576), so it does not establish an additional M1+ gain. It worsens X probability error here. This is not evidence that physical evolution is unimportant; daily scalars and changing masks are limited representations.

The X calibration split contains only two positives. Its 3–10% probability bin averages roughly 4–5%, while approximately 24% actually flare. At a fixed 20% reporting cutoff there are no X alarms and all 33 positives are missed. High ranking ability is not reliable probability calibration. Bootstrap intervals condition on fitted coefficients and this inspected experiment; they omit fitting/calibration/model-selection uncertainty.

The old Brier score and new Brier score are not directly comparable because populations, periods and event rates differ. Only the matched-sample predictor comparisons support incremental-gain statements here. Brier skill is a reduction in probability error relative to training climatology, not percent correct.

## Scientific interpretation

SHARP supplies quantitative magnetic flux, gradients, currents, helicity, shear, energy proxies and extent. The 45-feature experiment retains state, causal daily changes, position and prior flare history. Signed photospheric fields, Hale complexity and PFSS heliospheric polarity are distinct; no single sign represents an entire bipolar region.

Supported feature-development directions include stable-footprint vector tracking, polarity-inversion-line geometry/shear, multiepoch emergence/cancellation, McIntosh/Hale evolution and causal event sequences. These need historical reconstruction and incremental tests, not hand-assigned multipliers. Solar Demon strengthens prior-event identification; a detection after issue is not a predictor for that same flare. Magnetic Connectivity remains source-association context.

Primary references:
- Bobra and Couvidat 2015: https://arxiv.org/abs/1411.1405
- McCloskey et al. 2018: https://arxiv.org/abs/1805.00919
- Liu et al. 2026: https://doi.org/10.1029/2025SW004687
- Leka et al. 2019: https://arxiv.org/abs/1907.02905
- NOAA source: https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/l2/data/xrsf-l2-flrpt_science/csv/

Their methods motivate research; their scores are not transferred to WXF.

## UI and release

The Solar Flare workspace now uses a compact region rail, persistent guidance column and Overview/Magnetic Evolution/Event History/Verification tabs. Verification separates archive coverage, frozen recipe and the shared-patch experiment. Native imagery, frame controls and source associations remain coordinated. SWPC remains first and WXF second; genuine zeros remain visible and empty providers stay hidden.

Optical Class and Radio Sweep are now under SEP Flare Inputs, not Additional Observations. Their existing data handling and fitted equations are unchanged. Product names are Coronal Hole | HSS and SEP | Protons. The changed HTML has 63/69 original script blocks byte-identical, with one non-executable audit block added; forecast engines/exports are preserved.

The full review HTML is delivered separately as SpaceWxOps_Solar_Flare_Refined.html. The old repository-root HTML is not replaced. This directory supplies the guarded builder and sources. No live fitted coefficients are promoted by this release.

Build from the exact previous attachment (SHA256 c0a6ba01badcf866615da4ad9c8fd832605e9220769ef5ad7adc51d58f54d4a0):

```sh
python flare/reassessment/build_workspace.py SpaceWxOps_Solar_Flare.html SpaceWxOps_Solar_Flare_Refined.html --audit reassessment.json
```

The supplied evidence bundle contains reassessment.json, complete raw captures, frozen-input audit, exclusions, predictions, unit tests, browser tests and screenshots. No credential is required to rebuild the UI or run the analysis on supplied records.

Raw source-capture runs: 36312308127 and 36312641912, both successful. Re-run captures when their seven-day workflow artifacts expire, or use the delivered raw ZIPs.

```sh
python flare/reassessment/reassess_history.py --raw history-capture history-expansion --out audit/patch
WXF_AUDIT_OUTPUT="$PWD/audit/patch" python -m unittest discover -s flare/reassessment -p 'test_*.py' -v
```

Numerical environment: Python 3.13.5, NumPy 2.3.5, pandas 2.2.3, SciPy 1.17.0, scikit-learn 1.8.0. Dataset SHA256 b3499f73d17643033e3c3e86d85f72e2f5d4831c24ebd6b54067a440d536593c; predictions SHA256 123d7088109a20aca74c6951a3245d0374c97dcebb59b1276dc5b303b6e82671.

Software checks are distinct from historical forecast verification. Complete-dashboard checks used captured real responses and explicit failure fixtures, not a new workplace-network test. Full HF/UHF/Global exports were not regenerated. The pre-existing Plotly startup redraw warning remains documented.
