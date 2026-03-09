"""
Edge Harvest Scanner

Finds opportunities to buy NO on extreme buckets far from forecast.
Includes risk detection for forecast uncertainty (model spread, fronts).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class EdgeHarvestOpportunity:
    """A potential edge harvest trade."""
    # Market info
    city: str
    target_date: str
    bucket_low: Optional[float]  # None for "or below"
    bucket_high: Optional[float]  # None for "or above"
    bucket_str: str  # Display string like "≤35°F"
    
    # Pricing
    yes_price: float
    no_price: float
    potential_return_pct: float  # (1 - no_price) / no_price * 100
    
    # Distance from forecast
    forecast_temp: float
    bands_away: int  # How many 2°F bands from forecast
    degrees_away: float  # Actual distance in °F
    
    # Risk assessment
    risk_tier: str  # "LOW", "MEDIUM", "HIGH"
    risk_score: int  # 1-10 (10 = highest risk)
    risk_factors: List[str]  # Explanations
    
    # Model spread (uncertainty indicator)
    model_spread: float  # Max - Min of model forecasts
    ecmwf_temp: Optional[float]
    gfs_temp: Optional[float]
    nws_temp: Optional[float]
    
    # Front warning
    front_warning: bool
    front_warning_reason: Optional[str]
    
    # Classification
    threshold_type: str  # "AGGRESSIVE" (2 bands) or "CONSERVATIVE" (3 bands)
    
    # Token IDs for trading
    clob_token_ids: Tuple[Optional[str], Optional[str]]
    market_url: str
    liquidity: float
    hours_remaining: float

    # Order book data
    best_ask_price: float = 0.0
    best_ask_size: float = 0.0
    best_bid_price: float = 0.0
    best_bid_size: float = 0.0
    spread: float = 0.0  # ask - bid


class EdgeHarvestScanner:
    """
    Scans for edge harvest opportunities.
    
    Strategy: Buy NO on buckets far from forecast to collect 0.5-2% returns.
    """
    
    # Thresholds
    AGGRESSIVE_BANDS = 2  # 4°F away - higher ROI, more risk
    CONSERVATIVE_BANDS = 3  # 6°F away - lower ROI, safer
    
    # Risk thresholds
    HIGH_MODEL_SPREAD = 6.0  # °F - indicates uncertainty
    MEDIUM_MODEL_SPREAD = 4.0  # °F
    
    # Minimum return to consider
    MIN_RETURN_PCT = 0.5
    
    BUCKET_WIDTH = 2.0  # Standard Polymarket bucket width
    
    def __init__(self):
        pass
    
    def calculate_bands_away(
        self, 
        forecast: float, 
        bucket_low: Optional[float], 
        bucket_high: Optional[float]
    ) -> Tuple[int, float]:
        """
        Calculate how many bands and degrees away a bucket is from forecast.
        
        Returns (bands_away, degrees_away)
        """
        # Handle "or below" buckets (bucket_low is None/-inf)
        if bucket_low is None or bucket_low == float('-inf'):
            if bucket_high is None:
                return 0, 0
            # Distance from forecast to bucket ceiling
            if forecast <= bucket_high:
                return 0, 0
            degrees = forecast - bucket_high
            bands = int(degrees / self.BUCKET_WIDTH)
            return bands, degrees
        
        # Handle "or above" buckets (bucket_high is None/inf)
        if bucket_high is None or bucket_high == float('inf'):
            if bucket_low is None:
                return 0, 0
            # Distance from forecast to bucket floor
            if forecast >= bucket_low:
                return 0, 0
            degrees = bucket_low - forecast
            bands = int(degrees / self.BUCKET_WIDTH)
            return bands, degrees
        
        # Normal bucket
        if bucket_low <= forecast <= bucket_high:
            return 0, 0
        
        if forecast < bucket_low:
            degrees = bucket_low - forecast
        else:
            degrees = forecast - bucket_high
        
        bands = int(degrees / self.BUCKET_WIDTH)
        return bands, degrees
    
    def calculate_model_spread(
        self,
        ecmwf: Optional[float],
        gfs: Optional[float],
        nws: Optional[float]
    ) -> float:
        """Calculate spread between model forecasts."""
        temps = [t for t in [ecmwf, gfs, nws] if t is not None]
        if len(temps) < 2:
            return 0.0
        return max(temps) - min(temps)
    
    def detect_front_warning(
        self,
        model_spread: float,
        forecast_temp: float,
        city: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect if conditions suggest a front or high uncertainty.
        
        Returns (has_warning, reason)
        """
        warnings = []
        
        # High model disagreement = likely front timing uncertainty
        if model_spread >= self.HIGH_MODEL_SPREAD:
            warnings.append(f"High model spread ({model_spread:.1f}°F) - possible front timing uncertainty")
        
        # Seasonal transition periods are riskier
        # (could add more sophisticated checks here)
        
        if warnings:
            return True, "; ".join(warnings)
        return False, None
    
    def calculate_risk(
        self,
        bands_away: int,
        degrees_away: float,
        model_spread: float,
        front_warning: bool,
        no_price: float
    ) -> Tuple[str, int, List[str]]:
        """
        Calculate risk tier and score.
        
        Returns (tier, score, factors)
        """
        score = 0
        factors = []
        
        # Distance factor (lower bands = higher risk)
        if bands_away <= 2:
            score += 4
            factors.append(f"Close to forecast ({bands_away} bands / {degrees_away:.0f}°F)")
        elif bands_away <= 3:
            score += 2
            factors.append(f"Moderate distance ({bands_away} bands / {degrees_away:.0f}°F)")
        else:
            score += 1
            factors.append(f"Far from forecast ({bands_away} bands / {degrees_away:.0f}°F)")
        
        # Model spread factor
        if model_spread >= self.HIGH_MODEL_SPREAD:
            score += 4
            factors.append(f"High model disagreement ({model_spread:.1f}°F spread)")
        elif model_spread >= self.MEDIUM_MODEL_SPREAD:
            score += 2
            factors.append(f"Moderate model disagreement ({model_spread:.1f}°F spread)")
        
        # Front warning
        if front_warning:
            score += 2
            factors.append("⚠️ Front/uncertainty warning active")
        
        # Price factor (very cheap NO = market sees risk)
        if no_price < 0.95:
            score += 2
            factors.append(f"Market pricing higher risk (NO at ${no_price:.2f})")
        
        # Determine tier
        if score >= 7:
            tier = "HIGH"
        elif score >= 4:
            tier = "MEDIUM"
        else:
            tier = "LOW"
        
        return tier, min(score, 10), factors

    def _fetch_order_book(self, token_id: str) -> dict:
        """Fetch order book for a token. Returns best bid/ask info."""
        try:
            from executor import PolymarketExecutor
            executor = PolymarketExecutor(dry_run=False)
            book = executor.client.get_order_book(token_id)
            
            best_ask = float(book.asks[-1].price) if book.asks else 0.0
            best_ask_size = float(book.asks[-1].size) if book.asks else 0.0
            best_bid = float(book.bids[-1].price) if book.bids else 0.0
            best_bid_size = float(book.bids[-1].size) if book.bids else 0.0
            
            return {
                "best_ask_price": best_ask,
                "best_ask_size": best_ask_size,
                "best_bid_price": best_bid,
                "best_bid_size": best_bid_size,
                "spread": best_ask - best_bid if best_ask and best_bid else 0.0
            }
        except Exception as e:
            logger.warning(f"Failed to fetch order book for {token_id}: {e}")
            return {"best_ask_price": 0.0, "best_ask_size": 0.0, "best_bid_price": 0.0, "best_bid_size": 0.0, "spread": 0.0}
    
    def find_opportunities(
        self,
        markets: List,  # WeatherMarket objects from scanner
        forecasts: dict,  # {(city, date): DailyForecast}
    ) -> List[EdgeHarvestOpportunity]:
        """
        Find edge harvest opportunities from market data.
        
        Returns list of opportunities sorted by potential return.
        """
        opportunities = []
        
        for market in markets:
            # Get forecast for this market
            key = (market.city_key, market.target_date)
            forecast = forecasts.get(key)
            if not forecast:
                continue
            
            forecast_temp = forecast.high_f
            
            # Calculate distance
            bands_away, degrees_away = self.calculate_bands_away(
                forecast_temp, 
                market.bucket_low, 
                market.bucket_high
            )
            
            # Skip if too close to forecast
            if bands_away < self.AGGRESSIVE_BANDS:
                continue
            
            # Get NO price (we're buying NO)
            no_price = market.no_price
            if no_price is None or no_price <= 0:
                no_price = 1.0 - market.yes_price
            
            # Calculate potential return
            if no_price >= 1.0:
                continue
            potential_return = (1.0 - no_price) / no_price * 100
            
            # Skip if return too low
            if potential_return < self.MIN_RETURN_PCT:
                continue
            
            # Get model data
            ecmwf = getattr(forecast, 'ecmwf_high', None)
            gfs = getattr(forecast, 'gfs_high', None)
            nws = getattr(forecast, 'nws_high', None)
            
            # Calculate model spread
            model_spread = self.calculate_model_spread(ecmwf, gfs, nws)
            
            # Detect front warning
            front_warning, front_reason = self.detect_front_warning(
                model_spread, forecast_temp, market.city_key
            )
            
            # Calculate risk
            risk_tier, risk_score, risk_factors = self.calculate_risk(
                bands_away, degrees_away, model_spread, front_warning, no_price
            )
            
            # Determine threshold type
            if bands_away >= self.CONSERVATIVE_BANDS:
                threshold_type = "CONSERVATIVE"
            else:
                threshold_type = "AGGRESSIVE"
            
            # Build bucket string
            if market.bucket_low is None or market.bucket_low == float('-inf'):
                bucket_str = f"≤{market.bucket_high}°F"
            elif market.bucket_high is None or market.bucket_high == float('inf'):
                bucket_str = f"≥{market.bucket_low}°F"
            else:
                bucket_str = f"{market.bucket_low}-{market.bucket_high}°F"
            
            opp = EdgeHarvestOpportunity(
                city=market.city_key,
                target_date=market.target_date,
                bucket_low=market.bucket_low if market.bucket_low != float('-inf') else None,
                bucket_high=market.bucket_high if market.bucket_high != float('inf') else None,
                bucket_str=bucket_str,
                yes_price=market.yes_price,
                no_price=no_price,
                potential_return_pct=round(potential_return, 2),
                forecast_temp=round(forecast_temp, 1),
                bands_away=bands_away,
                degrees_away=round(degrees_away, 1),
                risk_tier=risk_tier,
                risk_score=risk_score,
                risk_factors=risk_factors,
                model_spread=round(model_spread, 1),
                ecmwf_temp=round(ecmwf, 1) if ecmwf else None,
                gfs_temp=round(gfs, 1) if gfs else None,
                nws_temp=round(nws, 1) if nws else None,
                front_warning=front_warning,
                front_warning_reason=front_reason,
                threshold_type=threshold_type,
                clob_token_ids=market.clob_token_ids,
                market_url=getattr(market, 'market_url', ''),
                liquidity=getattr(market, 'liquidity', 0),
                hours_remaining=getattr(market, 'hours_remaining', 0),
            )
            
            # Fetch order book for NO token (index 1)
            no_token_id = market.clob_token_ids[1] if len(market.clob_token_ids) > 1 else None
            if no_token_id:
                ob_data = self._fetch_order_book(no_token_id)
                opp.best_ask_price = ob_data["best_ask_price"]
                opp.best_ask_size = ob_data["best_ask_size"]
                opp.best_bid_price = ob_data["best_bid_price"]
                opp.best_bid_size = ob_data["best_bid_size"]
                opp.spread = ob_data["spread"]
                
                # Recalculate return based on actual ask price
                if opp.best_ask_price > 0:
                    opp.potential_return_pct = ((1.0 - opp.best_ask_price) / opp.best_ask_price) * 100
            
            opportunities.append(opp)
        
        # Sort by potential return (highest first)
        opportunities.sort(key=lambda x: x.potential_return_pct, reverse=True)
        
        return opportunities


def get_edge_harvest_scanner() -> EdgeHarvestScanner:
    """Get singleton scanner instance."""
    return EdgeHarvestScanner()
