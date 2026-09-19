# Maintained repository inventory

Consolidation baseline: `d68b02a449054104fad8ccdf9dfb1b0be7710ed2`.

| Area | Maintained source / decision |
| --- | --- |
| Dashboard | `SpaceWxOps_Coronal_Hole_HSS_Outlook.html`; the previous dashboard's base DOM IDs, embedded data blocks, flare desk, HMI loop, and external source interfaces are present. The newer document adds registered CH/HSS functionality and intentionally removes the alternate model/training interface. Old dashboard URL and root index redirect to it. |
| CH/HSS processing | `chhss/core.py`, `pipeline.py`, `live.py`, `aia_quality.py`; recovered from successful live runtime `4c0e78c224dfec00f0eeef81cda4201df353acb7`. Historical core/pipeline were identical at the former backfill pin `f99e2b556a49be2dcbb94e20ed20c32e302dabbc`. Package imports, CLI, and publication are maintained in this checkout. Science functions/recipe are unchanged. |
| Dashboard publication | `chhss/publish.py` produces the previously missing feed/history endpoints. The HTML decodes the worker's run-length rasters and consumes its actual `chhss-validation-1` report. |
| Backfill evidence | Complete run evidence goes to a unique release; `scripts/archive_backfill.py` produces its checksummed manifest. Only compact records are staged by the workflow. |
| 2024 partial observations | Removed at the owner's request, without a replacement release. The 2.4 KB performance report remains under `docs/validation/`; it is not current-period data. |
| Retired workflow | The one-off `chhss-persist-quarter.yml` and unused root `CHHSS_Automated_Data_Workflow.yml` are removed. No older embedded Python implementation is maintained. |
| Flare inference | `sharp_mag_pipeline.py`, frozen model artifacts, and the existing daily/recovery/external workflows remain active. |
| External flare adapter | `external_flare_guidance_strict_v4.py` is the workflow entry point. It actively imports `external_flare_guidance.py`, `external_flare_guidance_fixed.py`, and `external_flare_guidance_strict_v3.py` for acquisition, strict catalog matching and schema decoding. These are dependencies, not removable duplicate versions. Unreferenced `external_flare_guidance_v2.py` is removed. |
| Research datasets | Existing complete derived training/evaluation datasets, model artifacts, builders, manifests, and reports remain. They are intentionally reproducible scientific inputs rather than per-run rasters. See `DATASETS.md`. |

Both CH/HSS workflows now execute the triggering checkout. Branch runs upload test evidence but cannot write production products or releases. Main-branch publication retries against the latest main and stages only `chhss-data`. Existing flare publication guards remain unchanged.

The old setup guide described a different, unused embedded worker. It is replaced by instructions matching the active implementation, including the actual 18-hour daily-truth gate and the absence of staged JSOC exports. No scientific improvement or operational qualification is inferred from consolidation.

Large binaries are removed only from the current tree. Commit history, older source pins and branches are preserved; reducing stored Git history would be a separate migration. Live ledger files are bounded to 90 days. Temporary source caches, raw FITS, full observation directories and backfill ZIPs are ignored; the publisher stages an explicit compact allowlist after release verification.
