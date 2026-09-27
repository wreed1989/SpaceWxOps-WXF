# ESA M2M access checks

Status: **credentials verified; production transport not deployed**.

This branch uses repository secrets `ESAID` and `ESASECRET`. Do not put their values in code, issues, browser storage, or the dashboard HTML.

## Actual live verification — 2026-09-27

Run: https://github.com/wreed1989/SpaceWxOps-WXF/actions/runs/36298968187

Tests ran around 05:58–06:04 UTC. All 24 original offline tests and five focused offline tests passed. The live requests were separate, real provider requests from the GitHub runner.

- Both named repository secrets were present. ESA issued tokens for `swe_hapiserver` and `swe_contentproxy`.
- HAPI capabilities/catalog returned valid HTTP 200 JSON. The catalog contained 27 entries; individual dataset time series were not validated.
- SIDC coronal holes and processing runs returned JSON. Run metadata reported `ImageTime=2026-09-27T04:00:05`, `RunTime=2026-09-27T06:00:09`.
- SIDC flare forecasts returned XML. Provider validity was `2026-09-26T12:30:00` through `2026-09-27T12:30:00` (timestamps as returned, without timezone suffixes). Dashboard parsing of this live format is not yet validated.
- Solarmap returned SVG. The original checker rejected its standard SVG DOCTYPE. Removing that declaration without loading the external DTD produced a parseable SVG. Internal subsets, entities and nonstandard declarations remain rejected. The tested response contained vector elements and no `<image>` elements; complete rendered imagery is not verified.
- KSO advertised a separate resource scope. ESA issued the correctly scoped token, and the API returned HTTP 200. The 59-byte response was flagged by the current checker's HTML-content-type handling; actual image retrieval still needs validation.
- Magnetic Connectivity's tested ESA URL returned HTTP 500. The direct route returned HTML instead of an image. This does not establish that every time or route fails.
- EUHFORIA's authenticated provider page was retrieved, including same-origin movie references. Neither movie bytes nor numerical output was verified.
- A-EFFort's direct HTTPS request failed at the network layer; its specific cause was not isolated.

The aggregate workflow is intentionally red when any product request fails. That does **not** mean the credentials failed. The follow-up step and its separate report completed successfully.

## Boundaries

This is a read-only access diagnostic, not a running gateway or published live-data feed. It has no schedule and no repository write permission. Tokens stay in process memory, are masked in Actions, and are not included in artifacts. Reports contain statuses, schema field names and selected timestamps; not bulk provider data or secrets.

No existing dashboard, forecast engine or main-branch file was changed by this work. Do not treat merging this diagnostic alone as a dashboard repair. Next integration work: deploy an authenticated transport, adapt actual response schemas and imagery handling, then verify those transports in the dashboard.

Official authentication reference: https://swe.ssa.esa.int/sso-and-m2m
