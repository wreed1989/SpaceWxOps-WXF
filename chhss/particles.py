"""Relay public particle forecasts without changing provider issue/valid times.

ISWA does not grant browser CORS access. The existing hourly publication job
retrieves its numerical products; browser image panels use ISWA's latest-file
redirect directly, independently of this hourly numerical snapshot.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests

ISWA = 'https://iswa.ccmc.gsfc.nasa.gov/api/redirect?dataID='
REFM = 'https://services.swpc.noaa.gov/text/relativistic-electron-fluence-tabular.txt'
SOURCES = {'umasep10': ISWA+'1653', 'umasep100': ISWA+'1656',
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
