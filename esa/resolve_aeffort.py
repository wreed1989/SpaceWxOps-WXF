#!/usr/bin/env python3
import json,re
from urllib.parse import urlsplit,urljoin,urlencode
from datetime import timedelta
import collect_products as c

def main():
    data,rec=c.save('aeffort-portal','https://swe.ssa.esa.int/iaasars_s-federated',{'html'},False)
    if data:
        for item in rec.get('links',[]):
            if item.get('tag')!='iframe':continue
            target=urljoin(rec['source'],item.get('src',''))
            h=urlsplit(target).hostname or ''
            if h.endswith('.content.swe.s2p.esa.int') and ('noa' in h or 'effort' in h):
                c.access.AUTH_HOSTS[h]='swe_contentproxy'
            elif h.endswith('.noa.gr'):c.access.PUBLIC_HOSTS.add(h)
            else:continue
            body,frame=c.save('aeffort-current-page',target,{'html'})
            c.save('aeffort-current-xml',urljoin(target,'/prod/api/index.php')+'?component=latest&pc=S124',{'xml'})
            if body:
                for i,entry in enumerate(frame.get('links',[])):
                    href=entry.get('href') or entry.get('src') or ''
                    if any(v in href.lower() for v in ('api','forecast','latest','xml','data','about')):
                        u=urljoin(frame['source'],href)
                        if urlsplit(u).hostname==h:c.save('aeffort-current-link-'+str(i),u,None)
    for label,dataset in [('sosmag','spase://SSA/NumericalData/D3S/d3s_gk2a_sosmag_1m'),('sin1','spase://SSA/NumericalData/MAGSWEDAN/magswedan_SIN1')]:
        c.save('hapi-data-'+label,'https://swe.ssa.esa.int/hapi/data?'+urlencode({'dataset':dataset,'start':(c.NOW-timedelta(hours=2)).strftime('%Y-%m-%dT%H:00:00Z'),'stop':(c.NOW-timedelta(hours=1)).strftime('%Y-%m-%dT%H:00:00Z'),'format':'json','include':'header'}),{'json'})
    (c.ROOT/'manifest-followup.json').write_text(json.dumps(c.report,indent=2))
    print(json.dumps({'products':c.report['requests']},indent=2))
if __name__=='__main__':main()
