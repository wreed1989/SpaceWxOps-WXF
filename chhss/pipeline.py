"""CH/HSS real acquisition bootstrap; no forecasts are published by this check."""
import json, requests, argparse, re, traceback
from pathlib import Path
from urllib.parse import urljoin
from astropy.io import fits
from astropy.time import Time
import numpy as np
import sunpy.map

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    report={}
    for label,ds in [('historical','hmi.M_720s[2024.01.01_12:00_TAI/24m]'),('latest','hmi.M_720s_nrt[$]')]:
        try:
            base='http://jsoc.stanford.edu'
            r=requests.get(base+'/cgi-bin/ajax/jsoc_info',params={'op':'rs_list','ds':ds,'key':'**ALL**','seg':'magnetogram','n':1},timeout=90);r.raise_for_status();j=r.json();(a.output/(label+'_metadata.json')).write_text(json.dumps(j,indent=2))
            values={x['name']:x['values'][0] for x in j['keywords']};seg=j['segments'][0]['values'][0]
            r=requests.get(urljoin(base,seg),timeout=(15,120));r.raise_for_status();p=a.output/(label+'_hmi.fits');p.write_bytes(r.content)
            with fits.open(p) as hdus:
                h=next(h for h in hdus if h.data is not None and h.data.ndim==2);data=np.array(h.data);header=h.header.copy()
            for k,v in values.items():
                if v is None or str(v) in ['MISSING','NaN','nan']:continue
                if k in ['SIMPLE','BITPIX','NAXIS','NAXIS1','NAXIS2','EXTEND','BSCALE','BZERO','BLANK']:continue
                try:
                    if re.fullmatch(r'[+-]?\d+',str(v)):v=int(v)
                    elif re.fullmatch(r'[+-]?(?:\d*\.\d+|\d+\.?)(?:[eE][+-]?\d+)?',str(v)):v=float(v)
                    header[k]=v
                except Exception:pass
            header['DATE-OBS']=values.get('DATE-OBS',values.get('DATE__OBS'))
            m=sunpy.map.Map(data,header)
            report[label]={'shape':list(data.shape),'unit':str(m.unit),'time':str(m.date),'scale':str(m.scale),'rotation':m.rotation_matrix.tolist(),'quality':values.get('QUALITY'),'range':[float(np.nanmin(data)),float(np.nanmax(data))],'segment':seg,'bytes':len(r.content)}
            p.unlink()
        except Exception as e:report[label]={'error':str(e),'trace':traceback.format_exc()}
    for name,url in [('paper','https://pmc.ncbi.nlm.nih.gov/articles/PMC6445534/'),('qualitywiki','http://jsoc.stanford.edu/jsocwiki/Lev1Doc'),('qualityobservable','http://jsoc.stanford.edu/jsocwiki/Lev1.5Doc'),('observable_source','http://jsoc.stanford.edu/cvs/JSOC/proj/lev1.5_hmi/apps/HMI_observables.c?view=co')]:
        try:
            r=requests.get(url,timeout=45);r.raise_for_status();(a.output/(name+'.txt')).write_text(r.text)
            report[name]={'length':len(r.content),'matches':[r.text[max(0,m.start()-200):m.end()+400] for m in list(re.finditer(r'00000400|QUAL_NRT|Q_NRT|Near.Real.Time|near.real.time',r.text,re.I))[:25]]}
        except Exception as e:report[name]={'error':str(e)}
    (a.output/'science_check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
