"""Validated passive observation evidence. No credentials in browser products.
CACTus kinematics are plane-of-sky; Solar Demon classes are EUV estimates.
Neither feed overrides an existing model or declares an Earth-directed event.
"""
import re, math
from collections import Counter
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

CACTUS = 'https://www.sidc.be/cactus/out/cmecat.txt'
DEMON = 'https://www.sidc.be/solardemon/flares.php?days=14&min_flux_est=0.00001&min_seq=1&science=0'

def stamp(s):
    try:
        d = datetime.fromisoformat(str(s).strip().replace('/', '-').replace('Z', '+00:00'))
        if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    except (ValueError, TypeError): return None

def num(s):
    try: x = float(str(s).strip())
    except (ValueError, TypeError): return None
    return x if math.isfinite(x) else None

def flare_class(s):
    m = re.fullmatch(r'([ABCMX])\s*(\d+(?:\.\d+)?)', str(s).strip(), re.I)
    if not m or float(m[2]) <= 0: return None
    return m[1].upper() + m[2]

def major(s):
    c = flare_class(s)
    return bool(c and (c[0] == 'X' or (c[0] == 'M' and float(c[1:]) >= 1)))

def parse_cactus(text):
    if not isinstance(text, str) or len(text) > 2_000_000 or 'CACT' not in text or '# CME' not in text:
        raise ValueError('cactus_schema')
    m = re.search(r':Issued:\s*(.+)', text)
    try: issued = datetime.strptime(m[1].strip(), '%a %b %d %H:%M:%S %Y').replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
    except (ValueError, TypeError): raise ValueError('cactus_issue_time') from None
    coverage = {}
    for edge, detector, day, time in re.findall(r'\b(first|last)\s+(c[23]):\s*(\d{4}/\d\d/\d\d)\s+(\d\d:\d\d:\d\d(?:\.\d+)?)', text):
        coverage[f'{edge}_{detector}'] = stamp(day+' '+time)
    if not coverage.get('last_c2') or not coverage.get('last_c3'): raise ValueError('cactus_coverage')
    events, seen, section, rejected, flows = [], set(), None, 0, 0
    for line in text.splitlines():
        if re.match(r'\s*#\s*CME\s*\|', line): section='CME'; continue
        if re.match(r'\s*#\s*Flow\s*\|', line): section='Flow'; continue
        if not re.match(r'\s*\d+\s*\|', line): continue
        if section == 'Flow': flows += 1; continue
        if section != 'CME': continue
        parts = [x.strip() for x in line.split('|')]
        if len(parts) < 10: rejected+=1; continue
        event_id, onset = parts[0], stamp(parts[1])
        values = [num(v) for v in parts[2:9]]
        if not onset or any(v is None for v in values): rejected+=1; continue
        duration,pa,width,speed,sd,lo,hi=values
        if not (0<=duration<=168 and 0<=pa<=360 and 0<width<=360 and 0<lo<=speed<=hi<=10000 and sd>=0): rejected+=1;continue
        key=f'CACTus:{onset}:{event_id}'
        if key in seen: continue
        seen.add(key)
        events.append(dict(id=key,provider_id=event_id,onset=onset,duration_h=duration,position_angle_deg=pa,
            angular_width_deg=width,median_speed_km_s=speed,speed_sd_km_s=sd,min_speed_km_s=lo,max_speed_km_s=hi,
            halo_flag=parts[9] if parts[9] in ('II','III','IV') else None,source=CACTUS,
            velocity_frame='plane_of_sky',classification='automated_candidate'))
    if rejected: raise ValueError('cactus_rejected_rows')
    return dict(format='cactus-evidence-v1',source=CACTUS,issued_at=issued,coverage=coverage,
        observed_at=max(coverage['last_c2'],coverage['last_c3']),events=sorted(events,key=lambda x:x['onset'],reverse=True)[:500],
        flows_excluded=flows,scope='LASCO C2/C3 automated CME candidates; suspicious flows excluded',
        note='Plane-of-sky speed and position angle are not radial speed, source longitude, Earth impact or arrival time.')

class Tables(HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[];self.row=[];self.cell=None;self.text=[];self.links=[];self.href=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=[]
        if tag=='a':self.href=attrs.get('href')
        if tag in ('br','p','div','tr','td','th'):self.text.append(' ')
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(re.sub(r'\s+',' ',' '.join(self.cell)).strip());self.cell=None
        if tag=='tr' and self.row:self.rows.append(self.row);self.row=[]
        if tag=='a':self.href=None
    def handle_data(self,data):
        self.text.append(data)
        if self.cell is not None:self.cell.append(data)
        if self.href:self.links.append((data.strip(),self.href))

def parse_demon(text):
    if not isinstance(text,str) or len(text)>4_000_000:raise ValueError('demon_size')
    p=Tables();p.feed(text);whole=re.sub(r'\s+',' ',' '.join(p.text))
    if 'Overview of flares' not in whole or 'Quick-look' not in whole:raise ValueError('demon_schema')
    m=re.search(r'Last processed image:.{0,240}?(\d{4}-\d\d-\d\d\s+\d\d:\d\d)\s+UTC',whole,re.I)
    processed=stamp(m[1]) if m else None
    if not processed:raise ValueError('demon_heartbeat')
    year=month=None;events=[];seen=set();rejected=0;below=0
    months={datetime(2000,n,1).strftime('%B'):n for n in range(1,13)}
    for row in p.rows:
        header=re.search(r'\b('+'|'.join(months)+r'),?\s+(20\d\d)\b',' '.join(row))
        if header:month=months[header[1]];year=int(header[2])
        if len(row)<13 or not re.fullmatch(r'\d{1,2}',row[0]):continue
        cls=flare_class(row[1])
        if not cls:continue
        if not major(cls):below+=1;continue
        if not year or not month:rejected+=1;continue
        try:
            day=int(row[0]);base=datetime(year,month,day,tzinfo=timezone.utc)
            times=[]
            for token in row[2:5]:
                if not re.fullmatch(r'\d\d:\d\d(?::\d\d)?',token):raise ValueError()
                h,mi,*se=map(int,token.split(':'));d=base.replace(hour=h,minute=mi,second=se[0] if se else 0)
                if times and d<times[-1]:d+=timedelta(days=1)
                times.append(d)
            if times[-1]-times[0]>timedelta(days=1):raise ValueError()
            event_id=row[5]
            if not event_id.isdigit():raise ValueError()
            lat,lon=num(row[6]),num(row[7])
            if lat is None or lon is None or not(-90<=lat<=90 and -180<=lon<=180):raise ValueError()
        except (ValueError,TypeError):rejected+=1;continue
        if event_id in seen:continue
        seen.add(event_id)
        ar=re.search(r'\bAR\s*(\d{4,5})\b',row[9],re.I)
        region=int(ar[1]) if ar else None
        region_full=region+10000 if region is not None and 0<region<10000 else region
        src=next((urljoin(DEMON,u) for label,u in p.links if label==event_id and urlsplit(urljoin(DEMON,u)).hostname in ('www.sidc.be','sidc.be')),DEMON)
        goes=flare_class(row[11]);peak_match=re.search(r'(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d(?::\d\d)?)',row[12])
        goes_time=stamp(peak_match[1]+' '+peak_match[2]) if peak_match else None
        events.append(dict(id='SolarDemon:'+event_id,provider_id=event_id,start=stamp(times[0].isoformat()),peak=stamp(times[1].isoformat()),end=stamp(times[2].isoformat()),
            estimated_class=cls,class_basis='EUV_estimate',goes_class=goes,goes_flux_provider_text=row[11][:80],goes_peak_time=goes_time,
            latitude=lat,stonyhurst_longitude=lon,coordinate_frame='provider_heliographic',region=region_full,provider_region=region,
            estimated_flux_provider_text=row[10][:80],source=src))
    if rejected:raise ValueError('demon_rejected_major_rows')
    return dict(format='solardemon-evidence-v1',source=DEMON,last_processed_at=processed,observed_at=processed,
        events=sorted(events,key=lambda x:x['peak'],reverse=True)[:500],threshold='estimated_M1+',days=14,below_threshold_excluded=below,
        note='M1+ EUV-estimated events only. Estimated class is not an official GOES classification. Detector heartbeat, not the last major flare, determines coverage freshness.')

def parse_connectivity(text):
    if 'Carrington' not in text or 'density' not in text:raise ValueError('connectivity_frame')
    lines=[s.strip() for s in text.splitlines() if s.strip() and not s.lstrip().startswith('#')]
    if len(lines)<5 or lines[0]!='1':raise ValueError('connectivity_version')
    radius=num(lines[1]);at=stamp(lines[2]);obs=lines[3].split();counts=[int(v) for v in lines[4].split()]
    if len(obs)!=4 or obs[0] not in ('EARTH','PSP','STA','SOLO','BEPI') or not at or len(counts)!=4 or not 0<=counts[0]<=10000 or counts[0]!=sum(counts[1:]):raise ValueError('connectivity_header')
    origin=[num(x) for x in obs[1:]]
    if any(x is None for x in origin) or radius is None or radius<=0 or origin[0]<=radius or not -90<=origin[1]<=90 or not 0<=origin[2]<=360:raise ValueError('connectivity_observer')
    pts=[];seen=set()
    for line in lines[5:]:
        v=line.split()
        if len(v)!=9 or v[0] not in ('SSW','FSW','M') or not v[1].isdigit():raise ValueError('connectivity_row')
        nums=[num(x) for x in v[2:]]
        if any(x is None for x in nums):raise ValueError('connectivity_number')
        weight,r,lat,lon,dist,hplat,hplon=nums
        if not(0<=weight<=100 and r>0 and -90<=lat<=90 and 0<=lon<=360 and dist>0):raise ValueError('connectivity_range')
        identity=(v[0],v[1])
        if identity in seen:raise ValueError('connectivity_duplicate')
        seen.add(identity)
        pts.append(dict(group=v[0],index=int(v[1]),density_pct=weight,radius_m=r,latitude=lat,carrington_longitude=lon))
    got=Counter(p['group'] for p in pts)
    if len(pts)!=counts[0] or [got[k] for k in ('SSW','FSW','M')]!=counts[1:]:raise ValueError('connectivity_count')
    return dict(format='mct-footpoints-v1',coordinate_frame='HGC',observer=obs[0],observer_time=at,observer_carrington_longitude=origin[2],
        observer_latitude=origin[1],observer_radius_m=origin[0],solar_radius_m=radius,points=pts,
        density_note='Provider tracing density within separate wind scenarios; not an event or Earth-impact probability. Mode/cycle must be interpreted separately.')

def collect_cactus(h):
    raw,_=h.request(CACTUS,authenticate=False)
    return parse_cactus(raw.decode('utf-8'))

def collect_demon(h):
    raw,_=h.request(DEMON,authenticate=False)
    return parse_demon(raw.decode('utf-8'))

def enrich_connectivity(h,product):
    for model in product.get('models',[]):
        a=model.get('parameters',{});path=a.get('path','')
        if not re.fullmatch(r'assets/[a-f0-9]{64}\.txt',path):continue
        try:
            parsed=parse_connectivity((h.root/path).read_text())
            if parsed['observer']!=model.get('body') or parsed['observer_time']!=stamp(model.get('cycle')):raise ValueError('connectivity_epoch')
            model['footpoints']=parsed
        except (ValueError,OSError,UnicodeError):model['footpoints_status']='Unavailable'
    return product
