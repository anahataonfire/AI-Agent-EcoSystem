"""
Weather Forecaster

Fetches weather forecasts from NWS and Open-Meteo APIs.
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

from config import WEATHER_CITIES, API_CONFIG, celsius_to_fahrenheit

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
    forecast_range: str = "48hr"  # "48hr" for short-range, "7day" for extended

    # Optional: per-model breakdown
    ecmwf_high: Optional[float] = None
    gfs_high: Optional[float] = None
    nws_high: Optional[float] = None

    # PD-325 follow-up: track provenance of the low value so LOW-market
    # consumers can skip opps generated from the synthetic fallback
    # (avg_high - 15), which is wildly off for many climates and was the
    # root cause of pos_707's bad LOW opp.
    low_source: str = "OPEN_METEO"  # "OPEN_METEO" or "SYNTHETIC"


class WeatherForecaster:
    """
    Fetches weather forecasts from multiple sources.
    
    Priority:
    1. NWS API (US cities) - official resolution source
    2. Open-Meteo (global) - free ECMWF/GFS access
    """
    
    # PD-325 perf-during-outage: per-host circuit breaker so an Open-Meteo 502
    # storm trips fast (5 failures) and skips for a cooldown window instead of
    # consuming ~20 min per harvest on 30s timeouts.
    _CIRCUIT_THRESHOLD = 5
    _CIRCUIT_COOLDOWN_SEC = 60

    def __init__(self, request_timeout: float = 10.0):
        self.timeout = request_timeout
        self._cache: Dict[str, DailyForecast] = {}
        self._host_failures: Dict[str, int] = {}
        self._host_open_until: Dict[str, datetime] = {}

    def _circuit_blocks(self, host: str) -> bool:
        """True if circuit is currently open for host."""
        until = self._host_open_until.get(host)
        if until is None:
            return False
        if datetime.now(timezone.utc) >= until:
            # Cooldown elapsed — let next probe through; keep failure count so
            # one more failure re-opens immediately.
            self._host_open_until.pop(host, None)
            return False
        return True

    def _record_failure(self, host: str):
        self._host_failures[host] = self._host_failures.get(host, 0) + 1
        if self._host_failures[host] >= self._CIRCUIT_THRESHOLD:
            self._host_open_until[host] = (
                datetime.now(timezone.utc) + timedelta(seconds=self._CIRCUIT_COOLDOWN_SEC)
            )
            logger.warning(
                f"Circuit OPEN for {host} after {self._host_failures[host]} consecutive failures; "
                f"skipping for {self._CIRCUIT_COOLDOWN_SEC}s"
            )

    def _record_success(self, host: str):
        if self._host_failures.get(host, 0) or host in self._host_open_until:
            logger.info(f"Circuit CLOSED for {host} (request succeeded)")
        self._host_failures[host] = 0
        self._host_open_until.pop(host, None)

    def _make_request(self, url: str, headers: Dict = None, retries: int = 1) -> Optional[Dict]:
        """Make HTTP GET request and parse JSON response.

        Retries once on transient errors (502/504 gateway, socket timeout,
        connection reset). Returns None on terminal failure so callers can
        skip the city/date pair without crashing the whole harvest. PD-324
        forecaster-resilience fix: TimeoutError (socket read timeout) was
        not caught by the original URLError/HTTPError set and bubbled to
        FastAPI as 500 during Open-Meteo outages.

        PD-325 perf-during-outage: per-host circuit breaker short-circuits
        subsequent calls after `_CIRCUIT_THRESHOLD` consecutive failures.
        """
        host = urlparse(url).netloc
        if self._circuit_blocks(host):
            return None

        for attempt in range(retries + 1):
            try:
                req = Request(url)
                req.add_header("User-Agent", "WeatherTradingBot/1.0 (contact@example.com)")
                if headers:
                    for key, value in headers.items():
                        req.add_header(key, value)

                with urlopen(req, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode())
                    self._record_success(host)
                    return data
            except (OSError, HTTPError, json.JSONDecodeError) as e:
                if attempt < retries:
                    logger.warning(f"Request failed for {url} (attempt {attempt+1}/{retries+1}): {e}. Retrying in 1s...")
                    time.sleep(1.0)
                    continue
                logger.error(f"Request failed for {url} after {retries+1} attempts: {e}")
                self._record_failure(host)
                return None
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
    
    def fetch_open_meteo_daily(self, city_key: str) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Fetch DAILY high/low temperatures from Open-Meteo.
        
        This is more accurate than calculating from hourly data because
        it uses the actual daily max/min from the models.
        
        Returns:
            Dict mapping dates to {high_f, low_f} values
        """
        city = WEATHER_CITIES.get(city_key)
        if not city:
            return None
        
        lat, lon = city["lat"], city["lon"]
        
        # Use Open-Meteo's daily endpoint with temperature_2m_max/min
        url = (
            f"{API_CONFIG['open_meteo_base_url']}"
            f"?latitude={lat}&longitude={lon}"
            f"&daily=temperature_2m_max,temperature_2m_min"
            f"&forecast_days=7"
            f"&timezone=auto"
        )
        
        data = self._make_request(url)
        if not data or "daily" not in data:
            logger.warning(f"Failed to fetch Open-Meteo daily for {city_key}")
            return None
        
        daily = data["daily"]
        dates = daily.get("time", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        
        results = {}
        for date, high_c, low_c in zip(dates, highs, lows):
            if high_c is not None:
                # Codex C fix: explicit None-check on low_c so 0°C doesn't
                # get falsy-treated as missing (which flips low_source to
                # SYNTHETIC and suppresses real LOW opps).
                results[date] = {
                    "high_f": celsius_to_fahrenheit(high_c),
                    "low_f": celsius_to_fahrenheit(low_c) if low_c is not None else None,
                    "high_c": high_c,
                    "low_c": low_c
                }
        
        if results:
            logger.info(f"Fetched {len(results)} daily forecasts from Open-Meteo for {city_key}")
        
        return results
    
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
        lows = {}
        
        # PRIMARY: Use Open-Meteo DAILY endpoint (most accurate for daily max/min)
        om_daily = self.fetch_open_meteo_daily(city_key)
        if om_daily and target_date in om_daily:
            day_data = om_daily[target_date]
            highs["OPEN_METEO"] = day_data["high_f"]
            # Codex C fix: explicit None-check — `low_f == 0` (32°F low) is
            # real data, not absence. Falsy-skipping caused PD-325 follow-up
            # to incorrectly mark such forecasts as SYNTHETIC.
            if day_data.get("low_f") is not None:
                lows["OPEN_METEO"] = day_data["low_f"]
            logger.info(f"Open-Meteo daily: {day_data['high_f']:.1f}F high for {city_key} {target_date}")
        
        # SECONDARY: Try NWS hourly for US cities (only if within 48 hours)
        nws_forecasts = self.fetch_nws_forecast(city_key)
        if nws_forecasts:
            day_temps = [
                f.temp_f for f in nws_forecasts 
                if f.time.strftime("%Y-%m-%d") == target_date
            ]
            # Only use NWS if we have full day coverage (at least 18 hours)
            if len(day_temps) >= 18:
                highs["NWS"] = max(day_temps)
                logger.info(f"NWS hourly: {max(day_temps):.1f}F high for {city_key} {target_date}")
        
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
        
        # Determine forecast range based on days out
        try:
            target = datetime.strptime(target_date, "%Y-%m-%d").date()
            today = datetime.now(timezone.utc).date()
            days_out = (target - today).days
            forecast_range = "48hr" if days_out <= 2 else "7day"
        except ValueError:
            forecast_range = "7day"  # Default to conservative
        
        # Use actual low if we have it from Open-Meteo daily; otherwise fall
        # back to avg_high - 15 (crude; flag as SYNTHETIC so LOW consumers can opt out).
        if "OPEN_METEO" in lows:
            low_f = lows["OPEN_METEO"]
            low_source = "OPEN_METEO"
        else:
            low_f = avg_high - 15
            low_source = "SYNTHETIC"

        result = DailyForecast(
            city=city_key,
            date=target_date,
            high_f=avg_high,
            low_f=low_f,
            high_c=(avg_high - 32) * 5 / 9,
            low_c=(low_f - 32) * 5 / 9,
            source=source,
            confidence=confidence,
            fetched_at=datetime.now(timezone.utc),
            forecast_range=forecast_range,
            ecmwf_high=highs.get("ecmwf_ifs04") or highs.get("ECMWF_IFS04"),
            gfs_high=highs.get("gfs_seamless") or highs.get("GFS_SEAMLESS") or highs.get("OPEN_METEO"),
            nws_high=highs.get("NWS"),
            low_source=low_source,
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
