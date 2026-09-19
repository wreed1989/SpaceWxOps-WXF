# SEP/proton and electron forecasting options

Updated September 19, 2026 UTC. The dashboard now displays published UMASEP,
HESPERIA REleASE, SWPC REFM and NAIRAS products. The remaining options below are future
integrations.

## Available now

- **SEP / Proton:** interactive plots built from GOES numeric ≥10 and ≥50 MeV
  observations, with UMASEP's published validity windows and event thresholds.
  Choose 6, 24 or 72 hours of history. All-clear statements are not future flux
  curves or zero-flux predictions. A published peak, when supplied in pfu, appears
  as a point with a horizontal validity bar; its position does not claim peak timing.
  Missing/negative observations remain gaps; real zeros are shown. Flux axes have a
  hard zero floor, begin at 0–15 pfu, and grow to 125% of the highest displayed
  observation or supplied peak. Off-scale thresholds do not stretch the axes.
- **Electron Forecast:** SWPC REFM daily >2 MeV GEO fluence, 14/30/60-day observed
  history and three subsequent UTC forecast days. There is only one value per day,
  which explains the coarse appearance. The compact display uses daily markers
  with straight dashed joins and does not invent an hourly forecast. Negative fill
  values remain gaps. The linear fluence axis starts at zero, with proportional
  headroom in electrons cm⁻² sr⁻¹ per day; it is not a PFU axis.
- **Radiation Dose · 20 km:** native interactive north/south polar maps from the
  complete 1° global NAIRAS effective-dose-rate grid. Select current hourly nowcast
  or latest UMASEP-coupled SEP event forecast. Hover/click a map cell or enter
  latitude/longitude. See [radiation dose details](radiation-dose.md).
- All three products appear in Model and individually in Monitor's Radiation
  catalog. **Refresh** retrieves published outputs; no local solver is implied.

NASA ISWA does not grant browser CORS access. The existing hourly publisher relays
UMASEP and REleASE numeric submissions, GOES ≥10/≥50 MeV observations, and REFM to
`chhss-data/particle-forecasts.json`. Each source fails independently and preserves
its original successful retrieval time. The downloaded HTML embeds dated numeric
snapshots, then refreshes from the public repository. GOES and REFM also refresh
directly from NOAA. No provider chart images are required by these pages.

ISWA numeric IDs: UMASEP **1653 / 1655** (≥10 / ≥50 MeV); REleASE ACE
**1218 / 1219 / 1220** (30/60/90-minute products). REleASE's differential energy
bands are displayed separately in numerical details, never relabelled as integral
10 or 50 MeV. HESPERIA / EU funding attribution remains in those details.

## Broader integration options

Keep official SWPC guidance and GOES observations as the operational reference.
The initial integration uses NASA SEP Scoreboard submissions and NOAA
REFM for geosynchronous energetic-electron fluence. Keep each provider separate
with its energy channel, issue/valid time, lead time and availability.

| Tool | What it supplies | Integration fit |
|---|---|---|
| [UMASEP v3](https://ccmc.gsfc.nasa.gov/models/UMASEP~v3/) | SEP occurrence, peak intensity and fluence guidance across several proton energy thresholds, using X-ray/proton inputs and additional solar-event inputs for UMASEP-10. | Strong initial proton addition through published CCMC/ISWA output. Lead time depends on energy and event connectivity; it is not a fixed advance warning. |
| [HESPERIA REleASE v3](https://ccmc.gsfc.nasa.gov/models/HESPERIA_REleASE~v3/) | Proton-flux forecasts at 30, 60 and 90 minutes, using faster-arriving ACE/SOHO electron measurements as precursors. | Complements UMASEP for short warning. It predicts protons; the electron input does not make it a trapped-electron forecast. Confirm provider attribution and reuse terms when implementing. |
| [SEPMOD v2](https://ccmc.gsfc.nasa.gov/models/SEPMOD~v2.20221228/) | Proton time profiles and energy-time spectra driven by ENLIL shock and magnetic-connectivity output. | Useful second-stage link to the CME workspace. Published forecasts are easier to integrate than running it locally: local runs need special numeric ENLIL field-line/shock files, not the animation we display. |
| [NOAA REFM](https://www.spaceweather.gov/products/relativistic-electron-forecast-model) | One-, two- and three-day forecasts of daily >2 MeV electron **fluence at GEO**. | Best initial electron product. Public plot and ASCII forecast are available. It is a solar-wind-driven statistical model; sudden storm dropouts and rapid enhancements can cause large errors. |
| [SHELLS-hires](https://ccmc.gsfc.nasa.gov/models/SHELLS-hires~1/) | Radiation-belt electron state inferred from low-Earth-orbit measurements. | Adds spatial/energy context and nowcasting. Treat it as a reconstructed state, not automatically as a future forecast. |
| [BAS Radbelt-DA](https://www.bas.ac.uk/project/radbelt-da/) | Radiation-belt modelling with observation assimilation and forecasts up to about one day. | A later option for orbit-resolved electron assessment. Requires a confirmed accessible service/data product and more backend work. |

The [NASA SEP Scoreboard](https://ccmc.gsfc.nasa.gov/scoreboards/sep/) provides a
natural multi-provider entry point, similar to the CME Scoreboard now added.
Published forecast availability varies by model and event; a missing or stale
prediction must remain unavailable rather than imply an all-clear.

## Electron scope matters

Solar energetic electrons travelling through interplanetary space and trapped
radiation-belt electrons are different forecast targets. For this dashboard's
GOES and spacecraft-charging context, start with GEO >2 MeV fluence via REFM.
That is not a universal satellite charging or failure probability. Surface
charging, internal charging, orbit, energy and spacecraft material response need
separate treatment before turning environmental guidance into impact estimates.

## Suggested order

1. Published UMASEP and REleASE alongside official SWPC proton probabilities and
   GOES flux; retain each provider's own thresholds and timing.
2. REFM forecast and verification against observed daily GEO fluence.
3. SEPMOD linked to the exact ENLIL/CME event when its output is available.
4. SHELLS state context and a radiation-belt forecast service if orbit-specific
   electron guidance becomes a requirement.

Archive forward-issued predictions with their original issue times before
measuring skill. Assess event detection, false alarms, timing and flux/fluence
errors by energy threshold and lead time. Avoid deriving confidence from the
number of agreeing models or blending them without validation.

## Shared alert styling

Monitor and Model use the current **Alert Settings** for ≥10 MeV protons, ≥50 MeV
protons and >2 MeV 24-hour electron fluence. Colored bands and numeric dashed threshold labels update immediately after editing or resetting the
rules. Electron forecast markers and summary values also use the configured level;
proton peak markers use their own energy-channel rule. Missing predictions remain
missing. These visual classifications do not issue observed-event alarms.

REFM uses daily fluence (electrons cm⁻² sr⁻¹ per 24 hours), so its thresholds come
from **Electron Fluence**, not the instantaneous >2 MeV flux alert. Monitor uses
a rolling 24-hour integration; REFM values cover UTC days. The
[SWPC model description](https://www.spaceweather.gov/products/relativistic-electron-forecast-model)
explains this distinction. UMASEP's provider-defined event threshold remains a
separate dotted line over its published validity window; user settings do not
change or reinterpret the provider's all-clear statement. Hover boxes use opaque
backgrounds for legibility. Color names are not printed on threshold labels.
