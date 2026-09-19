"""Cache bounded, complete-month ISWA operational archives; never commit raw data."""
import argparse
import concurrent.futures
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = 'https://iswa.ccmc.gsfc.nasa.gov/hapi/'
PRODUCTS = {
    'particles': ('goesp_part_flux_P5M', ['P10', 'E2_0', 'satelliteElectron', 'satelliteProton']),
    'plasma': ('swpc_rtsw_plasma_P1M', ['ProtonDensity', 'BulkSpeed']),
    'mag': ('swpc_rtsw_mag_P1M', ['B_y', 'B_z', 'B_t']),
}


def acquire(cache, start, stop):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    start, stop = pd.Timestamp(start, tz='UTC'), pd.Timestamp(stop, tz='UTC')
    edges = [start, *pd.date_range(start.normalize() + pd.offsets.MonthBegin(), stop, freq='MS'), stop]
    edges = sorted(set(edges))
    jobs = [(name, a, b) for a, b in zip(edges, edges[1:]) for name in PRODUCTS]

    def download(job):
        name, a, b = job
        ident, parameters = PRODUCTS[name]
        params = {'id': ident, 'parameters': ','.join(parameters), 'time.min': a.isoformat(),
                  'time.max': b.isoformat(), 'format': 'csv'}
        path = cache / f'{name}-{a:%Y%m%d}-{b:%Y%m%d}.csv'
        meta_path = path.with_suffix('.json')
        if path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text())
            # An unfinished month/day is a live snapshot, not an immutable cache hit.
            if pd.Timestamp(meta['retrievedAt']) >= b and hashlib.sha256(path.read_bytes()).hexdigest() == meta.get('sha256'):
                return meta
        for attempt in range(4):
            try:
                response = requests.get(BASE + 'data', params=params, timeout=120)
                response.raise_for_status()
                content = response.content
                if not content or not content[:4].isdigit() or b'"status"' in content[:500]:
                    raise ValueError(f'Not a CSV data response: {content[:200]!r}')
                path.write_bytes(content)
                meta = {'path': path.name, 'url': response.url, 'parameters': parameters,
                        'retrievedAt': datetime.now(timezone.utc).isoformat(),
                        'start': a.isoformat(), 'stopExclusive': b.isoformat(),
                        'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}
                meta_path.write_text(json.dumps(meta, indent=2) + '\n')
                print(f'{path.name}: {len(content):,} bytes', flush=True)
                return meta
            except (requests.RequestException, ValueError):
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        manifest = list(pool.map(download, jobs))
    (cache / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for name, (ident, _) in PRODUCTS.items():
        response = requests.get(BASE + 'info', params={'id': ident}, timeout=60)
        response.raise_for_status()
        (cache / f'{name}-info.json').write_text(response.text)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--start', default='2025-04-07')
    parser.add_argument('--stop', required=True, help='Exclusive UTC date or timestamp')
    args = parser.parse_args()
    acquire(args.cache, args.start, args.stop)
