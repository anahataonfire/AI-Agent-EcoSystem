"""
Fetch Price History from Polymarket CLOB API

Fetches and stores historical price data for weather markets.
Uses the CLOB /prices-history endpoint to get time-series price data.

Usage:
    python3 fetch_price_history.py --days 30 --interval 1h
"""

import argparse
import json
import logging
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from config import CLOB_API_URL, ACTIVE_CITIES
from scanner import WeatherMarketScanner, WeatherMarket

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent / "weather_backtest.db"


def init_database() -> sqlite3.Connection:
    """
    Initialize the SQLite database with price_history table.
    
    Returns:
        Database connection
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY,
            market_id TEXT NOT NULL,
            condition_id TEXT NOT NULL,
            token_id TEXT NOT NULL,
            city_key TEXT,
            target_date TEXT,
            bucket_low REAL,
            bucket_high REAL,
            timestamp TEXT NOT NULL,
            price REAL NOT NULL,
            side TEXT NOT NULL,
            UNIQUE(token_id, timestamp, side)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_history_market 
        ON price_history(market_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_history_time 
        ON price_history(timestamp)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_history_city 
        ON price_history(city_key, target_date)
    """)
    
    conn.commit()
    logger.info(f"Database initialized at {DB_PATH}")
    return conn


class ClobClient:
    """Client for Polymarket CLOB API."""
    
    def __init__(self, base_url: str = None, request_delay: float = 0.5):
        self.base_url = base_url or CLOB_API_URL
        self.request_delay = request_delay
        self._last_request_time = 0.0
        self.timeout = 30.0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()
    
    def _make_request(self, endpoint: str, params: Dict = None, retries: int = 3) -> Optional[Dict]:
        """
        Make an HTTP GET request with retry logic.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            retries: Number of retry attempts
            
        Returns:
            Parsed JSON response or None on error
        """
        from urllib.parse import urlencode
        
        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        if params:
            url = f"{url}?{urlencode(params)}"
        
        logger.debug(f"Requesting: {url}")
        
        for attempt in range(retries):
            try:
                req = Request(url, headers={"User-Agent": "WeatherTradingBot/1.0"})
                with urlopen(req, timeout=self.timeout) as response:
                    return json.loads(response.read().decode())
            except HTTPError as e:
                logger.warning(f"HTTP Error {e.code} (attempt {attempt + 1}/{retries}): {e.reason}")
                if attempt < retries - 1:
                    backoff = 2 ** attempt
                    time.sleep(backoff)
            except URLError as e:
                logger.warning(f"URL Error (attempt {attempt + 1}/{retries}): {e.reason}")
                if attempt < retries - 1:
                    backoff = 2 ** attempt
                    time.sleep(backoff)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return None
        
        return None
    
    def fetch_price_history(
        self,
        token_id: str,
        interval: str = "1h",
        fidelity: int = 60,
        start_ts: int = None,
        end_ts: int = None
    ) -> List[Dict]:
        """
        Fetch price history from Polymarket CLOB.
        
        Endpoint: GET /prices-history
        
        Args:
            token_id: The clobTokenId (NOT conditionId)
            interval: Price interval - "1m", "5m", "1h", "1d"
            fidelity: Minutes between data points (default 60)
            start_ts: Unix timestamp for start (optional)
            end_ts: Unix timestamp for end (optional)
            
        Returns:
            List of {t: timestamp, p: price} objects
        """
        params = {
            "market": token_id,
            "interval": interval,
            "fidelity": fidelity,
        }
        
        if start_ts:
            params["startTs"] = start_ts
        if end_ts:
            params["endTs"] = end_ts
        
        result = self._make_request("/prices-history", params)
        
        if result and isinstance(result, dict) and "history" in result:
            return result["history"]
        elif result and isinstance(result, list):
            return result
        
        return []
    
    def fetch_market_info(self, condition_id: str) -> Optional[Dict]:
        """
        Fetch market info including token IDs.
        
        Args:
            condition_id: The market condition ID
            
        Returns:
            Market info dict or None
        """
        result = self._make_request(f"/markets/{condition_id}")
        return result


def get_token_ids_for_market(market: WeatherMarket, client: ClobClient = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract YES and NO token IDs from market.
    
    The clobTokenIds field in the Gamma API contains a JSON string:
    '["token_yes", "token_no"]'
    
    Args:
        market: WeatherMarket object
        client: Optional ClobClient for fallback API call
        
    Returns:
        Tuple of (yes_token_id, no_token_id) or (None, None) if not found
    """
    # Try to get from market attributes if available
    clob_token_ids = getattr(market, 'clob_token_ids', None)
    
    if clob_token_ids:
        # Handle tuple format (from WeatherMarket)
        if isinstance(clob_token_ids, tuple) and len(clob_token_ids) >= 2:
            if clob_token_ids[0] and clob_token_ids[1]:
                return (clob_token_ids[0], clob_token_ids[1])
        # Handle JSON string format (from raw API)
        elif isinstance(clob_token_ids, str):
            try:
                tokens = json.loads(clob_token_ids)
                if isinstance(tokens, list) and len(tokens) >= 2:
                    return (tokens[0], tokens[1])
            except json.JSONDecodeError:
                pass
        # Handle list format
        elif isinstance(clob_token_ids, list) and len(clob_token_ids) >= 2:
            return (clob_token_ids[0], clob_token_ids[1])
    
    # Fallback: fetch from CLOB API using condition_id
    if client and hasattr(market, 'condition_id') and market.condition_id:
        info = client.fetch_market_info(market.condition_id)
        if info:
            tokens = info.get("tokens", [])
            if len(tokens) >= 2:
                yes_token = next((t["token_id"] for t in tokens if t.get("outcome") == "Yes"), None)
                no_token = next((t["token_id"] for t in tokens if t.get("outcome") == "No"), None)
                if yes_token and no_token:
                    return (yes_token, no_token)
    
    return (None, None)


def fetch_and_store_history(
    markets: List[WeatherMarket],
    days_back: int = 30,
    interval: str = "1h",
    conn: sqlite3.Connection = None
) -> Tuple[int, int, int]:
    """
    Fetch historical prices for all markets and store in SQLite.
    
    Args:
        markets: List of WeatherMarket objects
        days_back: Number of days of history to fetch
        interval: Price interval (1m, 5m, 1h, 1d)
        conn: Database connection
        
    Returns:
        Tuple of (records_inserted, markets_processed, failures)
    """
    if conn is None:
        conn = init_database()
    
    client = ClobClient()
    cursor = conn.cursor()
    
    now = datetime.now(timezone.utc)
    start_ts = int((now - timedelta(days=days_back)).timestamp())
    end_ts = int(now.timestamp())
    
    records_inserted = 0
    markets_processed = 0
    failures = 0
    
    logger.info(f"Fetching {days_back} days of history for {len(markets)} markets")
    
    for market in markets:
        try:
            # Get token IDs
            yes_token, no_token = get_token_ids_for_market(market, client)
            
            if not yes_token or not no_token:
                logger.debug(f"No token IDs for market: {market.question[:50]}")
                failures += 1
                continue
            
            # Fetch YES price history
            yes_history = client.fetch_price_history(
                token_id=yes_token,
                interval=interval,
                start_ts=start_ts,
                end_ts=end_ts
            )
            
            # Fetch NO price history
            no_history = client.fetch_price_history(
                token_id=no_token,
                interval=interval,
                start_ts=start_ts,
                end_ts=end_ts
            )
            
            # Store YES prices
            for point in yes_history:
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO price_history 
                        (market_id, condition_id, token_id, city_key, target_date,
                         bucket_low, bucket_high, timestamp, price, side)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        market.market_id,
                        getattr(market, 'condition_id', ''),
                        yes_token,
                        market.city_key,
                        market.target_date,
                        market.bucket_low,
                        market.bucket_high,
                        point.get("t", ""),
                        float(point.get("p", 0)),
                        "YES"
                    ))
                    if cursor.rowcount > 0:
                        records_inserted += 1
                except sqlite3.Error as e:
                    logger.debug(f"Insert error: {e}")
            
            # Store NO prices
            for point in no_history:
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO price_history 
                        (market_id, condition_id, token_id, city_key, target_date,
                         bucket_low, bucket_high, timestamp, price, side)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        market.market_id,
                        getattr(market, 'condition_id', ''),
                        no_token,
                        market.city_key,
                        market.target_date,
                        market.bucket_low,
                        market.bucket_high,
                        point.get("t", ""),
                        float(point.get("p", 0)),
                        "NO"
                    ))
                    if cursor.rowcount > 0:
                        records_inserted += 1
                except sqlite3.Error as e:
                    logger.debug(f"Insert error: {e}")
            
            conn.commit()
            markets_processed += 1
            
            total_points = len(yes_history) + len(no_history)
            logger.info(f"Fetched {total_points} price points for {market.city_key} {market.bucket_low}-{market.bucket_high}")
            
        except Exception as e:
            logger.error(f"Error processing market {market.market_id}: {e}")
            failures += 1
    
    return records_inserted, markets_processed, failures


def get_markets_for_fetch(city_filter: List[str] = None) -> List[WeatherMarket]:
    """
    Get weather markets for price history fetching.
    
    Args:
        city_filter: Optional list of city keys to filter
        
    Returns:
        List of WeatherMarket objects
    """
    scanner = WeatherMarketScanner()
    markets = scanner.fetch_weather_markets(city_filter=city_filter or ACTIVE_CITIES)
    return markets


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch price history from Polymarket CLOB API"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days of history to fetch (default: 30)"
    )
    parser.add_argument(
        "--interval",
        type=str,
        default="1h",
        choices=["1m", "5m", "1h", "1d"],
        help="Price interval (default: 1h)"
    )
    parser.add_argument(
        "--city",
        type=str,
        default=None,
        help="Filter to specific city (optional)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )
    
    # Initialize database
    conn = init_database()
    
    # Get markets
    city_filter = [args.city] if args.city else None
    logger.info(f"Fetching weather markets...")
    markets = get_markets_for_fetch(city_filter)
    
    if not markets:
        logger.warning("No weather markets found")
        return
    
    logger.info(f"Found {len(markets)} weather markets")
    
    # Fetch and store history
    records, processed, failures = fetch_and_store_history(
        markets=markets,
        days_back=args.days,
        interval=args.interval,
        conn=conn
    )
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Price History Fetch Complete")
    print(f"{'='*50}")
    print(f"  Markets processed: {processed}")
    print(f"  Records inserted:  {records}")
    print(f"  Failures:          {failures}")
    print(f"  Database:          {DB_PATH}")
    print(f"{'='*50}")
    
    conn.close()


if __name__ == "__main__":
    main()
