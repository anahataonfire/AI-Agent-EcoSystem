#!/usr/bin/env python3
"""
Weather Market Auto-Trader Daemon

Runs on a schedule to:
1. Scrape Polymarket for weather/temperature markets (via Playwright)
2. Calculate probability edge using our model
3. Execute trades when edge threshold is met

Usage:
    python scripts/weather_auto_trader.py          # Run once
    python scripts/weather_auto_trader.py --loop   # Run continuously
    python scripts/weather_auto_trader.py --live   # Enable live trading
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, date, timedelta, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.weather_trading.trader import WeatherTrader
from src.weather_trading.probability import calculate_bucket_probability
from src.weather_trading.forecaster import WeatherForecaster
from src.weather_trading.browser_scraper import get_scraped_markets

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


ACTIVE_CITIES = ['nyc', 'london', 'seattle', 'toronto', 'atlanta']


def run_scan_and_trade(paper_mode: bool = True, min_edge: float = 0.15):
    """
    Run one scan cycle: scrape markets, analyze, trade.
    
    Args:
        paper_mode: If True, simulate trades. If False, execute real trades.
        min_edge: Minimum edge threshold (e.g., 0.15 = 15%)
    """
    logger.info("=" * 60)
    logger.info("WEATHER AUTO-TRADER SCAN")
    logger.info(f"Mode: {'PAPER' if paper_mode else 'LIVE'} | Min Edge: {min_edge*100:.0f}%")
    logger.info("=" * 60)
    
    # Step 1: Scrape current markets
    logger.info("Scraping Polymarket for weather markets...")
    try:
        markets = get_scraped_markets(force_refresh=True)
    except Exception as e:
        logger.error(f"Failed to scrape markets: {e}")
        return []
    
    logger.info(f"Found {len(markets)} temperature markets")
    
    # Filter to active/tradeable markets (today or tomorrow only)
    today = date.today().strftime("%Y-%m-%d")
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    tradeable = [m for m in markets 
                 if m.city_key in ACTIVE_CITIES 
                 and m.target_date in [today, tomorrow]
                 and m.yes_price > 0.01]  # Skip already-resolved markets
    
    logger.info(f"Tradeable markets (today/tomorrow): {len(tradeable)}")
    
    if not tradeable:
        logger.info("No tradeable markets found.")
        return []
    
    # Step 2: Get forecasts and calculate edge
    forecaster = WeatherForecaster()
    forecast_cache = {}  # Cache forecasts per city/date to avoid duplicate API calls
    opportunities = []
    
    for market in tradeable:
        try:
            # Use cached forecast if available
            cache_key = f"{market.city_key}_{market.target_date}"
            if cache_key in forecast_cache:
                fc = forecast_cache[cache_key]
            else:
                fc = forecaster.get_daily_high_forecast(market.city_key, market.target_date)
                forecast_cache[cache_key] = fc
            
            if not fc:
                continue
            
            forecast_temp = fc.high_f
            forecast_std = fc.uncertainty or 3.0
            
            # Calculate our probability
            our_prob = calculate_bucket_probability(
                forecast_temp, 
                forecast_std,
                market.bucket_low,
                market.bucket_high
            )
            
            # Calculate edge
            market_price = market.yes_price
            edge = our_prob - market_price
            
            if edge >= min_edge:
                logger.info(
                    f"🎯 EDGE: {market.city_key} {market.target_date} "
                    f"{market.bucket_low}-{market.bucket_high}°{market.bucket_unit} | "
                    f"Edge: {edge*100:.1f}% (our: {our_prob*100:.0f}% vs mkt: {market_price*100:.0f}%)"
                )
                
                opportunities.append({
                    'city': market.city_key,
                    'target_date': market.target_date,
                    'bucket_low': market.bucket_low,
                    'bucket_high': market.bucket_high,
                    'bucket_unit': market.bucket_unit,
                    'forecast_temp': forecast_temp,
                    'forecast_std': forecast_std,
                    'market_price': market_price,
                    'calculated_probability': our_prob,
                    'edge': edge,
                    'token_id': market.condition_id,
                    'market_slug': market.slug,
                    'liquidity': market.liquidity,
                })
                
        except Exception as e:
            logger.debug(f"Error analyzing {market.city_key}: {e}")
            continue
    
    logger.info(f"Found {len(opportunities)} opportunities above {min_edge*100:.0f}% edge")
    
    if not opportunities:
        return []
    
    # Step 3: Execute trades
    trader = WeatherTrader(paper_mode=paper_mode, min_edge=min_edge)
    orders = trader.process_scan_results(opportunities)
    
    if orders:
        logger.info(f"✅ Executed {len(orders)} trade(s)")
        trader.print_summary()
    
    return orders


def main():
    parser = argparse.ArgumentParser(description="Weather Market Auto-Trader")
    parser.add_argument('--loop', action='store_true', 
                       help='Run continuously (every 15 minutes)')
    parser.add_argument('--interval', type=int, default=900,
                       help='Scan interval in seconds (default: 900 = 15 min)')
    parser.add_argument('--live', action='store_true',
                       help='Enable LIVE trading (real money!)')
    parser.add_argument('--min-edge', type=float, default=0.15,
                       help='Minimum edge threshold (default: 0.15 = 15%%)')
    
    args = parser.parse_args()
    
    paper_mode = not args.live
    
    if not paper_mode:
        logger.warning("⚠️  LIVE TRADING MODE - Real money will be used!")
        logger.warning("⚠️  Position limits: $2/trade, $20 total exposure")
    
    if args.loop:
        logger.info(f"Starting auto-trader loop (every {args.interval}s)")
        logger.info(f"Mode: {'PAPER' if paper_mode else 'LIVE'}")
        logger.info("Press Ctrl+C to stop")
        
        while True:
            try:
                run_scan_and_trade(paper_mode=paper_mode, min_edge=args.min_edge)
                logger.info(f"Next scan in {args.interval} seconds...")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(60)  # Wait 1 min on error
    else:
        # Run once
        run_scan_and_trade(paper_mode=paper_mode, min_edge=args.min_edge)


if __name__ == "__main__":
    main()
