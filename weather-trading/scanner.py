"""
Polymarket Weather Market Scanner

Fetches and parses weather temperature markets from Polymarket.
"""

import json
import logging
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from config import WEATHER_CITIES, API_CONFIG, ACTIVE_CITIES

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
    clob_token_ids: tuple = (None, None)  # (yes_token_id, no_token_id)
    market_type: str = "high"  # "high" or "low" — which daily extreme the market resolves on (PD-321 R3)
    accepting_orders: bool = True  # Codex R3/R5 tradability — guards executor against orders to closed markets

    @property
    def hours_remaining(self) -> float:
        """Hours until market resolution."""
        now = datetime.now(timezone.utc)
        delta = self.end_time - now
        return max(0, delta.total_seconds() / 3600)


def _parse_clob_token_ids(market: Dict) -> tuple:
    """Extract YES and NO token IDs from market data."""
    raw = market.get("clobTokenIds", "[]")
    try:
        if isinstance(raw, str):
            tokens = json.loads(raw)
        else:
            tokens = raw
        if isinstance(tokens, list) and len(tokens) >= 2:
            return (str(tokens[0]), str(tokens[1]))
    except:
        pass
    return (None, None)


class WeatherMarketScanner:
    """
    Scans Polymarket for weather temperature bracket markets.
    """
    
    # Patterns to extract temperature buckets from questions
    BUCKET_PATTERNS = [
        # "between 42-43°F" or "between 42 and 43°F"
        r"between\s+(-?\d+)(?:\s*-\s*|\s+and\s+)(-?\d+)\s*°?\s*([FC])",
        # "42-43°F" standalone
        r"(-?\d+)\s*-\s*(-?\d+)\s*°?\s*([FC])",
        # "42°F or below" / "above 42°F"
        r"(-?\d+)\s*°?\s*([FC])\s+or\s+(below|above)",
        # Specific temp "exactly 42°F"
        r"(?:exactly\s+)?(-?\d+)\s*°?\s*([FC])",
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
        "paris": "paris",
        "ankara": "ankara",
        "madrid": "madrid",
        "miami": "miami",
        "denver": "denver",
        "tokyo": "tokyo",
        "berlin": "berlin",
        "sydney": "sydney",
        "mexico city": "mexico_city",
        "cdmx": "mexico_city",
        # PD-321 G5 rotation expansion 2026-05-26
        "amsterdam": "amsterdam",
        "austin": "austin",
        "beijing": "beijing",
        "busan": "busan",
        "cape town": "cape_town",
        "chengdu": "chengdu",
        "chongqing": "chongqing",
        "guangzhou": "guangzhou",
        "helsinki": "helsinki",
        "houston": "houston",
        "istanbul": "istanbul",
        "jakarta": "jakarta",
        "jeddah": "jeddah",
        "karachi": "karachi",
        "kuala lumpur": "kuala_lumpur",
        "lucknow": "lucknow",
        "manila": "manila",
        "milan": "milan",
        "moscow": "moscow",
        "munich": "munich",
        "panama city": "panama_city",
        "qingdao": "qingdao",
        "san francisco": "san_francisco",
        "sf": "san_francisco",
        "são paulo": "sao_paulo",
        "sao paulo": "sao_paulo",
        "shenzhen": "shenzhen",
        "singapore": "singapore",
        "warsaw": "warsaw",
        "wellington": "wellington",
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
        "chicago": "chicago",
        "los_angeles": "los-angeles",
        "paris": "paris",
        "ankara": "ankara",
        "madrid": "madrid",
        "miami": "miami",
        "denver": "denver",
        "tokyo": "tokyo",
        "berlin": "berlin",
        "sydney": "sydney",
        "mexico_city": "mexico-city",
        # PD-321 G5 rotation expansion 2026-05-26
        "amsterdam": "amsterdam",
        "austin": "austin",
        "beijing": "beijing",
        "busan": "busan",
        "cape_town": "cape-town",
        "chengdu": "chengdu",
        "chongqing": "chongqing",
        "guangzhou": "guangzhou",
        "helsinki": "helsinki",
        "houston": "houston",
        "istanbul": "istanbul",
        "jakarta": "jakarta",
        "jeddah": "jeddah",
        "karachi": "karachi",
        "kuala_lumpur": "kuala-lumpur",
        "lucknow": "lucknow",
        "manila": "manila",
        "milan": "milan",
        "moscow": "moscow",
        "munich": "munich",
        "panama_city": "panama-city",
        "qingdao": "qingdao",
        "san_francisco": "san-francisco",
        "sao_paulo": "sao-paulo",
        "shenzhen": "shenzhen",
        "singapore": "singapore",
        "warsaw": "warsaw",
        "wellington": "wellington",
    }
    
    def __init__(self, request_delay: float = 0.1, request_timeout: float = 30.0):
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
        """
        Extract city key from market question.

        Uses word-boundary regex match (not substring `in`) — the substring form
        had a critical collision where the 2-letter alias `"la"` matched inside
        words like `Manila`, `Kuala Lumpur`, and `Lahore`, mis-routing those
        markets to los_angeles with Manila's clob_token_ids attached. Operator
        observed real-money loss 2026-05-21 on Manila NO trades that were
        labeled LA in the dashboard.

        Word-boundary match requires the alias to be a complete token,
        not a substring fragment.
        """
        question_lower = question.lower()
        for alias, city_key in self.CITY_ALIASES.items():
            # \b respects word boundaries — "la" no longer matches inside "Manila"
            if re.search(r'\b' + re.escape(alias) + r'\b', question_lower):
                return city_key
        return None
    
    def _extract_bucket(self, question: str) -> Optional[Tuple[float, float, str]]:
        """
        Extract temperature bucket from market question.

        Returns: (low, high, unit) or None
        """
        # Detect unit before stripping (default F)
        unit = "C" if re.search(r'°\s*C\b', question, re.IGNORECASE) else "F"
        question = question.replace("°", "")  # Normalize

        # Try "X or below" pattern
        below_match = re.search(r'be\s+(-?\d+)\s*[FC]?\s+or\s+below', question, re.IGNORECASE)
        if below_match:
            temp = float(below_match.group(1))
            return (float('-inf'), temp, unit)

        # Try "X or above/higher" pattern
        above_match = re.search(r'be\s+(-?\d+)\s*[FC]?\s+or\s+(?:above|higher)', question, re.IGNORECASE)
        if above_match:
            temp = float(above_match.group(1))
            return (temp, float('inf'), unit)

        # Try single-integer pattern "be N°C on …" (PD-321 R2)
        # Polymarket post-redesign uses bare integers for 1°C C-cities (e.g. "be 22C on May 19?")
        # and could plausibly emit "be 86F on …" if 1°F single-integers ever appear.
        # Returns a degenerate bucket (N, N, unit) so calculate_bands_away treats it
        # as a 1-wide bucket centered at N. PD-321 R4 round 3: capture unit IN the
        # regex so a bare "22C" without degree sign still routes as °C (the
        # outer unit-detect requires ° presence).
        single_match = re.search(r'\bbe\s+(-?\d+)\s*([FC])\s+on\b', question, re.IGNORECASE)
        if single_match:
            temp = float(single_match.group(1))
            matched_unit = single_match.group(2).upper()
            return (temp, temp, matched_unit)

        # Try "between X and Y" pattern.
        # Codex R5 fix: capture the unit from the question text rather than
        # relying on the pre-detected `unit` variable, which requires a `°`
        # to disambiguate C. Forms like "between 8 and 9C" or "between 8C
        # and 9C" (no degree sign) were silently parsed as Fahrenheit.
        between_match = re.search(r'between\s+(-?\d+)\s*([FC])?\s+and\s+(-?\d+)\s*([FC])?', question, re.IGNORECASE)
        if between_match:
            low = float(between_match.group(1))
            high = float(between_match.group(3))
            matched_unit = (between_match.group(4) or between_match.group(2) or '').upper()
            return (min(low, high), max(low, high), matched_unit or unit)

        # Try range pattern "X-Y°F" or "X-YF" (Codex R5 fix: capture unit).
        range_match = re.search(r'be\s+(?:between\s+)?(-?\d+)-(-?\d+)\s*([FC])?', question, re.IGNORECASE)
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            matched_unit = (range_match.group(3) or '').upper()
            return (min(low, high), max(low, high), matched_unit or unit)

        return None
    
    def _extract_date(self, question: str, end_time: datetime) -> str:
        """
        Extract target date from question or fall back to end_time.
        
        Handles patterns like "on January 15" or "Jan 15th"
        """
        # Delegate to _try_extract_date; fall back to end_time only when nothing
        # in the text actually parsed (PD-321 R4 Codex round 3 finding: previous
        # "equal-to-endDate" fallback could overwrite a correct slug-derived
        # date with a year-rolled question parse around UTC-midnight same-day).
        parsed = self._try_extract_date(question)
        if parsed is not None:
            return parsed
        return end_time.strftime("%Y-%m-%d")

    def _try_extract_date(self, text: str) -> Optional[str]:
        """
        Parse a date out of free-form text. Returns YYYY-MM-DD or None.

        Accepts slug-form ("may-19-2026") and question-form ("on May 19, 2026"
        or just "on May 19"). Trailing 4-digit year is honored when present;
        otherwise year is inferred from now() with a roll-forward heuristic
        for past-this-year dates.
        """
        months = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
            'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
            'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
            'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
            'december': 12, 'dec': 12,
        }
        m = re.search(
            r"(?:on\s+)?(" + "|".join(months.keys()) + r")[-\s]+(\d{1,2})(?:st|nd|rd|th)?"
            r"(?:[-\s,]+(\d{4}))?",
            text.lower(),
        )
        if not m:
            return None
        month_name = m.group(1)
        day = int(m.group(2))
        year_str = m.group(3)
        month = months[month_name]

        if year_str:
            return f"{int(year_str)}-{month:02d}-{day:02d}"

        now = datetime.now(timezone.utc)
        year = now.year
        target = datetime(year, month, day, tzinfo=timezone.utc)
        if target < now:
            year += 1
        return f"{year}-{month:02d}-{day:02d}"
    
    def _generate_event_slugs(self, cities: List[str], days_ahead: int = 2,
                              skip_triples: Optional[set] = None) -> List[tuple]:
        """
        Generate expected event slugs for temperature markets.

        Polymarket uses slugs like: highest-temperature-in-nyc-on-january-14.
        Returns 4-tuples `(city_key, target_date, market_type, slug)`.

        Codex perf follow-up: when `skip_triples` is supplied (a set of
        `(city_key, target_date, market_type)` triples already covered by the
        tag-feed), those triples are skipped at generation time — we issue
        only the slug probes that tag-feed did NOT find. With a fully
        warm tag-feed, this reduces ~282 probes (47 cities × 3 days × 2
        flavors) to whatever's actually missing (often zero).
        """
        slugs = []
        skip = skip_triples or set()
        now = datetime.now(timezone.utc)
        months_lower = ['', 'january', 'february', 'march', 'april', 'may', 'june',
                        'july', 'august', 'september', 'october', 'november', 'december']

        for city_key in cities:
            slug_city = self.CITY_SLUG_NAMES.get(city_key, city_key.replace('_', '-'))
            for day_offset in range(days_ahead + 1):
                target = now + timedelta(days=day_offset)
                month_name = months_lower[target.month]
                day = target.day
                target_date = target.strftime("%Y-%m-%d")
                # PD-321 R3: emit both highest- and lowest-temperature flavors.
                for prefix, market_type in (("highest-temperature-in", "high"),
                                            ("lowest-temperature-in", "low")):
                    if (city_key, target_date, market_type) in skip:
                        continue
                    slug = f"{prefix}-{slug_city}-on-{month_name}-{day}"
                    slugs.append((city_key, target_date, market_type, slug))

        return slugs
    
    def _fetch_event_by_slug(self, slug: str) -> Optional[Dict]:
        """Fetch event data by slug. Tries numeric suffixes if base slug returns stale data."""
        now = datetime.now(timezone.utc)
        
        def fetch_single(s: str) -> Optional[Dict]:
            url = f"https://gamma-api.polymarket.com/events?slug={s}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read())
                    return data[0] if data else None
            except Exception:
                return None
        
        def is_current(event: Optional[Dict]) -> bool:
            """Check if event has ANY market still active/tradeable."""
            if not event:
                return False
            markets = event.get('markets', [])
            if not markets:
                return False
            # Use active/acceptingOrders fields — endDate is resolution time, not trading cutoff
            for m in markets:
                if m.get('active') and not m.get('closed', False):
                    return True
                if m.get('acceptingOrders'):
                    return True
                # Fallback: endDate check for APIs that don't return active/closed fields
                end_str = m.get('endDate', '')
                try:
                    end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                    if end_time > now:
                        return True
                except (ValueError, TypeError):
                    continue
            return False
        
        # PD-321 R5: only the year-suffixed slug ({slug}-YYYY). Polymarket's
        # post-redesign weather product always emits year-suffixed slugs; the
        # bare-slug fallback was returning Polymarket's most-recent-matching
        # event which could be year-prior stale data. R4 tag-feed is now the
        # primary discovery path; this slug fetcher is defense-in-depth only.
        current_year = now.year
        event = fetch_single(f"{slug}-{current_year}")
        if is_current(event):
            return event

        return None
    
    def _fetch_slug_worker(self, args: tuple) -> List[dict]:
        """Worker for parallel slug fetching. Returns list of (city_key, target_date, market_type, slug, event)."""
        city_key, target_date, market_type, slug = args
        event = self._fetch_event_by_slug(slug)
        if event and event.get('markets'):
            return [(city_key, target_date, market_type, slug, event)]
        return []

    def fetch_temperature_markets_by_slug(self, cities: List[str],
                                          skip_triples: Optional[set] = None) -> List[WeatherMarket]:
        """
        Fetch temperature markets by generating and checking slugs directly.

        Uses ThreadPoolExecutor for parallel fetching (19 cities would be
        too slow sequentially).
        """
        markets = []
        now = datetime.now(timezone.utc)
        slugs = self._generate_event_slugs(cities, skip_triples=skip_triples)

        if skip_triples is not None:
            total = len(cities) * 3 * 2  # cities × (days_ahead+1) × {high, low}
            logger.info(f"Targeted slug discovery: {len(slugs)}/{total} probes (skipped {total - len(slugs)} triples already in tag-feed)")
        else:
            logger.info(f"Checking {len(slugs)} potential temperature event slugs (parallel)...")

        # Parallel fetch -- up to 10 concurrent requests to avoid hammering the API
        found_events = []
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(self._fetch_slug_worker, s): s for s in slugs}
            for future in as_completed(futures):
                try:
                    results = future.result()
                    found_events.extend(results)
                except Exception as e:
                    logger.debug(f"Slug fetch error: {e}")

        logger.info(f"Parallel slug discovery found {len(found_events)} events")

        for city_key, target_date, market_type, slug, event in found_events:
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

                    # Skip only if truly settled — past resolution AND order book closed.
                    # Polymarket keeps acceptingOrders=True on many markets for hours past
                    # endDate (operator-observed 2026-05-21: NYC May 21 markets had
                    # endDate=12:00Z but 7/11 were still acceptingOrders at 13:47Z).
                    # Earlier "end_time < now: continue" was dropping today's tradeable markets.
                    if end_time < now and not market.get('acceptingOrders', False):
                        continue

                    # Get prices. Codex R5: parse outcomePrices[1] for NO independently
                    # — Polymarket's quotes can diverge from `1 - yes_price` due to
                    # spread / market-maker drift / fees layered on the resolution side.
                    prices_str = market.get('outcomePrices', '[0.5]')
                    try:
                        prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                        yes_price = float(prices[0])
                    except (ValueError, IndexError, TypeError, json.JSONDecodeError):
                        yes_price = 0.5
                    try:
                        no_price = float(prices[1]) if len(prices) > 1 else 1.0 - yes_price
                    except (ValueError, TypeError, IndexError):
                        no_price = 1.0 - yes_price

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
                        no_price=no_price,
                        liquidity=float(market.get('liquidity', 0)),
                        volume_24h=float(market.get('volume24hr', 0)),
                        end_time=end_time,
                        market_url=f"https://polymarket.com/event/{slug}",
                        clob_token_ids=_parse_clob_token_ids(market),
                        accepting_orders=bool(market.get('acceptingOrders', True)),
                        # market_type derived from the SLUG (canonical source), not
                        # the question — defends against bucket-only question text
                        # (PD-321 R4 Codex round 2 finding).
                        market_type=("low" if "lowest" in slug.lower() else "high"),
                    )

                    markets.append(wm)

                except (ValueError, KeyError, TypeError) as e:
                    continue

        return markets
    
    def fetch_via_daily_temperature_tag(
        self,
        city_filter: Optional[List[str]] = None,
    ) -> List[WeatherMarket]:
        """
        Bulk discovery via Polymarket's daily-temperature tag (PD-321 R4).

        Reads the tag feed once instead of probing 50+ individual slugs.
        Each event encodes city, target date, and high/low type in its
        slug/title; the market question carries only the bucket. The parser
        favors event metadata over question text for city/date/type because
        bucket-only questions are common post-redesign and would otherwise
        be mis-routed.

        Args:
            city_filter: Optional whitelist of city_keys. None = accept all
                rotation cities mappable via _extract_city. Callers from
                fetch_weather_markets pass ACTIVE_CITIES by default.

        Returns:
            list of WeatherMarket objects
        """
        url = (
            f"{API_CONFIG['polymarket_gamma_url']}/events"
            "?tag_slug=daily-temperature"
            "&order=endDate"
            "&ascending=false"
            "&limit=200"
        )
        data = self._make_request(url)
        if not data:
            logger.warning("daily-temperature tag-feed returned no events")
            return []

        markets: List[WeatherMarket] = []
        now = datetime.now(timezone.utc)

        for event in data:
            event_slug = event.get("slug", "") or ""
            event_title = event.get("title", "") or ""
            event_markets = event.get("markets", [])
            if not event_markets:
                continue

            # Event-level metadata. Slug example:
            #   highest-temperature-in-mexico-city-on-may-19-2026
            #   lowest-temperature-in-nyc-on-may-22-2026
            # Both city and high/low type live here; market questions can be
            # bucket-only and lack this info.
            slug_text = event_slug.replace("-", " ")
            event_city_key = self._extract_city(slug_text) or self._extract_city(event_title)
            event_market_type = (
                "low"
                if ("lowest" in event_slug.lower() or "lowest" in event_title.lower())
                else "high"
            )

            # Keep event if any market is tradeable OR has future resolution.
            keep_event = False
            for m in event_markets:
                if m.get("acceptingOrders"):
                    keep_event = True
                    break
                end_str = m.get("endDate", "")
                try:
                    et = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    if et > now:
                        keep_event = True
                        break
                except (ValueError, TypeError):
                    continue
            if not keep_event:
                continue

            for market in event_markets:
                try:
                    question = market.get("question", "")

                    bucket = self._extract_bucket(question)
                    if not bucket:
                        continue
                    bucket_low, bucket_high, bucket_unit = bucket

                    # City: prefer event-level (slug/title), question fallback.
                    city_key = event_city_key or self._extract_city(question)
                    if not city_key:
                        continue
                    if city_filter is not None and city_key not in city_filter:
                        continue

                    end_str = market.get("endDate") or market.get("end_date_iso", "")
                    try:
                        end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        end_time = now + timedelta(days=1)

                    # Skip truly-settled markets (post-resolution AND not tradeable).
                    if end_time < now and not market.get("acceptingOrders", False):
                        continue

                    # Target date: try slug first (carries explicit YYYY),
                    # then question, then fall back to endDate. Uses None-
                    # returning helper so a slug date that happens to equal
                    # endDate isn't mistaken for parse failure (Codex R3).
                    target_date = (
                        self._try_extract_date(slug_text)
                        or self._try_extract_date(question)
                        or end_time.strftime("%Y-%m-%d")
                    )

                    # Market type: event slug/title is the canonical source.
                    # Question can override only if it explicitly says "lowest".
                    market_type = event_market_type
                    if "lowest" in question.lower():
                        market_type = "low"

                    # Codex R5: parse outcomePrices[1] for NO independently
                    prices_raw = market.get("outcomePrices", "[0.5]")
                    try:
                        prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                        yes_price = float(prices[0])
                    except (ValueError, IndexError, TypeError, json.JSONDecodeError):
                        yes_price = 0.5
                    try:
                        no_price = float(prices[1]) if len(prices) > 1 else 1.0 - yes_price
                    except (ValueError, TypeError, IndexError):
                        no_price = 1.0 - yes_price

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
                        no_price=no_price,
                        liquidity=float(market.get("liquidity", 0)),
                        volume_24h=float(market.get("volume24hr", 0)),
                        end_time=end_time,
                        market_url=f"https://polymarket.com/event/{event_slug}",
                        clob_token_ids=_parse_clob_token_ids(market),
                        market_type=market_type,
                        accepting_orders=bool(market.get("acceptingOrders", True)),
                    )
                    markets.append(wm)
                except (ValueError, KeyError, TypeError) as e:
                    logger.debug(f"Failed to parse market in tag-feed: {e}")
                    continue

        n_cities = len(set(m.city_key for m in markets))
        logger.info(
            f"daily-temperature tag-feed: {len(markets)} markets across {n_cities} cities"
        )
        return markets

    def fetch_weather_markets(self, city_filter: Optional[List[str]] = None) -> List[WeatherMarket]:
        """
        Fetch all active weather temperature markets from Polymarket.

        Discovery cascade (PD-321 R4):
          1. Bulk tag-feed via daily-temperature (Method A — preferred).
          2. Slug-by-slug × ACTIVE_CITIES supplement (Method B — always
             merged as defense-in-depth against tag omissions, parser
             misses, or one side of high/low rotation being absent).

        Markets are deduped by market_id; tag-feed entries win on collision.

        Note: city_filter currently defaults to ACTIVE_CITIES; rotation
        expansion (passing None to ingest cities outside ACTIVE_CITIES)
        requires CITY_ALIASES + WEATHER_CITIES + forecaster entries for the
        new cities. See PD-321 G5 follow-up.

        Args:
            city_filter: Optional whitelist of city_keys. Defaults to ACTIVE_CITIES.

        Returns:
            list of WeatherMarket objects.
        """
        if city_filter is None:
            city_filter = ACTIVE_CITIES

        markets: List[WeatherMarket] = []

        # Method A: bulk daily-temperature tag-feed.
        tag_markets = self.fetch_via_daily_temperature_tag(city_filter=city_filter)
        markets.extend(tag_markets)
        seen_ids = {m.market_id for m in markets if m.market_id}

        # Method B: slug-by-slug supplement. Codex perf optimization: skip
        # (city, date, market_type) triples already covered by tag-feed —
        # we only probe slugs for triples NOT in Method A's output. With a
        # warm tag-feed this typically drops 282 probes to <20.
        seen_triples = {(m.city_key, m.target_date, m.market_type) for m in tag_markets}
        logger.info("Running targeted slug-based discovery as supplement...")
        slug_markets = self.fetch_temperature_markets_by_slug(city_filter, skip_triples=seen_triples)
        added = 0
        for m in slug_markets:
            if m.market_id and m.market_id in seen_ids:
                continue
            markets.append(m)
            if m.market_id:
                seen_ids.add(m.market_id)
            added += 1
        if added:
            logger.info(f"Slug discovery added {added} markets not in tag-feed")

        cities_found = sorted({m.city_key for m in markets})
        logger.info(
            f"Found {len(markets)} weather markets "
            f"({len(tag_markets)} tag + {added} slug-only) "
            f"across {len(cities_found)} cities"
        )
        return markets
    
    def fetch_markets_from_browser(self, city_filter: List[str] = None) -> List[WeatherMarket]:
        """
        Fetch markets using Playwright browser scraping.
        
        This is currently the most reliable method since Graph APIs are deprecated.
        Requires: pip install playwright && playwright install chromium
        """
        try:
            from browser_scraper import get_scraped_markets
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
                clob_token_ids=getattr(m, 'clob_token_ids', (None, None)),
            )
            
            markets.append(wm)
            logger.info(f"Found market via browser: {m.city_key} {m.question} @ {m.yes_price:.2f}")
        
        return markets
    
    def fetch_markets_from_graph(self, city_filter: List[str] = None) -> List[WeatherMarket]:
        """
        Fetch markets using The Graph with known condition IDs.
        
        This is the most reliable method - uses on-chain data.
        """
        try:
            from graph_client import get_graph_client
            from market_ids import get_markets_for_today_tomorrow, TemperatureMarketInfo
        except ImportError as e:
            logger.debug(f"Graph client not available: {e}")
            return []
        
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
