# Coronal-hole identification and solar context

## Identification recipe `chhss-euv-hmi-20260919.2`

The former detector displayed every sufficiently large disconnected dark patch
as a coronal-hole candidate. Darkness alone also selects filaments and quiet-Sun
structure. The updated recipe requires a cool-corona contrast signature before a
component can enter the CH mask and empirical HSS core-area calculation.

The input, WCS registration, source-quality checks and radial normalization are
unchanged. The dark-pixel thresholds remain 0.58, 0.60 and 1.05 times the radial
reference for AIA 193, 211 and 171 Å respectively. Components use eight-neighbour
connectivity, avoiding fragmentation along diagonals. Minimum size remains the
larger of 50 pixels and 0.1% of the valid disk. The >45% candidate-area failure
gate remains in force.

For each component, both median normalized-intensity ratios (171/193 and 171/211)
must be at least 1.5, and at least half of its pixels must meet both ratio gates.
Accepted components retain their boundaries and are numbered by descending area.
No desired number of holes is imposed. Rejected dark patches remain in
`reviewCandidates` with their location, area, ratios and exclusion reason; they
are never added back to the quantitative mask by the display toggle.

Signed HMI evidence is evaluated independently on the accepted mask. The existing
coverage, minimum-field, flux-imbalance and degraded-data temporal-agreement
checks remain unchanged. A component with adequate signed evidence is labelled
“magnetically-supported candidate”; others remain provisional. Magnetic sign
alone does not establish open magnetic topology. Polar and limb features can
remain magnetically unresolved.

This is a custom, fixed research screen, **not CHIMERA**, a trained classifier or
a validated detection-accuracy claim. Multithermal discrimination is motivated by
[Garton et al.'s CHIMERA paper](https://arxiv.org/abs/1711.11476), but its fitted
intensity boundaries have not been implemented here. Independent segmentation
labels across varied solar conditions are needed to quantify missed holes,
false detections, boundary errors and forecast effects. The new recipe has a new
version; earlier speed-validation scores are explicitly labelled as applying to
the earlier detector.

### Current-data acceptance

The real 2026-09-19 02:24 UTC AIA observation (September 18 locally) originally
produced 12 dark components. The updated recipe retains three candidates and
excludes nine patches. The three centres are approximately S25E23, N65W9 and
N36W64; only S25E23 meets the signed magnetic-evidence gate. This count is an
acceptance observation, not a target hard-coded into the algorithm. A fresh
NRT acquisition, signed HMI processing and rolling OMNI retrieval all succeeded.
The regression tests also demonstrate that an all-filament-like synthetic scene
can produce zero accepted holes.

## Solar Cycle product

Open **Solar Cycle** in the Solar + Source Region catalog, or from the CME model
inspector. The standalone two-panel plot shows monthly and 13-month smoothed
sunspot number and F10.7, predicted smoothed values, and NOAA's low/high range.
The supplied range is not relabelled as a probability or confidence interval.

Sources are NOAA SWPC's complete
[observed indices](https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json)
and [predicted indices](https://services.swpc.noaa.gov/json/solar-cycle/predicted-solar-cycle.json).
Use `ssn`, not `observed_swpc_ssn`, for the observed sunspot curve. Negative missing
sentinels become gaps, never zero. Each feed refreshes independently, retains its
last successful retrieval timestamp on error, and is cached locally. Range
controls cover Cycle 25, Cycles 24–25, or the complete available record beginning
in 1749. F10.7 has a shorter historical record.

The centered 13-month smooth requires six following months; its latest date
therefore lags the latest monthly observation. See
[SWPC prediction validation](https://testbed.swpc.noaa.gov/sites/default/files/2024-01/solar_cycle_experimental_prediction_validation.pdf).
The phase label compares the latest smoothed sunspot number with the smoothed
value six months earlier (change >5: rising; <-5: declining; otherwise near-flat).
It is an explicitly inferred trend, not a declaration of the official maximum.
It supplies context without changing event forecast coefficients.

To include an offline snapshot in a downloadable build, pass `--solar-cycle`
to `scripts/build_dashboard.py`. The JSON must contain the complete `observed`
and `predicted` arrays and the original `retrievedAt` timestamp. Live refresh
continues after opening. No selected 2024 observation archive is introduced.

## CME | Solar Wind

The model section now displays the actual published
[SWPC WSA–ENLIL visualization](https://www.spaceweather.gov/products/wsa-enlil-solar-wind-prediction)
and [Reading / SWx Forecast Lab HUXt product](https://swxforecastlab.org/forecasts.html).
ENLIL's directory supplies frames grouped by run; the latest forecast extent
selects the displayed run. Play/pause and the slider select forecast-valid times.
Run ID, frame time and retrieval time are separate. They are not inferred CME
arrival times. If the directory is unavailable, the official `latest.jpg` image
is a labelled fallback. DONKI analysis times are not attached to SWPC model runs.

The HUXt panel uses the provider's `WSA_DONKI_huxt_forecast_latest.png`, preserving
the issue and valid times printed on the plot. These are independent provider
forecasts, not a local ensemble execution or an automatically blended forecast.
Image failures leave an explicit unavailable message and provider link.

PyCAT is a visibly unconnected placeholder for coronagraph-based CME geometry
analysis; see the [SWPC/Met Office development overview](https://cpaess.ucar.edu/abstract-sww-2025/next-generation-noaaswpc-cme-analysis-tool-pycat).
It has no fabricated measurements, controls or output. OSPREI has been removed
from the model catalog and saved selections migrate safely. SEP/proton and
electron model integration is outside this change.

## Display and comparison update (2026-09-19)

The registered preview now contains a genuine RGB image: AIA 211 Å → red,
193 Å → green, 171 Å → blue. Each channel receives its own display-only log
stretch on the common WCS grid. This replaces the erroneous assignment of the
193 Å quicklook to `compositeUrl`. It does not change segmentation, HMI values
or forecast coefficients. Helioviewer's opaque single-channel layers are no
longer stacked and labelled RGB.

The recurrence view and main CH map render each accepted component's measured
raster contour, with the same frame transform as the image. Outlines appear only
on the registered 193 Å preview and registered RGB. Selecting the same identifier
again clears the feature selection and cursor. Excluded patches have markers
only; their geometry is not fabricated. SUVI is removed from these dropdowns
because no matched SUVI measurement/archive adapter is used.

For the reference epoch, the worker resolves actual NASA SDO RGB browse filenames
in a three-day window around the prior Carrington rotation. This avoids the
browser's cross-origin restriction on NASA directory listings and invented
rounded-minute filenames. The frontend accepts only images within two hours of
the requested reference and shows the actual filename timestamp. It never places
current measured boundaries on the prior epoch. Arbitrary reference dates outside
this small index may be unavailable; AIA 193 remains a Helioviewer comparison
option. This is current-date recurrence context, not a historical backfill.

The Solar Cycle view now uses coordinated cyan/amber panels, subdued monthly
curves, emphasized smoothed curves, dashed predictions, published-range shading,
a shared UTC date axis, a prediction-period background and concise custom legend.
The four context cards, range controls and collapsed timing/source notes retain
all underlying data and missing-value behavior.

Every configurable Monitor wall tile has a top-left remove button, including
pinned tiles. Removal persists in the saved layout; the catalog/customization
controls can restore tiles. The SWPC workspace places the alert timeline above
supporting official products; the local draft and coordination-note panels have
been removed.

## NASA CME Arrival Scoreboard

The CME workspace also ingests the [NASA CCMC CME Scoreboard](https://ccmc.gsfc.nasa.gov/scoreboards/cme/earth/).
This is an additional agency forecast source, separate from DONKI event analyses
and the SWPC ENLIL run. The rolling window is the last 30 days, with both active
and closed events requested (`closeOutCMEsOnly=false`,
`skipNoArrivalObservedCMEs=false`). NASA M2M, Met Office, KSWC and other available
submissions remain separate rows. Each retains its submission time, predicted
arrival, reported asymmetric uncertainty, Kp range, confidence and notes. Missing
values remain missing. Provider averages/medians are labelled summaries and do
not count as independent models. Observed arrivals are separate from predictions.

The arrival plot compares submitted times and reported uncertainty. NASA image
links in submission notes expose the associated published propagation animation
when available. Image valid times stay on the provider's image; submission and
retrieval times are not model initiation times. No local ensemble is executed.

The service currently uses `kauai.ccmc.gsfc.nasa.gov/CMEscoreboard/WS/get/predictions`.
NASA's [announced migration](https://ccmc.gsfc.nasa.gov/news/major-updates/) is
September 30, 2026; the adapter switches to
`ccmc.gsfc.nasa.gov/CMESB-Earth/WS/get/predictions` on that date, retaining the
alternate endpoint as a fallback. Refresh is manual or every 15 minutes while
mounted. A failed refresh preserves the last successful dated snapshot with an
error message. The build flag `--cme-scoreboard` embeds a `{rows,retrievedAt,source}`
snapshot for downloaded-HTML startup.
