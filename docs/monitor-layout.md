# Customizable Monitor

Monitor is one saved grid. Clicking a catalog product adds that product; clicking
it again removes it. No related products are inserted. The × at the upper-left
removes any card, including the heliospheric view, orbit view and alert summary.
An empty workspace remains empty after reload.

Drag the **bottom edge** to change height, the **right edge** to change width, or
the lower-right corner to change both. Height snaps in 12-pixel steps; width snaps
to one-third, half, two-thirds or full width. Focus an edge and use arrow keys
for keyboard control (Shift + up/down moves five height steps). **Size** retains
width presets and **Recommended size**, without a pixel/row input.

The whole card adapts: heading text, summary-box values, padding and spacing become
more compact in shorter cards, while the plots fill the remaining space. Narrow
cards wrap summaries into fewer columns. At the smallest sizes, content can scroll
inside the card rather than disappear. Existing saved card heights migrate to the
finer grid without changing their physical height.
The dotted header handle reorders cards; up/down buttons provide the same action
without dragging. Order and dimensions save automatically in this browser.

Time series start wide, images can share a row, and Solar Cycle starts at full
width with enough height for both plots. **Recommended size** restores a product's
default. Legacy small cards migrate once; subsequent chosen sizes are preserved.
The grid places cards in selection order, without moving later products forward
to fill gaps. Different-height neighboring cards can therefore leave whitespace.

**+ Add product** also includes the heliospheric and orbit views. **Save view**
records a named snapshot. The catalog and picker do not impose a twelve-card cap.
Each product retains its own observation or forecast dates; Monitor has no shared
forecast-time slider or model-run queue.

Scroll up or down over any Monitor plot to move the page. Plot hover and drag
interactions remain available. Expanding the notes or numerical details for SEP,
electrons or radiation dose adds room below the chart and grows the page. Closing
the details restores your chosen card height; the temporary expansion is not saved
as a resize. The same disclosures flow below the charts in Model.

All catalog observation panels render and refresh independently, including the
panels formerly labelled Alternate Panel. Those labels and ALT badges are removed.

## Awareness graphics

The heliosphere camera is fixed to the Sun → Earth view. The Sun is slightly
larger and the decorative limb loops are removed. Existing observed solar-wind
and geomagnetic drivers continue to control the illustration.

Satellite Risk and the compact Orbit Exposure view share a textured, sunlit Earth,
atmosphere, orbit rings, and illustrative moving satellites. Orbit selection is
synchronized with the impact analysis. Pause/Play and reduced-motion preferences
control animation. These are schematic objects, not tracked spacecraft.

Ap, ≥10 MeV protons and rolling >2 MeV 24-hour electron fluence update orbit colors
using the existing screening rules and saved alert thresholds. Each feed updates
the display when it arrives, independently of unrelated slow feeds. Particle
inputs expire after 20 minutes, Ap after 4 hours from its interval end (or point
timestamp). The electron integral requires at least 23 hours of valid coverage
within its preceding day; gaps longer than 10 minutes do not count as coverage.
Stale, missing, archive and partial inputs cannot produce a nominal assessment.
A threshold crossed with partial inputs is shown as **At least …**.

Driver values and UTC timestamps accompany the full graphic. **Orbit impact
analysis** expands below it, growing the card and page without hiding the
illustration. This remains environmental screening, not a spacecraft failure
probability or an orbit-resolved radiation forecast.
