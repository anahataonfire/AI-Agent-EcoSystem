"""
Weather Trading Main Orchestrator

Coordinates forecast fetching, market scanning, edge calculation, and alerting.
Run via cron/launchd every 30 minutes.
"""

import argparse
import logging
import sys
from datetime import datetime, timezone, timedelta
from typing import List

from config import ACTIVE_CITIES, SCAN_CONFIG, EDGE_CONFIG, WeatherOpportunity
from forecaster import get_forecaster, DailyForecast
from scanner import get_scanner, WeatherMarket
from edge_calculator import get_edge_calculator
from alerter import get_alerter, test_telegram_connection
from position_sizer import PositionSizer
from executor import PolymarketExecutor, execute_opportunity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def categorize_opportunity(opp):
    """Categorize opportunity by confidence tier based on backtest results."""
    if opp.edge >= EDGE_CONFIG["min_edge_trade"]:
        return "HIGH"    # 80% win rate - TRADE
    elif opp.edge >= EDGE_CONFIG["min_edge_alert"]:
        return "MEDIUM"  # 29% win rate - ALERT ONLY
    else:
        return "LOW"     # 2% win rate - IGNORE


def fetch_forecasts(cities: List[str], target_date: str) -> dict:
    """
    Fetch forecasts for all cities.
    
    Returns dict mapping city_key -> DailyForecast
    """
    forecaster = get_forecaster()
    forecasts = {}
    
    for city in cities:
        logger.info(f"Fetching forecast for {city}...")
        forecast = forecaster.get_daily_high_forecast(city, target_date)
        if forecast:
            forecasts[city] = forecast
            logger.info(f"  → High: {forecast.high_f:.0f}°F (confidence: {forecast.confidence:.0%})")
        else:
            logger.warning(f"  → Failed to get forecast for {city}")
    
    return forecasts


def scan_markets(cities: List[str]) -> List[WeatherMarket]:
    """
    Scan Polymarket for weather markets.
    """
    scanner = get_scanner()
    markets = scanner.fetch_weather_markets(city_filter=cities)
    
    logger.info(f"Found {len(markets)} weather markets")
    for market in markets[:5]:  # Log first 5
        logger.info(
            f"  → {market.city}: {market.bucket_low}-{market.bucket_high}°{market.bucket_unit} "
            f"@ {market.yes_price:.2f} ({market.hours_remaining:.1f}hr)"
        )
    
    return markets


def find_opportunities(
    markets: List[WeatherMarket],
    forecasts: dict
) -> List[WeatherOpportunity]:
    """
    Calculate edge for all markets and return opportunities.
    """
    calculator = get_edge_calculator()
    opportunities = calculator.find_opportunities(markets, forecasts)
    
    return opportunities


def send_alerts(opportunities: List[WeatherOpportunity]) -> int:
    """
    Send Telegram alerts for opportunities.
    """
    alerter = get_alerter()
    
    if not alerter.is_configured:
        logger.warning("Telegram not configured - printing to console instead")
        for opp in opportunities:
            print("\n" + "="*50)
            print(opp.to_alert_message())
        return len(opportunities)
    
    if opportunities:
        sent = alerter.send_batch_alert(opportunities)
        logger.info(f"Sent {sent} Telegram alerts")
        return sent
    else:
        # Optionally notify on no opportunities (disabled by default to reduce noise)
        # alerter.send_no_opportunities_message()
        logger.info("No opportunities found")
        return 0


def run_scan(
    cities: List[str] = None,
    dry_run: bool = False,
    verbose: bool = False
) -> List[WeatherOpportunity]:
    """
    Run full weather trading scan.
    
    Args:
        cities: Cities to scan (default: ACTIVE_CITIES)
        dry_run: If True, don't send alerts (just print)
        verbose: If True, increase logging verbosity
        
    Returns:
        List of opportunities found
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if cities is None:
        cities = ACTIVE_CITIES
    
    logger.info(f"Starting weather trading scan for: {cities}")
    
    # Determine target date(s)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Fetch forecasts for today and tomorrow
    logger.info(f"Fetching forecasts for {today} and {tomorrow}...")
    forecasts = {}
    for date in [today, tomorrow]:
        date_forecasts = fetch_forecasts(cities, date)
        for city, forecast in date_forecasts.items():
            # Key by (city, date) for precise matching in edge calculator
            forecasts[(city, date)] = forecast
    
    # Scan markets
    logger.info("Scanning Polymarket weather markets...")
    markets = scan_markets(cities)
    
    if not markets:
        logger.warning("No weather markets found")
        return []
    
    # Find opportunities
    logger.info("Calculating edge for markets...")
    opportunities = find_opportunities(markets, forecasts)
    
    # Send alerts
    if opportunities:
        # Group by tier
        tiered = {"HIGH": [], "MEDIUM": [], "LOW": []}
        for opp in opportunities:
            tier = categorize_opportunity(opp)
            tiered[tier].append(opp)
        
        logger.info(f"Scan found {len(opportunities)} opportunities:")
        print("\n" + "!"*60)
        print("WEATHER TRADING SCAN RESULTS (Validated Tiers)")
        print("!"*60)
        
        for tier, label, emoji in [
            ("HIGH", "EXECUTE TRADE (80% Win Rate)", "🟢"),
            ("MEDIUM", "MONITOR ONLY (29% Win Rate)", "🟡"),
            ("LOW", "SKIP (2% Win Rate)", "🔴")
        ]:
            if tiered[tier]:
                print(f"\n{emoji} {label}:")
                for opp in tiered[tier]:
                    print(f"  → {opp.city.upper()}: {opp.bucket_low}-{opp.bucket_high}°{opp.bucket_unit} ({opp.edge*100:.0f}% edge)")
        
        if not dry_run:
            # Only send alerts for HIGH and MEDIUM by default
            to_alert = tiered["HIGH"] + tiered["MEDIUM"]
            if to_alert:
                send_alerts(to_alert)
        else:
            logger.info("DRY RUN - Not sending Telegram alerts")
    else:
        logger.info("No opportunities found with sufficient edge")
    
    return opportunities


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Weather Trading Scanner - Find mispriced Polymarket weather markets"
    )
    parser.add_argument(
        "--cities",
        nargs="+",
        default=None,
        help=f"Cities to scan (default: {ACTIVE_CITIES})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't send Telegram alerts, just print"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Test Telegram connection and exit"
    )
    parser.add_argument("--bankroll", type=float, default=1000.0, help="Total bankroll for sizing (default: 1000.0)")
    parser.add_argument("--live", action="store_true", help="Execute real trades (requires configuration)")
    
    args = parser.parse_args()
    
    if args.test_telegram:
        success = test_telegram_connection()
        sys.exit(0 if success else 1)
    
    opportunities = run_scan(
        cities=args.cities,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    # Initialize sizing and execution
    sizer = PositionSizer(bankroll=args.bankroll)
    executor = PolymarketExecutor(dry_run=not args.live)
    
    # Process HIGH confidence opportunities (80% Win Rate tier)
    executed = []
    # Filter for High Confidence (40%+ edge) and valid pricing (>5 cents)
    for opp in [o for o in opportunities if o.edge >= 0.40 and o.yes_price >= 0.05]:
        pos = sizer.calculate(edge=opp.edge, entry_price=opp.yes_price, liquidity=getattr(opp, 'liquidity', 500))
        
        if pos.recommended_size < 1.0:
            continue
        
        print(f"\n🟢 EXECUTING: {opp.city.upper()} {opp.target_date}")
        print(f"   BUY YES @ {opp.yes_price*100:.1f}¢ | Edge: {opp.edge*100:.1f}%")
        print(f"   Position: ${pos.recommended_size:.2f}")
        
        result = execute_opportunity(executor, opp, pos.recommended_size)
        if result.success:
            sizer.reserve(pos.recommended_size)
            executed.append((opp, pos.recommended_size))
            print(f"   ✅ Order: {result.order_id}")
        else:
            print(f"   ❌ Error: {result.error}")
    
    if executed:
        print(f"\n{'='*50}")
        print(f"TRADING SUMMARY")
        print(f"Executed: {len(executed)} trades")
        print(f"Deployed Cap: ${sum(s for _, s in executed):.2f}")
        print(f"Remaining Cap: ${sizer.available_capital():.2f}")
        print(f"{'='*50}")
    
    logger.info(f"Scan complete. Found {len(opportunities)} opportunities.")
    return opportunities


if __name__ == "__main__":
    main()
