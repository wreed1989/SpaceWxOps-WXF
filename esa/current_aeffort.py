"""A-EFFort web data fallback. Never invent an issue time or validity window."""
import re
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit,urljoin
from harvest import Links,Harvester,auth

def parse_web(text):
 lines=[x.strip() for x in text.splitlines() if x.strip()]
 if len(lines)<10 or len(lines)>3000:raise auth.SafeError('aeffort_web_size')
 try:reference=datetime.strptime(lines[0],'%d/%m/%Y %H:%M:%S UT').replace(tzinfo=timezone.utc)
 except ValueError:raise auth.SafeError('aeffort_reference_time') from None
 if lines[1].lower() not in ('full disc probabilities','full disk probabilities'):raise auth.SafeError('aeffort_full_disk_header')
 def probabilities(block):
  p={}
  for s in block:
   m=re.fullmatch(r'(M1|M5|X1|X5):\s*(\d+(?:\.\d+)?)',s)
   if m:
    key=m[1]+'+';v=float(m[2])/100
    if key in p or not 0<=v<=1:raise auth.SafeError('aeffort_probability')
    p[key]=v
  if set(p)!={'M1+','M5+','X1+','X5+'}:raise auth.SafeError('aeffort_thresholds')
  values=[p[k] for k in ('M1+','M5+','X1+','X5+')]
  if any(b>a for a,b in zip(values,values[1:])):raise auth.SafeError('aeffort_nonmonotonic')
  return p
 records=[{'region':'full-disk','probabilities':probabilities(lines[3:7])}]
 n=next((re.fullmatch(r'Number of ARs:\s*(\d+)',x) for x in lines if x.startswith('Number of ARs:')),None)
 if not n or int(n[1])>100:raise auth.SafeError('aeffort_region_count')
 starts=[i for i,x in enumerate(lines) if re.fullmatch(r'AR:\s*NOAA AR \d{5}',x)]
 if len(starts)!=int(n[1]):raise auth.SafeError('aeffort_region_count')
 for i in starts:
  ar=lines[i].rsplit(' ',1)[-1];block=lines[i+1:i+7];location=next((x[5:] for x in block if x.startswith('Loc: ')),None)
  records.append({'region':ar,'probabilities':probabilities(block),'location':location})
 if len({r['region'] for r in records})!=len(records):raise auth.SafeError('aeffort_duplicate_region')
 return {'format':'aeffort-web-v1','reference_time':reference.isoformat().replace('+00:00','Z'),'reference_type':'Input Magnetogram','issued_at':None,'valid_start':None,'valid_end':None,'records':records,'note':'Published A-EFFort web probabilities. The first line is the input magnetogram time, not a declared issue time. This web feed supplies no explicit forecast begin/end timestamps. Probabilities are displayed as recent provider guidance and are not treated as formally window-matched forecasts.'}

def current_flare(self,provider):
 api=Harvester.flare(self,provider)
 if provider!='aeffort' or api.get('availability')=='current':return api
 host=urlsplit(api['source']).hostname
 if not host or not host.endswith('.content.swe.s2p.esa.int'):raise auth.SafeError('aeffort_host')
 source='https://'+host+'/results/prob.txt'
 raw,headers=self.request(source)
 try:web=parse_web(raw.decode('utf-8'))
 except (UnicodeError,auth.SafeError):return api
 ref=datetime.fromisoformat(web['reference_time'].replace('Z','+00:00'))
 recent=-timedelta(minutes=5)<=self.now-ref<=timedelta(hours=6)
 return {**api,'source':source,'api_source':api['source'],'api_availability':api['availability'],'availability':'recent_web_guidance' if recent else 'older_web_guidance','web':web,'web_last_modified':headers.get('last-modified'),'reference_time':web['reference_time'],'note':web['note']}
