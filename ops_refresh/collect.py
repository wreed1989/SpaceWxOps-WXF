"""Public operational delivery. No coefficients, credentials or fabricated issue times."""
from __future__ import annotations
import concurrent.futures
import hashlib
import io
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else 'ops-product')
OUT.mkdir(parents=True, exist_ok=True)
NOW = datetime.now(timezone.utc)
BASES = ['https://kauai.ccmc.gsfc.nasa.gov/CMEscoreboard/WS/get/predictions', 'https://webtools.ccmc.gsfc.nasa.gov/CMEscoreboard/WS/get/predictions', 'https://ccmc.gsfc.nasa.gov/CMESB-Earth/WS/get/predictions']
if NOW >= datetime(2026, 9, 30, tzinfo=timezone.utc):
    BASES = [BASES[-1], *BASES[:-1]]
REPORT = {'schemaVersion': 'ops-delivery-1', 'checkedAt': NOW.isoformat(), 'products': {}}


def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def stamp(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def get(url, params=None, cap=50000000):
    """Bound download size and timeout; only HTTPS public products are requested."""
    with requests.get(url, params=params, timeout=(15, 60), stream=True, headers={'User-Agent': 'SpaceWxOps/operational-delivery'}) as r:
        r.raise_for_status()
        if urlparse(r.url).scheme != 'https':
            raise ValueError('Non-HTTPS redirect')
        parts, size = [], 0
        for piece in r.iter_content(65536):
            size += len(piece)
            if size > cap:
                raise ValueError('Product exceeds size limit')
            parts.append(piece)
        return b''.join(parts), r.url, r.headers.get('Last-Modified')


def scoreboard():
    errors = []
    params = {'CMEtimeStart': (NOW-timedelta(days=30)).strftime('%Y-%m-%d'),
              'CMEtimeEnd': (NOW+timedelta(days=1)).strftime('%Y-%m-%d'),
              'closeOutCMEsOnly': 'false', 'skipNoArrivalObservedCMEs': 'false'}
    for base in BASES:
        try:
            raw, url, _ = get(base, params, 8000000)
            rows = json.loads(raw)
            if not isinstance(rows, list) or any(not isinstance(r, dict) or not r.get('cmeID') or not stamp(r.get('observedTime')) for r in rows):
                raise ValueError('Invalid Scoreboard schema')
            # The query covers today in full; discard future or out-of-window rows.
            rows = [r for r in rows if NOW-timedelta(days=31) <= stamp(r['observedTime']) <= NOW+timedelta(minutes=5)]
            result = {'rows': rows, 'source': url, 'retrievedAt': datetime.now(timezone.utc).isoformat(), 'windowStart': params['CMEtimeStart'], 'windowEnd': params['CMEtimeEnd']}
            save('cme-scoreboard.json', result)
            REPORT['products']['scoreboard'] = {'status': 'available', 'events': len(rows), 'retrievedAt': result['retrievedAt'], 'attempts': errors}
            return rows
        except Exception as exc:
            errors.append({'url': base, 'error': str(exc)[:180]})
    REPORT['products']['scoreboard'] = {'status': 'unavailable', 'attempts': errors}
    return []


def refm():
    url = 'https://services.swpc.noaa.gov/text/relativistic-electron-fluence-tabular.txt'
    try:
        raw, source, _ = get(url, cap=1000000)
        text = raw.decode('utf-8')
        match = re.search(r':Created:\s*(\d{4}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{4}) UTC', text)
        if not match or not re.search(r'^\d{4}\s+\d{2}\s+\d{2}\s', text, re.M):
            raise ValueError('Not a dated REFM bulletin')
        issued = datetime.strptime(match[1], '%Y %b %d %H%M').replace(tzinfo=timezone.utc)
        result = {'payload': text, 'sourceURL': source, 'retrievedAt': datetime.now(timezone.utc).isoformat()}
        save('particle-forecasts.json', {'schemaVersion': 'particle-forecasts-1', 'sources': {'refm': result}})
        REPORT['products']['refm'] = {'status': 'available' if -300 <= (NOW-issued).total_seconds() <= 129600 else 'stale', 'issuedAt': issued.isoformat()}
    except Exception as exc:
        REPORT['products']['refm'] = {'status': 'unavailable', 'error': str(exc)[:180]}


def media(url, name, kind):
    raw, source, modified = get(url)
    if kind == 'video':
        if len(raw) < 16 or raw[4:8] != b'ftyp':
            raise ValueError('Not an MP4 response')
        frames = None
    else:
        with Image.open(io.BytesIO(raw)) as im:
            frames = getattr(im, 'n_frames', 1)
            for i in range(frames):
                im.seek(i); im.load()
    (OUT/name).write_bytes(raw)
    return {'path': name, 'sourceURL': source, 'retrievedAt': datetime.now(timezone.utc).isoformat(), 'httpLastModified': modified, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'kind': kind, 'frames': frames}


def huxt():
    url = 'https://swxforecastlab.s3.eu-west-2.amazonaws.com/WSA_DONKI_huxt_animation_latest.mp4'
    try:
        item = media(url, 'huxt-animation.mp4', 'video')
        item['status'] = 'available'
        # HTTP metadata is not a model issue time.
        item['issueTimeSource'] = 'Read model times on provider animation'
        REPORT['products']['huxtAnimation'] = item
    except Exception as exc:
        REPORT['products']['huxtAnimation'] = {'status': 'unavailable', 'sourceURL': url, 'error': str(exc)[:180]}


def m2m(rows):
    candidates = []
    for event in rows:
        for p in event.get('predictions', []):
            if not re.search(r'NASA M2M|GSFC SWRC', str(p.get('predictedMethodName', '')), re.I):
                continue
            submitted = stamp(p.get('submissionTime'))
            if not submitted or submitted > NOW+timedelta(minutes=5):
                continue
            for value in re.findall(r'https://[^\s<>\"\']+', str(p.get('predictionNote', ''))):
                value = value.rstrip('),.;')
                host = urlparse(value).hostname or ''
                if host.endswith('.nasa.gov') and re.search(r'\.gif(?:$|[?&])', value, re.I):
                    candidates.append((submitted, bool(re.search(r'anim[._-]tim[._-]vel', value, re.I)), value, event['cmeID'], p.get('predictedMethodName')))
    candidates.sort(reverse=True)
    errors = []
    for submitted, _, url, event, method in candidates[:8]:
        try:
            item = media(url, 'm2m-animation.gif', 'image')
            if (item.get('frames') or 0) < 2:
                raise ValueError('Not animated')
            item.update(status='available', submittedAt=submitted.isoformat(), event=event, method=method)
            REPORT['products']['m2mAnimation'] = item
            return
        except Exception as exc:
            errors.append({'url': url, 'error': str(exc)[:120]})
    REPORT['products']['m2mAnimation'] = {'status': 'unavailable', 'attempts': errors, 'reason': 'No readable animated run linked by an eligible NASA submission'}


def main():
    rows = scoreboard()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda fn: fn(), [refm, huxt, lambda: m2m(rows)]))
    for name in ['electron-fluence.json', 'huxt-forecast.json']:
        p = OUT/name
        if p.exists():
            d = json.loads(p.read_text())
            REPORT['products'][name] = {k: d[k] for k in ['status', 'reason', 'issuedAt', 'dataAsOf', 'modelSHA256'] if k in d}
    save('manifest.json', REPORT)
    print(json.dumps(REPORT, indent=2))


if __name__ == '__main__':
    main()
