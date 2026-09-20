import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from research.proton_forecast import inputs, refresh

NOW=datetime(2026,9,20,tzinfo=timezone.utc)
RAW=dict(begin_time='2026-09-19T17:57:00Z',max_time='2026-09-19T18:17:00Z',end_time='2026-09-19T18:32:00Z',max_class='C3.3',max_xrlong=3.34659e-6,current_int_xrlong=.004062)
XRA=dict(type='XRA',begin_datetime=RAW['begin_time'],max_datetime=RAW['max_time'],end_datetime=RAW['end_time'],particulars1='C3.3',particulars2='4.1e-3',bin=9070,region=4533,location='')
FLA={**XRA,'type':'FLA','location':'S12W42','particulars1':'1B','max_datetime':'2026-09-19T18:20:00Z'}

class AutomaticInputs(unittest.TestCase):
    def test_linked_optical_location_radio_and_completed_integral(self):
        event=inputs.event_inputs(RAW,[XRA,FLA,{**XRA,'type':'RSP','particulars1':'II/2'},{**XRA,'type':'RSP','particulars1':'IV/1'}],NOW)
        self.assertEqual((event['latitude'],event['longitude']),(-12,42))
        self.assertEqual(event['region'],4533);self.assertEqual(event['radio'],'II+IV')
        self.assertEqual(event['opticalClass'],'1B');self.assertEqual(event['integral'],.004062)
        self.assertEqual(event['previous'],'unknown')

    def test_conflicts_reused_bins_and_type_three_are_not_associations(self):
        wrong={**FLA,'begin_datetime':'2026-08-19T18:00:00Z','location':'N10E70'}
        event=inputs.event_inputs(RAW,[XRA,wrong,{**XRA,'type':'RSP','particulars1':'III/2'}],NOW)
        self.assertIsNone(event['longitude']);self.assertEqual(event['radio'],'unknown')
        conflict=inputs.event_inputs(RAW,[XRA,FLA,{**FLA,'location':'N10E70'}],NOW)
        self.assertIsNone(conflict['longitude']);self.assertIn('Conflicting',conflict['inputNotes'][0])
        self.assertIsNone(inputs.position('N99W10'))
        self.assertEqual(inputs.position('N00E00'),(0,0))

    def test_incomplete_or_future_integral_not_accepted(self):
        for patch in [{'end_time':None},{'end_time':'2026-09-21T00:00:00Z'},{'current_int_xrlong':-1},{'end_time':RAW['begin_time']}]:
            self.assertIsNone(inputs.event_inputs({**RAW,**patch},[],NOW)['integral'])
        with self.assertRaises(ValueError):inputs.event_inputs(RAW,[],NOW-timedelta(days=1))

    def test_previous_region_requires_positive_match_before_current_start(self):
        old={**XRA,'bin':8000,'begin_datetime':'2026-09-18T09:50:00Z','max_datetime':'2026-09-18T10:00:00Z','end_datetime':'2026-09-18T10:15:00Z','particulars2':'0.123'}
        event=inputs.event_inputs(RAW,[XRA,FLA,old,{**old,'region':4534,'max_datetime':'2026-09-19T11:00:00Z'}],NOW)
        self.assertEqual(event['previous'],'yes');self.assertEqual(event['previousIntegral'],.123)
        self.assertEqual(inputs.event_inputs(RAW,[XRA,FLA],NOW)['previous'],'unknown')

    def test_aia_association_excludes_off_limb_or_ambiguous_locations(self):
        candidate=dict(start=inputs.date(RAW['begin_time']),peak=inputs.date(RAW['max_time'])+timedelta(minutes=4),end=inputs.date(RAW['end_time']),latitude=20,longitude=-42,radius=.8,url='https://www.sidc.be/solardemon/flares.php?fid=1&science=0')
        event=inputs.event_inputs(RAW,[],NOW,[candidate]);self.assertEqual(event['longitude'],-42)
        self.assertIsNone(event['region']) # Solar Demon's nearest AR is not a confirmed source region.
        for matches in [[{**candidate,'radius':1.02}],[candidate,{**candidate,'longitude':60}]]:
            self.assertIsNone(inputs.event_inputs(RAW,[],NOW,matches)['longitude'])

    def test_solar_demon_table_midnight_and_missing_coordinates(self):
        text='<th title="Stonyhurst Longitude"></th><th title="Stonyhurst Latitude"></th><tr><td>September, 2026</td></tr><tr>'
        text+=''.join('<td>'+v+'</td>' for v in ['19','C3','23:57','00:03','00:09','36208','','','1.02','','25.5','N/A','N/A','','0','4'])+'</tr>'
        rows=inputs.solar_demon_rows(text);self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['peak'],NOW+timedelta(minutes=3));self.assertIsNone(rows[0]['longitude'])
        with self.assertRaises(ValueError):inputs.solar_demon_rows('<html>Error</html>')

    def test_optional_location_source_outage_does_not_drop_flare(self):
        def get(url,**kwargs):
            if url in (refresh.EVENTS,inputs.SOLAR_DEMON):raise OSError('provider offline')
            return Mock(json=lambda:[RAW] if url==refresh.FLARES else [])
        result=refresh.collect(NOW,get)
        self.assertEqual(len(result['events']),1);self.assertEqual(len(result['inputWarnings']),2)
        self.assertEqual(result['events'][0]['integral'],.004062)
        self.assertEqual(len(result['rejected']),1)

if __name__=='__main__':unittest.main()
