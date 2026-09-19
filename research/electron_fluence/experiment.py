"""Reproduce the prespecified arrival/recurrence experiment; never auto-promote a model."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
try:
    from .model import forest,split_mask,score,flux_from_log,SPLITS,VERSION,prepare,build_examples
    from .arrivals import load_archive
    from .frozen import export_model,load_model
except ImportError:
    from model import forest,split_mask,score,flux_from_log,SPLITS,VERSION,prepare,build_examples
    from arrivals import load_archive
    from frozen import export_model,load_model

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--cache',type=Path,required=True)
parser.add_argument('--arrivals',type=Path,required=True)
parser.add_argument('--previous-model',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
out=args.output;out.mkdir(parents=True,exist_ok=True)
d,quality=prepare(args.cache)
d.to_csv(out/'hourly.csv')
e=build_examples(d,arrivals=load_archive(args.arrivals))
(out/'quality.json').write_text(json.dumps(quality,indent=2)+'\n')
x=e['x'];y=np.log1p(e['future'])-e['base'];names=e['names']
train=split_mask(e['times'],SPLITS['trainStart'],SPLITS['trainStop']);cal=split_mask(e['times'],SPLITS['calibrationStart'],SPLITS['calibrationStop'])
masks={'development':split_mask(e['times'],'2026-06-01','2026-09-01'),'september':split_mask(e['times'],'2026-09-01','2026-09-19')}
selected=[];last=None
for j in np.flatnonzero(cal):
 t=e['times'][j]
 if last is None or t-last>=pd.Timedelta(hours=24):selected.append(j);last=t
variants={
 'longHistoryObserved':[j for j,n in enumerate(names) if not n.startswith(('cme_','recurrence_'))],
 'longHistoryRecurrence':[j for j,n in enumerate(names) if not n.startswith('cme_')],
 'longHistoryArrivals':[j for j,n in enumerate(names) if not n.startswith('recurrence_')],
 'fullGuidance':list(range(len(names)))}
reports={};errors={}
def run_eval(name,logpred,residuals):
 reports[name]={};errors[name]={}
 for label,mask in masks.items():
  r=score(d,e,mask,logpred[mask],residuals)
  # Add regimes defined only by information available at origin.
  r['regimes']={}
  groups={'CMEWindowNext24h':(x[:,names.index('cme_window_0_12h')]>0)|(x[:,names.index('cme_window_12_24h')]>0),
          'observedFastWind':x[:,names.index('speed_24h')]>=500,
          'recurrenceFastWind':(x[:,names.index('recurrence_24h_speed')]>=500)&(x[:,names.index('recurrence_24h_coverage')]>=.75)}
  for group,g in groups.items():
   gm=mask&g
   if gm.sum():r['regimes'][group]=score(d,e,gm,logpred[gm],residuals)
  reports[name][label]=r
  preds=[];truth=[]
  for j in np.flatnonzero(mask):
   paths=flux_from_log(logpred[j]+residuals)
   preds.append(np.median(paths.sum(axis=1)*3600))
   truth.append(e['future'][j].sum()*3600)
  errors[name][label]=pd.Series(np.abs(np.array(preds)-truth),index=e['times'][mask]).resample('1D').mean()
  print(name,label,'MAE',r['metrics']['WXF']['24']['mae'],'RMSLE',r['metrics']['WXF']['24']['rmsle'],'coverage',r['coverage']['24'],flush=True)
for name,cols in variants.items():
 print('FIT',name,'train',train.sum(),'columns',len(cols),flush=True)
 model=forest().fit(x[train][:,cols],y[train]);residuals=y[selected]-model.predict(x[selected][:,cols])
 logpred=e['base']+model.predict(x[:,cols])
 run_eval(name,logpred,residuals)
 artifact={'version':VERSION,'estimator':model,'residuals':residuals,'featureNames':[names[j] for j in cols],
 'report':reports[name]['development'],'trainingFeatureMin':x[train][:,cols].min(axis=0),'trainingFeatureMax':x[train][:,cols].max(axis=0)}
 export_model(artifact,out/(name+'.npz'))
 # Keep a few numeric vectors to verify portable export, without executable artifacts.
 chosen=np.random.default_rng(1989).choice(len(x),200,replace=False)
 frozen=load_model(out/(name+'.npz'))
 export_diff=float(np.max(np.abs(model.predict(x[chosen][:,cols])-frozen['estimator'].predict(x[chosen][:,cols]))))
 if name=='fullGuidance':
  final=artifact;final_model=model;final_export_diff=export_diff
 print('Export verification',export_diff,flush=True)
old=load_model(args.previous_model);oldcols=[names.index(n) for n in old['featureNames']]
run_eval('previousWXF',e['base']+old['estimator'].predict(x[:,oldcols]),old['residuals'])
# Paired weekly blocks keep all available origins in the same dates together.
def bootstrap(candidate,reference,label):
 a=pd.concat([errors[candidate][label],errors[reference][label]],axis=1).dropna();a.columns=['new','old']
 day=(a.index-a.index[0]).days//7
 blocks=[v for _,v in a.groupby(day)]
 if len(blocks)<3:return {'note':'Too few weekly blocks'}
 rng=np.random.default_rng(1989);samples=[]
 for _ in range(2000):
  z=pd.concat([blocks[j] for j in rng.integers(0,len(blocks),len(blocks))]);samples.append(float((z.old-z.new).mean()))
 return {'dailyMAEImprovement':float((a.old-a.new).mean()),'bootstrap95':list(map(float,np.quantile(samples,[.025,.975]))),'weeklyBlocks':len(blocks),'dates':len(a)}
comparisons={ref:{label:bootstrap('fullGuidance',ref,label) for label in masks} for ref in ['previousWXF','longHistoryObserved','longHistoryRecurrence','longHistoryArrivals']}
report=reports['fullGuidance']['development']
report.update({'schemaVersion':VERSION,'splits':SPLITS,'quality':json.loads((out/'quality.json').read_text()),
 'partitionCounts':{'train':int(train.sum()),'calibration':int(cal.sum()),'test':int(masks['development'].sum())},
 'calibrationPaths':len(selected),'rejections':e['rejected'],'featureNames':names,'forecastHorizonHours':24,
 'thresholdsMeaning':'Office rolling 24-hour internal-charging exposure criterion; not a satellite failure probability',
 'verification':'Retrospective development evaluation. Submission-gated Scoreboard, no actual CME outcomes used. Complete revision/receipt history unavailable; forward shadow verification required.',
 'ablation':{k:v for k,v in reports.items() if k!='fullGuidance'},'septemberEvaluation':reports['fullGuidance']['september'],
 'pairedComparisons':comparisons,'experimentPlan':json.loads((Path(__file__).with_name('experiment-plan.json')).read_text())})
w=report['metrics']['WXF']['24'];base=report['metrics']['diurnalPersistence']['24'];prev=reports['previousWXF']['development']['metrics']['WXF']['24']
report['releaseGate']={'beatsDiurnalAt24hMAE':w['mae']<base['mae'],'beatsDiurnalAt24hRMSLE':w['rmsle']<base['rmsle'],
 'coverageWithinFivePoints':abs(report['coverage']['24']-.9)<=.05,'beatsPreviousWXFat24hMAE':w['mae']<prev['mae'],'forwardVerified':False}
report['releaseGate']['experimentalPromotion']=all(v for k,v in report['releaseGate'].items() if k!='forwardVerified')
final['report']=report
export_model(final,out/'model.npz')
(out/'evaluation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
(out/'export-verification.json').write_text(json.dumps({'randomFeatureVectors':200,'maximumAbsoluteLogPredictionDifference':final_export_diff},indent=2)+'\n')
print('GATE',json.dumps(report['releaseGate']),flush=True)
print('COMPARISONS',json.dumps(comparisons,indent=2),flush=True)
