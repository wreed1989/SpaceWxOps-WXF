# Satellite environment and radiation-belt view

The satellite graphic includes an inner proton-dominated belt, outer electron
belt, and intervening slot. A front sector is cut away to expose the volumes.
An idealized dipole shell uses `r = L cos²(latitude)`, with an 11° magnetic-axis
tilt. The Earth, shell geometry and representative orbits share a radial scale:

- LEO example: 1.13 Earth radii from the centre.
- GPS-like MEO example: 4.17 Earth radii.
- GEO: 6.61 Earth radii.
- HEO example: 1.15–7.2 Earth radii, with Earth at the ellipse's focus.

These are representative paths, not tracked satellites. The radial scale is not
altitude above the surface. Particle motions and spacecraft speeds are illustrative.
The diagram uses reference inner-belt shells around 1.25–2.4 Earth radii and
outer-belt shells around 3–7 Earth radii; real boundaries vary with energy,
longitude, magnetic conditions and the chosen population. The drawing is not an
IGRF/Tsyganenko field solution or a global radiation-belt reconstruction.

## Live data and limits

The existing timestamped Ap and GOES feeds supply the view without new services:

- **Outer electron brightness:** fresh >2 MeV GOES integral flux, on a compressed
  logarithmic visual scale. This is a local GEO proxy, not whole-belt density.
  Brightness is independent of Ap and user risk thresholds.
- **Outer geometry:** a bounded, explicitly illustrative Ap response, showing
  inward broadening and outer-edge compression as activity rises. Its numerical
  mapping is a design choice, not a validated boundary model. Live mode does not
  infer a measured storm phase or forecast recovery.
- **Inner belt:** stable reference population. GOES solar-proton readings do not
  measure trapped inner-belt protons and do not brighten that belt.
- **Orbit colors:** the existing environmental screening rules and the user's
  saved alert thresholds. These classifications are separate from belt colors.

GOES samples expire after 20 minutes. Loading is withheld when the current
proton sample is missing/stale or ≥10 MeV proton flux is at least 10 PFU, because
proton contamination of GOES electrons is possible. This is a conservative
visualization gate, not a provider quality flag or a universal contamination
boundary. It does not modify the existing raw plots or alert policy. Missing
loading renders a muted reference belt, never an empty radiation environment.

## Preview modes

Both the heliosphere and satellite controls use **Preview: Quiet**, **Preview:
Storm**, and **Preview: Recovery**. The satellite scenarios are detached synthetic
inputs, marked prominently on the scene and driver values:

| Preview | Illustration |
|---|---|
| Quiet | Separated reference belts, modest outer-electron intensity. |
| Storm | One possible combination of inward broadening, outer-edge compression and energetic-electron dropout. |
| Recovery | Replenished, brighter outer electrons and a broader example distribution. |

A storm need not increase radiation-belt electrons; depletion and enhancement
both occur. Recovery enhancement is also not guaranteed. Preview changes animate
smoothly; Pause and reduced-motion preferences show a static selected state.
Reload starts in Live data. Preview values never enter telemetry, alert settings,
alert issuance, or the **Live orbit impact analysis** beneath the illustration.
Orbit selection remains shared with that live analysis.

## References

- [NASA: energy-dependent radiation-belt structure and storm response](https://www.nasa.gov/missions/van-allen-probes/nasas-van-allen-probes-revolutionize-view-of-radiation-belts/).
- [NASA: electron losses during dropouts](https://www.nasa.gov/missions/van-allen-probes/nasas-van-allen-probes-spot-electron-rainfall-in-atmosphere/).
- [NASA: inner/outer belt altitude ranges](https://www.nasa.gov/image-article/radiation-belts-with-satellites/).
- [NOAA SWPC: GOES electron flux, local-time variation and proton contamination](https://www.swpc.noaa.gov/products/goes-electron-flux).
- [ESA SPENVIS: drift-shell coordinates and field models](https://www.spenvis.oma.be/help/models/shell.html).
