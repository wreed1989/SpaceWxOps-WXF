"""NAIRAS producer format, dose units and failure isolation."""
import json
import tempfile
from pathlib import Path
import unittest
from chhss.nairas import decode, normalize, collect, retrieve


def grid():
    return {'lat': [lat for lat in range(-90, 91) for lon in range(360)],
            'lon': list(range(360)) * 181, 'effective_dose': [10.] * 65160,
            'FlAGSEP': False}


class NAIRASTests(unittest.TestCase):
    def test_download_keeps_product_epoch_and_rate_units(self):
        from scripts.build_dashboard import build
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feed = root / 'feed.json'
            feed.write_text(json.dumps({'schemaVersion': 'chhss-feed-1'}))
            source = {'schemaVersion': 'nairas-effective-dose-1', 'sources': {'forecast': {
                'sourceTime': '2026-09-06T20:15:00Z', 'unit': 'mSv/h', 'values': [.012],
                'error': '</script>source unavailable'}}}
            nairas = root / 'nairas.json'; nairas.write_text(json.dumps(source))
            output = build(root / 'dashboard.html', feed=feed, nairas=nairas).read_text()
            embedded = output.split('id="nairasBootstrap">')[1].split('</script>')[0]
            self.assertNotIn('</script>', embedded)
            self.assertEqual(json.loads(embedded), source)

    def test_provider_concatenated_metadata(self):
        self.assertEqual(decode('{"effective_dose":[10]}{"Neutron_Monitor":{}}')['effective_dose'], [10])
        self.assertEqual(decode('  {"a":1}\n'), {'a': 1})
        with self.assertRaisesRegex(ValueError, 'Unexpected trailing'):
            decode('{"a":1}{"effective_dose":[999]}')
        with self.assertRaises(ValueError):
            decode('{"a":1}broken')

    def test_full_grid_conversion_hemispheres_and_fill(self):
        source = grid()
        source['effective_dose'][0] = 1000
        source['effective_dose'][-1] = 20
        source['effective_dose'][360] = -999
        out = normalize(source)
        self.assertEqual(out['values'][0], 1.)  # South pole: µSv/h -> mSv/h
        self.assertEqual(out['values'][-1], .02)  # North pole, 359 E
        self.assertIsNone(out['values'][360])
        self.assertEqual(out['unit'], 'mSv/h')
        self.assertEqual(out['altitudeKm'], 20)
        self.assertEqual(len(out['values']), 65160)
        # Source order is not assumed.
        for key in ['lat', 'lon', 'effective_dose']:
            source[key].reverse()
        self.assertEqual(normalize(source)['values'], out['values'])

    def test_missing_duplicate_and_wrong_altitude_rejected(self):
        source = grid()
        source['lon'][0] = 1
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            normalize(source)
        source = grid(); source['lat'].pop()
        with self.assertRaisesRegex(ValueError, 'complete'):
            normalize(source)
        class Response:
            def raise_for_status(self): pass
            def json(self):
                return {'files': [{'url': 'https://iswa.ccmc.gsfc.nasa.gov/EffectiveDose15km.json', 'timestamp': '2026-09-19T04:00:00Z'}]}
        with self.assertRaisesRegex(ValueError, 'altitude'):
            retrieve('nowcast', 2643, lambda *a, **k: Response())

    def test_outage_preserves_old_epoch_without_relabelling(self):
        old = {'sourceTime': '2026-09-06T20:15:00Z', 'retrievedAt': '2026-09-19T04:00:00Z', 'values': [.01]}
        def fail(*args, **kwargs): raise TimeoutError('source timeout')
        result = collect({'sources': {'forecast': old}}, fail)
        self.assertEqual(result['sources']['forecast']['sourceTime'], old['sourceTime'])
        self.assertEqual(result['sources']['forecast']['retrievedAt'], old['retrievedAt'])
        self.assertIn('timeout', result['sources']['nowcast']['error'])

if __name__ == '__main__': unittest.main()
