"""WXF-EF v0.1: causal 24-hour GEO electron paths and rolling fluence.

Seven days estimate only local diurnal shape. A multivariate regression forest
learns future changes from electron state and lagged observed solar-wind drivers.
No future measurements or manually assigned storm growth/dropout factors.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = 'WXF-EF-0.1'
THRESHOLDS = {'moderate': 1.1e8, 'severe': 4.8e8}
HORIZON = 24
SPLITS = {'trainStart': '2025-04-14', 'trainStop': '2026-03-01',
          'calibrationStart': '2026-03-01', 'calibrationStop': '2026-06-01',
          'testStart': '2026-06-01', 'testStop': '2026-09-01'}


def read_product(cache, name, columns):
    frames = []
    for path in sorted(Path(cache).glob(name + '-*.csv')):
        frame = pd.read_csv(path, names=['time', *columns], na_values=['null', 'NaN', '-100000'])
        frame['time'] = pd.to_datetime(frame['time'], utc=True)
        frames.append(frame)
    if not frames:
        raise ValueError(f'No {name} observations')
    return pd.concat(frames).drop_duplicates('time', keep='last').sort_values('time').set_index('time')


def prepare(cache):
    p = read_product(cache, 'particles', ['p10', 'flux', 'satellite', 'protonSatellite'])
    # NOAA five-minute averages are labelled at the START of their interval.
    # One sample is one boxcar, never a point for trapezoidal interpolation.
    p[['p10', 'flux']] = p[['p10', 'flux']].apply(pd.to_numeric, errors='coerce')
    valid = ((p.satellite == 'GOES-19') & p.flux.ge(0) & p.p10.ge(0) & p.p10.lt(10))
    p['accepted'] = valid
    p['flux'] = p.flux.where(valid)
    h = p[['flux']].resample('1h').mean()
    h['coverage'] = p.flux.resample('1h').count() / 12
    h['flux'] = h.flux.where(h.coverage == 1)
    h.index += pd.Timedelta(hours=1)  # hourly interval END, when all samples exist
    # One extra hour of latency for L1 driver feeds. No bow-shock-shifted OMNI.
    raw_drivers = []
    for name, columns in [('plasma', ['density', 'speed']), ('mag', ['by', 'bz', 'bt'])]:
        data = read_product(cache, name, columns).apply(pd.to_numeric, errors='coerce')
        data = data.mask(data <= -900)
        if name == 'plasma':
            data = data.mask(data < 0)
        else:
            data.bt = data.bt.where(data.bt >= 0)
        raw_drivers.append(data)
        means = data.resample('1h').mean().where(data.resample('1h').count() >= 45)
        means.index += pd.Timedelta(hours=2)
        h = h.join(means)
    # Proton-only dynamic pressure proxy, nPa; alpha-particle contribution absent.
    minute = raw_drivers[0].join(raw_drivers[1], how='inner')
    minute['pressure'] = 1.6726219e-6 * minute.density * minute.speed ** 2
    minute['southward'] = np.maximum(-minute.bz, 0)
    # Rectified VBs electric-field coupling proxy, mV/m. Not an inferred Dst/Kp.
    minute['coupling'] = minute.speed * minute.southward / 1000
    proxies = minute[['pressure','southward','coupling']]
    proxies = proxies.resample('1h').mean().where(proxies.resample('1h').count() >= 45)
    proxies.index += pd.Timedelta(hours=2)
    h = h.join(proxies)
    quality = {'rawSamples': len(p), 'acceptedSamples': int(valid.sum()),
               'otherElectronSpacecraft': int((p.satellite != 'GOES-19').sum()),
               'highProtonSamples': int(p.p10.ge(10).sum()),
               'missingProtonSamples': int((~p.p10.ge(0)).sum()),
               'completeElectronHours': int(h.flux.notna().sum()),
               'hourCount': len(h), 'firstHourEnd': h.index[0].isoformat(),
               'lastHourEnd': h.index[-1].isoformat()}
    return h, quality


def harmonics(times):
    # Midpoint of hourly average determines local diurnal phase; fixed GEO longitude.
    hour = np.asarray(times.hour + times.minute / 60 - .5)
    theta = 2 * np.pi * hour / 24
    return np.array([np.sin(theta), np.cos(theta), np.sin(2 * theta), np.cos(2 * theta)]).T


def diurnal_profile(history):
    """Robust two-harmonic shape with a separate level for each of seven days."""
    if len(history) != 168:
        raise ValueError('Profile requires exactly the preceding seven days')
    y = np.log1p(history.to_numpy())
    valid = np.isfinite(y)
    blocks = np.arange(168) // 24
    if valid.sum() < 132 or sum(np.sum(valid & (blocks == d)) >= 18 for d in range(7)) < 5:
        raise ValueError('Insufficient diurnal-profile coverage')
    design = np.column_stack([harmonics(history.index), np.eye(7)[blocks]])[valid]
    y = y[valid]
    weights = np.ones(len(y))
    penalty = np.diag([1., 1., 4., 4., *([.0001] * 7)])
    for _ in range(5):
        beta = np.linalg.solve(design.T @ (weights[:, None] * design) + penalty,
                               design.T @ (weights * y))
        resid = y - design @ beta
        scale = max(.05, 1.4826 * np.median(np.abs(resid - np.median(resid))))
        weights = np.minimum(1, 1.5 * scale / np.maximum(np.abs(resid), 1e-9))
    return beta[:4]


def features_at(data, i):
    past = data.iloc[i-167:i+1]
    if len(past) != 168 or past.flux.iloc[-24:].notna().sum() < 23 or not past.flux.iloc[-3:].notna().all():
        raise ValueError('Insufficient recent electron coverage')
    beta = diurnal_profile(past.flux)
    logflux = np.log1p(past.flux.to_numpy())
    residual = logflux - harmonics(past.index) @ beta
    level = float(np.mean(residual[-3:]))
    future = pd.date_range(data.index[i] + pd.Timedelta(hours=1), periods=24, freq='1h')
    base = level + harmonics(future) @ beta
    features = {'level': level}
    for hours in [1, 3, 6, 12, 24, 48, 72]:
        values = residual[-hours:]
        if np.isfinite(values).sum() < hours * .8:
            raise ValueError('Electron-history gap')
        features[f'level_{hours}h'] = float(np.nanmean(values))
        features[f'std_{hours}h'] = float(np.nanstd(values))
    for hours in [3, 6, 12, 24, 48]:
        lagged = residual[-hours-3:-hours]
        if not np.isfinite(lagged).any():
            raise ValueError('Electron-history gap')
        features[f'change_{hours}h'] = float(np.mean(residual[-3:]) - np.nanmean(lagged))
    features.update({f'diurnal_{k}': float(v) for k, v in enumerate(beta)})
    electron_count = len(features)
    for column in ['speed', 'density', 'bt', 'bz', 'southward', 'pressure', 'coupling']:
        for hours in [3, 12, 24, 48, 72]:
            values = past[column].iloc[-hours:].to_numpy()
            if np.isfinite(values).sum() < max(1, hours * .75):
                raise ValueError('Solar-wind-history gap')
            features[f'{column}_{hours}h'] = float(np.nanmean(values))
        features[f'{column}_change'] = features[f'{column}_3h'] - features[f'{column}_24h']
    return np.array(list(features.values())), base, list(features), electron_count


def build_examples(data, stride=3):
    records, rejected = [], {}
    for i in range(167, len(data)-24, stride):
        try:
            if not data.flux.iloc[i-23:i+1].notna().all():
                raise ValueError('Incomplete preceding 24 hours')
            x, base, names, ne = features_at(data, i)
            future = data.flux.iloc[i+1:i+25].to_numpy()
            if not np.isfinite(future).all():
                raise ValueError('Incomplete target or proton-contaminated target')
            records.append((i, x, base, future))
        except ValueError as exc:
            rejected[str(exc)] = rejected.get(str(exc), 0) + 1
    if not records:
        raise ValueError('No eligible training examples')
    return {'positions': np.array([r[0] for r in records]),
            'times': data.index[[r[0] for r in records]],
            'x': np.stack([r[1] for r in records]), 'base': np.stack([r[2] for r in records]),
            'future': np.stack([r[3] for r in records]), 'names': names,
            'electronFeatureCount': ne, 'rejected': rejected}


def split_mask(times, start, stop):
    # Purge origins whose 24-hour targets would reach the next partition.
    return (times >= pd.Timestamp(start, tz='UTC')) & (times + pd.Timedelta(hours=24) < pd.Timestamp(stop, tz='UTC'))


def rolling_paths(observed, future_paths, allow_observed_gaps=False):
    """Integrate each complete path FIRST; never integrate pointwise quantiles."""
    observed = np.asarray(observed, float)
    paths = np.atleast_2d(np.asarray(future_paths, float))
    if observed.shape != (24,) or paths.shape[1] != 24:
        raise ValueError('Exactly 24 hourly averages required')
    if (not allow_observed_gaps and not np.isfinite(observed).all()) or not np.isfinite(paths).all() or (observed < 0).any() or (paths < 0).any() or np.isinf(observed).any():
        raise ValueError('Missing or negative flux cannot become zero exposure')
    combined = np.concatenate([np.tile(observed, (len(paths), 1)), paths], axis=1)
    # A gap invalidates only windows that contain it; no fill or zero substitution.
    return np.stack([combined[:,h:h+24].sum(axis=1)*3600 for h in range(1,25)],axis=1)


def forest():
    from sklearn.ensemble import RandomForestRegressor
    return RandomForestRegressor(n_estimators=192, min_samples_leaf=12, max_depth=14,
                                 max_features=.8, random_state=1989, n_jobs=4)


def flux_from_log(log):
    # expm1 ensures nonnegative physical flux; very low estimates can be zero.
    return np.maximum(0., np.expm1(log))


def score(data, examples, mask, log_prediction, residuals):
    positions = examples['positions'][mask]
    truths = examples['future'][mask]
    bases = examples['base'][mask]
    methods = {'WXF': [], 'diurnalPersistence': [], 'persistence': []}
    coverage, width, truth24, predicted24, windows, threshold_cases = [], [], [], [], [], {}
    bands = []
    for j, pos in enumerate(positions):
        past = data.flux.iloc[pos-23:pos+1].to_numpy()
        truth = rolling_paths(past, truths[j])[0]
        paths = flux_from_log(log_prediction[j] + residuals)
        integrated = rolling_paths(past, paths)
        lo, mid, hi = np.quantile(integrated, [.05, .5, .95], axis=0)
        diurnal = rolling_paths(past, flux_from_log(bases[j]))[0]
        persistence = rolling_paths(past, np.repeat(past[-1], 24))[0]
        for key, value in [('WXF', mid), ('diurnalPersistence', diurnal), ('persistence', persistence)]:
            methods[key].append(value)
        coverage.append((truth >= lo) & (truth <= hi))
        width.append(hi-lo)
        truth24.append(truth)
        predicted24.append(mid)
        bands.append((lo,hi))
        windows.append(integrated)
    actual = np.asarray(truth24)
    result = {'originCount': len(positions), 'distinctDates': int(len(set(examples['times'][mask].date))),
              'metrics': {}, 'nominalBand': .90,
              'coverage': {}, 'thresholds': {}}
    for key, values in methods.items():
        prediction = np.asarray(values)
        result['metrics'][key] = {str(h): {'mae': float(np.mean(np.abs(prediction[:,h-1]-actual[:,h-1]))),
                 'rmsle': float(np.sqrt(np.mean((np.log1p(prediction[:,h-1])-np.log1p(actual[:,h-1]))**2)))} for h in [6,12,24]}
    for h in [6,12,24]:
        result['coverage'][str(h)] = float(np.mean(np.asarray(coverage)[:,h-1]))
    # Evaluate threshold cases on once-per-day origins to reduce duplicate events.
    day_seen, daily = set(), []
    for j,t in enumerate(examples['times'][mask]):
        if t.date() not in day_seen:
            day_seen.add(t.date()); daily.append(j)
    for name, threshold in THRESHOLDS.items():
        truth = actual[daily,23] >= threshold
        probability = np.array([np.mean(windows[j][:,23] >= threshold) for j in daily])
        result['thresholds'][name] = {'value': threshold, 'dailyOrigins': len(daily),
            'exceedanceCount': int(truth.sum()), 'nonExceedanceCount': int((~truth).sum()),
            'brier': float(np.mean((probability-truth)**2)),
            'note': 'Once-per-day sample; consecutive storm days remain correlated. Not failure probabilities.'}
    return result


def fit(data, quality, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    examples = build_examples(data)
    masks = {s: split_mask(examples['times'], SPLITS[s+'Start'], SPLITS[s+'Stop']) for s in ['train','calibration','test']}
    if any(int(mask.sum()) < 40 for mask in masks.values()):
        raise ValueError('Insufficient data in a prespecified partition')
    x = examples['x']; y = np.log1p(examples['future']) - examples['base']
    estimator = forest().fit(x[masks['train']], y[masks['train']])
    # Each residual vector is an entire 24-hour path. Keep its temporal dependence.
    # Once-daily calibration origins reduce overlapping target windows.
    cal = np.flatnonzero(masks['calibration'])
    selected, last = [], None
    for idx in cal:
        t = examples['times'][idx]
        if last is None or t-last >= pd.Timedelta(hours=24):
            selected.append(idx); last=t
    residuals = y[selected] - estimator.predict(x[selected])
    logtest = examples['base'][masks['test']] + estimator.predict(x[masks['test']])
    report = score(data, examples, masks['test'], logtest, residuals)
    # Prespecified ablation: does wind improve the same estimator over electrons only?
    ne = examples['electronFeatureCount']
    electron_only = forest().fit(x[masks['train'],:ne], y[masks['train']])
    eresidual = y[selected] - electron_only.predict(x[selected,:ne])
    elog = examples['base'][masks['test']] + electron_only.predict(x[masks['test'],:ne])
    report['electronOnlyAblation'] = score(data, examples, masks['test'], elog, eresidual)['metrics']['WXF']
    report.update({'schemaVersion': VERSION, 'splits': SPLITS, 'quality': quality,
                   'partitionCounts': {s:int(m.sum()) for s,m in masks.items()},
                   'calibrationPaths': len(residuals), 'rejections': examples['rejected'],
                   'featureNames': examples['names'],
                   'forecastHorizonHours': 24, 'thresholdsMeaning': 'Office internal-charging exposure criteria; not satellite failure probabilities',
                   'verification': 'Retrospective archive evaluation. Input receipt times and forecast revisions are not available. Forward shadow verification required.'})
    reference = report['metrics']['diurnalPersistence']['24']
    wxf = report['metrics']['WXF']['24']
    report['releaseGate'] = {'beatsDiurnalAt24hMAE': wxf['mae'] < reference['mae'],
                             'beatsDiurnalAt24hRMSLE': wxf['rmsle'] < reference['rmsle'],
                             'coverageWithinFivePoints': abs(report['coverage']['24']-.9) <= .05,
                             'forwardVerified': False}
    artifact = {'version': VERSION, 'estimator': estimator, 'residuals': residuals,
                'featureNames': examples['names'], 'report': report,
                'trainingFeatureMin': x[masks['train']].min(axis=0),
                'trainingFeatureMax': x[masks['train']].max(axis=0)}
    if __package__:
        from .frozen import export_model
    else:
        from frozen import export_model
    export_model(artifact, out/'model.npz')
    (out/'evaluation.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ['partitionCounts','calibrationPaths','metrics','coverage','electronOnlyAblation','releaseGate']},indent=2),flush=True)
    return artifact


def predict(data, artifact, issued_at=None):
    issued_at = pd.Timestamp.now(tz='UTC') if issued_at is None else pd.Timestamp(issued_at)
    if issued_at.tzinfo is None:
        raise ValueError('UTC issue time required')
    eligible = data.loc[data.index <= issued_at - pd.Timedelta(minutes=10)]
    pos = len(eligible)-1
    # No fallback to an old apparently valid state: a gap produces an explicit withheld result.
    result = {'schemaVersion': VERSION, 'issuedAt': issued_at.isoformat(), 'horizonHours':24,
              'units':'electrons cm^-2 sr^-1', 'fluxUnits':'electrons cm^-2 s^-1 sr^-1',
              'window':'preceding rolling 24 hours', 'thresholds':THRESHOLDS,
              'status':'experimental', 'evaluation':artifact['report'],
              'limitations':['GEO GOES-19 local measurement; not a belt-wide or orbit-specific dose forecast.',
                  'The range is an empirical residual ensemble, not a guaranteed 90% confidence interval.',
                  'New CME/HSS arrivals absent from recent measurements are not explicitly forecast.',
                  'REFM UTC-day totals are a separate product, not rolling fluence.']}
    try:
        if pos < 167 or issued_at-eligible.index[-1] > pd.Timedelta(hours=2):
            raise ValueError('Electron/solar-wind data are stale')
        x, base, names, _ = features_at(eligible, pos)
        if names != artifact['featureNames']:
            raise ValueError('Model/input feature mismatch')
        logpoint = base + artifact['estimator'].predict(x[None,:])[0]
        paths = flux_from_log(logpoint + artifact['residuals'])
        past = eligible.flux.iloc[-24:].to_numpy()
        fluence = rolling_paths(past, paths, allow_observed_gaps=True)
        fq = np.quantile(fluence,[.05,.5,.95],axis=0)
        xq = np.quantile(paths,[.05,.5,.95],axis=0)
        times = pd.date_range(eligible.index[-1]+pd.Timedelta(hours=1),periods=24,freq='1h')
        number = lambda value: float(value) if np.isfinite(value) else None
        result.update({'dataAsOf':eligible.index[-1].isoformat(), 'observedFluence':number(past.sum()*3600),
            'completeObservedHours':int(np.isfinite(past).sum()),
            'forecast':[{'time':t.isoformat(),'low':number(fq[0,k]),'median':number(fq[1,k]),'high':number(fq[2,k]),
                         'fluxLow':float(xq[0,k]),'fluxMedian':float(xq[1,k]),'fluxHigh':float(xq[2,k])} for k,t in enumerate(times)],
            'history':[{'time':t.isoformat(),'flux':number(v)} for t,v in eligible.flux.iloc[-24:].items()],
            'drivers':{c:float(eligible[c].iloc[-3:].mean()) for c in ['speed','bz','pressure','coupling']},
            'outOfTrainingRange':[names[i] for i,v in enumerate(x) if v < artifact['trainingFeatureMin'][i] or v > artifact['trainingFeatureMax'][i]]})
    except ValueError as exc:
        result.update({'status':'withheld','reason':str(exc),'forecast':[]})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fit', action='store_true')
    args = parser.parse_args()
    data, quality = prepare(args.cache)
    args.output.mkdir(parents=True,exist_ok=True)
    data.to_csv(args.output/'hourly.csv')
    from frozen import load_model
    artifact = fit(data,quality,args.output) if args.fit else load_model(args.output/'model.npz')
    forecast = predict(data,artifact)
    (args.output/'forecast.json').write_text(json.dumps(forecast,indent=2,allow_nan=False)+'\n')
    print('Forecast status:',forecast['status'],forecast.get('reason',''),flush=True)
