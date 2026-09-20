"""Associate reported flare inputs; never substitute an active-region centre for a flare."""
import math
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

FLARES = 'https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json'
EVENTS = 'https://services.swpc.noaa.gov/json/edited_events.json'
SOLAR_DEMON = 'https://www.sidc.be/solardemon/flares.php?min_seq=1&min_flux_est=0.000000001&days=14&science=0'


def date(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def number(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None


def position(value):
    m = re.fullmatch(r'([NS])(\d{1,2})([EW])(\d{1,2})', str(value or '').strip())
    if not m or int(m[2]) > 90 or int(m[4]) > 90:
        return None
    return (int(m[2]) * (1 if m[1] == 'N' else -1), int(m[4]) * (1 if m[3] == 'W' else -1))


class _Table(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr': self.row = []
        if tag in ('td', 'th') and self.row is not None: self.cell = []

    def handle_data(self, text):
        if self.cell is not None: self.cell.append(text)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split())); self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row); self.row = None


def solar_demon_rows(text):
    """Read the provider's labelled quick-look table, including off-limb detections."""
    if 'Stonyhurst Longitude' not in text or 'Stonyhurst Latitude' not in text:
        raise ValueError('Solar Demon coordinate table missing')
    table = _Table(); table.feed(text); month = None; out = []
    for row in table.rows:
        if len(row) == 1:
            try: month = datetime.strptime(row[0], '%B, %Y').replace(tzinfo=timezone.utc)
            except ValueError: pass
        if month is None or len(row) < 16: continue
        try:
            day = month.replace(day=int(row[0]))
            start, peak, end = [day.replace(hour=int(v[:2]), minute=int(v[3:5])) for v in row[2:5]]
            if peak < start: peak += timedelta(days=1)
            if end < peak: end += timedelta(days=1)
            identity = int(row[5]); lat, lon, radius = map(number, row[6:9])
        except (ValueError, TypeError): continue
        out.append({'start':start, 'peak':peak, 'end':end, 'latitude':lat, 'longitude':lon,
                    'radius':radius, 'url':f'https://www.sidc.be/solardemon/flares.php?fid={identity}&science=0'})
    return out


def event_inputs(raw, edits, now, demon=()):
    peak, start, end = date(raw.get('max_time')), date(raw.get('begin_time')), date(raw.get('end_time'))
    flux = number(raw.get('max_xrlong'))
    if not peak or not start or start > peak or peak > now or flux is None or flux <= 0:
        raise ValueError('Invalid flare peak/start/flux')
    integral = number(raw.get('current_int_xrlong'))
    complete = bool(end and peak <= end <= now and integral is not None and integral >= 0)
    event = dict(peakTime=peak.isoformat().replace('+00:00','Z'), startTime=start.isoformat().replace('+00:00','Z'),
                 flareClass=raw.get('max_class'), peakFlux=flux, riseMinutes=(peak-start).total_seconds()/60,
                 longitude=None, latitude=None, region=None, integral=integral if complete else None,
                 integralEnd=end.isoformat().replace('+00:00','Z') if complete else None,
                 previous='unknown', previousIntegral=None, opticalClass='', radio='unknown',
                 inputSources={'flare':FLARES, 'integral':FLARES if complete else None}, inputNotes=[])
    # Use the event number AND nearby dates, since SWPC reuses event numbers.
    anchors = [r for r in edits if r.get('type') == 'XRA' and date(r.get('max_datetime'))
               and abs((date(r['max_datetime'])-peak).total_seconds()) <= 120
               and str(r.get('particulars1','')).strip().upper() == str(raw.get('max_class','')).upper()]
    bins = {r['bin'] for r in anchors if r.get('bin') is not None}
    linked = [r for r in edits if len(bins) == 1 and r.get('bin') in bins and date(r.get('begin_datetime'))
              and abs((date(r['begin_datetime'])-start).total_seconds()) <= 6*3600]
    regions = {int(r['region']) for r in linked if number(r.get('region')) and number(r['region']) > 0}
    if len(regions) == 1: event['region'] = regions.pop()
    located = [(position(r.get('location')), r) for r in linked if r.get('type') in ('XRA','FLA') and position(r.get('location'))]
    conflict = bool(located and any(abs(p[0]-located[0][0][0])>5 or abs(p[1]-located[0][0][1])>5 for p,_ in located))
    if located and not conflict:
        pos, report = min(located, key=lambda pair: abs(((date(pair[1].get('max_datetime')) or start)-peak).total_seconds()))
        event.update(latitude=pos[0], longitude=pos[1]); event['inputSources']['location'] = EVENTS
        event['locationMethod'] = 'SWPC linked flare report'
    elif conflict or len(bins)>1:
        event['inputNotes'].append('Conflicting SWPC flare associations; coordinates require review.')
    else:
        matches = [r for r in demon if abs((r['peak']-peak).total_seconds()) <= 600 and r['start'] <= (end or peak+timedelta(minutes=10)) and r['end'] >= start]
        if len(matches) == 1:
            r = matches[0]
            if r['radius'] is not None and r['radius'] <= 1 and all(v is not None and abs(v)<=90 for v in (r['latitude'],r['longitude'])):
                event.update(latitude=r['latitude'],longitude=r['longitude']); event['inputSources']['location'] = r['url']
                event['locationMethod'] = 'SDO/AIA Solar Demon · temporal association'
            else:
                event['inputNotes'].append('Associated Solar Demon detection is off-limb or has no disk coordinates; location remains unknown.')
                event['inputSources']['locationContext'] = r['url']
        elif len(matches)>1: event['inputNotes'].append('Multiple nearby AIA detections; location remains unknown.')
    optical = {str(r.get('particulars1') or '').strip() for r in linked if r.get('type') == 'FLA'} - {''}
    if len(optical)==1: event['opticalClass']=optical.pop(); event['inputSources']['opticalClass']=EVENTS
    sweep = {m.group(1) for r in linked if r.get('type')=='RSP' for m in [re.match(r'^(II|IV)(?:/|\s|$)', str(r.get('particulars1') or '').strip())] if m}
    if sweep: event['radio']='+'.join(sorted(sweep)); event['inputSources']['radio']=EVENTS
    # A positive association is useful; an incomplete report catalogue cannot establish 'no previous flare'.
    prior = [r for r in edits if event['region'] and number(r.get('region'))==event['region'] and r.get('type')=='XRA'
             and date(r.get('max_datetime')) and date(r['max_datetime']) < start]
    if prior:
        previous_peak = max(date(r['max_datetime']) for r in prior)
        candidates = [r for r in prior if date(r['max_datetime'])==previous_peak]
        report = sorted(candidates, key=lambda r: (r.get('status_text') != '+', str(r.get('observatory'))))[0]
        event.update(previous='yes', previousPeak=previous_peak.isoformat().replace('+00:00','Z'))
        previous_end, previous_integral = date(report.get('end_datetime')), number(report.get('particulars2'))
        if previous_end and previous_peak <= previous_end < start and previous_integral is not None and previous_integral>=0:
            event['previousIntegral']=previous_integral
        event['inputSources']['previous']=EVENTS
    if event['longitude'] is None: event['inputNotes'].append('No unambiguous disk location: probability model will use its trained missing-location handling.')
    if not complete: event['inputNotes'].append('Completed half-power integral unavailable; peak-flux estimate waits for a completed flare.')
    return event
