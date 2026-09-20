"""Add a pre-flare episode audit without changing frozen outcomes or model weights."""
import json
import sqlite3
import numpy as np
import pandas as pd
from .episode import channel_context, POLICY
from .verification import metrics, block_intervals

def audit_database(database, report):
    from .database import stamp, encoded
    db=sqlite3.connect(database);db.row_factory=sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS episode_context(
      policy TEXT,case_id TEXT,channel TEXT,status TEXT,coverage REAL,max_gap_minutes INTEGER,last_above TEXT,
      PRIMARY KEY(policy,case_id,channel))''')
    flux=pd.read_sql_query('SELECT time,P10,P50 FROM observations ORDER BY time',db).set_index('time')
    rows=[]
    for c in db.execute('SELECT case_id,peak_time FROM forecast_cases'):
        peak=c['peak_time'];last=((peak-1)//300)*300
        prior=flux.reindex(np.arange(last-287*300,last+1,300)).reset_index().to_dict('records')
        for ch in ['P10','P50']:
            ctx=channel_context(prior,ch);last_above=stamp(ctx['lastAbove']) if ctx['lastAbove'] is not None else None
            rows.append((POLICY,c['case_id'],ch,ctx['status'],ctx['coverage'],ctx['maxGapMinutes'],last_above))
    db.executemany('INSERT OR REPLACE INTO episode_context VALUES(?,?,?,?,?,?,?)',rows)
    model=json.loads(db.execute('SELECT model_json FROM models WHERE model_id=?',(report['modelSHA256'],)).fetchone()[0])
    audit=dict(policy=POLICY,description='Diagnostic subset with no sustained ≥10 pfu crossing in the preceding 24 hours. Recent activity alone does not withhold a forecast; it can precede a renewed crossing. This is not an official event-end rule or a newly calibrated model.',targets={})
    for key,ch in [('p10_10','P10'),('p10_40','P10'),('p50_10','P50')]:
        samples=db.execute('''SELECT c.valid_start,c.input_eligible,o.label,e.status,p.probability
          FROM forecast_cases c JOIN outcomes o USING(case_id) JOIN episode_context e USING(case_id)
          JOIN predictions p ON p.case_id=c.case_id AND p.target=o.target
          WHERE c.partition='test' AND o.target=? AND e.channel=? AND e.policy=? AND p.model_id=? ORDER BY c.valid_start''',(key,ch,POLICY,report['modelSHA256'])).fetchall()
        original=[r for r in samples if r['label'] is not None]
        usable=[r for r in original if r['status']=='clear' and r['input_eligible']]
        y=[r['label'] for r in usable];p=[r['probability'] for r in usable];base=model['models'][key]['baseRate']
        v=metrics(y,p,base) if usable else None
        if v:
            v.update(block_intervals([stamp(r['valid_start']) for r in usable],y,p,base))
            v['decisionSweep']=[metrics(y,p,base,t) for t in [.05,.1,.2,.3,.5]]
        audit['targets'][key]=dict(statistics=v,originalScored=len(original),excludedRecent=sum(r['status']=='recent' for r in original),excludedUnknown=sum(r['status']=='unknown' for r in original),excludedInputCoverage=sum(r['status']=='clear' and not r['input_eligible'] for r in original))
    report['contextAudit']=audit
    db.execute('INSERT OR REPLACE INTO evaluations VALUES(?,?,?,?,?)',(report['modelSHA256'],POLICY,.2,report['generatedAt'],encoded(audit)))
    db.commit();db.close();return report
