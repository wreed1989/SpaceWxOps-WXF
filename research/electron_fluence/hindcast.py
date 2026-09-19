"""Expanding-window historical verification; refit only on each fold's past.

No deployment or tuning side effects. Reproduces all comparisons, thresholds,
whole-path interval coverage and paired temporal-block confidence intervals.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .model import build_examples, forest, split_mask, rolling_paths, flux_from_log
    from .arrivals import load_archive as load_arrivals
    from .impacts import load_archive as load_impacts
    from .frozen import load_model
except ImportError:
    from model import build_examples, forest, split_mask, rolling_paths, flux_from_log
    from arrivals import load_archive as load_arrivals
    from impacts import load_archive as load_impacts
    from frozen import load_model

HERE = Path(__file__).resolve().parent
TRIGGERS = {'moderate': 1.1e8, 'high': 4.8e8}
LEADS = [6, 12, 24]


def fold_masks(times, year, end='2026-09-01'):
    test_start = pd.Timestamp(f'{year}-01-01', tz='UTC')
    cal_start = test_start - pd.DateOffset(months=6)
    stop = min(pd.Timestamp(f'{year+1}-01-01', tz='UTC'), pd.Timestamp(end, tz='UTC'))
    train = split_mask(times, '2020-02-01', cal_start.strftime('%Y-%m-%d'))
    cal = split_mask(times, cal_start.strftime('%Y-%m-%d'), test_start.strftime('%Y-%m-%d'))
    test = split_mask(times, test_start.strftime('%Y-%m-%d'), stop.strftime('%Y-%m-%d'))
    return train, cal, test


def daily_calibration(times, mask):
    selected = []
    last = None
    for j in np.flatnonzero(mask):
        if last is None or times[j] - last >= pd.Timedelta(hours=24):
            selected.append(j)
            last = times[j]
    return np.asarray(selected, dtype=int)


def summaries(frame):
    results = {'originCount': len(frame), 'dates': int(frame.time.dt.date.nunique()),
               'spacecraftOrigins': frame.spacecraft.value_counts().to_dict(), 'models': {}}
    # Same once-per-day origin for every method and both office criteria.
    daily = frame.sort_values('time').drop_duplicates('date')
    for method in frame.attrs['methods']:
        scores = {}
        for h in LEADS:
            truth, pred = frame[f'truth{h}'], frame[f'{method}_median{h}']
            item = {'mae': float(np.abs(truth-pred).mean()),
                    'rmsle': float(np.sqrt(np.mean((np.log1p(truth)-np.log1p(pred))**2)))}
            if f'{method}_low{h}' in frame:
                item['coverage'] = float(((truth >= frame[f'{method}_low{h}']) &
                                          (truth <= frame[f'{method}_high{h}'])).mean())
                item['meanIntervalWidth'] = float((frame[f'{method}_high{h}']-frame[f'{method}_low{h}']).mean())
            scores[str(h)] = item
        thresholds = {}
        for name, value in TRIGGERS.items():
            observed = daily.truth24 >= value
            forecast = daily[f'{method}_median24'] >= value
            hit, miss = int((observed & forecast).sum()), int((observed & ~forecast).sum())
            false, correct = int((~observed & forecast).sum()), int((~observed & ~forecast).sum())
            thresholds[name] = {'value': value, 'dailyOrigins': len(daily), 'exceedanceDays': int(observed.sum()),
                'hits': hit, 'misses': miss, 'falseAlarms': false, 'correctNegatives': correct,
                'detectionRate': hit/(hit+miss) if hit+miss else None,
                'falseAlarmRatio': false/(hit+false) if hit+false else None,
                'criticalSuccessIndex': hit/(hit+miss+false) if hit+miss+false else None,
                'meaning': 'Median forecast crossing; sampled dates are not independent storm events.'}
        results['models'][method] = {'leads': scores, 'thresholds': thresholds}
    return results


def paired_blocks(frame, reference, days=7, count=2000, seed=1989):
    """Resample temporal blocks within each fold; never bootstrap individual hours."""
    strata = []
    for year, part in frame.groupby('fold'):
        delta = (np.abs(part.truth24-part[f'{reference}_median24']) -
                 np.abs(part.truth24-part.fullEventGuidance_median24))
        labels = (part.time - pd.Timestamp(f'{year}-01-01', tz='UTC')).dt.days // days
        groups = pd.DataFrame({'improvement': delta, 'block': labels}).groupby('block').improvement.agg(['sum', 'count'])
        strata.append(groups.to_numpy())
    rng = np.random.default_rng(seed)
    sums = np.zeros(count); sizes = np.zeros(count)
    for blocks in strata:
        sampled = blocks[rng.integers(0, len(blocks), size=(count, len(blocks)))]
        sums += sampled[:, :, 0].sum(axis=1)
        sizes += sampled[:, :, 1].sum(axis=1)
    point = np.mean(np.abs(frame.truth24-frame[f'{reference}_median24']) -
                    np.abs(frame.truth24-frame.fullEventGuidance_median24))
    return {'reference': reference, 'blockDays': days, 'resamples': count,
            'blocksPerFold': [len(b) for b in strata], 'maeImprovement': float(point),
            'bootstrap95': list(map(float, np.quantile(sums/sizes, [.025, .975]))),
            'meaning': 'Positive improvement favors full event guidance; paired origin-weighted MAE, stratified by historical test fold.'}


def evaluate(hourly, examples, out):
    plan = json.loads((HERE/'hindcast-plan.json').read_text())
    names = examples['names']; x = examples['x']; times = examples['times']
    target = np.log1p(examples['future']) - examples['base']
    current_names = load_model(HERE/'model.npz')['featureNames']
    observed = [i for i, n in enumerate(names) if not n.startswith(('cme_', 'recurrence_', 'ips_', 'hss_', 'impact_'))]
    recurrent = [i for i, n in enumerate(names) if not n.startswith(('cme_', 'ips_', 'hss_', 'impact_'))]
    variants = {'currentFeatureRecipe': [names.index(n) for n in current_names],
                'observedDrivers': observed, 'observedAndRecurrence': recurrent,
                'fullEventGuidance': list(range(len(names)))}
    frames = []; folds = []
    for year in plan['testYears']:
        train, cal, test = fold_masks(times, year, plan['testEndExclusive'])
        selected = daily_calibration(times, cal)
        if train.sum() < 500 or len(selected) < 30 or test.sum() < 30:
            raise ValueError(f'Insufficient coverage for prespecified fold {year}')
        idx = np.flatnonzero(test); positions = examples['positions'][idx]
        past = np.stack([hourly.flux.iloc[p-23:p+1].to_numpy() for p in positions])
        actual = np.stack([rolling_paths(p, f)[0] for p, f in zip(past, examples['future'][idx])])
        frame = pd.DataFrame({'time': times[idx], 'fold': year,
            'spacecraft': hourly.satellite.iloc[positions].to_numpy()})
        frame['date'] = frame.time.dt.strftime('%Y-%m-%d')
        for h in LEADS: frame[f'truth{h}'] = actual[:, h-1]
        for feature in ['ips_age_hours', 'hss_age_hours', 'speed_24h', 'cme_window_0_12h', 'cme_window_12_24h']:
            frame[feature] = x[idx, names.index(feature)]
        fold = {'year': year, 'trainingOrigins': int(train.sum()), 'calibrationOrigins': int(cal.sum()),
                'calibrationPaths': len(selected), 'trainingTargetEndsBefore': f'{year-1}-07-01',
                'calibrationTargetEndsBefore': f'{year}-01-01', 'firstTestOrigin': times[idx[0]].isoformat(),
                'lastTestOrigin': times[idx[-1]].isoformat(),
                'trainSpacecraft': sorted(hourly.satellite.iloc[examples['positions'][train]].unique().tolist()),
                'testSpacecraft': sorted(frame.spacecraft.unique().tolist())}
        for method, cols in variants.items():
            print('FIT', year, method, 'train', train.sum(), 'test', test.sum(), flush=True)
            estimator = forest().fit(x[train][:, cols], target[train])
            residuals = target[selected] - estimator.predict(x[selected][:, cols])
            logs = examples['base'][idx] + estimator.predict(x[idx][:, cols])
            bands = []
            for p, log in zip(past, logs):
                totals = rolling_paths(p, flux_from_log(log+residuals))
                bands.append(np.quantile(totals[:, np.array(LEADS)-1], [.05, .5, .95], axis=0))
            bands = np.asarray(bands)
            for k, h in enumerate(LEADS):
                for q, label in enumerate(['low', 'median', 'high']): frame[f'{method}_{label}{h}'] = bands[:, q, k]
        for method, future in [('diurnalPersistence', flux_from_log(examples['base'][idx])),
                               ('persistence', np.repeat(past[:, -1:], 24, axis=1))]:
            values = np.stack([rolling_paths(p, f)[0] for p, f in zip(past, future)])
            for h in LEADS: frame[f'{method}_median{h}'] = values[:, h-1]
        frame.attrs['methods'] = [*variants, 'diurnalPersistence', 'persistence']
        fold['scores'] = summaries(frame); folds.append(fold); frames.append(frame)
        frame.to_csv(out/f'fold-{year}.csv', index=False)
        print('FOLD', year, json.dumps({k:v['leads']['24'] for k,v in fold['scores']['models'].items()}), flush=True)
    combined = pd.concat(frames, ignore_index=True)
    combined.attrs['methods'] = frames[0].attrs['methods']
    report = {'schemaVersion':'wxf-electron-hindcast-1', 'plan':plan, 'folds':folds,
        'pooled':summaries(combined), 'pairedComparisons':{}, 'regimes':{},
        'conclusion':'Historical chronological out-of-sample verification of the fixed recipe; no deployed model changed.',
        'qualification':'CurrentFeatureRecipe is retrained on each fold past, including GOES-16; it is not the deployed GOES-19-only artifact. All methods use the same eligible origins. Availability statistics exclude calibration/training months and reflect strict retrospective truth-quality gates.'}
    for ref in plan['comparisons']:
        report['pairedComparisons'][ref] = {str(days): paired_blocks(combined, ref, days) for days in [7, 27]}
    for name, mask in {'IPSlast72h': combined.ips_age_hours <= 72, 'HSSlast72h': combined.hss_age_hours <= 72,
        'fastWind':combined.speed_24h >= 500, 'CMEWindowNext24h':(combined.cme_window_0_12h>0)|(combined.cme_window_12_24h>0)}.items():
        part = combined[mask].copy(); part.attrs = combined.attrs
        report['regimes'][name] = summaries(part)
    for satellite in combined.spacecraft.unique():
        part = combined[combined.spacecraft==satellite].copy();part.attrs=combined.attrs
        report['regimes'][satellite] = summaries(part)
    expected = sum(int((min(pd.Timestamp(f'{y+1}-01-01'),pd.Timestamp(plan['testEndExclusive']))-pd.Timestamp(f'{y}-01-01')).total_seconds()/10800)-8 for y in plan['testYears'])
    report['eligibleOriginFraction'] = len(combined)/expected
    report['eligibleOriginDenominator'] = expected
    combined.to_csv(out/'predictions.csv', index=False)
    report['predictionsSHA256'] = hashlib.sha256((out/'predictions.csv').read_bytes()).hexdigest()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hourly', type=Path, required=True)
    parser.add_argument('--arrivals', type=Path, required=True)
    parser.add_argument('--impacts', type=Path, required=True)
    parser.add_argument('--examples', type=Path, help='Optional previously saved causal feature matrix; verify against its exact acquisition/model source')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    hourly = pd.read_csv(args.hourly, index_col=0, parse_dates=True)
    if args.examples:
        with np.load(args.examples, allow_pickle=False) as a:
            examples = {k:a[k] for k in ['positions','x','base','future']}
            examples.update(times=pd.to_datetime(a['times'], utc=True), names=json.loads(str(a['names'])))
        # Matrix rows must be exactly the supplied table's origin and target bins.
        assert np.array_equal(hourly.index[examples['positions']].as_unit('ns').asi8, examples['times'].as_unit('ns').asi8)
        np.testing.assert_array_equal(np.stack([hourly.flux.iloc[p+1:p+25].to_numpy() for p in examples['positions']]), examples['future'])
    else:
        examples = build_examples(hourly, arrivals=load_arrivals(args.arrivals), impacts=load_impacts(args.impacts))
    report = evaluate(hourly, examples, args.output)
    report['inputs'] = {'hourlySHA256':hashlib.sha256(args.hourly.read_bytes()).hexdigest(),
        'exampleSHA256':hashlib.sha256(args.examples.read_bytes()).hexdigest() if args.examples else None,
        'modelCodeSHA256':hashlib.sha256((HERE/'model.py').read_bytes()).hexdigest(),
        'hindcastCodeSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'sourceManifestSHA256':hashlib.sha256((HERE/'input-manifest.json').read_bytes()).hexdigest()}
    (args.output/'hindcast-evaluation.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print('POOLED', json.dumps(report['pooled']), flush=True)
    print('PAIRED', json.dumps(report['pairedComparisons']), flush=True)


if __name__ == '__main__':
    main()
