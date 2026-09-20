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

## Verification database and historical test cases

`database.py` creates a portable SQLite database from the complete acquired May 2010–August 2026 GOES-primary particle archive and 2010–2026 NCEI flare files. It verifies all 213 source hashes and the frozen feature-table hash before import, independently rebuilds each target from the five-minute observations, and refuses to publish a database if any label disagrees. Missing/fill observations remain SQL NULL. Source file, model, feature, and partition provenance are retained.

The initial database contains **1,715,903 particle records, 43,926 flare reports, and 28,868 forecast cases**. There are **14,379 held-out cases** before target-specific exclusions. Training, calibration, embargo and crossing-region exclusions retain the original model's split. The SQLite file is a generated deliverable, not a large binary committed to Git. Rebuild or score it with:

```sh
python -m research.proton_forecast.database --cache /path/to/proton-history --database /path/to/WXF_Proton_Verification.sqlite --output /path/to/reports
# Subsequent scoring needs only the database and model:
python -m research.proton_forecast.database --database /path/to/WXF_Proton_Verification.sqlite --output /path/to/reports
# A compatible new model gets its own hash, predictions and evaluation row:
python -m research.proton_forecast.database --database /path/to/WXF_Proton_Verification.sqlite --model /path/to/candidate.json --output /path/to/candidate-reports
python -m research.proton_forecast.test_cases --database /path/to/WXF_Proton_Verification.sqlite
```

No fitting or cutoff selection occurs in these commands. `verification.json` is the reproducible scoring output embedded in the dashboard. In addition to the concise UI table, it includes confusion counts, false-positive rate (distinct from false-alarm ratio), precision, CSI, HSS, ROC AUC, average precision, reliability bins, per-year scores, and 14-day block intervals. A separately reported subset applies the current live pre-flare coverage gate; 33 otherwise scorable test windows per target fail that stricter input requirement. Frozen baseline statistics are preserved for comparison. Undefined ratios stay null; in particular, no issued ≥50 MeV yes forecasts means FAR is undefined, not zero.

The **Case** selector in WXF Proton Model contains three historical examples: an M2.9 crossing window on 31 May 2025, an X2.4 non-event on 24 April 2026, and an M3.6 declining-event window on 25 February 2025. The February example had substantial pre-flare activity but no in-window crossing; it is explicitly labelled as a recent event. The earlier November example was replaced because its preceding activity made it a confusing example of a fresh crossing. They are a subset of the existing held-out database, not new samples appended to the score. Selection fills the actual archived inputs, and Run reveals the archived observations and recorded window outcomes. The global alerts retain current conditions; a visible historical-test label prevents confusing the two. Returning to Live restores current input selection. Edited examples are labelled scenarios and cannot rewrite the recorded outcome or aggregate verification.

`test-cases.json` includes archived observations, complete pre-flare history, source URLs/hashes, expected frozen-model probabilities and quality-screened truth. The Node regression suite runs each through the real browser inference code and checks probability agreement with SQLite to 1e-10. The Python tests cover strict thresholds, unknown baselines, truth gaps, tied-probability metrics, null ratios, time-block intervals, checksum failures, and preserving multiple model versions. Dataset scoring reproduces the original held-out statistics; it does not establish PROTONS parity, forecast peak/timing skill, or prospective operational performance.

## Plot timing, preceding-event context and scoring cutoffs

The default plot starts at the selected flare peak and ends 24 hours after the forecast start (peak +10 minutes). A cyan divider marks the forecast start. **Show preceding 24 hours** adds the earlier observations and an orange flare-peak divider. Historical outcomes remain hidden until Run. The plot follows the last completed run until another run replaces it. Pre-flare level/trend predictors are retained even when that history is hidden.

`episode.py` records sustained ≥10 pfu activity during the 288 five-minute slots strictly before peak. A recent event needs three consecutive crossing samples. A “no recent crossing” classification requires ≥95% coverage and no gap over 30 minutes; otherwise context is unknown. These are WXF diagnostic rules, not NOAA's event-termination definition. A preceding crossing does **not** veto a prediction after flux falls below threshold. The frozen model target includes renewed crossings as well as first crossings; it does not establish causal flare association. Current-window baseline eligibility and fitted probabilities remain unchanged.

`audit.py` adds `episode_context` and a separately named diagnostic evaluation to the SQLite database without modifying original outcomes, partitions, model weights or predictions. The export includes all-window statistics and the subset without recent crossings. These cohorts must not be compared as evidence of a model improvement because their event mix differs. The February example is excluded only from the no-recent-crossing diagnostic cohort.

The 20% value is an illustrative **probability scoring cutoff**, not a particle-flux threshold, model coefficient, operational warning recommendation or required PROTONS setting. Probability forecasts and Brier scores do not depend on it. The interface leads with Brier skill and its uncertainty; an expandable verification table supports 5%, 10%, 20%, 30% and 50% cutoffs to show detection/false-alarm sensitivity. This control changes only the verification table, never Alert Settings or forecast probabilities. No optimal cutoff is selected using the inspected test years.

Event setup uses one aligned selector/run row, two rows of core inputs and compact analyst/source disclosures. Its CSS is maintained in `dashboard.css` and embedded in the standalone HTML.

## Interface Labels And Event Layout

Use Title Case for every title, field label, option label and action. Scientific unit/acronym case is preserved (for example mSv/h, nT, MeV, pfu, HUXt and PyCAT). The shared `scripts/dashboard_labels.js` presentation layer covers semantic labels and dynamic content; custom label elements can use `data-ui-label`. Descriptive paragraphs, editable values and raw provider records retain their original text. Native option display/accessible labels change without changing option values.

Coordinates explicitly show both hemispheres: **Latitude: N(+) S(-)** and **Longitude: W(+) E(-)**. Core fields are grouped into Flare Observations and Source & Energy. Analyst controls remain directly below them, with one disclosure open at a time. Selecting a historical case hides the redundant reported-flare selector. Automatic numeric fields display five significant figures while retaining their original precision for inference; analyst-entered values are preserved verbatim.
