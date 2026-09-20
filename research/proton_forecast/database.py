"""Build a source-checked SQLite verification database and score a frozen WXF model.

Run --cache to build once. Omit --cache to rescore the database without raw files.
The database stores all acquired observations, flare records, partitions, inputs,
truth-quality diagnostics, model versions, predictions, and evaluation runs.
"""
import argparse
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from .model import FEATURES, TARGETS, predict
from .verification import metrics, block_intervals

HERE=Path(__file__).parent


def clean(v):
    if isinstance(v, dict): return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v, (list,tuple)): return [clean(x) for x in v]
    if isinstance(v, np.generic): v=v.item()
    if isinstance(v, float) and not math.isfinite(v): return None
    return v


def encoded(v): return json.dumps(clean(v),separators=(',',':'),allow_nan=False)
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def stamp(seconds): return datetime.fromtimestamp(int(seconds),timezone.utc).isoformat().replace('+00:00','Z')
def epoch(value): return int(pd.Timestamp(value).timestamp())


def partitions(df):
    t=pd.to_datetime(df.time,utc=True);reg=pd.to_numeric(df.region,errors='coerce').where(lambda r:r>0)
    train=t<'2014-12-18';cal=(t>='2015-01-15')&(t<'2021-12-18');test=t>='2022-01-15'
    cross=set(reg[train].dropna()) & set(reg[cal|test].dropna());train &= ~reg.isin(cross)
    cross2=set(reg[cal].dropna()) & set(reg[test].dropna());cal &= ~reg.isin(cross2)
    return np.select([train,cal,test],['training','calibration','test'],default='embargo_or_region_purge')


def truth(times, series, issue, target):
    """Independently rebuild the frozen target definition from a five-minute grid."""
    lo=np.searchsorted(times,issue);hi=np.searchsorted(times,issue+86400)
    future=series[lo:hi][:288];before=series[np.searchsorted(times,issue-900):lo]
    valid=np.isfinite(future);coverage=float(valid.mean()) if len(future) else 0
    gap=max_gap=0
    for ok in valid:
        gap=0 if ok else gap+1;max_gap=max(max_gap,gap)
    active_limit=10 if target=='p10_40' else TARGETS[target][1]
    known=len(before)>=3 and np.isfinite(before).all()
    active=bool((before>=active_limit).all()) if known else None
    reasons=[]
    if len(future)<288:reasons.append('incomplete_window')
    if coverage<.95:reasons.append('truth_coverage_below_95_percent')
    if max_gap>6:reasons.append('truth_gap_over_30_minutes')
    if not known:reasons.append('baseline_unknown')
    elif active:reasons.append('already_active')
    above=future>TARGETS[target][1] if target=='p10_40' else future>=TARGETS[target][1]
    crossings=np.flatnonzero(above[2:] & above[1:-1] & above[:-2])+2
    label=int(len(crossings)>0) if not reasons else None
    return dict(label=label,exclusion=';'.join(reasons) or None,coverage=coverage,maxGapMinutes=max_gap*5,alreadyActive=active,
                observedPeak=float(np.nanmax(future)) if valid.any() else None,
                crossingConfirmed=stamp(times[lo+crossings[0]]) if len(crossings) and not reasons else None)


def build_database(cache, database, manifest_path=HERE/'input-manifest.json'):
    cache, database=Path(cache),Path(database)
    manifest=json.loads(Path(manifest_path).read_text());sources=manifest['sources']
    if any('error' in r for r in sources):raise ValueError('Source manifest contains acquisition failures')
    for r in sources:
        if digest(cache/r['file'])!=r['sha256']:raise ValueError('Source checksum mismatch: '+r['file'])
    if digest(cache/'features.csv.gz')!=manifest['featureSHA256']:raise ValueError('Feature checksum mismatch')
    if database.exists():raise FileExistsError(f'Database already exists; omit --cache to rescore: {database}')
    database.parent.mkdir(parents=True,exist_ok=True);temporary=database.with_suffix('.building.sqlite')
    if temporary.exists():raise FileExistsError(temporary)
    db=sqlite3.connect(temporary);db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE source_files(file TEXT PRIMARY KEY,url TEXT NOT NULL,sha256 TEXT NOT NULL,retrieved_at TEXT,bytes INTEGER);
    CREATE TABLE observations(time INTEGER PRIMARY KEY,P10 REAL CHECK(P10>=0),P50 REAL CHECK(P50>=0),satellite TEXT,source_file TEXT REFERENCES source_files(file));
    CREATE TABLE flares(id INTEGER PRIMARY KEY,peak_time INTEGER,start_time INTEGER,flare_class TEXT,source_file TEXT REFERENCES source_files(file),record_json TEXT);
    CREATE INDEX flare_peak ON flares(peak_time);
    CREATE TABLE forecast_cases(case_id TEXT PRIMARY KEY,peak_time INTEGER,valid_start INTEGER,valid_end INTEGER,partition TEXT,flare_id INTEGER REFERENCES flares(id),features_json TEXT,input_eligible INTEGER,input_note TEXT);
    CREATE TABLE outcomes(case_id TEXT REFERENCES forecast_cases(case_id),target TEXT,label INTEGER CHECK(label IN (0,1)),exclusion TEXT,truth_coverage REAL,max_gap_minutes INTEGER,already_active INTEGER,observed_peak_pfu REAL,crossing_confirmed_utc TEXT,PRIMARY KEY(case_id,target));
    CREATE TABLE models(model_id TEXT PRIMARY KEY,version TEXT,model_json TEXT,imported_at TEXT);
    CREATE TABLE predictions(model_id TEXT REFERENCES models(model_id),case_id TEXT REFERENCES forecast_cases(case_id),target TEXT,probability REAL CHECK(probability BETWEEN 0 AND 1),PRIMARY KEY(model_id,case_id,target));
    CREATE TABLE evaluations(model_id TEXT REFERENCES models(model_id),scope TEXT,decision_probability REAL,generated_at TEXT,report_json TEXT,PRIMARY KEY(model_id,scope,decision_probability));
    ''')
    db.executemany('INSERT INTO source_files VALUES(?,?,?,?,?)',[(r['file'],r['url'],r['sha256'],r['retrievedAt'],r['bytes']) for r in sources])
    frames=[];flare_id_by_peak={};flare_count=0
    for source in sources:
        name=source['file']
        if name.startswith('particles-'):
            d=pd.read_csv(cache/name,header=None,names=['time','P10','P50','satellite'])
            d['epoch']=pd.to_datetime(d.time,utc=True).dt.as_unit('ns').astype('int64')//10**9
            for ch in ('P10','P50'):d[ch]=pd.to_numeric(d[ch],errors='coerce').where(lambda x:np.isfinite(x)&(x>=0))
            rows=[(int(t),clean(a),clean(b),str(sat),name) for t,a,b,sat in d[['epoch','P10','P50','satellite']].itertuples(index=False,name=None)]
            db.executemany('INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?)',rows);frames.append(d[['epoch','P10','P50']])
        elif name.startswith('flares-'):
            for r in pd.read_csv(cache/name).to_dict('records'):
                peak=epoch(r['time']);flare_count+=1;flare_id_by_peak.setdefault(peak,flare_count)
                db.execute('INSERT INTO flares VALUES(?,?,?,?,?,?)',(flare_count,peak,epoch(r['start_time']),r['flare_class'],name,encoded(r)))
    flux=pd.concat(frames,ignore_index=True).drop_duplicates('epoch').set_index('epoch').sort_index()
    times=np.arange(flux.index.min(),flux.index.max()+300,300,dtype=np.int64);flux=flux.reindex(times)
    data=flux[['P10','P50']].to_numpy(float);features=pd.read_csv(cache/'features.csv.gz');split=partitions(features)
    cases=[];outcomes=[];mismatches=[]
    for i,r in features.iterrows():
        issue=epoch(r.time);peak=issue-600;identity=stamp(peak);at=np.searchsorted(times,peak)
        prior=data[max(0,at-288):at];recent=prior[-3:]
        usable=len(prior)==288 and ((np.isfinite(prior).sum(axis=0)>=240).all()) and (np.isfinite(recent).all(axis=1).any())
        cases.append((identity,peak,issue,issue+86400,split[i],flare_id_by_peak.get(peak),encoded([r[k] for k in FEATURES]),int(usable),None if usable else 'Does not satisfy current live pre-flare coverage gate'))
        for target,(channel,_) in TARGETS.items():
            result=truth(times,data[:,0 if channel=='P10' else 1],issue,target)
            expected=None if pd.isna(r[target]) else int(r[target])
            if result['label']!=expected:mismatches.append((identity,target,expected,result['label']))
            outcomes.append((identity,target,result['label'],result['exclusion'],result['coverage'],result['maxGapMinutes'],result['alreadyActive'],result['observedPeak'],result['crossingConfirmed']))
    if mismatches:
        db.close();raise ValueError(f'Truth audit differs from frozen labels: {len(mismatches)}; first {mismatches[:3]}')
    db.executemany('INSERT INTO forecast_cases VALUES(?,?,?,?,?,?,?,?,?)',cases)
    db.executemany('INSERT INTO outcomes VALUES(?,?,?,?,?,?,?,?,?)',outcomes)
    info=dict(schemaVersion='WXF-SEP-DB-1',createdAt=datetime.now(timezone.utc).isoformat(),sourceFiles=len(sources),sourceManifestSHA256=digest(manifest_path),featureSHA256=manifest['featureSHA256'],observationStart=stamp(times[0]),observationEnd=stamp(times[-1]),forecastCases=len(cases),flareReports=flare_count,truthAuditMismatches=0,partitions=pd.Series(split).value_counts().to_dict())
    db.executemany('INSERT INTO metadata VALUES(?,?)',[(k,encoded(v)) for k,v in info.items()]);db.commit()
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failure')
    db.close();temporary.rename(database)
    print('Database built:',encoded(info),flush=True)


def score_database(database, model_path=HERE/'model.json', decision=.2):
    if not Path(database).is_file():raise FileNotFoundError(database)
    fitted=json.loads(Path(model_path).read_text())
    if fitted['features']!=FEATURES:raise ValueError('Model feature schema does not match database')
    identity=digest(model_path);db=sqlite3.connect(database);db.row_factory=sqlite3.Row
    version=db.execute("SELECT value FROM metadata WHERE key='schemaVersion'").fetchone()
    if not version or json.loads(version[0])!='WXF-SEP-DB-1':raise ValueError('Unsupported verification database')
    now=datetime.now(timezone.utc).isoformat();db.execute('INSERT OR IGNORE INTO models VALUES(?,?,?,?)',(identity,fitted['version'],encoded(fitted),now))
    predictions=[]
    for row in db.execute('SELECT case_id,features_json FROM forecast_cases'):
        probabilities=predict(json.loads(row['features_json']),fitted)
        predictions.extend((identity,row['case_id'],key,p) for key,p in probabilities.items())
    db.executemany('INSERT OR REPLACE INTO predictions VALUES(?,?,?,?)',predictions)
    report=dict(schemaVersion='WXF-SEP-VERIFY-1',generatedAt=now,modelVersion=fitted['version'],modelSHA256=identity,dataset={r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM metadata')},targets={})
    report['dataset']['observationRows']=db.execute('SELECT count(*) FROM observations').fetchone()[0]
    report['dataset']['sourceProvenance']='Full acquired GOES primary P10/P50 archive and NCEI flare reports; checksums verified before import.'
    for target,m in fitted['models'].items():
        rows=db.execute('''SELECT c.valid_start,c.input_eligible,o.label,p.probability,o.exclusion FROM forecast_cases c
          JOIN outcomes o USING(case_id) JOIN predictions p ON p.case_id=c.case_id AND p.target=o.target
          WHERE c.partition='test' AND o.target=? AND p.model_id=? ORDER BY c.valid_start''',(target,identity)).fetchall()
        scored=[r for r in rows if r['label'] is not None];y=np.array([r['label'] for r in scored]);p=np.array([r['probability'] for r in scored]);times=[stamp(r['valid_start']) for r in scored]
        result=metrics(y,p,m['baseRate'],decision);result.update(block_intervals(times,y,p,m['baseRate'],decision))
        result['decisionSweep']=[metrics(y,p,m['baseRate'],t) for t in [.05,.1,.2,.3,.5]]
        result['withheld']=len(rows)-len(scored);result['excludedReasons']={str(k):int(v) for k,v in pd.Series([r['exclusion'] for r in rows if r['label'] is None]).value_counts().items()}
        current=[r for r in scored if r['input_eligible']]
        result['liveCoverageSubset']=metrics([r['label'] for r in current],[r['probability'] for r in current],m['baseRate'],decision) if current else None
        result['byYear']={str(year):metrics(y[mask],p[mask],m['baseRate'],decision) for year in sorted({t[:4] for t in times}) if (mask:=np.array([t[:4]==year for t in times])).any()}
        report['targets'][target]=result
    report['limitations']=['Counts are flare-triggered forecast windows, not independent solar-proton events or causal flare associations.',
        'Historical inputs are finalized archives; this is a hindcast, not a replay of operational feed delays.',
        'Training 2010–2014, calibration 2015–2021, evaluation 2022–2026 with the existing boundary embargo and region purge. No fitting or threshold optimization occurs here.',
        'The 20% decision cutoff is a fixed reporting point. Do not tune future model choices on these already-inspected evaluation years.',
        'Brier skill uses the stored training event rate. Uncertainty resamples 14-day calendar blocks, not individual overlapping forecasts.',
        'Peak-flux/timing relations and SWPC PROTONS skill are not validated by these occurrence-probability scores.']
    db.execute('INSERT OR REPLACE INTO evaluations VALUES(?,?,?,?,?)',(identity,'frozen_heldout_windows',decision,now,encoded(report)));db.commit();db.close();return report


def write_report(report, path):
    d=report['dataset'];pct=lambda x:'—' if x is None else f'{100*x:.1f}%'
    lines=['# WXF Proton Model verification','',f"Frozen model: **{report['modelVersion']}**. Generated {report['generatedAt']}.",'',
        f"Database: **{d['observationRows']:,} five-minute observation records**, **{d['flareReports']:,} flare reports**, and **{d['forecastCases']:,} forecast cases**.",
        f"Particle coverage: {d['observationStart']} through {d['observationEnd']}. All {d['sourceFiles']} source-file checksums passed; rebuilt truth labels match the original dataset with zero mismatches.",'',
        '| Target | Scored / positive windows | Brier skill (95% interval) | Detection at 20% | False-alarm ratio | Hits / false alarms / misses / correct negatives |',
        '|---|---:|---|---:|---:|---|']
    for key,v in report['targets'].items():
        interval=' to '.join(pct(x) for x in v['brierSkill95']);lines.append(f"| {key} | {v['n']:,} / {v['events']:,} | {pct(v['brierSkill'])} ({interval}) | {pct(v['POD'])} | {pct(v['FAR'])} | {v['hits']} / {v['falseAlarms']} / {v['misses']} / {v['correctNegatives']} |")
    lines+=['','p10_10: ≥10 MeV ≥10 pfu; p10_40: ≥10 MeV >40 pfu; p50_10: ≥50 MeV ≥10 pfu. An event requires three consecutive five-minute threshold crossings within the fixed 24-hour window beginning ten minutes after the flare peak.','',
        '**Interpretation:** this baseline has low detection at the illustrative 20% probability cutoff (a WXF scoring choice, not a PROTONS requirement). The 50 MeV model issues no positive decisions at that cutoff, so its false-alarm ratio is undefined—not zero. Its Brier-skill interval crosses zero. These results do not establish skill parity with PROTONS.','',
        '## What is stored','',
        'SQLite tables: `source_files`, `observations`, `flares`, `forecast_cases`, `outcomes`, `models`, `predictions`, `evaluations`, and `metadata`. Raw flare records retain their additional fields for future model development. Forecast cases retain the original train/calibration/test assignment. Outcomes record exclusions, truth coverage, maximum gap, observed window maximum and threshold-confirmation time. Models and evaluations are keyed by SHA-256 so additional versions can be compared without replacing the reference model.','',
        '## Limits','']+['- '+x for x in report['limitations']]+['','## Metric definitions','',
        'Detection = hits / (hits + misses). False-alarm ratio = false alarms / (hits + false alarms). False-positive rate is a different statistic, false alarms / observed non-events. Brier score measures squared probability error; lower is better. Positive Brier skill improves on the fixed training climatology. ROC AUC measures ranking, not calibration. Reliability bins compare forecast probability with observed frequency. The JSON report also contains 95% block intervals, per-year results, excluded-window reasons and the subset satisfying today’s live-input coverage rule.','',
        '## Reproduce','',
        'From the repository, run:', '', '```sh', 'python -m research.proton_forecast.database --database /path/to/WXF_Proton_Verification.sqlite --output /path/to/report-directory', '```','',
        'Add `--cache /path/to/proton-history` only when creating a new database. The build requires the exact source and feature checksums in the committed input manifest. `--model /path/to/candidate.json` can add a compatible frozen model for comparison; no training happens during verification.','',
        f"Model SHA-256: `{report['modelSHA256']}`", f"Feature SHA-256: `{d['featureSHA256']}`",'']
    if report.get('contextAudit'):
        a=report['contextAudit'];lines+=['## Pre-flare episode audit','',a['description'],'','The original scores above are retained for reproducibility. The following subset additionally requires no sustained pre-flare crossing and sufficient input coverage. It is a retrospective diagnostic of the same weights, not evidence of improved model skill.','','| Target | Scored / positive | Recent-event exclusions | Brier skill |','|---|---:|---:|---:|']
        for key,r in a['targets'].items():
            v=r['statistics']
            if v:lines.append(f"| {key} | {v['n']:,} / {v['events']:,} | {r['excludedRecent']:,} | {pct(v['brierSkill'])} |")
        lines+=['','The 20% probability cutoff is an illustrative WXF verification setting, not a pfu threshold or a PROTONS requirement. Probability scores do not require this cutoff. The JSON audit includes decision cutoffs of 5%, 10%, 20%, 30% and 50% to make the sensitivity visible.','']
    Path(path).write_text('\n'.join(lines))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache',type=Path);parser.add_argument('--database',type=Path,required=True);parser.add_argument('--model',type=Path,default=HERE/'model.json');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.cache:build_database(args.cache,args.database)
    from .audit import audit_database
    report=audit_database(args.database,score_database(args.database,args.model));args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'verification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');write_report(report,args.output/'WXF_Proton_Verification.md')
    print(encoded({k:{n:v[n] for n in ['n','events','brierSkill','POD','FAR']} for k,v in report['targets'].items()}))
if __name__=='__main__':main()
