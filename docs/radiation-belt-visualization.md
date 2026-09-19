# Satellite environment and radiation-belt view

The satellite graphic includes an inner proton-dominated belt, outer electron
belt, and intervening slot. The complete translucent volumes have no cutaway sectors or slice faces.
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

- **Outer electron brightness and particle count:** fresh >2 MeV GOES integral flux, on a compressed
  logarithmic visual scale. This is a local GEO proxy, not whole-belt density.
  Both are independent of Ap and user risk thresholds. More blue dots and moving tracers mean stronger current electron flux; low flux gives fewer. A bounded visual scale prevents excessive drawing cost.
- **Outer geometry:** a bounded, explicitly illustrative Ap response, showing
  inward broadening and outer-edge compression as activity rises. Its numerical
  mapping is a design choice, not a validated boundary model. Live mode does not
  infer a measured storm phase or forecast recovery.
- **Inner belt:** stable reference population. GOES solar-proton readings do not
  measure trapped inner-belt protons and do not brighten that belt.
- **Solar-proton exposure:** separate orange passing streaks scale with fresh ≥10 MeV proton flux. These are exposure glyphs, not trapped protons, a measured arrival direction, or traced trajectories. A zero reading gives no streaks; unavailable readings hide them with an explicit unavailable label.
- **Orbit colors:** the existing environmental screening rules and the user's
  saved alert thresholds. These classifications are separate from belt colors.

GOES samples expire after 20 minutes. Loading is withheld when the current
proton sample is missing/stale or ≥10 MeV proton flux is at least 10 PFU, because
proton contamination of GOES electrons is possible. This is a conservative
visualization gate, not a provider quality flag or a universal contamination
boundary. It does not modify the existing raw plots or alert policy. Missing
loading renders a muted reference cloud without moving electron tracers, never an empty radiation environment. Solar-proton streaks can remain visible when valid proton readings make the electron channel unreliable.

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

## The i explainer

The circular **i** control opens a concise introduction and particle key. Expandable
sections cover trapping and loss, separate surface/internal charging mechanisms,
single-event effects, cumulative damage, orbit differences, and display limits.
The panel has a close button and supports Escape; it scrolls independently when
necessary so all explanations remain accessible in small cards.

Particles spiral around field lines, bounce between magnetic mirror points, and
drift around Earth. Storm/substorm injections, transport and waves can replenish
or accelerate electrons. Compression can allow escape at the magnetopause;
wave scattering can send particles into the atmospheric loss cone. CME storms
and coronal-hole high-speed streams can therefore produce depletion or enhancement,
with possible delayed recovery buildup. Quiet does not mean radiation-free.

Many energetic inner-belt protons originate from decaying atmospheric albedo
neutrons produced by cosmic rays. Atmospheric losses and scattering compete with
sources; some trapped protons persist much longer than outer-belt electrons.
Exceptional storms can redistribute or inject protons. Transient flare/CME-shock
solar protons are a separate exposure; the GOES solar-proton feed cannot determine
inner-belt accumulation.

Surface charging reflects local plasma, sunlight and material-dependent current
balance, often involving lower-energy electrons. Internal charging involves
penetrating energetic electrons and charge storage in insulating materials or
isolated conductors. The >2 MeV display supports internal-charging awareness;
it does not measure surface potential. A single energetic proton or heavy ion
can cause an SEU without accumulated spacecraft charge. Dose and displacement
damage build over exposure, and depletion does not undo stored charge or damage.

| Orbit | Representative concerns |
|---|---|
| LEO | Atmospheric drag; SAA/polar radiation; auroral surface charging; possible internal charging in susceptible systems. |
| MEO | Trapped radiation, internal charging, dose and single-event effects; surface charging depends on local plasma and spacecraft. |
| GEO | Surface charging from hot plasma; internal charging from penetrating electrons; proton/ion single-event effects. |
| HEO | Changing exposure during belt crossings and high-altitude dwell; possible drag at a sufficiently low perigee. |

Orbit screening and user thresholds remain separate from particle counts.
Surface-charging screening uses Ap alone as a broad geomagnetic proxy; the former
MeV electron-fluence contribution has been removed from that category. Internal
charging retains its electron-fluence screening for MEO/GEO/HEO. This is not a
claim that LEO is immune: its local charging exposure is not resolved by GOES. An Ap-driven drag concern must not manufacture electron dots. These are
broad environmental screening cues, not local potential, dose or orbit-decay
calculations. The risks overlap and depend on orbit phase, shielding and design.

## References

- [NASA: energy-dependent radiation-belt structure and storm response](https://www.nasa.gov/missions/van-allen-probes/nasas-van-allen-probes-revolutionize-view-of-radiation-belts/).
- [NASA: electron losses during dropouts](https://www.nasa.gov/missions/van-allen-probes/nasas-van-allen-probes-spot-electron-rainfall-in-atmosphere/).
- [NASA: inner/outer belt altitude ranges](https://www.nasa.gov/image-article/radiation-belts-with-satellites/).
- [NOAA SWPC: GOES electron flux, local-time variation and proton contamination](https://www.swpc.noaa.gov/products/goes-electron-flux).
- [ESA SPENVIS: drift-shell coordinates and field models](https://www.spenvis.oma.be/help/models/shell.html).
- [ESA SPENVIS: trapping, sources and satellite effects](https://www.spenvis.oma.be/help/background/traprad/traprad.html).
- [ESA SPENVIS: surface and internal charging](https://www.spenvis.oma.be/help/background/charging/charging.html).
- [NASA: spacecraft radiation damage](https://science.nasa.gov/science-research/heliophysics/how-nasa-prepares-spacecraft-for-the-harsh-radiation-of-space/).
- [NOAA SWPC: satellite drag](https://www.swpc.noaa.gov/impacts/satellite-drag).
