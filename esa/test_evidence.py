"""Parsing, eligibility, missing-data and dimensional-contract tests."""
import unittest,json
from pathlib import Path
from solar_evidence import parse_cactus,parse_demon,parse_connectivity,major,stamp
CACTUS='''CACTus\n:Issued: Sun Sep 27 01:54:45 2026\nfirst c2: 2026/09/21 00:00:34\nlast c2: 2026/09/26 23:24:24\nfirst c3: 2026/09/21 01:42:25\nlast c3: 2026/09/26 22:06:25\n# CME | t0 | dt | pa | da | v | dv | min | max | halo\n0018 | 2026/09/26 21:12 | 1 | 228 | 14 | 1572 | 218 | 1498 | 1966 |\n# Flow | t0 | dt | pa | da | v | dv | min | max | halo\n0001 | 2026/09/26 21:12 | 1 | 50 | 14 | 300 | 18 | 250 | 350 |\n'''
def demon(rows=''):
 return '<h1>Quick-look Overview of flares</h1><p>Last processed image: 0 hours ago (2026-09-27 07:45 UTC)</p><table><tr><th>September, 2026</th></tr>'+rows+'</table>'
def row(cls='M2',lat='20',lon='30',start='07:00',peak='07:15',end='07:45'):
 cells=['27',cls,start,peak,end,'39000',lat,lon,'0.5','AR 4513','200','N/A','N/A','', '3','2','']
 return '<tr>'+''.join('<td>'+v+'</td>' for v in cells)+'</tr>'
POINTS='''# Carrington density format\n1\n695700000\n2026-09-27 06:00:00\nEARTH 149950000000 6.8 343.7\n2 1 1 0\nSSW 0 100 695700000 -2 79 149950000000 0 0\nFSW 0 100 695700000 8 32 149950000000 0 0\n'''
class Evidence(unittest.TestCase):
 def test_major_filter(self):
  for v in ['M1','M5.2','X1','X9.8']:self.assertTrue(major(v))
  for v in ['C9.9','M0.9','',None,'unknown']:self.assertFalse(major(v))
 def test_bad_dates(self):self.assertIsNone(stamp('2026-02-30T00:00:00Z'))
 def test_cactus_fields(self):
  p=parse_cactus(CACTUS);self.assertEqual(len(p['events']),1);self.assertEqual(p['events'][0]['median_speed_km_s'],1572);self.assertEqual(p['events'][0]['velocity_frame'],'plane_of_sky')
 def test_cactus_flows(self):self.assertEqual(parse_cactus(CACTUS)['flows_excluded'],1)
 def test_cactus_no_header(self):
  with self.assertRaises(ValueError):parse_cactus('<html>login</html>')
 def test_cactus_no_coverage(self):
  with self.assertRaises(ValueError):parse_cactus(CACTUS.replace('last c3:','missing c3:'))
 def test_cactus_bad_speed(self):
  with self.assertRaises(ValueError):parse_cactus(CACTUS.replace('| 1572 |','| nan |'))
 def test_cactus_bad_width(self):
  with self.assertRaises(ValueError):parse_cactus(CACTUS.replace('| 14 |','| 400 |'))
 def test_cactus_dedup(self):self.assertEqual(len(parse_cactus(CACTUS.replace('# Flow',CACTUS.splitlines()[7]+'\n# Flow'))['events']),1)
 def test_demon_major(self):
  p=parse_demon(demon(row()));self.assertEqual(p['events'][0]['estimated_class'],'M2');self.assertEqual(p['events'][0]['region'],14513);self.assertEqual(p['events'][0]['class_basis'],'EUV_estimate');self.assertIsNone(p['events'][0]['goes_class'])
 def test_demon_empty(self):self.assertEqual(parse_demon(demon())['events'],[])
 def test_demon_lower_excluded(self):self.assertEqual(parse_demon(demon(row('C9')))['events'],[])
 def test_demon_off_limb_not_dropped(self):
  e=parse_demon(demon(row('M6','','')))['events'][0];self.assertIsNone(e['latitude']);self.assertIsNone(e['stonyhurst_longitude'])
 def test_demon_midnight(self):
  e=parse_demon(demon(row(start='23:54',peak='00:03',end='00:12')))['events'][0];self.assertTrue(e['peak'].startswith('2026-09-28'))
 def test_demon_no_heartbeat(self):
  with self.assertRaises(ValueError):parse_demon(demon().replace('Last processed image','Unavailable'))
 def test_demon_bad_coordinates(self):
  with self.assertRaises(ValueError):parse_demon(demon(row(lat='95')))
 def test_mct_values(self):
  p=parse_connectivity(POINTS);self.assertEqual(p['coordinate_frame'],'HGC');self.assertEqual(len(p['points']),2)
 def test_mct_count_gate(self):
  with self.assertRaises(ValueError):parse_connectivity(POINTS.replace('2 1 1 0','3 2 1 0'))
 def test_mct_reject_frame(self):
  with self.assertRaises(ValueError):parse_connectivity(POINTS.replace('Carrington','Stonyhurst'))
 def test_mct_reject_number(self):
  with self.assertRaises(ValueError):parse_connectivity(POINTS.replace('100 695700000 -2','nan 695700000 -2'))
if __name__=='__main__':unittest.main()
