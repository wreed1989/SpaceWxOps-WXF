"""Reproduce the published chronological verification; never replace live models."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sharp_mag_pipeline as p

root = Path(__file__).resolve().parents[1]
path = root/'sharp_mag_training_report.json'
report = json.loads(path.read_text())
dataset = root/'datasets/sharp_mag_training_table_v2.csv.gz'
assert p.sha256_file(dataset) == report['dataset_sha256']
frame = p.load_training_table(dataset)
features = p.engineer_features(frame)
a, b, c = p.chronological_splits(frame)
overlaps = {name: len(set(frame.loc[x,'NOAA_REGION']) & set(frame.loc[y,'NOAA_REGION']))
            for name,x,y in [('trainCalibration',a,b),('trainTest',a,c),('calibrationTest',b,c)]}
assert not any(overlaps.values()), overlaps
_, m = p.train_one_threshold(frame,features,label_column='LABEL_M1',threshold_name='M1+',c_value=1.,min_positives=10,allow_small_sample=False)
_, x = p.train_x1_structure(frame,features,c_value=1.,min_positives=5,allow_small_sample=True)
for key, metric in [('M1+',m),('X1+',x)]:
    assert abs(metric['brier_score'] - report[key]['brier_score']) < 1e-8, (key, metric['brier_score'])
    # Correct only reliability membership/counts. Retain original scores and lineage.
    report[key]['reliability'] = metric['reliability']
    assert sum(row['count'] for row in metric['reliability']) == metric['samples']
report['verification_audit'] = {
    'checked_at':p.iso_z(p.utc_now()), 'dataset_sha256':p.sha256_file(dataset),
    'active_region_overlap':overlaps, 'scores_reproduced':True,
    'forecast_target':'Next UTC calendar day (00–24 UTC), issued at 21 UTC the preceding day',
    'calibration_bins':'Quantile membership shared by means and counts; tied probabilities stay together',
    'scope':'Regional SHARP recipe only. Excludes morphology fallbacks, full-disk independence aggregate, and browser consensus.',
    'production_note':'Deployed estimators were refit to all rows; holdout scores describe the training recipe, not an untouched test of those final estimators.',
    'selection_note':'The holdout has been inspected in model development; future changes need separate chronological evaluation.',
    'script_sha256':p.sha256_file(Path(__file__))}
path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['verification_audit'],indent=2))
