"""
Weather Forecaster

Fetches weather forecasts from NWS and Open-Meteo APIs.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from .config import WEATHER_CITIES, API_CONFIG, celsius_to_fahrenheit

logger = logging.getLogger(__name__)


@dataclass
class HourlyForecast:
    """Single hourly temperature forecast."""
    time: datetime
    temp_f: float
    temp_c: float
    source: str  # "NWS", "ECMWF", "GFS", etc.


@dataclass
class DailyForecast:
    """Daily high/low forecast for a city."""
    city: str
    date: str  # YYYY-MM-DD
    high_f: float
    low_f: float
    high_c: float
    low_c: float
    source: str
    confidence: float  # 0-1, based on model consensus
    fetched_at: datetime
    
    # Optional: per-model breakdown
    ecmwf_high: Optional[float] = None
    gfs_high: Optional[float] = None
    nws_high: Optional[float] = None


class WeatherForecaster:
    """
    Fetches weather forecasts from multiple sources.
    
    Priority:
    1. NWS API (US cities) - official resolution source
    2. Open-Meteo (global) - free ECMWF/GFS access
    """
    
    def __init__(self, request_timeout: float = 10.0):
        self.timeout = request_timeout
        self._cache: Dict[str, DailyForecast] = {}
    
    def _make_request(self, url: str, headers: Dict = None) -> Optional[Dict]:
        """Make HTTP GET request and parse JSON response."""
        try:
            req = Request(url)
            req.add_header("User-Agent", "WeatherTradingBot/1.0 (contact@example.com)")
            if headers:
                for key, value in headers.items():
                    req.add_header(key, value)
            
            with urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except (URLError, HTTPError, json.JSONDecodeError) as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
    
    def fetch_nws_forecast(self, city_key: str) -> Optional[List[HourlyForecast]]:
        """
        Fetch hourly forecast from NWS API (US cities only).
        
        Returns list of HourlyForecast for next 48 hours.
        """
        city = WEATHER_CITIES.get(city_key)
        if not city or not city.get("nws_office"):
            logger.debug(f"No NWS data for {city_key}")
            return None
        
        office = city["nws_office"]
        grid = city["nws_grid"]
        url = f"{API_CONFIG['nws_base_url']}/gridpoints/{office}/{grid}/forecast/hourly"
        
        data = self._make_request(url)
        if not data or "properties" not in data:
            return None
        
        forecasts = []
        for period in data["properties"].get("periods", [])[:48]:
            try:
                time_str = period.get("startTime", "")
                temp = period.get("temperature", 0)
                unit = period.get("temperatureUnit", "F")
                
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                temp_f = temp if unit == "F" else celsius_to_fahrenheit(temp)
                temp_c = temp if unit == "C" else (temp - 32) * 5 / 9
                
                forecasts.append(HourlyForecast(
                    time=dt,
                    temp_f=temp_f,
                    temp_c=temp_c,
                    source="NWS"
                ))
            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to parse NWS period: {e}")
                continue
        
        logger.info(f"Fetched {len(forecasts)} hourly forecasts from NWS for {city_key}")
        return forecasts
    
    def fetch_open_meteo_forecast(
        self, 
        city_key: str,
        models: List[str] = None
    ) -> Optional[Dict[str, List[HourlyForecast]]]:
        """
        Fetch hourly forecast from Open-Meteo (global, free).
        
        Returns dict of model_name -> List[HourlyForecast]
        Supports ECMWF, GFS, and other models.
        """
        city = WEATHER_CITIES.get(city_key)
        if not city:
            return None
        
        lat, lon = city["lat"], city["lon"]
        
        # Default to ECMWF and GFS
        if models is None:
            models = ["ecmwf_ifs04", "gfs_seamless"]
        
        results = {}
        
        for model in models:
            url = (
                f"{API_CONFIG['open_meteo_base_url']}"
                f"?latitude={lat}&longitude={lon}"
                f"&hourly=temperature_2m"
                f"&models={model}"
                f"&forecast_days=2"
                f"&timezone=auto"
            )
            
            data = self._make_request(url)
            if not data or "hourly" not in data:
                continue
            
            hourly = data["hourly"]
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            
            forecasts = []
            for i, (time_str, temp_c) in enumerate(zip(times, temps)):
                if temp_c is None:
                    continue
                try:
                    dt = datetime.fromisoformat(time_str)
                    # Make timezone-aware if not already
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    
                    forecasts.append(HourlyForecast(
                        time=dt,
                        temp_f=celsius_to_fahrenheit(temp_c),
                        temp_c=temp_c,
                        source=model.upper()
                    ))
                except (ValueError, TypeError) as e:
                    continue
            
            if forecasts:
                results[model] = forecasts
                logger.info(f"Fetched {len(forecasts)} hourly forecasts from {model} for {city_key}")
        
        return results if results else None
    
    def get_daily_high_forecast(self, city_key: str, target_date: str) -> Optional[DailyForecast]:
        """
        Get the forecasted daily high temperature for a city.
        
        Args:
            city_key: City identifier (e.g., "nyc")
            target_date: Date string YYYY-MM-DD
            
        Returns:
            DailyForecast with high temp and confidence
        """
        city = WEATHER_CITIES.get(city_key)
        if not city:
            logger.error(f"Unknown city: {city_key}")
            return None
        
        highs = {}
        
        # Try NWS first for US cities
        nws_forecasts = self.fetch_nws_forecast(city_key)
        if nws_forecasts:
            day_temps = [
                f.temp_f for f in nws_forecasts 
                if f.time.strftime("%Y-%m-%d") == target_date
            ]
            if day_temps:
                highs["NWS"] = max(day_temps)
        
        # Get Open-Meteo (ECMWF + GFS)
        om_forecasts = self.fetch_open_meteo_forecast(city_key)
        if om_forecasts:
            for model, forecasts in om_forecasts.items():
                day_temps = [
                    f.temp_f for f in forecasts
                    if f.time.strftime("%Y-%m-%d") == target_date
                ]
                if day_temps:
                    highs[model] = max(day_temps)
        
        if not highs:
            logger.warning(f"No forecasts found for {city_key} on {target_date}")
            return None
        
        # Calculate consensus high and confidence
        values = list(highs.values())
        avg_high = sum(values) / len(values)
        
        # Confidence based on model agreement
        if len(values) >= 2:
            spread = max(values) - min(values)
            # If models within 3°F, high confidence
            if spread <= 3:
                confidence = 0.9
            elif spread <= 5:
                confidence = 0.75
            else:
                confidence = 0.5
        else:
            confidence = 0.7  # Single source
        
        # Determine primary source
        source = "NWS" if "NWS" in highs else list(highs.keys())[0]
        
        result = DailyForecast(
            city=city_key,
            date=target_date,
            high_f=avg_high,
            low_f=avg_high - 15,  # Rough estimate, could improve
            high_c=(avg_high - 32) * 5 / 9,
            low_c=(avg_high - 15 - 32) * 5 / 9,
            source=source,
            confidence=confidence,
            fetched_at=datetime.now(timezone.utc),
            ecmwf_high=highs.get("ecmwf_ifs04") or highs.get("ECMWF_IFS04"),
            gfs_high=highs.get("gfs_seamless") or highs.get("GFS_SEAMLESS"),
            nws_high=highs.get("NWS"),
        )
        
        logger.info(
            f"Forecast for {city_key} on {target_date}: "
            f"High={avg_high:.1f}°F, Confidence={confidence:.0%}, "
            f"Sources={list(highs.keys())}"
        )
        
        return result


# Module-level singleton
_forecaster: Optional[WeatherForecaster] = None

def get_forecaster() -> WeatherForecaster:
    """Get or create the singleton forecaster instance."""
    global _forecaster
    if _forecaster is None:
        _forecaster = WeatherForecaster()
    return _forecaster
