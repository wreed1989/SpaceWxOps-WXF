# Repository retention and recovery

Cleanup date: **October 3, 2026**. Immutable pre-cleanup commit: `97e029c6840308112fc5b8a0b565210f13f0b8d7`.

## Scope

Keep the current dashboard, its source/build dependencies, scheduled publishing, operational recovery paths, scientific verification, and compact reproducibility records. Remove disconnected experimental lanes and bulky offline outputs. Source layout and public feed URLs are not renamed.

The baseline tree contains **317 tracked files, 118,304,308 bytes** (uncompressed contents, excluding Git history). The 34 retired files below total **20,875,306 bytes** before documentation and integrity-test changes. A temporary inventory test used during the audit is removed from the final change.

| Retired from the current tree | Reason |
| --- | --- |
| `research/cross-era/` and its four `datasets/` artifacts | Standalone retrospective experiment; no maintained runtime consumer found. |
| `research/sdo-temporal/` and its three `datasets/` artifacts | Standalone image-feature experiment; no maintained runtime consumer found. |
| `research/flaredb/` and `audit_flaredb_coverage.py` | Unreferenced offline coverage audit. |
| `ccmc_diagnostic.json` and `.github/workflows/ccmc-diagnostic.yml` | One-off catalog inspection, not the active external flare adapter. |
| `.github/workflows/solar-flare-review.yml` | One-off source/observation capture. The recurring `solar-flare-evidence.yml` publisher is retained. |
| Electron `hindcast-predictions.csv.gz`, `event-response.json`, and `event-response.png` | Offline per-case results and event-study output; the runtime uses compact evaluation reports, not these bulky files. Their evidence links now point to the exact archived versions. |

## Dependencies deliberately retained

- All three electron model arrays: `model.npz`, `model-guidance.npz`, and `model-no-cme.npz`. The publisher selects guidance/fallback models according to source availability. Their combined size is **71,327,718 bytes**. Removing the larger pair would disable an existing forecast path.
- `datasets/sharp_mag_training_table_v2.csv.gz`: consumed during live flare evidence generation, as well as offline verification.
- The full active external-adapter import chain, including `external_flare_guidance_fixed.py` and `external_flare_guidance_strict_v3.py`.
- Model manifests, compact validation reports, scientific tests, licenses and the HUXt ephemeris. In particular, `docs/validation/2024-q1.json` is a small regression fixture for rejecting old-recipe validation, not current-period evidence.
- CH/HSS backfill manifests, current feeds, rolling ledgers, and as-issued flare/electron histories. These are functional inputs or evidence, not temporary cache directories.
- `index.html` and the 311-byte old-dashboard redirect. Keeping bookmarks working costs less than removing a working interface.
- Scientific builders, model-reassessment tools, and documentation needed to reproduce or interpret the retained models. No accuracy claim changes as a result of file cleanup.

The active HTML, numerical code, frozen model files, feed snapshots, and scheduled live workflows are byte-for-byte unchanged in this cleanup. Existing tests are preserved; a small repository-integrity test checks retained dataset hashes and critical dependency paths.

## Recover historical research

All retired files remain available in the [complete pre-cleanup source tree](https://github.com/wreed1989/SpaceWxOps-WXF/tree/97e029c6840308112fc5b8a0b565210f13f0b8d7). The earlier [consolidation record](https://github.com/wreed1989/SpaceWxOps-WXF/blob/97e029c6840308112fc5b8a0b565210f13f0b8d7/docs/CONSOLIDATION.md) preserves CH/HSS acceptance results and links to archived full backfill evidence.

To inspect the original tree in a separate local directory after fetching its history:

```bash
git worktree add --detach ../SpaceWxOps-before-cleanup 97e029c6840308112fc5b8a0b565210f13f0b8d7
```

A shallow clone may first need `git fetch origin 97e029c6840308112fc5b8a0b565210f13f0b8d7`. The separate worktree avoids mixing retired datasets with current model inputs. The new ignore rules keep retired output paths and local workflow evidence from being accidentally recommitted.

This cleanup does **not** rewrite Git history, delete delivery branches, expire releases, purge Actions artifacts, or shrink all historical repository objects. Those are distinct operations with different recovery and compatibility consequences. Further substantial source-tree reduction requires a deliberate model-storage/deployment change, not guessing which live model to delete.
