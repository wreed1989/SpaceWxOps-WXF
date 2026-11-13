# WXF electron model: maintained runtime and evidence

This directory contains active forecast code, not an unused research copy. The October 3, 2026 repository cleanup does not change its numerical model, forecast behavior, quality gates, deployment artifacts, or validation results.

## Required runtime

`refresh.py` loads `model.npz` and verifies it against `model-manifest.json`. Its separate guidance forecast uses `model-guidance.npz` when the required external guidance is available, or `model-no-cme.npz` otherwise. Keep **all three** arrays: the larger files are not duplicate backups.

Runtime dependencies include `acquire.py`, `model.py`, `frozen.py`, `arrivals.py`, and `impacts.py`. `hindcast-evaluation.json` supplies the compact historical summary included in the issued product. Numerical HUXt support retains `huxt_run.py`, the vendored source, ephemeris, manifest, and license. Dashboard modules, tests, and reproducible scientific builders are retained.

```bash
python research/electron_fluence/refresh.py \
  --cache .electron-cache \
  --output product/electron-fluence.json \
  --evidence product/electron-evidence
```

Use the pinned environment required by the invoking publication workflow. Data-source outages must not be relabeled as fresh observations; unavailable candidate guidance must not remove a valid primary forecast. As-issued forecast histories are preserved separately from retrospective experiments.

## Scientific interpretation

The retained model predicts 24 hourly log-flux changes with random forests and coherent calibration-error paths. Rolling 24-hour fluence combines the retained observed tail with forecast hours. Missing or proton-contaminated inputs remain missing; future information cannot alter an earlier origin. Measured wind, reported events, and submitted CME guidance have explicit availability gates. HUXt/CH context is not silently substituted for a validated learned predictor.

The office fluence criteria are 1.1e8 and 4.8e8 electrons cm^-2 sr^-1 over the preceding rolling 24 hours. They screen accumulated exposure; they are not universal spacecraft-damage thresholds. These models describe local GEO electron measurements, not global belt density, surface charging, LEO drag, or satellite failure probability.

The chronological historical study supports improvement over persistence but does not establish additional average CME/HSS skill over the expanded measured-driver model. Input receipt/revision histories, contamination screening, sample exclusions, and instrument transfer limit interpretation. Cleanup does not promote research/shadow guidance to operationally validated guidance.

## Retained validation and reproducibility

- [Chronological historical report](hindcast-evaluation.json) and [fixed test plan](hindcast-plan.json).
- [Current development evaluation](evaluation.json), [initial arrival-candidate evaluation](evaluation-arrivals-v02.json), and [experiment plan](experiment-plan.json).
- [Source provenance](input-manifest.json), [model hashes](model-manifest.json), tests, and the experiment/hindcast builders.

The detailed original [methods, cohorts, scores, caveats, and publication decision](https://github.com/wreed1989/SpaceWxOps-WXF/blob/97e029c6840308112fc5b8a0b565210f13f0b8d7/research/electron_fluence/README.md) remain available at the exact pre-cleanup commit. That is a dated scientific record, not a statement that all historical interface labels are current.

## Archived bulky outputs

These outputs are not read by the live publisher. They remain byte-for-byte available in Git history rather than being duplicated in every current source snapshot:

- [Every paired hindcast prediction](https://github.com/wreed1989/SpaceWxOps-WXF/blob/97e029c6840308112fc5b8a0b565210f13f0b8d7/research/electron_fluence/hindcast-predictions.csv.gz); its SHA-256 is recorded in the retained historical report.
- [Numerical event-response study](https://github.com/wreed1989/SpaceWxOps-WXF/blob/97e029c6840308112fc5b8a0b565210f13f0b8d7/research/electron_fluence/event-response.json).
- [Event-response figure](https://github.com/wreed1989/SpaceWxOps-WXF/blob/97e029c6840308112fc5b8a0b565210f13f0b8d7/research/electron_fluence/event-response.png).

Reproduce the chronological study into an ignored working directory:

```bash
python research/electron_fluence/hindcast.py \
  --hourly work/electron-experiment/hourly.csv \
  --arrivals work/electron-arrivals --impacts work/donki-events \
  --output work/electron-hindcast
```

See [repository recovery instructions](../../docs/CONSOLIDATION.md) to inspect a complete historical checkout without mixing old experimental inputs into the live tree.
