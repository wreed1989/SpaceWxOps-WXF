#!/usr/bin/env python3
"""Read fixed provider-published resources; do not execute remote code."""
import json
from datetime import timedelta
from urllib.parse import urlencode
import collect_products as c
host='a-effort-astro-noa-gr.content.swe.s2p.esa.int'
c.access.AUTH_HOSTS[host]='swe_contentproxy'
base='https://'+host
c.save('aeffort-probabilities',base+'/results/prob.txt',{'txt'})
c.save('aeffort-recent-xml',base+'/prod/api/index.php?'+urlencode({'pc':'S124','component':'archive','from':(c.NOW-timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),'to':c.NOW.strftime('%Y-%m-%dT%H:%M:%SZ')}),{'xml'})
c.save('connectivity-registration-css','https://connect-tool.irap.omp.eu/static/css/connect2.css',{'txt'},False)
(c.ROOT/'manifest-followup.json').write_text(json.dumps(c.report,indent=2))
print(json.dumps({'products':c.report['requests']},indent=2))
