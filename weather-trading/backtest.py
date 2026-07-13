"""
Weather Trading Backtest
Analyzes historical edge calculations against actual outcomes.
"""
import sqlite3
import logging
import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from math import erf, sqrt
from config import EDGE_CONFIG

# Configuration (fallback if not in config.py)
DEFAULT_MIN_EDGE = 0.15
DEFAULT_STD_DEV = 2.0

logger = logging.getLogger(__name__)

@dataclass
class BacktestTrade:
    """A hypothetical historical trade."""
    city_key: str
    target_date: str
    bucket_low: float
    bucket_high: float
    side: str  # 'YES' or 'NO'
    entry_price: float
    edge: float
    bucket_probability: float
    actual_high_f: float
    outcome: str  # 'WIN' or 'LOSS'
    pnl: float  # profit/loss per $1 bet

def normal_cdf(x: float, mean: float, std: float) -> float:
    """CDF for normal distribution."""
    if std <= 0:
        return 1.0 if x >= mean else 0.0
    return 0.5 * (1 + erf((x - mean) / (std * sqrt(2))))

def bucket_probability(forecast_temp: float, bucket_low: float, bucket_high: float, std_dev: float = 2.0) -> float:
    """Calculate probability actual temp falls in bucket."""
    if bucket_low == float('-inf'):
        return normal_cdf(bucket_high, forecast_temp, std_dev)
    if bucket_high == float('inf'):
        return 1 - normal_cdf(bucket_low, forecast_temp, std_dev)
    return normal_cdf(bucket_high + 0.5, forecast_temp, std_dev) - normal_cdf(bucket_low - 0.5, forecast_temp, std_dev)

def temp_in_bucket(actual_temp: float, bucket_low: float, bucket_high: float) -> bool:
    """Check if actual temperature falls within bucket."""
    low = bucket_low if bucket_low != float('-inf') else -999
    high = bucket_high if bucket_high != float('inf') else 999
    return low <= actual_temp <= high

def run_backtest(
    min_edge: float = 0.15,
    std_dev: float = 2.0,
    min_price: float = 0.05,
    db_path: str = "weather_backtest.db"
) -> List[BacktestTrade]:
    """
    Run backtest against historical data.
    
    Logic:
    1. For each (city, date) with actual temp data
    2. Find all price snapshots for that city/date
    3. Use actual temp AS IF it were the forecast (perfect hindsight)
    4. Calculate edge = bucket_probability - market_price
    5. If edge >= min_edge AND price >= min_price, simulate a trade
    6. Determine WIN/LOSS based on whether actual temp hit the bucket
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all actuals
    cur.execute('SELECT city_key, date, actual_high_f FROM actual_temps')
    actuals = {(row[0], row[1]): row[2] for row in cur.fetchall()}
    
    if not actuals:
        logger.warning("No actual temperature data found")
        return []
    
    trades = []
    
    # For each actual, find matching price history
    for (city_key, target_date), actual_high in actuals.items():
        # Get distinct markets for this city/date
        cur.execute('''
            SELECT DISTINCT market_slug, bucket_low, bucket_high
            FROM poly_data_prices
            WHERE city_key = ? AND target_date = ?
        ''', (city_key, target_date))
        
        markets = cur.fetchall()
        
        for market_id, bucket_low, bucket_high in markets:
            # Check YES and NO sides
            for side in ['YES', 'NO']:
                cur.execute('''
                    SELECT price, timestamp FROM poly_data_prices
                    WHERE market_slug = ? AND side = ? AND price >= ?
                    ORDER BY timestamp DESC LIMIT 1
                ''', (market_id, side, min_price))
                
                row = cur.fetchone()
                if not row:
                    continue
                
                price = row[0]
                
                # Calculate bucket probability using actual temp as "forecast"
                prob = bucket_probability(actual_high, bucket_low, bucket_high, std_dev)
                
                if side == 'YES':
                    edge = prob - price
                    if edge >= min_edge:
                        hit = temp_in_bucket(actual_high, bucket_low, bucket_high)
                        outcome = 'WIN' if hit else 'LOSS'
                        pnl = (1 / price - 1) if hit else -1
                        
                        trades.append(BacktestTrade(
                            city_key=city_key,
                            target_date=target_date,
                            bucket_low=bucket_low,
                            bucket_high=bucket_high,
                            side='YES',
                            entry_price=price,
                            edge=edge,
                            bucket_probability=prob,
                            actual_high_f=actual_high,
                            outcome=outcome,
                            pnl=pnl
                        ))
                
                elif side == 'NO':
                    # NO wins if temp is NOT in bucket
                    no_prob = 1 - prob
                    # Note: price in price_history is for that specific side
                    edge = no_prob - price
                    
                    if edge >= min_edge:
                        hit = not temp_in_bucket(actual_high, bucket_low, bucket_high)
                        outcome = 'WIN' if hit else 'LOSS'
                        pnl = (1 / price - 1) if hit else -1
                        
                        trades.append(BacktestTrade(
                            city_key=city_key,
                            target_date=target_date,
                            bucket_low=bucket_low,
                            bucket_high=bucket_high,
                            side='NO',
                            entry_price=price,
                            edge=edge,
                            bucket_probability=no_prob,
                            actual_high_f=actual_high,
                            outcome=outcome,
                            pnl=pnl
                        ))
    
    conn.close()
    return trades

def print_backtest_report(trades: List[BacktestTrade], min_edge: float, std_dev: float):
    """Print backtest results summary."""
    if not trades:
        print("No trades generated. Need more data or lower min_edge threshold.")
        return
    
    wins = [t for t in trades if t.outcome == 'WIN']
    losses = [t for t in trades if t.outcome == 'LOSS']
    
    total_pnl = sum(t.pnl for t in trades)
    win_rate = len(wins) / len(trades) * 100
    avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0
    
    print("\n" + "=" * 60)
    print("WEATHER TRADING BACKTEST RESULTS")
    print("=" * 60)
    print(f"Parameters: min_edge={min_edge:.0%}, std_dev={std_dev}°F")
    print(f"\nTotal Trades: {len(trades)}")
    print(f"Wins: {len(wins)} | Losses: {len(losses)}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"\nAvg Win: +{avg_win:.2%} | Avg Loss: {avg_loss:.2%}")
    print(f"Total PnL (per $1/trade): ${total_pnl:.2f}")
    
    # By city
    print("\n--- By City ---")
    cities = set(t.city_key for t in trades)
    for city in sorted(cities):
        city_trades = [t for t in trades if t.city_key == city]
        city_wins = len([t for t in city_trades if t.outcome == 'WIN'])
        city_wr = city_wins / len(city_trades) * 100 if city_trades else 0
        print(f"  {city:10}: {len(city_trades):3} trades, {city_wr:.0f}% win rate")
    
    # By edge bucket
    print("\n--- By Edge Level ---")
    for edge_min, edge_max, label in [(0.15, 0.25, "15-25%"), (0.25, 0.40, "25-40%"), (0.40, 1.0, "40%+")]:
        bucket_trades = [t for t in trades if edge_min <= t.edge < edge_max]
        if bucket_trades:
            bucket_wins = len([t for t in bucket_trades if t.outcome == 'WIN'])
            bucket_wr = bucket_wins / len(bucket_trades) * 100
            print(f"  Edge {label}: {len(bucket_trades):3} trades, {bucket_wr:.0f}% win rate")
    
    # Sample trades
    print("\n--- Sample Trades ---")
    for t in trades[:5]:
        emoji = "✅" if t.outcome == 'WIN' else "❌"
        print(f"  {emoji} {t.city_key} {t.target_date} | {t.bucket_low}-{t.bucket_high}°F {t.side}")
        print(f"     Price: {t.entry_price:.2f} | Edge: {t.edge:.0%} | Actual: {t.actual_high_f:.0f}°F | PnL: {t.pnl:+.2%}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Weather Trading Backtest")
    parser.add_argument("--min-edge", type=float, default=0.15, help="Minimum edge threshold (default: 0.15)")
    parser.add_argument("--std-dev", type=float, default=2.0, help="Forecast std dev in °F (default: 2.0)")
    parser.add_argument("--min-price", type=float, default=0.05, help="Minimum price to consider (default: 0.05)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(message)s")
    
    trades = run_backtest(min_edge=args.min_edge, std_dev=args.std_dev, min_price=args.min_price)
    print_backtest_report(trades, args.min_edge, args.std_dev)


if __name__ == "__main__":
    main()
