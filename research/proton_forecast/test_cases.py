"""Export illustrative held-out cases without creating extra verification samples."""
import argparse
import json
import sqlite3
from pathlib import Path
from .database import HERE, clean, stamp, digest, epoch

CASES=[
 ('2025-11-11T08:09:00Z','Threshold crossing · M1.4 · 11 Nov 2025','All three thresholds were crossed within this forecast window. At 20%, the baseline catches the first target and misses the other two. A window outcome does not prove this flare caused the proton event.'),
 ('2026-04-24T01:07:00Z','No crossing · X2.4 · 24 Apr 2026','No target was crossed within the window despite an X-class flare. A large flare alone does not guarantee a proton event.'),
 ('2025-02-25T11:59:00Z','False alarm · M3.6 · 25 Feb 2025','At the fixed 20% cutoff, the first target is a false alarm. None of the three thresholds was crossed within the window.')]


def export_cases(database, model_path=HERE/'model.json'):
    db=sqlite3.connect(database);db.row_factory=sqlite3.Row;model_id=digest(model_path);cases=[]
    for identity,title,description in CASES:
        case=db.execute('SELECT c.*,f.record_json,f.source_file FROM forecast_cases c JOIN flares f ON f.id=c.flare_id WHERE case_id=?',(identity,)).fetchone()
        if not case or case['partition']!='test' or not case['input_eligible']:raise ValueError('Test case is not a usable held-out forecast: '+identity)
        f=json.loads(case['record_json']);lon=f.get('flare_loc_swpc_hgs_lon');lat=f.get('flare_loc_swpc_hgs_lat')
        if lon is None:lon=f.get('flare_loc_xrs_hgs_lon')
        if lat is None:lat=f.get('flare_loc_xrs_hgs_lat')
        if lon is not None and abs(lon)>90:lon=None
        if lat is not None and abs(lat)>90:lat=None
        sources=[dict(r) for r in db.execute('SELECT * FROM source_files WHERE file=? OR file IN (SELECT DISTINCT source_file FROM observations WHERE time BETWEEN ? AND ?)',(case['source_file'],case['peak_time']-86400,case['valid_end']))]
        flare_url=next(s['url'] for s in sources if s['file']==case['source_file'])
        event=dict(peakTime=identity,startTime=stamp(epoch(f['start_time'])),flareClass=f['flare_class'],peakFlux=f['xrsb_irrad'],riseMinutes=(case['peak_time']-epoch(f['start_time']))/60,longitude=lon,latitude=lat,
                   integral=f.get('integrated_irrad_end'),integralEnd=stamp(epoch(f['end_time'])),previous='unknown',previousIntegral=None,region=f.get('active_region'),
                   inputSources={'flare':flare_url,'location':flare_url,'integral':flare_url},locationMethod='NOAA NCEI archived flare location',inputNotes=['Historical test: finalized archived measurements, not live operational availability.'])
        observations=[dict(time=stamp(r['time']),P10=r['P10'],P50=r['P50']) for r in db.execute('SELECT time,P10,P50 FROM observations WHERE time>=? AND time<? ORDER BY time',(case['peak_time']-86400,case['valid_end']))]
        raw_flares=[]
        for row in db.execute('SELECT peak_time,record_json FROM flares WHERE peak_time>=? AND peak_time<? ORDER BY peak_time,id',(case['peak_time']-86400,case['peak_time'])):
            record=json.loads(row['record_json']);raw_flares.append({'max_time':stamp(row['peak_time']),'max_xrlong':record['xrsb_irrad']})
        raw_flares=list({r['max_time']:r for r in raw_flares}.values())
        outcomes={r['target']:dict(r) for r in db.execute('SELECT target,label,exclusion,truth_coverage,observed_peak_pfu,crossing_confirmed_utc FROM outcomes WHERE case_id=?',(identity,))}
        expected={r['target']:r['probability'] for r in db.execute('SELECT target,probability FROM predictions WHERE case_id=? AND model_id=?',(identity,model_id))}
        cases.append(dict(id=identity,title=title,description=description,event=clean(event),partition='test',modelSHA256=model_id,validStart=stamp(case['valid_start']),validEnd=stamp(case['valid_end']),outcomes=outcomes,expectedProbabilities=expected,
            data=dict(generatedAt=stamp(case['valid_end']),events=[clean(event)],observations=observations,rawFlares=raw_flares,flareHistoryStart=stamp(case['peak_time']-86400)),sources=sources))
    db.close();return {'schemaVersion':'WXF-SEP-TESTS-1','note':'Illustrative examples selected from the existing test partition. They are counted once in the full verification database, never added as new samples.','cases':cases}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',type=Path,required=True);p.add_argument('--output',type=Path,default=HERE/'test-cases.json');a=p.parse_args()
    a.output.write_text(json.dumps(export_cases(a.database),separators=(',',':'),allow_nan=False)+'\n')
