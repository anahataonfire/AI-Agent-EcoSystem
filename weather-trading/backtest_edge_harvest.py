"""
Edge Harvesting Backtester

Strategy: Buy NO on extreme buckets far from forecast.
Collect 0.5-2% daily returns on near-certain outcomes.

Key question: How many bands away from forecast is "safe"?
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from urllib.request import urlopen, Request
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EdgeTrade:
    """A single edge harvest trade."""
    date: str
    city: str
    bucket_low: float
    bucket_high: float
    bucket_center: float
    forecast_temp: float
    actual_temp: float
    bands_away: int  # How many 2°F bands from forecast
    degrees_away: float  # Actual distance in °F
    no_price: float  # What we paid for NO
    potential_return_pct: float  # (1 - no_price) / no_price * 100
    outcome: str  # "WIN" or "LOSS"
    pnl: float  # Actual P&L
    position_size: float


@dataclass 
class EdgeHarvestResult:
    """Results of edge harvest backtest."""
    bands_threshold: int
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    total_invested: float
    roi_pct: float
    avg_return_per_trade: float
    losing_trades: List[EdgeTrade] = field(default_factory=list)
    all_trades: List[EdgeTrade] = field(default_factory=list)


# City coordinates
CITY_COORDS = {
    "nyc": {"lat": 40.7128, "lon": -74.0060, "name": "New York City"},
    "london": {"lat": 51.5074, "lon": -0.1278, "name": "London"},
    "atlanta": {"lat": 33.7490, "lon": -84.3880, "name": "Atlanta"},
    "seattle": {"lat": 47.6062, "lon": -122.3321, "name": "Seattle"},
    "toronto": {"lat": 43.6532, "lon": -79.3832, "name": "Toronto"},
}

# Standard bucket width in Polymarket weather markets
BUCKET_WIDTH = 2.0  # 2°F bands typically


class EdgeHarvestBacktester:
    """
    Backtests the edge harvesting strategy.
    
    Tests buying NO on buckets X bands away from forecast.
    """
    
    def __init__(
        self,
        min_return_pct: float = 0.5,  # Minimum 0.5% return to take trade
        max_per_bucket: float = 300.0,  # Max $300 per bucket
        max_per_day: float = 1000.0,  # Max $1000 per day
        bucket_width: float = 2.0,  # 2°F bands
        forecast_error_std: float = 2.5,  # Typical 24hr forecast error
    ):
        self.min_return_pct = min_return_pct
        self.max_per_bucket = max_per_bucket
        self.max_per_day = max_per_day
        self.bucket_width = bucket_width
        self.forecast_error_std = forecast_error_std
    
    def _fetch_json(self, url: str) -> dict:
        """Fetch JSON from URL."""
        try:
            req = Request(url, headers={"User-Agent": "EdgeHarvestBacktester/1.0"})
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return {}
    
    def fetch_historical_temps(
        self,
        city: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, float]:
        """Fetch actual historical high temperatures."""
        if city not in CITY_COORDS:
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
        
        logger.info(f"Fetched {len(actuals)} days for {city}")
        return actuals
    
    def simulate_forecast(self, actual: float, seed: int) -> float:
        """
        Simulate what a 24-48hr forecast would have been.
        
        NWS forecasts are typically within 2-3°F for 24hr predictions.
        We add gaussian noise to actuals to simulate forecast error.
        """
        random.seed(seed)
        # Heavy-tailed: 95% normal, 5% big bust
        if random.random() < 0.95:
            error = random.gauss(0, 2.5)
        else:
            error = random.gauss(0, 8.0)
        return actual + error
    
    def generate_buckets(self, center_temp: float, num_buckets: int = 10) -> List[Tuple[float, float]]:
        """
        Generate realistic bucket ranges around a temperature.
        
        Returns list of (low, high) tuples.
        """
        buckets = []
        
        # Start from well below to well above
        start = center_temp - (num_buckets * self.bucket_width)
        
        for i in range(num_buckets * 2 + 1):
            low = start + (i * self.bucket_width)
            high = low + self.bucket_width
            buckets.append((low, high))
        
        return buckets
    
    def estimate_no_price(self, forecast: float, bucket_low: float, bucket_high: float) -> float:
        """
        Estimate what the NO price would be for a bucket.
        
        Based on distance from forecast and typical market pricing.
        Markets price probability based on forecast distribution.
        """
        bucket_center = (bucket_low + bucket_high) / 2
        distance = abs(forecast - bucket_center)
        
        # Convert distance to approximate probability
        # Using gaussian CDF approximation
        # P(temp in bucket) decreases with distance
        z_score = distance / self.forecast_error_std
        
        # Approximate bucket probability
        if z_score < 0.5:
            yes_prob = 0.30  # Close to forecast
        elif z_score < 1.0:
            yes_prob = 0.15
        elif z_score < 1.5:
            yes_prob = 0.08
        elif z_score < 2.0:
            yes_prob = 0.04
        elif z_score < 2.5:
            yes_prob = 0.02
        elif z_score < 3.0:
            yes_prob = 0.01
        else:
            yes_prob = 0.005
        
        # NO price = 1 - YES price (with small spread)
        no_price = 1.0 - yes_prob + 0.005  # Add small spread
        return min(no_price, 0.995)  # Cap at 99.5%
    
    def calculate_bands_away(self, forecast: float, bucket_low: float, bucket_high: float) -> int:
        """
        Calculate how many bands away a bucket is from forecast.
        
        Returns positive integer (0 = forecast is in bucket).
        """
        if bucket_low <= forecast <= bucket_high:
            return 0
        
        if forecast < bucket_low:
            # Bucket is above forecast
            distance = bucket_low - forecast
        else:
            # Bucket is below forecast
            distance = forecast - bucket_high
        
        bands = int(distance / self.bucket_width)
        return bands
    
    def run_single_day(
        self,
        date: str,
        city: str,
        forecast: float,
        actual: float,
        bands_threshold: int,
        daily_budget: float
    ) -> List[EdgeTrade]:
        """
        Simulate trading for a single day.
        
        Args:
            bands_threshold: Only trade buckets >= this many bands away
        """
        trades = []
        spent = 0.0
        
        # Generate buckets
        buckets = self.generate_buckets(forecast)
        
        for bucket_low, bucket_high in buckets:
            if spent >= daily_budget:
                break
            
            bands_away = self.calculate_bands_away(forecast, bucket_low, bucket_high)
            
            # Skip if not far enough from forecast
            if bands_away < bands_threshold:
                continue
            
            # Get NO price
            no_price = self.estimate_no_price(forecast, bucket_low, bucket_high)
            
            # Calculate potential return
            potential_return = (1.0 - no_price) / no_price * 100
            
            # Skip if return too low
            if potential_return < self.min_return_pct:
                continue
            
            # Determine position size
            position_size = min(
                self.max_per_bucket,
                daily_budget - spent,
                self.max_per_bucket
            )
            
            if position_size < 10:  # Min $10 trade
                continue
            
            # Did we win? (actual temp NOT in this bucket)
            in_bucket = bucket_low <= actual <= bucket_high
            won = not in_bucket
            
            # Calculate P&L
            if won:
                # We paid no_price, receive $1.00
                pnl = position_size * (1.0 - no_price) / no_price
            else:
                # We lose our entire position
                pnl = -position_size
            
            trade = EdgeTrade(
                date=date,
                city=city,
                bucket_low=bucket_low,
                bucket_high=bucket_high,
                bucket_center=(bucket_low + bucket_high) / 2,
                forecast_temp=forecast,
                actual_temp=actual,
                bands_away=bands_away,
                degrees_away=abs(forecast - (bucket_low + bucket_high) / 2),
                no_price=no_price,
                potential_return_pct=potential_return,
                outcome="WIN" if won else "LOSS",
                pnl=pnl,
                position_size=position_size
            )
            
            trades.append(trade)
            spent += position_size
        
        return trades
    
    def run_backtest(
        self,
        cities: List[str] = None,
        days: int = 90,
        bands_threshold: int = 3
    ) -> EdgeHarvestResult:
        """
        Run backtest across cities and days.
        
        Args:
            bands_threshold: Only trade buckets >= this many bands from forecast
        """
        if cities is None:
            cities = ["nyc", "atlanta"]
        
        end_date = datetime.now() - timedelta(days=2)  # Data delay
        start_date = end_date - timedelta(days=days)
        
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        all_trades = []
        
        for city in cities:
            logger.info(f"Fetching data for {city}...")
            actuals = self.fetch_historical_temps(city, start_str, end_str)
            
            if not actuals:
                logger.warning(f"No data for {city}")
                continue
            
            for i, (date, actual) in enumerate(sorted(actuals.items())):
                # Simulate forecast
                forecast = self.simulate_forecast(actual, seed=hash(f"{city}_{date}"))
                
                # Run day's trades
                daily_trades = self.run_single_day(
                    date=date,
                    city=city,
                    forecast=forecast,
                    actual=actual,
                    bands_threshold=bands_threshold,
                    daily_budget=self.max_per_day / len(cities)
                )
                
                all_trades.extend(daily_trades)
        
        # Calculate results
        wins = sum(1 for t in all_trades if t.outcome == "WIN")
        losses = sum(1 for t in all_trades if t.outcome == "LOSS")
        total = len(all_trades)
        
        total_pnl = sum(t.pnl for t in all_trades)
        total_invested = sum(t.position_size for t in all_trades)
        
        result = EdgeHarvestResult(
            bands_threshold=bands_threshold,
            total_trades=total,
            wins=wins,
            losses=losses,
            win_rate=round(wins / total * 100, 2) if total > 0 else 0,
            total_pnl=round(total_pnl, 2),
            total_invested=round(total_invested, 2),
            roi_pct=round(total_pnl / total_invested * 100, 2) if total_invested > 0 else 0,
            avg_return_per_trade=round(total_pnl / total, 2) if total > 0 else 0,
            losing_trades=[t for t in all_trades if t.outcome == "LOSS"],
            all_trades=all_trades
        )
        
        return result
    
    def find_optimal_threshold(
        self,
        cities: List[str] = None,
        days: int = 90
    ) -> Dict[int, EdgeHarvestResult]:
        """
        Test different band thresholds to find optimal.
        
        Returns results for each threshold tested.
        """
        results = {}
        
        for bands in range(2, 7):  # Test 2-6 bands away
            logger.info(f"\n{'='*50}")
            logger.info(f"Testing {bands} bands threshold...")
            logger.info(f"{'='*50}")
            
            result = self.run_backtest(
                cities=cities,
                days=days,
                bands_threshold=bands
            )
            results[bands] = result
            
            logger.info(f"Bands: {bands} | Trades: {result.total_trades} | "
                       f"Win Rate: {result.win_rate}% | ROI: {result.roi_pct}%")
        
        return results


def print_report(result: EdgeHarvestResult):
    """Print detailed backtest report."""
    print("\n" + "=" * 70)
    print("EDGE HARVEST BACKTEST REPORT")
    print("=" * 70)
    print(f"Strategy: Buy NO on buckets >= {result.bands_threshold} bands from forecast")
    print()
    print(f"  Total Trades:     {result.total_trades}")
    print(f"  Wins:             {result.wins}")
    print(f"  Losses:           {result.losses}")
    print(f"  Win Rate:         {result.win_rate}%")
    print()
    print(f"  Total Invested:   ${result.total_invested:,.2f}")
    print(f"  Total P&L:        ${result.total_pnl:+,.2f}")
    print(f"  ROI:              {result.roi_pct:+.2f}%")
    print(f"  Avg Per Trade:    ${result.avg_return_per_trade:+.2f}")
    print()
    
    if result.losing_trades:
        print("-" * 70)
        print(f"LOSING TRADES ({len(result.losing_trades)} total)")
        print("-" * 70)
        for t in result.losing_trades[:20]:
            print(f"  {t.date} | {t.city:8} | {t.bucket_low:.0f}-{t.bucket_high:.0f}°F | "
                  f"Fcst: {t.forecast_temp:.1f}° | Actual: {t.actual_temp:.1f}° | "
                  f"Bands: {t.bands_away} | P&L: ${t.pnl:+.2f}")
    
    print("=" * 70)


def print_comparison(results: Dict[int, EdgeHarvestResult]):
    """Print comparison of different thresholds."""
    print("\n" + "=" * 70)
    print("THRESHOLD COMPARISON")
    print("=" * 70)
    print(f"{'Bands':>6} | {'Trades':>7} | {'Win%':>6} | {'Total P&L':>12} | {'ROI%':>8} | {'Losses':>7}")
    print("-" * 70)
    
    for bands, r in sorted(results.items()):
        print(f"{bands:>6} | {r.total_trades:>7} | {r.win_rate:>5.1f}% | "
              f"${r.total_pnl:>+10,.2f} | {r.roi_pct:>+7.2f}% | {r.losses:>7}")
    
    print("=" * 70)
    
    # Find optimal
    best = max(results.items(), key=lambda x: x[1].roi_pct)
    print(f"\nOPTIMAL: {best[0]} bands away")
    print(f"  → {best[1].win_rate}% win rate with {best[1].roi_pct}% ROI")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Edge Harvest Backtester")
    parser.add_argument("--cities", type=str, default="nyc,atlanta",
                        help="Comma-separated cities")
    parser.add_argument("--days", type=int, default=90,
                        help="Days to backtest")
    parser.add_argument("--bands", type=int, default=None,
                        help="Bands threshold (or test all if not specified)")
    parser.add_argument("--min-return", type=float, default=0.5,
                        help="Minimum return %% per trade")
    
    args = parser.parse_args()
    
    backtester = EdgeHarvestBacktester(
        min_return_pct=args.min_return,
        max_per_bucket=300.0,
        max_per_day=1000.0
    )
    
    cities = args.cities.split(",")
    
    if args.bands:
        # Single threshold
        result = backtester.run_backtest(cities=cities, days=args.days, bands_threshold=args.bands)
        print_report(result)
    else:
        # Compare all thresholds
        results = backtester.find_optimal_threshold(cities=cities, days=args.days)
        print_comparison(results)
        
        # Also print details for the best
        best_bands = max(results.items(), key=lambda x: x[1].roi_pct)[0]
        print_report(results[best_bands])
