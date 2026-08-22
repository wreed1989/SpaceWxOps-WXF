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

The workflow requests the formal 21Z issue at 21:20 UTC and retries at 22:20 and 23:20 UTC. Retries accommodate delayed SHARP NRT availability. All three runs target the same formal 21Z cycle; unchanged output is not recommitted.

## Files that may be public

The public repository contains the frozen model artifacts, the inference program, and forecast output. It does **not** need the 7,145-row historical training table or raw HMI/NOAA cache. Do not upload the training cache unless you deliberately want it public.

## What the work HTML does

The HTML checks the public GitHub REST endpoint every 15 minutes, caches the latest successful payload locally, and falls back to an optional same-folder `flare_guidance.js` if GitHub is temporarily unavailable. The existing MCSTAT, EVOL-P, Ensemble, and SWPC members remain usable even when WXF is unavailable.

## Model identity

Expected frozen model: `sharp-mag-20260822-hierx1` (displayed as **WXF** on the wall). Keep the research flag false/experimental until prospective shadow verification supports a status change.
