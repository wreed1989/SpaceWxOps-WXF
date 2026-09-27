"""Offline fixtures only. Tests never use real credentials or provider connections."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import check_access as m


def response(body=b'{}', status=200, kind='application/json', **headers):
    return m.Response(status, {'content-type':kind, **headers}, body)


class AccessTests(unittest.TestCase):
    def test_missing_secret_does_not_send(self):
        with patch.object(m,'exchange') as send:
            with self.assertRaisesRegex(m.SafeError,'missing_repository_secret'):
                m.M2M('fixture-id','').token('swe_hapiserver')
            send.assert_not_called()

    def test_token_scopes_separate_cached(self):
        def reply(url, **kwargs):
            return response(json.dumps({'access_token': 'FAKE.'+kwargs['form']['scope'],
                                        'token_type':'Bearer','expires_in':300}).encode())
        with patch.object(m,'exchange',side_effect=reply) as send:
            client=m.M2M('fixture-id','fixture-secret')
            h=client.token('swe_hapiserver')
            self.assertEqual(h,client.token('swe_hapiserver'))
            self.assertNotEqual(h,client.token('swe_contentproxy'))
            self.assertEqual(send.call_count,2)
            self.assertEqual(send.call_args.kwargs['form']['client_secret'],'fixture-secret')

    def test_unsupported_scope(self):
        with self.assertRaisesRegex(m.SafeError,'unapproved_scope'):
            m.M2M('fixture-id','fixture-secret').token('openid')

    def test_token_error_no_body_leak_and_negative_cache(self):
        reply=response(b'{"error":"invalid_client","error_description":"VERY_PRIVATE"}',401)
        with patch.object(m,'exchange',return_value=reply) as send:
            client=m.M2M('fixture-id','fixture-secret')
            for _ in range(2):
                with self.assertRaisesRegex(m.SafeError,'^invalid_client$'):
                    client.token('swe_hapiserver')
            self.assertEqual(send.call_count,1)

    def test_network_failure_negative_cache(self):
        with patch.object(m,'exchange',side_effect=m.SafeError('dns_failure')) as send:
            client=m.M2M('fixture-id','fixture-secret')
            for _ in range(2):
                with self.assertRaises(m.SafeError):client.token('swe_contentproxy')
            self.assertEqual(send.call_count,1)

    def test_missing_token(self):
        with patch.object(m,'exchange',return_value=response(b'{"expires_in":300}')):
            with self.assertRaisesRegex(m.SafeError,'invalid_token_response'):
                m.M2M('fixture-id','fixture-secret').token('swe_contentproxy')

    def test_misrouted_bearer_denied(self):
        for url,scope in [('https://sso.kso.ac.at/prod/API/index.php','swe_hapiserver'),
                          (m.SIDC,'swe_hapiserver')]:
            with self.assertRaisesRegex(m.SafeError,'token_audience_mismatch'):
                m.exchange(url,bearer='FAKE',scope=scope)

    def test_secret_post_only_esa(self):
        with self.assertRaisesRegex(m.SafeError,'unsafe_token_destination'):
            m.exchange(m.SIDC,form={'client_secret':'FAKE'})

    def test_bad_destinations(self):
        for url in ['http://swe.ssa.esa.int/hapi/catalog','https://127.0.0.1/x',
                    'https://swe.ssa.esa.int.evil.test/x','https://u:p@swe.ssa.esa.int/x']:
            with self.assertRaises(m.SafeError):m.exchange(url)

    def test_redirect_handler(self):
        self.assertIsNone(m.NoRedirect().redirect_request(None,None,302,'',{},'https://example.test'))

    def test_login_redirect_detected_no_query_leak(self):
        result=m.inspect_response(response(status=302,location='https://sso.s2p.esa.int/realms/swe/protocol/openid-connect/auth?client_id=swe_contentproxy&state=PRIVATE'),'svg')
        self.assertEqual(result['status'],'login_redirect')
        self.assertEqual(result['required_scope'],'swe_contentproxy')
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_hapi_status_required(self):
        self.assertEqual(m.inspect_response(response(b'{"status":{"code":1200},"catalog":[]}'),'hapi')['status'],'readable_json')
        self.assertEqual(m.inspect_response(response(b'{"catalog":[]}'),'hapi')['status'],'hapi_not_ok')

    def test_json_schema_not_values(self):
        result=m.inspect_response(response(b'{"data":[{"area":13,"label":"PRIVATE"}]}'),'json')
        self.assertEqual(result['schema']['record_count'],1)
        self.assertEqual(result['schema']['record_keys'],['area','label'])
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_false_json(self):
        for body,status in [(b'null','unexpected_json_root'),(b'garbage','invalid_json'),(b'{"error":"secret reason"}','provider_error_json')]:
            self.assertEqual(m.inspect_response(response(body),'json')['status'],status)

    def test_html_not_json(self):
        for kind in ['text/html','application/json']:
            self.assertEqual(m.inspect_response(response(b'<!doctype html><html>login</html>',kind=kind),'json')['status'],'html_instead_of_product')

    def test_provider_page_not_model_data(self):
        self.assertEqual(m.inspect_response(response(b'<html>EUHFORIA</html>',kind='text/html'),'provider_page')['status'],'provider_page_only')

    def test_password_page_never_success(self):
        self.assertEqual(m.inspect_response(response(b'<html><input type="password"></html>',kind='text/html'),'provider_page')['status'],'login_page')

    def test_xml_schema_no_values(self):
        result=m.inspect_response(response(b'<forecast><probability value="0.3"/></forecast>',kind='application/xml'),'xml')
        self.assertEqual(result['status'],'readable_xml')
        self.assertEqual(result['schema']['attribute_names'],['value'])
        self.assertNotIn('0.3',json.dumps(result))

    def test_dtd_rejected(self):
        self.assertEqual(m.inspect_response(response(b'<!DOCTYPE a [<!ENTITY x "oops">]><a>&x;</a>'),'xml')['status'],'xml_dtd_rejected')

    def test_svg_required(self):
        self.assertEqual(m.inspect_response(response(b'<svg xmlns="http://www.w3.org/2000/svg"/>'),'svg')['status'],'readable_svg')
        self.assertEqual(m.inspect_response(response(b'<error>oops</error>'),'svg')['status'],'unexpected_xml_root')

    def test_image_magic(self):
        self.assertEqual(m.inspect_response(response(b'\x89PNG\r\n\x1a\nfixture'),'map')['status'],'image_signature_received')
        self.assertEqual(m.inspect_response(response(b'not image',kind='image/png'),'map')['status'],'not_an_image')

    def test_dynamic_date(self):
        rows=m.targets(datetime(2026,9,27,5,43,tzinfo=timezone.utc))
        self.assertTrue(any('20260927T000000' in row[1] for row in rows))
        self.assertFalse(any('/2021' in row[1] for row in rows))
        self.assertEqual(len(rows),11)

    def test_report_has_no_secrets(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,{'ESAID':'PRIVATEID','ESASECRET':'PRIVATESECRET','ESA_REPORT_DIR':temp,'GITHUB_ACTIONS':'false'},clear=True):
            with patch.object(m,'exchange',side_effect=m.SafeError('dns_failure')),contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(m.main(),1)
            report=''.join(p.read_text() for p in Path(temp).glob('*'))+stdout.getvalue()
            self.assertNotIn('PRIVATEID',report)
            self.assertNotIn('PRIVATESECRET',report)
            self.assertIn('dns_failure',report)

    def test_all_failures_still_report_all_targets(self):
        with patch.object(m,'exchange',side_effect=m.SafeError('network_failure')):
            r=m.run(m.M2M('fixture-id','fixture-secret'))
            self.assertEqual(len(r['products']),11)


if __name__=='__main__':unittest.main()
