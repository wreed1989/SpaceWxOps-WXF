"""Probability verification, with undefined ratios kept null and time-block uncertainty."""
import numpy as np
import pandas as pd


def ratio(a, b):
    return float(a / b) if b else None


def metrics(y, p, base, decision=.2):
    y, p = np.asarray(y, float), np.asarray(p, float)
    if not len(y) or len(y) != len(p) or not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Verification needs binary outcomes and finite probabilities in [0,1]')
    if not 0 <= decision <= 1 or not 0 <= base <= 1: raise ValueError('Invalid decision/base rate')
    yes = p >= decision
    tp, fp, fn, tn = [int(m.sum()) for m in ((y == 1) & yes, (y == 0) & yes, (y == 1) & ~yes, (y == 0) & ~yes)]
    brier = float(np.mean((p-y)**2)); reference = float(np.mean((base-y)**2))
    # Average ranks give tied probabilities half credit for ROC AUC.
    ranks = pd.Series(p).rank(method='average').to_numpy(); pos = int(y.sum()); neg = len(y)-pos
    auc = ratio(ranks[y == 1].sum()-pos*(pos+1)/2, pos*neg)
    order = np.argsort(-p, kind='stable'); yy, pp = y[order], p[order]
    ends = np.r_[np.flatnonzero(np.diff(pp)), len(y)-1]; cumulative = np.cumsum(yy)[ends]
    ap = float(np.sum(np.diff(np.r_[0, cumulative]) * cumulative/(ends+1))/pos) if pos else None
    reliability = []
    for lo, hi in zip([0,.01,.03,.1,.3,.6], [.01,.03,.1,.3,.6,1.00001]):
        mask = (p >= lo) & (p < hi)
        if mask.any(): reliability.append(dict(min=lo,max=min(1,hi),n=int(mask.sum()),meanProbability=float(p[mask].mean()),observedFraction=float(y[mask].mean())))
    return dict(n=len(y),events=pos,nonEvents=neg,brier=brier,brierReference=reference,brierSkill=1-brier/reference if reference else None,
                auc=auc,averagePrecision=ap,decisionProbability=decision,POD=ratio(tp,tp+fn),FAR=ratio(fp,tp+fp),falsePositiveRate=ratio(fp,fp+tn),
                precision=ratio(tp,tp+fp),CSI=ratio(tp,tp+fp+fn),HSS=ratio(2*(tp*tn-fn*fp),(tp+fn)*(fn+tn)+(tp+fp)*(fp+tn)),
                hits=tp,falseAlarms=fp,misses=fn,correctNegatives=tn,reliability=reliability)


def block_intervals(times, y, p, base, decision=.2):
    y, p = np.asarray(y, float), np.asarray(p, float); yes = p >= decision
    block = pd.DatetimeIndex(times).as_unit('ns').asi8 // (14*86400*10**9)
    sums = pd.DataFrame(dict(block=block,loss=(p-y)**2,reference=(base-y)**2,hits=(y==1)&yes,falseAlarms=(y==0)&yes,misses=(y==1)&~yes)).groupby('block').sum()
    rng = np.random.default_rng(1989); indices = rng.integers(0,len(sums),size=(1000,len(sums)))
    totals = {k:sums[k].to_numpy()[indices].sum(axis=1) for k in sums}
    result = {'bootstrapBlocks':len(sums),'bootstrapReplicates':1000,'bootstrapBlockDays':14}
    for key, a, b, skill in [('brierSkill',totals['loss'],totals['reference'],True),('POD',totals['hits'],totals['hits']+totals['misses'],False),('FAR',totals['falseAlarms'],totals['hits']+totals['falseAlarms'],False)]:
        good = b > 0; samples = a[good]/b[good]
        if skill: samples = 1-samples
        result[key+'95'] = np.quantile(samples,[.025,.975]).tolist() if len(samples) else None
    return result
