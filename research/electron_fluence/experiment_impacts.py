import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from model import build_examples,split_mask,forest,score
from arrivals import load_archive as load_arrivals
from impacts import load_archive as load_impacts
from frozen import load_model,export_model
parser=argparse.ArgumentParser(description='Reproduce the post-IPS/HSS phase candidate on reused development dates; never auto-promote')
parser.add_argument('--hourly',type=Path,required=True);parser.add_argument('--arrivals',type=Path,required=True)
parser.add_argument('--impacts',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--arrival-evaluation',type=Path,default=Path(__file__).with_name('evaluation-arrivals-v02.json'))
args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
data=pd.read_csv(args.hourly,index_col=0,parse_dates=True)
e=build_examples(data,arrivals=load_arrivals(args.arrivals),impacts=load_impacts(args.impacts))
x=e['x'];y=np.log1p(e['future'])-e['base'];train=split_mask(e['times'],'2020-02-01','2026-03-01');cal=split_mask(e['times'],'2026-03-01','2026-06-01')
print('examples',len(x),'training',train.sum(),'features',len(e['names']),flush=True)
selected=[];last=None
for j in np.flatnonzero(cal):
 t=e['times'][j]
 if last is None or t-last>=pd.Timedelta(hours=24):selected.append(j);last=t
model=forest().fit(x[train],y[train]);res=y[selected]-model.predict(x[selected]);log=e['base']+model.predict(x)
report={'modelVersion':'WXF-EF-0.3','candidateOnly':True,'featureNames':e['names'],'metrics':{},'evaluation':{},
 'hypothesis':'Explicit submission-gated IPS/HSS phase and observed post-event electron response, plus causal wind-compression/rise timing.',
 'developmentNote':'Requested after inspecting the v0.2 comparison; all reused test dates are development data. Not a new independent validation.',
 'promotionStatus':'Shadow candidate only; prospective event-level verification required.'}
for name,start,stop in [('development','2026-06-01','2026-09-01'),('september','2026-09-01','2026-09-19')]:
 mask=split_mask(e['times'],start,stop);r=score(data,e,mask,log[mask],res)
 r['regimes']={}
 for kind in ['ips','hss']:
  group=mask&(x[:,e['names'].index(kind+'_age_hours')]<=72)
  if group.sum():r['regimes'][kind+'ReportedLast72h']=score(data,e,group,log[group],res)
 report['evaluation'][name]=r
 print(name,r['metrics']['WXF']['24'],r['coverage'], 'regimes',{k:v['originCount'] for k,v in r['regimes'].items()},flush=True)
base=json.loads(args.arrival_evaluation.read_text())
full={**base,**report['evaluation']['development'],'modelVersion':'WXF-EF-0.3','impactExperiment':report,
 'featureNames':e['names'],'septemberEvaluation':report['evaluation']['september'],
 'releaseGate':{**base['releaseGate'],'experimentalPromotion':False,'forwardVerified':False},
 'publicationDecision':'Keep current v0.1 default. Explicit IPS/HSS-phase model is a shadow candidate, evaluated on previously inspected development dates.'}
full['releaseGate']['coverageWithinFivePoints']=abs(full['coverage']['24']-.9)<=.05
full['releaseGate']['independentValidation']=False
full.pop('pairedComparisons',None)
artifact={'version':'WXF-EF-0.3','estimator':model,'residuals':res,'featureNames':e['names'],'report':full,
 'trainingFeatureMin':x[train].min(axis=0),'trainingFeatureMax':x[train].max(axis=0)}
export_model(artifact,out/'model.npz');(out/'evaluation.json').write_text(json.dumps(full,indent=2,allow_nan=False)+'\n')
frozen=load_model(out/'model.npz');chosen=np.random.default_rng(1989).choice(len(x),200,replace=False)
(out/'export-verification.json').write_text(json.dumps({'randomFeatureVectors':200,'maximumAbsoluteLogPredictionDifference':float(np.max(np.abs(model.predict(x[chosen])-frozen['estimator'].predict(x[chosen]))))},indent=2)+'\n')
