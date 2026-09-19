"""Published particle data retains source times through partial outages."""
import unittest
from chhss.particles import collect, retrieve, SOURCES

SUBMISSION = {'sep_forecast_submission': {'issue_time': '2026-09-19T05:00:00Z',
               'forecasts': [{'prediction_window': {'end_time': '2026-09-19T07:00:00Z'}}]}}

class Response:
    url = 'https://iswa.ccmc.gsfc.nasa.gov/iswa_data_tree/model/example.json'
    text = ':Created: 2026 Sep 19 0014 UTC\n# UTC Date\n'
    def raise_for_status(self): pass
    def json(self): return SUBMISSION

class ParticleTests(unittest.TestCase):
    def test_partial_failure_keeps_original_retrieval_and_payload(self):
        old = {'payload': SUBMISSION, 'retrievedAt': '2026-09-18T00:00:00Z'}
        def get(url, **kwargs):
            if url == SOURCES['release30']: raise TimeoutError('provider timeout')
            return Response()
        out = collect({'sources': {'release30': old}}, get)
        self.assertEqual(out['sources']['release30']['retrievedAt'], old['retrievedAt'])
        self.assertEqual(out['sources']['release30']['payload'], SUBMISSION)
        self.assertIn('timeout', out['sources']['release30']['error'])
        self.assertIsNone(out['sources']['umasep10']['error'])
        self.assertEqual(out['sources']['umasep10']['payload'], SUBMISSION)
        self.assertEqual(out['sources']['umasep10']['payload']['sep_forecast_submission']['issue_time'], '2026-09-19T05:00:00Z')

    def test_invalid_response_is_not_published_as_a_forecast(self):
        response = Response()
        response.json = lambda: {'error': 'no data'}
        with self.assertRaisesRegex(ValueError, 'Missing SEP'):
            retrieve('umasep10', SOURCES['umasep10'], lambda *a, **k: response)
        response.url = 'https://example.com/unexpected'
        with self.assertRaisesRegex(ValueError, 'Unexpected source'):
            retrieve('refm', SOURCES['refm'], lambda *a, **k: response)

    def test_integral_channels_do_not_mix_with_other_energies(self):
        response = Response()
        response.json = lambda: [{'energy': e, 'flux': .25, 'time_tag': '2026-09-19T06:00Z'}
                                 for e in ('>=10 MeV', '>=50 MeV', '>=100 MeV')]
        result = retrieve('goesProtons', SOURCES['goesProtons'], lambda *a, **k: response)
        self.assertEqual([r['energy'] for r in result['payload']], ['>=10 MeV', '>=50 MeV'])
        self.assertEqual(SOURCES['umasep50'].split('=')[-1], '1655')
        response.json = lambda: [{'energy': '>=10 MeV'}]
        with self.assertRaisesRegex(ValueError, '10 or 50'):
            retrieve('goesProtons', SOURCES['goesProtons'], lambda *a, **k: response)

if __name__ == '__main__': unittest.main()
