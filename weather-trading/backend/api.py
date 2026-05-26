"""
Weather Trading API
FastAPI backend for the trading dashboard.
"""
import os
import sys
import threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# PD-230 (HOLMES-098): critical-import probe with fail-fast on wrong Python.
#
# Backend uses py_clob_client_v2 inside method bodies (executor._init_client,
# edge_harvest._get_ro_client), so module-load won't catch the missing dep.
# This probe fires at api.py import time, before uvicorn binds port 8000.
#
# Most common trigger: operator launches via PATH-resolved `uvicorn` (homebrew
# Python 3.14, no v2 SDK) instead of `.venv/bin/python -m uvicorn`. Without
# this probe the dashboard silently serves all-zero scanner data; with this
# probe uvicorn refuses to start with an actionable error message.
try:
    import py_clob_client_v2 as _v2  # noqa: F401
except ImportError:
    _msg = (
        "\n=========================================================================\n"
        "FATAL: py_clob_client_v2 is not importable in this Python interpreter.\n"
        f"  Running Python: {sys.executable}\n"
        "  Required package: py-clob-client-v2 (>=1.0.0)\n"
        "\n"
        "  Most likely cause: uvicorn was launched via PATH-resolved binary using\n"
        "  the wrong Python. Use the project's venv-bound launcher instead.\n"
        "\n"
        "  Fix:\n"
        "    cd ~/Documents/Projects/Ecosystem/weather-trading && ./run-dev.sh\n"
        "\n"
        "  Or directly:\n"
        "    cd ~/Documents/Projects/Ecosystem/weather-trading/backend && \\\n"
        "    ../.venv/bin/python -m uvicorn api:app --reload --port 8000\n"
        "=========================================================================\n"
    )
    print(_msg, file=sys.stderr)
    raise SystemExit(1)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Weather Trading API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}):3000$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import trading modules
try:
    from config import ACTIVE_CITIES, EDGE_CONFIG, EXECUTION_CONFIG
    from scanner import get_scanner
    from forecaster import get_forecaster
    from edge_calculator import get_edge_calculator
    from edge_harvest import get_edge_harvest_scanner
    from position_sizer import PositionSizer
    from executor import PolymarketExecutor, execute_opportunity
    MODULES_LOADED = True
except ImportError as e:
    logger.warning(f"Trading modules not fully loaded: {e}")
    MODULES_LOADED = False
    ACTIVE_CITIES = [
        "nyc", "atlanta", "seattle", "chicago", "dallas", "los_angeles", "miami", "denver",
        "london", "toronto", "buenos_aires", "paris", "ankara", "madrid",
        "seoul", "tokyo", "berlin", "sydney", "mexico_city",
    ]

# Import and initialize database
from database import init_db, save_position, load_positions, update_position_status, save_order, get_position_count, expire_stale_positions
init_db()
expire_stale_positions(hours=48)

# App State
class AppState:
    def __init__(self):
        self.bankroll = 1000.0
        self.positions = load_positions()  # Load from SQLite on startup
        self.opportunities = []
        self.edge_harvest_opportunities = []
        self.last_scan = None
        self.is_live = False
        if MODULES_LOADED:
            self.sizer = PositionSizer(bankroll=self.bankroll)
            self.executor = PolymarketExecutor(dry_run=True)
    
    def set_live(self, live: bool):
        self.is_live = live
        if MODULES_LOADED:
            def _reinit():
                self.executor = PolymarketExecutor(dry_run=not live)
            threading.Thread(target=_reinit, daemon=True).start()
    
    def set_bankroll(self, amount: float):
        self.bankroll = amount
        if MODULES_LOADED:
            self.sizer = PositionSizer(bankroll=amount)

state = AppState()

# Pydantic Models
class TradeRequest(BaseModel):
    opportunity_id: str
    side: str  # "YES" or "NO"
    size: Optional[float] = None  # Override position size

class ScanRequest(BaseModel):
    cities: Optional[List[str]] = None

class SettingsRequest(BaseModel):
    bankroll: Optional[float] = None
    is_live: Optional[bool] = None


@app.get("/api/status")
def get_status():
    open_pos = [p for p in state.positions if p.get("status") == "OPEN"]
    deployed = sum(p.get("size", 0) for p in open_pos)
    
    return {
        "bankroll": state.bankroll,
        "deployed": deployed,
        "available": state.bankroll - deployed,
        "positions": len(open_pos),
        "isLive": state.is_live,
        "lastScan": state.last_scan,
    }


@app.post("/api/settings")
def update_settings(request: SettingsRequest):
    """Update trading settings (bankroll, live mode)."""
    if request.bankroll is not None:
        state.set_bankroll(request.bankroll)
        logger.info(f"Updated bankroll to ${request.bankroll}")
    
    if request.is_live is not None:
        state.set_live(request.is_live)
        logger.info(f"Trading mode set to: {'LIVE' if request.is_live else 'PAPER'}")
    
    return {
        "success": True,
        "bankroll": state.bankroll,
        "isLive": state.is_live,
    }


@app.post("/api/scan")
def scan_opportunities(request: Optional[ScanRequest] = None):
    """Scan for edge-based trading opportunities."""
    if not MODULES_LOADED:
        raise HTTPException(500, "Trading modules not loaded")
    
    cities = request.cities if request and request.cities else ACTIVE_CITIES
    
    logger.info(f"Scanning opportunities for: {cities}")
    
    scanner = get_scanner()
    forecaster = get_forecaster()
    edge_calc = get_edge_calculator()
    
    # Fetch weather markets
    markets = scanner.fetch_weather_markets(city_filter=cities)
    logger.info(f"Found {len(markets)} markets")
    
    # Calculate edges
    results = []
    for market in markets:
        # Get forecast
        forecast = forecaster.get_daily_high_forecast(market.city_key, market.target_date)
        if not forecast:
            continue
        
        # Calculate edge
        opp = edge_calc.calculate_opportunity(market, forecast)
        if not opp or abs(opp.edge) < 0.1:
            continue
        
        # Get position sizing
        pos = state.sizer.calculate(opp.edge, opp.yes_price, getattr(opp, 'liquidity', 500))
        
        # Determine tier
        edge_abs = abs(opp.edge)
        if edge_abs >= 0.40:
            tier = "HIGH"
        elif edge_abs >= 0.25:
            tier = "MEDIUM"
        else:
            tier = "LOW"
        
        # Format bucket string
        bucket_low = opp.bucket_low if opp.bucket_low != float('-inf') else None
        bucket_high = opp.bucket_high if opp.bucket_high != float('inf') else None
        
        # Safe values for JSON
        bucket_low_safe = None if bucket_low is None or bucket_low == float('-inf') else bucket_low
        bucket_high_safe = None if bucket_high is None or bucket_high == float('inf') else bucket_high
        
        unit = getattr(opp, 'forecast_unit', 'F') or 'F'
        if bucket_low_safe is None:
            bucket_str = f"≤{bucket_high_safe}°{unit}"
        elif bucket_high_safe is None:
            bucket_str = f"≥{bucket_low_safe}°{unit}"
        else:
            bucket_str = f"{bucket_low_safe}-{bucket_high_safe}°{unit}"
        
        results.append({
            "id": f"{opp.city}_{opp.target_date}_{bucket_low_safe or 'below'}_{bucket_high_safe or 'above'}".replace("-", "").replace(".", "_"),
            "city": opp.city,
            "targetDate": opp.target_date,
            "bucket": bucket_str,
            "bucketLow": bucket_low_safe,
            "bucketHigh": bucket_high_safe,
            "forecastTemp": opp.forecast_temp,
            "forecastRange": getattr(opp, 'forecast_range', '48hr'),  # "48hr" or "7day"
            "yesPrice": opp.yes_price,
            "noPrice": opp.no_price,
            "edge": opp.edge,
            "tier": tier,
            "hoursRemaining": opp.hours_remaining,
            "liquidity": getattr(opp, 'liquidity', 500),
            "recommendedSide": opp.recommended_side,
            "positionSize": pos.recommended_size,
            "clobTokenIds": opp.clob_token_ids,
            "marketUrl": getattr(opp, 'market_url', ''),
        })
    
    results.sort(key=lambda x: abs(x["edge"]), reverse=True)
    
    state.opportunities = results
    state.last_scan = datetime.now(timezone.utc).isoformat()
    
    return {"opportunities": results, "scanTime": state.last_scan}


@app.get("/api/opportunities")
def get_opportunities():
    return {"opportunities": state.opportunities, "lastScan": state.last_scan}


@app.post("/api/trade")
async def execute_trade(request: TradeRequest):
    if not MODULES_LOADED:
        raise HTTPException(500, "Trading modules not loaded")
    
    # Check both regular and edge harvest opportunities
    opp = next((o for o in state.opportunities if o["id"] == request.opportunity_id), None)
    if not opp:
        opp = next((o for o in state.edge_harvest_opportunities if o["id"] == request.opportunity_id), None)
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    
    size = request.size
    if size is None:
        if "positionSize" in opp:
            size = opp["positionSize"]
        else:
            size = 10.0  # Default for edge harvest
    
    if size < 0.01:
        raise HTTPException(400, "Position size too small (min $0.01)")
    
    open_positions = [p for p in state.positions if p.get("status") == "OPEN"]
    deployed = sum(p.get("size", 0) for p in open_positions)
    if size > state.bankroll - deployed:
        raise HTTPException(400, f"Insufficient funds. Available: ${state.bankroll - deployed:.2f}")
    
    # Safety gate for edge harvest trades (PD-147 NO-side; PD-195 YES-side mirror)
    if opp.get("thresholdType"):
        side_for_floor = opp.get("recommendedSide") or "NO"
        if side_for_floor == "YES":
            yes_price_chk = opp.get("yesPrice", 0)
            if yes_price_chk < 0.60:
                raise HTTPException(400, f"Safety floor: YES price ${yes_price_chk:.2f} too low (min $0.60)")
        else:
            no_price_chk = opp.get("bestAskPrice") or opp.get("noPrice", 0)
            if no_price_chk < 0.60:
                raise HTTPException(400, f"Safety floor: NO price ${no_price_chk:.2f} too low (min $0.60)")
        risk = opp.get("riskScore", 0)
        if risk >= 8:
            raise HTTPException(400, f"Safety gate: risk score {risk}/10 exceeds limit")

    # PD-191: short-side scan opportunities are display-only until PD-193 backtest validates
    if (
        not opp.get("thresholdType")
        and request.side == "NO"
        and not EXECUTION_CONFIG.get("short_side_execution_enabled", False)
    ):
        raise HTTPException(
            400,
            "Short-side (BUY NO) execution disabled pending PD-193 backtest. "
            "Flip EXECUTION_CONFIG.short_side_execution_enabled in config.py once validated."
        )

    # Determine side — respect edge-harvest recommendedSide (PD-195: can be YES or NO)
    if opp.get("thresholdType"):
        side = opp.get("recommendedSide") or "NO"
    else:
        side = request.side

    token_ids = opp.get("clobTokenIds", (None, None))
    if side == "YES":
        token_id = token_ids[0] if token_ids else None
        # For edge-harvest YES, prefer best_ask (immediate fill); fall back to yesPrice
        price = (opp.get("bestAskPrice") if opp.get("thresholdType") else None) or opp.get("yesPrice")
    else:  # NO
        token_id = token_ids[1] if token_ids and len(token_ids) > 1 else None
        price = (opp.get("bestAskPrice") if opp.get("thresholdType") else None) or opp.get("noPrice")
    
    if not token_id:
        raise HTTPException(400, "No token ID available for this market")
    
    try:
        # Convert dollar amount to shares (CLOB API expects number of contracts)
        shares = size / price if price > 0 else 0
        logger.info(f"Placing order: {side} {shares:.2f} shares @ ${price:.4f} (${size:.2f} notional)")
        
        result = state.executor.place_order(
            token_id=token_id,
            side=side,
            price=price,
            size=shares
        )
        
        # Only create position if order was actually successful
        if not result.success:
            error_msg = result.error or "Order placement failed"
            logger.warning(f"Order failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "executionResult": {
                    "success": False,
                    "error": error_msg
                }
            }
        
        position = {
            "id": f"pos_{get_position_count() + 1}",
            "opportunityId": opp["id"],
            "city": opp["city"],
            "bucket": opp["bucket"],
            "targetDate": opp["targetDate"],
            "side": side,
            "entryPrice": price,
            "shares": size / price if price > 0 else 0,  # Convert dollar amount to shares
            "currentPrice": price,  # Same as entry for now
            "size": size,
            "status": "OPEN",
            "openedAt": datetime.now(timezone.utc).isoformat(),
            "orderId": result.order_id,
            "unrealizedPnl": 0,
            "hoursRemaining": opp.get("hoursRemaining", 24),
            "thresholdType": opp.get("thresholdType"),  # Track edge harvest trades
        }
        
        state.positions.append(position)
        save_position(position)
        
        # Also save the order record
        save_order({
            "id": result.order_id or f"ord_{get_position_count()}",
            "positionId": position["id"],
            "opportunityId": opp["id"],
            "tokenId": token_id,
            "side": side,
            "price": price,
            "sizeShares": shares,
            "sizeDollars": size,
            "status": "FILLED" if result.filled_amount > 0 else "SUBMITTED",
            "filledAmount": result.filled_amount,
            "avgPrice": result.avg_price,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        })
        
        return {
            "success": True,
            "position": position,
            "executionResult": {
                "success": True,
                "order_id": result.order_id,
                "filled_amount": result.filled_amount,
                "avg_price": result.avg_price
            }
        }
    
    except Exception as e:
        logger.error(f"Trade execution failed: {e}")
        raise HTTPException(500, f"Trade failed: {str(e)}")


@app.get("/api/positions")
def get_positions():
    return {"positions": state.positions}


@app.post("/api/positions/{position_id}/close")
def close_position(position_id: str, outcome: str = "MANUAL"):
    pos = next((p for p in state.positions if p["id"] == position_id), None)
    if not pos:
        raise HTTPException(404, "Position not found")
    
    pos["status"] = outcome
    pos["hoursRemaining"] = 0
    update_position_status(position_id, outcome)
    
    return {"success": True, "position": pos}


@app.get("/api/stats")
def get_stats():
    open_pos = [p for p in state.positions if p.get("status") == "OPEN"]
    closed_pos = [p for p in state.positions if p.get("status") in ["WON", "LOST"]]
    
    wins = len([p for p in closed_pos if p["status"] == "WON"])
    losses = len([p for p in closed_pos if p["status"] == "LOST"])
    total_pnl = sum(p.get("unrealizedPnl", 0) for p in state.positions)
    deployed = sum(p.get("size", 0) for p in open_pos)
    
    return {
        "bankroll": state.bankroll,
        "deployed": deployed,
        "available": state.bankroll - deployed,
        "totalPnl": total_pnl,
        "winCount": wins,
        "lossCount": losses,
        "winRate": wins / (wins + losses) if (wins + losses) > 0 else None,
        "openPositions": len(open_pos),
        "totalTrades": len(state.positions),
    }



@app.post("/api/edge-harvest")
def scan_edge_harvest(request: Optional[ScanRequest] = None):
    """
    Scan for edge harvest opportunities.
    
    Strategy: Buy NO on buckets far from forecast to collect 0.5-2% returns.
    Returns both CONSERVATIVE (3+ bands) and AGGRESSIVE (2+ bands) opportunities.
    """
    if not MODULES_LOADED:
        raise HTTPException(500, "Trading modules not loaded")
    
    cities = request.cities if request and request.cities else ACTIVE_CITIES
    
    logger.info(f"Edge harvest scan for: {cities}")
    
    scanner = get_scanner()
    forecaster = get_forecaster()
    edge_scanner = get_edge_harvest_scanner()
    
    # Fetch markets
    markets = scanner.fetch_weather_markets(city_filter=cities)
    logger.info(f"Found {len(markets)} markets for edge harvest")
    
    # Fetch forecasts
    forecasts = {}
    for city in cities:
        for offset in [0, 1, 2]:
            target = (datetime.now(timezone.utc) + timedelta(days=offset)).strftime("%Y-%m-%d")
            forecast = forecaster.get_daily_high_forecast(city, target)
            if forecast:
                forecasts[(city, target)] = forecast
    
    # Find edge harvest opportunities
    opportunities = edge_scanner.find_opportunities(markets, forecasts)
    logger.info(f"Found {len(opportunities)} edge harvest opportunities")
    
    results = []
    for opp in opportunities:
        # Generate ID from fields.
        # market_type ("high"/"low") AND recommended_side ("NO"/"YES") are both
        # required to make the ID unique:
        #   - market_type: Polymarket runs BOTH "highest-temperature-in-X" and
        #     "lowest-temperature-in-X" events on the same city/date. They share
        #     bucket labels (e.g. Miami May 24 90-91°F exists in both events as
        #     distinct markets with different clob_token_ids). Without
        #     market_type in the key, dedup collapses two real markets into one
        #     row — same routing-collision class as PD-322 (Manila/LA alias bug).
        #   - recommended_side: find_opportunities can emit NO and YES rows for
        #     the same market (single-integer C-buckets where forecast sits
        #     exactly inside the bucket).
        mtype_suffix = (getattr(opp, 'market_type', 'high') or 'high').lower()
        side_suffix = (getattr(opp, 'recommended_side', 'NO') or 'NO').lower()
        opp_id = (
            f"eh_{opp.city}_{opp.target_date}_{opp.bucket_str}_{mtype_suffix}_{side_suffix}"
            .replace(" ", "")
            .replace("°", "")
            .replace("≤", "lte")
            .replace("≥", "gte")
            .replace("-", "_")
        )
        
        results.append({
            "id": opp_id,
            "city": opp.city,
            "targetDate": opp.target_date,
            "bucket": opp.bucket_str,
            "bucketLow": opp.bucket_low,
            "bucketHigh": opp.bucket_high,
            "forecastTemp": opp.forecast_temp,
            "forecastRange": "48hr" if opp.hours_remaining <= 48 else "7day",
            "bandsAway": opp.bands_away,
            "degreesAway": opp.degrees_away,
            "thresholdType": opp.threshold_type,
            "yesPrice": opp.yes_price,
            "noPrice": opp.no_price,
            "potentialReturnPct": opp.potential_return_pct,
            "riskTier": opp.risk_tier,
            "riskScore": opp.risk_score,
            "riskFactors": opp.risk_factors,
            "modelSpread": opp.model_spread,
            "ecmwfTemp": opp.ecmwf_temp,
            "gfsTemp": opp.gfs_temp,
            "nwsTemp": opp.nws_temp,
            "frontWarning": bool(opp.front_warning),
            "frontWarningSeverity": opp.front_warning.severity if opp.front_warning else None,
            "frontWarningReason": opp.front_warning_reason,
            "recommendedSide": opp.recommended_side,
            "marketType": getattr(opp, 'market_type', 'high'),
            "clobTokenIds": opp.clob_token_ids,
            "marketUrl": opp.market_url,
            "liquidity": opp.liquidity,
            "bestAskPrice": opp.best_ask_price,
            "bestAskSize": opp.best_ask_size,
            "bestBidPrice": opp.best_bid_price,
            "bestBidSize": opp.best_bid_size,
            "spread": opp.spread,
            "hoursRemaining": opp.hours_remaining,
        })
    
    # Store for trading
    state.edge_harvest_opportunities = results
    
    return {
        "opportunities": results,
        "scanTime": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total": len(results),
            "conservative": len([r for r in results if r["thresholdType"] == "CONSERVATIVE"]),
            "aggressive": len([r for r in results if r["thresholdType"] == "AGGRESSIVE"]),
            "withWarnings": len([r for r in results if r["frontWarning"]]),
            "highRisk": len([r for r in results if r["riskScore"] >= 7]),
            "mediumRisk": len([r for r in results if 4 <= r["riskScore"] < 7]),
            "lowRisk": len([r for r in results if r["riskScore"] < 4]),
        }
    }


@app.get("/api/edge-harvest")
def get_edge_harvest():
    """Get cached edge harvest opportunities."""
    return {
        "opportunities": state.edge_harvest_opportunities,
        "lastScan": state.last_scan
    }




@app.get("/api/orders")
def get_open_orders():
    """Fetch open orders from CLOB API and local database."""
    if not MODULES_LOADED:
        raise HTTPException(500, "Trading modules not loaded")
    
    orders = []
    
    # Try to fetch live orders from CLOB
    if state.is_live and state.executor.client:
        try:
            live_orders = state.executor.client.get_orders()
            if live_orders:
                for o in live_orders:
                    orders.append({
                        "id": o.get("id", ""),
                        "tokenId": o.get("asset_id", ""),
                        "side": o.get("side", ""),
                        "price": float(o.get("price", 0)),
                        "originalSize": float(o.get("original_size", 0)),
                        "sizeMatched": float(o.get("size_matched", 0)),
                        "sizeRemaining": float(o.get("original_size", 0)) - float(o.get("size_matched", 0)),
                        "status": o.get("status", "UNKNOWN"),
                        "createdAt": o.get("created_at", ""),
                        "source": "LIVE",
                    })
        except Exception as e:
            logger.warning(f"Failed to fetch live orders: {e}")
    
    # Also include local order records from database
    from database import load_orders
    local_orders = load_orders()
    for o in local_orders:
        # Don't duplicate if already in live orders
        if not any(lo["id"] == o["id"] for lo in orders):
            orders.append({
                "id": o["id"],
                "tokenId": o.get("token_id", ""),
                "side": o["side"],
                "price": o["price"],
                "originalSize": o["size_shares"],
                "sizeMatched": o.get("filled_amount", 0),
                "sizeRemaining": o["size_shares"] - o.get("filled_amount", 0),
                "status": o.get("status", "UNKNOWN"),
                "createdAt": o["created_at"],
                "source": "LOCAL",
            })
    
    return {"orders": orders}


@app.post("/api/orders/{order_id}/cancel")
def cancel_order(order_id: str):
    """Cancel an open order on the CLOB."""
    if not MODULES_LOADED:
        raise HTTPException(500, "Trading modules not loaded")
    
    if not state.is_live or not state.executor.client:
        raise HTTPException(400, "Cannot cancel orders in paper mode")
    
    try:
        result = state.executor.client.cancel(order_id)
        logger.info(f"Cancel order {order_id}: {result}")
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Failed to cancel order {order_id}: {e}")
        raise HTTPException(500, f"Cancel failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
