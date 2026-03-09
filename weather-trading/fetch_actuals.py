"""
Fetch historical actual temperatures from NWS and Open-Meteo.
"""
import json
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Optional, Dict, List
from config import WEATHER_CITIES, API_CONFIG, ACTIVE_CITIES

logger = logging.getLogger(__name__)

# NWS observation stations (closest to city centers)
NWS_STATIONS = {
    "nyc": "KNYC",      # Central Park
    "atlanta": "KATL",   # Hartsfield-Jackson
    "seattle": "KSEA",   # Sea-Tac
    # Non-US cities use Open-Meteo instead
}

def fetch_nws_observations(station_id: str, days_back: int = 7) -> List[Dict]:
    """
    Fetch historical observations from NWS API.
    
    Endpoint: https://api.weather.gov/stations/{station}/observations
    Returns list of {date, high_f, low_f}
    """
    url = f"https://api.weather.gov/stations/{station_id}/observations"
    params = f"?limit={days_back * 24}"  # Hourly obs
    
    try:
        req = Request(url + params, headers={
            "User-Agent": "WeatherBacktest/1.0 (contact@example.com)",
            "Accept": "application/geo+json"
        })
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, HTTPError) as e:
        logger.error(f"NWS fetch failed for {station_id}: {e}")
        return []
    
    # Group by date and find daily high/low
    daily = {}
    for obs in data.get("features", []):
        props = obs.get("properties", {})
        timestamp = props.get("timestamp")
        temp_c = props.get("temperature", {}).get("value")
        
        if not timestamp or temp_c is None:
            continue
        
        date = timestamp[:10]  # YYYY-MM-DD
        temp_f = temp_c * 9/5 + 32
        
        if date not in daily:
            daily[date] = {"high": temp_f, "low": temp_f}
        else:
            daily[date]["high"] = max(daily[date]["high"], temp_f)
            daily[date]["low"] = min(daily[date]["low"], temp_f)
    
    return [{"date": d, "high_f": v["high"], "low_f": v["low"]} for d, v in daily.items()]


def fetch_open_meteo_historical(lat: float, lon: float, days_back: int = 7) -> List[Dict]:
    """
    Fetch historical actuals from Open-Meteo archive.
    
    Works for any location globally.
    """
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f"&temperature_unit=fahrenheit"
        f"&timezone=auto"
    )
    
    try:
        req = Request(url, headers={"User-Agent": "WeatherBacktest/1.0"})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, HTTPError) as e:
        logger.error(f"Open-Meteo fetch failed: {e}")
        return []
    
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    
    results = []
    for i, date in enumerate(dates):
        if i < len(highs) and highs[i] is not None:
            results.append({
                "date": date,
                "high_f": highs[i],
                "low_f": lows[i] if i < len(lows) else None
            })
    
    return results


def fetch_and_store_actuals(cities: List[str] = None, days_back: int = 7) -> int:
    """Fetch actual temps for all cities and store in SQLite."""
    if cities is None:
        cities = ACTIVE_CITIES
    
    conn = sqlite3.connect("weather_backtest.db")
    cur = conn.cursor()
    
    # Create table if not exists
    cur.execute('''
        CREATE TABLE IF NOT EXISTS actual_temps (
            id INTEGER PRIMARY KEY,
            city_key TEXT NOT NULL,
            date TEXT NOT NULL,
            actual_high_f REAL NOT NULL,
            actual_low_f REAL,
            source TEXT NOT NULL,
            station_id TEXT,
            recorded_at TEXT NOT NULL,
            UNIQUE(city_key, date)
        )
    ''')
    
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    
    for city_key in cities:
        city = WEATHER_CITIES.get(city_key)
        if not city:
            continue
        
        logger.info(f"Fetching actuals for {city_key}...")
        
        # Try NWS first for US cities
        station = NWS_STATIONS.get(city_key)
        if station:
            observations = fetch_nws_observations(station, days_back)
            source = "NWS"
        else:
            # Use Open-Meteo for non-US
            observations = fetch_open_meteo_historical(
                city["lat"], city["lon"], days_back
            )
            source = "Open-Meteo"
            station = None
        
        for obs in observations:
            try:
                cur.execute('''
                    INSERT OR REPLACE INTO actual_temps 
                    (city_key, date, actual_high_f, actual_low_f, source, station_id, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    city_key,
                    obs["date"],
                    obs["high_f"],
                    obs.get("low_f"),
                    source,
                    station,
                    now
                ))
                inserted += 1
            except sqlite3.Error as e:
                logger.warning(f"Insert failed for {city_key} {obs['date']}: {e}")
        
        logger.info(f"  {city_key}: {len(observations)} days from {source}")
    
    conn.commit()
    conn.close()
    
    return inserted


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch historical actual temperatures")
    parser.add_argument("--days", type=int, default=7, help="Days of history")
    parser.add_argument("--cities", nargs="+", default=None, help="Cities to fetch")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(message)s")
    
    inserted = fetch_and_store_actuals(args.cities, args.days)
    print(f"\\nInserted {inserted} actual temperature records")


if __name__ == "__main__":
    main()
