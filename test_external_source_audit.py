import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest

from external_source_audit import main, update_audit


UTC = dt.timezone.utc


def payload(*, available: bool) -> dict:
    member = {
        "m1": 25.0,
        "x1": 5.0,
        "issued": "2026-08-23T12:00:00Z",
        "valid_start": "2026-08-23T12:00:00Z",
        "valid_end": "2026-08-24T12:00:00Z",
        "dataset_id": "MagPy_SHARP_HMI_CEA_FULLDISK",
        "source": "NASA/CCMC Flare Scoreboard · MagPy SHARP",
    }
    return {
        "issued": "2026-08-22T21:00:00Z",
        "valid_start": "2026-08-23T00:00:00Z",
        "valid_end": "2026-08-24T00:00:00Z",
        "regions": [
            {
                "id": "full-disk",
                "members": {"ccmc_magpy": member} if available else {},
            }
        ],
        "external_sources": {
            "provider_catalog": [
                {
                    "key": "ccmc_magpy",
                    "label": "CCMC MagPy SHARP",
                    "dataset_ids": ["MagPy_SHARP_HMI_CEA_FULLDISK"],
                }
            ],
            "ccmc_ccmc_magpy": {
                "ok": available,
                "detail": (
                    "Current probability accepted"
                    if available
                    else "Forecast window does not meaningfully overlap target"
                ),
            },
        },
    }


class ExternalSourceAuditTests(unittest.TestCase):
    def test_cli_writes_audit_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload_path = root / "flare_guidance.json"
            audit_path = root / "external_source_audit.json"
            payload_path.write_text(json.dumps(payload(available=True)), encoding="utf-8")

            result = main(
                [
                    "--payload",
                    str(payload_path),
                    "--audit-output",
                    str(audit_path),
                    "--checked-at",
                    "2026-08-23T12:20:00Z",
                ]
            )

            self.assertEqual(result, 0)
            self.assertTrue(audit_path.exists())
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertEqual(audit["providers"]["ccmc_magpy"]["state"], "available")

    def test_records_initial_state_once(self) -> None:
        first = update_audit(
            payload(available=False),
            None,
            checked_at=dt.datetime(2026, 8, 23, 0, 20, tzinfo=UTC),
        )
        self.assertEqual(first["providers"]["ccmc_magpy"]["state"], "unavailable")
        self.assertEqual(first["events"][-1]["event"], "observed_unavailable")

        second = update_audit(
            payload(available=False),
            first,
            checked_at=dt.datetime(2026, 8, 23, 12, 20, tzinfo=UTC),
        )
        self.assertEqual(len(second["events"]), 1)
        self.assertEqual(second["providers"]["ccmc_magpy"]["since"], "2026-08-23T00:20:00Z")

    def test_records_resume_and_stop_transitions(self) -> None:
        unavailable = update_audit(
            payload(available=False),
            None,
            checked_at=dt.datetime(2026, 8, 23, 0, 20, tzinfo=UTC),
        )
        resumed = update_audit(
            payload(available=True),
            unavailable,
            checked_at=dt.datetime(2026, 8, 23, 12, 20, tzinfo=UTC),
        )
        self.assertEqual(resumed["events"][-1]["event"], "resumed")
        self.assertEqual(resumed["providers"]["ccmc_magpy"]["state"], "available")
        self.assertEqual(resumed["providers"]["ccmc_magpy"]["latest_forecast"]["m1"], 25.0)

        stopped = update_audit(
            payload(available=False),
            resumed,
            checked_at=dt.datetime(2026, 8, 24, 0, 20, tzinfo=UTC),
        )
        self.assertEqual(stopped["events"][-1]["event"], "stopped")
        self.assertEqual(stopped["providers"]["ccmc_magpy"]["state"], "unavailable")
        self.assertEqual(
            stopped["providers"]["ccmc_magpy"]["latest_forecast"]["dataset_id"],
            "MagPy_SHARP_HMI_CEA_FULLDISK",
        )

    def test_requires_probability_member(self) -> None:
        candidate = payload(available=True)
        candidate["regions"][0]["members"] = {}
        audit = update_audit(
            candidate,
            None,
            checked_at=dt.datetime(2026, 8, 23, 12, 20, tzinfo=UTC),
        )
        self.assertEqual(audit["providers"]["ccmc_magpy"]["state"], "unavailable")

    def test_prefers_available_sidc_fallback_status(self) -> None:
        candidate = payload(available=False)
        candidate["external_sources"]["provider_catalog"] = [
            {"key": "sidc", "label": "SIDC Operator", "dataset_ids": []}
        ]
        candidate["regions"][0]["members"] = {"sidc": {"m1": 15.0, "x1": 2.0}}
        candidate["external_sources"].update(
            {
                "sidc_direct": {"ok": False, "detail": "Direct page unavailable"},
                "ccmc_sidc": {"ok": True, "detail": "Current HAPI fallback"},
            }
        )
        audit = update_audit(
            candidate,
            None,
            checked_at=dt.datetime(2026, 8, 23, 12, 20, tzinfo=UTC),
        )
        sidc = audit["providers"]["sidc"]
        self.assertEqual(sidc["state"], "available")
        self.assertEqual(sidc["status_key"], "ccmc_sidc")


if __name__ == "__main__":
    unittest.main()
