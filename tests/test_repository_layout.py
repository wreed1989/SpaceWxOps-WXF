"""Small integrity gates for the maintained runtime/verification checkout."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RepositoryLayoutTests(unittest.TestCase):
    def test_retained_dataset_manifest_matches_files_and_hashes(self):
        manifest = json.loads((ROOT / 'datasets/manifest.json').read_text())
        self.assertEqual(manifest['schema_version'], '1.0')
        entries = manifest['files']
        listed = {entry['path'] for entry in entries}
        self.assertEqual(len(listed), len(entries), 'Duplicate dataset manifest path')
        actual = {p.relative_to(ROOT).as_posix()
                  for p in (ROOT / 'datasets').rglob('*')
                  if p.is_file() and p != ROOT / 'datasets/manifest.json'}
        self.assertEqual(listed, actual)
        self.assertEqual(manifest['total_bytes'], sum(entry['bytes'] for entry in entries))
        for entry in entries:
            with self.subTest(path=entry['path']):
                data = (ROOT / entry['path']).read_bytes()
                self.assertEqual(len(data), entry['bytes'])
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])

    def test_critical_runtime_and_verification_dependencies_exist(self):
        required = (
            'SpaceWxOps_Coronal_Hole_HSS_Outlook.html', 'index.html',
            'dashboard/SpaceWxOps_3.9_WXF_FullDisk_XModel_Standalone.html',
            'sharp_mag_pipeline.py', 'sharp_mag_m1.joblib', 'sharp_mag_x1.joblib',
            'sharp_mag_manifest.json', 'sharp_mag_training_report.json',
            'external_flare_guidance.py', 'external_flare_guidance_fixed.py',
            'external_flare_guidance_strict_v3.py', 'external_flare_guidance_strict_v4.py',
            'datasets/sharp_mag_training_table_v2.csv.gz',
            'flare/refresh_evidence.py', 'chhss/publish.py', 'ops_refresh/collect.py',
            'research/electron_fluence/model.npz',
            'research/electron_fluence/model-guidance.npz',
            'research/electron_fluence/model-no-cme.npz',
            'research/electron_fluence/model-manifest.json',
            'research/electron_fluence/hindcast-evaluation.json',
            'research/electron_fluence/vendor/huxt/LICENSE.md',
            'research/electron_fluence/vendor/huxt/data/ephemeris/ephemeris.hdf5',
            'research/proton_forecast/model.json', 'docs/validation/2024-q1.json',
        )
        for path in required:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), 'Missing runtime dependency: ' + path)

    def test_tracked_footprint_is_reported(self):
        # No historical-byte or transient-cache count is presented as checkout size.
        result = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT,
                                text=True, capture_output=True, check=False)
        if result.returncode:
            self.skipTest('Source snapshot has no Git index')
        paths = [p for p in result.stdout.split('\0') if p]
        size = sum((ROOT / p).stat().st_size for p in paths)
        print('MAINTAINED_CHECKOUT ' + json.dumps({'files': len(paths), 'bytes': size}), flush=True)
