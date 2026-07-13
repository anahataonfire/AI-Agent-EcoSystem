"""
Regression tests for edge_calculator.py.
Covers: std_dev unit conversion (PD-144 R1), probability calculation,
        unit normalization, and opportunity detection.

PD-144 R5
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edge_calculator import EdgeCalculator, bucket_probability, normal_cdf


class TestNormalCdf(unittest.TestCase):
    """Pure Python CDF implementation correctness."""

    def test_mean_is_50_percent(self):
        self.assertAlmostEqual(normal_cdf(0, 0, 1), 0.5, places=4)

    def test_one_std_above(self):
        # P(X <= mean + 1*std) ~ 0.8413
        self.assertAlmostEqual(normal_cdf(1, 0, 1), 0.8413, places=3)

    def test_two_std_above(self):
        # P(X <= mean + 2*std) ~ 0.9772
        self.assertAlmostEqual(normal_cdf(2, 0, 1), 0.9772, places=3)

    def test_zero_std_above_mean(self):
        self.assertEqual(normal_cdf(5, 3, 0), 1.0)

    def test_zero_std_below_mean(self):
        self.assertEqual(normal_cdf(1, 3, 0), 0.0)


class TestBucketProbability(unittest.TestCase):
    """Probability of temperature falling in a bucket."""

    def test_forecast_in_bucket(self):
        # Forecast right in the middle of bucket -- high probability
        prob = bucket_probability(50, 49, 51, 2.5)
        self.assertGreater(prob, 0.3)

    def test_forecast_far_from_bucket(self):
        # 10 degrees away
        prob = bucket_probability(50, 60, 62, 2.5)
        self.assertLess(prob, 0.01)

    def test_or_below_bucket(self):
        prob = bucket_probability(50, float('-inf'), 40, 2.5)
        self.assertLess(prob, 0.01)

    def test_or_above_bucket(self):
        prob = bucket_probability(50, 60, float('inf'), 2.5)
        self.assertLess(prob, 0.01)

    def test_probabilities_sum_greater_than_one_due_to_discrete_rounding(self):
        """bucket_probability adds +/-0.5 for discrete temp rounding.

        This means adjacent non-overlapping buckets will sum to >1.0 when
        using the +0.5 padding. This is intentional to handle integer
        temperature readings -- the test documents this behavior.
        """
        total = (
            bucket_probability(50, float('-inf'), 45, 2.5) +
            bucket_probability(50, 45, 48, 2.5) +
            bucket_probability(50, 48, 50, 2.5) +
            bucket_probability(50, 50, 52, 2.5) +
            bucket_probability(50, 52, 55, 2.5) +
            bucket_probability(50, 55, float('inf'), 2.5)
        )
        # Sum > 1.0 is expected due to +0.5 overlap at bucket boundaries
        self.assertGreater(total, 1.0)
        # But shouldn't be wildly off
        self.assertLess(total, 1.6)


class TestStdDevUnitConversion(unittest.TestCase):
    """PD-144 R1: std_dev must be converted for Celsius markets."""

    def setUp(self):
        self.calc = EdgeCalculator()

    def test_fahrenheit_std_dev_unchanged(self):
        std = self.calc._get_std_dev(24, "F")
        self.assertAlmostEqual(std, 2.5, places=2)

    def test_celsius_std_dev_scaled(self):
        std = self.calc._get_std_dev(24, "C")
        expected = 2.5 / 1.8
        self.assertAlmostEqual(std, expected, places=2)

    def test_celsius_std_dev_in_fahrenheit_equivalent(self):
        """C std * 1.8 should equal the F std."""
        std_f = self.calc._get_std_dev(24, "F")
        std_c = self.calc._get_std_dev(24, "C")
        self.assertAlmostEqual(std_c * 1.8, std_f, places=2)

    def test_longer_horizon_scales_both_units(self):
        std_f_24 = self.calc._get_std_dev(24, "F")
        std_f_48 = self.calc._get_std_dev(48, "F")
        std_c_24 = self.calc._get_std_dev(24, "C")
        std_c_48 = self.calc._get_std_dev(48, "C")
        self.assertGreater(std_f_48, std_f_24)
        self.assertGreater(std_c_48, std_c_24)
        # Ratio should be the same
        ratio_f = std_f_48 / std_f_24
        ratio_c = std_c_48 / std_c_24
        self.assertAlmostEqual(ratio_f, ratio_c, places=2)

    def test_celsius_probability_no_longer_inflated(self):
        """Before fix: 2.5C std gave 0.1935. After fix: ~0.1342 (correct)."""
        std_c = self.calc._get_std_dev(24, "C")
        prob = bucket_probability(10, 7, 8, std_c)
        # Should be significantly less than the old buggy value of 0.1935
        self.assertLess(prob, 0.16)
        # But still a reasonable probability for 3C away
        self.assertGreater(prob, 0.05)


class TestUnitNormalization(unittest.TestCase):
    """_normalize_units converts forecast to bucket's unit system."""

    def setUp(self):
        self.calc = EdgeCalculator()

    def test_same_units_no_conversion(self):
        temp, lo, hi = self.calc._normalize_units(50.0, "F", 48.0, 52.0, "F")
        self.assertEqual(temp, 50.0)

    def test_f_to_c_conversion(self):
        temp, lo, hi = self.calc._normalize_units(50.0, "F", 8.0, 10.0, "C")
        self.assertAlmostEqual(temp, 10.0, places=1)  # 50F = 10C
        self.assertEqual(lo, 8.0)  # Bucket bounds unchanged

    def test_c_to_f_conversion(self):
        temp, lo, hi = self.calc._normalize_units(10.0, "C", 48.0, 52.0, "F")
        self.assertAlmostEqual(temp, 50.0, places=1)  # 10C = 50F


if __name__ == "__main__":
    unittest.main()
