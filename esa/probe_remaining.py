#!/usr/bin/env python3
"""Bounded follow-up using provider-published links; no credentials in output."""
import json,re,html
from datetime import timedelta
from urllib.parse import urlencode,urljoin,urlsplit
import collect_products as c

def main():
    c.save('euhforia-series','https://www-h-esc-org.content.swe.s2p.esa.int/h101g/data/euhforia_Earth.dsv',{'txt'})
    c.save('euhforia-help','https://www-h-esc-org.content.swe.s2p.esa.int/h101g/euhforia_help.html',{'html'})
    flags={'regions_noaa_region':1,'regions_noaa_returning':1,'coronal_holes_sidc':1,'flares_solardemon':1,'features_grid':1,'features_legend':1,'features_width':1024}
    for name,opts in [('swap',{'component':'latest','images_sun':'SWAP'}),('aia-previous',{'component':'archive','images_sun':'AIA193','timenavbar.date':(c.NOW-timedelta(hours=3)).strftime('%Y-%m-%dT%H:00:00Z')})]:
        c.save('solarmap-'+name,c.access.SIDC+'?'+urlencode({'pc':'S101','psc':'c',**flags,**opts}),{'svg'})
    for key,typ,ft in [('contrast','hc','jpeg'),('color','nm','jpegc'),('clv','nm','jpegfc')]:
        c.save('kso-archive-'+key,'https://sso.kso.ac.at/prod/API/index.php?'+urlencode({'component':'archive','pc':'S107','psc':'a','type':typ,'filetype':ft,'dts_start':(c.NOW-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),'dts_end':c.NOW.strftime('%Y-%m-%dT%H:%M:%SZ')}),{'json'})
    # Public portal product metadata is not the HAPI resource server.
    for name,path in [('portal-solar','/solar-weather'),('portal-solarmap','/sidc-S101c-federated'),('portal-aeffort','/aoa-s124-federated')]:
        data,rec=c.save(name,'https://swe.ssa.esa.int'+path,{'html'},False)
        if not data:continue
        for i,item in enumerate(rec.get('links',[])):
            href=item.get('src','')
            if item.get('tag')=='iframe':
                candidate=urljoin(rec['source'],href)
                if urlsplit(candidate).hostname in c.access.AUTH_HOSTS:
                    c.save(name+'-frame',candidate,None)
            if item.get('tag')=='script' and href and ('swe' in href.lower() or 'product' in href.lower()):
                candidate=urljoin(rec['source'],href)
                if urlsplit(candidate).hostname=='swe.ssa.esa.int':c.save(name+'-script-'+str(i),candidate,None,False)
    # Metadata, then a bounded recent data sample; no bulk archive crawl.
    data,rec=c.save('hapi-catalog','https://swe.ssa.esa.int/hapi/catalog',{'json'})
    if data:
        for i,item in enumerate(json.loads(data).get('catalog',[])[:27]):
            c.save('hapi-info-'+str(i),'https://swe.ssa.esa.int/hapi/info?'+urlencode({'dataset':item['id']}),{'json'})
    (c.ROOT/'manifest-followup.json').write_text(json.dumps(c.report,indent=2))
    print(json.dumps({'products':c.report['requests']},indent=2))
if __name__=='__main__':main()
