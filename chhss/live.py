#!/usr/bin/env python3
"""NRT entry point. Definitive AIA images lag about seven days; never use
that archive to impersonate current observations. NRT quality flags are
checked separately from HMI observable flags.
"""
import argparse,re,sys
from datetime import datetime,timedelta
from urllib.parse import urljoin
from pathlib import Path
from . import pipeline, aia_quality
from .core import date,iso,UTC
class NearRealTime(pipeline.Acquire):
    def aia(self,when,wavelength):
        import sunpy.map
        when=date(when);errors=[];candidates=[]
        for hour in sorted({(when+timedelta(minutes=x)).replace(minute=0,second=0,microsecond=0) for x in [-15,0,15]}):
            base=pipeline.AIA+f'nrt/{hour:%Y/%m/%d}/H{hour:%H}00/'
            try:
                r=self.http.get(base,timeout=(10,25));r.raise_for_status()
                names=set(re.findall(r'AIA\d{8}_\d{4,6}_\d{4}\.fits',r.text))
                for name in names:
                    m=re.fullmatch(r'AIA(\d{8})_(\d{4,6})_(\d{4})\.fits',name)
                    if int(m[3])!=wavelength:continue
                    t=datetime.strptime(m[1]+m[2],'%Y%m%d%H%M%S' if len(m[2])==6 else '%Y%m%d%H%M').replace(tzinfo=UTC)
                    if abs((t-when).total_seconds())<=900:candidates.append((abs((t-when).total_seconds()),base,name))
            except Exception as e:errors.append(str(e))
        for _,base,name in sorted(candidates)[:6]:
            try:
                p,src=self.download(urljoin(base,name),'aia-nrt/'+name);m=sunpy.map.Map(p)
                q=int(str(m.meta.get('quality','-1')),0);quality=aia_quality.validate(self,q)
                pipeline.check_map(m,'AIA',quality=False,expected_wave=wavelength)
                if abs((pipeline.map_time(m)-when).total_seconds())>900:raise ValueError('AIA actual time outside 15-minute match')
                src.update(observationTime=iso(pipeline.map_time(m)),processingStream='AIA NRT synoptic; not definitive archive',qualityEvidence=quality)
                return m,src
            except Exception as e:errors.append(str(e))
        raise ValueError(f'AIA{wavelength} NRT: no quality-accepted co-timed FITS. '+('; '.join(errors[-2:]) if errors else 'No matching files listed'))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=Path('chhss-data'));p.add_argument('--cache',type=Path,default=Path('.chhss-cache'));a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    sys.exit(0 if pipeline.live(NearRealTime(a.cache),a.output) else 2)
if __name__=='__main__':main()
