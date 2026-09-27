"""Deterministic source-contract checks. Does not establish forecast skill."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import refresh_evidence as e

class Registration(unittest.TestCase):
    meta={'dsun':149600000000,'rsun':1600,'refPixelX':2048.5,'refPixelY':2048.5,'rotation':0}
    def point(self,lat=0,lon=0,header='<CRLT_OBS>0</CRLT_OBS><CRLN_OBS>0</CRLN_OBS>',**kw):
        return e.image_geometry(dict(self.meta,**kw),header,{'latitude':lat,'carrington_longitude':lon,'observed_date':'2026-09-27'})
    def test_hmi_crlt_center(self):
        p=self.point();self.assertEqual(p['x'],2048);self.assertEqual(p['y'],2048)
    def test_hglt_alias(self): self.assertEqual(self.point(header='<HGLT_OBS>0</HGLT_OBS><CRLN_OBS>0</CRLN_OBS>')['b0'],0)
    def test_north_up(self): self.assertLess(self.point(lat=20)['y'],2048)
    def test_west_right(self): self.assertGreater(self.point(lon=20)['x'],2048)
    def test_negative_east_left(self): self.assertLess(self.point(lon=-20)['x'],2048)
    def test_wraparound(self): self.assertAlmostEqual(self.point(lon=350)['x'],self.point(lon=-10)['x'])
    def test_far_side_omitted(self):self.assertIsNone(self.point(lon=140))
    def test_b0_applied(self):self.assertAlmostEqual(self.point(lat=7,header='<CRLT_OBS>7</CRLT_OBS><CRLN_OBS>0</CRLN_OBS>')['y'],2048)
    def test_missing_registration_rejected(self):
        with self.assertRaises(ValueError):self.point(header='<CRLN_OBS>0</CRLN_OBS>')
    def test_rotation_rejected(self):
        with self.assertRaises(ValueError):self.point(rotation=180)
    def test_invalid_sun_distance_rejected(self):
        with self.assertRaises(ValueError):self.point(dsun=1)
    def test_invalid_latitude_rejected(self):
        with self.assertRaises(ValueError):self.point(lat=120)
    def test_header_date(self):self.assertEqual(e.header_value('<DATE-OBS>2026-09-27T00:00:00.25</DATE-OBS>','DATE-OBS'),'2026-09-27T00:00:00.25')

class EventMatching(unittest.TestCase):
    def row(self,**kw):return dict(type='XRA',particulars1='M1.2',max_datetime='2026-09-27T07:53:00',begin_datetime='2026-09-27T07:45:00',end_datetime='2026-09-27T08:00:00',region=4535,bin=7180,observatory='G18',status_text='',**kw)
    def test_duplicate_satellites_one_event(self):
        a=self.row();b=dict(a,begin_datetime='2026-09-27T07:46:00',observatory='G19',status_text='+')
        rows=e.dedup_events([a,b]);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['reports'],2);self.assertTrue(rows[0]['preferred'])
    def test_preferred_class_retained(self):
        a=self.row();b=dict(a,particulars1='M1.1',status_text='+');self.assertEqual(e.dedup_events([a,b])[0]['class'],'M1.1')
    def test_region_conflict_remains_ambiguous(self):
        a=self.row();rows=e.dedup_events([a,dict(a,region=4536)]);self.assertIsNone(rows[0]['region']);self.assertEqual(rows[0]['association'],'Ambiguous')
    def test_unassigned_nearby_events_not_conflated(self):
        a=dict(self.row(),region=None,bin=None);b=dict(a,max_datetime='2026-09-27T07:54:00');self.assertEqual(len(e.dedup_events([a,b])),2)
    def test_distinct_events_retained(self):
        a=self.row();b=dict(a,bin=7200,max_datetime='2026-09-27T10:00:00');self.assertEqual(len(e.dedup_events([a,b])),2)
    def test_non_xray_omitted(self):self.assertEqual(e.dedup_events([dict(self.row(),type='FLA')]),[])
    def test_invalid_class_omitted(self):self.assertEqual(e.dedup_events([dict(self.row(),particulars1='???')]),[])
    def test_invalid_timestamp_omitted(self):self.assertEqual(e.dedup_events([dict(self.row(),max_datetime='bad')]),[])
    def test_canonical_region(self):self.assertEqual(e.dedup_events([self.row()])[0]['region'],14535)

class Serialization(unittest.TestCase):
    def test_nan_null_not_zero(self):self.assertIsNone(e.clean(float('nan')))
    def test_zero_preserved(self):self.assertEqual(e.clean(0.0),0)
    def test_missing_timestamp_rejected(self):
        with self.assertRaises(ValueError):e.stamp(None)
    def test_utc(self):self.assertEqual(e.stamp('2026-09-27T01:00:00+01:00'),'2026-09-27T00:00:00Z')
    def test_column_contract_accepts_tuples(self):
        columns=['HARPNUM']+list(e.model.SHARP_PARAMETERS)+list(e.model.HISTORY_RAW_COLUMNS);self.assertIn('USFLUX',columns);self.assertIn('PRIOR_M1_COUNT_24H',columns)

if __name__=='__main__':unittest.main()
