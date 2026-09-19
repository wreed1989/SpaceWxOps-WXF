"""Strict SWPC next-calendar-day benchmark, independent of magnetic inference."""
import datetime as dt
import re
import requests

URL = 'https://services.swpc.noaa.gov/text/3-day-solar-geomag-predictions.txt'


def parse(text, valid_date):
    def field(pattern):
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            raise ValueError('Missing SWPC prediction dates, issue time or M/X columns')
        return match.group(1).strip()
    dates = [dt.datetime.strptime(v, '%Y %b %d').date() for v in re.findall(
        r'\d{4}\s+[A-Z][a-z]{2}\s+\d{1,2}', field(r'^:Prediction_dates:[ \t]+(.+)$'))]
    m = [float(v) for v in field(r'^Class_M[ \t]+([\d \t]+)$').split()]
    x = [float(v) for v in field(r'^Class_X[ \t]+([\d \t]+)$').split()]
    issued = dt.datetime.strptime(field(r'^:Issued:[ \t]+(.+)$'), '%Y %b %d %H%M UTC').replace(tzinfo=dt.timezone.utc)
    if valid_date not in dates:
        raise ValueError(f'SWPC bulletin does not cover {valid_date}')
    i = dates.index(valid_date)
    if i >= len(m) or i >= len(x) or not 0 <= x[i] <= m[i] <= 100:
        raise ValueError('Incomplete or inconsistent SWPC probabilities')
    start = dt.datetime.combine(valid_date, dt.time(), tzinfo=dt.timezone.utc)
    if issued >= start + dt.timedelta(days=1):
        raise ValueError('SWPC bulletin was issued after this forecast window')
    return {'m1':m[i], 'x1':x[i], 'source':'NOAA/SWPC 3-day whole-disk flare forecast',
            'quality':'official-operational', 'method':'official_swpc',
            'issued':issued.isoformat(), 'valid_start':start.isoformat(),
            'valid_end':(start+dt.timedelta(days=1)).isoformat()}


def refresh_benchmark(payload):
    """Run even when SHARP failed; preserve nulls if SWPC itself is unavailable.

    A structured unavailable member satisfies the publication's source inventory
    contract without inventing a probability or blocking independent providers.
    """
    full = next((r for r in payload.get('regions', []) if r.get('id') == 'full-disk'), None)
    if full is None:
        return
    try:
        date = dt.datetime.fromisoformat(payload['valid_start'].replace('Z', '+00:00')).date()
        response = requests.get(URL, timeout=30)
        response.raise_for_status()
        member = parse(response.text, date)
        status = {'ok':True, 'detail':'Official benchmark refreshed independently of SHARP', 'issued':member['issued']}
    except (requests.RequestException, ValueError, KeyError) as exc:
        detail = str(exc)
        member = {'m1':None, 'x1':None, 'source':URL, 'quality':'unavailable', 'method':'official_swpc', 'note':detail}
        status = {'ok':False, 'detail':detail}
    full.setdefault('members', {})['swpc'] = member
    payload.setdefault('external_sources', {})['swpc'] = {**status, 'url':URL}


def preserve_stale_windows(payload):
    """Keep old WXF targets when the scheduler advances the provider envelope."""
    if not payload.get('generation_status', {}).get('used_previous_forecast'):
        return
    for region in payload.get('regions', []):
        member = region.get('members', {}).get('sharpmag')
        if not isinstance(member, dict):
            continue
        issued = member.get('issued') or payload['generation_status'].get('previous_issued')
        # Nested retained issuances must not drift forward on every failed retry.
        if member.get('valid_start') and member.get('valid_end'):
            continue
        try:
            issue = dt.datetime.fromisoformat(issued.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            member.update(m1=None,x1=None,quality='unavailable',note='Original WXF issue time unavailable')
            continue
        start = (issue + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        member.update(issued=issued, valid_start=start.isoformat(), valid_end=(start+dt.timedelta(days=1)).isoformat(), quality='stale-fallback')
