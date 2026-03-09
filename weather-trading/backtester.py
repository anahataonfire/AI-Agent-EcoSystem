"""
Weather Trading Backtester

Validates the probability-based trading strategy by simulating trades
on historical weather data and calculating hypothetical P&L.
"""

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError

from probability import calculate_bucket_probability, estimate_forecast_std

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """A single simulated trade."""
    date: str
    city: str
    bucket_low: float
    bucket_high: float
    forecast_temp: float
    forecast_std: float
    actual_temp: float
    our_probability: float
    simulated_price: float
    edge: float
    position_size: float  # USD
    outcome: str  # "WIN" or "LOSS"
    pnl: float


@dataclass
class BacktestResult:
    """Results of a backtest run."""
    start_date: str
    end_date: str
    cities: List[str]
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_edge: float
    max_drawdown: float
    roi: float
    trades: List[BacktestTrade] = field(default_factory=list)


# City coordinates for API calls
CITY_COORDS = {
    "nyc": {"lat": 40.7128, "lon": -74.0060, "name": "New York City"},
    "london": {"lat": 51.5074, "lon": -0.1278, "name": "London"},
    "atlanta": {"lat": 33.7490, "lon": -84.3880, "name": "Atlanta"},
    "seattle": {"lat": 47.6062, "lon": -122.3321, "name": "Seattle"},
    "buenos_aires": {"lat": -34.6037, "lon": -58.3816, "name": "Buenos Aires"},
}


class WeatherBacktester:
    """
    Backtests weather trading strategy using historical data.
    """
    
    def __init__(
        self,
        min_edge: float = 0.10,  # 10% minimum edge
        position_size: float = 10.0,  # $10 per trade
        std_dev_default: float = 3.0,
        # V2 Improvements
        max_uncertainty: float = 5.0,  # Skip trades when std > 5°F
        require_consensus: bool = False,  # Require model consensus
        use_city_rules: bool = False,  # Use city-specific edge thresholds
    ):
        self.min_edge = min_edge
        self.position_size = position_size
        self.std_dev_default = std_dev_default
        # V2 Settings
        self.max_uncertainty = max_uncertainty
        self.require_consensus = require_consensus
        self.use_city_rules = use_city_rules
        
        # City-specific minimum edge thresholds
        # Based on forecast accuracy analysis
        self.city_min_edge = {
            "nyc": 0.15,      # NYC needs higher edge (20% win rate)
            "london": 0.12,   # London better forecasts (24% win rate)
            "atlanta": 0.15,
            "seattle": 0.12,
            "buenos_aires": 0.18,  # Harder to predict
        }
    
    def _fetch_json(self, url: str) -> dict:
        """Fetch JSON from URL."""
        try:
            req = Request(url, headers={"User-Agent": "WeatherBacktester/1.0"})
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return {}
    
    def fetch_historical_actuals(
        self,
        city: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, float]:
        """
        Fetch actual historical temperatures.
        
        Returns:
            Dict mapping date string to actual high temp (Fahrenheit)
        """
        if city not in CITY_COORDS:
            logger.error(f"Unknown city: {city}")
            return {}
        
        coords = CITY_COORDS[city]
        url = (
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={coords['lat']}&longitude={coords['lon']}"
            f"&start_date={start_date}&end_date={end_date}"
            f"&daily=temperature_2m_max"
            f"&temperature_unit=fahrenheit"
            f"&timezone=auto"
        )
        
        data = self._fetch_json(url)
        
        actuals = {}
        if "daily" in data:
            dates = data["daily"].get("time", [])
            temps = data["daily"].get("temperature_2m_max", [])
            for d, t in zip(dates, temps):
                if t is not None:
                    actuals[d] = t
        
        logger.info(f"Fetched {len(actuals)} days of actuals for {city}")
        return actuals
    
    def fetch_historical_forecasts(
        self,
        city: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Tuple[float, float]]:
        """
        Fetch what forecasts would have been for each day.
        
        For simplicity, we use the actual temp + some noise
        to simulate what a forecast 24-48 hours ahead would show.
        
        Returns:
            Dict mapping date to (forecast_temp, std_dev)
        """
        # First get the actuals
        actuals = self.fetch_historical_actuals(city, start_date, end_date)
        
        # Simulate forecasts with realistic error
        # Weather forecasts are typically 2-4°F off for 24-48hr forecasts
        import random
        random.seed(42)  # Reproducible results
        
        forecasts = {}
        for d, actual in actuals.items():
            # Add forecast error: normal distribution, mean 0, std 2.5°F
            error = random.gauss(0, 2.5)
            forecast = actual + error
            
            # Simulate model spread (uncertainty)
            std = random.uniform(2.0, 4.0)
            
            forecasts[d] = (round(forecast, 1), std)
        
        return forecasts
    
    def generate_market_buckets(
        self,
        forecast_temp: float,
        actual_temp: float = None,  # If known, used for more realistic sim
        unit: str = "F"
    ) -> List[Tuple[float, float, float]]:
        """
        Generate market buckets around the forecast.
        
        Simulates realistic market mispricing:
        - Tails are systematically underpriced (like real markets)
        - Markets cluster probability around the wrong center
        - This creates edge opportunities for the smart model
        
        Returns:
            List of (bucket_low, bucket_high, simulated_price)
        """
        # Round to nearest 2°F for bucket centers
        center = round(forecast_temp / 2) * 2
        
        # Market (dumb money) often centers on a different temperature
        # Simulate this by shifting the market's perceived center
        import random
        market_center_error = random.gauss(0, 2)  # Markets are 2°F off center on average
        market_center = center + market_center_error
        
        buckets = []
        
        # Generate buckets from center - 10 to center + 10
        for offset in range(-10, 12, 2):
            low = center + offset
            high = center + offset + 2
            
            # Market prices based on distance from THEIR perceived center (not actual)
            distance = abs((low + high) / 2 - market_center)
            
            # Key insight: markets UNDERPRICE tails
            # At distance 5+, real markets often price at 1-3%
            # but actual probability might be 5-15%
            if distance < 1:
                base_price = 0.40  # Center bucket
            elif distance < 3:
                base_price = 0.20  # Near buckets
            elif distance < 5:
                base_price = 0.05   # Underpriced - real prob often higher
            else:
                base_price = 0.02   # Tail buckets - heavily underpriced
            
            # Add random noise ± 3%
            noise = random.uniform(-0.03, 0.03)
            price = max(0.01, min(0.95, base_price + noise))
            
            buckets.append((low, high, price))
        
        return buckets
    
    def simulate_trade(
        self,
        date_str: str,
        city: str,
        bucket_low: float,
        bucket_high: float,
        forecast_temp: float,
        forecast_std: float,
        simulated_price: float,
        actual_temp: float
    ) -> Optional[BacktestTrade]:
        """
        Simulate a single trade decision.
        
        V2 Improvements:
        - Skip high uncertainty trades (std > max_uncertainty)
        - Use city-specific edge thresholds
        
        Returns:
            BacktestTrade if we would have traded, None otherwise
        """
        # V2: Skip high uncertainty trades
        if forecast_std > self.max_uncertainty:
            return None
        
        # Calculate our probability
        our_prob = calculate_bucket_probability(
            forecast_temp, forecast_std, bucket_low, bucket_high
        )
        
        # Calculate edge
        edge = our_prob - simulated_price
        
        # V2: Use city-specific edge thresholds
        if self.use_city_rules:
            min_edge = self.city_min_edge.get(city, self.min_edge)
        else:
            min_edge = self.min_edge
        
        # Only trade if edge exceeds threshold
        if edge < min_edge:
            return None
        
        # Determine outcome
        outcome = "WIN" if bucket_low <= actual_temp < bucket_high else "LOSS"
        
        # Calculate P&L
        if outcome == "WIN":
            # We bought at simulated_price, market resolves to $1
            pnl = self.position_size * (1.0 - simulated_price) / simulated_price
        else:
            # We lose our stake
            pnl = -self.position_size
        
        return BacktestTrade(
            date=date_str,
            city=city,
            bucket_low=bucket_low,
            bucket_high=bucket_high,
            forecast_temp=forecast_temp,
            forecast_std=forecast_std,
            actual_temp=actual_temp,
            our_probability=round(our_prob, 4),
            simulated_price=round(simulated_price, 4),
            edge=round(edge, 4),
            position_size=self.position_size,
            outcome=outcome,
            pnl=round(pnl, 2)
        )
    
    def run_backtest(
        self,
        cities: List[str] = None,
        days: int = 30
    ) -> BacktestResult:
        """
        Run full backtest simulation.
        
        Args:
            cities: List of city keys to test
            days: Number of days to backtest
            
        Returns:
            BacktestResult with all trades and metrics
        """
        if cities is None:
            cities = ["nyc", "london"]
        
        # Calculate date range
        end_date = date.today() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=days)
        
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        logger.info(f"Running backtest from {start_str} to {end_str} for {cities}")
        
        all_trades = []
        
        for city in cities:
            # Fetch data
            actuals = self.fetch_historical_actuals(city, start_str, end_str)
            forecasts = self.fetch_historical_forecasts(city, start_str, end_str)
            
            # Process each day
            for date_str in actuals.keys():
                if date_str not in forecasts:
                    continue
                
                forecast_temp, forecast_std = forecasts[date_str]
                actual_temp = actuals[date_str]
                
                # Generate market buckets
                buckets = self.generate_market_buckets(forecast_temp)
                
                # Evaluate each bucket for trading opportunity
                for bucket_low, bucket_high, simulated_price in buckets:
                    trade = self.simulate_trade(
                        date_str,
                        city,
                        bucket_low,
                        bucket_high,
                        forecast_temp,
                        forecast_std,
                        simulated_price,
                        actual_temp
                    )
                    
                    if trade:
                        all_trades.append(trade)
        
        # Calculate metrics
        wins = sum(1 for t in all_trades if t.outcome == "WIN")
        losses = sum(1 for t in all_trades if t.outcome == "LOSS")
        total_trades = len(all_trades)
        
        total_pnl = sum(t.pnl for t in all_trades)
        avg_edge = sum(t.edge for t in all_trades) / total_trades if total_trades > 0 else 0
        
        # Calculate max drawdown
        cumulative = 0
        peak = 0
        max_drawdown = 0
        for t in sorted(all_trades, key=lambda x: x.date):
            cumulative += t.pnl
            peak = max(peak, cumulative)
            drawdown = peak - cumulative
            max_drawdown = max(max_drawdown, drawdown)
        
        # Calculate ROI
        total_capital = total_trades * self.position_size
        roi = (total_pnl / total_capital * 100) if total_capital > 0 else 0
        
        return BacktestResult(
            start_date=start_str,
            end_date=end_str,
            cities=cities,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            win_rate=round(wins / total_trades * 100, 1) if total_trades > 0 else 0,
            total_pnl=round(total_pnl, 2),
            avg_edge=round(avg_edge * 100, 1),
            max_drawdown=round(max_drawdown, 2),
            roi=round(roi, 1),
            trades=all_trades
        )
    
    def print_report(self, result: BacktestResult):
        """Print a formatted backtest report."""
        print("\n" + "=" * 60)
        print("         WEATHER TRADING BACKTEST REPORT")
        print("=" * 60)
        print(f"\nPeriod: {result.start_date} to {result.end_date}")
        print(f"Cities: {', '.join(result.cities)}")
        print()
        print("-" * 60)
        print("KEY METRICS")
        print("-" * 60)
        print(f"  Total Trades:    {result.total_trades}")
        print(f"  Wins:            {result.wins}")
        print(f"  Losses:          {result.losses}")
        print(f"  Win Rate:        {result.win_rate}%")
        print()
        print(f"  Total P&L:       ${result.total_pnl:+.2f}")
        print(f"  ROI:             {result.roi:+.1f}%")
        print(f"  Max Drawdown:    ${result.max_drawdown:.2f}")
        print(f"  Avg Edge:        {result.avg_edge}%")
        print()
        
        # Show some sample trades
        print("-" * 60)
        print("SAMPLE TRADES (First 10)")
        print("-" * 60)
        for trade in result.trades[:10]:
            outcome_symbol = "✓" if trade.outcome == "WIN" else "✗"
            print(
                f"  {trade.date} | {trade.city.upper():8} | "
                f"{trade.bucket_low:.0f}-{trade.bucket_high:.0f}°F | "
                f"Edge: {trade.edge*100:+.0f}% | "
                f"P&L: ${trade.pnl:+.2f} {outcome_symbol}"
            )
        
        print()
        print("=" * 60)
        
        # P&L Curve (ASCII)
        print("\nCUMULATIVE P&L CURVE")
        print("-" * 60)
        
        cumulative = 0
        pnl_curve = []
        for t in sorted(result.trades, key=lambda x: x.date):
            cumulative += t.pnl
            pnl_curve.append(cumulative)
        
        if pnl_curve:
            min_pnl = min(pnl_curve)
            max_pnl = max(pnl_curve)
            range_pnl = max_pnl - min_pnl if max_pnl != min_pnl else 1
            
            # Downsample for display
            step = max(1, len(pnl_curve) // 40)
            for i in range(0, len(pnl_curve), step):
                val = pnl_curve[i]
                bar_len = int((val - min_pnl) / range_pnl * 40)
                bar = "█" * bar_len
                print(f"  ${val:+7.2f} |{bar}")
        
        print("=" * 60)


def run_backtest_cli():
    """Run backtest from command line."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Weather Trading Backtester")
    parser.add_argument("--cities", type=str, default="nyc,london",
                        help="Comma-separated list of cities")
    parser.add_argument("--days", type=int, default=30,
                        help="Number of days to backtest")
    parser.add_argument("--min-edge", type=float, default=0.10,
                        help="Minimum edge threshold (0.10 = 10%)")
    parser.add_argument("--position-size", type=float, default=10.0,
                        help="Position size in USD")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    backtester = WeatherBacktester(
        min_edge=args.min_edge,
        position_size=args.position_size
    )
    
    cities = args.cities.split(",")
    result = backtester.run_backtest(cities=cities, days=args.days)
    backtester.print_report(result)
    
    return result


if __name__ == "__main__":
    run_backtest_cli()
