import urllib.request, pathlib, json, hashlib
root=pathlib.Path('model-assets');root.mkdir(exist_ok=True)
urls={
 'highlat-v13.pdf':'https://www.researchgate.net/profile/James-Secan/publication/235197572_An_Improved_Model_of_High-Latitude_F-Region_Scintillation_WBMOD_Version_13/links/57740f4208aeb9427e241dc9/An-Improved-Model-of-High-Latitude-F-Region-Scintillation-WBMOD-Version-13.pdf',
 'equatorial-report2.pdf':'https://apps.dtic.mil/sti/tr/pdf/ADA278568.pdf',
 'equatorial-report1.pdf':'https://apps.dtic.mil/sti/tr/pdf/ADA264156.pdf',
 'equatorial-report2.txt':'https://archive.org/download/DTIC_ADA278568/DTIC_ADA278568_djvu.txt',
 'equatorial-report1.txt':'https://archive.org/download/DTIC_ADA264156/DTIC_ADA264156_djvu.txt'
}
log=[]
for name,url in urls.items():
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'SpaceWxOps scientific model evaluation'})
  with urllib.request.urlopen(req,timeout=40) as r: data=r.read();ctype=r.headers.get('Content-Type','')
  (root/name).write_bytes(data)
  entry=dict(name=name,url=url,bytes=len(data),type=ctype,sha256=hashlib.sha256(data).hexdigest());log.append(entry);print(entry,flush=True)
 except Exception as e:log.append(dict(name=name,error=str(e)));print(name,e,flush=True)
(root/'references.json').write_text(json.dumps(log,indent=2))
