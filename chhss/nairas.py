"""Publish the full NAIRAS 20 km effective-dose-rate grids from NASA ISWA.

The provider's effective_dose field is in microSieverts/hour (CCMC NAIRAS
model documentation). Convert once to mSv/hour. Product epochs are preserved;
fetching the latest event forecast does not make an old SEP event current.
"""
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

HOST = 'iswa.ccmc.gsfc.nasa.gov'
SOURCES = {'nowcast': 2643, 'forecast': 3589}
DOCS = 'https://ccmc.gsfc.nasa.gov/models/NAIRAS~4/'


def decode(text):
    """ISWA appends a second JSON object containing Neutron_Monitor metadata."""
    decoder = json.JSONDecoder()
    payload, end = decoder.raw_decode(text.lstrip())
    tail = text.lstrip()[end:].strip()
    if tail:
        metadata = json.loads(tail)
        if not isinstance(metadata, dict) or set(metadata) != {'Neutron_Monitor'}:
            raise ValueError('Unexpected trailing NAIRAS data')
    if not isinstance(payload, dict):
        raise ValueError('Expected NAIRAS grid object')
    return payload


def normalize(payload):
    lat, lon, values = (payload.get(k) for k in ('lat', 'lon', 'effective_dose'))
    if not all(isinstance(v, list) for v in (lat, lon, values)) or not len(lat) == len(lon) == len(values) == 65160:
        raise ValueError('Expected complete 181 by 360 NAIRAS grid')
    grid = [None] * 65160
    seen = set()
    for latitude, longitude, dose in zip(lat, lon, values):
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise ValueError('Invalid grid coordinate')
        if not (-90 <= latitude <= 90 and 0 <= longitude < 360 and latitude == int(latitude) and longitude == int(longitude)):
            raise ValueError('Unexpected NAIRAS coordinates')
        index = (int(latitude) + 90) * 360 + int(longitude)
        if index in seen:
            raise ValueError('Duplicate NAIRAS coordinate')
        seen.add(index)
        # Invalid/fill values remain missing; zero is a valid reported rate.
        grid[index] = round(dose / 1000, 9) if isinstance(dose, (int, float)) and math.isfinite(dose) and dose >= 0 else None
    if not any(value is not None for value in grid):
        raise ValueError('No valid effective dose rates')
    return {'altitudeKm': 20, 'unit': 'mSv/h', 'sourceUnit': 'µSv/h',
            'latitudes': list(range(-90, 91)), 'longitudes': list(range(360)),
            'values': grid, 'sepEvent': payload.get('FlAGSEP') is True}


def retrieve(kind, data_id, get=requests.get):
    recent_url = f'https://{HOST}/api/recent?dataID={data_id}&n=1'
    response = get(recent_url, timeout=(8, 25))
    response.raise_for_status()
    files = response.json().get('files', [])
    if len(files) != 1:
        raise ValueError('Missing NAIRAS source file')
    source = files[0]
    url, epoch = source['url'], source['timestamp']
    dt = datetime.fromisoformat(epoch.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('NAIRAS epoch must include timezone')
    if urlparse(url).hostname != HOST or urlparse(url).scheme != 'https' or not re.search(r'EffectiveDose20km\.json$', url):
        raise ValueError('Unexpected NAIRAS source or altitude')
    raw = get(url, timeout=(8, 45))
    raw.raise_for_status()
    if urlparse(raw.url).hostname != HOST:
        raise ValueError('Unexpected NAIRAS redirect')
    return {**normalize(decode(raw.text)), 'sourceTime': epoch, 'sourceURL': raw.url,
            'kind': kind, 'dataID': data_id, 'modelDocumentation': DOCS,
            'retrievedAt': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            'error': None}


def collect(previous=None, get=requests.get):
    result = {'schemaVersion': 'nairas-effective-dose-1', 'sources': {}}
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {k: pool.submit(retrieve, k, v, get) for k, v in SOURCES.items()}
        for key, job in jobs.items():
            try:
                result['sources'][key] = job.result()
            except Exception as exc:
                result['sources'][key] = {**(previous or {}).get('sources', {}).get(key, {}), 'error': str(exc)[:240]}
    result['attemptedAt'] = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    return result


def publish(root):
    from .publish import read, write
    path = root / 'nairas.json'
    result = collect(read(path, {}))
    write(path, result)
    return result
