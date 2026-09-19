"""One-time idempotent source migration; not a runtime patch dependency."""
from pathlib import Path
p=Path('chhss/pipeline.py');s=p.read_text()
if '# CHHSS_QA_UPGRADE_1' not in s:
 def change(a,b):
  global s
  if a not in s:raise ValueError('Missing expected source: '+a[:100])
  s=s.replace(a,b,1)
 change("'dsun_obs','hgln_obs','hglt_obs','rsun_obs'", "'dsun_obs','rsun_obs'")
 change("if any(k not in m.meta for k in keys):raise ValueError(label+': incomplete WCS/observer header')", "if any(k not in m.meta for k in keys):raise ValueError(label+': missing WCS '+str([k for k in keys if k not in m.meta]))\n    if not (all(k in m.meta for k in ['hgln_obs','hglt_obs']) or all(k in m.meta for k in ['crln_obs','crlt_obs'])):raise ValueError(label+': observer longitude/latitude missing')")
 change("# Only informational observable NRT bit permitted. This is not\n                # the same definition as bit 10 in lower-level filtergrams.","# Observable 0x400 is NOCOSMICRAY (missing cosmic-ray lists),\n                # NOT an NRT identity bit. Accepted only as DEGRADED,\n                # with independent temporal sign agreement required below.")
 change("_,t,row=ok[0];seg=row['_segment']", "_,t,row=ok[0];seg=row['_segment']\n        self.reference=next((x[2] for x in ok[1:] if 600<=(t-x[1]).total_seconds()<=1800),None) if when is None else None")
 change("return m,src,t\n    def aia", "src['degraded']=int(str(row['QUALITY']),0)==0x400\n        src['qualityFlags']=['NOCOSMICRAY'] if src['degraded'] else []\n        return m,src,t\n    def aia")
 change("from sunpy.coordinates import frames,transform_with_sun_center", "from sunpy.coordinates import frames,transform_with_sun_center,propagate_with_solar_surface")
 change("blos=np.asarray(hm.data,dtype=float)*hmi.unit.to(u.G);b0=", """blos=np.asarray(hm.data,dtype=float)*hmi.unit.to(u.G)
    prior=None;prior_foot=None;prior_src=None
    if hsrc['degraded'] and acq.reference:
        row=acq.reference;pp,prior_src=acq.download(urljoin(JSOC,row['_segment']),'hmi/'+digest(('reference'+row['T_REC']).encode())[:24]+'.fits')
        ref=raw_hmi_map(pp,row).superpixel(u.Quantity([4,4],u.pix),func=np.mean)
        with propagate_with_solar_surface():
            oldmap,prior_foot=ref.reproject_to(target.wcs,return_footprint=True,order='bilinear')
        prior=np.asarray(oldmap.data,dtype=float)*ref.unit.to(u.G);prior_src={**prior_src,'observationTime':iso(hmi_time(row)),'record':row['T_REC'],'quality':row['QUALITY']}
    b0=""")
 change("sectors={k:polarity(mask&(labels==i),blos,mu,hfoot) for i,k in enumerate(CORES,1)}", """def diagnose(region):
        result=polarity(region,blos,mu,hfoot)
        if hsrc['degraded']:
            comparison=polarity(region,prior,mu,prior_foot) if prior is not None else None
            agree=bool(result['polarity'] is not None and comparison and comparison['polarity']==result['polarity'])
            result['temporalAgreement']=agree;result['referenceEvidence']=comparison
            if not agree:result['polarity']=None;result['quality']='degraded HMI: temporal sign not established'
            else:result['quality']='degraded HMI: sign consistent in two observations'
        return result
    sectors={k:diagnose(mask&(labels==i)) for i,k in enumerate(CORES,1)}""")
 change("ph=polarity(reg,blos,mu,hfoot);lat0=", "ph=diagnose(reg);lat0=")
 change("'areaFraction':float(n/valid.sum()),'areaPct':float(100*n/valid.sum())", "'areaDisk':float(n/(np.pi*R*R)),'areaFraction':float(n/(np.pi*R*R)),'areaPct':float(100*n/(np.pi*R*R))")
 change("points=line[::max(1,len(line)//160)];contours.append({'id':hid,'points':[[float(x/size*100),float(y/size*100)] for y,x in points]})", """points=line[::max(1,len(line)//160)]
            ring=[{'lat':float(lat[int(np.clip(round(size-1-y),0,size-1)),int(np.clip(round(x),0,size-1))]),'lon':float(cmd[int(np.clip(round(size-1-y),0,size-1)),int(np.clip(round(x),0,size-1))])} for y,x in points]
            ring=[v for v in ring if np.isfinite(v['lat']) and np.isfinite(v['lon'])]
            contours.append({'id':hid,'lat':lat0,'lon':lon0,'nPix':n,'areaPct':float(100*n/(np.pi*R*R)),'ring':ring,'points':[[float(x/size*100),float(y/size*100)] for y,x in points]})
            if not holes[-1].get('ring'):holes[-1]['ring']=ring""")
 change("'hmiQuality':hsrc['quality'],'hmiSource':hsrc", "'hmiQuality':hsrc['quality'],'degraded':hsrc['degraded'],'qualityFlags':hsrc['qualityFlags'],'temporalReference':prior_src,'hmiSource':hsrc")
 change("status.update(ok=True,observationTime=pack['observationTime'],maskId=pack['maskId'],perCore={k:v['polarity'] for k,v in pack['polarity']['sector'].items()})", """status.update(ok=True,observationTime=pack['observationTime'],maskId=pack['maskId'],degraded=pack['polarity']['degraded'],qualityFlags=pack['polarity']['qualityFlags'],perCore={k:v['polarity'] for k,v in pack['polarity']['sector'].items()})
        try:
            recent=output/'recurrence-source';recent.mkdir(parents=True,exist_ok=True)
            rows=get_truth(acq,datetime.now(UTC)-timedelta(days=75),datetime.now(UTC),recent)
            dump(output/'recurrence.json',{'schemaVersion':'chhss-recurrence-1','generatedAt':iso(datetime.now(UTC)),'source':'NASA OMNI2 retrospective hourly','rows':rows})
            status['recurrenceRows']=len(rows)
        except Exception as e:status['recurrenceError']=str(e)""")
 s+='\n# CHHSS_QA_UPGRADE_1\n';p.write_text(s)
p=Path('chhss/core.py');s=p.read_text()
if '# CHHSS_QA_UPGRADE_1' not in s:
 s=s.replace("k=max(CORES,key=lambda k:w[k]['A']);signal=w[k]['A']>=.025", "k=max(['W','M','E'],key=lambda k:w[k]['A']);signal=w[k]['A']>=.02")
 s=s.replace("'speedKms':350+900*w[k]['A']", "'speedKms':350+900*w[k]['A'] if signal else None")
 s=s.replace("for c in cases:\n        t=date(c['targetStart'])", "for c in cases:\n        if c['speedKms'] is None:excluded.append({'caseId':c['caseId'],'reason':'No issued core-speed signal; abstention, not a fabricated background forecast'});continue\n        t=date(c['targetStart'])")
 s=s.replace("'successfulCases':len(cases),'failedAcquisitionDays'", "'successfulCases':len(cases),'abstainedCases':sum(c['speedKms'] is None for c in cases),'failedAcquisitionDays'")
 s+='\n# CHHSS_QA_UPGRADE_1\n';p.write_text(s)
