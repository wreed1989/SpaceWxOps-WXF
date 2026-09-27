import ast
import json
import os
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import reassess_history as m

class CurationContracts(unittest.TestCase):
    def test_tai_offsets(self):
        r=m.tai_utc(pd.Series(['2014.01.01_18:00:00_TAI','2016.01.01_18:00:00_TAI','2024.01.01_18:00:00_TAI']))
        self.assertEqual([x.strftime('%H:%M:%S') for x in r],['17:59:25','17:59:24','17:59:23'])
    def test_tai_scope_guard(self):
        with self.assertRaises(ValueError):m.tai_utc(pd.Series(['2001.01.01_18:00:00_TAI']))
    def test_members_union(self):
        self.assertEqual(m.members({'NOAA_ARS':'13664,13668','NOAA_AR':13664}),(13664,13668))
    def test_no_invented_identity(self):
        self.assertEqual(m.members({'NOAA_ARS':'MISSING','NOAA_AR':0}),())
        self.assertEqual(m.members({'NOAA_ARS':'-9999','NOAA_AR':9999}),())
    def test_short_region_normalization(self):
        self.assertEqual(m.members({'NOAA_AR':3664}),(13664,))
    def test_connected_components(self):
        g=m.Groups();g.join('H1','N1');g.join('H2','N1');g.join('H2','N2')
        self.assertEqual(g.root('H1'),g.root('N2'));self.assertNotEqual(g.root('H1'),g.root('N3'))
    def test_event_dedup_and_causality(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'events.csv'
            pd.DataFrame([{'flare_id':'one','flare_class':'X2.1','active_region':3664,'time':'2024-05-01T21:15Z','start_time':'2024-05-01T20:50Z','end_time':'2024-05-01T21:30Z'}]*2).to_csv(p,index=False)
            e,_=m.event_catalog([p]);self.assertEqual(len(e),1);self.assertTrue(e.iloc[0].M1);self.assertTrue(e.iloc[0].X1);self.assertEqual(e.iloc[0].region,13664)
            self.assertGreater(e.iloc[0].known,pd.Timestamp('2024-05-01T21:00Z'))
    def test_zero_not_missing(self):
        self.assertTrue(np.isfinite(m.logit(np.array([0.,1.]))).all())
    def test_group_purge(self):
        d=pd.DataFrame({'issue':pd.to_datetime(['2018-01-01','2021-01-01','2023-01-01','2018-02-01','2021-02-01'],utc=True),'valid_day':pd.to_datetime(['2018-01-02','2021-01-02','2023-01-02','2018-02-02','2021-02-02'],utc=True),'group':['shared','shared','shared','train','cal']})
        tr,ca,te=m.split(d)
        self.assertEqual(list(np.flatnonzero(tr)),[3]);self.assertEqual(list(np.flatnonzero(ca)),[4]);self.assertEqual(list(np.flatnonzero(te)),[2])
    def test_signed_changes(self):
        d=pd.DataFrame({p:[10.] for p in m.PARAMETERS})
        for p in m.PARAMETERS:d['PREV_'+p]=[20.]
        for h in m.HISTORY:d[h]=[0.]
        d['LON_FWT']=0.;d['LAT_FWT']=0.
        x=m.features(d);self.assertEqual(x.shape[1],45);self.assertLess(x.iloc[0]['USFLUX__EVOLUTION'],0.)
    def test_brier_baseline(self):
        r=m.score(np.array([0,0,1,1]),np.repeat(.5,4),.5,['a','a','b','b'],draws=20)
        self.assertAlmostEqual(r['brier'],.25);self.assertAlmostEqual(r['brier_skill'],0.)
    def test_paired_gain_direction(self):
        y=np.array([0,1,0,1]);r=m.paired_gain(y,y.astype(float),np.repeat(.5,4),['a','a','b','b'])
        self.assertAlmostEqual(r['brier_reduction'],.25)

@unittest.skipUnless(os.environ.get('WXF_AUDIT_OUTPUT'),'Captured regression records not supplied')
class CapturedRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r=Path(os.environ['WXF_AUDIT_OUTPUT']);cls.d=pd.read_csv(r/'patch_dataset.csv.gz');cls.p=pd.read_csv(r/'patch_holdout_predictions.csv');cls.r=json.loads((r/'patch_report.json').read_text())
    def test_unique_patch_issue(self):
        self.assertFalse(self.d.duplicated(['issue','HARPNUM']).any())
    def test_no_simultaneous_ambiguous_noaa(self):
        e=self.d[['issue','members']].copy();e.members=e.members.map(ast.literal_eval);e=e.explode('members');self.assertFalse(e.duplicated(['issue','members']).any())
    def test_no_group_overlap(self):
        self.assertTrue(all(n==0 for n in self.r['group_overlap'].values()))
    def test_recovered_positives(self):
        self.assertEqual(int(self.p.M1.sum()),369);self.assertEqual(int(self.p.X1.sum()),33)
    def test_probability_order(self):
        for v in ['History','Magnetic State','State + Evolution','Combined']:
            self.assertTrue(self.p[v+' X1'].le(self.p[v+' M1']+1e-12).all());self.assertTrue(self.p[v+' M1'].between(0,1).all())
    def test_prediction_score_recomputes(self):
        for k in ['M1','X1']:self.assertAlmostEqual(np.mean((self.p[k]-self.p['Combined '+k])**2),self.r['scores']['Combined'][k]['brier'],12)
    def test_previous_member_continuity(self):
        d=self.d.sort_values(['HARPNUM','issue']);g=d.groupby('HARPNUM');prev=g.members.shift();flag=d.previous_available.astype(str).str.lower().eq('true')
        adjacent=(pd.to_datetime(d.issue)-pd.to_datetime(g.issue.shift())).dt.total_seconds().eq(86400)
        self.assertTrue(d.loc[flag&adjacent,'members'].eq(prev[flag&adjacent]).all())

if __name__=='__main__':unittest.main()
