#!/usr/bin/env python3
"""
Alpaca Markets Data Client

Provides real-time and historical market data for Quant jobs.
Supports equities, options, and crypto via Alpaca's data API.

API Docs: https://alpaca.markets/docs/api-references/market-data-api/

Environment Variables:
    ALPACA_API_KEY: Your Alpaca API key
    ALPACA_API_SECRET: Your Alpaca API secret
    ALPACA_PAPER: Set to 'true' for paper trading endpoint (optional)
"""

import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import urllib.request
import urllib.error

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, rely on environment variables


# Alpaca API endpoints
ALPACA_DATA_URL = "https://data.alpaca.markets"
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"
ALPACA_LIVE_URL = "https://api.alpaca.markets"


@dataclass
class Quote:
    """Market quote data."""
    symbol: str
    price: float
    bid: float
    ask: float
    volume: int
    timestamp: datetime
    source: str = "alpaca"


@dataclass
class Snapshot:
    """Market snapshot with freshness tracking."""
    snapshot_id: str
    timestamp: datetime
    quotes: Dict[str, Quote]
    freshness_seconds: float
    is_stale: bool


class AlpacaClient:
    """Client for Alpaca Markets data API."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        paper: bool = True
    ):
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.api_secret = api_secret or os.environ.get("ALPACA_API_SECRET")
        self.paper = paper or os.environ.get("ALPACA_PAPER", "true").lower() == "true"
        
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "Alpaca API credentials required. Set ALPACA_API_KEY and ALPACA_API_SECRET "
                "environment variables or pass to constructor."
            )
        
        self.data_url = ALPACA_DATA_URL
        self.trading_url = ALPACA_PAPER_URL if self.paper else ALPACA_LIVE_URL
    
    def _headers(self) -> Dict[str, str]:
        """Build authentication headers."""
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json"
        }
    
    def _request(self, url: str) -> Dict:
        """Make authenticated request to Alpaca API."""
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            raise RuntimeError(f"Alpaca API error {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Alpaca connection error: {e.reason}")
    
    def get_stock_quote(self, symbol: str) -> Quote:
        """Get latest quote for a stock/ETF."""
        url = f"{self.data_url}/v2/stocks/{symbol}/quotes/latest"
        data = self._request(url)
        
        quote_data = data.get("quote", {})
        return Quote(
            symbol=symbol,
            price=(quote_data.get("ap", 0) + quote_data.get("bp", 0)) / 2,  # midpoint
            bid=quote_data.get("bp", 0),
            ask=quote_data.get("ap", 0),
            volume=quote_data.get("as", 0) + quote_data.get("bs", 0),
            timestamp=datetime.fromisoformat(quote_data.get("t", "").replace("Z", "+00:00"))
        )
    
    def get_stock_quotes_batch(self, symbols: List[str]) -> Dict[str, Quote]:
        """Get latest quotes for multiple stocks."""
        # Alpaca allows comma-separated symbols
        symbols_str = ",".join(symbols)
        url = f"{self.data_url}/v2/stocks/quotes/latest?symbols={symbols_str}"
        data = self._request(url)
        
        quotes = {}
        for symbol, quote_data in data.get("quotes", {}).items():
            quotes[symbol] = Quote(
                symbol=symbol,
                price=(quote_data.get("ap", 0) + quote_data.get("bp", 0)) / 2,
                bid=quote_data.get("bp", 0),
                ask=quote_data.get("ap", 0),
                volume=quote_data.get("as", 0) + quote_data.get("bs", 0),
                timestamp=datetime.fromisoformat(quote_data.get("t", "").replace("Z", "+00:00"))
            )
        return quotes
    
    def get_crypto_quote(self, symbol: str) -> Quote:
        """Get latest quote for a crypto asset (e.g., BTC/USD)."""
        # Alpaca uses format like "BTC/USD"
        crypto_symbol = f"{symbol}/USD" if "/" not in symbol else symbol
        url = f"{self.data_url}/v1beta3/crypto/us/latest/quotes?symbols={crypto_symbol}"
        data = self._request(url)
        
        quote_data = data.get("quotes", {}).get(crypto_symbol, {})
        return Quote(
            symbol=symbol,
            price=(quote_data.get("ap", 0) + quote_data.get("bp", 0)) / 2,
            bid=quote_data.get("bp", 0),
            ask=quote_data.get("ap", 0),
            volume=0,  # Crypto quotes don't include volume in this endpoint
            timestamp=datetime.fromisoformat(quote_data.get("t", "").replace("Z", "+00:00")) if quote_data.get("t") else datetime.now(timezone.utc),
            source="alpaca_crypto"
        )
    
    def get_snapshot(
        self,
        stock_symbols: List[str],
        crypto_symbols: List[str],
        freshness_threshold_seconds: float = 300.0
    ) -> Snapshot:
        """
        Get a market snapshot with freshness tracking.
        
        Args:
            stock_symbols: List of stock/ETF symbols (e.g., ["XAU", "XAG", "GME"])
            crypto_symbols: List of crypto symbols (e.g., ["BTC"])
            freshness_threshold_seconds: Max age before data is considered stale
        
        Returns:
            Snapshot with quotes and staleness flag
        """
        now = datetime.now(timezone.utc)
        epoch = int(now.timestamp())
        
        quotes = {}
        oldest_timestamp = now
        
        # Fetch stock quotes
        if stock_symbols:
            try:
                stock_quotes = self.get_stock_quotes_batch(stock_symbols)
                quotes.update(stock_quotes)
                for q in stock_quotes.values():
                    if q.timestamp < oldest_timestamp:
                        oldest_timestamp = q.timestamp
            except Exception as e:
                print(f"Warning: Failed to fetch stock quotes: {e}")
        
        # Fetch crypto quotes
        for symbol in crypto_symbols:
            try:
                crypto_quote = self.get_crypto_quote(symbol)
                quotes[symbol] = crypto_quote
                if crypto_quote.timestamp < oldest_timestamp:
                    oldest_timestamp = crypto_quote.timestamp
            except Exception as e:
                print(f"Warning: Failed to fetch crypto quote for {symbol}: {e}")
        
        # Calculate freshness
        freshness_seconds = (now - oldest_timestamp).total_seconds()
        is_stale = freshness_seconds > freshness_threshold_seconds
        
        return Snapshot(
            snapshot_id=f"mkt_alpaca_{epoch}",
            timestamp=now,
            quotes=quotes,
            freshness_seconds=freshness_seconds,
            is_stale=is_stale
        )


def create_client() -> AlpacaClient:
    """Factory function to create Alpaca client from environment."""
    return AlpacaClient()


def test_connection() -> bool:
    """Test Alpaca API connection."""
    try:
        client = create_client()
        # Test with a simple quote
        quote = client.get_stock_quote("AAPL")
        print(f"Connection OK. AAPL: ${quote.price:.2f}")
        return True
    except Exception as e:
        print(f"Connection FAILED: {e}")
        return False


if __name__ == "__main__":
    # Quick test
    test_connection()
