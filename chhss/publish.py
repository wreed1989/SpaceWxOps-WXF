"""Build the bounded dashboard interface from the current checkout's products.

Run after applying a worker result to the latest publication checkout. Observation
timestamps and verification metrics are copied, never restamped or recomputed.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')
    temporary.replace(path)


def build(root, now=None):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    stamp = now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    # Only compact case records and links belong here; full rasters live in releases.
    periods, cases = [], {}
    selected_report = None
    for directory in sorted((root / 'backfill').glob('*')):
        if not directory.is_dir():
            continue
        rows = read(directory / 'cases.json', [])
        progress = read(directory / 'backfill-progress.json', {})
        manifest = read(directory / 'archive.json')
        for row in rows:
            cases[row['caseId']] = row
        period = {'period': directory.name, 'cases': len(rows),
                  'progress': progress, 'archive': manifest}
        periods.append(period)
        report = read(directory / 'validation.json')
        if report:
            selected_report = (directory.name, report)
    ordered = sorted(cases.values(), key=lambda row: row['issueTime'])
    history = {'schemaVersion': 'chhss-history-1', 'generatedAt': stamp,
               'caseType': 'retrospective-reconstruction', 'cases': ordered,
               'periods': periods, 'caseCount': len(ordered)}
    write(root / 'history.json', history)
    status = read(root / 'status.json', {'ok': False, 'error': 'No live run published'})
    current = read(root / 'current.json')
    verification, verification_period = None, None
    if selected_report:
        verification_period, report = selected_report
        # Counts and metrics still refer to the whole period. Only bulky paired
        # rows are bounded; the full report remains at the explicit URL below.
        verification = {**report, 'pairs': report.get('pairs', [])[:200],
                        'excluded': report.get('excluded', [])[:200]}
    latest = periods[-1]['progress'] if periods else {}
    requested = 0
    if latest.get('start') and latest.get('endExclusive'):
        requested = (datetime.fromisoformat(latest['endExclusive'].replace('Z', '+00:00')) -
                     datetime.fromisoformat(latest['start'].replace('Z', '+00:00'))).days
    feed = {'schemaVersion': 'chhss-feed-1', 'generatedAt': stamp,
            'recipe': current.get('measurementEngine') if current else status.get('methodVersion'),
            'current': current, 'recurrence': read(root / 'recurrence.json'),
            'status': {'current': status, 'backfill': {
                'period': periods[-1]['period'] if periods else None,
                'requestedDays': requested, 'completedDays': latest.get('succeeded', 0),
                'failedDays': latest.get('failed', 0)}},
            'history': ordered[-90:], 'historyCount': len(ordered),
            'verification': verification, 'verificationPeriod': verification_period,
            'verificationAppliesToCurrent': bool(current and verification and verification.get('methodVersion')==current.get('measurementEngine')),
            'verificationURL': f'backfill/{verification_period}/validation.json' if verification else None}
    write(root / 'feed.json', feed)
    # A rolling 90-day measurement ledger is sufficient for current operations.
    # Full run evidence has explicit 30-day Actions retention; selected datasets
    # must be preserved in a release before that retention expires.
    cutoff = (now - timedelta(days=90)).isoformat().replace('+00:00', 'Z')
    for path in (root / 'live-ledger').glob('*.json'):
        row = read(path)
        if row.get('observationTime', stamp) < cutoff:
            path.unlink()
    return feed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('chhss-data'))
    root = parser.parse_args().root
    from .particles import publish as publish_particles
    from .nairas import publish as publish_nairas
    publish_particles(root)
    publish_nairas(root)
    from research.electron_fluence.huxt_run import run as run_huxt
    try:
        run_huxt(Path('../product/huxt-evidence'),root/'huxt-forecast.json')
    except Exception as exc:
        write(root/'huxt-forecast.json',{'schemaVersion':'wxf-huxt-1','issuedAt':datetime.now(timezone.utc).isoformat(),
            'status':'withheld','reason':'HUXt inputs/run unavailable: '+str(exc)[:200],'rows':[]})
    from research.electron_fluence.refresh import refresh as refresh_electrons, append_ledger
    try:
        refresh_electrons(Path('.electron-current'), root / 'electron-fluence.json', Path('../product/electron-evidence'))
        append_ledger(root / 'electron-fluence.json', root / 'electron-forecast-history.jsonl')
    except Exception as exc:
        write(root / 'electron-fluence.json', {'schemaVersion':'WXF-EF-0.2',
              'issuedAt':datetime.now(timezone.utc).isoformat(), 'status':'withheld',
              'reason':'Experimental model unavailable: '+str(exc)[:200], 'forecast':[]})
    build(root)
