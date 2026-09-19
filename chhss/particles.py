"""Relay public particle forecasts without changing provider issue/valid times.

ISWA does not grant browser CORS access. The hourly publication job retrieves
numerical forecasts and a GOES observation snapshot for downloaded dashboards.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests

ISWA = 'https://iswa.ccmc.gsfc.nasa.gov/api/redirect?dataID='
REFM = 'https://services.swpc.noaa.gov/text/relativistic-electron-fluence-tabular.txt'
GOES = 'https://services.swpc.noaa.gov/json/goes/primary/integral-protons-3-day.json'
SOURCES = {'umasep10': ISWA+'1653', 'umasep50': ISWA+'1655', 'goesProtons': GOES,
           'release30': ISWA+'1218', 'release60': ISWA+'1219',
           'release90': ISWA+'1220', 'refm': REFM}


def retrieve(key, url, get=requests.get):
    response = get(url, timeout=(8, 20))
    response.raise_for_status()
    if urlparse(response.url).hostname not in ('iswa.ccmc.gsfc.nasa.gov', 'services.swpc.noaa.gov'):
        raise ValueError('Unexpected source redirect')
    payload = response.text if key == 'refm' else response.json()
    if key == 'refm':
        if ':Created:' not in payload or '# UTC Date' not in payload:
            raise ValueError('Invalid REFM bulletin')
    elif key == 'goesProtons':
        if not isinstance(payload, list):
            raise ValueError('Invalid GOES proton observations')
        payload = [r for r in payload if r.get('energy') in ('>=10 MeV', '>=50 MeV')]
        if not payload or not all(any(r['energy'] == energy for r in payload)
                                  for energy in ('>=10 MeV', '>=50 MeV')):
            raise ValueError('Missing GOES 10 or 50 MeV observations')
    else:
        submission = payload.get('sep_forecast_submission', {})
        if not submission.get('issue_time') or not submission.get('forecasts'):
            raise ValueError('Missing SEP submission dates or forecasts')
        datetime.fromisoformat(submission['issue_time'].replace('Z', '+00:00'))
    return {'payload': payload, 'sourceURL': response.url,
            'retrievedAt': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            'error': None}


def collect(previous=None, get=requests.get):
    previous = previous or {}
    result = {'schemaVersion': 'particle-forecasts-1', 'sources': {}}
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {key: pool.submit(retrieve, key, url, get) for key, url in SOURCES.items()}
        for key, job in jobs.items():
            try:
                result['sources'][key] = job.result()
            except Exception as exc:
                # Preserve the original successful retrieval time on failure.
                result['sources'][key] = {**previous.get('sources', {}).get(key, {}),
                                          'error': str(exc)[:240]}
    result['attemptedAt'] = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    return result


def publish(root):
    from .publish import read, write
    path = root / 'particle-forecasts.json'
    result = collect(read(path, {}))
    write(path, result)
    return result
