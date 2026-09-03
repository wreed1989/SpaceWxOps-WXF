# NJIT FlareDB integration note

WXF uses FlareDB as a positive-event sequence and coverage audit, not as a standalone classifier training set.

The paper describes 151 M5+/X events from 82 active regions, 32-hour HMI/AIA sequences, and more than 30 X events in 2024. The repository event-list snapshot audited on 2026-09-03 contained 103 events, including 13 X events in 2024. Ten of those 13 came from AR 13663/13664 but collapse to eight unique region-day forecast cases; repeated flares and overlapping 32-hour sequences are not independent samples.

To reproduce the audit without redistributing the upstream file:

```bash
curl -L https://raw.githubusercontent.com/Reasopprime/njit-flaredb/main/Flare_event_list.csv -o /tmp/Flare_event_list.csv
python audit_flaredb_coverage.py \
  --events /tmp/Flare_event_list.csv \
  --goes-catalog datasets/goes_region_flares_1995_2026.csv.gz \
  --training-table datasets/sharp_mag_training_table_v2.csv.gz \
  --output research/flaredb/coverage_audit.json
```

The large movies/FITS data are candidates for a future grouped temporal-image experiment. Any such experiment must add quiet controls, keep all sequences from one active region in one split, collapse overlapping event windows, and preserve a genuinely future test block.
