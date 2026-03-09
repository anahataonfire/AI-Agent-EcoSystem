import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import json
import os

# Add project root to sys.path
project_root = "/Users/adamc/Documents/001 AI Agents/AI Agent EcoSystem 2.0/weather-trading"
sys.path.append(project_root)

from scanner import WeatherMarketScanner

class TestSuffixLogic(unittest.TestCase):
    def setUp(self):
        self.scanner = WeatherMarketScanner()
        self.now = datetime.now(timezone.utc)
        self.future_date = (self.now + timedelta(days=1)).isoformat().replace('+00:00', 'Z')
        self.past_date = (self.now - timedelta(days=1)).isoformat().replace('+00:00', 'Z')

    @patch('urllib.request.urlopen')
    @patch('urllib.request.Request')
    def test_fetch_event_success_base(self, mock_request, mock_urlopen):
        """Test fetching the base slug when it's current."""
        # Setup mock response
        mock_resp = MagicMock()
        future_market = {"endDate": self.future_date}
        mock_resp.read.return_value = json.dumps([{"markets": [future_market]}]).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = self.scanner._fetch_event_by_slug("test-slug")
        
        self.assertIsNotNone(result)
        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertEqual(result['markets'][0]['endDate'], self.future_date)

    @patch('urllib.request.urlopen')
    @patch('urllib.request.Request')
    def test_fetch_event_with_year_suffix(self, mock_request, mock_urlopen):
        """Test fetching with year suffix (prioritized)."""
        stale_market = {"endDate": self.past_date}
        future_market = {"endDate": self.future_date}
        current_year = datetime.now(timezone.utc).year
        
        # Mock Request object with full_url
        def request_side_effect(url, headers=None):
            mock_req = MagicMock()
            mock_req.full_url = url
            return mock_req
        mock_request.side_effect = request_side_effect

        def urlopen_side_effect(req, timeout=None):
            url = req.full_url
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            
            if f"test-slug-{current_year}" in url:
                mock_resp.read.return_value = json.dumps([{"markets": [future_market]}]).encode()
            elif url.endswith("slug=test-slug"):
                mock_resp.read.return_value = json.dumps([{"markets": [stale_market]}]).encode()
            else:
                mock_resp.read.return_value = json.dumps([]).encode()
            return mock_resp

        mock_urlopen.side_effect = urlopen_side_effect

        result = self.scanner._fetch_event_by_slug("test-slug")
        
        self.assertIsNotNone(result)
        # Should call base (1) then year_suffix (1) = 2 calls total
        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertEqual(result['markets'][0]['endDate'], self.future_date)

    @patch('urllib.request.urlopen')
    @patch('urllib.request.Request')
    def test_fetch_event_with_numeric_suffix_fallback(self, mock_request, mock_urlopen):
        """Test fetching with numeric suffix (fallback after year)."""
        stale_market = {"endDate": self.past_date}
        future_market = {"endDate": self.future_date}
        
        def request_side_effect(url, headers=None):
            mock_req = MagicMock()
            mock_req.full_url = url
            return mock_req
        mock_request.side_effect = request_side_effect

        def urlopen_side_effect(req, timeout=None):
            url = req.full_url
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            
            if "test-slug-142" in url:
                mock_resp.read.return_value = json.dumps([{"markets": [future_market]}]).encode()
            elif "slug=test-slug" in url:
                # Base or year suffixes
                mock_resp.read.return_value = json.dumps([{"markets": [stale_market]}]).encode()
            else:
                mock_resp.read.return_value = json.dumps([]).encode()
            return mock_resp

        mock_urlopen.side_effect = urlopen_side_effect

        result = self.scanner._fetch_event_by_slug("test-slug")
        
        self.assertIsNotNone(result)
        # Calls: base (1) + 2 years (2) + suffixes (140, 141, 142) = 6 calls total
        self.assertEqual(mock_urlopen.call_count, 6)
        self.assertEqual(result['markets'][0]['endDate'], self.future_date)

    @patch('urllib.request.urlopen')
    @patch('urllib.request.Request')
    def test_fetch_event_fallback_to_base(self, mock_request, mock_urlopen):
        """Test fallback to base if all suffixes are stale/missing."""
        stale_market = {"endDate": self.past_date}
        
        def request_side_effect(url, headers=None):
            mock_req = MagicMock()
            mock_req.full_url = url
            return mock_req
        mock_request.side_effect = request_side_effect

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps([{"markets": [stale_market]}]).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = self.scanner._fetch_event_by_slug("test-slug")
        
        # It tries base (1) + 2 years (2) + 20 suffixes (20) + final fallback (1) = 24 calls
        self.assertEqual(mock_urlopen.call_count, 24)
        self.assertIsNotNone(result)
        self.assertEqual(result['markets'][0]['endDate'], self.past_date)

if __name__ == '__main__':
    unittest.main()
