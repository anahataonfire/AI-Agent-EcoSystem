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

from .config import ACTIVE_CITIES, SCAN_CONFIG, WeatherOpportunity
from .forecaster import get_forecaster, DailyForecast
from .scanner import get_scanner, WeatherMarket
from .edge_calculator import get_edge_calculator
from .alerter import get_alerter, test_telegram_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


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
            # Key by city (we'll match by date in edge calculator)
            forecasts[city] = forecast
    
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
        logger.info(f"Found {len(opportunities)} opportunities!")
        if dry_run:
            logger.info("DRY RUN - Not sending alerts")
            for opp in opportunities:
                print("\n" + "="*50)
                print(opp.to_alert_message())
        else:
            send_alerts(opportunities)
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
    
    args = parser.parse_args()
    
    if args.test_telegram:
        success = test_telegram_connection()
        sys.exit(0 if success else 1)
    
    opportunities = run_scan(
        cities=args.cities,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    
    logger.info(f"Scan complete. Found {len(opportunities)} opportunities.")
    return opportunities


if __name__ == "__main__":
    main()
