# SpaceWxOps WXF automatic forecast repository

This repository runs the frozen WXF flare model automatically in GitHub Actions and publishes a small daily `flare_guidance.json` product. The operations-wall HTML retrieves that file automatically. Python does **not** run on the work computer.

## One-time deployment

1. On the Mac that contains the trained model, open `WXF_GitHub_AutoUpdate_Setup.ipynb` and run every cell.
2. The notebook creates `WXF_GITHUB_REPO_UPLOAD.zip` with the real model files already included.
3. Create a **public** GitHub repository named exactly `SpaceWxOps-WXF` under `wreed1989`.
4. Extract the ZIP and upload its contents to the repository root. Preserve `.github/workflows/wxf-daily.yml`.
5. In repository **Settings → Actions → General**, ensure Actions are enabled and Workflow permissions allow read/write if the repository policy does not already permit the workflow's `contents: write` request.
6. Open the repository's **Actions** tab, choose **Update daily WXF flare guidance**, and run it once with **Run workflow**.
7. Confirm that `flare_guidance.json` and `flare_guidance.js` were updated and that the workflow is green.
8. At work, use `SpaceWxOps_FlareGuidance_WXF_AutoUpdate.html`. No daily file replacement is required.

## Automatic schedule

The daily workflow requests the formal 21Z issue at 21:20 UTC and retries at 22:20, 23:20, and 00:20 UTC. Retries accommodate delayed SHARP NRT and SolarMonitor availability. A separate lightweight workflow refreshes SolarMonitor, SIDC, and the NASA/CCMC Flare Scoreboard at 12:20 UTC without retraining or advancing the formal WXF cycle. Both workflows share one publication lock so they cannot overwrite each other.

`external_source_audit.json` records the first observed state of every configured external provider and then appends only real state changes. An accepted provider changing to unavailable is recorded as `stopped`; a provider that becomes current again is recorded as `resumed`. The last accepted forecast remains in the audit record for diagnosis, but stale members are never retained in `flare_guidance.json`.

## Files that may be public

The public repository contains the frozen model artifacts, the inference program, and forecast output. It does **not** need the 7,145-row historical training table or raw HMI/NOAA cache. Do not upload the training cache unless you deliberately want it public.

## What the work HTML does

The HTML checks the public GitHub REST endpoint every 15 minutes, caches the latest successful payload locally, and falls back to an optional same-folder `flare_guidance.js` if GitHub is temporarily unavailable. The five baseline methods remain visible. Any additional configured model appears only while the repository publishes a current forecast that overlaps the card's valid window; it disappears automatically when that condition is no longer met.

## Model identity

Expected frozen model: `sharp-mag-20260822-hierx1` (displayed as **WXF** on the wall). Keep the research flag false/experimental until prospective shadow verification supports a status change.
