"""
Polymarket Weather Market Scanner

Fetches and parses weather temperature markets from Polymarket.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from .config import WEATHER_CITIES, API_CONFIG, ACTIVE_CITIES

logger = logging.getLogger(__name__)


@dataclass
class WeatherMarket:
    """Represents a Polymarket weather temperature market."""
    market_id: str
    question: str
    city: str
    city_key: str
    target_date: str  # YYYY-MM-DD
    bucket_low: float
    bucket_high: float
    bucket_unit: str  # "F" or "C"
    yes_price: float
    no_price: float
    liquidity: float
    volume_24h: float
    end_time: datetime
    market_url: str
    
    @property
    def hours_remaining(self) -> float:
        """Hours until market resolution."""
        now = datetime.now(timezone.utc)
        delta = self.end_time - now
        return max(0, delta.total_seconds() / 3600)


class WeatherMarketScanner:
    """
    Scans Polymarket for weather temperature bracket markets.
    """
    
    # Patterns to extract temperature buckets from questions
    BUCKET_PATTERNS = [
        # "between 42-43°F" or "between 42 and 43°F"
        r"between\s+(\d+)(?:\s*-\s*|\s+and\s+)(\d+)\s*°?\s*([FC])",
        # "42-43°F" standalone
        r"(\d+)\s*-\s*(\d+)\s*°?\s*([FC])",
        # "42°F or below" / "above 42°F"
        r"(\d+)\s*°?\s*([FC])\s+or\s+(below|above)",
        # Specific temp "exactly 42°F"
        r"(?:exactly\s+)?(\d+)\s*°?\s*([FC])",
    ]
    
    # City name variations in questions
    CITY_ALIASES = {
        "new york": "nyc",
        "nyc": "nyc",
        "new york city": "nyc",
        "london": "london",
        "buenos aires": "buenos_aires",
        "atlanta": "atlanta",
        "dallas": "dallas",
        "seattle": "seattle",
        "chicago": "chicago",
        "los angeles": "los_angeles",
        "la": "los_angeles",
        "toronto": "toronto",
        "seoul": "seoul",
    }
    
    # City name to use in event slugs
    CITY_SLUG_NAMES = {
        "nyc": "nyc",
        "london": "london",
        "buenos_aires": "buenos-aires",
        "atlanta": "atlanta",
        "dallas": "dallas",
        "seattle": "seattle",
        "toronto": "toronto",
        "seoul": "seoul",
    }
    
    def __init__(self, request_delay: float = 0.5, request_timeout: float = 10.0):
        self.request_delay = request_delay
        self.timeout = request_timeout
        self._last_request = 0.0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request = time.time()
    
    def _make_request(self, url: str) -> Optional[Dict]:
        """Make HTTP GET request and parse JSON response."""
        self._rate_limit()
        try:
            req = Request(url)
            req.add_header("User-Agent", "WeatherTradingBot/1.0")
            
            with urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except (URLError, HTTPError, json.JSONDecodeError) as e:
            logger.debug(f"Request failed for {url}: {e}")
            return None
    
    def _extract_city(self, question: str) -> Optional[str]:
        """Extract city key from market question."""
        question_lower = question.lower()
        for alias, city_key in self.CITY_ALIASES.items():
            if alias in question_lower:
                return city_key
        return None
    
    def _extract_bucket(self, question: str) -> Optional[Tuple[float, float, str]]:
        """
        Extract temperature bucket from market question.
        
        Returns: (low, high, unit) or None
        """
        question = question.replace("°", "")  # Normalize
        
        # Try "X or below" pattern
        below_match = re.search(r"(\d+)\s*([FC])\s+or\s+below", question, re.I)
        if below_match:
            temp = float(below_match.group(1))
            unit = below_match.group(2).upper()
            return (float('-inf'), temp, unit)
        
        # Try "above X" or "X or above" pattern
        above_match = re.search(r"(?:above\s+)?(\d+)\s*([FC])\s+or\s+above|above\s+(\d+)\s*([FC])", question, re.I)
        if above_match:
            temp = float(above_match.group(1) or above_match.group(3))
            unit = (above_match.group(2) or above_match.group(4)).upper()
            return (temp, float('inf'), unit)
        
        # Try range pattern "X-Y" or "between X and Y"
        range_match = re.search(r"(\d+)\s*(?:-|to|and)\s*(\d+)\s*([FC])", question, re.I)
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            unit = range_match.group(3).upper()
            return (min(low, high), max(low, high), unit)
        
        return None
    
    def _extract_date(self, question: str, end_time: datetime) -> str:
        """
        Extract target date from question or fall back to end_time.
        
        Handles patterns like "on January 15" or "Jan 15th"
        """
        months = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
            'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
            'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
            'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
        
        # Pattern: "on January 15" or "Jan 15th"
        date_match = re.search(
            r"(?:on\s+)?(" + "|".join(months.keys()) + r")\s+(\d{1,2})(?:st|nd|rd|th)?",
            question.lower()
        )
        
        if date_match:
            month_name = date_match.group(1)
            day = int(date_match.group(2))
            month = months[month_name]
            
            # Determine year (assume current or next year)
            now = datetime.now(timezone.utc)
            year = now.year
            target = datetime(year, month, day, tzinfo=timezone.utc)
            if target < now:
                year += 1
            
            return f"{year}-{month:02d}-{day:02d}"
        
        # Fall back to end_time date
        return end_time.strftime("%Y-%m-%d")
    
    def _generate_event_slugs(self, cities: List[str], days_ahead: int = 3) -> List[str]:
        """
        Generate expected event slugs for temperature markets.
        
        Polymarket uses slugs like: highest-temperature-in-nyc-on-january-14
        """
        slugs = []
        now = datetime.now(timezone.utc)
        months_lower = ['', 'january', 'february', 'march', 'april', 'may', 'june',
                        'july', 'august', 'september', 'october', 'november', 'december']
        
        for city_key in cities:
            slug_city = self.CITY_SLUG_NAMES.get(city_key, city_key.replace('_', '-'))
            for day_offset in range(days_ahead + 1):
                target = now + timedelta(days=day_offset)
                month_name = months_lower[target.month]
                day = target.day
                slug = f"highest-temperature-in-{slug_city}-on-{month_name}-{day}"
                slugs.append((city_key, target.strftime("%Y-%m-%d"), slug))
        
        return slugs
    
    def _fetch_event_by_slug(self, slug: str) -> Optional[Dict]:
        """Fetch a single event by its slug."""
        url = f"{API_CONFIG['polymarket_gamma_url']}/events/{slug}"
        return self._make_request(url)
    
    def fetch_temperature_markets_by_slug(self, cities: List[str]) -> List[WeatherMarket]:
        """
        Fetch temperature markets by generating and checking slugs directly.
        
        This is a fallback when the standard search doesn't work.
        """
        markets = []
        now = datetime.now(timezone.utc)
        slugs = self._generate_event_slugs(cities)
        
        logger.info(f"Checking {len(slugs)} potential temperature event slugs...")
        
        for city_key, target_date, slug in slugs:
            event = self._fetch_event_by_slug(slug)
            if not event or not event.get('markets'):
                logger.debug(f"No event found for slug: {slug}")
                continue
            
            logger.info(f"Found event: {event.get('title', slug)}")
            
            for market in event.get('markets', []):
                try:
                    question = market.get('question', '')
                    
                    # Extract bucket
                    bucket = self._extract_bucket(question)
                    if not bucket:
                        continue
                    
                    bucket_low, bucket_high, bucket_unit = bucket
                    
                    # Parse end time
                    end_str = market.get('endDate') or market.get('end_date_iso', '')
                    try:
                        end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    except ValueError:
                        end_time = now + timedelta(days=1)  # Default
                    
                    if end_time < now:
                        continue
                    
                    # Get prices
                    prices_str = market.get('outcomePrices', '[0.5]')
                    try:
                        yes_price = float(prices_str.strip('[]').split(',')[0])
                    except:
                        yes_price = 0.5
                    
                    city_info = WEATHER_CITIES.get(city_key, {})
                    
                    wm = WeatherMarket(
                        market_id=market.get('id', ''),
                        question=question,
                        city=city_info.get('name', city_key),
                        city_key=city_key,
                        target_date=target_date,
                        bucket_low=bucket_low,
                        bucket_high=bucket_high,
                        bucket_unit=bucket_unit,
                        yes_price=yes_price,
                        no_price=1 - yes_price,
                        liquidity=float(market.get('liquidity', 0)),
                        volume_24h=float(market.get('volume24hr', 0)),
                        end_time=end_time,
                        market_url=f"https://polymarket.com/event/{slug}",
                    )
                    
                    markets.append(wm)
                    
                except (ValueError, KeyError, TypeError) as e:
                    continue
        
        return markets
    
    def fetch_weather_markets(self, city_filter: List[str] = None) -> List[WeatherMarket]:
        """
        Fetch all active weather temperature markets from Polymarket.
        
        Tries multiple methods:
        1. Standard API tag-based search
        2. Direct slug-based fetching (fallback)
        
        Args:
            city_filter: Only return markets for these cities (default: ACTIVE_CITIES)
            
        Returns:
            List of WeatherMarket objects
        """
        if city_filter is None:
            city_filter = ACTIVE_CITIES
        
        markets = []
        now = datetime.now(timezone.utc)
        
        # Method 1: Try standard API with weather tag
        url = f"{API_CONFIG['polymarket_gamma_url']}/events?tag=weather&closed=false&limit=100"
        data = self._make_request(url)
        
        if data:
            for event in data:
                event_slug = event.get("slug", "")
                event_markets = event.get("markets", [])
                
                for market in event_markets:
                    try:
                        question = market.get("question", "")
                        
                        # Only process temperature markets
                        if not any(word in question.lower() for word in ['temperature', '°f', '°c', 'degrees']):
                            continue
                        
                        city_key = self._extract_city(question)
                        if not city_key or city_key not in city_filter:
                            continue
                        
                        bucket = self._extract_bucket(question)
                        if not bucket:
                            continue
                        
                        bucket_low, bucket_high, bucket_unit = bucket
                        
                        end_str = market.get("endDate") or market.get("end_date_iso", "")
                        try:
                            end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                        except ValueError:
                            continue
                        
                        if end_time < now:
                            continue
                        
                        target_date = self._extract_date(question, end_time)
                        yes_price = float(market.get("outcomePrices", "[0.5]").strip("[]").split(",")[0])
                        
                        city_info = WEATHER_CITIES.get(city_key, {})
                        
                        wm = WeatherMarket(
                            market_id=market.get("id", ""),
                            question=question,
                            city=city_info.get("name", city_key),
                            city_key=city_key,
                            target_date=target_date,
                            bucket_low=bucket_low,
                            bucket_high=bucket_high,
                            bucket_unit=bucket_unit,
                            yes_price=yes_price,
                            no_price=1 - yes_price,
                            liquidity=float(market.get("liquidity", 0)),
                            volume_24h=float(market.get("volume24hr", 0)),
                            end_time=end_time,
                            market_url=f"https://polymarket.com/event/{event_slug}",
                        )
                        
                        markets.append(wm)
                        
                    except (ValueError, KeyError, TypeError):
                        continue
        
        # Method 2: If no markets found, try browser scraping (most reliable)
        if not markets:
            logger.info("No markets from API, trying browser scraping...")
            markets = self.fetch_markets_from_browser(city_filter)
        
        # Method 3: If still no markets, try Graph with known IDs
        if not markets:
            logger.info("No markets from browser, trying Graph-based discovery...")
            markets = self.fetch_markets_from_graph(city_filter)
        
        # Method 4: Last resort - try slug-based fetching
        if not markets:
            logger.info("No markets from Graph, trying slug-based discovery...")
            markets = self.fetch_temperature_markets_by_slug(city_filter)
        
        logger.info(f"Found {len(markets)} weather markets for cities: {city_filter}")
        return markets
    
    def fetch_markets_from_browser(self, city_filter: List[str] = None) -> List[WeatherMarket]:
        """
        Fetch markets using Playwright browser scraping.
        
        This is currently the most reliable method since Graph APIs are deprecated.
        Requires: pip install playwright && playwright install chromium
        """
        try:
            from .browser_scraper import get_scraped_markets
        except ImportError as e:
            logger.debug(f"Browser scraper not available: {e}")
            return []
        
        if city_filter is None:
            city_filter = ACTIVE_CITIES
        
        markets = []
        now = datetime.now(timezone.utc)
        
        try:
            scraped = get_scraped_markets()
        except Exception as e:
            logger.error(f"Browser scraping failed: {e}")
            return []
        
        for m in scraped:
            if m.city_key not in city_filter:
                continue
            
            city_info = WEATHER_CITIES.get(m.city_key, {})
            
            wm = WeatherMarket(
                market_id=m.condition_id,
                question=m.question,
                city=city_info.get('name', m.city_key),
                city_key=m.city_key,
                target_date=m.target_date,
                bucket_low=m.bucket_low,
                bucket_high=m.bucket_high,
                bucket_unit=m.bucket_unit,
                yes_price=m.yes_price,
                no_price=m.no_price,
                liquidity=m.liquidity,
                volume_24h=m.volume_24h,
                end_time=now + timedelta(days=1),  # Estimate
                market_url=f"https://polymarket.com/market/{m.slug}",
            )
            
            markets.append(wm)
            logger.info(f"Found market via browser: {m.city_key} {m.question} @ {m.yes_price:.2f}")
        
        return markets
    
    def fetch_markets_from_graph(self, city_filter: List[str] = None) -> List[WeatherMarket]:
        """
        Fetch markets using The Graph with known condition IDs.
        
        This is the most reliable method - uses on-chain data.
        """
        from .graph_client import get_graph_client
        from .market_ids import get_markets_for_today_tomorrow, TemperatureMarketInfo
        
        if city_filter is None:
            city_filter = ACTIVE_CITIES
        
        markets = []
        graph = get_graph_client()
        now = datetime.now(timezone.utc)
        
        for city_key in city_filter:
            # Get known market IDs for this city
            known_markets = get_markets_for_today_tomorrow(city_key)
            
            if not known_markets:
                logger.debug(f"No known markets for {city_key}")
                continue
            
            # Fetch prices from Graph for each market
            for market_info in known_markets:
                on_chain = graph.get_market_by_condition(market_info.condition_id)
                
                if not on_chain:
                    logger.debug(f"No Graph data for {market_info.condition_id}")
                    continue
                
                city_info = WEATHER_CITIES.get(city_key, {})
                
                # Build market question from metadata
                if market_info.bucket_high == float('inf'):
                    question = f"{market_info.bucket_low}°{market_info.bucket_unit} or above"
                elif market_info.bucket_low == float('-inf'):
                    question = f"{market_info.bucket_high}°{market_info.bucket_unit} or below"
                else:
                    question = f"{market_info.bucket_low}-{market_info.bucket_high}°{market_info.bucket_unit}"
                
                wm = WeatherMarket(
                    market_id=market_info.condition_id,
                    question=question,
                    city=city_info.get('name', city_key),
                    city_key=city_key,
                    target_date=market_info.target_date,
                    bucket_low=market_info.bucket_low,
                    bucket_high=market_info.bucket_high,
                    bucket_unit=market_info.bucket_unit,
                    yes_price=on_chain.yes_price,
                    no_price=on_chain.no_price,
                    liquidity=on_chain.liquidity,
                    volume_24h=on_chain.volume,
                    end_time=now + timedelta(days=1),  # Estimate
                    market_url=f"https://polymarket.com/market/{market_info.slug}",
                )
                
                markets.append(wm)
                logger.info(f"Found market via Graph: {city_key} {question} @ {on_chain.yes_price:.2f}")
        
        return markets


# Module-level singleton
_scanner: Optional[WeatherMarketScanner] = None

def get_scanner() -> WeatherMarketScanner:
    """Get or create the singleton scanner instance."""
    global _scanner
    if _scanner is None:
        _scanner = WeatherMarketScanner()
    return _scanner
