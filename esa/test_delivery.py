import base64,hashlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import harvest as h
from current_connectivity import registration,registered
from current_aeffort import parse_web
from current_hapi import current_hapi

CSS='.map_frame_popup {width:1250px;height:600px;top:50%;left:50%;}\n.map_img_popup {width:900px;height:498px;left:84px;bottom:48px;}'
WEB='''27/09/2026 03:58:39 UT
Full disc probabilities
ARIA_Image_20260927_035839.png
M1: 20
M5: 7
X1: 4
X5: 0
----------
Number of ARs: 1
----------
AR14535_20260927_035839_connections.png
0.50 0.49 0.60 0.59
AR: NOAA AR 14535
Loc: N12 W07
Beff: 403
M1: 14
M5: 5
X1: 3
X5: 0
EOF
'''
class DeliveryContracts(unittest.TestCase):
 def test_utc_naive(self):self.assertEqual(h.utc('2026-09-27T04:00:05'),'2026-09-27T04:00:05Z')
 def test_utc_offset(self):self.assertEqual(h.utc('2026-09-27T01:00:00-05:00'),'2026-09-27T06:00:00Z')
 def test_utc_bad_calendar(self):self.assertIsNone(h.utc('2026-02-30T04:00:05'))
 def test_utc_missing(self):self.assertIsNone(h.utc(None))
 def test_svg_external_declaration(self):self.assertEqual(h.tag(h.xml_root(b'<!DOCTYPE svg PUBLIC "a" "https://w3.org/test.dtd"><svg/>')),'svg')
 def test_svg_entity_rejected(self):
  with self.assertRaises(h.auth.SafeError):h.xml_root(b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg>&x;</svg>')
 def test_non_svg_dtd_rejected(self):
  with self.assertRaises(h.auth.SafeError):h.xml_root(b'<!DOCTYPE html SYSTEM "x"><html/>')
 def test_active_svg_removed(self):
  r=h.passive_svg(b'<svg onload="evil()"><script>evil()</script><foreignObject/><image href="https://evil.invalid/a"/><circle fill="url(https://evil.invalid/b)"/></svg>')['svg']
  for x in ('script','evil','foreignObject','https://'):self.assertNotIn(x,r)
 def test_mislabeled_embedded_jpeg(self):
  out=io.BytesIO();Image.new('RGB',(100,100)).save(out,format='JPEG');b=base64.b64encode(out.getvalue()).decode()
  r=h.passive_svg(('<svg><g id="group_current_regions_noaa_region"><text>1234</text></g><image href="data:image/jp2;base64,'+b+'"/></svg>').encode())
  self.assertTrue(r['has_image']);self.assertIn('data:image/jpeg;',r['svg']);self.assertEqual(r['layers']['regions_noaa_region'],1)
 def test_invalid_embedded_image_removed(self):self.assertFalse(h.passive_svg(b'<svg><image href="data:image/jpeg;base64,AAAA"/></svg>')['has_image'])
 def test_native_model_units_preserved(self):
  r=h.parse_dsv('# DATE = 2026-09-26T07:00:35\ndate[UTC] vr[km/s] Bclt[nT]\n2026-09-27T00:00:00 500 -4\n2026-09-27T01:00:00 501 -3\n')
  self.assertEqual(r['columns'][2]['name'],'Bclt');self.assertEqual(r['rows'][0][1],500);self.assertEqual(r['run_at'],'2026-09-26T07:00:35Z')
 def test_provider_internal_runlog_not_published(self):
  r=h.parse_dsv('# VERSION = internal run log\n# DATE = 2026-09-26T07:00:35\ndate[UTC] n[1/cm^3]\n2026-09-27T00:00:00 3\n');self.assertNotIn('VERSION',r['metadata'])
 def test_nonfinite_model_rejected(self):
  with self.assertRaises(h.auth.SafeError):h.parse_dsv('date[UTC] vr[km/s]\n2026-09-27T00:00:00 nan\n')
 def test_unordered_model_rejected(self):
  with self.assertRaises(h.auth.SafeError):h.parse_dsv('date[UTC] vr[km/s]\n2026-09-27T01:00:00 3\n2026-09-27T00:00:00 4\n')
 def test_registration_uses_provider_offsets(self):
  r=registration(CSS);self.assertEqual((r['left'],r['top'],r['map_width'],r['map_height']),(84,54,900,498))
 def test_missing_registration_rejected(self):
  with self.assertRaises(h.auth.SafeError):registration('.map_frame{width:1px;}')
 def test_out_of_frame_registration_rejected(self):
  with self.assertRaises(h.auth.SafeError):registration(CSS.replace('left:84px','left:999px'))
 def test_registered_pixels_not_interpolated(self):
  with tempfile.TemporaryDirectory() as d:
   c=h.Harvester(Path(d));out=io.BytesIO();Image.new('RGBA',(900,498),(30,90,200,127)).save(out,format='PNG');c.request=lambda u:(out.getvalue(),{})
   a=c.asset('https://connect-tool.irap.omp.eu/a.png');r=registered(c,'https://connect-tool.irap.omp.eu/a.png',a,registration(CSS),False)
   im=Image.open(Path(d)/r['path']);self.assertEqual(im.size,(1250,600));self.assertEqual(im.getpixel((84,54)),(30,90,200,127));self.assertEqual(im.getpixel((83,54)),(0,0,0,0))
 def test_aeffort_values_and_regions(self):
  r=parse_web(WEB);self.assertEqual(len(r['records']),2);self.assertEqual(r['records'][0]['probabilities']['M1+'],.20);self.assertEqual(r['records'][1]['region'],'14535')
 def test_aeffort_no_invented_validity(self):
  r=parse_web(WEB);self.assertIsNone(r['issued_at']);self.assertIsNone(r['valid_start']);self.assertIsNone(r['valid_end']);self.assertEqual(r['reference_type'],'Input Magnetogram')
 def test_aeffort_region_count_rejected(self):
  with self.assertRaises(h.auth.SafeError):parse_web(WEB.replace('Number of ARs: 1','Number of ARs: 2'))
 def test_aeffort_nonmonotonic_rejected(self):
  with self.assertRaises(h.auth.SafeError):parse_web(WEB.replace('M5: 7','M5: 70'))
 def test_path_traversal_rejected(self):self.assertIsNone(h.ASSET_RE.fullmatch('../../main.html'))
 def test_login_not_image(self):
  with tempfile.TemporaryDirectory() as d:
   c=h.Harvester(Path(d));c.request=lambda u:(b'<html>Login</html>',{})
   with self.assertRaises(h.auth.SafeError):c.asset('https://sso.kso.ac.at/image.jpg')
 def test_failure_keeps_original_freshness(self):
  with tempfile.TemporaryDirectory() as d:
   c=h.Harvester(Path(d));c.old={'products':{'sidc':{'status':'ok','fetched_at':'2026-09-26T00:00:00Z','xml':'<a/>'}}}
   def fail():raise h.auth.SafeError('timeout')
   c.product('sidc',fail);self.assertEqual(c.doc['products']['sidc']['fetched_at'],'2026-09-26T00:00:00Z');self.assertEqual(c.doc['products']['sidc']['status'],'last_good')
 def test_new_failure_not_zero(self):
  with tempfile.TemporaryDirectory() as d:
   c=h.Harvester(Path(d))
   def fail():raise h.auth.SafeError('timeout')
   c.product('sidc',fail);self.assertEqual(c.doc['products']['sidc']['status'],'unavailable');self.assertNotIn('probabilities',c.doc['products']['sidc'])
 def test_no_foreign_token_redirect(self):
  with tempfile.TemporaryDirectory() as d:
   c=h.Harvester(Path(d));c.client.token=lambda s:'TOKEN';calls=[]
   def exchange(u,**kw):calls.append(u);return h.auth.Response(302,{'location':'https://evil.invalid/foo'},b'')
   with patch.object(h.auth,'exchange',exchange):
    with self.assertRaises(h.auth.SafeError):c.request(h.SIDC)
   self.assertEqual(len(calls),1)
 def test_hapi_size_one_and_no_data(self):
  with tempfile.TemporaryDirectory() as d:
   c=h.Harvester(Path(d));calls=[]
   def fake(u):
    calls.append(u)
    if 'catalog' in u:return {'status':{'code':1200},'catalog':[{'id':'x'}]}
    if 'info?' in u:return {'status':{'code':1200},'parameters':[{'name':'utc','type':'isotime','size':[1]},{'name':'B','type':'double','size':[1]}]}
    return {'status':{'code':1201,'message':'No data for time range'}}
   c.json=fake;r=current_hapi(c);self.assertEqual(r['samples']['x']['response']['status']['code'],1201);self.assertIn('parameters=utc%2CB',calls[-1]);self.assertNotIn('data',r['samples']['x']['response'])
if __name__=='__main__':unittest.main(verbosity=2)
