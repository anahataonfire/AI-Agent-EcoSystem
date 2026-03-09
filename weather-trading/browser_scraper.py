"""
Browser-based Market Scraper

Scrapes temperature market data from Polymarket using Playwright.
This is the most reliable method since Graph APIs are deprecated.

Requires: pip install playwright && playwright install chromium
"""

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScrapedMarket:
    """Market data scraped from Polymarket website."""
    event_title: str
    question: str
    condition_id: str
    slug: str
    yes_price: float
    no_price: float
    liquidity: float
    volume_24h: float
    city_key: str
    target_date: str
    bucket_low: float
    bucket_high: float
    bucket_unit: str
    clob_token_ids: tuple = (None, None)


# JavaScript to execute in browser to extract market data
EXTRACTION_SCRIPT = """
(() => {
    const nextData = document.querySelector('#__NEXT_DATA__');
    if (!nextData) return { error: "No __NEXT_DATA__ found" };
    
    const data = JSON.parse(nextData.textContent);
    const queries = data.props.pageProps.dehydratedState.queries;
    
    const results = [];
    
    queries.forEach(q => {
        if (q.state && q.state.data && q.state.data.pages) {
            q.state.data.pages.forEach(page => {
                if (page.events) {
                    page.events.forEach(event => {
                        const title = event.title || "";
                        if (title.toLowerCase().includes('temperature') || 
                            title.toLowerCase().includes('hottest')) {
                            event.markets.forEach(m => {
                                results.push({
                                    eventTitle: event.title,
                                    question: m.question,
                                    conditionId: m.conditionId,
                                    slug: m.slug,
                                    outcomePrices: m.outcomePrices,
                                    liquidity: m.liquidity || 0,
                                    volume24hr: m.volume24hr || 0,
                                    clobTokenIds: m.clobTokenIds || []
                                });
                            });
                        }
                    });
                }
            });
        }
    });
    
    return results;
})()
"""


def parse_city_from_title(title: str) -> Optional[str]:
    """Extract city key from event title."""
    title_lower = title.lower()
    city_mappings = {
        "nyc": "nyc", "new york": "nyc",
        "london": "london",
        "buenos aires": "buenos_aires",
        "toronto": "toronto",
        "seattle": "seattle",
        "atlanta": "atlanta",
        "dallas": "dallas",
        "seoul": "seoul",
    }
    for pattern, city_key in city_mappings.items():
        if pattern in title_lower:
            return city_key
    return None


def parse_date_from_title(title: str) -> Optional[str]:
    """Extract date from event title like 'Highest temperature in NYC on January 14'."""
    import re
    months = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
        'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
        'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
        'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
        'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    pattern = r"(" + "|".join(months.keys()) + r")\s+(\d{1,2})"
    match = re.search(pattern, title.lower())
    if match:
        month = months[match.group(1)]
        day = int(match.group(2))
        year = datetime.now().year
        return f"{year}-{month:02d}-{day:02d}"
    return None


def parse_bucket_from_question(question: str) -> tuple:
    """Extract temperature bucket from question."""
    import re
    question = question.replace("°", "")
    
    # "X or below" pattern
    below_match = re.search(r"(-?\d+)\s*([FCc])\s+or\s+below", question, re.I)
    if below_match:
        return (float('-inf'), float(below_match.group(1)), below_match.group(2).upper())
    
    # "X or above/higher" pattern
    above_match = re.search(r"(-?\d+)\s*([FCc])\s+or\s+(?:above|higher)", question, re.I)
    if above_match:
        return (float(above_match.group(1)), float('inf'), above_match.group(2).upper())
    
    # Range pattern "X-Y"
    range_match = re.search(r"(-?\d+)\s*-\s*(-?\d+)\s*([FCc])", question, re.I)
    if range_match:
        return (float(range_match.group(1)), float(range_match.group(2)), range_match.group(3).upper())
    
    # Single temp "XC" or "XF"
    single_match = re.search(r"^(-?\d+)\s*([FCc])$", question.strip(), re.I)
    if single_match:
        temp = float(single_match.group(1))
        return (temp, temp, single_match.group(2).upper())
    
    return (None, None, None)


def scrape_markets_with_playwright() -> List[ScrapedMarket]:
    """
    Scrape markets using Playwright (requires installation).
    
    Install with: pip install playwright && playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return []
    
    markets = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Set longer timeout for slow connections
            page.set_default_timeout(60000)  # 60 seconds
            
            logger.info("Navigating to Polymarket weather page...")
            
            # Use 'domcontentloaded' instead of 'networkidle' - much faster
            page.goto(
                "https://polymarket.com/climate-science/weather", 
                wait_until="domcontentloaded",
                timeout=60000
            )
            
            # Wait for the __NEXT_DATA__ script to be present (script tags are hidden, so just wait for DOM)
            page.wait_for_selector("#__NEXT_DATA__", state="attached", timeout=30000)
            
            # Execute extraction script
            result = page.evaluate(EXTRACTION_SCRIPT)
            
            browser.close()
            
            if isinstance(result, dict) and "error" in result:
                logger.error(f"Extraction failed: {result['error']}")
                return []
            
            logger.info(f"Extracted {len(result) if result else 0} raw markets from page")
            
            # Parse results into ScrapedMarket objects
            for item in result:
                try:
                    city = parse_city_from_title(item["eventTitle"])
                    date = parse_date_from_title(item["eventTitle"])
                    bucket_low, bucket_high, bucket_unit = parse_bucket_from_question(item["question"])
                    
                    if not city or not date or bucket_low is None:
                        continue
                    
                    # Parse prices (format: "[yes, no]" or just yes price)
                    prices = item.get("outcomePrices", "[0.5, 0.5]")
                    if isinstance(prices, str):
                        prices = json.loads(prices.replace("'", '"'))
                    yes_price = float(prices[0]) if prices else 0.5
                    no_price = float(prices[1]) if len(prices) > 1 else 1 - yes_price
                    
                    # Parse clobTokenIds
                    raw_tokens = item.get("clobTokenIds", [])
                    if isinstance(raw_tokens, str):
                        try:
                            raw_tokens = json.loads(raw_tokens)
                        except:
                            raw_tokens = []
                    clob_ids = (str(raw_tokens[0]), str(raw_tokens[1])) if len(raw_tokens) >= 2 else (None, None)
                    
                    market = ScrapedMarket(
                        event_title=item["eventTitle"],
                        question=item["question"],
                        condition_id=item.get("conditionId", ""),
                        slug=item.get("slug", ""),
                        yes_price=yes_price,
                        no_price=no_price,
                        liquidity=float(item.get("liquidity", 0)),
                        volume_24h=float(item.get("volume24hr", 0)),
                        city_key=city,
                        target_date=date,
                        bucket_low=bucket_low,
                        bucket_high=bucket_high,
                        bucket_unit=bucket_unit,
                        clob_token_ids=clob_ids,
                    )
                    markets.append(market)
                    
                except (ValueError, KeyError, TypeError) as e:
                    logger.debug(f"Failed to parse market: {e}")
                    continue
                    
    except PlaywrightTimeout as e:
        logger.error(f"Browser timeout: {e}")
        return []
    except Exception as e:
        logger.error(f"Browser scraping error: {e}")
        return []
    
    logger.info(f"Scraped {len(markets)} temperature markets")
    return markets


def scrape_markets_simple() -> List[dict]:
    """
    Alternative scraping without Playwright (using requests + js2py or similar).
    Returns raw dict data that needs external browser execution.
    
    For use when Playwright isn't available.
    """
    # This would require an external browser or service
    # For now, return empty and suggest using Playwright
    logger.warning("Simple scraping not implemented - use Playwright or browser subagent")
    return []


# Cache for scraped markets
_cached_markets: Optional[List[ScrapedMarket]] = None
_cache_time: Optional[datetime] = None
CACHE_DURATION = timedelta(minutes=15)


def get_scraped_markets(force_refresh: bool = False) -> List[ScrapedMarket]:
    """
    Get scraped markets, with caching.
    
    Args:
        force_refresh: Force re-scrape even if cache is valid
        
    Returns:
        List of ScrapedMarket objects
    """
    global _cached_markets, _cache_time
    
    now = datetime.now(timezone.utc)
    
    if not force_refresh and _cached_markets and _cache_time:
        if now - _cache_time < CACHE_DURATION:
            logger.debug("Using cached markets")
            return _cached_markets
    
    markets = scrape_markets_with_playwright()
    
    if markets:
        _cached_markets = markets
        _cache_time = now
    
    return markets
