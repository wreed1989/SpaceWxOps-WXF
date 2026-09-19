"""Coronal Hole / HSS Outlook: numerical measurement and paired verification.
Thresholds are fixed research choices, not a claim of operational calibration.
"""
from datetime import datetime, timedelta, timezone
import numpy as np
from scipy import ndimage as ndi
VERSION='chhss-euv-hmi-20260919.1'
CORES={'E':(-40.,-20.),'M':(-10.,10.),'W':(20.,40.)}
LAGS={'E':6,'M':4,'W':2}
UTC=timezone.utc

def iso(t):return t.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00','Z')
def date(t):
    if isinstance(t,datetime):return t.astimezone(UTC)
    return datetime.fromisoformat(str(t).replace('Z','+00:00')).replace(tzinfo=UTC)

def encode_runs(a):
    a=np.asarray(a,dtype=np.uint8).ravel()
    if not len(a):return []
    starts=np.r_[0,np.flatnonzero(a[1:]!=a[:-1])+1]
    counts=np.diff(np.r_[starts,len(a)])
    return np.column_stack([a[starts],counts]).astype(int).ravel().tolist()

def decode_runs(runs,shape):
    r=np.asarray(runs)
    if len(r)%2 or r.ndim!=1:raise ValueError('Malformed runs')
    if np.any(r<0) or np.any(r!=r.astype(int)):raise ValueError('Invalid run values')
    r=r.reshape(-1,2)
    if r[:,1].sum()!=np.prod(shape) or np.any(r[:,1]<=0):raise ValueError('Run length mismatch')
    return np.repeat(r[:,0],r[:,1]).astype(np.uint8).reshape(shape)

def polarity(mask,blos,mu,footprint,minimum=100):
    nmask=int(np.count_nonzero(mask))
    good=mask&np.isfinite(blos)&np.isfinite(mu)&(mu>=.4)&(footprint>=.99)
    n=int(good.sum());coverage=n/nmask if nmask else 0.
    if n:
        br=blos[good]/mu[good];weights=1/mu[good]
        signed=float(np.sum(br*weights));unsigned=float(np.sum(np.abs(br)*weights))
        imbalance=signed/unsigned if unsigned else 0.
        mean=float(np.average(br,weights=weights));median=float(np.median(br))
    else:imbalance=0.;mean=median=None
    accepted=n>=minimum and coverage>=.8 and abs(imbalance)>=.15 and mean is not None and abs(mean)>=1
    return {'coreDefinition':'20deg-hgs','polarity':int(np.sign(imbalance)) if accepted else None,'fluxImbalance':imbalance,'meanBr':mean,'medianBr':median,'validMaskedPixelFraction':coverage,'nValid':n,'nMasked':nmask,'quality':'signed-field QA passed' if accepted else 'mixed/weak/insufficient','thresholds':{'minMeanBrG':1.,'minPixels':minimum,'minImbalance':.15,'minCoverage':.8},'resolutionNote':'Pixel count is sampling coverage, not number of independent measurements.'}

def segment(channels,valid,rho):
    """Fixed multithermal low-intensity candidates, NOT a CHIMERA implementation.
    Radial medians reduce limb/throughput effects. No wind outcomes are used.
    Polarity is diagnosed separately, never imposed by the EUV classification.
    """
    if set(channels)!={171,193,211}:raise ValueError('All three AIA channels required')
    normalized={};diagnostics={}
    for wavelength,data in channels.items():
        data=np.asarray(data,dtype=float);ok=valid&np.isfinite(data)&(data>0)
        if ok.sum()<.95*valid.sum():raise ValueError(f'AIA{wavelength}: insufficient positive disk coverage')
        profile=np.array([np.median(data[ok&(rho>=lo)&(rho<lo+.05)]) if np.count_nonzero(ok&(rho>=lo)&(rho<lo+.05))>50 else np.nan for lo in np.arange(0,1,.05)])
        good=np.flatnonzero(np.isfinite(profile)&(profile>0))
        if len(good)<15:raise ValueError('Radial reference incomplete')
        profile=np.interp(np.arange(20),good,profile[good]);profile=ndi.median_filter(profile,size=3,mode='nearest')
        reference=np.interp(rho,np.arange(20)*.05+.025,profile)
        normalized[wavelength]=ndi.median_filter(np.nan_to_num(data/reference,nan=2,posinf=2),size=3)
        diagnostics[str(wavelength)]={'radialMedian':profile.round(4).tolist(),'positivePixels':int(ok.sum())}
    candidate=valid&(normalized[193]<.58)&(normalized[211]<.60)&(normalized[171]<1.05)
    candidate=ndi.binary_opening(candidate,iterations=1);candidate=ndi.binary_closing(candidate,iterations=2)&valid
    labels,n=ndi.label(candidate);sizes=np.bincount(labels.ravel());minimum=max(50,int(valid.sum()*.001))
    keep=np.flatnonzero(sizes>=minimum);keep=keep[keep!=0];mask=np.isin(labels,keep)&valid
    if mask.sum()/valid.sum()>.45:raise ValueError('Candidate area >45%: segmentation failure gate')
    labels,n=ndi.label(mask)
    return mask,labels,{'method':VERSION,'thresholds':{'193':.58,'211':.60,'171':1.05},'channels':diagnostics,'components':int(n),'minimumComponentPixels':minimum,'candidateDiskFraction':float(mask.sum()/valid.sum()),'qualification':'Automatic EUV candidate mask; detector and forecast skill not certified.'}

def windows(mask,valid,cmd,lat):
    labels=np.zeros(mask.shape,dtype=np.uint8);out={}
    for i,(key,(lo,hi)) in enumerate(CORES.items(),1):
        ok=valid&np.isfinite(cmd)&np.isfinite(lat)&(cmd>=lo)&(cmd<=hi);labels[ok]=i;selected=ok&mask;n=int(ok.sum());count=int(selected.sum())
        if n<100:raise ValueError(f'{key} core coverage insufficient')
        out[key]={'A':count/n,'disk':n,'ch':count,'centroidLat':float(np.mean(lat[selected])) if count else None,'centroidCmd':float(np.mean(cmd[selected])) if count else None}
    return labels,out

def issue_case(pack):
    """Retrospective reconstruction; never a fabricated historical issuance."""
    w=pack['measured']['window'];k=max(['W','M','E'],key=lambda k:w[k]['A']);signal=w[k]['A']>=.02
    if not signal:k='M'
    obs=date(pack['observationTime']);issuance=obs.replace(hour=18,minute=0,second=0,microsecond=0)
    if issuance<obs:issuance+=timedelta(days=1)
    target=(issuance+timedelta(days=LAGS[k])).replace(hour=0,minute=0,second=0,microsecond=0)
    return {'caseId':f'{VERSION}:{obs:%Y%m%dT%H%M}:{pack["maskId"][:12]}','kind':'retrospective-reconstruction','issueTime':iso(issuance),'sourceObservationTime':pack['observationTime'],'retrievedAt':pack['availableAt'],'targetStart':iso(target),'targetEnd':iso(target+timedelta(days=1)),'core':k,'coreAreaFraction':w[k]['A'],'speedKms':350+900*w[k]['A'] if signal else None,'signal':signal,'maskId':pack['maskId'],'measurementEngine':VERSION,'polarity':(pack.get('polarity') or {}).get('sector',{}).get(k,{}).get('polarity'),'groupId':f'timeblock-{obs:%Y}-'+str((obs.timetuple().tm_yday-1)//34),'groupMeaning':'Conservative 34-day time block, not a proven recurrent-hole identity.'}

def daily_truth(rows):
    buckets={}
    for row in rows:
        if row.get('speed') is not None:buckets.setdefault(row['time_tag'][:10],{})[row['time_tag']]=row['speed']
    return {d:{'speed':float(np.mean(list(v.values()))) if len(v)>=18 else None,'hours':len(v)} for d,v in buckets.items()}

def verify(cases,truth,failed=0):
    """Paired daily means, no tuning or optimal timing; all attempted dates counted.
    ICME coverage UNKNOWN without a separately versioned interval catalogue.
    """
    pairs=[];excluded=[]
    for c in cases:
        if c['speedKms'] is None:excluded.append({'caseId':c['caseId'],'reason':'No issued core-speed signal; abstention, not a fabricated background forecast'});continue
        t=date(c['targetStart']);y=truth.get(t.strftime('%Y-%m-%d'),{});base=truth.get((t-timedelta(days=27)).strftime('%Y-%m-%d'),{})
        if y.get('speed') is None or base.get('speed') is None:excluded.append({'caseId':c['caseId'],'reason':'Target or recurrence has <18 valid hours'});continue
        pairs.append({**c,'observedSpeed':y['speed'],'recurrenceSpeed':base['speed'],'error':c['speedKms']-y['speed'],'baselineError':base['speed']-y['speed'],'targetHours':y['hours'],'recurrenceHours':base['hours'],'icmeState':'unknown'})
    def stats(rows):
        if not rows:return {'n':0,'mae':None,'rmse':None,'bias':None,'recurrenceMae':None,'skill':None}
        e=np.array([x['error'] for x in rows]);b=np.array([x['baselineError'] for x in rows]);den=np.mean(abs(b))
        return {'n':len(rows),'mae':float(np.mean(abs(e))),'rmse':float(np.sqrt(np.mean(e**2))),'bias':float(np.mean(e)),'recurrenceMae':float(den),'skill':float(1-np.mean(abs(e))/den) if den>0 else None}
    groups={}
    for row in pairs:groups.setdefault(row['groupId'],[]).append(row)
    ci=None
    if len(groups)>=10:
        rng=np.random.default_rng(82719);blocks=list(groups.values());skills=[]
        for _ in range(1000):
            v=stats([r for j in rng.integers(0,len(blocks),len(blocks)) for r in blocks[j]])['skill']
            if v is not None:skills.append(v)
        ci=[float(x) for x in np.percentile(skills,[2.5,97.5])] if skills else None
    return {'schemaVersion':'chhss-validation-1','product':'Coronal Hole / HSS Outlook','generatedAt':iso(datetime.now(UTC)),'methodVersion':VERSION,'provenance':{'target':'Fixed forecast-selected UTC daily mean speed; >=18 hourly observations','baseline':'Same daily-mean statistic at target minus 27 days','truth':'NASA OMNI2 retrospective hourly, not vintage real-time data','caseType':'reconstructed predictions from numerical FITS, not forecasts issued historically','selection':'All scheduled dates; no event-only selection; no fitted coefficients or holdout tuning','icmeCoverage':'Not supplied: all-events results only','uncertainty':'34-day time-block bootstrap; recurring-source identity not established'},'coverage':{'successfulCases':len(cases),'abstainedCases':sum(c['speedKms'] is None for c in cases),'failedAcquisitionDays':failed,'scoredPairs':len(pairs),'excludedPairs':len(excluded),'timeBlocks':len(groups)},'metrics':{**stats(pairs),'skill95TimeBlockCI':ci},'strata':{'signal':stats([r for r in pairs if r['signal']]),'noSignal':stats([r for r in pairs if not r['signal']])},'promotion':{'eligible':False,'reason':'Data/processing functioning does not establish operational forecast skill; detector, event timing, source connectivity and independent validation remain required.'},'pairs':pairs,'excluded':excluded}

# CHHSS_QA_UPGRADE_1
