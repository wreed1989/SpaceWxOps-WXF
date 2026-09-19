# NAIRAS effective-dose nowcast at 20 km

The dashboard uses the current full 181 × 360 global grid at **20 km barometric
altitude**, using effective dose (not absorbed dose or ambient dose equivalent).
Radiation forecasting is deferred. The old UMASEP event forecast is no longer
fetched, embedded, or offered in the product selector.

## Interactive maps

The two polar maps include the equator. Choose both hemispheres, NH or SH; hover
for the original grid-cell coordinates and rate; click to select a location.
Latitude/longitude fields offer keyboard access. Drag to pan, use +/− to zoom,
focus the selected location or reset to the full hemisphere. The mouse wheel
scrolls the page. Product refreshes and quantity changes retain the map view;
changing hemisphere resets its extent. Both hemispheres share a color scale.
Coordinate labels clip at the viewport when zoomed. Coastlines are Natural Earth
1:110m public-domain data embedded in the HTML.

The projection displays the nearest original **1° cell**, without smoothing dose
values. Zoom does not increase data resolution. Opaque hover labels show source
coordinates and values; the white ring marks the selected location. Model mode
lets the map and notes expand down the page. Monitor keeps its resizable cards.

NAIRAS supplies **µSv/h**, converted once to **mSv/h**. The optional exposure
control shows a **constant-rate dose estimate in mSv** (rate × hours at one
location), not a forecast or a time-integrated flight calculation. Units remain
explicit even for a one-hour estimate whose numerical value equals the rate.

## Freshness and ingestion

The nowcast is normally hourly. A grid more than three hours old is marked stale
and reported as a feed issue, even if its JSON downloaded successfully. Fetching
an old grid never updates its product epoch. The latest dated grid remains
available through an outage, with its status visible.

`chhss.nairas` uses iSWA's `recent` API, data ID **2643**, to retrieve the dated
20 km effective-dose numeric file. It validates the altitude, host, full coverage
and coordinates, then normalizes ordering. Missing/fill values remain null.
The parser accepts the provider's appended `Neutron_Monitor` metadata object.

The hourly publisher writes `chhss-data/nairas.json`; the downloadable HTML
embeds the full nowcast and checks the public publication every five minutes.
The builder also strips the retired forecast from older source snapshots.
No unrelated observation archive is introduced.

## Alternate delivery and independent models

Checked September 19, 2026:

- **NASA Langley:** its [NAIRAS page](https://spaceradiation.larc.nasa.gov/nairs.html)
  points to CCMC. It is not a separate public numeric mirror.
- **Space Environment Technologies:** also distributes NAIRAS and asks users to
  arrange access to [numeric data](https://spacewx.com/current-data/). Its public
  maps list 5, 11, 15 and 90 km, not 20 km. [RADIAN](https://spacewx.com/radian/)
  is a commercial service offering historical, current and future radiation
  products. Confirm 20 km effective-dose coverage, delivery/API rights and
  latency before integrating it. No public numeric 20 km endpoint was verified.
- **FAA CARI-7A:** an [independent effective-dose model](https://www.faa.gov/data_research/research/med_humanfacs/aeromedical/radiobiology/cari7)
  covering altitudes well above 20 km, with GCR and solar-particle options.
  It is a candidate for a separately labeled local fallback. It requires
  maintained inputs, spectrum selection and validation against NAIRAS and
  available measurements; it is not a ready-to-use live global feed.
- **CCMC runs on request:** supports [custom global and trajectory runs](https://ccmc.gsfc.nasa.gov/news/nairas-update/),
  useful for reconstruction and validation, not an established immediate failover.
- **NASA ARMAS portal:** [measured flight radiation](https://data.nas.nasa.gov/helio/portals/rdp/rdp_index.html)
  is useful validation evidence, not a complete global 20 km grid.

No substitute is automatically presented as current NAIRAS. A future fallback
must retain its own model identity, original time, altitude, dose definition and
coverage. Raw GOES proton flux alone is not an effective-dose conversion.

Sources: [NASA CCMC NAIRAS 4](https://ccmc.gsfc.nasa.gov/models/NAIRAS~4/),
[CCMC physical variables](https://ccmc.gsfc.nasa.gov/VIS-DOCS/physical-variables/),
[NASA iSWA catalog](https://iswa.ccmc.gsfc.nasa.gov/catalog/data-feeds),
[Natural Earth](https://www.naturalearthdata.com/).
