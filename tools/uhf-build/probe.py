import pathlib, subprocess,sys,json,urllib.request,hashlib
root=pathlib.Path('model-assets');root.mkdir(exist_ok=True)
subprocess.run([sys.executable,'-m','pip','install','numpy','apexpy'],check=True,timeout=240)
import numpy as np,apexpy
lat=np.repeat(np.arange(89.5,-90,-1.),360);lon=np.tile(np.arange(-179.5,180,1.),180)
output={}
for year in [2025.,2027.5,2030.]:
 a=apexpy.Apex(date=year,refh=350.)
 al,ao=a.geo2apex(lat,lon,350.);qd,qo=a.geo2qd(lat,lon,350.)
 nlat,nlon,_=a.apex2geo(np.abs(al),ao,110.)
 slat,slon,_=a.apex2geo(-np.abs(al),ao,110.)
 output[str(year)]={k:np.asarray(v,dtype=np.float32) for k,v in dict(alat=al,alon=ao,nlat=nlat,nlon=nlon,slat=slat,slon=slon).items()}
 print('APEX',year,np.nanmin(al),np.nanmax(al),np.count_nonzero(~np.isfinite(al)),flush=True)
 # For magnetic local time, Apex uses the subsolar longitude mapped at 50 Earth radii.
 decs=np.repeat(np.arange(-24.,24.01,1.),360);sunlons=np.tile(np.arange(-179.5,180,1.),49)
 _,sa=a.geo2apex(decs,sunlons,50*6371.)
 output[str(year)]['sunlon']=np.asarray(sa,dtype=np.float32)
np.savez_compressed(root/'apex_atlas.npz',**{yr+'_'+k:v for yr,row in output.items() for k,v in row.items()})
(root/'apex_manifest.json').write_text(json.dumps({'apexpy':apexpy.__version__,'refh_km':350,'E_height_km':110,'years':list(output),'lat':'89.5 to -89.5 by -1','lon':'-179.5 to179.5 by1','shape':[180,360],'sun_decl':'-24 to24 by1','sun_height_km':50*6371,'inputs':'IGRF-14, no observations'},indent=2))
# Retrieve author-hosted mathematical source as a separate research reference.
url='https://www.researchgate.net/publication/331067650_On_the_Relationship_Between_the_Rate_of_Change_of_Total_Electron_Content_Index_ROTI_Irregularity_Strength_CkL_and_the_Scintillation_Index_S4'
try:
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=40) as r:b=r.read()
 (root/'carrano2019.html').write_bytes(b)
except Exception as e:print('PAPER',e)
