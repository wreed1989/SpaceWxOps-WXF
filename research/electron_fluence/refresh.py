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
else:
    from acquire import acquire
    from model import VERSION, predict, prepare
    from frozen import load_model

HERE = Path(__file__).resolve().parent
FORECAST_URL = 'https://services.swpc.noaa.gov/text/3-day-forecast.txt'


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
        acquire(cache, (now-timedelta(days=9)).strftime('%Y-%m-%d'), (now+timedelta(days=1)).strftime('%Y-%m-%d'))
        data, quality = prepare(cache)
        result = predict(data, artifact, pd.Timestamp(datetime.now(timezone.utc)))
        result['inputQuality'] = quality
    except Exception as exc:
        result = {'schemaVersion':VERSION, 'issuedAt':datetime.now(timezone.utc).isoformat(),
                  'status':'withheld', 'reason':'Input retrieval/quality failure: '+str(exc)[:240],
                  'forecast':[], 'evaluation':artifact['report']}
    result['modelSHA256'] = metadata['modelSHA256']
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
            'observedFluence','completeObservedHours','outOfTrainingRange','externalGuidance']
    row = {k:result[k] for k in keep if k in result}
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
