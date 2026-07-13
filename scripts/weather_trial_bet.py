#!/usr/bin/env python3
"""
Weather Trading - Trial Bet using Official Polymarket Client

This script uses the official py-clob-client to place a trade.
"""

import logging
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import our scanning components
from src.weather_trading.probability import calculate_bucket_probability
from src.weather_trading.forecaster import WeatherForecaster
from src.weather_trading.browser_scraper import get_scraped_markets

# Import official Polymarket client
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType

ACTIVE_CITIES = ['nyc', 'london', 'seattle', 'toronto', 'atlanta']


def find_best_opportunity():
    """Scan markets and find the best opportunity."""
    logger.info("=" * 60)
    logger.info("WEATHER TRIAL BET - Finding best opportunity")
    logger.info("=" * 60)
    
    logger.info("Scraping Polymarket for weather markets...")
    try:
        markets = get_scraped_markets(force_refresh=True)
    except Exception as e:
        logger.error(f"Failed to scrape markets: {e}")
        return None
    
    logger.info(f"Found {len(markets)} temperature markets")
    
    today = date.today().strftime("%Y-%m-%d")
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    tradeable = [m for m in markets 
                 if m.city_key in ACTIVE_CITIES 
                 and m.target_date in [today, tomorrow]
                 and m.yes_price > 0.01
                 and m.yes_price < 0.95]
    
    logger.info(f"Tradeable markets: {len(tradeable)}")
    
    if not tradeable:
        return None
    
    forecaster = WeatherForecaster()
    forecast_cache = {}
    all_opportunities = []
    
    for market in tradeable:
        try:
            cache_key = f"{market.city_key}_{market.target_date}"
            if cache_key in forecast_cache:
                fc = forecast_cache[cache_key]
            else:
                fc = forecaster.get_daily_high_forecast(market.city_key, market.target_date)
                forecast_cache[cache_key] = fc
            
            if not fc:
                continue
            
            forecast_temp = fc.high_f
            forecast_std = 2 + (1 - fc.confidence) * 5
            
            # Handle unit conversion
            bucket_low_f = market.bucket_low
            bucket_high_f = market.bucket_high
            if market.bucket_unit == 'C':
                bucket_low_f = market.bucket_low * 9/5 + 32 if market.bucket_low != float('-inf') else float('-inf')
                bucket_high_f = market.bucket_high * 9/5 + 32 if market.bucket_high != float('inf') else float('inf')
            
            our_prob = calculate_bucket_probability(forecast_temp, forecast_std, bucket_low_f, bucket_high_f)
            edge = our_prob - market.yes_price
            
            all_opportunities.append({
                'city': market.city_key,
                'target_date': market.target_date,
                'bucket_low': market.bucket_low,
                'bucket_high': market.bucket_high,
                'bucket_unit': market.bucket_unit,
                'forecast_temp': forecast_temp,
                'market_price': market.yes_price,
                'calculated_probability': our_prob,
                'edge': edge,
                'token_id': market.condition_id,
                'market_slug': market.slug,
            })
            
        except Exception as e:
            continue
    
    if not all_opportunities:
        return None
    
    all_opportunities.sort(key=lambda x: x['edge'], reverse=True)
    
    logger.info("\nTOP 5 OPPORTUNITIES:")
    for i, opp in enumerate(all_opportunities[:5], 1):
        logger.info(
            f"{i}. {opp['city'].upper()} {opp['target_date']} "
            f"{opp['bucket_low']}-{opp['bucket_high']}°{opp['bucket_unit']} | "
            f"Edge: {opp['edge']*100:+.1f}%"
        )
    
    return all_opportunities[0]


def execute_trade_with_official_client(opportunity: dict) -> bool:
    """Execute trade using official py-clob-client."""
    logger.info("\n" + "=" * 60)
    logger.info("🚀 EXECUTING TRADE WITH OFFICIAL CLIENT")
    logger.info("=" * 60)
    
    logger.info(f"Market: {opportunity['city'].upper()} {opportunity['target_date']}")
    logger.info(f"Token ID: {opportunity['token_id']}")
    logger.info(f"Edge: {opportunity['edge']*100:+.1f}%")
    logger.info(f"Price: {opportunity['market_price']*100:.1f}%")
    
    # Get credentials from environment
    api_key = os.getenv("POLYMARKET_API_KEY")
    api_secret = os.getenv("POLYMARKET_API_SECRET")
    api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE")
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
    
    if not all([api_key, api_secret, api_passphrase]):
        logger.error("Missing API credentials in .env")
        return False
    
    # Check if we have private key for signing
    if not private_key:
        logger.warning("No POLYMARKET_PRIVATE_KEY - checking if API creds work for order placement")
    
    try:
        # Initialize client with API credentials
        creds = ApiCreds(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
        )
        
        # Create client - Polygon mainnet chain_id=137
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=137,
            key=private_key if private_key else None,
            creds=creds,
        )
        
        logger.info("Connected to Polymarket CLOB")
        
        # Get current orderbook to verify token exists
        try:
            book = client.get_order_book(opportunity['token_id'])
            logger.info(f"Order book fetched - bids: {len(book.bids) if book.bids else 0}, asks: {len(book.asks) if book.asks else 0}")
        except Exception as e:
            logger.warning(f"Could not fetch order book: {e}")
        
        # Calculate size in shares: size_in_usd / price
        usd_size = 1.0  # $1 trial bet
        price = opportunity['market_price']
        shares = usd_size / price
        
        logger.info(f"Placing order: {shares:.2f} shares @ ${price:.2f} = ${usd_size:.2f}")
        
        # Build order
        order_args = OrderArgs(
            price=price,
            size=shares,
            side="BUY",
            token_id=opportunity['token_id'],
        )
        
        # Create and submit order
        signed_order = client.create_order(order_args)
        logger.info(f"Order created and signed")
        
        result = client.post_order(signed_order, OrderType.GTC)
        
        if result:
            logger.info(f"✅ ORDER SUBMITTED: {result}")
            return True
        else:
            logger.error("Order submission returned empty result")
            return False
            
    except Exception as e:
        logger.error(f"Trade failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    logger.info("🎯 WEATHER TRADING - TRIAL BET (Official Client)")
    
    opportunity = find_best_opportunity()
    
    if not opportunity:
        logger.error("No opportunities found")
        return False
    
    return execute_trade_with_official_client(opportunity)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
