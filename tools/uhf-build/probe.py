"""Read public client-side interface assets. No operational files are changed."""
import hashlib,json,pathlib,urllib.request
root=pathlib.Path('model-assets');root.mkdir(exist_ok=True)
base='https://kauai.ccmc.gsfc.nasa.gov/instantrun/_next/static/chunks/'
refs={'wbmod_interface.js':base+'pages/wbmod-9d75550207c5ded7.js','common_interface.js':base+'141-1bda8db760f23174.js'}
records=[]
for name,url in refs.items():
 record={'file':name,'url':url}
 try:
  request=urllib.request.Request(url,headers={'User-Agent':'SpaceWxOps-Model-Research/1.0'})
  with urllib.request.urlopen(request,timeout=35) as response: data=response.read(3000000)
  (root/name).write_bytes(data)
  record.update(status='success',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 except Exception as error: record.update(status='failed',error=str(error))
 records.append(record)
 print(json.dumps(record),flush=True)
(root/'manifest.json').write_text(json.dumps(records,indent=2))
