# SEP/proton and electron forecasting options

Updated September 19, 2026 UTC. The dashboard now displays published UMASEP,
HESPERIA REleASE and SWPC REFM products. The remaining options below are future
integrations.

## Available now

- **SEP / Proton:** UMASEP ≥10 and ≥100 MeV provider charts, plus the HESPERIA
  REleASE ACE EPAM chart. NASA numerical submissions show the energy channel,
  source issue time, valid window and published prediction. All-clear statements
  retain the provider's event threshold; they are not a zero-flux prediction.
- **Electron Forecast:** SWPC REFM daily >2 MeV GEO fluence, 14/30/60-day observed
  history and the latest three subsequent UTC forecast days. Negative fill values
  remain gaps. This is environmental guidance, not spacecraft failure probability.
- These products appear in Model and can be selected individually from Monitor's
  Radiation catalog. They refresh automatically; **Refresh forecasts** only
  retrieves published outputs. The old Configure + run interface was a concept
  interface without a connected solver and has been removed from these pages.

NASA ISWA's API does not provide browser CORS access. `chhss.particles` retrieves
five numeric feeds during the existing hourly publication job and publishes
`chhss-data/particle-forecasts.json`. Each source fails independently and retains
its original successful retrieval time. The downloadable HTML embeds a dated
snapshot and refreshes it from the public repository. Provider charts use ISWA's
latest-file redirect every five minutes, independently of the hourly numeric
relay. Read the issue and valid times printed on those images; successful loading
does not prove that the upstream model issued a new forecast. Expired numerical
windows are labelled explicitly. REFM is fetched directly from SWPC.

Source IDs, verified against the [NASA ISWA catalog](https://iswa.ccmc.gsfc.nasa.gov/catalog/data-feeds):
UMASEP images 1647/1650, numerical 1653/1656; REleASE ACE image 1221, numerical
1218/1219/1220 (30/60/90-minute products). No retired UMASEP version is selected.
Attribution for HESPERIA and EU funding appears with its chart.

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
