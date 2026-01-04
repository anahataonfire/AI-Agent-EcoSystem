"""
Polymarket Certainty Scanner

Scans Polymarket for high-certainty markets approaching resolution.
Identifies opportunities where outcome probability is >= 95% or <= 5%.
"""

import json
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

from config.polymarket_config import POLYMARKET_CONFIG, HOURS_PER_YEAR

logger = logging.getLogger(__name__)


@dataclass
class Opportunity:
    """Represents a high-certainty trading opportunity."""
    market_id: str
    question: str
    end_time: datetime
    hours_remaining: float
    yes_price: float
    no_price: float
    liquidity: float
    volume_24h: float
    certainty_side: str  # "YES" or "NO"
    certainty_pct: float  # The higher probability (0-1)
    apr_estimate: float  # Annualized return estimate
    event_slug: str
    market_url: str
    outcomes: List[str] = field(default_factory=lambda: ["Yes", "No"])
    
    @property
    def potential_return(self) -> float:
        """Return per dollar if the certain outcome occurs."""
        if self.certainty_side == "YES":
            return (1 / self.yes_price) - 1 if self.yes_price > 0 else 0
        else:
            return (1 / self.no_price) - 1 if self.no_price > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "market_id": self.market_id,
            "question": self.question,
            "end_time": self.end_time.isoformat(),
            "hours_remaining": round(self.hours_remaining, 2),
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "liquidity": self.liquidity,
            "volume_24h": self.volume_24h,
            "certainty_side": self.certainty_side,
            "certainty_pct": round(self.certainty_pct * 100, 1),
            "apr_estimate": round(self.apr_estimate, 1),
            "potential_return_pct": round(self.potential_return * 100, 2),
            "event_slug": self.event_slug,
            "market_url": self.market_url,
            "outcomes": self.outcomes,
        }


class PolymarketClient:
    """Client for interacting with Polymarket Gamma API."""
    
    def __init__(self, base_url: str = None, request_delay: float = None):
        self.base_url = base_url or POLYMARKET_CONFIG["base_url"]
        self.request_delay = request_delay or POLYMARKET_CONFIG["request_delay_seconds"]
        self._last_request_time = 0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Any:
        """Make an HTTP GET request to the API."""
        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        if params:
            url = f"{url}?{urlencode(params)}"
        
        logger.debug(f"Requesting: {url}")
        
        try:
            req = Request(url, headers={"User-Agent": "PolymarketScanner/1.0"})
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except HTTPError as e:
            logger.error(f"HTTP Error {e.code}: {e.reason} for {url}")
            raise
        except URLError as e:
            logger.error(f"URL Error: {e.reason} for {url}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise
    
    def fetch_events(
        self, 
        closed: bool = False, 
        limit: int = None,
        tag: str = None
    ) -> List[Dict]:
        """Fetch events from the API."""
        params = {
            "closed": str(closed).lower(),
            "limit": limit or POLYMARKET_CONFIG["fetch_limit"],
        }
        if tag:
            params["tag"] = tag
        
        return self._make_request("/events", params)
    
    def fetch_series(self, slug: str) -> Optional[Dict]:
        """Fetch a specific series by slug."""
        result = self._make_request("/series", {"slug": slug})
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result if isinstance(result, dict) else None
    
    def fetch_all_series(
        self, 
        recurrence_filter: List[str] = None,
        closed: bool = False
    ) -> List[Dict]:
        """Fetch all series, optionally filtered by recurrence type."""
        params = {
            "closed": str(closed).lower(),
            "limit": 200,
        }
        series_list = self._make_request("/series", params)
        
        if recurrence_filter:
            series_list = [
                s for s in series_list 
                if s.get("recurrence") in recurrence_filter
            ]
        
        return series_list
    
    def fetch_event_by_slug(self, slug: str) -> Optional[Dict]:
        """Fetch a specific event by slug to get full market data with prices."""
        result = self._make_request("/events", {"slug": slug})
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result if isinstance(result, dict) else None


class CertaintyScanner:
    """
    Scanner for finding high-certainty Polymarket opportunities.
    
    Scans both standard events and recurring series for markets that:
    1. End within the specified time window
    2. Have probability >= min_certainty (for Yes) OR <= (1 - min_certainty) (for No)
    3. Have liquidity >= min_liquidity
    """
    
    def __init__(self, client: PolymarketClient = None):
        self.client = client or PolymarketClient()
    
    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        """Parse ISO datetime string to timezone-aware datetime."""
        if not date_str:
            return None
        try:
            # Handle 'Z' suffix and various formats
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            return datetime.fromisoformat(date_str)
        except ValueError:
            logger.warning(f"Could not parse datetime: {date_str}")
            return None
    
    def _parse_market(
        self, 
        market: Dict, 
        event_slug: str,
        now: datetime
    ) -> Optional[Opportunity]:
        """Parse a market dict into an Opportunity if it qualifies."""
        try:
            # Get end date
            end_str = market.get("endDate")
            end_time = self._parse_datetime(end_str)
            if not end_time:
                return None
            
            # Skip if already ended or closed
            if market.get("closed", False):
                return None
            
            hours_remaining = (end_time - now).total_seconds() / 3600
            if hours_remaining <= 0:
                return None
            
            # Parse prices
            prices_raw = market.get("outcomePrices", "[]")
            if isinstance(prices_raw, str):
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw
            
            if len(prices) < 2:
                return None
            
            yes_price = float(prices[0])
            no_price = float(prices[1])
            
            # Parse outcomes (Yes/No or Up/Down)
            outcomes_raw = market.get("outcomes", '["Yes", "No"]')
            if isinstance(outcomes_raw, str):
                outcomes = json.loads(outcomes_raw)
            else:
                outcomes = outcomes_raw
            
            # Get liquidity
            liquidity = float(market.get("liquidity", 0) or 0)
            volume_24h = float(market.get("volume24hr", 0) or 0)
            
            # Determine certainty side
            if yes_price >= no_price:
                certainty_side = outcomes[0] if outcomes else "YES"
                certainty_pct = yes_price
            else:
                certainty_side = outcomes[1] if len(outcomes) > 1 else "NO"
                certainty_pct = no_price
            
            # Calculate APR
            # APR = (potential_return) * (hours_per_year / hours_remaining)
            if certainty_side in ["YES", "Yes", "Up"]:
                potential_return = (1 / yes_price) - 1 if yes_price > 0 else 0
            else:
                potential_return = (1 / no_price) - 1 if no_price > 0 else 0
            
            apr = potential_return * (HOURS_PER_YEAR / hours_remaining) if hours_remaining > 0 else 0
            
            # Build market URL
            slug = market.get("slug", event_slug)
            market_url = f"https://polymarket.com/event/{slug}"
            
            return Opportunity(
                market_id=market.get("id", ""),
                question=market.get("question", ""),
                end_time=end_time,
                hours_remaining=hours_remaining,
                yes_price=yes_price,
                no_price=no_price,
                liquidity=liquidity,
                volume_24h=volume_24h,
                certainty_side=certainty_side.upper(),
                certainty_pct=certainty_pct,
                apr_estimate=apr * 100,  # Convert to percentage
                event_slug=event_slug,
                market_url=market_url,
                outcomes=outcomes,
            )
        except Exception as e:
            logger.warning(f"Error parsing market: {e}")
            return None
    
    def scan_events(
        self,
        max_hours: float,
        min_certainty: float,
        min_liquidity: float,
        now: datetime
    ) -> List[Opportunity]:
        """Scan standard events for opportunities."""
        opportunities = []
        
        # Fetch events with relevant tags
        for tag in POLYMARKET_CONFIG.get("target_tags", []):
            try:
                events = self.client.fetch_events(closed=False, tag=tag)
                logger.info(f"Fetched {len(events)} events with tag '{tag}'")
                
                for event in events:
                    event_slug = event.get("slug", "")
                    markets = event.get("markets", [])
                    
                    for market in markets:
                        opp = self._parse_market(market, event_slug, now)
                        if opp and self._qualifies(opp, max_hours, min_certainty, min_liquidity):
                            opportunities.append(opp)
            except Exception as e:
                logger.error(f"Error fetching events with tag '{tag}': {e}")
        
        # Also fetch without tag filter
        try:
            events = self.client.fetch_events(closed=False, limit=1000)
            logger.info(f"Fetched {len(events)} total events")
            
            for event in events:
                event_slug = event.get("slug", "")
                markets = event.get("markets", [])
                
                for market in markets:
                    opp = self._parse_market(market, event_slug, now)
                    if opp and self._qualifies(opp, max_hours, min_certainty, min_liquidity):
                        # Avoid duplicates
                        if not any(o.market_id == opp.market_id for o in opportunities):
                            opportunities.append(opp)
        except Exception as e:
            logger.error(f"Error fetching all events: {e}")
        
        return opportunities
    
    def scan_series(
        self,
        max_hours: float,
        min_certainty: float,
        min_liquidity: float,
        now: datetime
    ) -> List[Opportunity]:
        """Scan recurring series for opportunities."""
        opportunities = []
        
        for series_slug in POLYMARKET_CONFIG.get("target_series", []):
            try:
                series = self.client.fetch_series(series_slug)
                if not series:
                    logger.warning(f"Series not found: {series_slug}")
                    continue
                
                events = series.get("events", [])
                logger.info(f"Series '{series_slug}' has {len(events)} events")
                
                # Pre-filter events by time window and closed status
                candidate_events = []
                for event in events:
                    if event.get("closed", False):
                        continue
                    
                    end_str = event.get("endDate")
                    if not end_str:
                        continue
                    
                    end_time = self._parse_datetime(end_str)
                    if not end_time:
                        continue
                    
                    hours_remaining = (end_time - now).total_seconds() / 3600
                    if 0 < hours_remaining <= max_hours:
                        candidate_events.append(event)
                
                logger.debug(f"Series '{series_slug}': {len(candidate_events)} events within {max_hours}h window")
                
                for event in candidate_events:
                    event_slug = event.get("slug", "")
                    markets = event.get("markets", [])
                    
                    # Series endpoint often returns events without embedded price data
                    # Check if we have prices, if not fetch the full event by slug
                    has_prices = bool(event.get("outcomePrices") or 
                                     any(m.get("outcomePrices") for m in markets))
                    
                    if not has_prices and event_slug:
                        logger.debug(f"Fetching full event data for: {event_slug}")
                        full_event = self.client.fetch_event_by_slug(event_slug)
                        if full_event:
                            markets = full_event.get("markets", [])
                            # If still no markets, try to use the event itself
                            if not markets and full_event.get("outcomePrices"):
                                markets = [full_event]
                    
                    for market in markets:
                        opp = self._parse_market(market, event_slug, now)
                        if opp and self._qualifies(opp, max_hours, min_certainty, min_liquidity):
                            opportunities.append(opp)
                            
            except Exception as e:
                logger.error(f"Error scanning series '{series_slug}': {e}")
        
        return opportunities

    
    def _qualifies(
        self,
        opp: Opportunity,
        max_hours: float,
        min_certainty: float,
        min_liquidity: float
    ) -> bool:
        """Check if an opportunity meets the criteria."""
        # Time window check
        if opp.hours_remaining > max_hours:
            return False
        
        # Certainty check (>=95% for Yes OR >=95% for No means No <= 5%)
        if opp.certainty_pct < min_certainty:
            return False
        
        # Liquidity check
        if opp.liquidity < min_liquidity:
            return False
        
        return True
    
    def scan(
        self,
        max_hours: float = None,
        min_certainty: float = None,
        min_liquidity: float = None
    ) -> List[Opportunity]:
        """
        Run a full scan for high-certainty opportunities.
        
        Args:
            max_hours: Maximum hours until market resolution (default: 4)
            min_certainty: Minimum certainty threshold (default: 0.95)
            min_liquidity: Minimum liquidity in USD (default: 100)
        
        Returns:
            List of Opportunity objects sorted by APR (descending)
        """
        max_hours = max_hours or POLYMARKET_CONFIG["default_time_window_hours"]
        min_certainty = min_certainty or POLYMARKET_CONFIG["min_certainty_threshold"]
        min_liquidity = min_liquidity or POLYMARKET_CONFIG["min_liquidity_usd"]
        
        now = datetime.now(timezone.utc)
        logger.info(f"Starting scan: max_hours={max_hours}, min_certainty={min_certainty}, min_liquidity={min_liquidity}")
        
        # Scan both sources
        opportunities = []
        opportunities.extend(self.scan_events(max_hours, min_certainty, min_liquidity, now))
        opportunities.extend(self.scan_series(max_hours, min_certainty, min_liquidity, now))
        
        # Remove duplicates by market_id
        seen = set()
        unique = []
        for opp in opportunities:
            if opp.market_id not in seen:
                seen.add(opp.market_id)
                unique.append(opp)
        
        # Sort by APR descending
        unique.sort(key=lambda x: x.apr_estimate, reverse=True)
        
        logger.info(f"Scan complete: found {len(unique)} opportunities")
        return unique


def format_opportunity(opp: Opportunity, index: int = 1) -> str:
    """Format an opportunity for display."""
    lines = [
        f"\n#{index} | {opp.hours_remaining:.1f}h remaining | APR: {opp.apr_estimate:,.0f}%",
        f"   Question: \"{opp.question}\"",
        f"   Certainty: {opp.certainty_side} @ {opp.certainty_pct*100:.1f}% | Liquidity: ${opp.liquidity:,.0f}",
        f"   Link: {opp.market_url}",
    ]
    return "\n".join(lines)


def run_scan(
    max_hours: float = 4,
    min_certainty: float = 0.95,
    min_liquidity: float = 100,
    output_json: bool = False
) -> List[Opportunity]:
    """
    Run a scan and optionally output results.
    
    Args:
        max_hours: Maximum hours until resolution
        min_certainty: Minimum certainty (0.95 = 95%)
        min_liquidity: Minimum liquidity in USD
        output_json: If True, print JSON output
    
    Returns:
        List of opportunities found
    """
    scanner = CertaintyScanner()
    opportunities = scanner.scan(
        max_hours=max_hours,
        min_certainty=min_certainty,
        min_liquidity=min_liquidity
    )
    
    if output_json:
        print(json.dumps([o.to_dict() for o in opportunities], indent=2))
    else:
        print(f"\n🎯 Polymarket Certainty Scanner - Results (<{max_hours}h window)")
        print("=" * 65)
        
        if opportunities:
            print(f"\nFound {len(opportunities)} high-certainty opportunities:\n")
            for i, opp in enumerate(opportunities, 1):
                print(format_opportunity(opp, i))
        else:
            print("\nNo opportunities found matching criteria.")
            print(f"  • Time window: <{max_hours} hours")
            print(f"  • Min certainty: {min_certainty*100:.0f}%")
            print(f"  • Min liquidity: ${min_liquidity:,.0f}")
    
    return opportunities


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    run_scan(max_hours=24, min_certainty=0.95, min_liquidity=100)
