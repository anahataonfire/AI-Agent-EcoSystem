"""
Edge Harvest Scanner

Finds "edge harvesting" opportunities - buying NO on buckets
far from forecast to collect 0.5-2% daily returns.

Includes risk detection for fronts and forecast uncertainty.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class FrontWarning:
    """Warning about approaching weather front or high uncertainty."""
    city: str
    date: str
    warning_type: str  # "MODEL_SPREAD", "TEMP_SWING", "PRECIPITATION"
    severity: str  # "LOW", "MEDIUM", "HIGH"
    description: str
    model_spread: Optional[float] = None  # °F difference between models
    temp_swing: Optional[float] = None  # Day-to-day change


@dataclass
class EdgeHarvestOpportunity:
    """A single edge harvest opportunity."""
    id: str
    city: str
    target_date: str
    bucket: str
    bucket_low: float
    bucket_high: float
    forecast_temp: float
    bands_away: int
    degrees_away: float
    threshold_type: str  # "CONSERVATIVE" (3 bands) or "AGGRESSIVE" (2 bands)
    no_price: float
    potential_return_pct: float
    risk_score: int  # 1-10, higher = riskier
    risk_factors: List[str]
    clob_token_ids: Tuple[Optional[str], Optional[str]]
    liquidity: float
    market_url: str
    front_warning: Optional[FrontWarning] = None


class EdgeHarvestScanner:
    """
    Scans for edge harvest opportunities.
    
    Strategy: Buy NO on buckets far from forecast.
    - Conservative: 3+ bands away (6°F) - 99.9% win rate
    - Aggressive: 2+ bands away (4°F) - 99.7% win rate
    """
    
    def __init__(
        self,
        bucket_width: float = 2.0,
        min_return_pct: float = 0.5,
        conservative_bands: int = 3,
        aggressive_bands: int = 2,
    ):
        self.bucket_width = bucket_width
        self.min_return_pct = min_return_pct
        self.conservative_bands = conservative_bands
        self.aggressive_bands = aggressive_bands
    
    def detect_front_warnings(
        self,
        city: str,
        target_date: str,
        forecast: 'DailyForecast'
    ) -> List[FrontWarning]:
        """
        Detect conditions that increase forecast uncertainty.
        
        Returns list of warnings if any risk factors found.
        """
        warnings = []
        
        # Check model spread (ECMWF vs GFS)
        if forecast.ecmwf_high and forecast.gfs_high:
            spread = abs(forecast.ecmwf_high - forecast.gfs_high)
            
            if spread >= 8:
                warnings.append(FrontWarning(
                    city=city,
                    date=target_date,
                    warning_type="MODEL_SPREAD",
                    severity="HIGH",
                    description=f"Models disagree by {spread:.0f}°F - major front likely",
                    model_spread=spread
                ))
            elif spread >= 5:
                warnings.append(FrontWarning(
                    city=city,
                    date=target_date,
                    warning_type="MODEL_SPREAD",
                    severity="MEDIUM",
                    description=f"Models disagree by {spread:.0f}°F - elevated uncertainty",
                    model_spread=spread
                ))
            elif spread >= 3:
                warnings.append(FrontWarning(
                    city=city,
                    date=target_date,
                    warning_type="MODEL_SPREAD",
                    severity="LOW",
                    description=f"Models disagree by {spread:.0f}°F - minor uncertainty",
                    model_spread=spread
                ))
        
        # Check forecast confidence
        if hasattr(forecast, 'confidence') and forecast.confidence:
            if forecast.confidence < 0.5:
                warnings.append(FrontWarning(
                    city=city,
                    date=target_date,
                    warning_type="LOW_CONFIDENCE",
                    severity="HIGH",
                    description=f"Forecast confidence only {forecast.confidence*100:.0f}%"
                ))
            elif forecast.confidence < 0.7:
                warnings.append(FrontWarning(
                    city=city,
                    date=target_date,
                    warning_type="LOW_CONFIDENCE",
                    severity="MEDIUM",
                    description=f"Forecast confidence {forecast.confidence*100:.0f}%"
                ))
        
        return warnings
    
    def calculate_bands_away(
        self,
        forecast: float,
        bucket_low: float,
        bucket_high: float
    ) -> int:
        """Calculate how many bands a bucket is from forecast."""
        if bucket_low <= forecast <= bucket_high:
            return 0
        
        if forecast < bucket_low:
            distance = bucket_low - forecast
        else:
            distance = forecast - bucket_high
        
        return int(distance / self.bucket_width)
    
    def calculate_risk_score(
        self,
        bands_away: int,
        forecast: 'DailyForecast',
        front_warnings: List[FrontWarning]
    ) -> Tuple[int, List[str]]:
        """
        Calculate risk score 1-10 for an opportunity.
        
        Lower = safer.
        """
        score = 0
        factors = []
        
        # Base risk from distance
        if bands_away <= 2:
            score += 4
            factors.append("Only 2 bands from forecast")
        elif bands_away == 3:
            score += 2
            factors.append("3 bands from forecast")
        elif bands_away == 4:
            score += 1
        # 5+ bands = minimal base risk
        
        # Add risk for front warnings
        for warning in front_warnings:
            if warning.severity == "HIGH":
                score += 4
                factors.append(f"⚠️ {warning.description}")
            elif warning.severity == "MEDIUM":
                score += 2
                factors.append(f"⚡ {warning.description}")
            elif warning.severity == "LOW":
                score += 1
        
        # Model spread adds uncertainty
        if forecast.ecmwf_high and forecast.gfs_high:
            spread = abs(forecast.ecmwf_high - forecast.gfs_high)
            if spread >= 5:
                score += 2
            elif spread >= 3:
                score += 1
        
        # Low confidence forecast
        if hasattr(forecast, 'confidence') and forecast.confidence:
            if forecast.confidence < 0.6:
                score += 2
                factors.append(f"Low forecast confidence ({forecast.confidence*100:.0f}%)")
        
        # Cap at 10
        score = min(score, 10)
        
        return score, factors
    
    def estimate_no_price(self, bands_away: int) -> float:
        """
        Estimate NO price based on distance from forecast.
        
        Based on typical Polymarket pricing.
        """
        # Typical market pricing by distance
        price_map = {
            2: 0.92,   # 8% return potential
            3: 0.96,   # 4% return potential  
            4: 0.98,   # 2% return potential
            5: 0.99,   # 1% return potential
            6: 0.995,  # 0.5% return potential
        }
        
        if bands_away >= 6:
            return 0.995
        return price_map.get(bands_away, 0.99)
    
    def find_opportunities(
        self,
        markets: List,  # WeatherMarket from scanner
        forecasts: dict,  # (city, date) -> DailyForecast
    ) -> List[EdgeHarvestOpportunity]:
        """
        Find edge harvest opportunities from current markets.
        
        Returns both conservative (3+ bands) and aggressive (2+ bands) opportunities.
        """
        opportunities = []
        
        for market in markets:
            key = (market.city_key, market.target_date)
            forecast = forecasts.get(key)
            
            if not forecast:
                continue
            
            forecast_temp = forecast.high_f
            
            # Calculate distance
            bucket_low = market.bucket_low if market.bucket_low != float('-inf') else forecast_temp - 30
            bucket_high = market.bucket_high if market.bucket_high != float('inf') else forecast_temp + 30
            bucket_center = (bucket_low + bucket_high) / 2
            
            bands_away = self.calculate_bands_away(forecast_temp, bucket_low, bucket_high)
            degrees_away = abs(forecast_temp - bucket_center)
            
            # Skip if too close to forecast
            if bands_away < self.aggressive_bands:
                continue
            
            # Detect front warnings
            front_warnings = self.detect_front_warnings(
                market.city_key, market.target_date, forecast
            )
            
            # Calculate risk
            risk_score, risk_factors = self.calculate_risk_score(
                bands_away, forecast, front_warnings
            )
            
            # Determine threshold type
            if bands_away >= self.conservative_bands:
                threshold_type = "CONSERVATIVE"
            else:
                threshold_type = "AGGRESSIVE"
            
            # Get NO price (we want to buy NO)
            no_price = market.no_price if market.no_price else self.estimate_no_price(bands_away)
            
            # Calculate potential return
            if no_price < 1.0:
                potential_return = (1.0 - no_price) / no_price * 100
            else:
                potential_return = 0
            
            # Skip if return too low
            if potential_return < self.min_return_pct:
                continue
            
            # Format bucket string
            if market.bucket_low == float('-inf'):
                bucket_str = f"≤{market.bucket_high}°F"
            elif market.bucket_high == float('inf'):
                bucket_str = f"≥{market.bucket_low}°F"
            else:
                bucket_str = f"{market.bucket_low}-{market.bucket_high}°F"
            
            opp = EdgeHarvestOpportunity(
                id=f"edge_{market.city_key}_{market.target_date}_{bucket_low}_{bucket_high}".replace("-", "_").replace(".", "_"),
                city=market.city_key,
                target_date=market.target_date,
                bucket=bucket_str,
                bucket_low=bucket_low,
                bucket_high=bucket_high,
                forecast_temp=forecast_temp,
                bands_away=bands_away,
                degrees_away=degrees_away,
                threshold_type=threshold_type,
                no_price=no_price,
                potential_return_pct=round(potential_return, 2),
                risk_score=risk_score,
                risk_factors=risk_factors,
                clob_token_ids=market.clob_token_ids,
                liquidity=getattr(market, 'liquidity', 0),
                market_url=getattr(market, 'market_url', ''),
                front_warning=front_warnings[0] if front_warnings else None
            )
            
            opportunities.append(opp)
        
        # Sort by: threshold type (conservative first), then potential return
        opportunities.sort(
            key=lambda x: (
                0 if x.threshold_type == "CONSERVATIVE" else 1,
                -x.potential_return_pct,
                x.risk_score
            )
        )
        
        return opportunities


def get_edge_harvest_scanner() -> EdgeHarvestScanner:
    """Factory function."""
    return EdgeHarvestScanner()
