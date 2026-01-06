"""
Polymarket Scanner Configuration

Configuration settings for the Polymarket Certainty Scanner.
"""

POLYMARKET_CONFIG = {
    # API Settings
    "base_url": "https://gamma-api.polymarket.com",
    "request_delay_seconds": 0.5,  # Rate limiting between requests
    "fetch_limit": 500,  # Max items per API request
    
    # Scanner Defaults
    "default_time_window_hours": 24,  # Default: markets ending within 24 hours
    "max_time_window_hours": 168,  # Maximum configurable window (1 week)
    "min_certainty_threshold": 0.90,  # 90% certainty (Yes >= 90% OR No >= 90%)
    "min_liquidity_usd": 100,  # Minimum liquidity to consider
    
    # Target Series (recurring daily/hourly markets)
    "target_series": [
        # Crypto Daily
        "btc-up-or-down-daily",
        "solana-up-or-down-daily",
        "eth-up-or-down-daily",
        "dogecoin-up-or-down-daily",
        "hyperliquid-up-or-down-daily",
        
        # Crypto 4H (these are the correct slugs!)
        "xrp-up-or-down-4h",
        "ethereum-up-or-down-4h",
        "solana-up-or-down-4h",
        "sol-up-or-down-4h",
        
        # Crypto Hourly
        "xrp-up-or-down-hourly",
        
        # Crypto Weekly
        "bitcoin-up-or-down-weekly",
        "ethereum-up-or-down-weekly",
        "ethbtc-up-or-down-weekly",
        
        # Stocks Daily
        "aapl-daily-up-down",
        "amzn-daily-up-down",
        "msft-daily-up-down",
        
        # Forex Daily
        "eurusd-daily-up-or-down",
        "usdjpy-daily-up-or-down",
        "gbpusd-daily-up-or-down",
        
        # Commodities Daily
        "xau-daily-up-or-down",  # Gold
        "cl-daily-up-or-down",   # Crude Oil
        "brent-crude-oil-daily-up-or-down",
    ],

    
    # Additional tags to scan from standard events
    "target_tags": [
        "crypto",
        "crypto-prices",
        "recurring",
        "politics",
        "geopolitics", 
        "world",
        "sports",
        "entertainment",
    ],
}

# APR Calculation Constants
HOURS_PER_YEAR = 8760
