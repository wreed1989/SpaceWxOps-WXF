# Desk refresh — CME, Electron and navigation

Release: 2026-09-27. Build from the user's `SpaceWxOps_Solar_Flare_Refined.html`, not the older repository-root HTML.

## Changes

- Navigation is MONITOR / FORECASTING / CHARTS / SWPC / SHIFT CHANGE. Routing keys are unchanged. The electron workspace is titled Electron.
- CME uses the shared saved 24-column workspace: move handles/arrows, width/height controls and edge/corner resizing. Default pairs are SWPC + HUXt, then EUHFORIA + NASA M2M. Small screens stack the cards. All media is contained without stretching.
- HUXt's main panel plays the provider's actual propagation MP4 instead of the previous static forecast PNG. The separate numerical WXF HUXt Earth wind-speed plot remains explicitly labeled as a diagnostic.
- The Scoreboard refreshes on mount, every five minutes while visible, when returning to the visible page, and via its working Refresh button. It uses the rolling publication plus official API fallbacks, sorts by CME observation date, follows new latest events until an explicit historical selection, and preserves the original retrieval time on failed refreshes. Errors do not manufacture new entries.
- Electron now reads an independently refreshed publication, rather than a September 20 snapshot. The existing frozen model, candidate, scientific thresholds, quality gates and forecast equations are not changed. Current inputs are still required; stale and future observation cutoffs are rejected.
- A working SWPC REFM relay is not reported as failed solely because the browser's direct request is blocked. SWPC daily fluence and WXF rolling fluence remain distinct products.
- Repeated inner identity headings are hidden only inside already-titled product frames; status values, selectors and refresh controls remain. Satellite Orbit Risk is removed inside Orbit Exposure. No document-wide mutation observer is added.

## Publication and observed source state

`Desk CME and Electron Products` is scheduled hourly at minute 11 on main. It publishes to the separate `ops-live` branch. The HTML checks these current files every five minutes; the browser cannot trigger an authenticated Actions run. This workflow does not require or expose ESA credentials.

Actual first production run: **36315126834**, successful, source **9fc4d68d813bcf2df29bb8367f35e13a55b09ab8**. The captured products were:

- Electron issued 2026-09-27 11:15:56 UTC, observation cutoff 11:00 UTC. Frozen model SHA-256: `929c5ee2a3d24db0838a4d389ae996d165bcf1c54dbedc9719ac38c82f241732`.
- CME Scoreboard: 10 catalog events, retrieved 11:15:57 UTC. The latest event returned in this collection is September 14. The Scoreboard is a submission catalog, not a complete CME-detection catalog.
- NASA M2M: linked September 14 submission, readable 41-frame GIF. It is labeled Older Run, not relabeled current because it was just downloaded.
- HUXt: actual provider MP4 retrieved and decoded. HTTP Last-Modified is not used as model issue time; the provider's model times stay on the movie.
- NOAA REFM: bulletin issued September 27 at 00:14 UTC.

The source manifest records each product's status, timestamps, URL and asset hash. Successful collection is not proof that the provider has issued a new run. No HUXt, M2M or EUHFORIA animations are synthesized from one-dimensional series.

## Build

With current `cme-scoreboard.json`, `electron-fluence.json` and `particle-forecasts.json` from ops-live in a local products directory:

```sh
python dashboard/desk_refresh/build_refresh.py \
  SpaceWxOps_Solar_Flare_Refined.html SpaceWxOps_Desk_Refresh.html \
  --products products
```

The builder rejects missing or unexpected source patterns and writes a change/hash manifest. It requires the reviewed baseline, not an arbitrary older or already-patched HTML. All code stays inline in the output, so the new file does not require the dashboard source folder beside it.

## Testing and limitations

The complete new HTML passed 43 Chromium functional checks and all 49 executable-script syntax checks. Browser routes served captured real production payloads/media; other network routes, including direct REFM and Scoreboard requests, were deliberately blocked. This tests the anonymous mirror fallback, media decoding/playback, refresh and failure behavior, controls, saved layout, EUHFORIA series containment, 1,000/640-pixel workspace widths, navigation and duplicate-header removal. It is not another live-network test or a test of the user's workplace network.

61 of 70 existing script blocks are byte-identical to the baseline. Nine targeted blocks changed; one tiny compatibility script was added. The HF/UHF/Global scientific and export code, UHF tables, solar-flare calculation and heliospheric animation are not changed. Full chart exports were not regenerated. The previously documented Plotly `_redrawFromAutoMarginCount` startup warning remains; there were no additional unhandled error types in this test. App regression tests do not establish new forecast skill.

Baseline SHA-256: `ecb54f2be2313218260b6dad30ed11de02f53d4a636c4cbd040543adc0a30025`.
Output SHA-256: `299e6652308fe14dc356d5e71e00073ac191d21a9661867c3d69822f544dd2d3`.

The standalone HTML is delivered separately. These source changes do not overwrite the older repository-root HTML.
