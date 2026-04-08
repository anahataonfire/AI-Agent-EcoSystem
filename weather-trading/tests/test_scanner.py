"""
Regression tests for scanner.py and browser_scraper.py.
Covers: city alias resolution, bucket extraction, date extraction, slug generation.

PD-144 R5
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner import WeatherMarketScanner
from browser_scraper import parse_city_from_title, parse_date_from_title, parse_bucket_from_question
from config import ACTIVE_CITIES


class TestCityAliases(unittest.TestCase):
    """All 19 active cities must be discoverable from market questions."""

    def setUp(self):
        self.scanner = WeatherMarketScanner()

    def test_all_active_cities_have_aliases(self):
        """Every ACTIVE_CITIES entry must be a value in CITY_ALIASES."""
        alias_values = set(self.scanner.CITY_ALIASES.values())
        for city in ACTIVE_CITIES:
            self.assertIn(city, alias_values, f"{city} has no alias mapping")

    def test_all_active_cities_have_slugs(self):
        """Every ACTIVE_CITIES entry must have a slug name."""
        for city in ACTIVE_CITIES:
            self.assertIn(city, self.scanner.CITY_SLUG_NAMES, f"{city} has no slug")

    def test_us_city_aliases(self):
        self.assertEqual(self.scanner._extract_city("temperature in NYC"), "nyc")
        self.assertEqual(self.scanner._extract_city("temperature in New York"), "nyc")
        self.assertEqual(self.scanner._extract_city("temperature in Chicago"), "chicago")
        self.assertEqual(self.scanner._extract_city("temperature in Dallas"), "dallas")
        self.assertEqual(self.scanner._extract_city("temperature in Miami"), "miami")
        self.assertEqual(self.scanner._extract_city("temperature in Denver"), "denver")

    def test_international_city_aliases(self):
        self.assertEqual(self.scanner._extract_city("temperature in Paris"), "paris")
        self.assertEqual(self.scanner._extract_city("temperature in Ankara"), "ankara")
        self.assertEqual(self.scanner._extract_city("temperature in Madrid"), "madrid")
        self.assertEqual(self.scanner._extract_city("temperature in Seoul"), "seoul")
        self.assertEqual(self.scanner._extract_city("temperature in Tokyo"), "tokyo")
        self.assertEqual(self.scanner._extract_city("temperature in Berlin"), "berlin")
        self.assertEqual(self.scanner._extract_city("temperature in Sydney"), "sydney")
        self.assertEqual(self.scanner._extract_city("temperature in Mexico City"), "mexico_city")

    def test_unknown_city_returns_none(self):
        self.assertIsNone(self.scanner._extract_city("temperature in Timbuktu"))


class TestBucketExtraction(unittest.TestCase):
    """Bucket extraction from Polymarket question strings."""

    def setUp(self):
        self.scanner = WeatherMarketScanner()

    def test_between_pattern(self):
        result = self.scanner._extract_bucket(
            "Will the highest temperature be between 42 and 43°F?"
        )
        self.assertEqual(result, (42, 43, "F"))

    def test_or_below_pattern(self):
        result = self.scanner._extract_bucket(
            "Will the highest temperature be 41°F or below?"
        )
        self.assertEqual(result, (float('-inf'), 41, "F"))

    def test_or_above_pattern(self):
        result = self.scanner._extract_bucket(
            "Will the highest temperature be 50°F or above?"
        )
        self.assertEqual(result, (50, float('inf'), "F"))

    def test_celsius_detection(self):
        result = self.scanner._extract_bucket(
            "Will the highest temperature be between 8 and 9°C?"
        )
        self.assertEqual(result, (8, 9, "C"))

    def test_celsius_or_below(self):
        result = self.scanner._extract_bucket(
            "Will the highest temperature be 5°C or below?"
        )
        self.assertEqual(result, (float('-inf'), 5, "C"))

    def test_range_pattern(self):
        result = self.scanner._extract_bucket(
            "Will the highest temperature be 42-43°F?"
        )
        self.assertEqual(result, (42, 43, "F"))


class TestBrowserScraperCityParsing(unittest.TestCase):
    """parse_city_from_title must detect all 19 active cities."""

    def test_all_active_cities_parseable(self):
        test_titles = {
            "nyc": "Highest temperature in NYC on April 8",
            "atlanta": "Highest temperature in Atlanta on April 8",
            "seattle": "Highest temperature in Seattle on April 8",
            "chicago": "Highest temperature in Chicago on April 8",
            "dallas": "Highest temperature in Dallas on April 8",
            "los_angeles": "Highest temperature in Los Angeles on April 8",
            "miami": "Highest temperature in Miami on April 8",
            "denver": "Highest temperature in Denver on April 8",
            "london": "Highest temperature in London on April 8",
            "toronto": "Highest temperature in Toronto on April 8",
            "buenos_aires": "Highest temperature in Buenos Aires on April 8",
            "paris": "Highest temperature in Paris on April 8",
            "ankara": "Highest temperature in Ankara on April 8",
            "madrid": "Highest temperature in Madrid on April 8",
            "seoul": "Highest temperature in Seoul on April 8",
            "tokyo": "Highest temperature in Tokyo on April 8",
            "berlin": "Highest temperature in Berlin on April 8",
            "sydney": "Highest temperature in Sydney on April 8",
        }
        for expected_key, title in test_titles.items():
            result = parse_city_from_title(title)
            self.assertEqual(result, expected_key, f"Failed for: {title}")

    def test_new_york_full_name(self):
        self.assertEqual(
            parse_city_from_title("Highest temperature in New York on April 8"),
            "nyc",
        )


class TestBrowserScraperBucketParsing(unittest.TestCase):
    """parse_bucket_from_question must handle F and C markets."""

    def test_fahrenheit_range(self):
        low, high, unit = parse_bucket_from_question("42-43F")
        self.assertEqual((low, high, unit), (42, 43, "F"))

    def test_celsius_range(self):
        low, high, unit = parse_bucket_from_question("8-9C")
        self.assertEqual((low, high, unit), (8, 9, "C"))

    def test_or_below(self):
        low, high, unit = parse_bucket_from_question("36C or below")
        self.assertEqual(low, float('-inf'))
        self.assertEqual(high, 36)

    def test_or_above(self):
        low, high, unit = parse_bucket_from_question("50F or above")
        self.assertEqual(low, 50)
        self.assertEqual(high, float('inf'))


class TestDateExtraction(unittest.TestCase):
    def test_standard_date(self):
        result = parse_date_from_title("Highest temperature in NYC on April 8")
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith("-04-08"))

    def test_abbreviated_month(self):
        result = parse_date_from_title("Highest temperature in NYC on Jan 15")
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith("-01-15"))


class TestSlugGeneration(unittest.TestCase):
    def test_generates_slugs_for_all_active_cities(self):
        scanner = WeatherMarketScanner()
        slugs = scanner._generate_event_slugs(ACTIVE_CITIES, days_ahead=1)
        cities_in_slugs = {s[0] for s in slugs}
        for city in ACTIVE_CITIES:
            self.assertIn(city, cities_in_slugs, f"No slugs for {city}")


if __name__ == "__main__":
    unittest.main()
