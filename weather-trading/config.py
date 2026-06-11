"""
Weather Trading Configuration

Configuration for weather bracket trading on Polymarket.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

# Cities with coordinates and forecast sources
# Format: (lat, lon, nws_gridpoint, timezone)
WEATHER_CITIES: Dict[str, Dict] = {
    "nyc": {
        "name": "New York City",
        "lat": 40.7128,
        "lon": -74.0060,
        "nws_office": "OKX",  # NWS forecast office
        "nws_grid": "33,37",  # NWS grid coordinates
        "timezone": "America/New_York",
        "resolution_source": "NWS",  # What Polymarket uses for settlement
    },
    "london": {
        "name": "London",
        "lat": 51.5074,
        "lon": -0.1278,
        "nws_office": None,  # No NWS for UK
        "nws_grid": None,
        "timezone": "Europe/London",
        "resolution_source": "Met Office",
    },
    "buenos_aires": {
        "name": "Buenos Aires",
        "lat": -34.6037,
        "lon": -58.3816,
        "nws_office": None,  # No NWS for Argentina
        "nws_grid": None,
        "timezone": "America/Argentina/Buenos_Aires",
        "resolution_source": "SMN Argentina",
    },
    "atlanta": {
        "name": "Atlanta",
        "lat": 33.7490,
        "lon": -84.3880,
        "nws_office": "FFC",
        "nws_grid": "52,88",
        "timezone": "America/New_York",
        "resolution_source": "NWS",
    },
    "seattle": {
        "name": "Seattle",
        "lat": 47.6062,
        "lon": -122.3321,
        "nws_office": "SEW",
        "nws_grid": "124,67",
        "timezone": "America/Los_Angeles",
        "resolution_source": "NWS",
    },
    "toronto": {
        "name": "Toronto",
        "lat": 43.6532,
        "lon": -79.3832,
        "nws_office": None,  # No NWS for Canada
        "nws_grid": None,
        "timezone": "America/Toronto",
        "resolution_source": "Environment Canada",
    },
    "chicago": {
        "name": "Chicago",
        "lat": 41.8781,
        "lon": -87.6298,
        "nws_office": "LOT",
        "nws_grid": "65,76",
        "timezone": "America/Chicago",
        "resolution_source": "NWS",
    },
    "paris": {
        "name": "Paris",
        "lat": 48.8566,
        "lon": 2.3522,
        "nws_office": None,
        "nws_grid": None,
        "timezone": "Europe/Paris",
        "resolution_source": "Meteo-France",
    },
    "ankara": {
        "name": "Ankara",
        "lat": 39.9334,
        "lon": 32.8597,
        "nws_office": None,
        "nws_grid": None,
        "timezone": "Europe/Istanbul",
        "resolution_source": "Turkish State Meteorological Service",
    },
    "madrid": {
        "name": "Madrid",
        "lat": 40.4168,
        "lon": -3.7038,
        "nws_office": None,
        "nws_grid": None,
        "timezone": "Europe/Madrid",
        "resolution_source": "AEMET",
    },
    "dallas": {
        "name": "Dallas",
        "lat": 32.7767,
        "lon": -96.7970,
        "nws_office": "FWD",
        "nws_grid": "80,108",
        "timezone": "America/Chicago",
        "resolution_source": "NWS",
    },
    "seoul": {
        "name": "Seoul",
        "lat": 37.5665,
        "lon": 126.9780,
        "nws_office": None,
        "nws_grid": None,
        "timezone": "Asia/Seoul",
        "resolution_source": "KMA",
    },
    "los_angeles": {
        "name": "Los Angeles",
        "lat": 34.0522,
        "lon": -118.2437,
        "nws_office": "LOX",
        "nws_grid": "154,44",
        "timezone": "America/Los_Angeles",
        "resolution_source": "NWS",
    },
    "miami": {
        "name": "Miami",
        "lat": 25.7617,
        "lon": -80.1918,
        "nws_office": "MFL",
        "nws_grid": "75,67",
        "timezone": "America/New_York",
        "resolution_source": "NWS",
    },
    "denver": {
        "name": "Denver",
        "lat": 39.7392,
        "lon": -104.9903,
        "nws_office": "BOU",
        "nws_grid": "62,60",
        "timezone": "America/Denver",
        "resolution_source": "NWS",
    },
    "tokyo": {
        "name": "Tokyo",
        "lat": 35.6762,
        "lon": 139.6503,
        "nws_office": None,
        "nws_grid": None,
        "timezone": "Asia/Tokyo",
        "resolution_source": "JMA",
    },
    "berlin": {
        "name": "Berlin",
        "lat": 52.5200,
        "lon": 13.4050,
        "nws_office": None,
        "nws_grid": None,
        "timezone": "Europe/Berlin",
        "resolution_source": "DWD",
    },
    "sydney": {
        "name": "Sydney",
        "lat": -33.8688,
        "lon": 151.2093,
        "nws_office": None,
        "nws_grid": None,
        "timezone": "Australia/Sydney",
        "resolution_source": "BOM",
    },
    "mexico_city": {
        "name": "Mexico City",
        "lat": 19.4326,
        "lon": -99.1332,
        "nws_office": None,
        "nws_grid": None,
        "timezone": "America/Mexico_City",
        "resolution_source": "SMN Mexico",
    },
    # PD-321 G5 rotation expansion — 28 cities from Polymarket's full daily-temperature
    # rotation, added 2026-05-26. NWS office/grid left None for the US cities here
    # (Austin/Houston/San Francisco) — Open-Meteo coverage is sufficient; operator can
    # backfill NWS grids later if needed.
    "amsterdam": {"name": "Amsterdam", "lat": 52.3676, "lon": 4.9041, "nws_office": None, "nws_grid": None, "timezone": "Europe/Amsterdam", "resolution_source": "KNMI"},
    "austin": {"name": "Austin", "lat": 30.2672, "lon": -97.7431, "nws_office": None, "nws_grid": None, "timezone": "America/Chicago", "resolution_source": "NWS"},
    "beijing": {"name": "Beijing", "lat": 39.9042, "lon": 116.4074, "nws_office": None, "nws_grid": None, "timezone": "Asia/Shanghai", "resolution_source": "CMA"},
    "busan": {"name": "Busan", "lat": 35.1796, "lon": 129.0756, "nws_office": None, "nws_grid": None, "timezone": "Asia/Seoul", "resolution_source": "KMA"},
    "cape_town": {"name": "Cape Town", "lat": -33.9249, "lon": 18.4241, "nws_office": None, "nws_grid": None, "timezone": "Africa/Johannesburg", "resolution_source": "SAWS"},
    "chengdu": {"name": "Chengdu", "lat": 30.5728, "lon": 104.0668, "nws_office": None, "nws_grid": None, "timezone": "Asia/Shanghai", "resolution_source": "CMA"},
    "chongqing": {"name": "Chongqing", "lat": 29.4316, "lon": 106.9123, "nws_office": None, "nws_grid": None, "timezone": "Asia/Shanghai", "resolution_source": "CMA"},
    "guangzhou": {"name": "Guangzhou", "lat": 23.1291, "lon": 113.2644, "nws_office": None, "nws_grid": None, "timezone": "Asia/Shanghai", "resolution_source": "CMA"},
    "helsinki": {"name": "Helsinki", "lat": 60.1699, "lon": 24.9384, "nws_office": None, "nws_grid": None, "timezone": "Europe/Helsinki", "resolution_source": "FMI"},
    "houston": {"name": "Houston", "lat": 29.7604, "lon": -95.3698, "nws_office": None, "nws_grid": None, "timezone": "America/Chicago", "resolution_source": "NWS"},
    "istanbul": {"name": "Istanbul", "lat": 41.0082, "lon": 28.9784, "nws_office": None, "nws_grid": None, "timezone": "Europe/Istanbul", "resolution_source": "Turkish State Meteorological Service"},
    "jakarta": {"name": "Jakarta", "lat": -6.2088, "lon": 106.8456, "nws_office": None, "nws_grid": None, "timezone": "Asia/Jakarta", "resolution_source": "BMKG"},
    "jeddah": {"name": "Jeddah", "lat": 21.4858, "lon": 39.1925, "nws_office": None, "nws_grid": None, "timezone": "Asia/Riyadh", "resolution_source": "NCM"},
    "karachi": {"name": "Karachi", "lat": 24.8607, "lon": 67.0011, "nws_office": None, "nws_grid": None, "timezone": "Asia/Karachi", "resolution_source": "PMD"},
    "kuala_lumpur": {"name": "Kuala Lumpur", "lat": 3.1390, "lon": 101.6869, "nws_office": None, "nws_grid": None, "timezone": "Asia/Kuala_Lumpur", "resolution_source": "MMD"},
    "lucknow": {"name": "Lucknow", "lat": 26.8467, "lon": 80.9462, "nws_office": None, "nws_grid": None, "timezone": "Asia/Kolkata", "resolution_source": "IMD"},
    "manila": {"name": "Manila", "lat": 14.5995, "lon": 120.9842, "nws_office": None, "nws_grid": None, "timezone": "Asia/Manila", "resolution_source": "PAGASA"},
    "milan": {"name": "Milan", "lat": 45.4642, "lon": 9.1900, "nws_office": None, "nws_grid": None, "timezone": "Europe/Rome", "resolution_source": "ARPA Lombardia"},
    "moscow": {"name": "Moscow", "lat": 55.7558, "lon": 37.6173, "nws_office": None, "nws_grid": None, "timezone": "Europe/Moscow", "resolution_source": "Roshydromet"},
    "munich": {"name": "Munich", "lat": 48.1351, "lon": 11.5820, "nws_office": None, "nws_grid": None, "timezone": "Europe/Berlin", "resolution_source": "DWD"},
    "panama_city": {"name": "Panama City", "lat": 8.9824, "lon": -79.5199, "nws_office": None, "nws_grid": None, "timezone": "America/Panama", "resolution_source": "ETESA"},
    "qingdao": {"name": "Qingdao", "lat": 36.0671, "lon": 120.3826, "nws_office": None, "nws_grid": None, "timezone": "Asia/Shanghai", "resolution_source": "CMA"},
    "san_francisco": {"name": "San Francisco", "lat": 37.7749, "lon": -122.4194, "nws_office": None, "nws_grid": None, "timezone": "America/Los_Angeles", "resolution_source": "NWS"},
    "sao_paulo": {"name": "São Paulo", "lat": -23.5505, "lon": -46.6333, "nws_office": None, "nws_grid": None, "timezone": "America/Sao_Paulo", "resolution_source": "INMET"},
    "shenzhen": {"name": "Shenzhen", "lat": 22.5431, "lon": 114.0579, "nws_office": None, "nws_grid": None, "timezone": "Asia/Shanghai", "resolution_source": "CMA"},
    "singapore": {"name": "Singapore", "lat": 1.3521, "lon": 103.8198, "nws_office": None, "nws_grid": None, "timezone": "Asia/Singapore", "resolution_source": "MSS"},
    "warsaw": {"name": "Warsaw", "lat": 52.2297, "lon": 21.0122, "nws_office": None, "nws_grid": None, "timezone": "Europe/Warsaw", "resolution_source": "IMGW"},
    "wellington": {"name": "Wellington", "lat": -41.2865, "lon": 174.7762, "nws_office": None, "nws_grid": None, "timezone": "Pacific/Auckland", "resolution_source": "MetService NZ"},
}

# Active cities to scan — add markets as Polymarket lists them
ACTIVE_CITIES = [
    # US cities (NWS resolution source)
    "nyc", "atlanta", "seattle", "chicago", "dallas", "los_angeles", "miami", "denver",
    # International cities (Open-Meteo only)
    "london", "toronto", "buenos_aires", "paris", "ankara", "madrid",
    "seoul", "tokyo", "berlin", "sydney", "mexico_city",
    # PD-321 G5 rotation expansion — 28 cities from Polymarket's full daily-temperature
    # rotation. Added 2026-05-26.
    "amsterdam", "austin", "beijing", "busan", "cape_town", "chengdu", "chongqing",
    "guangzhou", "helsinki", "houston", "istanbul", "jakarta", "jeddah", "karachi",
    "kuala_lumpur", "lucknow", "manila", "milan", "moscow", "munich", "panama_city",
    "qingdao", "san_francisco", "sao_paulo", "shenzhen", "singapore", "warsaw",
    "wellington",
]

# Edge calculation settings
#
# YES-side thresholds (backtester.py simulation, 1,212 trades, Jan 2026):
#   40%+ edge:  80% win rate (410 trades) ← PRIMARY THRESHOLD
#   25-40% edge: 29% win rate (504 trades) ← SECONDARY/ALERT ONLY
#   15-25% edge:  2% win rate (298 trades) ← DO NOT TRADE
# Caveat: backtester uses synthetic market prices (gauss-offset forecast + baked-in
# tail-underpricing prior) with real actual_temps for resolution. Not a real-market backtest.
#
# NO-side thresholds: UNVALIDATED. PD-193 (Open-Meteo historical backtest against real
# poly_data_prices) will produce per-side win-rate tables. Until then, short-side signals
# surface on the dashboard but do NOT auto-execute (see EXECUTION_CONFIG below).
#
EDGE_CONFIG = {
    "min_edge_trade": 0.40,      # Minimum |edge| to execute trade (YES: 80% win rate; NO: unvalidated)
    "min_edge_alert": 0.25,      # Minimum |edge| to generate alert
    "min_edge_scan": 0.15,       # Minimum |edge| to log/track (data collection)
    "std_dev_default": 2.5,      # Forecast uncertainty in °F
    "confidence_weight": True,   # Weight edge by forecast confidence
}

# Alerting thresholds
ALERT_CONFIG = {
    "high_confidence_edge": 0.40,   # Send immediate alert
    "medium_confidence_edge": 0.25, # Log but don't alert by default
    "min_liquidity": 100,           # Minimum $ liquidity to consider
    "max_hours_to_resolution": 48,  # Don't trade markets >48h out
}

# Scanning configuration
SCAN_CONFIG = {
    "scan_interval_minutes": 30,  # Normal scan frequency
    "near_resolution_interval_minutes": 15,  # When <6hr to resolution
    "near_resolution_hours": 6,  # Threshold for faster scanning
    "max_hours_to_resolution": 48,  # Only look at markets resolving within 48hr
}

# Position sizing (conservative defaults)
POSITION_CONFIG = {
    "default_position_usd": 10,  # Default suggestion
    "high_edge_position_usd": 20,  # When edge > 25%
    "max_position_usd": 50,  # Never suggest more than this
}

# Execution gating (PD-191, revised 2026-04-22)
# Short-side (BUY NO) dashboard-clicked trades are ENABLED after PD-193 backtest
# passed (156 trades, 78.8% win rate at |edge| ≥ 40%, +58.8pts over breakeven).
# Manual-execution only: scheduled auto-traders have been unloaded from launchd.
# Operator will re-engage auto-execution on observed live performance, not backtest.
EXECUTION_CONFIG = {
    "short_side_execution_enabled": True,
}

# PD-351 server-side trade gates. Grounded in the realized book (736 settled,
# Feb–Jun 2026): NO at p>=0.95 was net −$1,170 on $77k deployed (win% at or
# below breakeven — tail losses eat the pennies); the 0.85–0.95 band was +6.5%
# ROI; open-ended extreme buckets and basis-suspect cities produced the four
# largest losses; losers were sized LARGER than winners ($136 vs $114 avg).
# Every gate is overridable per-trade ({"override": true}) — gates inform
# operator discretion, they don't replace it (PD-340 ruling).
TRADE_GATES = {
    # NO entries at/above this price require ROOM status + TRUSTED basis.
    "no_price_ceiling": 0.95,
    # Hard per-position size cap (NO-side downside = full size).
    "max_loss_cap_usd": 150.0,
    # Reject trades when the backing scan is older than this (cached prices are
    # the execution prices — a restart-restored disk cache can be days old).
    "max_scan_age_min": 15.0,
    # Reject when the live ask has moved beyond this from the displayed price.
    "requote_tolerance": 0.02,
}

# API endpoints
API_CONFIG = {
    "nws_base_url": "https://api.weather.gov",
    "open_meteo_base_url": "https://api.open-meteo.com/v1/forecast",
    "polymarket_gamma_url": "https://gamma-api.polymarket.com",
}

# CLOB API for price history
CLOB_API_URL = "https://clob.polymarket.com"

# Telegram config (set in .env)
TELEGRAM_CONFIG = {
    "env_token_key": "TELEGRAM_BOT_TOKEN",
    "env_chat_id_key": "TELEGRAM_CHAT_ID",
}

# Temperature conversion helpers
def fahrenheit_to_celsius(f: float) -> float:
    return (f - 32) * 5 / 9

def celsius_to_fahrenheit(c: float) -> float:
    return c * 9 / 5 + 32


@dataclass
class WeatherOpportunity:
    """Represents a weather trading opportunity."""
    city: str
    city_name: str
    market_id: str
    market_question: str
    market_url: str
    target_date: str
    resolution_time: str
    hours_remaining: float
    
    # Forecast data
    forecast_temp: float
    forecast_unit: str  # "F" or "C"
    forecast_source: str
    model_consensus: bool  # True if multiple models agree
    
    # Market data
    bucket_low: float
    bucket_high: float
    bucket_unit: str
    yes_price: float
    no_price: float
    liquidity: float
    
    bucket_probability: float
    edge: float
    recommended_side: str
    suggested_action: str  # "BUY YES" or "BUY NO" or "SKIP"
    suggested_position: float
    
    # Optional fields with defaults (must come last)
    clob_token_ids: tuple = (None, None)
    forecast_range: str = "48hr"  # "48hr" for short-range, "7day" for extended
    
    def to_alert_message(self) -> str:
        """Format as Telegram alert message."""
        emoji = "🌡️" if abs(self.edge) >= 0.25 else "📊"
        consensus = "✅ Consensus" if self.model_consensus else "⚠️ Models differ"

        if self.recommended_side == "NO":
            price_line = f"💰 NO Price: {self.no_price*100:.1f}¢ (YES: {self.yes_price*100:.1f}¢)"
        else:
            price_line = f"💰 YES Price: {self.yes_price*100:.1f}¢ (NO: {self.no_price*100:.1f}¢)"

        return f"""{emoji} {self.city_name.upper()} WEATHER OPPORTUNITY

📍 Market: High temp {self.bucket_low}-{self.bucket_high}°{self.bucket_unit}
📅 Resolves in: {self.hours_remaining:.1f} hours
🔮 Forecast: {self.forecast_temp:.0f}°{self.forecast_unit} ({self.forecast_source})
{consensus}

{price_line}
📈 Your Edge: {self.edge*100:+.0f}%
🎯 Bucket Prob: {self.bucket_probability*100:.0f}%

💵 Suggested: {self.suggested_action} ${self.suggested_position:.0f}

🔗 {self.market_url}"""
