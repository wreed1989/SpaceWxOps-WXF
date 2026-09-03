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


if __name__ == "__main__":
    unittest.main()
