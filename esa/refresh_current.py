#!/usr/bin/env python3
"""Production entry point. Provider collection is separate from publication."""
import hashlib,os,sys
from pathlib import Path
from datetime import datetime,timedelta
from harvest import Harvester,ASSET_RE,utc,auth
from current_hapi import current_hapi
from current_connectivity import current_connectivity
from current_aeffort import current_flare
from solar_evidence import collect_cactus,collect_demon,enrich_connectivity
auth.PUBLIC_HOSTS.update({"www.sidc.be","sidc.be"})

class Collector(Harvester):
 hapi=current_hapi
 def connectivity(self):return enrich_connectivity(self,current_connectivity(self))
 def run(self):
  self.product("cactus",lambda:collect_cactus(self))
  self.product("solardemon",lambda:collect_demon(self))
  return super().run()
 flare=current_flare
 def __init__(self,root):
  super().__init__(root)
  for url,value in self.old.get('assets',{}).items():
   path=value.get('path','');seen=utc(value.get('last_referenced_at') or self.old.get('checked_at'))
   if not ASSET_RE.fullmatch(path) or not seen:continue
   age=self.now-datetime.fromisoformat(seen.replace('Z','+00:00'))
   if not timedelta(0)<=age<timedelta(hours=2):continue
   file=self.root/path
   if file.is_file() and not file.is_symlink() and hashlib.sha256(file.read_bytes()).hexdigest()==value.get('sha256'):
    self.asset_index[url]={**value,'last_referenced_at':seen}
 def asset(self,url,**kw):
  value={**super().asset(url,**kw),'last_referenced_at':self.stamp}
  self.asset_index[url]=value
  return value

if __name__=='__main__':
 try:sys.exit(Collector(Path(os.environ.get('ESA_OUTPUT_DIR','esa-live-output'))).run())
 except Exception as e:
  print('Collector stopped:',str(e) if isinstance(e,auth.SafeError) else type(e).__name__)
  sys.exit(1)
