import urllib.request, urllib.parse, pathlib, json
root=pathlib.Path('model-assets');root.mkdir(exist_ok=True)
def get(url):
 return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'SpaceWxOps model research'}),timeout=60).read()
ids=['DTIC_ADA264156','DTIC_ADA278568']
q='title:("Improved Model" AND "High-Latitude")'
try:
 search=json.loads(get('https://archive.org/advancedsearch.php?'+urllib.parse.urlencode({'q':q,'output':'json','rows':10,'fl[]':'identifier'})))
 print('SEARCH',search,flush=True);(root/'archive-search.json').write_text(json.dumps(search))
 ids += [r['identifier'] for r in search.get('response',{}).get('docs',[])]
except Exception as e:print('SEARCH ERROR',e)
for ident in dict.fromkeys(ids):
 try:
  meta=json.loads(get('https://archive.org/metadata/'+ident));(root/(ident+'-metadata.json')).write_text(json.dumps(meta))
  names=[f['name'] for f in meta.get('files',[]) if f['name'].lower().endswith('.pdf')];print('ITEM',ident,names,flush=True)
  for name in names[:1]:
   blob=get('https://archive.org/download/'+ident+'/'+urllib.parse.quote(name));(root/(ident+'.pdf')).write_bytes(blob);print('PDF',ident,len(blob),flush=True)
 except Exception as e:print('ERROR',ident,e,flush=True)
