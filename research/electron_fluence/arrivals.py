"""Submission-gated CME guidance. Observed arrivals/closeout fields are never read.

Historical API snapshots can contain later revisions: submission gating is necessary
but not proof of a pristine as-issued archive. Preserve raw live snapshots too.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

URL = 'https://kauai.ccmc.gsfc.nasa.gov/CMEscoreboard/WS/get/predictions'


def acquire(cache, start, stop):
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True)
    response = requests.get(URL, params={'CMEtimeStart': start, 'CMEtimeEnd': stop,
        'closeOutCMEsOnly': 'false', 'skipNoArrivalObservedCMEs': 'false'}, timeout=90)
    response.raise_for_status()
    events = response.json()
    if not isinstance(events, list):
        raise ValueError('Scoreboard did not return an event list')
    path = cache/f'{start}_{stop}.json'
    path.write_bytes(response.content)
    meta = {'url': response.url, 'retrievedAt': datetime.now(timezone.utc).isoformat(),
            'sha256': hashlib.sha256(response.content).hexdigest(), 'path': path.name,
            'eventCount': len(events)}
    path.with_suffix('.meta.json').write_text(json.dumps(meta, indent=2)+'\n')
    return events, meta


def timestamp(value):
    try:
        t = pd.Timestamp(value)
        return t.tz_convert('UTC') if t.tzinfo and not pd.isna(t) else None
    except (ValueError, TypeError):
        return None


def number(value, lo, hi, default):
    try:
        n = float(value)
        return n if np.isfinite(n) and lo <= n <= hi else default
    except (ValueError, TypeError):
        return default


def provider(method):
    s = method.lower()
    for token, group in [('nasa m2m','NASA M2M'),('gsfc swrc','NASA M2M'),
                         ('noaa','NOAA/SWPC'),('met office','Met Office'),('huxt','HUXt'),
                         ('bom','BoM'),('kswc','KSWC')]:
        if token in s:
            return group
    return method.strip()


class ArrivalArchive:
    def __init__(self, events, available=True):
        self.available = available
        self.rows = []
        for event in events:
            observed = timestamp(event.get('observedTime'))
            if observed is None:
                continue
            for p in event.get('predictions') or []:
                method = str(p.get('predictedMethodName') or '')
                if not method or 'average' in method.lower() or 'median' in method.lower():
                    continue
                submitted, arrival = timestamp(p.get('submissionTime')), timestamp(p.get('predictedArrivalTime'))
                if submitted is None or arrival is None or not observed <= submitted <= arrival:
                    continue
                if arrival-observed > pd.Timedelta(days=14):
                    continue
                minus = number(p.get('uncertaintyMinusInHrs'),0,72,None)
                plus = number(p.get('uncertaintyPlusInHrs'),0,72,None)
                kp = number(p.get('predictedMaxKpUpperRange'),0,9,None)
                self.rows.append({'event':str(event.get('cmeID') or observed.isoformat()),
                    'provider':provider(method),'method':method,'submitted':submitted,
                    'arrival':arrival,'minus':minus,'plus':plus,'kp':kp})
        self.rows.sort(key=lambda r:(r['submitted'],r['method']))
        self.submitted = np.array([r['submitted'].value for r in self.rows],dtype=np.int64)

    def at(self, origin):
        """Latest available forecast per CME/provider, with summaries de-duplicated."""
        origin = pd.Timestamp(origin)
        stop = np.searchsorted(self.submitted,origin.value,side='right')
        start = np.searchsorted(self.submitted,(origin-pd.Timedelta(days=17)).value)
        latest = {}
        for r in self.rows[start:stop]:
            latest[(r['event'],r['provider'])] = r
        return [r for r in latest.values() if -72 <= (r['arrival']-origin).total_seconds()/3600 <= 72]

    def features(self, origin):
        rows = self.at(origin)
        # These are ensemble agreement descriptors, NOT calibrated impact probabilities.
        f = {'cme_feed_available':float(self.available),'cme_event_count':0.,
             'cme_provider_count':0.,'cme_nearest_arrival_hours':96.,
             'cme_arrival_spread_hours':0.,'cme_reported_uncertainty_hours':0.,
             'cme_uncertainty_coverage':0.,'cme_forecast_kp':0.,'cme_kp_coverage':0.}
        for a,b in [(-72,-24),(-24,0),(0,12),(12,24),(24,48),(48,72)]:
            f[f'cme_window_{a}_{b}h'] = 0.
        groups = {}
        for r in rows:
            groups.setdefault(r['event'],[]).append(r)
        f['cme_event_count'] = float(len(groups))
        f['cme_provider_count'] = float(len({r['provider'] for r in rows}))
        nearest = None
        for group in groups.values():
            hours = np.array([(r['arrival']-origin).total_seconds()/3600 for r in group])
            mid = float(np.median(hours))
            if nearest is None or abs(mid) < abs(nearest):
                nearest = mid
                f['cme_nearest_arrival_hours'] = mid
                f['cme_arrival_spread_hours'] = float(np.max(hours)-np.min(hours))
            for a,b in [(-72,-24),(-24,0),(0,12),(12,24),(24,48),(48,72)]:
                # Fraction of providers for this event whose stated window overlaps.
                # An unstated uncertainty is a point estimate, not a made-up +/- range.
                overlap = [(h+(r['plus'] or 0) >= a and h-(r['minus'] or 0) < b)
                           for h,r in zip(hours,group)]
                f[f'cme_window_{a}_{b}h'] = max(f[f'cme_window_{a}_{b}h'],float(np.mean(overlap)))
        widths = [r['minus']+r['plus'] for r in rows if r['minus'] is not None and r['plus'] is not None]
        kps = [r['kp'] for r in rows if r['kp'] is not None]
        if rows:
            f['cme_uncertainty_coverage'] = len(widths)/len(rows)
            f['cme_kp_coverage'] = len(kps)/len(rows)
        if widths: f['cme_reported_uncertainty_hours'] = float(np.median(widths))
        if kps: f['cme_forecast_kp'] = float(np.max(kps))
        return f

    def context(self, origin):
        return {'source':URL,'available':self.available,'features':self.features(origin),
                'predictions':[{**r, 'submitted':r['submitted'].isoformat(),
                    'arrival':r['arrival'].isoformat()} for r in self.at(origin)],
                'caution':'Provider agreement is not an impact probability. Arrival timing does not forecast Bz or guarantee an electron dropout.'}


def load_archive(cache):
    events = []
    for path in sorted(Path(cache).glob('*.json')):
        if path.name == 'manifest.json' or path.name.endswith('.meta.json'):
            continue
        raw = json.loads(path.read_text())
        if isinstance(raw,list): events.extend(raw)
    return ArrivalArchive(events)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,required=True);p.add_argument('--start',required=True);p.add_argument('--stop',required=True)
    a=p.parse_args();events,meta=acquire(a.cache,a.start,a.stop);print(json.dumps(meta,indent=2))
