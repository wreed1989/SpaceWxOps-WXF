# NAIRAS effective-dose nowcast at 20 km

The dashboard uses the current full 181 × 360 global grid at **20 km barometric
altitude**, using effective dose (not absorbed dose or ambient dose equivalent).
Radiation forecasting is deferred. The old UMASEP event forecast is no longer
fetched, embedded, or offered in the product selector.

## Alert card

**Effective Dose · 20 km** appears alongside the other Alert criteria. Click it
for source time, selected grid location, NH/SH maxima, and configured thresholds.
Alert Settings offers a global maximum, NH maximum, SH maximum, or a specific
latitude/longitude. Point selection uses the nearest original 1° cell. Missing
cells remain unavailable; maxima describe available cells, not interpolated data.

NAIRAS supplies **µSv/h**, converted once to **mSv/h**. The tile displays a rate,
not an accumulated dose. Yellow/red/purple thresholds and sound preferences are
editable and persist with the other alert settings. Blank levels are disabled;
configured levels must be nonnegative and increasing. No health or office
exposure limits are invented. The supplied SST reference of 3 mrem/h converts to
0.03 mSv/h, but its dose definition/altitude must match before adopting it as a
20 km effective-dose criterion.

Unknown/stale readings have a neutral state and cannot trigger a new popup or
sound. A stale interval does not reset an active threshold crossing. Startup
primes the existing state without alarming on an already elevated value.
Changing the monitored location also primes that area's state. Valid increases
through configured thresholds follow the same popup/audio behavior as the other
criteria. The summary labels current exceedances as nowcasts, not observed
crossing times. Rate values use the source product epoch.

## Forecast-only Models entry

Radiation is absent from Models, the Product Catalog and the Monitor tile picker
while no radiation forecast is connected. Saved nowcast-only tiles are removed
on load; a saved radiation model selection returns to CME | Solar Wind.

The existing interactive polar-map renderer is retained for future use, but is
not offered as a forecast. A future integration must register
`window.SpaceWxRadiationForecast` with:

- `available()` returning exactly `true` only for a scientifically usable,
  nonexpired forecast or runnable forecast method; nowcasts do not qualify.
- `mount(root)` rendering forecast quantities, original issue/valid dates,
  altitude, dose definition, units, provenance and uncertainty.
- Optional `unmount()` for cleanup. Dispatch `spacewx:radiation-forecast-updated`
  when availability changes so navigation/catalog/saved tiles update together.

This contract does not supply a forecasting method. Forecast development remains
deferred. No stale event forecast is restored to make the tab appear.

## Freshness and ingestion

The nowcast is normally hourly. A future-dated grid is withheld from alerts. A grid more than three hours old is marked stale
and reported as a feed issue, even if its JSON downloaded successfully. Fetching
an old grid never updates its product epoch. The latest dated grid remains
available through an outage, with its status visible.

`chhss.nairas` uses iSWA's `recent` API, data ID **2643**, to retrieve the dated
20 km effective-dose numeric file. It validates the altitude, host, full coverage
and coordinates, then normalizes ordering. Missing/fill values remain null.
The parser accepts the provider's appended `Neutron_Monitor` metadata object.

The hourly publisher writes `chhss-data/nairas.json`; the downloadable HTML
embeds the full nowcast and checks the public publication every five minutes,
independent of which desk tab is open.
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
