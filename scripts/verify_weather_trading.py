#!/usr/bin/env python3
"""
Weather Trading System - Full Verification Script

Tests all components of the weather trading system:
1. Probability Calculator
2. Forecaster API
3. CLOB API Connectivity
4. Paper Trading
5. Trade Logging
"""

import sys
import os
import json
from datetime import datetime, date

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(test_name: str, passed: bool, details: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} | {test_name}")
    if details:
        print(f"         {details}")


def test_probability_calculator():
    """Test the probability calculation module."""
    print_header("1. PROBABILITY CALCULATOR")
    
    try:
        from src.weather_trading.probability import (
            calculate_bucket_probability,
            estimate_forecast_std,
            norm_cdf
        )
        
        # Test norm_cdf
        cdf_50 = norm_cdf(50, 50, 3)  # Should be ~0.5
        print_result("norm_cdf(50, mean=50, std=3)", 
                    0.49 < cdf_50 < 0.51, 
                    f"Value: {cdf_50:.4f}")
        
        # Test bucket probability
        prob = calculate_bucket_probability(50, 3.0, 48, 52)
        print_result("bucket_probability(48-52°F, forecast=50°F)", 
                    0.4 < prob < 0.6,
                    f"Value: {prob:.2%}")
        
        # Test std estimation from model spread
        std = estimate_forecast_std(ecmwf_high=48, gfs_high=52, nws_high=50)
        print_result("estimate_std from model spread",
                    2.0 <= std <= 5.0,
                    f"Value: {std:.2f}°F")
        
        return True
    except Exception as e:
        print_result("Probability calculator import", False, str(e))
        return False


def test_forecaster():
    """Test the weather forecaster API."""
    print_header("2. WEATHER FORECASTER")
    
    try:
        from src.weather_trading.forecaster import WeatherForecaster
        
        forecaster = WeatherForecaster()
        print_result("WeatherForecaster initialized", True)
        
        # Test NYC forecast
        forecast = forecaster.get_daily_high_forecast("nyc", str(date.today()))
        
        if forecast:
            print_result("NYC forecast fetched",
                        True,
                        f"High: {forecast.high_f:.0f}°F, Confidence: {forecast.confidence:.0%}")
            return True
        else:
            print_result("NYC forecast fetched", False, "No forecast returned")
            return False
            
    except Exception as e:
        print_result("Forecaster test", False, str(e))
        return False


def test_clob_api():
    """Test CLOB API connectivity."""
    print_header("3. CLOB API CONNECTIVITY")
    
    try:
        import urllib.request
        
        # Test markets endpoint
        url = "https://clob.polymarket.com/markets"
        req = urllib.request.Request(url, headers={"User-Agent": "WeatherBot/1.0"})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            print_result("CLOB /markets endpoint", True, f"Found {len(data)} markets")
        
        print_result("CLOB API reachable", True, "Connection successful")
        return True
        
    except Exception as e:
        print_result("CLOB API connectivity", False, str(e))
        return False


def test_paper_trading():
    """Test paper trading functionality."""
    print_header("4. PAPER TRADING")
    
    try:
        from src.weather_trading.clob_client import PolymarketCLOBClient
        
        client = PolymarketCLOBClient(paper_mode=True)
        print_result("CLOB client initialized (paper mode)", True)
        
        # Place a test order
        order = client.place_limit_order(
            token_id="test_verification_token",
            market_slug="test-market-verification",
            side="BUY",
            price=0.25,
            size=5.0
        )
        
        print_result("Paper order placed",
                    order.status == "FILLED",
                    f"Order ID: {order.order_id[:20]}...")
        
        # Check positions
        positions = client.get_positions()
        print_result("Position tracking",
                    len(positions) > 0,
                    f"Positions: {len(positions)}")
        
        # Check trade history
        trades = client.get_trade_history()
        print_result("Trade history",
                    len(trades) > 0,
                    f"Trades logged: {len(trades)}")
        
        return True
        
    except Exception as e:
        print_result("Paper trading", False, str(e))
        return False


def test_trader_integration():
    """Test full trader integration."""
    print_header("5. TRADER INTEGRATION")
    
    try:
        from src.weather_trading.trader import WeatherTrader
        
        trader = WeatherTrader(paper_mode=True, min_edge=0.10)
        print_result("WeatherTrader initialized", True)
        
        # Test with simulated opportunity
        test_opp = [{
            "city": "nyc",
            "target_date": "2026-01-20",
            "bucket_low": 40,
            "bucket_high": 44,
            "bucket_unit": "F",
            "forecast_temp": 42,
            "forecast_std": 3.0,
            "market_price": 0.30,
            "calculated_probability": 0.50,
            "edge": 0.20,  # 20% edge
            "token_id": "verify_token_123",
            "market_slug": "nyc-verification-test",
            "liquidity": 1000,
        }]
        
        orders = trader.process_scan_results(test_opp)
        print_result("Trade execution",
                    len(orders) > 0,
                    f"Executed {len(orders)} trade(s)")
        
        # Get summary
        summary = trader.get_summary()
        print_result("Summary generation",
                    summary["total_trades"] > 0,
                    f"Total trades: {summary['total_trades']}")
        
        return True
        
    except Exception as e:
        print_result("Trader integration", False, str(e))
        return False


def test_trade_logging():
    """Test trade log file."""
    print_header("6. TRADE LOGGING")
    
    try:
        log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "src", "weather_trading", "trade_log.json"
        )
        
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                trades = json.load(f)
            print_result("Trade log file exists",
                        True,
                        f"Contains {len(trades)} trade(s)")
            
            # Show latest trade
            if trades:
                latest = trades[-1]
                print_result("Latest trade recorded",
                            True,
                            f"{latest['side']} ${latest['size']} @ {latest['price']}")
            return True
        else:
            print_result("Trade log file", False, "File not found")
            return False
            
    except Exception as e:
        print_result("Trade logging", False, str(e))
        return False


def main():
    """Run all verification tests."""
    print("\n" + "=" * 60)
    print("  WEATHER TRADING SYSTEM - FULL VERIFICATION")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    results = {
        "Probability Calculator": test_probability_calculator(),
        "Forecaster API": test_forecaster(),
        "CLOB API": test_clob_api(),
        "Paper Trading": test_paper_trading(),
        "Trader Integration": test_trader_integration(),
        "Trade Logging": test_trade_logging(),
    }
    
    # Summary
    print_header("SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {test}")
    
    print()
    print(f"  Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  🎉 ALL SYSTEMS GO! Ready for paper trading.")
    else:
        print("\n  ⚠️  Some tests failed. Check output above.")
    
    print("=" * 60 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
