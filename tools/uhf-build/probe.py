import urllib.request,pathlib,json,subprocess,sys
root=pathlib.Path('model-assets');root.mkdir(exist_ok=True)
urls={
 'rino-carrano2019.html':'https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2018JA026353',
 'secan1995.html':'https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/94RS03172',
 'secan1995.pdf':'https://agupubs.onlinelibrary.wiley.com/doi/pdfdirect/10.1029/94RS03172',
 'gussenhoven1983.html':'https://agupubs.onlinelibrary.wiley.com/doi/10.1029/JA088iA07p05692',
 'ocb-models.html':'https://ocbpy.readthedocs.io/en/latest/_modules/ocbpy/boundaries/models.html'
}
for name,url in urls.items():
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=60) as r:data=r.read()
  (root/name).write_bytes(data);print(name,len(data),flush=True)
 except Exception as e:print(name,e,flush=True)
subprocess.run([sys.executable,'-m','pip','download','--no-deps','--no-binary=:all:','--no-build-isolation','apexpy','-d',str(root)],check=False,timeout=180)
