"""
Weather Trader - Automated Order Execution

Connects the weather scanner (edge detection) with the CLOB client (order execution)
to automatically trade weather markets based on probability edge.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from clob_client import PolymarketCLOBClient, Order, Trade
from probability import calculate_bucket_probability, estimate_forecast_std

logger = logging.getLogger(__name__)


@dataclass
class TradingOpportunity:
    """An opportunity identified by the scanner."""
    city: str
    target_date: str
    bucket_low: float
    bucket_high: float
    bucket_unit: str
    forecast_temp: float
    forecast_std: float
    market_price: float
    calculated_prob: float
    edge: float
    token_id: str
    market_slug: str
    liquidity: float


class WeatherTrader:
    """
    Automated trader for weather markets.
    
    Monitors scanner output and executes trades when edge threshold is met.
    """
    
    def __init__(
        self,
        clob_client: Optional[PolymarketCLOBClient] = None,
        min_edge: float = 0.15,  # 15% minimum edge
        min_liquidity: float = 100.0,  # $100 minimum liquidity
        max_position_per_market: float = 2.0,  # Max $2 per market
        max_total_exposure: float = 20.0,  # Max $20 total
        paper_mode: bool = True,
    ):
        """
        Initialize the weather trader.
        
        Args:
            clob_client: CLOB client for order execution
            min_edge: Minimum edge to take a trade
            min_liquidity: Minimum market liquidity to trade
            max_position_per_market: Max position size per market
            max_total_exposure: Max total exposure across all markets
            paper_mode: If True, use paper trading
        """
        self.min_edge = min_edge
        self.min_liquidity = min_liquidity
        self.max_position_per_market = max_position_per_market
        self.max_total_exposure = max_total_exposure
        self.paper_mode = paper_mode
        
        # Initialize CLOB client
        if clob_client:
            self.clob = clob_client
        else:
            self.clob = PolymarketCLOBClient(
                paper_mode=paper_mode,
                max_position_size=max_position_per_market,
                max_total_exposure=max_total_exposure
            )
        
        # Track executed trades to avoid duplicates
        self._traded_markets: Dict[str, datetime] = {}
        
        logger.info(
            f"WeatherTrader initialized - "
            f"min_edge={min_edge*100:.0f}%, "
            f"{'PAPER' if paper_mode else 'LIVE'}"
        )
    
    def evaluate_opportunity(self, opp: TradingOpportunity) -> bool:
        """
        Evaluate if an opportunity should be traded.
        
        Returns:
            True if the opportunity meets all criteria
        """
        # Check edge threshold
        if opp.edge < self.min_edge:
            logger.debug(f"Edge {opp.edge*100:.1f}% below threshold {self.min_edge*100:.0f}%")
            return False
        
        # Check liquidity
        if opp.liquidity < self.min_liquidity:
            logger.debug(f"Liquidity ${opp.liquidity:.0f} below threshold ${self.min_liquidity:.0f}")
            return False
        
        # Check if already traded this market today
        market_key = f"{opp.market_slug}_{opp.target_date}"
        if market_key in self._traded_markets:
            logger.debug(f"Already traded {market_key}")
            return False
        
        # Check total exposure limit
        current_exposure = self.clob.get_total_exposure()
        if current_exposure >= self.max_total_exposure:
            logger.warning(f"Max exposure ${self.max_total_exposure} reached")
            return False
        
        return True
    
    def calculate_position_size(self, opp: TradingOpportunity) -> float:
        """
        Calculate optimal position size based on edge and risk.
        
        Uses Kelly criterion with fraction cap.
        """
        # Simple Kelly: edge / (1 - price) for binary options
        # But cap at max_position_per_market
        
        kelly_fraction = opp.edge / (1 - opp.market_price) if opp.market_price < 1 else 0
        
        # Cap Kelly at 0.25 (quarter Kelly for safety)
        capped_kelly = min(0.25, kelly_fraction)
        
        # Calculate position size
        bankroll = 1000  # Assume $1000 bankroll for sizing
        position_size = bankroll * capped_kelly
        
        # Apply max limit
        position_size = min(position_size, self.max_position_per_market)
        
        # Check remaining exposure room
        current_exposure = self.clob.get_total_exposure()
        remaining_room = self.max_total_exposure - current_exposure
        position_size = min(position_size, remaining_room)
        
        return max(1.0, position_size)  # Minimum $1
    
    def execute_trade(self, opp: TradingOpportunity) -> Optional[Order]:
        """
        Execute a trade for an opportunity.
        
        Args:
            opp: The trading opportunity
            
        Returns:
            Order object if executed, None otherwise
        """
        if not self.evaluate_opportunity(opp):
            return None
        
        position_size = self.calculate_position_size(opp)
        
        logger.info(
            f"Executing trade: {opp.city} {opp.target_date} "
            f"{opp.bucket_low}-{opp.bucket_high}°{opp.bucket_unit} "
            f"edge={opp.edge*100:.1f}% size=${position_size:.2f}"
        )
        
        try:
            order = self.clob.place_limit_order(
                token_id=opp.token_id,
                market_slug=opp.market_slug,
                side="BUY",  # Always buying "Yes" on our predicted bucket
                price=opp.market_price,
                size=position_size,
                order_type="GTC"
            )
            
            # Mark as traded
            market_key = f"{opp.market_slug}_{opp.target_date}"
            self._traded_markets[market_key] = datetime.now(timezone.utc)
            
            return order
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return None
    
    def process_scan_results(
        self, 
        opportunities: List[Dict]
    ) -> List[Order]:
        """
        Process scanner results and execute qualifying trades.
        
        Args:
            opportunities: List of opportunities from weather scanner
            
        Returns:
            List of executed orders
        """
        executed_orders = []
        
        for opp_dict in opportunities:
            # Convert dict to TradingOpportunity
            opp = TradingOpportunity(
                city=opp_dict.get("city", ""),
                target_date=opp_dict.get("target_date", ""),
                bucket_low=opp_dict.get("bucket_low", 0),
                bucket_high=opp_dict.get("bucket_high", 0),
                bucket_unit=opp_dict.get("bucket_unit", "F"),
                forecast_temp=opp_dict.get("forecast_temp", 0),
                forecast_std=opp_dict.get("forecast_std", 3.0),
                market_price=opp_dict.get("market_price", 0),
                calculated_prob=opp_dict.get("calculated_probability", 0),
                edge=opp_dict.get("edge", 0),
                token_id=opp_dict.get("token_id", "unknown"),
                market_slug=opp_dict.get("market_slug", "unknown"),
                liquidity=opp_dict.get("liquidity", 0),
            )
            
            order = self.execute_trade(opp)
            if order:
                executed_orders.append(order)
        
        return executed_orders
    
    def get_summary(self) -> Dict:
        """Get trading summary."""
        positions = self.clob.get_positions()
        trades = self.clob.get_trade_history()
        
        return {
            "mode": "PAPER" if self.paper_mode else "LIVE",
            "total_trades": len(trades),
            "open_positions": len(positions),
            "total_exposure": self.clob.get_total_exposure(),
            "markets_traded_today": len(self._traded_markets),
        }
    
    def print_summary(self):
        """Print detailed trading summary."""
        self.clob.print_summary()


# Test function
def test_trading():
    """Quick test of trading functionality."""
    logging.basicConfig(level=logging.INFO)
    
    trader = WeatherTrader(paper_mode=True, min_edge=0.10)
    
    # Simulate scanner result
    test_opportunities = [
        {
            "city": "nyc",
            "target_date": "2026-01-15",
            "bucket_low": 44,
            "bucket_high": 46,
            "bucket_unit": "F",
            "forecast_temp": 47,
            "forecast_std": 3.0,
            "market_price": 0.35,
            "calculated_probability": 0.52,
            "edge": 0.17,  # 17% edge
            "token_id": "test_token_nyc_44_46",
            "market_slug": "nyc-daily-high-temp-jan-15",
            "liquidity": 1500,
        },
        {
            "city": "london",
            "target_date": "2026-01-15",
            "bucket_low": 6,
            "bucket_high": 8,
            "bucket_unit": "C",
            "forecast_temp": 7,
            "forecast_std": 2.5,
            "market_price": 0.28,
            "calculated_probability": 0.48,
            "edge": 0.20,  # 20% edge
            "token_id": "test_token_london_6_8",
            "market_slug": "london-daily-high-temp-jan-15",
            "liquidity": 800,
        },
    ]
    
    orders = trader.process_scan_results(test_opportunities)
    
    print(f"\nExecuted {len(orders)} trades")
    trader.print_summary()
    
    return trader


if __name__ == "__main__":
    test_trading()
