"""
Known Temperature Market IDs

Stores condition IDs and metadata for temperature markets.
These are scraped from Polymarket's website since the API doesn't expose them.

To refresh: Run the browser scraper to extract __NEXT_DATA__ from
https://polymarket.com/climate-science/weather
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, List, Optional

# Scraped on 2026-01-14
# Source: Polymarket __NEXT_DATA__ parsing via browser automation


@dataclass
class TemperatureMarketInfo:
    """Metadata for a temperature market bucket."""
    condition_id: str
    question_id: str
    city_key: str
    target_date: str  # YYYY-MM-DD
    bucket_low: float
    bucket_high: float
    bucket_unit: str  # "F" or "C"
    slug: str


# Known temperature markets - organized by city and date
# Structure: city_key -> date -> list of bucket markets
KNOWN_TEMPERATURE_MARKETS: Dict[str, Dict[str, List[TemperatureMarketInfo]]] = {
    "nyc": {
        "2026-01-14": [
            TemperatureMarketInfo(
                condition_id="0x740aec",  # Truncated for readability
                question_id="0xf97300",
                city_key="nyc",
                target_date="2026-01-14",
                bucket_low=float('-inf'),
                bucket_high=41,
                bucket_unit="F",
                slug="highest-temp-nyc-jan-14-41forbelow"
            ),
            TemperatureMarketInfo(
                condition_id="0x4e8f0f",
                question_id="0xf97301",
                city_key="nyc",
                target_date="2026-01-14",
                bucket_low=42,
                bucket_high=43,
                bucket_unit="F",
                slug="highest-temp-nyc-jan-14-42-43f"
            ),
            TemperatureMarketInfo(
                condition_id="0x3eebec",
                question_id="0xf97305",
                city_key="nyc",
                target_date="2026-01-14",
                bucket_low=50,
                bucket_high=51,
                bucket_unit="F",
                slug="highest-temp-nyc-jan-14-50-51f"
            ),
        ],
    },
    "london": {
        "2026-01-14": [
            TemperatureMarketInfo(
                condition_id="0xdbdef2",
                question_id="0x270205",
                city_key="london",
                target_date="2026-01-14",
                bucket_low=8,
                bucket_high=8,
                bucket_unit="C",
                slug="highest-temp-london-jan-14-8c"
            ),
            TemperatureMarketInfo(
                condition_id="0xb4fe69",
                question_id="0x270206",
                city_key="london",
                target_date="2026-01-14",
                bucket_low=9,
                bucket_high=float('inf'),
                bucket_unit="C",
                slug="highest-temp-london-jan-14-9corhigher"
            ),
        ],
    },
    "toronto": {
        "2026-01-13": [
            TemperatureMarketInfo(
                condition_id="0x4b7968",
                question_id="0x338d03",
                city_key="toronto",
                target_date="2026-01-13",
                bucket_low=3,
                bucket_high=3,
                bucket_unit="C",
                slug="highest-temp-toronto-jan-13-3c"
            ),
        ],
    },
    "seattle": {
        "2026-01-14": [
            TemperatureMarketInfo(
                condition_id="0x33ae6f",
                question_id="0xaab9d3",
                city_key="seattle",
                target_date="2026-01-14",
                bucket_low=50,
                bucket_high=51,
                bucket_unit="F",
                slug="highest-temp-seattle-jan-14-50-51f"
            ),
        ],
    },
    "buenos_aires": {
        "2026-01-14": [
            TemperatureMarketInfo(
                condition_id="0x972e27",
                question_id="0x229700",
                city_key="buenos_aires",
                target_date="2026-01-14",
                bucket_low=float('-inf'),
                bucket_high=36,
                bucket_unit="C",
                slug="highest-temp-buenos-aires-jan-14-36corbelow"
            ),
        ],
    },
}


def get_markets_for_city_date(
    city_key: str, 
    target_date: str
) -> List[TemperatureMarketInfo]:
    """Get known markets for a city and date."""
    city_markets = KNOWN_TEMPERATURE_MARKETS.get(city_key, {})
    return city_markets.get(target_date, [])


def get_all_condition_ids() -> List[str]:
    """Get all known condition IDs."""
    condition_ids = []
    for city_data in KNOWN_TEMPERATURE_MARKETS.values():
        for date_markets in city_data.values():
            for market in date_markets:
                condition_ids.append(market.condition_id)
    return condition_ids


def get_markets_for_today_tomorrow(city_key: str) -> List[TemperatureMarketInfo]:
    """Get markets for today and tomorrow for a city."""
    from datetime import timedelta
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    
    markets = []
    markets.extend(get_markets_for_city_date(city_key, today))
    markets.extend(get_markets_for_city_date(city_key, tomorrow))
    return markets


# Note: These condition IDs may need to be refreshed daily or weekly
# as new temperature markets are created for future dates.
# Run the browser scraper to update this file with fresh IDs.
