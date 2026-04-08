"""
Regression tests for the consolidated EdgeHarvestScanner.
Covers: band calculation, unit awareness, risk scoring, front warnings,
        opportunity filtering, and the bucket property alias.

PD-144 R5
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edge_harvest import (
    EdgeHarvestScanner,
    EdgeHarvestOpportunity,
    FrontWarning,
    get_edge_harvest_scanner,
)


class TestBucketWidth(unittest.TestCase):
    """BUCKET_WIDTH_F and BUCKET_WIDTH_C drive all distance calculations."""

    def setUp(self):
        self.scanner = EdgeHarvestScanner()

    def test_fahrenheit_width(self):
        self.assertEqual(self.scanner._bucket_width("F"), 2.0)

    def test_celsius_width(self):
        self.assertEqual(self.scanner._bucket_width("C"), 1.0)

    def test_default_is_fahrenheit(self):
        self.assertEqual(self.scanner._bucket_width(), 2.0)


class TestBandsAway(unittest.TestCase):
    """Band calculation must be unit-aware (PD-144 R2)."""

    def setUp(self):
        self.scanner = EdgeHarvestScanner()

    # -- Fahrenheit markets --

    def test_f_normal_bucket_below_forecast(self):
        bands, deg = self.scanner.calculate_bands_away(50.0, 42.0, 43.0, unit="F")
        self.assertEqual(bands, 3)
        self.assertAlmostEqual(deg, 7.0)

    def test_f_normal_bucket_above_forecast(self):
        bands, deg = self.scanner.calculate_bands_away(50.0, 58.0, 59.0, unit="F")
        self.assertEqual(bands, 4)
        self.assertAlmostEqual(deg, 8.0)

    def test_f_forecast_inside_bucket(self):
        bands, deg = self.scanner.calculate_bands_away(50.0, 49.0, 51.0, unit="F")
        self.assertEqual(bands, 0)
        self.assertAlmostEqual(deg, 0.0)

    def test_f_or_below_bucket(self):
        bands, deg = self.scanner.calculate_bands_away(50.0, None, 40.0, unit="F")
        self.assertEqual(bands, 5)
        self.assertAlmostEqual(deg, 10.0)

    def test_f_or_above_bucket(self):
        bands, deg = self.scanner.calculate_bands_away(50.0, 60.0, None, unit="F")
        self.assertEqual(bands, 5)
        self.assertAlmostEqual(deg, 10.0)

    def test_f_negative_inf_bucket(self):
        bands, deg = self.scanner.calculate_bands_away(50.0, float('-inf'), 40.0, unit="F")
        self.assertEqual(bands, 5)

    def test_f_positive_inf_bucket(self):
        bands, deg = self.scanner.calculate_bands_away(50.0, 62.0, float('inf'), unit="F")
        self.assertEqual(bands, 6)

    # -- Celsius markets --

    def test_c_normal_bucket(self):
        # 15C forecast, 10-11C bucket = 4C / 1.0 = 4 bands
        bands, deg = self.scanner.calculate_bands_away(15.0, 10.0, 11.0, unit="C")
        self.assertEqual(bands, 4)
        self.assertAlmostEqual(deg, 4.0)

    def test_c_close_bucket(self):
        # 15C forecast, 13-14C bucket = 1C / 1.0 = 1 band
        bands, deg = self.scanner.calculate_bands_away(15.0, 13.0, 14.0, unit="C")
        self.assertEqual(bands, 1)
        self.assertAlmostEqual(deg, 1.0)

    def test_c_or_below_bucket(self):
        bands, deg = self.scanner.calculate_bands_away(15.0, None, 10.0, unit="C")
        self.assertEqual(bands, 5)

    def test_c_or_above_bucket(self):
        bands, deg = self.scanner.calculate_bands_away(15.0, 20.0, None, unit="C")
        self.assertEqual(bands, 5)

    # -- Cross-unit equivalence --

    def test_same_physical_distance_different_bands(self):
        """6F away = 3 bands. 3.33C away (same physical distance) = 3 bands."""
        bands_f, _ = self.scanner.calculate_bands_away(50.0, 44.0, 44.0, unit="F")
        bands_c, _ = self.scanner.calculate_bands_away(10.0, 7.0, 7.0, unit="C")
        self.assertEqual(bands_f, 3)
        self.assertEqual(bands_c, 3)


class TestFrontWarnings(unittest.TestCase):
    """Front warning detection from forecast model disagreement."""

    def setUp(self):
        self.scanner = EdgeHarvestScanner()

    def _make_forecast(self, ecmwf=None, gfs=None, confidence=0.9):
        class MockForecast:
            pass
        f = MockForecast()
        f.ecmwf_high = ecmwf
        f.gfs_high = gfs
        f.confidence = confidence
        return f

    def test_no_warnings_when_models_agree(self):
        forecast = self._make_forecast(ecmwf=50.0, gfs=51.0)
        warnings = self.scanner.detect_front_warnings("nyc", "2026-04-08", forecast)
        self.assertEqual(len(warnings), 0)

    def test_low_severity_3f_spread(self):
        forecast = self._make_forecast(ecmwf=50.0, gfs=53.0)
        warnings = self.scanner.detect_front_warnings("nyc", "2026-04-08", forecast)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].severity, "LOW")

    def test_medium_severity_5f_spread(self):
        forecast = self._make_forecast(ecmwf=50.0, gfs=55.0)
        warnings = self.scanner.detect_front_warnings("nyc", "2026-04-08", forecast)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].severity, "MEDIUM")

    def test_high_severity_8f_spread(self):
        forecast = self._make_forecast(ecmwf=50.0, gfs=58.0)
        warnings = self.scanner.detect_front_warnings("nyc", "2026-04-08", forecast)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].severity, "HIGH")

    def test_low_confidence_high_severity(self):
        forecast = self._make_forecast(ecmwf=50.0, gfs=50.0, confidence=0.4)
        warnings = self.scanner.detect_front_warnings("nyc", "2026-04-08", forecast)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].warning_type, "LOW_CONFIDENCE")
        self.assertEqual(warnings[0].severity, "HIGH")

    def test_multiple_warnings(self):
        """High spread + low confidence = two warnings."""
        forecast = self._make_forecast(ecmwf=50.0, gfs=59.0, confidence=0.3)
        warnings = self.scanner.detect_front_warnings("nyc", "2026-04-08", forecast)
        self.assertEqual(len(warnings), 2)
        types = {w.warning_type for w in warnings}
        self.assertIn("MODEL_SPREAD", types)
        self.assertIn("LOW_CONFIDENCE", types)

    def test_front_warning_dataclass_fields(self):
        w = FrontWarning(
            city="paris", date="2026-04-08",
            warning_type="MODEL_SPREAD", severity="HIGH",
            description="test", model_spread=9.0
        )
        self.assertEqual(w.severity, "HIGH")
        self.assertEqual(w.model_spread, 9.0)


class TestRiskScoring(unittest.TestCase):
    """Risk scoring integrates distance, model spread, front warnings, and price."""

    def setUp(self):
        self.scanner = EdgeHarvestScanner()

    def test_low_risk_far_from_forecast(self):
        tier, score, _ = self.scanner.calculate_risk(
            bands_away=5, degrees_away=10.0, model_spread=1.0,
            front_warnings=[], no_price=0.98,
        )
        self.assertEqual(tier, "LOW")
        self.assertLessEqual(score, 3)

    def test_high_risk_close_with_spread(self):
        tier, score, _ = self.scanner.calculate_risk(
            bands_away=2, degrees_away=4.0, model_spread=7.0,
            front_warnings=[
                FrontWarning("nyc", "2026-04-08", "MODEL_SPREAD", "HIGH", "test")
            ],
            no_price=0.90,
        )
        self.assertEqual(tier, "HIGH")
        self.assertGreaterEqual(score, 7)

    def test_front_warning_adds_to_score(self):
        _, score_no_warn, _ = self.scanner.calculate_risk(
            bands_away=3, degrees_away=6.0, model_spread=2.0,
            front_warnings=[], no_price=0.97,
        )
        _, score_with_warn, _ = self.scanner.calculate_risk(
            bands_away=3, degrees_away=6.0, model_spread=2.0,
            front_warnings=[
                FrontWarning("nyc", "2026-04-08", "MODEL_SPREAD", "MEDIUM", "test")
            ],
            no_price=0.97,
        )
        self.assertGreater(score_with_warn, score_no_warn)

    def test_score_capped_at_10(self):
        _, score, _ = self.scanner.calculate_risk(
            bands_away=2, degrees_away=4.0, model_spread=8.0,
            front_warnings=[
                FrontWarning("nyc", "2026-04-08", "MODEL_SPREAD", "HIGH", "big"),
                FrontWarning("nyc", "2026-04-08", "LOW_CONFIDENCE", "HIGH", "bad"),
            ],
            no_price=0.85,
        )
        self.assertLessEqual(score, 10)


class TestOpportunityBackwardsCompat(unittest.TestCase):
    """The `bucket` property alias must work for auto_harvest compatibility."""

    def _make_opp(self, bucket_str="30-31°F"):
        return EdgeHarvestOpportunity(
            city="nyc", target_date="2026-04-08",
            bucket_low=30.0, bucket_high=31.0, bucket_str=bucket_str,
            yes_price=0.02, no_price=0.98, potential_return_pct=2.04,
            forecast_temp=50.0, bands_away=9, degrees_away=19.0,
            risk_tier="LOW", risk_score=1, risk_factors=[],
            model_spread=1.0, ecmwf_temp=None, gfs_temp=None, nws_temp=None,
            front_warning=None, front_warning_reason=None,
            threshold_type="CONSERVATIVE",
            clob_token_ids=(None, None), market_url="", liquidity=100,
            hours_remaining=24,
        )

    def test_bucket_property_returns_bucket_str(self):
        opp = self._make_opp("≤35°F")
        self.assertEqual(opp.bucket, "≤35°F")
        self.assertEqual(opp.bucket, opp.bucket_str)

    def test_bucket_property_celsius(self):
        opp = self._make_opp("7-8°C")
        self.assertEqual(opp.bucket, "7-8°C")

    def test_front_warning_none_is_falsy(self):
        opp = self._make_opp()
        self.assertFalse(opp.front_warning)

    def test_front_warning_object_has_severity(self):
        opp = self._make_opp()
        opp.front_warning = FrontWarning("nyc", "2026-04-08", "MODEL_SPREAD", "HIGH", "test")
        self.assertEqual(opp.front_warning.severity, "HIGH")


class TestGetSingleton(unittest.TestCase):
    def test_get_edge_harvest_scanner_returns_instance(self):
        s = get_edge_harvest_scanner()
        self.assertIsInstance(s, EdgeHarvestScanner)


if __name__ == "__main__":
    unittest.main()
