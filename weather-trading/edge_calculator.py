"""
Edge Calculator

Calculates trading edge by comparing weather forecasts to market prices.
Uses normal distribution assumption for temperature probability.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from math import erf, sqrt
from typing import List, Optional

from config import (
    EDGE_CONFIG,
    POSITION_CONFIG,
    WeatherOpportunity,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
)
from forecaster import DailyForecast
from scanner import WeatherMarket

logger = logging.getLogger(__name__)


def normal_cdf(x: float, mean: float, std: float) -> float:
    """
    Cumulative distribution function for normal distribution.
    
    Uses error function for calculation (no scipy dependency).
    """
    if std <= 0:
        return 1.0 if x >= mean else 0.0
    return 0.5 * (1 + erf((x - mean) / (std * sqrt(2))))


def bucket_probability(
    forecast_temp: float,
    bucket_low: float,
    bucket_high: float,
    std_dev: float = 2.0
) -> float:
    """
    Calculate probability that actual temperature falls within bucket.
    
    Assumes temperature follows normal distribution around forecast.
    
    Args:
        forecast_temp: Forecasted temperature (same units as bucket)
        bucket_low: Lower bound of bucket (use -inf for "or below")
        bucket_high: Upper bound of bucket (use inf for "or above")
        std_dev: Standard deviation of forecast error (default 2°F for 24hr)
        
    Returns:
        Probability (0-1) that temp falls in bucket
    """
    # Handle edge cases
    if bucket_low == float('-inf'):
        return normal_cdf(bucket_high, forecast_temp, std_dev)
    if bucket_high == float('inf'):
        return 1 - normal_cdf(bucket_low, forecast_temp, std_dev)
    
    # P(low <= X <= high) = CDF(high) - CDF(low)
    prob_high = normal_cdf(bucket_high + 0.5, forecast_temp, std_dev)  # +0.5 for discrete temp
    prob_low = normal_cdf(bucket_low - 0.5, forecast_temp, std_dev)
    
    return max(0, min(1, prob_high - prob_low))


class EdgeCalculator:
    """
    Calculates trading edge for weather markets.
    """
    
    def __init__(
        self,
        min_edge: float = None,
        high_edge: float = None,
        std_dev_24hr: float = None,
        std_dev_48hr: float = None,
    ):
        self.min_edge = min_edge or EDGE_CONFIG["min_edge_scan"]
        self.high_edge = high_edge or EDGE_CONFIG["min_edge_trade"]
        self.std_dev_default = std_dev_24hr or EDGE_CONFIG["std_dev_default"]
    
    def _get_std_dev(self, hours_remaining: float, bucket_unit: str = "F") -> float:
        """Get appropriate std_dev based on time to resolution and market unit.

        The stored std_dev_default (2.5) is calibrated in °F.
        For °C markets, convert: °C_std = °F_std / 1.8.
        """
        std = self.std_dev_default  # Always in °F

        # Scale uncertainty slightly as we look further ahead
        if hours_remaining > 24:
            scale = min(1.5, 1.0 + (hours_remaining - 24) / 48)
            std *= scale

        # Convert to market's unit (PD-144 R1)
        if bucket_unit == "C":
            std /= 1.8

        return std
    
    def _normalize_units(
        self,
        forecast_temp: float,
        forecast_unit: str,
        bucket_low: float,
        bucket_high: float,
        bucket_unit: str
    ) -> tuple:
        """Ensure forecast and bucket are in same units."""
        if forecast_unit == bucket_unit:
            return forecast_temp, bucket_low, bucket_high
        
        # Convert forecast to bucket units
        if bucket_unit == "F" and forecast_unit == "C":
            return celsius_to_fahrenheit(forecast_temp), bucket_low, bucket_high
        elif bucket_unit == "C" and forecast_unit == "F":
            return fahrenheit_to_celsius(forecast_temp), bucket_low, bucket_high
        
        return forecast_temp, bucket_low, bucket_high
    
    def calculate_opportunity(
        self,
        market: WeatherMarket,
        forecast: DailyForecast,
    ) -> Optional[WeatherOpportunity]:
        """
        Calculate trading opportunity for a market given forecast.
        
        Returns:
            WeatherOpportunity if edge >= min_edge, else None
        """
        # PD-321 R4 (Codex R4): low-temperature markets flow through
        # EdgeHarvestScanner (/api/edge-harvest) only. The legacy
        # /api/scan + alert path doesn't yet expose market_type on
        # WeatherOpportunity, so low markets would render as "High temp"
        # in alerts and use high-only categorization. Skip them here
        # until the legacy path is made low-aware.
        if getattr(market, 'market_type', 'high') == 'low':
            return None
        # Normalize units (both to bucket's unit)
        forecast_temp, bucket_low, bucket_high = self._normalize_units(
            forecast.high_f,  # Use high temp forecast
            "F",
            market.bucket_low,
            market.bucket_high,
            market.bucket_unit,
        )
        
        # Get appropriate std_dev (unit-aware: PD-144 R1)
        std_dev = self._get_std_dev(market.hours_remaining, market.bucket_unit)
        
        # Adjust std_dev based on forecast confidence
        if forecast.confidence < 0.7:
            std_dev *= 1.3  # More uncertainty if models disagree
        
        # Calculate bucket probability
        prob = bucket_probability(
            forecast_temp,
            bucket_low,
            bucket_high,
            std_dev
        )
        
        logger.debug(
            f"Edge Calc Details: {market.city} | Bucket: [{bucket_low}, {bucket_high}] {market.bucket_unit} | "
            f"Forecast: {forecast_temp} {market.bucket_unit} | Std: {std_dev:.2f} | Prob: {prob:.4f}"
        )
        
        # Signed edge: + = YES underpriced (buy YES), − = YES overpriced (buy NO)
        edge = prob - market.yes_price

        if abs(edge) < self.min_edge:
            logger.debug(
                f"Skipping {market.city} {bucket_low}-{bucket_high}: "
                f"|edge|={abs(edge):.1%} < min={self.min_edge:.1%}"
            )
            return None

        if edge > 0:
            recommended_side = "YES"
            suggested_action = "BUY YES"
        else:
            recommended_side = "NO"
            suggested_action = "BUY NO"

        if abs(edge) >= self.high_edge:
            suggested_position = POSITION_CONFIG["high_edge_position_usd"]
        else:
            suggested_position = POSITION_CONFIG["default_position_usd"]

        suggested_position = min(suggested_position, POSITION_CONFIG["max_position_usd"])

        model_consensus = True
        if forecast.ecmwf_high and forecast.gfs_high:
            model_consensus = abs(forecast.ecmwf_high - forecast.gfs_high) <= 3

        opportunity = WeatherOpportunity(
            city=market.city_key,
            city_name=market.city,
            market_id=market.market_id,
            market_question=market.question,
            market_url=market.market_url,
            target_date=market.target_date,
            resolution_time=market.end_time.isoformat(),
            hours_remaining=market.hours_remaining,
            forecast_temp=forecast_temp,
            forecast_unit=market.bucket_unit,
            forecast_source=forecast.source,
            model_consensus=model_consensus,
            forecast_range=getattr(forecast, 'forecast_range', '48hr'),
            bucket_low=bucket_low,
            bucket_high=bucket_high,
            bucket_unit=market.bucket_unit,
            yes_price=market.yes_price,
            no_price=market.no_price,
            liquidity=market.liquidity,
            bucket_probability=prob,
            edge=edge,
            recommended_side=recommended_side,
            clob_token_ids=market.clob_token_ids,
            suggested_action=suggested_action,
            suggested_position=suggested_position,
        )

        logger.info(
            f"Found opportunity: {market.city} {bucket_low}-{bucket_high}°{market.bucket_unit} "
            f"| Forecast: {forecast_temp:.0f}° | YES: {market.yes_price:.2f} NO: {market.no_price:.2f} "
            f"| Prob: {prob:.0%} | Edge: {edge:+.0%} | {suggested_action}"
        )

        return opportunity
    
    def find_opportunities(
        self,
        markets: List[WeatherMarket],
        forecasts: dict,  # city_key -> DailyForecast
    ) -> List[WeatherOpportunity]:
        """
        Find all opportunities across markets and forecasts.
        
        Args:
            markets: List of WeatherMarket objects
            forecasts: Dict mapping city_key to DailyForecast
            
        Returns:
            List of WeatherOpportunity sorted by edge (descending)
        """
        opportunities = []
        
        for market in markets:
            # Get forecast for this city and target date
            forecast = forecasts.get((market.city_key, market.target_date))
            if not forecast:
                logger.debug(f"No forecast for {market.city_key} on {market.target_date}")
                continue
            
            # Check if forecast date matches market date
            if forecast.date != market.target_date:
                logger.debug(
                    f"Date mismatch: forecast={forecast.date}, market={market.target_date}"
                )
                continue
            
            opp = self.calculate_opportunity(market, forecast)
            if opp:
                opportunities.append(opp)
        
        # Rank by magnitude of mispricing so large short-side signals surface alongside long
        opportunities.sort(key=lambda x: abs(x.edge), reverse=True)

        logger.info(f"Found {len(opportunities)} opportunities with |edge| >= {self.min_edge:.0%}")
        return opportunities


# Module-level singleton
_calculator: Optional[EdgeCalculator] = None

def get_edge_calculator() -> EdgeCalculator:
    """Get or create the singleton calculator instance."""
    global _calculator
    if _calculator is None:
        _calculator = EdgeCalculator()
    return _calculator
