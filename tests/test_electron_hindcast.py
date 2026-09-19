"""Temporal separation and block statistics for historical electron verification."""
import unittest

import numpy as np
import pandas as pd

from research.electron_fluence.hindcast import fold_masks, daily_calibration, paired_blocks


class HistoricalVerificationTests(unittest.TestCase):
    def test_training_and_calibration_targets_finish_before_next_partition(self):
        times = pd.date_range('2020-02-01', '2026-09-01', freq='3h', tz='UTC')
        for year in range(2022, 2027):
            train, cal, test = fold_masks(times, year)
            self.assertFalse((train & cal).any())
            self.assertFalse((cal & test).any())
            self.assertLess(times[train][-1]+pd.Timedelta(hours=24), times[cal][0])
            self.assertLess(times[cal][-1]+pd.Timedelta(hours=24), times[test][0])
            self.assertLess(times[test][-1]+pd.Timedelta(hours=24),
                            min(pd.Timestamp(f'{year+1}-01-01', tz='UTC'), pd.Timestamp('2026-09-01', tz='UTC')))

    def test_calibration_error_paths_do_not_overlap(self):
        times = pd.date_range('2024-07-01', periods=100, freq='3h', tz='UTC')
        mask = np.ones(len(times), dtype=bool); mask[7:19] = False
        chosen = daily_calibration(times, mask)
        self.assertTrue(mask[chosen].all())
        self.assertTrue(((times[chosen][1:]-times[chosen][:-1]) >= pd.Timedelta(hours=24)).all())

    def test_paired_blocks_preserve_known_error_difference_and_fold_boundaries(self):
        times = pd.date_range('2022-01-01', periods=60, freq='1D', tz='UTC').append(
            pd.date_range('2023-01-01', periods=60, freq='1D', tz='UTC'))
        frame = pd.DataFrame({'time':times, 'fold':times.year, 'truth24':100.,
                              'reference_median24':130., 'fullEventGuidance_median24':110.})
        for days in [7, 27]:
            result = paired_blocks(frame, 'reference', days, count=100)
            self.assertEqual(result['maeImprovement'], 20)
            np.testing.assert_array_equal(result['bootstrap95'], [20, 20])
            self.assertEqual(len(result['blocksPerFold']), 2)
            self.assertLess(sum(result['blocksPerFold']), len(frame))


if __name__ == '__main__':
    unittest.main()
