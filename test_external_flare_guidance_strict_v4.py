import unittest

import external_flare_guidance_strict_v4 as guidance


class StrictGuidanceCompatibilityTests(unittest.TestCase):
    def test_restores_unique_component_union_after_legacy_proxy(self):
        payload = {
            "model_version": "test-direct-x",
            "operational": False,
            "wxf_full_disk": {"method": "maximum regional probability (dominant-region proxy)"},
            "wxf_region_components": [
                {"component_id": "HARP1", "m1": 10.04, "x1": 1.04},
                {"component_id": "AR10003-fallback", "m1": 20.04, "x1": 2.04},
            ],
            "regions": [
                {
                    "id": "full-disk",
                    "members": {"sharpmag": {"m1": 10.0, "x1": 1.0}},
                },
                {
                    "id": "AR10001",
                    "members": {"sharpmag": {
                        "m1": 10.0,
                        "x1": 1.0,
                        "method": "sharp_magnetic",
                        "component_id": "HARP1",
                    }},
                },
                {
                    "id": "AR10002",
                    "members": {"sharpmag": {
                        "m1": 10.0,
                        "x1": 1.0,
                        "method": "sharp_magnetic",
                        "component_id": "HARP1",
                    }},
                },
                {
                    "id": "AR10003",
                    "members": {"sharpmag": {
                        "m1": 20.0,
                        "x1": 2.0,
                        "method": "morphology_fallback",
                        "component_id": "AR10003-fallback",
                    }},
                },
            ],
        }
        guidance._restore_wxf_full_disk_union(payload)
        full = payload["regions"][0]["members"]["sharpmag"]
        self.assertEqual(full["m1"], 28.1)
        self.assertEqual(full["x1"], 3.1)
        self.assertEqual(payload["wxf_full_disk"]["components"], 2)
        self.assertEqual(payload["wxf_full_disk"]["method"], "union_of_unique_region_components")

class SwpcRecoveryTests(unittest.TestCase):
    def test_swpc_refreshed_when_magnetic_benchmark_missing(self):
        import datetime as dt
        from unittest.mock import patch, Mock
        import swpc_flare
        text = ':Issued: 2026 Sep 19 2200 UTC\n:Prediction_dates: 2026 Sep 20 2026 Sep 21 2026 Sep 22\nClass_M 15 20 25\nClass_X 1 2 3\n'
        p={'valid_start':'2026-09-20T00:00:00Z','regions':[{'id':'full-disk','members':{'sharpmag':{'m1':10,'x1':1}}}]}
        with patch('swpc_flare.requests.get',return_value=Mock(text=text)):
            swpc_flare.refresh_benchmark(p)
        self.assertEqual(p['regions'][0]['members']['swpc']['m1'],15)
        self.assertTrue(p['external_sources']['swpc']['ok'])
        with self.assertRaises(ValueError):swpc_flare.parse(text.replace('Class_X 1 2 3','Class_X 16 2 3'),dt.date(2026,9,20))
        with patch('swpc_flare.requests.get',side_effect=swpc_flare.requests.Timeout('Timed out')):
            swpc_flare.refresh_benchmark(p)
        self.assertIsNone(p['regions'][0]['members']['swpc']['m1'])
        self.assertFalse(p['external_sources']['swpc']['ok'])

    def test_retained_wxf_does_not_acquire_new_valid_window(self):
        import swpc_flare
        p={'issued':'2026-09-19T21:00:00Z','generation_status':{'used_previous_forecast':True,'previous_issued':'2026-09-16T21:00:00Z'},'regions':[{'id':'AR12345','members':{'sharpmag':{'m1':10,'x1':1}}},{'id':'full-disk','members':{'sharpmag':{'m1':10,'x1':1}}}]}
        swpc_flare.preserve_stale_windows(p)
        guidance._restore_wxf_full_disk_union(p)
        swpc_flare.preserve_stale_windows(p)
        p['generation_status']['previous_issued']='2026-09-19T21:00:00Z'
        swpc_flare.preserve_stale_windows(p)
        for r in p['regions']:
            self.assertEqual(r['members']['sharpmag']['valid_end'],'2026-09-18T00:00:00+00:00')
            self.assertEqual(r['members']['sharpmag']['quality'],'stale-fallback')


class ScheduledBaseRecoveryTests(unittest.TestCase):
    def test_only_newer_current_published_base_is_accepted(self):
        import datetime as dt
        from unittest.mock import patch, Mock
        stale={'issued':'2026-09-16T21:00:00Z','valid_start':'2026-09-17T00:00:00Z','valid_end':'2026-09-18T00:00:00Z'}
        current={'issued':'2026-09-19T21:00:00Z','valid_start':'2026-09-20T00:00:00Z','valid_end':'2026-09-21T00:00:00Z','regions':[{'id':'full-disk','members':{'sharpmag':{'m1':10,'x1':1}}}]}
        now=dt.datetime(2026,9,19,22,tzinfo=dt.timezone.utc)
        get=Mock(return_value=Mock(json=lambda:current))
        with patch.dict('os.environ',{'GITHUB_WORKFLOW':'Refresh current external flare guidance'}):
            self.assertIs(guidance.recover_current_publication(stale,now=now,get=get),current)
            get.reset_mock()
            self.assertIs(guidance.recover_current_publication(current,now=now,get=get),current)
            get.assert_not_called()
            get.return_value=Mock(json=lambda:stale)
            self.assertIs(guidance.recover_current_publication(stale,now=now,get=get),stale)
        with patch.dict('os.environ',{'GITHUB_WORKFLOW':'WXF daily'}):
            get.reset_mock()
            self.assertIs(guidance.recover_current_publication(stale,now=now,get=get),stale)
            get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
