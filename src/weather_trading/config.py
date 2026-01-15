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
}

# Active cities to scan (start with subset)
ACTIVE_CITIES = ["nyc", "london", "seattle", "toronto", "atlanta"]

# Edge thresholds
EDGE_CONFIG = {
    "min_edge_threshold": 0.15,  # 15% minimum edge to alert
    "high_confidence_edge": 0.25,  # 25%+ edge = larger suggested position
    "std_dev_24hr": 2.0,  # Standard deviation in °F for 24hr forecasts
    "std_dev_48hr": 3.0,  # Wider uncertainty for 48hr
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

# API endpoints
API_CONFIG = {
    "nws_base_url": "https://api.weather.gov",
    "open_meteo_base_url": "https://api.open-meteo.com/v1/forecast",
    "polymarket_gamma_url": "https://gamma-api.polymarket.com",
}

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
    liquidity: float
    
    # Calculated edge
    bucket_probability: float
    edge: float
    suggested_action: str  # "BUY YES" or "SKIP"
    suggested_position: float
    
    def to_alert_message(self) -> str:
        """Format as Telegram alert message."""
        emoji = "🌡️" if self.edge >= 0.25 else "📊"
        consensus = "✅ Consensus" if self.model_consensus else "⚠️ Models differ"
        
        return f"""{emoji} {self.city_name.upper()} WEATHER OPPORTUNITY

📍 Market: High temp {self.bucket_low}-{self.bucket_high}°{self.bucket_unit}
📅 Resolves in: {self.hours_remaining:.1f} hours
🔮 Forecast: {self.forecast_temp:.0f}°{self.forecast_unit} ({self.forecast_source})
{consensus}

💰 Market Price: {self.yes_price*100:.1f}¢
📈 Your Edge: {self.edge*100:.0f}%
🎯 Bucket Prob: {self.bucket_probability*100:.0f}%

💵 Suggested: {self.suggested_action} ${self.suggested_position:.0f}

🔗 {self.market_url}"""
