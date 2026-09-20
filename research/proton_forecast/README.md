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

## On-demand analyst workflow

The Models tab presents **WXF Proton Model** with inputs and an explicit Run button at the top. Load an observed flare or enter a historical scenario. Automatic inference reconstructs the pre-peak five-minute grid for that event; manual mode accepts the same channel medians, earlier medians, global flare count and baseline event eligibility. Missing baseline status withholds the affected probability. Observation refreshes neither execute edited inputs nor overwrite the last completed run. Navigating between products retains the draft and run for that browser session. The published first-issuance ledger is unchanged.

The optional >10 MeV peak estimates use the published relations in [Balch (2008), section 2](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2007SW000337), cross-checked visually against [Whitman et al., section 3.20, equations 7–9](https://repository.library.noaa.gov/view/noaa/52048/noaa_52048_DS1.pdf):

- Peak flux in pfu: `10 * alpha * (Xint / 0.00987)^0.82`.
- `alpha = (Xprevious / 0.167)^1.146` when `Xprevious > 0.08 J/m²`; otherwise `alpha = 1`. Unknown previous-flare status or a missing integral for a known previous flare withholds peak flux.
- Flare-peak to proton-peak delay in hours: `9.4 + ((longitudeWest - 78) / 18.1)^2`. This is **not onset delay**, and may extend beyond the probability model's fixed window.

Both estimates are conditional on an SEP event and are screened to C2.4+ and visible-disc coordinates. Integrals are GOES SXR in J/m², from onset through the decay time where flux reaches `(peak + pre-flare background) / 2`, including background in the integral. This corrects the less precise half-maximum wording in the review. No generic event-end or background-subtracted integral is substituted. The WXF probability verification does not validate these additional historical relations, and no synthetic uncertainty interval is attached.

The [NOAA presentation supplied by the user](https://www.spaceweather.gov/sites/default/files/images/u59/05%20Hazel%20Bain%20Official.pdf) confirms the PROTONS inputs and three outputs, and discusses sparse-bin and false-alarm limitations. Reproducing its occurrence probability requires **Balch (1999), Tables 6–8**, including bin boundaries and sparse-sample fallback rules. Those tables are referenced but not reproduced in the 2008 paper; the verification-frequency table is not an inference lookup table. We have not obtained the complete 1999 tables. Consequently radio sweep and optical class are explicitly recorded-only inputs in this release. They do not secretly introduce arbitrary probability multipliers.

Neither user-supplied source specifies high-/mid-latitude aurora probabilities, SSC, post-SSC Ap, PCA, SST dose, >50 MeV peak flux or proton onset predictions. These remain unavailable pending separately sourced or fitted and validated methods. The existing WXF >50 MeV occurrence probability remains functional and independent of the legacy peak relation.

SSC and aurora outputs are omitted from the interface at the user’s request, along with the unused current-Ap input.

## Automatic input preparation (input version 2)

The latest reported C1+ flare is selected automatically; earlier flares from the last 48 hours remain selectable. Peak time, measured peak irradiance (without rounding it back to the class string), rise time, completed integrated irradiance and available source coordinates populate the form. The pre-flare channel medians, trends, global flare count and initial event status load with the event; Run is the only action needed to calculate when required particle history is available. The three probabilities occupy a compact row with tooltips, without a duplicate bar chart.

SWPC XRA records are matched by peak time and class, then joined to optical/radio reports by event number and date. Conflicting locations or event associations stay unknown. As an optional fallback, a unique temporally overlapping [Solar Demon quick-look AIA detection](https://www.sidc.be/solardemon/) within ten minutes of the GOES peak can supply on-disk Stonyhurst coordinates. Its estimated EUV class never replaces the GOES magnitude, and its nearest active region is not treated as a confirmed source region. Off-limb detections, multiple candidates and missing coordinates are flagged; no disk-centre position is invented. Source failures are retained as input warnings and do not prevent loading the GOES flare.

The completed `current_int_xrlong` is accepted only after a valid end time. [SWPC's GOES X-ray product documentation](https://www.spaceweather.gov/products/goes-x-ray-flux) defines that end at the midpoint between peak and pre-flare background, consistent with the published PROTONS integration limit. A still-growing integral is not passed to the peak relation. A positive same-region prior-flare report can load the preceding integral, but absence from a finite or incompletely located catalogue never becomes "No previous flare." Unknown prior status continues to withhold the conditional peak estimate. Optical class and Type II/IV associations remain recorded inputs, not fitted probability predictors.

Untouched drafts follow refreshed inputs; selecting an event, making an edit or running freezes that selection until explicitly reloaded. Editing a peak timestamp clears the previous event association. Editing particle-history values switches to manual mode. The last result records a copy of its inputs and source snapshot timestamp, so later edits cannot rewrite its provenance. Probability predictors still stop before peak; event-eligibility checks use only the three samples preceding the fixed +10-minute target start. Missing eligibility samples now withhold probabilities in the publisher as well as the browser.

This input and interface change does not retrain the model or claim improved forecast skill. The historical probability scores above remain the baseline; the optional peak equations do not share those scores. A fair PROTONS comparison must use matched solar events, identical event definitions and issuance times, consistent GOES calibration, and separately score probability reliability, detection/false alarms, peak-flux error and timing error. Candidate predictors such as integrated SXR, Type II/IV emission, CME speed/width and magnetic connection should be compared through prespecified ablations on time-separated data; the existing held-out years cannot become a repeatedly tuned test set. The screenshot's SSC, aurora, PCA and dose outputs require separately documented models and are not inferred from SEP probability.
