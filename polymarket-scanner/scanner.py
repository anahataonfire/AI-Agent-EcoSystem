"""
Polymarket Certainty Scanner

Scans Polymarket for high-certainty markets approaching resolution.
Identifies opportunities where outcome probability is >= 95% or <= 5%.

Usage:
    python scanner.py --max-hours 24 --min-certainty 95 --min-liquidity 100
"""

import json
import time
import logging
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

from config import POLYMARKET_CONFIG, HOURS_PER_YEAR

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


@dataclass
class MultiOutcomeOpportunity:
    """Represents an opportunity in a multi-outcome/time-bucketed market."""
    event_id: str
    event_question: str
    outcome_label: str  # e.g., "November 21", "Q1 2026", "42-43°F"
    end_time: datetime
    hours_remaining: float
    yes_price: float
    no_price: float
    liquidity: float
    certainty_side: str  # "YES" or "NO"
    certainty_pct: float  # The higher probability (0-1)
    potential_return_pct: float  # (1/price - 1) * 100
    apr_estimate: float
    market_url: str
    market_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "event_question": self.event_question,
            "outcome_label": self.outcome_label,
            "end_time": self.end_time.isoformat(),
            "hours_remaining": round(self.hours_remaining, 2),
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "liquidity": self.liquidity,
            "certainty_side": self.certainty_side,
            "certainty_pct": round(self.certainty_pct * 100, 1),
            "potential_return_pct": round(self.potential_return_pct, 2),
            "apr_estimate": round(self.apr_estimate, 1),
            "market_url": self.market_url,
            "market_id": self.market_id,
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
        tag: str = None,
        order: str = None,
        ascending: bool = True,
        offset: int = None
    ) -> List[Dict]:
        """Fetch events from the API with optional ordering and pagination."""
        params = {
            "closed": str(closed).lower(),
            "limit": limit or POLYMARKET_CONFIG["fetch_limit"],
        }
        if tag:
            params["tag"] = tag
        if order:
            params["order"] = order
            params["ascending"] = str(ascending).lower()
        if offset:
            params["offset"] = offset
        
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
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            return datetime.fromisoformat(date_str)
        except ValueError:
            logger.warning(f"Could not parse datetime: {date_str}")
            return None
    
    def _extract_date_from_question(self, question: str, now: datetime) -> Optional[datetime]:
        """Extract resolution date from question text for multi-market events."""
        import re
        
        MONTHS = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
            'march': 3, 'mar': 3, 'april': 4, 'apr': 4, 'may': 5,
            'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
            'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
        
        pattern = r'(?:on|by|before|in|during)\s+(?P<month>january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(?P<year>\d{4}))?'
        
        match = re.search(pattern, question.lower())
        
        if match:
            month_name = match.group('month')
            day = int(match.group('day'))
            month = MONTHS.get(month_name)
            year = int(match.group('year')) if match.group('year') else now.year
            
            if month:
                try:
                    target = datetime(year, month, day, 23, 59, 59, tzinfo=timezone.utc)
                    if target < now:
                        return None
                    return target
                except ValueError:
                    return None
        
        return None
    
    def _parse_market(
        self, 
        market: Dict, 
        event_slug: str,
        now: datetime
    ) -> Optional[Opportunity]:
        """Parse a market dict into an Opportunity if it qualifies."""
        try:
            question = market.get("question", "")
            end_str = market.get("endDate")
            api_end_time = self._parse_datetime(end_str)
            
            if not api_end_time:
                return None
            
            extracted_date = self._extract_date_from_question(question, now)
            
            api_hours = (api_end_time - now).total_seconds() / 3600 if api_end_time else -9999
            extracted_hours = (extracted_date - now).total_seconds() / 3600 if extracted_date else -9999
            
            if api_hours <= 0 and extracted_hours > 0:
                end_time = extracted_date
            elif extracted_hours > 0 and extracted_hours < api_hours:
                end_time = extracted_date
            else:
                end_time = api_end_time
            
            if market.get("closed", False):
                return None
            
            hours_remaining = (end_time - now).total_seconds() / 3600 if end_time else -1
            if hours_remaining <= 0:
                return None
            
            prices_raw = market.get("outcomePrices", "[]")
            if isinstance(prices_raw, str):
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw
            
            if len(prices) < 2:
                return None
            
            yes_price = float(prices[0])
            no_price = float(prices[1])
            
            outcomes_raw = market.get("outcomes", '["Yes", "No"]')
            if isinstance(outcomes_raw, str):
                outcomes = json.loads(outcomes_raw)
            else:
                outcomes = outcomes_raw
            
            liquidity = float(market.get("liquidity", 0) or 0)
            volume_24h = float(market.get("volume24hr", 0) or 0)
            
            if yes_price >= no_price:
                certainty_side = outcomes[0] if outcomes else "YES"
                certainty_pct = yes_price
            else:
                certainty_side = outcomes[1] if len(outcomes) > 1 else "NO"
                certainty_pct = no_price
            
            if certainty_side in ["YES", "Yes", "Up"]:
                potential_return = (1 / yes_price) - 1 if yes_price > 0 else 0
            else:
                potential_return = (1 / no_price) - 1 if no_price > 0 else 0
            
            apr = potential_return * (HOURS_PER_YEAR / hours_remaining) if hours_remaining > 0 else 0
            
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
                apr_estimate=apr * 100,
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
        
        if POLYMARKET_CONFIG.get("scan_all_active", True):
            try:
                max_pages = POLYMARKET_CONFIG.get("max_pages", 5)
                limit = POLYMARKET_CONFIG.get("fetch_limit", 500)
                all_events = []
                
                for page in range(max_pages):
                    events = self.client.fetch_events(closed=False, limit=limit)
                    logger.info(f"Fetched {len(events)} events (page {page + 1}/{max_pages})")
                    
                    if not events:
                        break
                    
                    all_events.extend(events)
                    
                    if len(events) < limit:
                        break
                
                logger.info(f"Total events from comprehensive scan: {len(all_events)}")
                
                seen_ids = {o.market_id for o in opportunities}
                for event in all_events:
                    event_slug = event.get("slug", "")
                    markets = event.get("markets", [])
                    
                    for market in markets:
                        market_id = market.get("id", "")
                        if market_id in seen_ids:
                            continue
                            
                        opp = self._parse_market(market, event_slug, now)
                        if opp and self._qualifies(opp, max_hours, min_certainty, min_liquidity):
                            opportunities.append(opp)
                            seen_ids.add(opp.market_id)
            except Exception as e:
                logger.error(f"Error in comprehensive event scan: {e}")
        
        try:
            recent_events = self.client.fetch_events(
                closed=False, 
                limit=500, 
                order="startDate", 
                ascending=False
            )
            logger.info(f"Fetched {len(recent_events)} recent events (by startDate desc)")
            
            seen_ids = {o.market_id for o in opportunities}
            for event in recent_events:
                event_slug = event.get("slug", "")
                markets = event.get("markets", [])
                
                for market in markets:
                    market_id = market.get("id", "")
                    if market_id in seen_ids:
                        continue
                        
                    opp = self._parse_market(market, event_slug, now)
                    if opp and self._qualifies(opp, max_hours, min_certainty, min_liquidity):
                        opportunities.append(opp)
                        seen_ids.add(opp.market_id)
        except Exception as e:
            logger.error(f"Error fetching recent events: {e}")
        
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
                    
                    has_prices = bool(event.get("outcomePrices") or 
                                     any(m.get("outcomePrices") for m in markets))
                    
                    if not has_prices and event_slug:
                        logger.debug(f"Fetching full event data for: {event_slug}")
                        full_event = self.client.fetch_event_by_slug(event_slug)
                        if full_event:
                            markets = full_event.get("markets", [])
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
        if opp.hours_remaining <= 0 or opp.hours_remaining > max_hours:
            return False
        
        if opp.certainty_pct < min_certainty:
            return False
        
        if opp.liquidity < min_liquidity:
            return False
        
        return True
    
    def scan_crypto_daily(
        self,
        max_hours: float,
        min_certainty: float,
        min_liquidity: float,
        now: datetime
    ) -> List[Opportunity]:
        """Scan for daily crypto up-or-down-on-[date] events."""
        opportunities = []
        tokens = POLYMARKET_CONFIG.get("crypto_daily_tokens", [])
        
        dates_to_check = []
        for days_ahead in range(3):
            date = now + timedelta(days=days_ahead)
            month_name = date.strftime("%B").lower()
            day = date.day
            dates_to_check.append(f"{month_name}-{day}")
            dates_to_check.append(f"on-{month_name}-{day}")
        
        for token in tokens:
            for date_pattern in dates_to_check:
                patterns = [
                    f"{token}-up-or-down-{date_pattern}",
                    f"{token}-up-or-down-on-{date_pattern.replace('on-', '')}",
                ]
                
                for slug in patterns:
                    try:
                        event = self.client.fetch_event_by_slug(slug)
                        if event:
                            event_slug = event.get("slug", "")
                            markets = event.get("markets", [])
                            
                            for market in markets:
                                opp = self._parse_market(market, event_slug, now)
                                if opp and self._qualifies(opp, max_hours, min_certainty, min_liquidity):
                                    opportunities.append(opp)
                                    logger.info(f"Found crypto daily: {opp.question}")
                    except Exception:
                        pass
        
        return opportunities
    
    def scan_multi_outcome_markets(
        self,
        max_hours: float,
        min_certainty: float,
        min_liquidity: float,
        now: datetime
    ) -> List[MultiOutcomeOpportunity]:
        """
        Scan for multi-outcome/time-bucketed markets.
        
        These are events with multiple sub-markets (e.g., date brackets, time windows).
        Identifies high-certainty outcomes within these events.
        """
        opportunities = []
        
        try:
            # Fetch all active events
            events = self.client.fetch_events(closed=False, limit=500)
            logger.info(f"Scanning {len(events)} events for multi-outcome markets")
            
            for event in events:
                markets = event.get("markets", [])
                
                # Only process events with multiple markets
                if len(markets) < 2:
                    continue
                
                event_id = event.get("id", "")
                event_question = event.get("title", event.get("question", ""))
                event_slug = event.get("slug", "")
                
                for market in markets:
                    try:
                        # Parse end time
                        end_str = market.get("endDate")
                        end_time = self._parse_datetime(end_str)
                        if not end_time:
                            continue
                        
                        hours_remaining = (end_time - now).total_seconds() / 3600
                        if hours_remaining <= 0:
                            continue
                        
                        # Filter by max_hours
                        if hours_remaining > max_hours:
                            continue
                        
                        # Parse prices
                        prices_raw = market.get("outcomePrices", "[]")
                        if isinstance(prices_raw, str):
                            prices = json.loads(prices_raw)
                        else:
                            prices = prices_raw
                        
                        if len(prices) < 2:
                            continue
                        
                        yes_price = float(prices[0])
                        no_price = float(prices[1])
                        
                        # Determine certainty side
                        if yes_price >= min_certainty:
                            certainty_side = "YES"
                            certainty_pct = yes_price
                            potential_return = (1 / yes_price) - 1 if yes_price > 0 else 0
                        elif no_price >= min_certainty:
                            certainty_side = "NO"
                            certainty_pct = no_price
                            potential_return = (1 / no_price) - 1 if no_price > 0 else 0
                        else:
                            continue
                        
                        liquidity = float(market.get("liquidity", 0) or 0)
                        if liquidity < min_liquidity:
                            continue
                        
                        # Extract outcome label from market question
                        market_question = market.get("question", "")
                        # Try to extract the distinctive part (date, bracket, etc.)
                        outcome_label = market_question
                        if "?" in market_question:
                            outcome_label = market_question.split("?")[0].strip()
                        
                        # Calculate APR
                        apr = potential_return * (HOURS_PER_YEAR / hours_remaining) if hours_remaining > 0 else 0
                        
                        opp = MultiOutcomeOpportunity(
                            event_id=event_id,
                            event_question=event_question,
                            outcome_label=outcome_label,
                            end_time=end_time,
                            hours_remaining=hours_remaining,
                            yes_price=yes_price,
                            no_price=no_price,
                            liquidity=liquidity,
                            certainty_side=certainty_side,
                            certainty_pct=certainty_pct,
                            potential_return_pct=potential_return * 100,
                            apr_estimate=apr * 100,
                            market_url=f"https://polymarket.com/event/{event_slug}",
                            market_id=market.get("id", ""),
                        )
                        opportunities.append(opp)
                        
                    except (ValueError, KeyError, TypeError) as e:
                        logger.debug(f"Error parsing multi-outcome market: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error scanning multi-outcome markets: {e}")
        
        # Sort by potential return
        opportunities.sort(key=lambda x: x.potential_return_pct, reverse=True)
        logger.info(f"Found {len(opportunities)} multi-outcome opportunities")
        return opportunities
    
    def scan(
        self,
        max_hours: float = None,
        min_certainty: float = None,
        min_liquidity: float = None,
        include_multi: bool = True
    ) -> tuple:
        """
        Run a full scan for high-certainty opportunities.
        
        Returns:
            Tuple of (List[Opportunity], List[MultiOutcomeOpportunity])
        """
        max_hours = max_hours or POLYMARKET_CONFIG["default_time_window_hours"]
        min_certainty = min_certainty or POLYMARKET_CONFIG["min_certainty_threshold"]
        min_liquidity = min_liquidity or POLYMARKET_CONFIG["min_liquidity_usd"]
        
        now = datetime.now(timezone.utc)
        logger.info(f"Starting scan: max_hours={max_hours}, min_certainty={min_certainty}, min_liquidity={min_liquidity}")
        
        # Binary opportunities
        opportunities = []
        opportunities.extend(self.scan_events(max_hours, min_certainty, min_liquidity, now))
        opportunities.extend(self.scan_series(max_hours, min_certainty, min_liquidity, now))
        opportunities.extend(self.scan_crypto_daily(max_hours, min_certainty, min_liquidity, now))
        
        seen = set()
        unique = []
        for opp in opportunities:
            if opp.market_id not in seen:
                seen.add(opp.market_id)
                unique.append(opp)
        
        unique.sort(key=lambda x: x.apr_estimate, reverse=True)
        
        # Multi-outcome opportunities
        multi_opps = []
        if include_multi:
            multi_opps = self.scan_multi_outcome_markets(max_hours, min_certainty, min_liquidity, now)
        
        logger.info(f"Scan complete: {len(unique)} binary, {len(multi_opps)} multi-outcome")
        return unique, multi_opps


def format_opportunity(opp: Opportunity, index: int = 1) -> str:
    """Format an opportunity for display."""
    lines = [
        f"\n#{index} | {opp.hours_remaining:.1f}h remaining | APR: {opp.apr_estimate:,.0f}%",
        f'   Question: "{opp.question}"',
        f"   Certainty: {opp.certainty_side} @ {opp.certainty_pct*100:.1f}% | Liquidity: ${opp.liquidity:,.0f}",
        f"   Link: {opp.market_url}",
    ]
    return "\n".join(lines)


def format_multi_outcome_group(opps: List[MultiOutcomeOpportunity]) -> str:
    """
    Format a group of multi-outcome opportunities from the same event.
    Groups by event_question and shows each outcome.
    """
    if not opps:
        return ""
    
    # Group by event
    by_event: Dict[str, List[MultiOutcomeOpportunity]] = {}
    for opp in opps:
        key = opp.event_question
        if key not in by_event:
            by_event[key] = []
        by_event[key].append(opp)
    
    lines = []
    for event_q, event_opps in by_event.items():
        lines.append(f"\n📊 {event_q}")
        lines.append("   " + "-" * 60)
        
        # Sort by hours remaining
        event_opps.sort(key=lambda x: x.hours_remaining)
        
        for opp in event_opps:
            side_emoji = "✅" if opp.certainty_side == "YES" else "❌"
            price = opp.yes_price if opp.certainty_side == "YES" else opp.no_price
            lines.append(
                f"   {side_emoji} {opp.outcome_label[:50]}"
            )
            lines.append(
                f"      {opp.certainty_side} @ {price*100:.0f}¢ | "
                f"Return: {opp.potential_return_pct:.1f}% | "
                f"{opp.hours_remaining:.0f}h | "
                f"Liq: ${opp.liquidity:,.0f}"
            )
        
        lines.append(f"   🔗 {event_opps[0].market_url}")
    
    return "\n".join(lines)


def run_scan(
    max_hours: float = 24,
    min_certainty: float = 0.90,
    min_liquidity: float = 100,
    output_json: bool = False,
    include_multi: bool = True
) -> tuple:
    """Run a scan and optionally output results."""
    scanner = CertaintyScanner()
    opportunities, multi_opps = scanner.scan(
        max_hours=max_hours,
        min_certainty=min_certainty,
        min_liquidity=min_liquidity,
        include_multi=include_multi
    )
    
    if output_json:
        output = {
            "binary_opportunities": [o.to_dict() for o in opportunities],
            "multi_outcome_opportunities": [o.to_dict() for o in multi_opps],
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n🎯 Polymarket Certainty Scanner - Results (<{max_hours}h window)")
        print("=" * 65)
        
        # Binary opportunities
        if opportunities:
            print(f"\n📈 BINARY MARKETS ({len(opportunities)} found):\n")
            for i, opp in enumerate(opportunities, 1):
                print(format_opportunity(opp, i))
        else:
            print("\n📈 No binary opportunities found.")
        
        # Multi-outcome opportunities
        if include_multi and multi_opps:
            print(f"\n\n📊 MULTI-OUTCOME MARKETS ({len(multi_opps)} found):")
            print(format_multi_outcome_group(multi_opps))
        elif include_multi:
            print("\n📊 No multi-outcome opportunities found.")
        
        print("\n" + "=" * 65)
        print(f"Criteria: certainty ≥{min_certainty*100:.0f}%, liquidity ≥${min_liquidity:,.0f}")
    
    return opportunities, multi_opps


def main():
    parser = argparse.ArgumentParser(description="Polymarket Certainty Scanner")
    parser.add_argument("--max-hours", type=float, default=24, help="Max hours until resolution")
    parser.add_argument("--min-certainty", type=float, default=90, help="Min certainty %% (e.g., 90)")
    parser.add_argument("--min-liquidity", type=float, default=100, help="Min liquidity USD")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-multi", action="store_true", help="Exclude multi-outcome markets")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s | %(levelname)s | %(message)s")
    
    run_scan(
        max_hours=args.max_hours,
        min_certainty=args.min_certainty / 100,
        min_liquidity=args.min_liquidity,
        output_json=args.json,
        include_multi=not args.no_multi
    )


if __name__ == "__main__":
    main()
