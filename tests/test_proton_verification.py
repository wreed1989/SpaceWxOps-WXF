import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from research.proton_forecast.database import truth, partitions, score_database, build_database
from research.proton_forecast.verification import metrics, block_intervals

class VerificationMetrics(unittest.TestCase):
    def test_counts_ties_and_undefined_ratios(self):
        v=metrics([1,0,0,1],[.8,.4,.1,.1],.5)
        for k in ['hits','falseAlarms','misses','correctNegatives']:self.assertEqual(v[k],1)
        self.assertEqual(v['POD'],.5);self.assertEqual(v['FAR'],.5);self.assertEqual(v['auc'],.625)
        self.assertAlmostEqual(v['averagePrecision'],.75)
        quiet=metrics([0,1],[.1,.1],.5)
        self.assertIsNone(quiet['FAR']);self.assertEqual(quiet['POD'],0)
        self.assertIsNone(metrics([0,0],[.1,.2],.1)['auc'])
        for bad in [[float('nan'),.1],[-1,.1],[1.01,.1]]:
            with self.assertRaises(ValueError):metrics([0,1],bad,.1)

    def test_block_uncertainty_is_reproducible(self):
        t=pd.date_range('2023-01-01',periods=40,freq='D');y=np.tile([0,1],20);p=np.tile([.1,.4],20)
        first=block_intervals(t,y,p,.1);self.assertEqual(first,block_intervals(t,y,p,.1))
        self.assertLess(first['brierSkill95'][0],first['brierSkill95'][1])

    def test_truth_strict_threshold_gaps_and_baseline(self):
        times=np.arange(291)*300;series=np.zeros(291);series[3:6]=40
        self.assertEqual(truth(times,series,900,'p10_10')['label'],1)
        self.assertEqual(truth(times,series,900,'p10_40')['label'],0)
        series[3:6]=40.01;self.assertEqual(truth(times,series,900,'p10_40')['label'],1)
        series[50:57]=np.nan;result=truth(times,series,900,'p10_40')
        self.assertIsNone(result['label']);self.assertIn('truth_gap_over_30_minutes',result['exclusion'])
        series=np.zeros(291);series[1]=np.nan
        self.assertEqual(truth(times,series,900,'p10_10')['exclusion'],'baseline_unknown')
        series[:3]=10;self.assertEqual(truth(times,series,900,'p10_40')['exclusion'],'already_active')

    def test_partitions_keep_embargo_and_region_purge(self):
        df=pd.DataFrame({'time':['2014-01-01','2015-01-16','2022-02-01','2014-12-25','2013-01-01'],'region':[1,1,2,3,4]})
        self.assertEqual(partitions(df).tolist(),['embargo_or_region_purge','calibration','test','embargo_or_region_purge','training'])

    def test_checksum_failure_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'particles.csv').write_text('changed')
            (root/'manifest.json').write_text(json.dumps({'sources':[{'file':'particles.csv','sha256':'incorrect'}],'featureSHA256':'wrong'}))
            with self.assertRaisesRegex(ValueError,'checksum'):build_database(root,root/'output.sqlite',root/'manifest.json')
            self.assertFalse((root/'output.sqlite').exists())

    def test_database_rescore_keeps_separate_model_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.sqlite';db=sqlite3.connect(path)
            db.executescript('''
              CREATE TABLE metadata(key TEXT,value TEXT);
              CREATE TABLE observations(time INTEGER);
              CREATE TABLE forecast_cases(case_id TEXT,features_json TEXT,partition TEXT,valid_start INTEGER,input_eligible INTEGER);
              CREATE TABLE outcomes(case_id TEXT,target TEXT,label INTEGER,exclusion TEXT);
              CREATE TABLE models(model_id TEXT PRIMARY KEY,version TEXT,model_json TEXT,imported_at TEXT);
              CREATE TABLE predictions(model_id TEXT,case_id TEXT,target TEXT,probability REAL,PRIMARY KEY(model_id,case_id,target));
              CREATE TABLE evaluations(model_id TEXT,scope TEXT,decision_probability REAL,generated_at TEXT,report_json TEXT,PRIMARY KEY(model_id,scope,decision_probability));
            ''')
            db.execute('INSERT INTO metadata VALUES(?,?)',('schemaVersion',json.dumps('WXF-SEP-DB-1')))
            fixture=json.loads(Path('research/proton_forecast/inference-fixture.json').read_text())
            for i in range(4):
                db.execute('INSERT INTO forecast_cases VALUES(?,?,?,?,?)',(str(i),json.dumps(fixture['features']),'test',1672531200+i*86400,1))
                for key in ['p10_10','p10_40','p50_10']:db.execute('INSERT INTO outcomes VALUES(?,?,?,?)',(str(i),key,i%2,None))
            db.commit();db.close()
            a=score_database(path);model=json.loads(Path('research/proton_forecast/model.json').read_text());model['models']['p10_10']['intercept']+=.1
            candidate=Path(folder)/'candidate.json';candidate.write_text(json.dumps(model));b=score_database(path,candidate)
            self.assertNotEqual(a['modelSHA256'],b['modelSHA256'])
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM models').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT count(*) FROM evaluations').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT count(*) FROM outcomes').fetchone()[0],12)
            with self.assertRaises(FileNotFoundError):score_database(Path(folder)/'missing.sqlite')

if __name__=='__main__':unittest.main()
