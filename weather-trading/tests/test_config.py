"""
Regression tests for config.py.
Covers: city definitions completeness, temperature conversion, active cities consistency.

PD-144 R5
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import WEATHER_CITIES, ACTIVE_CITIES, fahrenheit_to_celsius, celsius_to_fahrenheit


class TestCityDefinitions(unittest.TestCase):
    """Every active city must have a complete definition."""

    REQUIRED_FIELDS = ["name", "lat", "lon", "timezone", "resolution_source"]

    def test_all_active_cities_defined(self):
        for city in ACTIVE_CITIES:
            self.assertIn(city, WEATHER_CITIES, f"{city} in ACTIVE_CITIES but not WEATHER_CITIES")

    def test_all_cities_have_required_fields(self):
        for key, city in WEATHER_CITIES.items():
            for field in self.REQUIRED_FIELDS:
                self.assertIn(field, city, f"{key} missing field: {field}")

    def test_us_cities_have_nws(self):
        us_cities = ["nyc", "atlanta", "seattle", "chicago", "dallas",
                      "los_angeles", "miami", "denver"]
        for city in us_cities:
            info = WEATHER_CITIES[city]
            self.assertIsNotNone(info["nws_office"], f"{city} should have NWS office")
            self.assertIsNotNone(info["nws_grid"], f"{city} should have NWS grid")
            self.assertEqual(info["resolution_source"], "NWS")

    def test_international_cities_no_nws(self):
        intl_cities = ["london", "toronto", "buenos_aires", "paris", "ankara",
                        "madrid", "seoul", "tokyo", "berlin", "sydney", "mexico_city"]
        for city in intl_cities:
            info = WEATHER_CITIES[city]
            self.assertIsNone(info["nws_office"], f"{city} should NOT have NWS office")

    def test_coordinates_reasonable(self):
        for key, city in WEATHER_CITIES.items():
            self.assertGreaterEqual(city["lat"], -90, f"{key} lat < -90")
            self.assertLessEqual(city["lat"], 90, f"{key} lat > 90")
            self.assertGreaterEqual(city["lon"], -180, f"{key} lon < -180")
            self.assertLessEqual(city["lon"], 180, f"{key} lon > 180")

    def test_no_duplicate_active_cities(self):
        self.assertEqual(len(ACTIVE_CITIES), len(set(ACTIVE_CITIES)))


class TestTemperatureConversion(unittest.TestCase):
    def test_freezing_point(self):
        self.assertAlmostEqual(fahrenheit_to_celsius(32), 0.0)
        self.assertAlmostEqual(celsius_to_fahrenheit(0), 32.0)

    def test_boiling_point(self):
        self.assertAlmostEqual(fahrenheit_to_celsius(212), 100.0)
        self.assertAlmostEqual(celsius_to_fahrenheit(100), 212.0)

    def test_round_trip(self):
        for temp_f in [0, 32, 50, 72, 100, 212]:
            result = celsius_to_fahrenheit(fahrenheit_to_celsius(temp_f))
            self.assertAlmostEqual(result, temp_f, places=5)


if __name__ == "__main__":
    unittest.main()
