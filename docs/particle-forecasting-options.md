# SEP/proton and electron forecasting options

Reviewed September 19, 2026 UTC (September 18 locally). These are integration
recommendations; no new particle forecast model is enabled by this update.

## Recommended first step

Keep official SWPC guidance and GOES observations as the operational reference.
Add published NASA SEP Scoreboard forecasts for proton-event context, then NOAA
REFM for geosynchronous energetic-electron fluence. Show each provider separately
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
