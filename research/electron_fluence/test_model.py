import hashlib
import json
import tempfile
import os
import unittest
from unittest.mock import patch, Mock
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .model import diurnal_profile, features_at, harmonics, prepare, predict, rolling_paths, split_mask
    from .refresh import append_ledger
    from .frozen import load_model
    from .arrivals import ArrivalArchive
    from .refresh import refresh
    from .impacts import ImpactArchive
    from .huxt_run import selected_cones
else:
    from model import diurnal_profile, features_at, harmonics, prepare, predict, rolling_paths, split_mask
    from refresh import append_ledger
    from frozen import load_model
    from arrivals import ArrivalArchive
    from refresh import refresh
    from impacts import ImpactArchive
    from huxt_run import selected_cones

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

    def test_spacecraft_handoff_is_not_spliced(self):
        data=synthetic();data['satellite']='GOES-16'
        features_at(data,190)
        data.loc[data.index[180]:,'satellite']='GOES-19'
        with self.assertRaisesRegex(ValueError,'handoff'):features_at(data,190)
        # Missing flux is already excluded from the profile; unknown identity on
        # that missing hour must not falsely imply a different spacecraft.
        data['satellite']='GOES-19';data.loc[data.index[100],'satellite']=None
        data.loc[data.index[100],'flux']=np.nan
        features_at(data,190)

    def test_recurrence_uses_only_previous_rotation(self):
        data=synthetic().reindex(pd.date_range('2026-08-01',periods=1000,freq='1h',tz='UTC')).ffill()
        origin=900;stop=data.index[origin]+pd.Timedelta(hours=24-648)
        data.loc[(data.index>stop-pd.Timedelta(hours=24))&(data.index<=stop),'speed']=700
        x,b,n,_=features_at(data,origin);f=dict(zip(n,x))
        self.assertEqual(f['recurrence_24h_speed'],700)
        self.assertEqual(f['recurrence_24h_coverage'],1)
        data.iloc[origin+1:]=1e8
        xx,bb,_,_=features_at(data,origin)
        np.testing.assert_array_equal(x,xx);np.testing.assert_array_equal(b,bb)

    def test_scoreboard_submission_gate_and_provider_deduplication(self):
        def run(method,submitted,arrival):
            return {'predictedMethodName':method,'submissionTime':submitted,
                    'predictedArrivalTime':arrival,'uncertaintyMinusInHrs':3,'uncertaintyPlusInHrs':6,
                    'predictedMaxKpUpperRange':5}
        origin=pd.Timestamp('2026-08-03T00:00Z')
        event={'cmeID':'one','observedTime':'2026-08-01T00:00Z','arrivalTime':'2026-08-04T00:00Z',
            'maxKP':9,'predictions':[
            run('WSA-ENLIL (NASA M2M)','2026-08-01T06:00Z','2026-08-03T06:00Z'),
            run('Ensemble WSA-ENLIL (NASA M2M)','2026-08-02T06:00Z','2026-08-03T12:00Z'),
            run('WSA-ENLIL (NOAA/SWPC)','2026-08-03T01:00Z','2026-08-03T18:00Z'),
            run('Average of all Methods','2026-08-02T09:00Z','2026-08-03T18:00Z')]}
        archive=ArrivalArchive([event]);rows=archive.at(origin)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['arrival'],pd.Timestamp('2026-08-03T12:00Z'))
        before=archive.features(origin)
        event['arrivalTime']='2026-08-05T00:00Z';event['maxKP']=0;event['noArrivalObserved']=True
        event['predictions'][-2]['predictedArrivalTime']='2026-08-08T00:00Z'
        event['predictions'][0]['differenceInHrs']=100
        self.assertEqual(before,ArrivalArchive([event]).features(origin))
        self.assertEqual(before['cme_event_count'],1)
        self.assertEqual(before['cme_forecast_kp'],5)

    def test_scoreboard_rejects_hindsight_and_bad_chronology(self):
        event={'observedTime':'2026-08-01T00:00Z','predictions':[
            {'predictedMethodName':'HUXt','submissionTime':'2026-08-04T00:00Z','predictedArrivalTime':'2026-08-03T00:00Z'},
            {'predictedMethodName':'HUXt','submissionTime':'2026-07-31T00:00Z','predictedArrivalTime':'2026-08-03T00:00Z'}]}
        self.assertEqual(ArrivalArchive([event]).rows,[])
        self.assertEqual(ArrivalArchive([],available=False).features(pd.Timestamp('2026-08-01T00:00Z'))['cme_feed_available'],0)

    def test_scoreboard_outage_uses_reviewed_fallback(self):
        data=synthetic();data.index=pd.date_range(end=pd.Timestamp.now(tz='UTC').floor('h')-pd.Timedelta(hours=1),periods=len(data),freq='h')
        module=refresh.__module__
        response=Mock();response.text=':Issued: Test bulletin';response.raise_for_status=Mock()
        with tempfile.TemporaryDirectory() as tmp, patch(module+'.acquire'), patch(module+'.prepare',return_value=(data,{})), patch(module+'.acquire_arrivals',side_effect=ValueError('offline')), patch(module+'.acquire_impacts',side_effect=ValueError('offline')), patch(module+'.requests.get',return_value=response):
            result=refresh(Path(tmp)/'cache',Path(tmp)/'forecast.json',Path(tmp)/'evidence')
            self.assertEqual(result['status'],'experimental')
            self.assertEqual(result['candidate']['status'],'experimental')
            self.assertIn('fallback',result['candidate']['guidanceMode'])
            self.assertFalse(result['arrivalGuidance']['available'])
            self.assertFalse(any(n.startswith('cme_') for n in result['candidate']['predictorValues']))
            self.assertEqual(result['thresholds'],{'moderate':1.1e8,'high':4.8e8})

    def test_impact_versions_are_not_backdated(self):
        event={'activityID':'one','location':'Earth','eventTime':'2026-08-02T00:00Z',
            'submissionTime':'2026-08-02T06:00Z','versionId':1,'linkedEvents':None}
        revision={**event,'submissionTime':'2026-08-03T06:00Z','versionId':2,
                  'linkedEvents':[{'activityID':'2026-08-01-CME-001'}]}
        a=ImpactArchive({'IPS':[event,revision]})
        self.assertEqual(a.at(pd.Timestamp('2026-08-02T05:00Z')),[])
        self.assertEqual(a.at(pd.Timestamp('2026-08-03T00:00Z'))[0]['version'],1)
        self.assertEqual(a.at(pd.Timestamp('2026-08-03T00:00Z'))[0]['cmes'],[])
        self.assertEqual(a.at(pd.Timestamp('2026-08-03T07:00Z'))[0]['version'],2)
        other={**event,'location':'Mars'}
        self.assertEqual(ImpactArchive({'IPS':[other]}).rows,[])

    def test_event_response_is_pre_origin_only(self):
        data=synthetic()
        e={'hssID':'hss','eventTime':data.index[180].isoformat(),
           'submissionTime':data.index[186].isoformat(),'versionId':1}
        impacts=ImpactArchive({'HSS':[e]})
        x,b,n,_=features_at(data,200,impacts=impacts)
        self.assertEqual(dict(zip(n,x))['hss_age_hours'],20)
        data.iloc[201:]=1e8
        xx,bb,_,_=features_at(data,200,impacts=impacts)
        np.testing.assert_array_equal(x,xx);np.testing.assert_array_equal(b,bb)

    def test_huxt_cones_use_available_analyses_not_future_revisions(self):
        now=pd.Timestamp('2026-09-19T00:00Z');start=now-pd.Timedelta(days=7)
        row={'associatedCMEID':'one','submissionTime':'2026-09-18T23:00Z','time21_5':'2026-09-19T01:00Z',
            'speed':800,'halfAngle':30,'latitude':0,'longitude':0}
        later={**row,'submissionTime':'2026-09-19T01:00Z','speed':1500}
        selected=selected_cones([row,later],now,start)
        self.assertEqual(len(selected),1);self.assertEqual(selected[0]['speed'],800)
        self.assertGreater(pd.Timestamp(selected[0]['launchAt21_5']),now)

    def test_vendored_huxt_integrity_and_analytic_solution(self):
        root=HERE/'vendor/huxt';meta=json.loads((root/'manifest.json').read_text())
        for path,sha in meta['files'].items():self.assertEqual(hashlib.sha256((root/path).read_bytes()).hexdigest(),sha)
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.setdefault('SUNPY_CONFIGDIR',str(Path(tmp)/'sunpy'))
            from astropy import units as u
            if __package__:
                from .vendor.huxt import huxt as H
            else:
                from vendor.huxt import huxt as H
            with patch.object(H,'user_data_dir',return_value=tmp):
                m=H.HUXt(v_boundary=np.full(128,350)*u.km/u.s,cr_num=2300,lon_out=0*u.deg,simtime=1*u.day,dt_scale=8)
                m.solve([])
                c=H.huxt_constants()
                expected=m.v_boundary[0]*(1+c['alpha']*(1-np.exp((m.r[0]-m.r)/c['r_accel'])))
                np.testing.assert_allclose(m.v_grid[:,:,0].value,np.broadcast_to(expected.value,m.v_grid[:,:,0].shape),rtol=1e-3)

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
