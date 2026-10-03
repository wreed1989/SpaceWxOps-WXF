"""Read-only cleanup inventory; removed after the dependency audit is reviewed."""
from collections import defaultdict
from pathlib import Path
import json
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RepositoryCleanupAudit(unittest.TestCase):
    def test_inventory_and_references(self):
        paths = subprocess.check_output(
            ['git', 'ls-files', '-z'], cwd=ROOT
        ).decode().strip('\0').split('\0')
        inventory = [(p, (ROOT / p).stat().st_size) for p in paths]
        totals = defaultdict(lambda: [0, 0])
        for path, size in inventory:
            group = path.split('/')[0] if '/' in path else '[root]'
            totals[group][0] += 1
            totals[group][1] += size
        print('CLEANUP_TOTALS ' + json.dumps(dict(totals), sort_keys=True), flush=True)
        for path, size in inventory:
            print('CLEANUP_FILE ' + json.dumps([path, size]), flush=True)
        candidates = [p for p in paths if (
            p.startswith(('datasets/', 'research/cross-era/', 'research/sdo-temporal/',
                          'research/flaredb/', 'docs/validation/'))
            or p in {'ccmc_diagnostic.json', 'audit_flaredb_coverage.py',
                     'build_dataset_manifest.py', 'build_goes_region_catalog.py'}
            or (p.startswith('research/electron_fluence/') and Path(p).suffix in {'.gz', '.png', '.json'})
        )]
        sources = {}
        for p in paths:
            if Path(p).suffix in {'.py', '.js', '.cjs', '.html', '.yml', '.yaml'} and p != 'tests/test_repository_cleanup_audit.py':
                sources[p] = (ROOT / p).read_text(errors='replace').splitlines()
        for target in candidates:
            hits = []
            for source, lines in sources.items():
                if source == target:
                    continue
                for number, line in enumerate(lines, 1):
                    if target in line or Path(target).name in line:
                        hits.append([source, number, line.strip()[:220]])
            print('CLEANUP_REFERENCES ' + json.dumps({'path': target, 'hits': hits}), flush=True)
        self.assertTrue((ROOT / 'SpaceWxOps_Coronal_Hole_HSS_Outlook.html').is_file())
        self.assertTrue((ROOT / 'sharp_mag_m1.joblib').is_file())
        self.assertTrue((ROOT / 'research/electron_fluence/model-guidance.npz').is_file())
