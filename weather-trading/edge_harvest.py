"""
Edge Harvest Scanner (consolidated)

Finds near-certain small-margin trades: BUY NO on buckets far from forecast,
BUY YES on buckets containing the forecast. Both sides produce high-price
low-return trades when model and market strongly agree on directional outcome.
Includes risk detection for forecast uncertainty (model spread, fronts).

This is the single canonical implementation. Previously split across
edge_harvest.py and edge_harvest_scanner.py (retired in PD-144 R2).
YES-side symmetry added in PD-195.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# PD-221: cached read-only V2 ClobClient for orderbook reads.
# No key required (orderbook reads are public per Polymarket V2 docs).
# Avoids per-call PolymarketExecutor reinstantiation + credential-derive
# network call that was the V1→V2 migration breakage in _fetch_order_book.
# Codex Falsifier F2 polish: double-check lock prevents duplicate construction.
_RO_CLIENT = None
_RO_CLIENT_LOCK = threading.Lock()


def _get_ro_client():
    """Cached read-only V2 ClobClient for orderbook reads."""
    global _RO_CLIENT
    if _RO_CLIENT is None:
        with _RO_CLIENT_LOCK:
            if _RO_CLIENT is None:
                from py_clob_client_v2 import ClobClient
                _RO_CLIENT = ClobClient(host="https://clob.polymarket.com", chain_id=137)
    return _RO_CLIENT


@dataclass
class FrontWarning:
    """Warning about approaching weather front or high uncertainty."""
    city: str
    date: str
    warning_type: str  # "MODEL_SPREAD", "LOW_CONFIDENCE"
    severity: str  # "LOW", "MEDIUM", "HIGH"
    description: str
    model_spread: Optional[float] = None


@dataclass
class EdgeHarvestOpportunity:
    """A potential edge harvest trade."""
    # Market info
    city: str
    target_date: str
    bucket_low: Optional[float]  # None for "or below"
    bucket_high: Optional[float]  # None for "or above"
    bucket_str: str  # Display string like "≤35°F" or "≤10°C"

    # Pricing
    yes_price: float
    no_price: float
    potential_return_pct: float  # (1 - no_price) / no_price * 100

    # Distance from forecast
    forecast_temp: float
    bands_away: int  # How many bucket-widths from forecast
    degrees_away: float  # Actual distance in native unit

    # Risk assessment
    risk_tier: str  # "LOW", "MEDIUM", "HIGH"
    risk_score: int  # 1-10 (10 = highest risk)
    risk_factors: List[str]  # Explanations

    # Model spread (uncertainty indicator, always in °F)
    model_spread: float  # Max - Min of model forecasts
    ecmwf_temp: Optional[float]
    gfs_temp: Optional[float]
    nws_temp: Optional[float]

    # Front warning (structured object for rich filtering)
    front_warning: Optional[FrontWarning]
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

    # PD-195: "NO" (buy NO far from forecast) or "YES" (buy YES inside forecast band)
    recommended_side: str = "NO"

    # PD-321 R3: "high" or "low" — which daily extreme this market resolves on
    market_type: str = "high"

    # Codex R3/R5 tradability — propagated from WeatherMarket; guards api.py /api/trade
    # against orders to markets whose CLOB book is closed.
    accepting_orders: bool = True

    @property
    def bucket(self) -> str:
        """Alias for bucket_str (backwards compatibility with auto_harvest)."""
        return self.bucket_str


class EdgeHarvestScanner:
    """
    Scans for edge harvest opportunities.

    Strategy: Buy NO on buckets far from forecast to collect 0.5-2% returns.
    """

    # Thresholds
    # Distance thresholds in BANDS (each band = 1 bucket width).
    # Polymarket resolves the daily high to integer °F; an F-bucket
    # labeled "86-87°F" covers integer outcomes {86, 87} = 2 outcomes wide.
    # C-buckets are single-integer ("be 22°C") = 1 outcome wide.
    # Original PD-321 R1 mistakenly set BUCKET_WIDTH_F = 1.0; reverted
    # 2026-05-21 after operator caught the doubled band counts.
    AGGRESSIVE_BANDS = 2  # 2 bucket-widths away (=4°F F-markets, =2°C C-markets)
    CONSERVATIVE_BANDS = 3  # 3 bucket-widths away (=6°F F-markets, =3°C C-markets)

    # Risk thresholds (in °F; converted for °C markets)
    HIGH_MODEL_SPREAD = 6.0  # °F - indicates uncertainty
    MEDIUM_MODEL_SPREAD = 4.0  # °F

    # Minimum return to consider (PD-195: lowered from 0.5 to 0.1 to keep 99.1¢+ trades)
    MIN_RETURN_PCT = 0.1

    # Price-based safety thresholds: price above this = safe regardless of distance
    SAFE_NO_PRICE = 0.90   # 90¢+ NO = genuinely conservative (≤10% YES probability)
    SAFE_YES_PRICE = 0.90  # 90¢+ YES = near-certain hit (PD-195 YES-side mirror)

    # Bucket widths by unit. Polymarket resolves daily extreme to integer degrees;
    # bucket coverage in outcome space determines band size.
    BUCKET_WIDTH_F = 2.0  # F-bucket "86-87°F" covers integers {86, 87} → 2 outcomes
    BUCKET_WIDTH_C = 1.0  # C-bucket "22°C" covers integer {22} → 1 outcome
    
    def __init__(self):
        pass
    
    def _bucket_width(self, unit: str = "F") -> float:
        """Get bucket width for the given temperature unit."""
        return self.BUCKET_WIDTH_C if unit == "C" else self.BUCKET_WIDTH_F

    def calculate_bands_away(
        self,
        forecast: float,
        bucket_low: Optional[float],
        bucket_high: Optional[float],
        unit: str = "F",
    ) -> Tuple[int, float]:
        """
        Calculate how many bands and degrees away a bucket is from forecast.

        Args:
            unit: "F" or "C" - determines bucket width used for band calculation

        Returns (bands_away, degrees_away)
        """
        bucket_width = self._bucket_width(unit)

        # Handle "or below" buckets (bucket_low is None/-inf)
        if bucket_low is None or bucket_low == float('-inf'):
            if bucket_high is None:
                return 0, 0
            # Distance from forecast to bucket ceiling
            if forecast <= bucket_high:
                return 0, 0
            degrees = forecast - bucket_high
            bands = int(degrees / bucket_width)
            return bands, degrees

        # Handle "or above" buckets (bucket_high is None/inf)
        if bucket_high is None or bucket_high == float('inf'):
            if bucket_low is None:
                return 0, 0
            # Distance from forecast to bucket floor
            if forecast >= bucket_low:
                return 0, 0
            degrees = bucket_low - forecast
            bands = int(degrees / bucket_width)
            return bands, degrees

        # Normal bucket
        if bucket_low <= forecast <= bucket_high:
            return 0, 0

        if forecast < bucket_low:
            degrees = bucket_low - forecast
        else:
            degrees = forecast - bucket_high

        bands = int(degrees / bucket_width)
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
    
    def detect_front_warnings(
        self,
        city: str,
        target_date: str,
        forecast,  # DailyForecast
    ) -> List[FrontWarning]:
        """
        Detect conditions that increase forecast uncertainty.

        Returns list of FrontWarning objects (empty if no warnings).
        Absorbed from edge_harvest_scanner.py (PD-144 R2).
        """
        warnings = []

        # Check model spread (ECMWF vs GFS) -- always in °F
        ecmwf = getattr(forecast, 'ecmwf_high', None)
        gfs = getattr(forecast, 'gfs_high', None)
        if ecmwf is not None and gfs is not None:
            spread = abs(ecmwf - gfs)
            if spread >= 8:
                warnings.append(FrontWarning(
                    city=city, date=target_date,
                    warning_type="MODEL_SPREAD", severity="HIGH",
                    description=f"Models disagree by {spread:.0f}°F -- major front likely",
                    model_spread=spread,
                ))
            elif spread >= 5:
                warnings.append(FrontWarning(
                    city=city, date=target_date,
                    warning_type="MODEL_SPREAD", severity="MEDIUM",
                    description=f"Models disagree by {spread:.0f}°F -- elevated uncertainty",
                    model_spread=spread,
                ))
            elif spread >= 3:
                warnings.append(FrontWarning(
                    city=city, date=target_date,
                    warning_type="MODEL_SPREAD", severity="LOW",
                    description=f"Models disagree by {spread:.0f}°F -- minor uncertainty",
                    model_spread=spread,
                ))

        # Check forecast confidence
        confidence = getattr(forecast, 'confidence', None)
        if confidence is not None:
            if confidence < 0.5:
                warnings.append(FrontWarning(
                    city=city, date=target_date,
                    warning_type="LOW_CONFIDENCE", severity="HIGH",
                    description=f"Forecast confidence only {confidence*100:.0f}%",
                ))
            elif confidence < 0.7:
                warnings.append(FrontWarning(
                    city=city, date=target_date,
                    warning_type="LOW_CONFIDENCE", severity="MEDIUM",
                    description=f"Forecast confidence {confidence*100:.0f}%",
                ))

        return warnings
    
    def calculate_risk(
        self,
        bands_away: int,
        degrees_away: float,
        model_spread: float,
        front_warnings: List[FrontWarning],
        price: Optional[float] = None,
        side: str = "NO",
        no_price: Optional[float] = None,  # legacy alias, accepted for backwards compat
    ) -> Tuple[str, int, List[str]]:
        """
        Calculate risk tier and score (PD-195: side-aware messaging, math unchanged).

        For NO trades: bands_away = distance from forecast to bucket; price = no_price.
        For YES trades: bands_away = margin from forecast to nearest bucket boundary; price = yes_price.
        In both cases, larger bands_away = safer, higher price = safer.

        Returns (tier, score, factors)
        """
        # Backwards compatibility: accept legacy `no_price` kwarg
        if price is None:
            price = no_price
        if price is None:
            raise TypeError("calculate_risk requires 'price' (or legacy 'no_price') kwarg")
        score = 0
        factors = []

        # Distance factor (lower bands = higher risk; interpretation differs by side)
        if side == "YES":
            distance_label = "boundary"
        else:
            distance_label = "forecast"
        # Reverted 2026-05-21 to original cutoffs alongside BUCKET_WIDTH_F=2.0.
        # ≤2 bands = ≤4°F (F) / ≤2°C (C) close; ≤3 bands = ≤6°F / ≤3°C moderate.
        if bands_away <= 2:
            score += 4
            factors.append(f"Close to {distance_label} ({bands_away} bands / {degrees_away:.1f} away)")
        elif bands_away <= 3:
            score += 2
            factors.append(f"Moderate distance ({bands_away} bands / {degrees_away:.1f} away)")
        else:
            score += 1
            factors.append(f"Far from {distance_label} ({bands_away} bands / {degrees_away:.1f} away)")

        # Model spread factor
        if model_spread >= self.HIGH_MODEL_SPREAD:
            score += 4
            factors.append(f"High model disagreement ({model_spread:.1f}°F spread)")
        elif model_spread >= self.MEDIUM_MODEL_SPREAD:
            score += 2
            factors.append(f"Moderate model disagreement ({model_spread:.1f}°F spread)")

        # Front warnings (structured severity from FrontWarning objects)
        for warning in front_warnings:
            if warning.severity == "HIGH":
                score += 4
                factors.append(f"⚠️ {warning.description}")
            elif warning.severity == "MEDIUM":
                score += 2
                factors.append(f"⚡ {warning.description}")
            elif warning.severity == "LOW":
                score += 1

        # Price factor — low price means market disagrees with our directional call
        # This is the strongest signal: the market aggregates all information
        other_side = "YES" if side == "NO" else "NO"
        if price < 0.60:
            score += 5
            factors.append(f"Market pricing majority risk ({side} at ${price:.2f}, {other_side} >{(1-price)*100:.0f}%)")
        elif price < 0.75:
            score += 4
            factors.append(f"Market pricing significant risk ({side} at ${price:.2f}, {other_side} >{(1-price)*100:.0f}%)")
        elif price < 0.85:
            score += 3
            factors.append(f"Market pricing moderate risk ({side} at ${price:.2f})")
        elif price < 0.95:
            score += 1
            factors.append(f"Market pricing low risk ({side} at ${price:.2f})")

        # Determine tier
        if score >= 7:
            tier = "HIGH"
        elif score >= 4:
            tier = "MEDIUM"
        else:
            tier = "LOW"

        return tier, min(score, 10), factors

    def _fetch_order_book(self, token_id: str) -> dict:
        """Fetch order book for a token. Returns best bid/ask info.

        PD-221: V2 ClobClient.get_order_book returns dict (not object). Uses
        module-cached read-only client to avoid per-call credential derive.
        Sort: bids ascending (best=last), asks descending (best=last).
        Verified empirically against LA + Dem Pres 2028 markets + V2 SDK
        get_price helper cross-check.
        """
        try:
            client = _get_ro_client()
            book = client.get_order_book(token_id)

            # Codex F6: error-shaped 200 dicts must surface, not silently zero out.
            if isinstance(book, dict) and "error" in book:
                logger.warning(f"Orderbook returned error for token_id={token_id}: {book['error']}")
                return {"best_ask_price": 0.0, "best_ask_size": 0.0,
                        "best_bid_price": 0.0, "best_bid_size": 0.0, "spread": 0.0}

            bids = book.get("bids", [])
            asks = book.get("asks", [])
            best_ask = float(asks[-1]["price"]) if asks else 0.0
            best_ask_size = float(asks[-1]["size"]) if asks else 0.0
            best_bid = float(bids[-1]["price"]) if bids else 0.0
            best_bid_size = float(bids[-1]["size"]) if bids else 0.0

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

            # Shared computation (PD-195: hoisted so YES branch can reuse)
            unit = getattr(market, 'bucket_unit', 'F')
            # PD-321 R3: route highest-temp markets to forecast.high, lowest-temp to forecast.low.
            mtype = getattr(market, 'market_type', 'high')
            if mtype == 'low':
                # PD-325 follow-up: refuse LOW opps when low_f is the synthetic
                # `avg_high - 15` fallback. Synthetic lows are wildly off for many
                # climates and produced confidently-wrong NO recommendations
                # (pos_707 lost ~$4 on London May 26 17°C LOW with synthetic-low forecast).
                if getattr(forecast, 'low_source', 'OPEN_METEO') == 'SYNTHETIC':
                    continue
                forecast_temp = forecast.low_c if unit == "C" else forecast.low_f
            else:
                forecast_temp = forecast.high_c if unit == "C" else forecast.high_f
            if forecast_temp is None:
                # Forecast lacks the requested extreme (e.g. some sources omit lows). Skip.
                continue

            bands_away, degrees_away = self.calculate_bands_away(
                forecast_temp,
                market.bucket_low,
                market.bucket_high,
                unit=unit,
            )

            no_price = market.no_price
            if no_price is None or no_price <= 0:
                no_price = 1.0 - (market.yes_price or 0)

            ecmwf = getattr(forecast, 'ecmwf_high', None)
            gfs = getattr(forecast, 'gfs_high', None)
            nws = getattr(forecast, 'nws_high', None)
            model_spread = self.calculate_model_spread(ecmwf, gfs, nws)
            front_warnings = self.detect_front_warnings(
                market.city_key, market.target_date, forecast
            )

            if market.bucket_low is None or market.bucket_low == float('-inf'):
                bucket_str = f"≤{market.bucket_high}°{unit}"
            elif market.bucket_high is None or market.bucket_high == float('inf'):
                bucket_str = f"≥{market.bucket_low}°{unit}"
            else:
                bucket_str = f"{market.bucket_low}-{market.bucket_high}°{unit}"

            # --- NO-side evaluation ---
            no_passes = True
            if bands_away < self.AGGRESSIVE_BANDS and no_price < self.SAFE_NO_PRICE:
                no_passes = False
            if no_price >= 1.0:
                no_passes = False
            potential_return = 0.0
            if no_passes:
                potential_return = (1.0 - no_price) / no_price * 100
                if potential_return < self.MIN_RETURN_PCT:
                    no_passes = False

            if no_passes:
                risk_tier, risk_score, risk_factors = self.calculate_risk(
                    bands_away, degrees_away, model_spread, front_warnings,
                    price=no_price, side="NO",
                )
                if no_price >= self.SAFE_NO_PRICE:
                    threshold_type = "CONSERVATIVE"
                elif bands_away >= self.CONSERVATIVE_BANDS and no_price >= 0.80:
                    threshold_type = "CONSERVATIVE"
                else:
                    threshold_type = "AGGRESSIVE"

                no_opp = EdgeHarvestOpportunity(
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
                    front_warning=front_warnings[0] if front_warnings else None,
                    front_warning_reason=front_warnings[0].description if front_warnings else None,
                    threshold_type=threshold_type,
                    clob_token_ids=market.clob_token_ids,
                    market_url=getattr(market, 'market_url', ''),
                    liquidity=getattr(market, 'liquidity', 0),
                    hours_remaining=getattr(market, 'hours_remaining', 0),
                    recommended_side="NO",
                    market_type=mtype,
                    accepting_orders=bool(getattr(market, 'accepting_orders', True)),
                )
                no_token_id = market.clob_token_ids[1] if len(market.clob_token_ids) > 1 else None
                if no_token_id:
                    ob_data = self._fetch_order_book(no_token_id)
                    no_opp.best_ask_price = ob_data["best_ask_price"]
                    no_opp.best_ask_size = ob_data["best_ask_size"]
                    no_opp.best_bid_price = ob_data["best_bid_price"]
                    no_opp.best_bid_size = ob_data["best_bid_size"]
                    no_opp.spread = ob_data["spread"]
                    if no_opp.best_ask_price > 0:
                        no_opp.potential_return_pct = ((1.0 - no_opp.best_ask_price) / no_opp.best_ask_price) * 100
                opportunities.append(no_opp)

            # --- YES-side evaluation (PD-195): forecast inside band, high YES price ---
            # Includes open-ended bands (≤X°F when forecast < X; ≥X°F when forecast > X)
            b_low = market.bucket_low
            b_high = market.bucket_high
            forecast_in_band = False
            if b_low is None or b_low == float('-inf'):
                forecast_in_band = (b_high is not None and forecast_temp <= b_high)
            elif b_high is None or b_high == float('inf'):
                forecast_in_band = (b_low is not None and forecast_temp >= b_low)
            else:
                forecast_in_band = (b_low <= forecast_temp <= b_high)
            if forecast_in_band:
                yes_price = market.yes_price
                if yes_price is None or yes_price <= 0:
                    yes_price = 1.0 - (market.no_price or 0)
                if self.SAFE_YES_PRICE <= yes_price < 1.0:
                    yes_return = (1.0 - yes_price) / yes_price * 100
                    if yes_return >= self.MIN_RETURN_PCT:
                        # Margin = distance from forecast to nearest bucket boundary.
                        # Open-ended bands: only the bounded side matters.
                        margin_candidates = []
                        if b_low is not None and b_low != float('-inf'):
                            margin_candidates.append(forecast_temp - b_low)
                        if b_high is not None and b_high != float('inf'):
                            margin_candidates.append(b_high - forecast_temp)
                        margin = min(margin_candidates) if margin_candidates else 0.0
                        margin_bands = int(margin / self._bucket_width(unit))
                        y_tier, y_score, y_factors = self.calculate_risk(
                            margin_bands, margin, model_spread, front_warnings,
                            price=yes_price, side="YES",
                        )
                        y_thresh = "CONSERVATIVE" if yes_price >= self.SAFE_YES_PRICE else "AGGRESSIVE"
                        yes_opp = EdgeHarvestOpportunity(
                            city=market.city_key,
                            target_date=market.target_date,
                            bucket_low=market.bucket_low if market.bucket_low != float('-inf') else None,
                            bucket_high=market.bucket_high if market.bucket_high != float('inf') else None,
                            bucket_str=bucket_str,
                            yes_price=yes_price,
                            no_price=market.no_price if market.no_price is not None else (1.0 - yes_price),
                            potential_return_pct=round(yes_return, 2),
                            forecast_temp=round(forecast_temp, 1),
                            bands_away=margin_bands,
                            degrees_away=round(margin, 1),
                            risk_tier=y_tier,
                            risk_score=y_score,
                            risk_factors=y_factors,
                            model_spread=round(model_spread, 1),
                            ecmwf_temp=round(ecmwf, 1) if ecmwf else None,
                            gfs_temp=round(gfs, 1) if gfs else None,
                            nws_temp=round(nws, 1) if nws else None,
                            front_warning=front_warnings[0] if front_warnings else None,
                            front_warning_reason=front_warnings[0].description if front_warnings else None,
                            threshold_type=y_thresh,
                            clob_token_ids=market.clob_token_ids,
                            market_url=getattr(market, 'market_url', ''),
                            liquidity=getattr(market, 'liquidity', 0),
                            hours_remaining=getattr(market, 'hours_remaining', 0),
                            recommended_side="YES",
                            market_type=mtype,
                            accepting_orders=bool(getattr(market, 'accepting_orders', True)),
                        )
                        yes_token_id = market.clob_token_ids[0] if len(market.clob_token_ids) > 0 else None
                        if yes_token_id:
                            ob_data = self._fetch_order_book(yes_token_id)
                            yes_opp.best_ask_price = ob_data["best_ask_price"]
                            yes_opp.best_ask_size = ob_data["best_ask_size"]
                            yes_opp.best_bid_price = ob_data["best_bid_price"]
                            yes_opp.best_bid_size = ob_data["best_bid_size"]
                            yes_opp.spread = ob_data["spread"]
                            if yes_opp.best_ask_price > 0:
                                yes_opp.potential_return_pct = ((1.0 - yes_opp.best_ask_price) / yes_opp.best_ask_price) * 100
                        opportunities.append(yes_opp)
        
        # Sort by potential return (highest first)
        opportunities.sort(key=lambda x: x.potential_return_pct, reverse=True)
        
        return opportunities


def get_edge_harvest_scanner() -> EdgeHarvestScanner:
    """Get singleton scanner instance."""
    return EdgeHarvestScanner()
