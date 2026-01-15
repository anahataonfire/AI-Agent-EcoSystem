"""
Weather Probability Calculator

Calculates the probability that a city's daily high temperature
falls within a specific bucket range, enabling edge detection
for weather trading on Polymarket.
"""

import math
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class BucketProbability:
    """Probability that temperature falls in a bucket."""
    bucket_low: float
    bucket_high: float
    unit: str  # 'F' or 'C'
    probability: float  # 0.0-1.0
    confidence: float  # 0.0-1.0


def norm_cdf(x: float, mean: float, std: float) -> float:
    """
    Calculate cumulative distribution function for normal distribution.
    
    Pure Python implementation - no scipy required.
    Uses the error function approximation.
    
    Args:
        x: Value to evaluate
        mean: Distribution mean
        std: Standard deviation
        
    Returns:
        Probability P(X <= x)
    """
    if std <= 0:
        # Degenerate case - point distribution
        return 1.0 if x >= mean else 0.0
    
    z = (x - mean) / (std * math.sqrt(2))
    return 0.5 * (1 + math.erf(z))


def calculate_bucket_probability(
    forecast_mean: float,
    forecast_std: float,
    bucket_low: float,
    bucket_high: float
) -> float:
    """
    Calculate probability of temperature falling within a bucket.
    
    Uses normal distribution CDF to compute:
    P(bucket_low <= temp <= bucket_high)
    
    Args:
        forecast_mean: Forecasted temperature (mean)
        forecast_std: Forecast uncertainty (standard deviation)
        bucket_low: Lower bound of bucket (use -inf for "or below")
        bucket_high: Upper bound of bucket (use inf for "or above")
        
    Returns:
        Probability between 0.0 and 1.0
    """
    # Handle infinite bounds
    if bucket_low == float('-inf'):
        bucket_low = forecast_mean - 10 * forecast_std  # Effectively -inf
    if bucket_high == float('inf'):
        bucket_high = forecast_mean + 10 * forecast_std  # Effectively +inf
    
    # Calculate P(temp <= bucket_high) - P(temp <= bucket_low)
    prob = norm_cdf(bucket_high, forecast_mean, forecast_std) - \
           norm_cdf(bucket_low, forecast_mean, forecast_std)
    
    # Clamp to valid range
    return max(0.0, min(1.0, prob))


def estimate_forecast_std(
    ecmwf_high: Optional[float] = None,
    gfs_high: Optional[float] = None,
    nws_high: Optional[float] = None,
    default_std: float = 4.0
) -> float:
    """
    Estimate forecast uncertainty from model spread.
    
    When models disagree more, uncertainty is higher.
    This uses the spread between different forecast sources
    as a proxy for forecast uncertainty.
    
    Args:
        ecmwf_high: ECMWF model forecast
        gfs_high: GFS model forecast
        nws_high: NWS forecast (US only)
        default_std: Default std if not enough data
        
    Returns:
        Estimated standard deviation in temperature units
    """
    values = [v for v in [ecmwf_high, gfs_high, nws_high] if v is not None]
    
    if len(values) >= 2:
        # Use model spread as uncertainty proxy
        # Spread = max - min, std ≈ spread / 2
        spread = max(values) - min(values)
        # Minimum uncertainty of 2°F even when models agree
        # Maximum uncertainty of 8°F to avoid extreme values
        return max(2.0, min(8.0, spread / 2 + 1.5))
    
    if len(values) == 1:
        # Single source - use moderate uncertainty
        return 3.5
    
    # No forecast data - use conservative default
    return default_std


def calculate_edge(
    forecast_probability: float,
    market_price: float
) -> float:
    """
    Calculate edge: difference between forecast probability and market price.
    
    Positive edge = buy opportunity (market underpricing)
    Negative edge = potential sell or avoid
    
    Args:
        forecast_probability: Our calculated probability (0.0-1.0)
        market_price: Market's implied probability (0.0-1.0)
        
    Returns:
        Edge as decimal (e.g., 0.15 = 15% edge)
    """
    return forecast_probability - market_price


def analyze_all_buckets(
    forecast_mean: float,
    forecast_std: float,
    buckets: List[Tuple[float, float]],
    market_prices: List[float]
) -> List[dict]:
    """
    Analyze all buckets for a market and identify opportunities.
    
    Args:
        forecast_mean: Forecasted temperature
        forecast_std: Forecast uncertainty
        buckets: List of (low, high) bucket ranges
        market_prices: List of market prices for each bucket
        
    Returns:
        List of analysis dicts sorted by edge (best first)
    """
    results = []
    
    for i, ((bucket_low, bucket_high), market_price) in enumerate(zip(buckets, market_prices)):
        prob = calculate_bucket_probability(
            forecast_mean, forecast_std, bucket_low, bucket_high
        )
        edge = calculate_edge(prob, market_price)
        
        results.append({
            "bucket_index": i,
            "bucket_low": bucket_low,
            "bucket_high": bucket_high,
            "forecast_probability": round(prob, 4),
            "market_price": market_price,
            "edge": round(edge, 4),
            "signal": "BUY" if edge > 0.10 else ("AVOID" if edge < -0.10 else "NEUTRAL")
        })
    
    # Sort by edge (best opportunities first)
    results.sort(key=lambda x: -x["edge"])
    return results


# Example usage and testing
if __name__ == "__main__":
    # Test: Forecast 50°F with 3°F uncertainty
    print("=== Probability Calculator Test ===")
    print(f"Forecast: 50°F ± 3°F (std dev)")
    print()
    
    # Common bucket ranges for a 50°F forecast day
    test_buckets = [
        (float('-inf'), 46, "46°F or below"),
        (46, 48, "46-48°F"),
        (48, 50, "48-50°F"),
        (50, 52, "50-52°F"),
        (52, 54, "52-54°F"),
        (54, float('inf'), "54°F or above"),
    ]
    
    print("Bucket Probabilities:")
    for low, high, label in test_buckets:
        prob = calculate_bucket_probability(50, 3, low, high)
        print(f"  {label}: {prob*100:.1f}%")
    
    print()
    print("=== Edge Detection Example ===")
    print("If market prices '48-50°F' at 5% but we calculate 25%:")
    edge = calculate_edge(0.25, 0.05)
    print(f"  Edge: +{edge*100:.0f}% → BUY signal!")
    
    print()
    print("=== Model Spread → Uncertainty ===")
    scenarios = [
        (51, 50, 49, "Models agree (±1°F)"),
        (54, 50, 48, "Models disagree (6°F spread)"),
        (None, 50, None, "Single source only"),
    ]
    for ecmwf, gfs, nws, desc in scenarios:
        std = estimate_forecast_std(ecmwf, gfs, nws)
        print(f"  {desc}: std = {std:.1f}°F")
