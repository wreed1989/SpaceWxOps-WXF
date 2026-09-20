# WXF experimental proton forecast, version 0.1

This is an event-triggered empirical baseline, not a reproduction of the legacy SWPC Proton Prediction Model. It provides probabilities after C1-or-larger flares for a new, sustained proton threshold crossing within a fixed 24-hour window:

- ≥10 MeV reaching ≥10 pfu;
- ≥10 MeV exceeding 40 pfu;
- ≥50 MeV reaching ≥10 pfu.

These are the requested office event thresholds. They are distinct from UMASEP's published thresholds and from a user's configurable observation alerts. Integral pfu means protons cm⁻² s⁻¹ sr⁻¹ above the stated energy, not a differential energy channel. A crossing requires three consecutive five-minute samples. No PCA absorption, dose, aurora probability, flux trajectory or arrival-time range is inferred from these three probabilities.

## Data and causal timing

The acquisition uses the full available overlap from May 2010 through August 2026: 196 monthly NASA ISWA GOES-primary P10/P50 files and 17 NOAA NCEI annual flare files. `input-manifest.json` records the exact URLs, retrieval times and SHA-256 hashes. Sources:

- [NASA ISWA HAPI catalog](https://iswa.ccmc.gsfc.nasa.gov/hapi/catalog), dataset `goesp_part_flux_P5M`.
- [NOAA NCEI GOES multi-satellite flare reports](https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/l2/data/xrsf-l2-flrpt_science/csv/).
- Current inference uses [SWPC flare observations](https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json), [proton observations](https://services.swpc.noaa.gov/json/goes/primary/integral-protons-3-day.json), and [reported event locations](https://services.swpc.noaa.gov/json/edited_events.json).

Predictors are peak X-ray flux, rise time, disk longitude and latitude when reported, pre-peak GOES P10/P50 medians and trends, and the preceding 24-hour C1+ flare count. The live event location is used only when explicitly matched to that flare. Missing coordinates are not assigned a disk-center location. Historical reports can include subsequently finalized measurements or locations; this is a retrospective hindcast, not a replay of historical feed availability.

Features end before the flare peak. The target starts ten minutes after the peak. Both 10 MeV models require the ≥10 pfu event to be inactive at issue time; the 50 MeV model similarly excludes an already active ≥10 pfu event. Future truth needs 95% coverage and no gap longer than 30 minutes. Missing and negative-fill observations never become zero.

Publication runs hourly through the existing science workflow. The UI shows the actual calculation time and fixed target window. A late first calculation is explicitly a reconstruction, not remaining-window risk. `proton-forecast-ledger.json` preserves the first published calculation for later prospective scoring. Subsequent refreshes do not rewrite that first record. Analyst adjustments are local scenarios, not published forecasts.

## Training and verification

Regularized logistic regression (`C=0.1`) uses training-period medians, scaling and missingness indicators. A separate logistic calibration (`C=1`) preserves observed prevalence; there is no class balancing. The two 10 MeV probabilities are ordered so the higher-threshold event cannot be more likely.

Training: 2010–2014. Calibration: 2015–2021. Held-out test: January 15, 2022 through August 2026. A 28-day split-boundary embargo and exclusion of active regions shared across partitions reduce leakage. Test years do not choose coefficients, calibration or the displayed 20% decision cutoff. Overlapping flare windows can share a single SEP event: counts are forecast windows, not independent events. Brier skill compares with training climatology, not persistence or UMASEP. Its interval uses 1,000 bootstrap resamples of 14-day calendar blocks.

| Target | Test / positive windows | Brier skill (95% interval) | Detection at 20% | False-alarm ratio |
|---|---:|---:|---:|---:|
| P10 ≥10 | 13,745 / 450 | 7.0% (3.4–10.4%) | 10.2% | 64.1% |
| P10 >40 | 13,745 / 207 | 3.4% (1.5–5.5%) | 1.4% | 25.0% |
| P50 ≥10 | 14,189 / 67 | 3.5% (−1.7–5.7%) | 0% | No yes forecasts |

**The baseline has low detection at that cutoff. P50 skill is inconclusive.** These results do not establish operational warning performance. Full probability reliability bins, AUC, average precision and error counts are in `evaluation.json`; `hindcast.csv.gz` contains every scored test-window forecast. STIS, CME geometry, radio bursts, integrated X-ray flux, and shock context are not fitted predictors yet. Adding them requires time-stamped historical inputs and a new prospective or untouched evaluation period, not tuning on these test years.

## Reproduction

Use Python with NumPy, pandas, requests and scikit-learn. From the repository root:

```sh
python -m research.proton_forecast.acquire --cache work/proton-history
python -m research.proton_forecast.train --cache work/proton-history
python -m research.proton_forecast.refresh
python -m unittest discover -s tests -v
node tests/test_dashboard.cjs
```

Keep the cached source hashes from the manifest: finalized archive files can change. The acquisition's stop date is fixed for this version. The trained model and browser inference fixture are committed; inference does not require scikit-learn. The dashboard test suite checks that its embedded model and JavaScript match these source files.
