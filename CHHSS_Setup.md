# Coronal Hole / HSS Outlook

## Status of this delivery

This package adds an automatic data producer and connects it to the revised HTML. It is not a populated historical archive or an already-running hosted service. The delivery environment could not resolve the NASA/JSOC hosts or install the FITS dependency stack. Consequently, live NASA acquisition, archive staging and real AIA/HMI reprojection were **not executed successfully here**. Tests using numerical arrays and controlled browser fixtures are included separately.

The first successful source run must occur on your GitHub runner or processing workstation. It will create the actual feed and begin the backfill. No synthetic observations are shipped as live input. Neither running the worker nor receiving a magnetic sign makes the forecast operationally validated.

## Files you actually need

- `SpaceWxOps_Coronal_Hole_HSS_Outlook.html`: complete revised dashboard. The v2.2 heliospheric script is unchanged. The alternate model/training interface has been removed, not merely renamed.
- `.github/workflows/chhss.yml`: a **self-contained workflow** containing readable copies of the producer and its acceptance tests. This is the only file you need to add to the existing GitHub repository for hosted processing.
- `Run_CHHSS.ipynb`: local Mac/Jupyter alternative. It uses the Python modules in this package, runs acquisition and creates a transferable HTML snapshot.

The HTML has no additional external JavaScript dependencies and no credentials. It reads JSON from the producer. It supports a public HTTPS endpoint even when the dashboard is opened as a local file. Actual work-network CORS/allow-list behavior still needs checking after deployment.

## Activate on the existing GitHub feed repository

The default HTML endpoint is:

`https://raw.githubusercontent.com/wreed1989/SpaceWxOps-WXF/main/chhss-data/feed.json`

1. In `wreed1989/SpaceWxOps-WXF`, add the supplied workflow at the exact path `.github/workflows/chhss.yml` on `main`. Do not replace the existing flare-guidance workflow. The CH/HSS workflow materializes its own bundled Python files in a temporary runtime directory; separate Python uploads are not needed.
2. Add a repository Actions secret named `JSOC_EMAIL`, containing an email address **already registered with JSOC**. Direct-online segment access does not require an export account, but records needing archive/tape staging do. Do not place this address in the HTML, public JSON, notebook source, or a public workflow literal.
3. Open Actions → **Coronal Hole / HSS Outlook data** → Run workflow. Leave dates blank to initialize/resume the default plan. After the job publishes, open the new HTML and press **Refresh data** in the Data connection panel.

The initial plan covers approximately the preceding year, ending eight days before the first run; daily slots are at 12:00 UTC. The end date is exclusive. Each run attempts at most seven historical dates within a 28-minute processing budget, in addition to the current measurement. The schedule repeats hourly at minute 13. An unfinished JSOC staging request is remembered and retried rather than resubmitted repeatedly. Failed dates remain failed/unknown, never quiet cases.

The historical plan is persisted in `backfill_ledger.json`; blank inputs resume it rather than moving the date window every hour. To extend the archive, run again with explicit start/end dates, for example start `2020-01-01`, end `2026-09-01`. Supported start dates are 2010-05-01 or later. This is a processing range, not a guarantee of continuous instrument coverage.

The workflow commits **only `chhss-data/`**, retries a normal rebase/push when another workflow updates `main`, and never force-pushes. Its separate concurrency group does not block the existing formal flare job. A source failure still publishes explicit health information and retains the original timestamp on any last-good measurement; the job then reports failure rather than pretending the source is healthy.

A workflow file must be on `main` and Actions must be enabled for the schedule to run. No workflow was uploaded or dispatched by this chat session.

## What the producer does

### Current measurement and polarity

For the current view it discovers the newest QUALITY=0 AIA 193 observation in the preceding six hours, rather than assuming a fixed provider latency. Historical selection remains near each fixed requested time. It fetches co-timed AIA 171/211 observations and a signed HMI line-of-sight magnetogram. Definitive `hmi.M_720s` is used where available; the current path can use `hmi.M_720s_nrt`. Backfill uses the definitive series. The precise series is recorded, and report statistics are separated by it rather than silently treating NRT and definitive measurements as interchangeable.

DRMS record times are converted from TAI to UTC with Astropy. Direct JSOC segment FITS do not necessarily contain WCS/observer keywords. The worker therefore pairs the data with keywords queried from the **same exact record**, checks the record identity, keeps checksums, and avoids applying FITS BSCALE/BZERO twice. Offline records can be staged via a registered JSOC export; request IDs are cached for resumption.

AIA is rotated/resampled to a north-up target grid. The other EUV channels and HMI are reprojected to that WCS. All passbands must be within 90 seconds and HMI within 30 minutes. The source observation times—not fetch or publication times—control freshness.

The automatic candidate mask uses exposure-normalized FITS intensities, annular-median normalization, fixed 193/211 dark thresholds, a 171 constraint, connected-region filtering, and a science-disk mask. This is **a custom, versioned candidate detector, not CHIMERA, not a manually reviewed catalogue, and not an already-validated segmentation method**. The previous manual-mask requirement is removed; the scientific limits are not hidden. Filaments, bright active-region obscuration, polar geometry, instrument changes and radiometric effects still need targeted validation. A segmentation failure does not become an empty/quiet Sun.

Polarity is measured over the matching candidate pixels. It uses a labelled B_LOS/mu radial approximation and relative surface-area weighting, with mu >= 0.4. Each E/M/W core and each connected candidate has independent signed statistics. The initial gates are >=100 valid target-grid pixels, >=80% coverage, |imbalance| >=0.15 and |mean Br| >=1 G. These are provisional QA settings, not universally calibrated constants. Target-grid interpolation is not native-resolution magnetic-flux measurement. Mixed, weak, too-small or limb-excluded candidates stay unknown; a global sign is never copied across all holes.

The browser verifies the mask SHA-256, recomputes core counts from the WCS labels and checks ages/polarity evidence before using the package. Individual hole signs now reach the comparison inspector as well as the core outlook. Reference-rotation markers do not inherit today's sign.

### Historical backfill and verification

Every requested daily slot has a ledger entry or is explicitly not attempted. Successful slots store their measured core filling factors, signed-field statistics, actual source times, record IDs and checksums. Historical inputs are labelled **retrospective reconstructions**, not claims that these definitive data existed at the original forecast issuance.

The same detector recipe is used for current and historical measurements. The existing area-to-speed relation is retained as one outlook: V = 350 + 900 A, with the 20-degree E/M/W cores mapped to 6/4/2-day speed lags. No untrained regression or user-adjustable model blend overrides it. No-signal cores below 2% filling are recorded but do not masquerade as correct quiet forecasts.

NASA OMNI2 hourly data provide verification truth and the 27-day comparator. Documented fill values stay missing. Both use the **same fixed UTC daily-mean speed target**, with at least 20 valid hours; no searching around an event for a favorable observed peak. Missing recurrence cannot count as zero baseline error. Completed target dates and adequate observation coverage are required.

Reports include matched sample counts, MAE, RMSE, bias, recurrence MAE, skill, per-core/series breakdowns and chronological evaluation partitions with a 34-day embargo. Block-bootstrap intervals require at least six 54-day test blocks. Recurrent-source identities are not tracked, so these are **not family-purged confidence intervals**. Scores include all solar-wind regimes because an independently qualified Earth-ICME screening catalogue is not supplied. Do not call them clean-HSS scores. No coefficients or alert rules are promoted automatically.

This implementation gets the *acquisition, processing, archive and verification plumbing* in place. It does not certify the empirical detector/forecast combination or establish onset, duration, Kp, hourly Dst or local-impact skill. The displayed conditional geomagnetic context remains separate from source-sign measurement; source polarity is not a prediction of the IMF Bz time series.

## Published and cached outputs

| File | Purpose |
|---|---|
| `chhss-data/feed.json` | Atomic envelope consumed by HTML: current registered measurement, recent OMNI history, archive counts and verification summary. |
| `current.json` | Full last-good current measurement, mask, raster and signed-field evidence. |
| `history.json` | Complete compact historical input archive. The HTML's **Export archive** retrieves this file. |
| `backfill_ledger.json` | All planned-slot results, failures and retry metadata. |
| `verification.json` | Complete paired verification report and paired cases. The HTML exports a bounded summary; the full file remains here. |
| `recurrence.json` | Recent gap-preserving hourly OMNI inputs and daily statistics. |
| `status.json` | Acquisition health, actual progress and explicit errors. |
| `.chhss-cache/packs/` | Compressed full historical mask packages for review, retained on the processing machine/cache, not committed. |
| `.chhss-cache/solar/` | Bounded raw FITS cache, exact-record metadata and resumable export tickets. |

To keep the HTML feed bounded, it contains up to 90 recent historical summaries and 200 paired verification rows; its counts/metrics use the full successfully processed archive. Complete datasets are in the separate files above. An unavailable full archive does not silently get replaced by the bounded summary.

The raw FITS cache is capped at approximately 1 GiB; older raw segments can be retrieved again using recorded IDs/checksums. The full historical mask packages are not independently backed up by this delivery; copy them to durable storage when they form part of an operational audit record. GitHub cache eviction does not erase the compact historical archive or ledger committed to the repository, but can remove raw caches and staging tickets.

## Run locally instead

Extract this package on the Mac and open `Run_CHHSS.ipynb` in that folder. Run all cells. The notebook installs the dependency stack, requests the registered email without embedding it in source, runs tests, retrieves data and produces `Coronal_Hole_HSS_Outlook_Snapshot.html`.

Equivalent terminal commands in a dedicated environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-chhss.txt
# Set JSOC_EMAIL privately in your environment when archive staging is needed.
python -m unittest discover -s tests -p 'test_pipeline.py' -v
python -m chhss.worker run --chunk 7 --embed-html SpaceWxOps_Coronal_Hole_HSS_Outlook.html
```

A second run resumes the archive. For a deliberately larger local batch, increase both `--chunk` and `--budget-minutes`. The producer does not run in the background after this command exits. The work PC only opens the resulting HTML or the public live-feed HTML; Python is not required there.

The snapshot embeds actual producer output once it exists. It is not a self-updating solar archive; old observations expire after six hours for live forcing. Publish/run the worker regularly for continued live use.

## First-run acceptance and diagnosis

A useful first-run test requires actual source evidence, not merely a green install step:

- `status.current.ok` must be true, with plausible recent EUV/HMI times and real record IDs/checksums. Unknown individual signs can be the correct scientific result.
- `status.truth.ok` must be true; check valid hourly counts rather than HTTP status alone.
- Backfill completed dates must increase on successive runs. Examine failed dates; a complete processing ledger is not complete science coverage.
- Open the measurement raster; inspect mask registration and field signs on positive, negative, mixed and limb cases. Then inspect actual validation errors before operational promotion.

“Worker feed not published yet” / HTTP 404 means the workflow has not produced the feed at the configured URL. A JSOC staging message means a registered `JSOC_EMAIL` is needed or a stored request is pending. A QUALITY/WCS/coverage rejection means the scientific input did not pass the declared gates; do not bypass it by converting a display image to gauss or forcing a sign.

## Code maintenance

The readable Python source is in `chhss/`. After making changes, run `python make_workflow.py` to regenerate the single-file workflow. The generated YAML is checked against these source files in the delivery QA. Keep measurement-recipe changes versioned; do not pool incompatible recipes in a skill score.

## Sources used to define the interfaces

- SunPy/drms tutorial, direct segments, same-record keywords, TAI and export staging: https://docs.sunpy.org/projects/drms/en/stable/tutorial.html
- SunPy AIA/HMI WCS reprojection example: https://docs.sunpy.org/en/stable/generated/gallery/map_transformations/reprojection_align_aia_hmi.html
- drms Client and ExportRequest API: https://docs.sunpy.org/projects/drms/en/stable/generated/api/drms.Client.html and https://docs.sunpy.org/projects/drms/en/stable/generated/api/drms.ExportRequest.html
- NASA OMNI2 format, processing and missing-value conventions: https://omniweb.gsfc.nasa.gov/html/ow_data.html

These sources support the data interfaces and registration approach. They do **not** validate the new segmentation thresholds, the transferred area-to-speed coefficient, or this product's forecast skill.
