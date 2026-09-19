"""Package a complete backfill run, with checksums and explicit coverage.

The archive includes all acquired measurements, truth, failures, source, and
environment. 'Complete run' does not imply that all requested observations exist.
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def package(source, destination, release_url):
    source, destination = Path(source), Path(destination)
    required = ['cases.json', 'validation.json', 'backfill-progress.json',
                'omni-manifest.json', 'omni_hourly.jsonl.gz',
                'source-commit.txt', 'environment.txt']
    for name in required:
        if not (source / name).is_file():
            raise ValueError(f'Missing evidence: {name}')
    cases = json.loads((source / 'cases.json').read_text())
    histories = sorted((source / 'history').glob('*.json'))
    if len(histories) != len(cases):
        raise ValueError('Registered observation count differs from case count')
    files = sorted(p for p in source.rglob('*') if p.is_file() and p.name != 'archive.json')
    members = {p.relative_to(source).as_posix(): {
        'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()
    } for p in files}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, path.relative_to(source).as_posix())
    progress = json.loads((source / 'backfill-progress.json').read_text())
    manifest = {'schemaVersion': 'chhss-archive-1', 'url': release_url,
                'asset': destination.name, 'bytes': destination.stat().st_size,
                'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                'sourceCommit': (source / 'source-commit.txt').read_text().strip(),
                'start': progress['start'], 'endExclusive': progress['endExclusive'],
                'attempted': progress['attempted'], 'succeeded': progress['succeeded'],
                'failed': progress['failed'], 'members': members}
    (source / 'archive.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--url', required=True)
    args = parser.parse_args()
    package(args.source, args.output, args.url)
