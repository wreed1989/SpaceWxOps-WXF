# Satellite screening: scientific review

Reviewed 19 September 2026. This dashboard provides environmental screening;
it does not calculate spacecraft failure probabilities. Its configurable colors
are **Below triggers / Trigger 1 / Trigger 2 / Trigger 3**. They identify the
highest crossed local trigger, without adding arbitrary scores across hazards.
A valid input set does not mean every spacecraft hazard has been assessed.

## Findings and corrections

| Topic | Correction and interpretation |
|---|---|
| Surface charging | Removed the remaining claim that MeV electron fluence estimates its probability. Lower-energy plasma, illumination and material current balance determine surface charging. Three-hour planetary ap is only a broad activity proxy. |
| Internal charging | GOES >2 MeV, time-integrated over 24 hours, supports exposure awareness. It does not predict a discharge probability or directly measure MEO/HEO exposure. LEO susceptibility is acknowledged but not numerically assessed by this GEO proxy. |
| Single-event effects | The ≥10 MeV solar-proton channel flags one environmental contributor. An upset does not require stored charge. Device response, spectra, shielding and orbit are needed for rates; trapped protons and cosmic-ray ions are not represented by this feed. |
| Cumulative damage | Removed the unsupported Total Dose score. The panel now says **Not calculated**, distinguishes total ionizing dose from displacement damage, and explains the required inputs. NAIRAS human effective dose in mSv cannot serve as satellite absorbed dose. |
| Drag | Three-hour ap provides LEO activity screening, not atmospheric density or orbital decay. HEO drag is conditional on actual perigee; it is explicitly unassessed. |
| Orbit context | Separated high-altitude spacecraft plasma exposure from high-latitude ionospheric effects on ground links. Orbit classes are not exclusive hazard categories. |
| Data quality | Missing/stale inputs are unassessed, not zero. Affected electron-fluence windows are withheld following a proton event. Each mechanism shows its own input status. |
| Presentation | Removed probability-like progress bars. Added actual saved trigger values, units, scientific basis, sources and mission-specific review guidance. The scene and analysis use the same policy and quality gates. |

## Threshold provenance

Existing defaults and user settings are preserved. These are local review
triggers, not universal spacecraft susceptibility limits:

| Input | Existing defaults | Meaning |
|---|---|---|
| Three-hour planetary ap | 32 / 56 / 111 | Local activity triggers. Three-hour ap and daily Ap differ. NOAA G categories use Kp and must not be inferred from custom ap thresholds. |
| ≥10 MeV solar protons | 10 / 40 / 1,000 PFU | Local exposure triggers. NOAA S1/S2/S3 start at 10 / 100 / 1,000 PFU; **40 PFU is not S2**. |
| >2 MeV electrons, 24-hour fluence | 1.1×10⁸ e⁻ cm⁻² sr⁻¹ | Office rolling 24-hour accumulated-exposure trigger. This is not a universal damage criterion. The former severe criterion was removed at the user’s request. |

NOAA's 1,000 e⁻ cm⁻² s⁻¹ electron **flux** alert criterion is not a 24-hour
**fluence** threshold. The units differ by time. An official NOAA alert also has
its own issuance logic; this dashboard's local thresholds do not reproduce it.
This matrix is not the NOAA SEAESRT model or its GEO-specific hazard quotients.

## Alignment with the animation

- Blue particle count responds to current GOES >2 MeV flux. It is a bounded,
  qualitative local GEO proxy, not a global population or failure probability.
- Orange passing streaks respond to current ≥10 MeV solar-proton flux. They do
  not populate the fixed amber inner-belt reference.
- Orbit colors use the same local thresholds as the live analysis. A high
  previous-day electron exposure can coexist with fewer current electron dots;
  an ap-driven surface-charging or drag trigger can also coexist with a dropout.
- Geometry remains an explicitly schematic ap response. Real storms can either
  enhance or deplete particles; the drawn boundaries are not measurements.
- Quiet, Storm and Recovery are labelled synthetic examples. They change neither
  live telemetry nor the analysis or alert settings.

## Electron validity and numerical integration

Instantaneous electron loading requires fresh electron and proton samples (20
minutes maximum age), sampled within 10 minutes of one another. Solar-proton
flux ≥10 PFU suppresses animated electron tracers and leaves a muted reference.
This is a conservative **local display gate**, not a NOAA quality flag, correction
algorithm or guarantee of contamination-free data below that threshold.

The 24-hour screening additionally requires coverage of the same full window by
both electron and proton data, with no ≥10 PFU proton observation in that window.
A proton-affected window remains unassessed after current electron loading can
resume. A one-second numerical tolerance is allowed in the coverage check.

Fluence uses trapezoidal integration in seconds, clips the first segment to the
24-hour boundary, ignores invalid/negative samples and deduplicates timestamps.
Only sampling gaps of at most 10 minutes are interpolated. Longer gaps contribute
neither invented flux nor coverage, and prevent a complete screening assessment.
Raw observation plots and notification thresholds remain separate from this
satellite-specific validity screen; they are not proton-corrected measurements.

## Sources

- [ESA SPENVIS: spacecraft charging](https://www.spenvis.oma.be/help/background/charging/charging.html) — charging mechanisms and environmental dependence.
- [ESA SPENVIS: SEU-rate models](https://www.spenvis.oma.be/help/models/longupset.html) — particle spectra and device-response requirements.
- [NOAA: GOES electron flux](https://www.swpc.noaa.gov/products/goes-electron-flux) — integral-channel units, local GEO variability, internal charging and proton contamination.
- [NOAA: Space Weather Scales](https://www.swpc.noaa.gov/noaa-scales-explanation) — official G and S categories and possible effects.
- [GFZ: related geomagnetic indices](https://www.gfz.de/en/section/geomagnetism/data-products-services/kp-index/related-indices) — three-hour ap versus daily Ap.
- [NOAA: satellite drag](https://www.swpc.noaa.gov/impacts/satellite-drag) — storm-related thermospheric heating and drag.
- [NASA: spacecraft radiation damage](https://science.nasa.gov/science-research/heliophysics/how-nasa-prepares-spacecraft-for-the-harsh-radiation-of-space/) — distinct radiation effects and spacecraft susceptibility.
- [NOAA: SEAESRT](https://www.spaceweather.gov/products/seaesrt) — reference for a separately developed, GEO-specific hazard assessment, not implemented here.
- [NOAA: relativistic electron forecast model](https://www.swpc.noaa.gov/products/relativistic-electron-forecast-model) — distinguishes daily-fluence forecasting from instantaneous flux alerts.

## Verification

Regression checks exercise configured threshold crossings, mechanism separation,
missing/stale data, current and historical proton contamination, preview/live
isolation, orbital applicability, and gap-aware 24-hour integration. Browser
checks cover actual source/threshold text, live scene/analysis agreement, and
synthetic preview labels. These are software and scientific-consistency checks,
not empirical calibration against spacecraft anomalies.
