"""Issue the frozen experimental model, preserving original timestamps and gaps."""
import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

if __package__:
    from .acquire import acquire
    from .model import VERSION, predict, prepare
    from .frozen import load_model
    from .arrivals import acquire as acquire_arrivals, ArrivalArchive
    from .impacts import acquire as acquire_impacts, ImpactArchive
else:
    from acquire import acquire
    from model import VERSION, predict, prepare
    from frozen import load_model
    from arrivals import acquire as acquire_arrivals, ArrivalArchive
    from impacts import acquire as acquire_impacts, ImpactArchive

HERE = Path(__file__).resolve().parent
FORECAST_URL = 'https://services.swpc.noaa.gov/text/3-day-forecast.txt'


def historical_summary():
    """Compact statistics for the recipe study, not scores of today's frozen run."""
    report = json.loads((HERE/'hindcast-evaluation.json').read_text())
    return {'schemaVersion': report['schemaVersion'], 'start': '2022-01-01', 'endExclusive': '2026-09-01',
        'foldCount': len(report['folds']), 'originCount': report['pooled']['originCount'],
        'dates': report['pooled']['dates'], 'eligibleOriginFraction': report['eligibleOriginFraction'],
        'models': report['pooled']['models'], 'pairedComparisons': report['pairedComparisons'],
        'qualification': report['qualification'],
        'meaning': 'Chronological out-of-sample recipe comparison. Each fold refits using only earlier training/calibration targets; these are not predictions from the currently deployed frozen artifacts.',
        'source': 'https://github.com/wreed1989/SpaceWxOps-WXF/blob/main/research/electron_fluence/hindcast-evaluation.json'}


def refresh(cache, output, evidence):
    now = datetime.now(timezone.utc)
    metadata = json.loads((HERE/'model-manifest.json').read_text())
    model_path = HERE/'model.npz'
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != metadata['modelSHA256']:
        raise ValueError('Model checksum does not match reviewed manifest')
    artifact = load_model(model_path)  # Numeric arrays only; allow_pickle=False.
    output, evidence = Path(output), Path(evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    try:
        acquire(cache, (now-timedelta(days=35)).strftime('%Y-%m-%d'), (now+timedelta(days=1)).strftime('%Y-%m-%d'))
        data, quality = prepare(cache)
        try:
            events, arrival_meta = acquire_arrivals(evidence/'scoreboard',
                (now-timedelta(days=21)).strftime('%Y-%m-%d'),now.strftime('%Y-%m-%d'))
            arrivals = ArrivalArchive(events)
            guidance_mode = 'CME arrival guidance + recurrence + observed drivers'
        except Exception as exc:
            arrivals = ArrivalArchive([],available=False)
            arrival_meta = {'source':'NASA CME Scoreboard','error':str(exc)[:200]}
            guidance_mode = 'CME feed unavailable; observed-driver + recurrence fallback'
        try:
            impacts,impact_meta=acquire_impacts(evidence/'donki-impacts',
                (now-timedelta(days=14)).strftime('%Y-%m-%d'),now.strftime('%Y-%m-%d'))
        except Exception as exc:
            impacts=ImpactArchive({},available=False)
            impact_meta={'error':str(exc)[:200]}
        issue = pd.Timestamp(datetime.now(timezone.utc))
        result = predict(data, artifact, issue, arrivals=arrivals)
        result['guidanceMode'] = 'Current WXF · observed drivers'
        result['arrivalSource'] = arrival_meta
        result['impactSource'] = impact_meta
        result['impactGuidance'] = impacts.context(pd.Timestamp(result.get('dataAsOf',issue)))
        # Candidate stays separate after failing the prespecified coverage gate.
        # An external-guidance or candidate failure must not remove current WXF.
        try:
            complete_guidance=arrivals.available and impacts.available
            candidate_path = HERE/('model-guidance.npz' if complete_guidance else 'model-no-cme.npz')
            key = 'candidateModelSHA256' if complete_guidance else 'fallbackModelSHA256'
            if hashlib.sha256(candidate_path.read_bytes()).hexdigest() != metadata[key]:
                raise ValueError('Candidate model checksum mismatch')
            candidate = predict(data,load_model(candidate_path),issue,arrivals=arrivals,impacts=impacts if complete_guidance else None)
            guidance_mode=('IPS/HSS phase + CME arrivals + recurrence + observed drivers' if complete_guidance else 'External guidance incomplete; observed-driver + recurrence fallback')
            candidate.update({'guidanceMode':guidance_mode,'modelSHA256':metadata[key],
                'promotionStatus':'Historical hindcasts support improvement over persistence, but do not establish added CME/HSS skill over measured drivers. Candidate remains separate.',
                'role':'shadow candidate'})
            result['candidate'] = candidate
        except Exception as exc:
            result['candidate'] = {'schemaVersion':VERSION,'issuedAt':issue.isoformat(),'status':'withheld',
                'reason':'Candidate unavailable: '+str(exc)[:200],'forecast':[],'role':'shadow candidate'}
        result['inputQuality'] = quality
    except Exception as exc:
        result = {'schemaVersion':VERSION, 'issuedAt':datetime.now(timezone.utc).isoformat(),
                  'status':'withheld', 'reason':'Input retrieval/quality failure: '+str(exc)[:240],
                  'forecast':[], 'evaluation':artifact['report']}
    result.setdefault('modelSHA256', metadata['modelSHA256'])
    result['historicalValidation'] = historical_summary()
    if isinstance(result.get('candidate'), dict):
        result['candidate']['historicalValidation'] = result['historicalValidation']
    # Preserve as-issued external guidance for later development/verification.
    # It is context, NOT secretly substituted for historical future observations.
    try:
        response = requests.get(FORECAST_URL,timeout=25); response.raise_for_status()
        if ':Issued:' not in response.text:
            raise ValueError('No bulletin issue time')
        (evidence/'swpc-3-day-forecast.txt').write_text(response.text)
        result['externalGuidance'] = {'source':FORECAST_URL,'retrievedAt':datetime.now(timezone.utc).isoformat(),
            'bulletin':response.text,'usedAsModelInput':False}
    except Exception as exc:
        result['externalGuidance'] = {'source':FORECAST_URL,'error':str(exc)[:200],'usedAsModelInput':False}
    # Preserve current CH geometry and recurrence issuance for future calibration.
    # No learned CH coefficient is claimed without a consistent historical series.
    try:
        current = json.loads((output.parent/'current.json').read_text())
        keep = ['id','latitude','longitude','cmd','areaDisk','areaFraction','areaPct','width','quantitative','time']
        result['coronalHoleGuidance'] = {'source':'WXF CH/HSS current.json',
            'observationTime':current.get('observationTime'),'availableAt':current.get('availableAt'),
            'measurementEngine':current.get('measurementEngine'),
            'holes':[{k:h[k] for k in keep if k in h} for h in current.get('holes',[])],
            'usedAsModelInput':False,'reason':'Consistent as-issued CH forecast history is still accumulating; 27-day wind recurrence is a separate trained predictor.'}
        recurrence = json.loads((output.parent/'recurrence.json').read_text())
        result['coronalHoleGuidance']['recurrencePublication'] = {k:recurrence.get(k) for k in ['generatedAt','source','coverage']}
    except (OSError,ValueError):
        result['coronalHoleGuidance'] = {'usedAsModelInput':False,'reason':'Current CH context unavailable'}
    try:
        huxt=json.loads((output.parent/'huxt-forecast.json').read_text())
        end=pd.Timestamp(huxt['issuedAt'])+pd.Timedelta(hours=24)
        future=[r for r in huxt.get('rows',[]) if pd.Timestamp(huxt['issuedAt'])<pd.Timestamp(r['time'])<=end]
        result['huxtGuidance']={k:huxt.get(k) for k in ['schemaVersion','issuedAt','status','reason','boundary','cmeInputs','source','qualification']}
        result['huxtGuidance'].update({'next24Hours':future,'usedAsModelInput':False,
            'reasonNotTrained':'Forward numerical HUXt archive just started. Historical boundary/run pairs must be evaluated before using predicted wind in place of measured wind.'})
    except (OSError,ValueError,KeyError):
        result['huxtGuidance']={'status':'unavailable','usedAsModelInput':False}
    serialized = json.dumps(result,indent=2,allow_nan=False)+'\n'
    output.write_text(serialized)
    (evidence/'issued-forecast.json').write_text(serialized)
    print('WXF experimental forecast:',result['status'],result.get('reason',''),flush=True)
    return result


def append_ledger(forecast, ledger):
    """One full set of 24 lead-time predictions per issue; never revise prior issues."""
    ledger = Path(ledger)
    result = json.loads(Path(forecast).read_text())
    keep = ['schemaVersion','issuedAt','dataAsOf','status','reason','modelSHA256','forecast',
            'observedFluence','completeObservedHours','outOfTrainingRange','externalGuidance',
            'predictorValues','arrivalGuidance','arrivalSource','guidanceMode','coronalHoleGuidance','modelVersion','thresholds','impactGuidance','impactSource','huxtGuidance']
    row = {k:result[k] for k in keep if k in result}
    if isinstance(result.get('candidate'),dict):
        row['candidate'] = {k:result['candidate'][k] for k in [*keep,'role','promotionStatus'] if k in result['candidate']}
    # Save the dated bulletin too: future Kp/arrival-conditioned models need issue history.
    ledger.parent.mkdir(parents=True,exist_ok=True)
    prior = ledger.read_text().splitlines() if ledger.exists() else []
    if any(json.loads(line).get('issuedAt') == row['issuedAt'] for line in prior):
        return
    with ledger.open('a') as handle:
        handle.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,default=Path('.electron-cache'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,default=Path('product/electron-evidence'))
    parser.add_argument('--ledger',type=Path)
    parser.add_argument('--append-only',action='store_true')
    args=parser.parse_args()
    if not args.append_only:
        refresh(args.cache,args.output,args.evidence)
    if args.ledger:
        append_ledger(args.output,args.ledger)
