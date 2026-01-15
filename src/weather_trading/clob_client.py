"""
Polymarket CLOB Trading Client

Provides order execution capabilities for weather trading.
Supports both paper trading and live mode with safety limits.
"""

import json
import logging
import os
import time
import hmac
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)


# CLOB API Endpoints
CLOB_BASE_URL = "https://clob.polymarket.com"
GAMMA_BASE_URL = "https://gamma-api.polymarket.com"


@dataclass
class Order:
    """Represents a trading order."""
    order_id: str
    token_id: str
    side: str  # "BUY" or "SELL"
    price: float
    size: float
    status: str  # "OPEN", "FILLED", "CANCELLED", "PENDING"
    created_at: datetime
    filled_at: Optional[datetime] = None
    paper_mode: bool = True


@dataclass
class Position:
    """Represents a market position."""
    token_id: str
    market_slug: str
    outcome: str  # "Yes" or "No"
    size: float
    avg_price: float
    current_price: float
    unrealized_pnl: float
    paper_mode: bool = True


@dataclass
class Trade:
    """Represents a completed trade."""
    trade_id: str
    order_id: str
    token_id: str
    market_slug: str
    side: str
    price: float
    size: float
    executed_at: datetime
    pnl: Optional[float] = None
    paper_mode: bool = True


class PolymarketCLOBClient:
    """
    Client for Polymarket CLOB order execution.
    
    Supports:
    - Paper trading (simulated orders)
    - Live trading with position limits
    - GTC/FOK order types
    """
    
    def __init__(
        self,
        private_key: Optional[str] = None,
        paper_mode: bool = True,
        max_position_size: float = 10.0,  # Max $10 per trade
        max_total_exposure: float = 100.0,  # Max $100 total
    ):
        """
        Initialize CLOB client.
        
        Args:
            private_key: Wallet private key (from env if None)
            paper_mode: If True, simulate trades without real execution
            max_position_size: Maximum size per trade in USD
            max_total_exposure: Maximum total exposure across all positions
        """
        self.paper_mode = paper_mode
        self.max_position_size = max_position_size
        self.max_total_exposure = max_total_exposure
        
        # Load credentials from env
        self.api_key = os.getenv("POLYMARKET_API_KEY")
        self.api_secret = os.getenv("POLYMARKET_API_SECRET")
        self.api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE")
        self.address = os.getenv("POLYMARKET_ADDRESS")
        
        # Fallback to private key
        if private_key is None:
            private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
        self.private_key = private_key
        
        # Paper trading state
        self._paper_orders: List[Order] = []
        self._paper_positions: Dict[str, Position] = {}
        self._paper_trades: List[Trade] = []
        self._paper_balance: float = 1000.0  # Simulated balance
        
        # Trade log
        self._trade_log_path = os.path.join(
            os.path.dirname(__file__), 
            "trade_log.json"
        )
        
        # Validate credentials for live mode
        if not paper_mode:
            if not (self.api_key and self.api_secret and self.api_passphrase):
                raise ValueError(
                    "API credentials required for live trading. "
                    "Run: python scripts/setup_polymarket_api.py"
                )
        
        logger.info(
            f"Initialized CLOB client - "
            f"{'PAPER MODE' if paper_mode else 'LIVE MODE'}"
        )
    
    def _generate_signature(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """Generate HMAC-SHA256 signature for API request."""
        message = timestamp + method + path + body
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _auth_headers(self, method: str, path: str, body: str = "") -> Dict:
        """Generate authenticated headers for CLOB API."""
        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp, method, path, body)
        
        return {
            "POLY_ADDRESS": self.address,
            "POLY_SIGNATURE": signature,
            "POLY_TIMESTAMP": timestamp,
            "POLY_NONCE": str(int(time.time() * 1000)),
            "POLY_API_KEY": self.api_key,
            "POLY_PASSPHRASE": self.api_passphrase,
            "Content-Type": "application/json",
            "User-Agent": "WeatherTrader/1.0"
        }
    
    def _make_request(
        self, 
        url: str, 
        method: str = "GET",
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict:
        """Make HTTP request to API."""
        try:
            headers = headers or {}
            headers["Content-Type"] = "application/json"
            headers["User-Agent"] = "WeatherTrader/1.0"
            
            if data:
                encoded_data = json.dumps(data).encode()
            else:
                encoded_data = None
            
            req = Request(url, data=encoded_data, headers=headers, method=method)
            
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except HTTPError as e:
            logger.error(f"HTTP error {e.code}: {e.reason}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {"error": str(e)}
    
    def get_orderbook(self, token_id: str) -> Dict:
        """
        Fetch orderbook for a specific token.
        
        Args:
            token_id: The condition token ID
            
        Returns:
            Orderbook with bids and asks
        """
        url = f"{CLOB_BASE_URL}/book?token_id={token_id}"
        return self._make_request(url)
    
    def get_market_price(self, token_id: str) -> Tuple[float, float]:
        """
        Get best bid/ask prices for a token.
        
        Returns:
            Tuple of (best_bid, best_ask) prices
        """
        book = self.get_orderbook(token_id)
        
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        
        best_bid = float(bids[0]["price"]) if bids else 0.0
        best_ask = float(asks[0]["price"]) if asks else 1.0
        
        return best_bid, best_ask
    
    def place_limit_order(
        self,
        token_id: str,
        market_slug: str,
        side: str,  # "BUY" or "SELL"
        price: float,
        size: float,
        order_type: str = "GTC"  # GTC, FOK, FAK
    ) -> Order:
        """
        Place a limit order.
        
        Args:
            token_id: The condition token ID
            market_slug: Market slug for logging
            side: "BUY" or "SELL"
            price: Limit price (0-1)
            size: Position size in USD
            order_type: GTC (Good Til Cancelled), FOK (Fill Or Kill), FAK (Fill And Kill)
            
        Returns:
            Order object
        """
        # Validate inputs
        if side not in ["BUY", "SELL"]:
            raise ValueError(f"Invalid side: {side}")
        if not 0 < price < 1:
            raise ValueError(f"Price must be between 0 and 1: {price}")
        if size <= 0:
            raise ValueError(f"Size must be positive: {size}")
        if size > self.max_position_size:
            logger.warning(f"Capping size from ${size} to ${self.max_position_size}")
            size = self.max_position_size
        
        order_id = f"{'paper_' if self.paper_mode else ''}{int(time.time() * 1000)}"
        
        order = Order(
            order_id=order_id,
            token_id=token_id,
            side=side,
            price=price,
            size=size,
            status="PENDING",
            created_at=datetime.now(timezone.utc),
            paper_mode=self.paper_mode
        )
        
        if self.paper_mode:
            # Paper trading - simulate fill
            order.status = "FILLED"
            order.filled_at = datetime.now(timezone.utc)
            
            # Update paper positions
            self._update_paper_position(token_id, market_slug, side, price, size)
            
            # Log trade
            trade = Trade(
                trade_id=f"trade_{order_id}",
                order_id=order_id,
                token_id=token_id,
                market_slug=market_slug,
                side=side,
                price=price,
                size=size,
                executed_at=datetime.now(timezone.utc),
                paper_mode=True
            )
            self._paper_trades.append(trade)
            self._log_trade(trade)
            
            logger.info(
                f"[PAPER] Placed {side} order: ${size:.2f} @ {price:.2f} "
                f"on {market_slug}"
            )
            
        else:
            # Live trading - submit to CLOB API
            logger.info(f"[LIVE] Placing {side} order: ${size:.2f} @ {price:.2f}")
            
            # Build order payload
            order_payload = {
                "tokenID": token_id,
                "price": str(price),
                "size": str(size),
                "side": side,
                "type": order_type,
            }
            
            body = json.dumps(order_payload)
            path = "/order"
            headers = self._auth_headers("POST", path, body)
            
            try:
                req = Request(
                    f"{CLOB_BASE_URL}{path}",
                    data=body.encode(),
                    headers=headers,
                    method="POST"
                )
                
                with urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode())
                    
                    order.order_id = result.get("orderID", order.order_id)
                    order.status = "SUBMITTED"
                    
                    logger.info(f"[LIVE] Order submitted: {order.order_id}")
                    
                    # Log the trade
                    trade = Trade(
                        trade_id=f"live_{order.order_id}",
                        order_id=order.order_id,
                        token_id=token_id,
                        market_slug=market_slug,
                        side=side,
                        price=price,
                        size=size,
                        executed_at=datetime.now(timezone.utc),
                        paper_mode=False
                    )
                    self._log_trade(trade)
                    
            except HTTPError as e:
                error_body = e.read().decode() if e.fp else ""
                logger.error(f"[LIVE] Order failed: {e.code} - {error_body}")
                order.status = "FAILED"
            except Exception as e:
                logger.error(f"[LIVE] Order error: {e}")
                order.status = "FAILED"
        
        self._paper_orders.append(order)
        return order
    
    def _update_paper_position(
        self,
        token_id: str,
        market_slug: str,
        side: str,
        price: float,
        size: float
    ):
        """Update paper trading positions."""
        if token_id in self._paper_positions:
            pos = self._paper_positions[token_id]
            if side == "BUY":
                # Add to position
                new_size = pos.size + size
                pos.avg_price = (pos.avg_price * pos.size + price * size) / new_size
                pos.size = new_size
            else:
                # Reduce position
                pos.size = max(0, pos.size - size)
        else:
            if side == "BUY":
                self._paper_positions[token_id] = Position(
                    token_id=token_id,
                    market_slug=market_slug,
                    outcome="Yes",
                    size=size,
                    avg_price=price,
                    current_price=price,
                    unrealized_pnl=0.0,
                    paper_mode=True
                )
    
    def _log_trade(self, trade: Trade):
        """Log trade to JSON file."""
        try:
            if os.path.exists(self._trade_log_path):
                with open(self._trade_log_path, 'r') as f:
                    trades = json.load(f)
            else:
                trades = []
            
            trades.append({
                "trade_id": trade.trade_id,
                "order_id": trade.order_id,
                "token_id": trade.token_id,
                "market_slug": trade.market_slug,
                "side": trade.side,
                "price": trade.price,
                "size": trade.size,
                "executed_at": trade.executed_at.isoformat(),
                "paper_mode": trade.paper_mode
            })
            
            with open(self._trade_log_path, 'w') as f:
                json.dump(trades, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error logging trade: {e}")
    
    def get_positions(self) -> List[Position]:
        """Get all current positions."""
        if self.paper_mode:
            return list(self._paper_positions.values())
        else:
            # TODO: Fetch real positions from API
            return []
    
    def get_total_exposure(self) -> float:
        """Calculate total position exposure in USD."""
        positions = self.get_positions()
        return sum(p.size * p.avg_price for p in positions)
    
    def get_trade_history(self) -> List[Trade]:
        """Get trade history."""
        if self.paper_mode:
            return self._paper_trades
        else:
            # TODO: Fetch real trade history
            return []
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if self.paper_mode:
            for order in self._paper_orders:
                if order.order_id == order_id and order.status == "OPEN":
                    order.status = "CANCELLED"
                    logger.info(f"[PAPER] Cancelled order {order_id}")
                    return True
            return False
        else:
            # TODO: Implement real order cancellation
            logger.warning("Live order cancellation not yet implemented")
            return False
    
    def print_summary(self):
        """Print trading summary."""
        print("\n" + "=" * 60)
        print(f"  TRADING SUMMARY {'(PAPER MODE)' if self.paper_mode else '(LIVE)'}")
        print("=" * 60)
        
        positions = self.get_positions()
        trades = self.get_trade_history()
        
        print(f"\n  Total Trades: {len(trades)}")
        print(f"  Open Positions: {len(positions)}")
        print(f"  Total Exposure: ${self.get_total_exposure():.2f}")
        
        if positions:
            print("\n  POSITIONS:")
            for pos in positions:
                print(f"    {pos.market_slug}: ${pos.size:.2f} @ {pos.avg_price:.2f}")
        
        if trades:
            print("\n  RECENT TRADES:")
            for trade in trades[-5:]:
                print(
                    f"    {trade.executed_at.strftime('%Y-%m-%d %H:%M')} | "
                    f"{trade.side} ${trade.size:.2f} @ {trade.price:.2f}"
                )
        
        print("=" * 60)


# Convenience function for paper trading test
def test_paper_trading():
    """Quick test of paper trading functionality."""
    client = PolymarketCLOBClient(paper_mode=True)
    
    # Simulate buying a weather market
    client.place_limit_order(
        token_id="test_token_123",
        market_slug="nyc-daily-high-temp-jan-15",
        side="BUY",
        price=0.35,
        size=10.0
    )
    
    client.print_summary()
    return client


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_paper_trading()
