"""HAPI 3.0 current samples: provider size=[1] represents a scalar."""
import json
from datetime import timedelta,datetime
from urllib.parse import urlencode
from harvest import HAPI,utc

def current_hapi(self):
 catalog=self.json(HAPI+'catalog')
 if catalog.get('status',{}).get('code')!=1200 or not isinstance(catalog.get('catalog'),list):
  from check_access import SafeError
  raise SafeError('hapi_catalog_error')
 prior=self.old.get('products',{}).get('hapi',{});info={};samples={}
 stop=(self.now-timedelta(minutes=10)).replace(second=0,microsecond=0);start=stop-timedelta(minutes=10)
 for item in catalog['catalog'][:40]:
  ident=item['id']
  try:
   d=utc(prior.get('fetched_at'))
   metadata=prior.get('info',{}).get(ident) if d and self.now-datetime.fromisoformat(d.replace('Z','+00:00'))<timedelta(hours=24) else None
   if not metadata:metadata=self.json(HAPI+'info?'+urlencode({'dataset':ident}))
   if metadata.get('status',{}).get('code')!=1200:continue
   info[ident]=metadata
   all_params=metadata.get('parameters',[])
   params=[p for p in all_params if p.get('type') in ('double','integer') and p.get('size') in (None,[],[1])]
   preferred=[p for p in params if not any(x in p['name'].lower() for x in ('version','flag','quality','validity','index'))]
   params=(preferred or params)[:3]
   names=[p['name'] for p in params]
   if not names:continue
   time_param=next((p['name'] for p in all_params if p.get('type')=='isotime'),None)
   if time_param:names.insert(0,time_param)
   q={'dataset':ident,'start':start.strftime('%Y-%m-%dT%H:%M:%SZ'),'stop':stop.strftime('%Y-%m-%dT%H:%M:%SZ'),'parameters':','.join(names),'format':'json','include':'header'}
   data=self.json(HAPI+'data?'+urlencode(q))
   if len(data.get('data',[]))>5000:raise ValueError('sample_too_large')
   json.dumps(data,allow_nan=False)
   samples[ident]={'request':q,'response':data}
  except Exception as e:
   from check_access import SafeError
   samples[ident]={'error':str(e) if isinstance(e,SafeError) else 'unavailable'}
 return {'source':HAPI,'catalog':catalog['catalog'],'info':info,'samples':samples,'sample_note':'Ten-minute samples of up to three scalar science parameters plus UTC. Size=[1] scalars supported. Declared coverage endpoints do not establish observation freshness; original fill values and no-data codes are retained.'}
