import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .model import diurnal_profile, features_at, harmonics, prepare, predict, rolling_paths, split_mask
    from .refresh import append_ledger
    from .frozen import load_model
else:
    from model import diurnal_profile, features_at, harmonics, prepare, predict, rolling_paths, split_mask
    from refresh import append_ledger
    from frozen import load_model

HERE=Path(__file__).resolve().parent


def synthetic():
    times=pd.date_range('2026-08-01',periods=240,freq='1h',tz='UTC')
    frame=pd.DataFrame(index=times)
    frame['flux']=np.expm1(7 + harmonics(times) @ np.array([.4,-.2,.05,.02]))
    for key,value in {'speed':450,'density':5,'bt':5,'bz':-1,'southward':1,'pressure':1.6,'coupling':.45}.items():frame[key]=value
    return frame


class ScienceTests(unittest.TestCase):
    def test_rolling_keeps_observed_tail_and_ages_it_out(self):
        result=rolling_paths(np.full(24,1000),np.full((2,24),2000))
        self.assertEqual(result[0,0],(23*1000+2000)*3600)
        self.assertEqual(result[0,-1],24*2000*3600)

    def test_gap_invalidates_only_containing_windows(self):
        past=np.ones(24);past[3]=np.nan
        with self.assertRaises(ValueError):rolling_paths(past,np.ones(24))
        result=rolling_paths(past,np.ones(24),allow_observed_gaps=True)[0]
        self.assertTrue(np.isnan(result[:3]).all())
        np.testing.assert_array_equal(result[3:],86400)

    def test_negative_and_missing_forecasts_are_not_zero(self):
        for bad in [-1,np.nan,np.inf]:
            path=np.ones(24);path[4]=bad
            with self.assertRaises(ValueError):rolling_paths(np.ones(24),path)

    def test_integrate_paths_before_quantiles(self):
        paths=np.zeros((2,24));paths[0,::2]=100;paths[1,1::2]=100
        integrated=rolling_paths(np.zeros(24),paths)
        self.assertEqual(np.quantile(integrated[:,-1],.95),12*100*3600)
        self.assertGreater(rolling_paths(np.zeros(24),np.quantile(paths,.95,axis=0))[0,-1],integrated[0,-1])

    def test_diurnal_separates_daily_amplitude(self):
        series=synthetic().flux.iloc[:168]
        original=diurnal_profile(series)
        levels=np.repeat(np.linspace(-2,2,7),24)
        shifted=pd.Series(np.expm1(np.log1p(series)+levels),index=series.index)
        np.testing.assert_allclose(diurnal_profile(shifted),original,atol=1e-5)
        np.testing.assert_allclose(original,[.4,-.2,.05,.02],atol=.01)

    def test_future_values_cannot_change_features(self):
        data=synthetic();x,b,_,_=features_at(data,190)
        data.iloc[191:]=1e8
        x2,b2,_,_=features_at(data,190)
        np.testing.assert_array_equal(x,x2);np.testing.assert_array_equal(b,b2)

    def test_partitions_purge_future_target_overlap(self):
        t=pd.DatetimeIndex(['2026-02-27T23:00Z','2026-02-28T00:00Z','2026-03-01T00:00Z'])
        np.testing.assert_array_equal(split_mask(t,'2025-04-14','2026-03-01'),[True,False,False])

    def test_boxcars_quality_and_driver_latency(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            times=pd.date_range('2026-08-01',periods=36,freq='5min',tz='UTC')
            rows=[f'{t.isoformat()},.1,100,GOES-19,GOES-18' for t in times]
            # A proton-contaminated bin and a spacecraft change must mask their hours.
            rows[15]=f'{times[15].isoformat()},10,100,GOES-19,GOES-18'
            rows[30]=f'{times[30].isoformat()},.1,100,GOES-18,GOES-18'
            (p/'particles-a.csv').write_text('\n'.join(rows))
            minutes=pd.date_range('2026-08-01',periods=180,freq='min',tz='UTC')
            (p/'plasma-a.csv').write_text('\n'.join(f'{t.isoformat()},5,500' for t in minutes))
            (p/'mag-a.csv').write_text('\n'.join(f'{t.isoformat()},0,{10 if i%2 else -10},10' for i,t in enumerate(minutes)))
            h,q=prepare(p)
            self.assertEqual(h.flux.iloc[0],100)
            self.assertTrue(h.flux.iloc[1:].isna().all())
            self.assertTrue(np.isnan(h.speed.iloc[0]))
            self.assertEqual(h.speed.iloc[1],500)
            self.assertEqual(h.bz.iloc[1],0)
            self.assertEqual(h.coupling.iloc[1],2.5) # rectify minute Bz before averaging
            self.assertEqual(q['highProtonSamples'],1)
            self.assertEqual(q['otherElectronSpacecraft'],1)

    def test_frozen_model_manifest(self):
        metadata=json.loads((HERE/'model-manifest.json').read_text())
        self.assertEqual(hashlib.sha256((HERE/'model.npz').read_bytes()).hexdigest(),metadata['modelSHA256'])
        artifact=load_model(HERE/'model.npz')
        data=synthetic();issued=data.index[-1]+pd.Timedelta(minutes=15)
        result=predict(data,artifact,issued)
        self.assertEqual(result['status'],'experimental')
        self.assertEqual(len(result['forecast']),24)
        self.assertTrue(all(r['fluxLow']>=0 for r in result['forecast']))
        self.assertFalse(artifact['report']['releaseGate']['forwardVerified'])
        data.iloc[-5,data.columns.get_loc('flux')]=np.nan
        result=predict(data,artifact,issued)
        self.assertEqual(result['status'],'experimental')
        self.assertIsNone(result['forecast'][0]['median'])
        self.assertIsNotNone(result['forecast'][-1]['median'])
        self.assertIsNone(result['observedFluence'])
        data.iloc[-1,data.columns.get_loc('flux')]=np.nan
        result=predict(data,artifact,issued)
        self.assertEqual(result['status'],'withheld')
        result=predict(synthetic(),artifact,issued+pd.Timedelta(hours=3))
        self.assertEqual(result['status'],'withheld')

    def test_ledger_preserves_each_issue_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);forecast=p/'forecast.json';ledger=p/'history.jsonl'
            forecast.write_text(json.dumps({'issuedAt':'2026-09-19T20:15:00Z','status':'withheld','forecast':[]}))
            append_ledger(forecast,ledger);before=ledger.read_text();append_ledger(forecast,ledger)
            self.assertEqual(before,ledger.read_text())
            forecast.write_text(json.dumps({'issuedAt':'2026-09-19T21:15:00Z','status':'withheld','forecast':[]}))
            append_ledger(forecast,ledger)
            self.assertEqual(len(ledger.read_text().splitlines()),2)
            self.assertTrue(ledger.read_text().startswith(before))


if __name__=='__main__':unittest.main()
