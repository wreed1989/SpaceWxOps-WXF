import argparse
import datetime as dt
import tempfile
import unittest
from pathlib import Path

import numpy as np

import sharp_mag_pipeline as smp


class SharpMagPipelineTests(unittest.TestCase):
    def test_canonical_region_and_explicit_fallback_coverage(self):
        issue = dt.datetime(2026, 9, 3, 21, tzinfo=smp.UTC)
        metadata = {
            14524: {
                "observed_date": "2026-09-03",
                "status": "f",
                "longitude": 64,
                "location": "N12E64",
                "spot_class": "Hax",
            },
            14523: {
                "observed_date": "2026-09-03",
                "status": "f",
                "longitude": 36,
                "location": "N10E36",
                "spot_class": "Cao",
            },
        }
        payload = smp.create_forecast_payload(
            live_rows=smp.pd.DataFrame(),
            m1_bundle={"training_prevalence": 0.03},
            x1_bundle={"training_prevalence": 0.004},
            manifest={"model_version": "unit-test"},
            issue_time=issue,
            input_stats={},
            operational=False,
            region_metadata=metadata,
        )
        regions = {row["id"]: row for row in payload["regions"]}
        self.assertEqual(smp.canonical_noaa_region(4524), 14524)
        self.assertIn("AR14523", regions)
        self.assertIn("AR14524", regions)
        self.assertEqual(
            regions["AR14524"]["members"]["sharpmag"]["method"],
            "morphology_fallback",
        )
        self.assertEqual(payload["wxf_full_disk"]["fallback_regions"], 2)
        self.assertGreater(regions["full-disk"]["members"]["sharpmag"]["m1"], 3.0)

    def test_direct_x1_is_feature_dependent_and_nested(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "synthetic.csv.gz"
            frame = smp.synthetic_training_table(dataset, days=900, regions_per_day=6)
            args = argparse.Namespace(
                dataset=dataset,
                model_dir=root / "models",
                model_version="unit-test-x",
                c_value=1.0,
                min_m1_positives=10,
                min_x1_positives=5,
                allow_small_sample=True,
                historical_series=smp.DEFAULT_HISTORICAL_SERIES,
                live_series=smp.DEFAULT_LIVE_SERIES,
                issue_hour=smp.DEFAULT_ISSUE_HOUR,
                input_lag_hours=smp.DEFAULT_INPUT_LAG_HOURS,
                max_longitude=smp.DEFAULT_MAX_LONGITUDE,
                max_obs_vr=smp.DEFAULT_MAX_OBS_VR,
                max_quality=smp.DEFAULT_MAX_QUALITY,
                max_input_age_hours=smp.DEFAULT_MAX_INPUT_AGE_HOURS,
            )
            paths = smp.train_models(args)
            _, x1, _, _ = smp.load_models(paths.directory)
            features = smp.engineer_features(frame)
            candidates = features.iloc[[0, -1]].copy()
            m1 = np.array([0.4, 0.4])
            x_probability = smp.x1_predict(m1, x1, candidates)
            self.assertEqual(x1["method"], "direct_magnetic_x1")
            self.assertFalse(np.isclose(x_probability[0], x_probability[1]))
            self.assertTrue(np.all(x_probability <= m1))


if __name__ == "__main__":
    unittest.main()
