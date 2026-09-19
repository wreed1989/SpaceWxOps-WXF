import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np

from chhss import core, pipeline, publish, aia_quality
from scripts.archive_backfill import package

ROOT = Path(__file__).resolve().parents[1]


class ScienceTests(unittest.TestCase):
    def test_registered_current_mask_and_core_counts(self):
        pack = json.loads((ROOT / 'chhss-data/current.json').read_text())
        measured = pack['measured']
        shape = (measured['height'], measured['width'])
        mask = core.decode_runs(measured['maskRuns'], shape)
        labels = core.decode_runs(measured['coreLabelRuns'], shape)
        self.assertEqual(hashlib.sha256(mask.tobytes()).hexdigest(), pack['maskId'])
        for index, key in enumerate(core.CORES, 1):
            selected = labels == index
            self.assertEqual(int(selected.sum()), measured['window'][key]['disk'])
            self.assertEqual(int(mask[selected].sum()), measured['window'][key]['ch'])

    def test_signed_mixed_and_limb_measurements(self):
        mask = np.ones((20, 20), dtype=bool)
        mu = np.full(mask.shape, .8)
        for sign in [-1, 1]:
            result = core.polarity(mask, np.full(mask.shape, 8 * sign), mu, np.ones(mask.shape))
            self.assertEqual(result['polarity'], sign)
        field = np.full(mask.shape, 8.)
        field[:, 10:] = -8
        self.assertIsNone(core.polarity(mask, field, mu, np.ones(mask.shape))['polarity'])
        self.assertIsNone(core.polarity(mask, field, mu * 0 + .2, np.ones(mask.shape))['polarity'])

    def test_missing_recurrence_and_no_signal_not_scored(self):
        case = {'caseId': 'test', 'speedKms': 500, 'targetStart': '2026-09-05T00:00:00Z'}
        report = core.verify([case], {'2026-09-05': {'speed': 500, 'hours': 24}})
        self.assertEqual(report['metrics']['n'], 0)
        report = core.verify([{**case, 'speedKms': None}], {})
        self.assertEqual(report['coverage']['abstainedCases'], 1)
        self.assertFalse(report['promotion']['eligible'])

    def test_fixed_daily_target_does_not_search_a_better_peak(self):
        case = {'caseId': 'test', 'speedKms': 500, 'targetStart': '2026-09-05T00:00:00Z',
                'groupId': 'test-block', 'signal': True}
        truth = {'2026-09-05': {'speed': 450, 'hours': 24},
                 '2026-08-09': {'speed': 460, 'hours': 24},
                 '2026-09-06': {'speed': 500, 'hours': 24}}
        report = core.verify([case], truth)
        self.assertEqual(report['metrics']['mae'], 50)
        self.assertEqual(report['metrics']['recurrenceMae'], 10)
        self.assertEqual(report['metrics']['skill'], -4)

    def test_omni_fill_remains_missing(self):
        row = ['0'] * 57
        row[:3] = ['2026', '244', '12']
        row[24] = '9999'
        self.assertIsNone(pipeline.omni_line(' '.join(row))['speed'])
        row[24] = '450'
        self.assertEqual(pipeline.omni_line(' '.join(row))['speed'], 450)

    def test_nrt_rejects_unverified_quality_flags(self):
        self.assertEqual(aia_quality.validate(None, 0)['quality'], 0)
        with self.assertRaises(ValueError):
            aia_quality.validate(None, 0x400)

    def test_registered_fits_path(self):
        import astropy.units as u
        import sunpy.map
        n = 256
        y, x = np.indices((n, n))
        image = np.full((n, n), 100.)
        image[(abs(x-128)<15) & (y>80) & (y<130)] = 20.
        base = {'CTYPE1': 'HPLN-TAN', 'CTYPE2': 'HPLT-TAN', 'CUNIT1': 'arcsec',
                'CUNIT2': 'arcsec', 'CRPIX1': 128.5, 'CRPIX2': 128.5,
                'CRVAL1': 0., 'CRVAL2': 0., 'CDELT1': 8.565, 'CDELT2': 8.565,
                'DSUN_OBS': 149597870700., 'RSUN_OBS': 959.23, 'RSUN_REF': 695700000.,
                'HGLN_OBS': 0., 'HGLT_OBS': 0., 'DATE-OBS': '2026-09-01T12:00:00Z',
                'QUALITY': 0, 'EXPTIME': 2., 'TELESCOP': 'SDO', 'WAVEUNIT': 'angstrom'}
        maps = {w: sunpy.map.Map(image, {**base, 'INSTRUME': 'AIA', 'DETECTOR': 'AIA',
                    'WAVELNTH': w, 'BUNIT': 'DN'}) for w in [171, 193, 211]}
        hmi = sunpy.map.Map(np.full((n, n), 10.), {**base, 'INSTRUME': 'HMI',
                              'DETECTOR': 'HMI', 'WAVELNTH': 6173, 'BUNIT': 'G'})
        class Fixture:
            def hmi(self, when):
                return hmi, {'degraded': False, 'quality': 0, 'qualityFlags': []}, core.date(when)
            def aia(self, when, wave):
                return maps[wave], {'observationTime': core.iso(core.date(when))}
        pack = pipeline.make_pack(Fixture(), '2026-09-01T12:00:00Z', size=256)
        self.assertTrue(pack['historical'])
        self.assertEqual(pack['polarity']['sector']['M']['polarity'], 1)
        self.assertGreater(pack['measured']['window']['M']['A'], 0)
        self.assertTrue(hmi.unit.is_equivalent(u.G))


class PublicationTests(unittest.TestCase):
    def test_failure_keeps_original_observation_age_and_no_old_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack = {'observationTime': '2026-09-01T12:00:00Z', 'measurementEngine': core.VERSION}
            publish.write(root / 'current.json', pack)
            publish.write(root / 'status.json', {'ok': False, 'error': 'Source unavailable'})
            feed = publish.build(root)
            self.assertEqual(feed['current'], pack)
            self.assertFalse(feed['status']['current']['ok'])
            self.assertIsNone(feed['verification'])
            self.assertEqual(feed['historyCount'], 0)

    def test_latest_period_report_stays_labeled_and_history_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {'caseId': 'same', 'issueTime': '2026-09-01T18:00:00Z'}
            for period in ['2026-08-01_2026-08-08', '2026-09-01_2026-09-08']:
                dest = root / 'backfill' / period
                publish.write(dest / 'cases.json', [row])
                publish.write(dest / 'validation.json', {'metrics': {'n': 1}, 'pairs': list(range(220))})
            feed = publish.build(root)
            self.assertEqual(feed['historyCount'], 1)
            self.assertEqual(feed['verificationPeriod'], '2026-09-01_2026-09-08')
            self.assertEqual(len(feed['verification']['pairs']), 200)
            self.assertEqual(feed['verification']['metrics'], {'n': 1})
            self.assertEqual(len(publish.read(root / 'history.json')['cases']), 1)

    def test_live_failure_does_not_write_a_fresh_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch('chhss.pipeline.make_pack', side_effect=ValueError('No quality data')), patch('builtins.print'):
                self.assertFalse(pipeline.live(None, output))
            self.assertFalse((output / 'current.json').exists())
            self.assertFalse(publish.read(output / 'status.json')['ok'])

    def test_archive_requires_full_evidence_and_records_all_member_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'run'
            root.mkdir()
            destination = Path(directory) / 'archive.zip'
            with self.assertRaises(ValueError):
                package(root, destination, 'https://example.test/archive.zip')
            progress = {'start': '2026-09-01T00:00:00Z', 'endExclusive': '2026-09-02T00:00:00Z',
                        'attempted': 1, 'succeeded': 1, 'failed': 0}
            for name, value in [('cases.json', [{'caseId': 'test'}]), ('validation.json', {}),
                                ('backfill-progress.json', progress), ('omni-manifest.json', {})]:
                publish.write(root / name, value)
            publish.write(root / 'history/20260901.json', {'maskId': 'test'})
            for name in ['omni_hourly.jsonl.gz', 'source-commit.txt', 'environment.txt']:
                (root / name).write_bytes(b'test')
            manifest = package(root, destination, 'https://example.test/archive.zip')
            self.assertEqual(manifest['sha256'], hashlib.sha256(destination.read_bytes()).hexdigest())
            self.assertIn('history/20260901.json', manifest['members'])
            self.assertEqual(manifest['succeeded'], 1)


if __name__ == '__main__':
    unittest.main()
