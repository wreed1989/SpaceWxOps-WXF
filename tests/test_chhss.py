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
from scripts.build_dashboard import build as build_dashboard

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

    def test_thermal_screen_separates_cool_corona_from_dark_filament(self):
        y,x=np.indices((256,256));rho=np.hypot(x-127.5,y-127.5)/120
        valid=rho<=.97
        hole=(abs(x-92)<10)&(abs(y-115)<16)
        filament=(abs(x-170)<10)&(abs(y-130)<16)
        channels={w:np.full(rho.shape,100.) for w in [171,193,211]}
        for w in channels:channels[w][hole|filament]=20
        channels[171][hole]=70
        mask,labels,diagnostics=core.segment(channels,valid,rho)
        self.assertEqual(diagnostics['rawComponents'],2)
        self.assertEqual(diagnostics['components'],1)
        self.assertGreater(mask[hole].sum(),400)
        self.assertEqual(mask[filament].sum(),0)
        self.assertEqual(labels.max(),1)
        # There is no minimum desired count: an all-filament scene has zero CHs.
        channels[171][hole]=20
        mask,labels,diagnostics=core.segment(channels,valid,rho)
        self.assertEqual(mask.sum(),0)
        self.assertEqual(diagnostics['components'],0)

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
        maps = {w: sunpy.map.Map(np.where(image==20,70,image) if w==171 else image, {**base, 'INSTRUME': 'AIA', 'DETECTOR': 'AIA',
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
        self.assertNotEqual(pack['preview']['url'],pack['preview']['compositeUrl'])
        self.assertEqual(pack['preview']['compositeChannels'],{'red':211,'green':193,'blue':171})

    def test_composite_uses_three_independent_registered_channels(self):
        y,x=np.indices((64,64));valid=np.ones(x.shape,dtype=bool);rho=np.zeros(x.shape)
        channels={211:x+1,193:y+1,171:x+y+1}
        rgb=pipeline.composite_rgb(channels,valid,rho)
        changed=pipeline.composite_rgb({**channels,171:65-x},valid,rho)
        np.testing.assert_array_equal(rgb[:,:,:2],changed[:,:,:2])
        self.assertTrue(np.any(rgb[:,:,2]!=changed[:,:,2]))
        missing={w:a.astype(float) for w,a in channels.items()}
        missing[171][0,0]=np.nan
        np.testing.assert_array_equal(pipeline.composite_rgb(missing,valid,rho)[-1,0],0)


class PublicationTests(unittest.TestCase):
    def test_reference_index_uses_listed_rgb_files_and_actual_times(self):
        with tempfile.TemporaryDirectory() as directory:
            listing=Path(directory)/'listing.html'
            listing.write_text('20260822_204709_1024_211193171.jpg 20260822_204709_1024_0193.jpg 20240822_204709_1024_211193171.jpg')
            class Fake:
                def download(self,url,*args,**kwargs):
                    if '/2026/08/22/' not in url:raise ValueError('Unavailable')
                    return listing,{}
            result=pipeline.composite_reference_index(Fake(),'2026-09-19T03:24:04Z')
            self.assertEqual(len(result['images']),1)
            self.assertEqual(result['images'][0]['observationTime'],'2026-08-22T20:47:09Z')
            self.assertEqual(len(result['errors']),2)

    def test_download_embeds_original_timestamps_and_escapes_script_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            feed=publish.read(ROOT/'chhss-data/feed.json')
            feed['note']='</script><script>bad()</script>\u2028'
            publish.write(root/'feed.json',feed)
            html=build_dashboard(root/'dashboard.html',root/'feed.json').read_text()
            payload=html.split('<script type="application/json" id="chhssBootstrap">',1)[1].split('</script>',1)[0]
            self.assertEqual(json.loads(payload),feed)
            self.assertNotIn('<script>bad()',html)
            solar={'observed':[{'time-tag':'2026-08','ssn':76}], 'predicted':[{'time-tag':'2026-09','predicted_ssn':80}], 'retrievedAt':'2026-09-19T00:00:00Z'}
            publish.write(root/'solar.json',solar)
            html=build_dashboard(root/'dashboard.html',root/'feed.json',root/'solar.json').read_text()
            embedded=html.split('<script type="application/json" id="solarCycleBootstrap">',1)[1].split('</script>',1)[0]
            self.assertEqual(json.loads(embedded),solar)
            scoreboard={'rows':[{'note':'</script><script>bad()</script>\u2028'}],'retrievedAt':'2026-09-19T01:00:00Z'}
            publish.write(root/'scoreboard.json',scoreboard)
            html=build_dashboard(root/'dashboard.html',root/'feed.json',root/'solar.json',root/'scoreboard.json').read_text()
            embedded=html.split('<script type="application/json" id="cmeScoreboardBootstrap">',1)[1].split('</script>',1)[0]
            self.assertEqual(json.loads(embedded),scoreboard)
            self.assertNotIn('<script>bad()',html)

    def test_prior_detector_scores_do_not_validate_current_recipe(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            publish.write(root/'current.json',{'measurementEngine':core.VERSION})
            publish.write(root/'backfill'/'2026-09-01_2026-09-08'/'validation.json',{'methodVersion':'prior-detector','pairs':[]})
            self.assertFalse(publish.build(root)['verificationAppliesToCurrent'])

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
            with patch('chhss.pipeline.make_pack', side_effect=ValueError('No quality data')), patch('chhss.pipeline.get_truth', side_effect=ValueError('OMNI unavailable')), patch('builtins.print'):
                self.assertFalse(pipeline.live(None, output))
            self.assertFalse((output / 'current.json').exists())
            self.assertFalse(publish.read(output / 'status.json')['ok'])

    def test_omni_refresh_survives_imagery_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            day = (datetime.now(timezone.utc)-timedelta(days=27)).replace(hour=0, minute=0, second=0, microsecond=0)
            rows = [{'time_tag': core.iso(day+timedelta(hours=i)), 'speed': 450 if i<18 else None} for i in range(24)]
            def truth(acq, start, end, root):
                publish.write(root/'omni-manifest.json', {'sources': [{'url':'fixture'}]})
                return rows
            with patch('chhss.pipeline.get_truth', side_effect=truth), patch('chhss.pipeline.make_pack', side_effect=ValueError('AIA unavailable')), patch('builtins.print'):
                self.assertFalse(pipeline.live(None, output))
            status=publish.read(output/'status.json')
            self.assertFalse(status['measurement']['ok'])
            self.assertTrue(status['recurrence']['ok'])
            recurrence=publish.read(output/'recurrence.json')
            self.assertEqual(recurrence['rows'], rows)
            self.assertEqual(recurrence['coverage']['forecastDays'][0]['speed'], 450)
            self.assertEqual(recurrence['coverage']['forecastDays'][1]['speed'], None)
            self.assertEqual(recurrence['coverage']['validSpeedHours'], 18)

    def test_imagery_refresh_survives_omni_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)
            pack=publish.read(ROOT/'chhss-data/current.json')
            old={'generatedAt':'2026-09-01T00:00:00Z','rows':[]}
            publish.write(output/'recurrence.json',old)
            with patch('chhss.pipeline.get_truth', side_effect=ValueError('OMNI unavailable')), patch('chhss.pipeline.make_pack', return_value=pack), patch('builtins.print'):
                self.assertFalse(pipeline.live(None, output))
            self.assertEqual(publish.read(output/'current.json'),pack)
            self.assertEqual(publish.read(output/'recurrence.json'),old)
            self.assertTrue(publish.read(output/'status.json')['measurement']['ok'])
            self.assertFalse(publish.read(output/'status.json')['recurrence']['ok'])

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
