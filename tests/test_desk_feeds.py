import csv
import io
import json
import math
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from chhss import geomag, suprathermal
from research.proton_forecast import model, refresh

UTC = timezone.utc
NOW = datetime(2026, 9, 20, tzinfo=UTC)


class DatedFeeds(unittest.TestCase):
    def test_gfz_fill_future_duplicate_and_interval_start(self):
        text = '# header\n2026 09 19 23 23.5 0 0 1.333 5 0\n2026 09 19 22 22.5 0 0 -1 -1 0\n2026 09 20 02 2.5 0 0 3 15 0\n2026 09 19 23 23.5 0 0 2 7 0'
        rows = geomag.parse(text, NOW)
        self.assertEqual(rows, [{'start':'2026-09-19T23:00:00Z','hp60':2,'ap60':7}])
        with self.assertRaises(ValueError):
            geomag.parse('provider unavailable', NOW)

    def test_stis_quality_source_negative_fill_and_future(self):
        fields = ['time_tag', *suprathermal.CHANNELS, 'quality', 'source']
        buf=io.StringIO(); writer=csv.DictWriter(buf, fieldnames=fields);writer.writeheader()
        for minute,quality,source in [(0,0,4),(1,1,4),(2,0,1),(61,0,4)]:
            writer.writerow({'time_tag':(NOW-timedelta(hours=1)+timedelta(minutes=minute)).isoformat(),
                             **dict.fromkeys(suprathermal.CHANNELS,1), 'p2':-9999, 'quality':quality,'source':source})
        rows=suprathermal.parse(buf.getvalue(),NOW)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['p1'],1)
        self.assertIsNone(rows[0]['p2'])
        self.assertTrue(all(rows[1][k] is None for k in suprathermal.CHANNELS))


class ProtonCausality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fitted=json.loads(Path('research/proton_forecast/model.json').read_text())
        cls.event={'peakTime':refresh.stamp(NOW),'peakFlux':1e-5,'flareClass':'M1.0','riseMinutes':15,'longitude':None,'latitude':None}
        cls.obs=[{'time':refresh.stamp(NOW-timedelta(minutes=5*i)),'P10':.2,'P50':.1} for i in reversed(range(-3,289))]

    def test_no_future_particle_or_flare_feature_leakage(self):
        issued=NOW+timedelta(minutes=10)
        a=refresh.forecast(self.event,[],self.obs,self.fitted,issued)
        changed=[{**r,'P10':1e5,'P50':1e5} if refresh.date(r['time'])>=NOW else r for r in self.obs]
        b=refresh.forecast(self.event,[{'max_time':refresh.stamp(NOW+timedelta(minutes=5)),'max_xrlong':.01}],changed,self.fitted,issued)
        self.assertEqual(a['features'],b['features'])
        self.assertEqual(a['probabilities'],b['probabilities'])
        self.assertEqual(a['validStart'],'2026-09-20T00:10:00Z')
        self.assertEqual(a['validEnd'],'2026-09-21T00:10:00Z')
        self.assertIsNone(a['features']['longitude_sin'])
        self.assertTrue(0<=a['probabilities']['p10_40']<=a['probabilities']['p10_10']<=1)

    def test_ongoing_event_excluded_and_no_zero_for_gaps(self):
        active=[{**r,'P10':20} for r in self.obs]
        r=refresh.forecast(self.event,[],active,self.fitted,NOW+timedelta(minutes=10))
        self.assertFalse(r['eligible']['p10_10']);self.assertFalse(r['eligible']['p10_40'])
        self.assertTrue(r['eligible']['p50_10'])
        with self.assertRaisesRegex(ValueError,'20 hours'):
            refresh.forecast(self.event,[],self.obs[-100:],self.fitted,NOW+timedelta(minutes=10))
        with self.assertRaises(ValueError):
            refresh.forecast(self.event,[],self.obs,self.fitted,NOW+timedelta(days=2))
        self.assertFalse(model.exceeds(40,'p10_40'))
        self.assertTrue(model.exceeds(40.001,'p10_40'))
        self.assertFalse(model.exceeds(math.nan,'p10_10'))
        self.assertTrue(model.exceeds(10,'p50_10'))

    def test_late_run_preserves_the_original_window(self):
        late=refresh.forecast(self.event,[],self.obs,self.fitted,NOW+timedelta(hours=6))
        self.assertEqual(late['latencyMinutes'],350)
        self.assertEqual(late['validEnd'],'2026-09-21T00:10:00Z')
        self.assertEqual(late['createdAt'],'2026-09-20T06:00:00Z')

    def test_negative_and_missing_measurements_not_zero(self):
        rows=refresh.observations([{'time_tag':'2026-09-20T00:00Z','energy':'>=10 MeV','flux':-9999},
            {'time_tag':'2026-09-20T00:00Z','energy':'>=50 MeV','flux':0}])
        self.assertNotIn('P10',rows[0]);self.assertEqual(rows[0]['P50'],0)

if __name__=='__main__':unittest.main()
