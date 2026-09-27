# ESA solar-product delivery

## Deployed architecture

`ESA Solar Products` uses the existing repository secrets `ESAID` and `ESASECRET` to collect provider products. It validates the payloads, then publishes passive media and normalized data to the separate rolling `esa-live` branch. The dashboard reads `https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/esa-live/latest.json`; its browser receives no ESA credentials, tokens, login pages, or executable provider scripts.

The scheduled refresh is at minutes 17 and 47 of each hour. GitHub schedules are not a guaranteed delivery SLA. The client checks the published feed every five minutes and preserves original provider timestamps. Source failures do not become zero values or fresh observations. Manual refresh: Actions → ESA Solar Products → Run workflow.

The data branch is intentionally a rolling cache. Only that branch is replaced, using an expected-ref lease. Source history and main are not rewritten. Old asset references have a two-hour grace period for open browser tabs. Provider terms and attribution are retained in the cache README and interfaces.

## Verified provider results

Live collection plus public-feed Chromium tests passed in run `36302502593` at source commit `1a9387715710c17b0feb283b46a24ec5e781eaa8`. The published snapshot checked at `2026-09-27T07:15:29Z` used data commit `b8f348c22f0d1255e96b88269b1829958b1cce94`.

- SIDC: current XML, nine full-disk/active-region scopes; full disk M1+ 10%, X1+ 1% in that sample.
- A-EFFort: current published web data, three scopes; full disk M1+ 20%, X1+ 4%. Its XML API was still returning May 2019 forecasts. The web data identifies the input magnetogram at 2026-09-27 03:58:39 UTC; it does not declare an issue time or explicit validity dates. These remain missing. The UI labels the values as recent published web guidance, not a formally window-matched forecast. No ensemble weights or verification records are changed.
- SIDC coronal holes: actual S126 run and tracked-detection records. Two detections at 2026-09-27 04:00:05 UTC. Undeclared area units remain undeclared; null polarity remains unknown. Centers are not fabricated boundary polygons and are not injected into the numerical HSS model.
- Solarmap: provider-registered SWAP Earth-view SVG with actual NOAA/other available feature layers. Corrected an embedded JPEG incorrectly labeled image/jp2. No independent raster stretching or guessed feature registration.
- KSO: 50 normal, 50 color/grid, 50 CLV-removed archive images, and one real high-contrast image. All decode in the browser; the original imagery selector and slider remain in use. High-contrast observation time must be read on the image because its latest URL does not supply that timestamp.
- Magnetic Connectivity: six actual published spacecraft selections, NSO/PFSS/Parker SCTIME maps at 06 UTC. Provider CSS places the 900×498 map layers at x=84, y=54 in a 1250×600 legend frame. The adapter preserves those exact pixels and offsets; it does not stretch maps or calculate its own field lines.
- EUHFORIA: original H.264 animation, verified playback, plus 1,729 Earth-series rows and plotted native quantities. Model run 2026-09-26 07:00:35 UTC. Bclt remains colatitudinal field, not GSM Bz. This is provider model guidance, not observations or a local run.
- HAPI: 27 catalog entries and bounded recent scalar samples. Ten datasets returned samples in the above browser run; others reported their original no-data responses. Size=[1] scalar parameters, UTC, units, and fill values are preserved.

## Important limits

Solarmap's AIA/white-light backgrounds and some feature layers were missing upstream. The delivered view uses the working registered SWAP product and disables empty layers. Independent S126 coronal-hole records remain accessible. Current-only static publication does not implement arbitrary authenticated archive requests, arbitrary spacecraft/model cycles, or full HAPI archive extraction. Those controls link to the actual provider or an explicitly configured gateway instead of pretending to work.

Observational and model-product availability may change. Passing delivery and rendering tests is not scientific validation of forecast skill.

## Standalone dashboard build

The complete standalone file is delivered separately as `SpaceWxOps_Solar_Live.html`. This repository commit contains the collector, client modules, tests, and deterministic patch/build program. **It does not replace the older root `SpaceWxOps_Coronal_Hole_HSS_Outlook.html`.** That older repository file does not contain the newer UHF/UI work from the conversation and must not be used as the build baseline. The connector used for this work supports literal text writes but no mounted-file upload of the complete 23 MB conversation artifact.

Build from the complete `SpaceWxOps_Solar_Integrated.html` supplied with the conversation:

```sh
python3 esa/build_dashboard.py SpaceWxOps_Solar_Integrated.html SpaceWxOps_Solar_Live.html
```

Verified baseline SHA-256:
`ff7e9478d98bdbae2b2a858877b4210914bb042db5c2dbd53b9b155fdac739d3`

Verified standalone output SHA-256:
`c154016d0a01049565816a45464034e807da848b573c1d9d24d88b1d621672a4`

The build adds `esaSolarDelivery`, changes only `solarProviderServices`, and leaves all 65 other script blocks byte-identical. HF/UHF/Global engines, exports, embedded numerical tables, heliospheric animation, and established workspaces are preserved. Station failures still read Unavailable. The standalone file contains the new client inline; no external JavaScript installation is required.

## Validation

- 28 collector/parser/security unit tests passed.
- 308 unique passive assets decoded and matched SHA-256 in the verified published run, including the rolling-cache grace assets.
- 28 real-network Chromium checks passed against the published branch: image/video decoding and playback, forecast parsers, native model coordinates, HAPI sample display, absence of browser authentication headers/login requests, and no module runtime errors.
- 27 complete-dashboard regression checks passed locally using captured real provider payloads. Other external feeds were blocked during that local test. It exercised the actual Model/catalog routes, flare comparison, all four KSO choices, frame slider, SWPC, Shift Change, downloads menu and view disposal.
- The pre-existing Plotly startup warning (`_redrawFromAutoMarginCount`) reproduced in baseline and updated offline tests. No new runtime error remained. Complete HF/UHF/Global image export rendering was not rerun for this solar-delivery revision; their script blocks are unchanged.

Run unit tests: `python3 -m unittest discover -s esa -p test_delivery.py -v`.
Run passive-bundle validation: `python3 esa/validate_products.py esa-live-output`.
Run the public browser smoke test: `python3 esa/browser_smoke.py`.

Dependencies are pinned in the workflow; ffprobe validates video and Chromium tests playback. Diagnostics and credentials are never published with media. Existing ESA access-check workflow remains available separately.
