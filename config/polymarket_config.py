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
    
    # Crypto tokens to search for daily "up-or-down-on-[date]" events
    # These generate unique events each day that aren't part of a series
    "crypto_daily_tokens": [
        "xrp", "btc", "bitcoin", "eth", "ethereum", "solana", "sol",
        "dogecoin", "doge", "cardano", "ada", "bnb", "avax", "link",
        "matic", "polkadot", "dot", "shib", "ltc", "atom", "uni",
    ],

    
    # Additional tags to scan from standard events
    # Expanded to cover all major categories for comprehensive discovery
    "target_tags": [
        # Core markets
        "crypto",
        "crypto-prices",
        "recurring",
        # Politics & World Events
        "politics",
        "geopolitics", 
        "world",
        "elections",
        "government",
        # Finance & Economy
        "finance",
        "stocks",
        "economics",
        "central-banks",
        # Tech & AI
        "tech",
        "ai",
        "science",
        # Entertainment & Sports
        "sports",
        "entertainment",
        "culture",
        # Other
        "weather",
        "legal",
    ],
    
    # Set to True to scan ALL active markets (ignores target_tags for broader discovery)
    "scan_all_active": True,
    
    # Pagination for comprehensive fetches
    "max_pages": 5,  # Max pagination iterations (5 x 500 = 2500 markets max)
}

# APR Calculation Constants
HOURS_PER_YEAR = 8760
