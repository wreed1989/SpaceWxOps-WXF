"""Score only issued core-area outlooks; missing/withheld targets remain explicit.
No fitting or operational promotion. The archive and live detectors differ.
"""
from __future__ import annotations
import json,sys,math
from pathlib import Path
from datetime import datetime,timezone

def metrics(rows):
    paired=[r for r in rows if r.get('issued') and r.get('observedSpeed') is not None and r.get('recurrenceSpeed') is not None]
    if not paired:return {'n':0,'mae':None,'rmse':None,'bias':None,'recurrenceMae':None,'maeSkillVsRecurrence':None}
    errors=[r['forecastSpeed']-r['observedSpeed'] for r in paired];base=[r['recurrenceSpeed']-r['observedSpeed'] for r in paired]
    n=len(paired);mae=sum(map(abs,errors))/n;bm=sum(map(abs,base))/n
    return {'n':n,'mae':mae,'rmse':math.sqrt(sum(x*x for x in errors)/n),'bias':sum(errors)/n,'recurrenceMae':bm,'maeSkillVsRecurrence':1-mae/bm if bm else None}

def gate(out):
    out=Path(out);h=json.loads((out/'history.json').read_text());v=json.loads((out/'validation.json').read_text());st=json.loads((out/'backfill_status.json').read_text())
    rec={r['day']:r for r in h['records']}
    for row in v['pairs']:
        a=rec[row['day']]['window'][row['core']]['A']
        if not 0<=a<=1:raise ValueError('Invalid core fraction')
        if abs(row['forecastSpeed']-(350+900*a))>1e-6:raise ValueError('Forecast does not match declared area relation')
        row['issued']=a>=.02;row['withheldReason']=None if row['issued'] else 'Core fill below 2%: no quantitative outlook issued'
    cutoff=v['partition']['cutoff'];hold=[r for r in v['pairs'] if r['day']>=cutoff]
    v['metrics']={'allCompleteCaseIssuances':metrics(v['pairs']),'temporalHoldout':metrics(hold),'byCore':{k:metrics([r for r in hold if r['core']==k]) for k in 'EMW'}}
    v['issuanceRule']='A >= 0.02 in the 20-degree core; below-threshold cases are withheld, never scored as 350 km/s forecasts'
    v['counts']={'candidateCoreDays':len(v['pairs']),'issuedCoreDays':sum(r['issued'] for r in v['pairs']),'withheldCoreDays':sum(not r['issued'] for r in v['pairs']),'pairedIssuedCoreDays':v['metrics']['allCompleteCaseIssuances']['n']}
    v['qualification']={'status':'not-promoted','reason':'Core-area relation underperforms matched 27-day recurrence on this archive' if v['metrics']['temporalHoldout']['maeSkillVsRecurrence'] is not None and v['metrics']['temporalHoldout']['maeSkillVsRecurrence']<=0 else 'Further independent detector and forward verification required','operationallyValidated':False,'liveDetectorValidated':False}
    v['generatedAt']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    st.update(completePairs=v['counts']['pairedIssuedCoreDays'],withheldCoreDays=v['counts']['withheldCoreDays'],historicalPolarity='Whole-hole catalogue metadata only; per-core signed HMI backfill is separate',generatedAt=v['generatedAt'])
    for name,obj in [('validation.json',v),('backfill_status.json',st)]:
        (out/name).write_text(json.dumps(obj,indent=2,allow_nan=False))
    print(json.dumps(st));return v
if __name__=='__main__':gate(sys.argv[1] if len(sys.argv)>1 else 'chhss-data')
