# NAIRAS effective dose at 20 km

The dashboard ingests the full current 181 × 360 global grid at **20 km barometric
altitude**, using the effective-dose field (not absorbed dose or ambient dose
equivalent). The two interactive polar maps cover NH and SH, including the equator.
The projection displays the nearest original 1° grid cell, without smoothing dose
values. Coastlines are Natural Earth 1:110m public-domain data embedded in the HTML.

NAIRAS publishes **effective dose rate in µSv/h**. The relay divides by 1,000 and
stores **mSv/h**. The exposure control also offers a **constant-rate dose estimate
in mSv**: rate × hours at one location. It is not a time-integrated forecast or a
flight-trajectory calculation. For the event forecast, the estimate assumes the
forecast peak rate persists for the entire selected duration, which is labelled
explicitly. Rate and dose are always labelled separately, even for a one-hour
estimate when the numeric values coincide.

## Dates and event forecasts

- The nowcast is normally hourly; a product more than three hours old is marked stale.
- UMASEP-coupled forecasts are event-triggered SEP peak guidance, not a continuous
  hourly forecast. ISWA's latest product can belong to an earlier event.
- The source's product epoch is preserved. The numeric file supplies no explicit
  validity interval, so the dashboard does not manufacture one. A forecast epoch
  older than 24 hours is labelled **No current event forecast** and remains an
  explicitly dated event reference. A more recent epoch is still labelled as a
  latest event product with unspecified validity.
- At the September 19, 2026 integration check, the nowcast epoch was September 19
  04:00 UTC and the latest event forecast epoch was **September 6 20:15 UTC**.
  Fetching it today does not update that epoch or imply a forecast for today.

## Ingestion and preservation

`chhss.nairas` uses ISWA's `recent` API to retrieve the exact dated numeric file:
**2643** for the current 20 km effective-dose grid; **3589** for its event forecast.
It validates altitude, source host, complete grid coverage and coordinates, and
normalizes source ordering. Missing/fill values remain null. ISWA currently appends
a separate `Neutron_Monitor` JSON object; the parser accepts that known metadata
format and rejects other trailing data.

The existing hourly publisher writes `chhss-data/nairas.json`. Each source retains
its own epoch, retrieval timestamp and error status through partial failures. The
downloadable HTML embeds both full grids and fetches updates from the public
repository every five minutes while the product is mounted. No unrelated archive
or historical backfill is introduced.

Sources: [NASA CCMC NAIRAS 4](https://ccmc.gsfc.nasa.gov/models/NAIRAS~4/),
[CCMC physical variables](https://ccmc.gsfc.nasa.gov/VIS-DOCS/physical-variables/),
[NASA ISWA catalog](https://iswa.ccmc.gsfc.nasa.gov/catalog/data-feeds),
[Natural Earth](https://www.naturalearthdata.com/).
