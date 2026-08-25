import copy
import unittest

from publication_guard import publish_worthy_change


def payload() -> dict:
    return {
        "issued": "2026-08-23T21:00:00Z",
        "valid_start": "2026-08-24T00:00:00Z",
        "regions": [{"id": "full-disk", "members": {"mcstat": {"m1": 82.0, "x1": 20.0}}}],
        "solar_monitor": {"retrieved_at": "2026-08-24T04:10:23Z", "regional_forecasts": 4},
        "external_sources": {"generated_at": "2026-08-24T12:20:00Z", "script_version": "5.0.0"},
    }


def audit(state: str = "available") -> dict:
    return {
        "schema_version": 1,
        "updated_at": "2026-08-24T12:20:00Z",
        "forecast_issued": "2026-08-23T21:00:00Z",
        "forecast_valid_start": "2026-08-24T00:00:00Z",
        "forecast_valid_end": "2026-08-25T00:00:00Z",
        "providers": {"sidc": {"state": state, "last_checked": "2026-08-24T12:20:00Z"}},
        "events": [{"at": "2026-08-24T00:20:00Z", "provider": "sidc", "event": "observed_available"}],
    }


class PublicationGuardTests(unittest.TestCase):
    def test_ignores_retrieval_and_check_timestamps(self) -> None:
        candidate_payload = copy.deepcopy(payload())
        candidate_payload["solar_monitor"]["retrieved_at"] = "2026-08-24T19:05:02Z"
        candidate_payload["external_sources"]["generated_at"] = "2026-08-24T19:05:02Z"
        candidate_payload["external_sources"]["sidc_direct"] = {
            "ok": True,
            "detail": "HTTP diagnostic wording changed",
        }
        candidate_audit = copy.deepcopy(audit())
        candidate_audit["updated_at"] = "2026-08-24T19:05:02Z"
        candidate_audit["providers"]["sidc"]["last_checked"] = "2026-08-24T19:05:02Z"

        changed, reasons = publish_worthy_change(payload(), candidate_payload, audit(), candidate_audit)
        self.assertFalse(changed)
        self.assertEqual(reasons, [])

    def test_probability_change_is_publish_worthy(self) -> None:
        candidate = copy.deepcopy(payload())
        candidate["regions"][0]["members"]["mcstat"]["m1"] = 85.0
        self.assertTrue(publish_worthy_change(payload(), candidate)[0])

    def test_provider_state_and_transition_are_publish_worthy(self) -> None:
        candidate = audit("unavailable")
        candidate["events"].append(
            {"at": "2026-08-24T12:20:00Z", "provider": "sidc", "event": "stopped"}
        )
        self.assertTrue(publish_worthy_change(payload(), payload(), audit(), candidate)[0])


if __name__ == "__main__":
    unittest.main()
