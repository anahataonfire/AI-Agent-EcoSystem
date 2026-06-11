"""
Weather Trading API
FastAPI backend for the trading dashboard.
"""
import os
import sys
import json
import threading

# PD-326 (handoff Step 4): persist the edge-harvest opp cache across uvicorn
# --reload restarts so the /api/trade lookup doesn't 404 during the empty
# window between reload and the next POST /api/edge-harvest.
_OPP_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".opp-cache.json")


def _save_opp_cache(opps: list, last_scan=None) -> None:
    try:
        with open(_OPP_CACHE_PATH, "w") as f:
            json.dump({"opportunities": opps, "lastScan": last_scan}, f)
    except OSError as e:
        # Cache write failure is non-fatal — log and move on.
        # (FastAPI is configured before logger; deferred print used.)
        print(f"[opp-cache] save failed: {e}", file=sys.stderr)


def _load_opp_cache() -> tuple:
    """Returns (opportunities, last_scan) or ([], None) on miss."""
    try:
        with open(_OPP_CACHE_PATH, "r") as f:
            data = json.load(f)
            return data.get("opportunities", []), data.get("lastScan")
    except (OSError, json.JSONDecodeError):
        return [], None
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
from typing import List, Literal, Optional
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
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
    from config import ACTIVE_CITIES, EDGE_CONFIG, EXECUTION_CONFIG, TRADE_GATES
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
from database import init_db, save_position, load_positions, update_position_status, save_order, get_position_count, expire_stale_positions, create_position_with_order
init_db()
expire_stale_positions(hours=48)

# App State
class AppState:
    def __init__(self):
        self.bankroll = 1000.0
        self.positions = load_positions()  # Load from SQLite on startup
        self.opportunities = []
        # PD-326: restore opp cache across uvicorn reloads.
        cached_opps, cached_scan = _load_opp_cache()
        self.edge_harvest_opportunities = cached_opps
        self.last_scan = cached_scan
        if cached_opps:
            logger.info(f"Restored {len(cached_opps)} cached edge-harvest opps from disk (lastScan={cached_scan})")
        self.is_live = False
        if MODULES_LOADED:
            self.sizer = PositionSizer(bankroll=self.bankroll)
            self.executor = PolymarketExecutor(dry_run=True)
    
    def set_live(self, live: bool):
        """Synchronously swap the executor, THEN flip the flag (PD-351 H1).

        The old background-thread swap left a seconds-long window where
        is_live said one mode while trades executed on the other executor —
        and a failed live init died silently, leaving is_live=True with a
        dry-run executor forever. Raises on failure; caller surfaces it.
        """
        if MODULES_LOADED:
            new_executor = PolymarketExecutor(dry_run=not live)
            if live and new_executor.client is None:
                raise RuntimeError(
                    "Live executor init failed (no CLOB client — check POLY_PRIVATE_KEY in .env)"
                )
            self.executor = new_executor
        self.is_live = live
    
    def set_bankroll(self, amount: float):
        self.bankroll = amount
        if MODULES_LOADED:
            self.sizer = PositionSizer(bankroll=amount)

state = AppState()

# Pydantic Models
class TradeRequest(BaseModel):
    opportunity_id: str
    # Literal, not str: executor.py maps ANY string outside ["YES","NO","BUY"] to
    # a SELL order — a lowercase "no" from a curl typo or future client would
    # place a real wrong-direction trade. Reject at validation instead.
    side: Literal["YES", "NO"]
    size: Optional[float] = None  # Override position size
    # PD-351: trade past the strategy gates (price ceiling / open bucket /
    # NO_ROOM / loss cap). Gates inform discretion, not replace it.
    override: bool = False

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
        # Ground truth from the executor itself, not the flag — these can only
        # diverge if a mode switch failed, and that divergence must be visible.
        "executorLive": bool(MODULES_LOADED and state.executor and not state.executor.dry_run),
        "lastScan": state.last_scan,
    }


@app.post("/api/settings")
def update_settings(request: SettingsRequest):
    """Update trading settings (bankroll, live mode)."""
    if request.bankroll is not None:
        state.set_bankroll(request.bankroll)
        logger.info(f"Updated bankroll to ${request.bankroll}")
    
    if request.is_live is not None:
        try:
            state.set_live(request.is_live)
        except Exception as e:
            logger.error(f"Mode switch failed: {e}")
            raise HTTPException(
                500,
                f"Could not switch to {'LIVE' if request.is_live else 'PAPER'}: {e}. "
                f"Mode unchanged ({'LIVE' if state.is_live else 'PAPER'}).",
            )
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


# PD-351 M2: per-opportunity in-flight guard. execute_trade is now `def`
# (threadpool — blocking CLOB I/O off the event loop), which removes the
# accidental request serialization the old no-await `async def` provided, so
# duplicate-click protection must be explicit.
_TRADE_INFLIGHT = set()
_TRADE_INFLIGHT_LOCK = threading.Lock()


@app.post("/api/trade")
def execute_trade(request: TradeRequest):
    if not MODULES_LOADED:
        raise HTTPException(500, "Trading modules not loaded")

    with _TRADE_INFLIGHT_LOCK:
        if request.opportunity_id in _TRADE_INFLIGHT:
            raise HTTPException(409, "A trade for this opportunity is already in flight")
        _TRADE_INFLIGHT.add(request.opportunity_id)
    try:
        return _execute_trade_inner(request)
    finally:
        with _TRADE_INFLIGHT_LOCK:
            _TRADE_INFLIGHT.discard(request.opportunity_id)


def _execute_trade_inner(request: TradeRequest):
    # Check both regular and edge harvest opportunities
    opp = next((o for o in state.opportunities if o["id"] == request.opportunity_id), None)
    if not opp:
        opp = next((o for o in state.edge_harvest_opportunities if o["id"] == request.opportunity_id), None)
    if not opp:
        # PD-326: distinguish "cache empty after restart" from "stale ID" so the
        # operator knows whether to click Run Scanner or whether the row simply rolled off.
        if not state.edge_harvest_opportunities and not state.opportunities:
            raise HTTPException(
                503,
                "Opportunity cache empty (backend restart). Click Run Scanner to refresh, then retry the trade."
            )
        raise HTTPException(404, "Opportunity not found in current scan (rolled off or stale ID)")

    # Codex R3/R5 tradability guard — refuse orders to markets whose CLOB book is closed.
    if opp.get("acceptingOrders") is False:
        raise HTTPException(
            423,
            "Market is no longer accepting orders (Polymarket marked acceptingOrders=False). "
            "Refresh the scanner to drop stale rows."
        )

    # PD-351 H3: cached prices ARE the execution prices — refuse to trade off a
    # stale scan (the disk-restored cache can be days old after a restart).
    # Deliberately NOT overridable: stale quotes are objectively wrong, and a
    # fresh scan is 20-40s away.
    max_age_min = TRADE_GATES["max_scan_age_min"]
    scan_age_min = None
    if state.last_scan:
        try:
            scan_age_min = (
                datetime.now(timezone.utc) - datetime.fromisoformat(state.last_scan)
            ).total_seconds() / 60.0
        except (ValueError, TypeError):
            scan_age_min = None
    if scan_age_min is None or scan_age_min > max_age_min:
        age_txt = f"{scan_age_min:.0f} min old" if scan_age_min is not None else "of unknown age"
        raise HTTPException(
            409,
            f"Scan data is {age_txt} (max {max_age_min:.0f} min for trading). "
            f"Run Scanner to refresh prices, then retry.",
        )

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

    # PD-351 strategy gates — server-side enforcement of what the display
    # already says (numbers + rationale in config.TRADE_GATES). Overridable
    # per-trade: {"override": true}.
    if not request.override:
        reasons = []
        if opp.get("thresholdType") and side == "NO":
            if opp.get("openBucket"):
                reasons.append(
                    "open-ended extreme bucket — NO here bets against the whole tail "
                    "(PD-343 loss class: tokyo ≥28°C −$542, BA ≥27°C −$225)"
                )
            if opp.get("recommendationStatus") == "NO_ROOM":
                margin = opp.get("marginC")
                margin_txt = f" (margin {margin:+.1f}°C)" if isinstance(margin, (int, float)) else ""
                reasons.append(f"NO_ROOM — corrected forecast leaves no room{margin_txt}")
            if price >= TRADE_GATES["no_price_ceiling"] and not (
                opp.get("recommendationStatus") == "ROOM"
                and opp.get("basisConfidence") == "TRUSTED"
            ):
                reasons.append(
                    f"NO at ${price:.2f} ≥ ${TRADE_GATES['no_price_ceiling']:.2f} ceiling without "
                    f"ROOM + TRUSTED basis — this band is net-negative in the realized book"
                )
        if size > TRADE_GATES["max_loss_cap_usd"]:
            reasons.append(
                f"size ${size:.0f} > ${TRADE_GATES['max_loss_cap_usd']:.0f} max-loss cap "
                f"(downside on a {side} buy is the full size)"
            )
        if reasons:
            raise HTTPException(400, {
                "gate": True,
                "reasons": reasons,
                "hint": "Re-send with override:true to trade past the gates.",
            })

    # PD-351 H3 re-quote: the displayed ask is from scan time. A GTC limit at a
    # stale price either overpays (ask moved up) or rests unfilled and invisible.
    # Not overridable — if the price genuinely moved, re-scan and trade fresh.
    if opp.get("thresholdType"):
        live_book = get_edge_harvest_scanner()._fetch_order_book(token_id)
        live_ask = live_book.get("best_ask_price") or 0.0
        if live_ask <= 0:
            raise HTTPException(
                423,
                "Live order book has no asks for this token — market likely closed or exhausted. Re-scan.",
            )
        if abs(live_ask - price) > TRADE_GATES["requote_tolerance"]:
            raise HTTPException(
                409,
                f"Price moved since the scan: displayed ${price:.3f}, live ask ${live_ask:.3f} "
                f"(tolerance ${TRADE_GATES['requote_tolerance']:.2f}). Re-scan to refresh.",
            )

    # ---- Order placement (own try: PD-351 C1/M3 — an exception here does NOT
    # mean no order exists; a timeout after CLOB acceptance leaves a live order) ----
    shares = size / price if price > 0 else 0
    logger.info(f"Placing order: {side} {shares:.2f} shares @ ${price:.4f} (${size:.2f} notional)")
    try:
        result = state.executor.place_order(
            token_id=token_id,
            side=side,
            price=price,
            size=shares
        )
    except Exception as e:
        logger.error(f"Order POST raised: {e}")
        raise HTTPException(
            502,
            f"Order state UNKNOWN ({type(e).__name__}: {e}). The order MAY have been placed — "
            f"check Open Orders / Polymarket before retrying.",
        )

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

    # ---- Persistence (separate try: PD-351 C1 — the order above is REAL even
    # if these writes fail; never report a placed order as a failed trade) ----
    position = {
        "id": None,  # assigned atomically by create_position_with_order
        "opportunityId": opp["id"],
        "city": opp["city"],
        "bucket": opp["bucket"],
        "targetDate": opp["targetDate"],
        "side": side,
        "entryPrice": price,
        "shares": shares,
        "currentPrice": price,  # static until a pricing refresher exists
        "size": size,
        "status": "OPEN",
        "openedAt": datetime.now(timezone.utc).isoformat(),
        "orderId": result.order_id,
        "unrealizedPnl": 0,
        "hoursRemaining": opp.get("hoursRemaining", 24),
        "thresholdType": opp.get("thresholdType"),  # Track edge harvest trades
    }
    order_record = {
        # Real CLOB ids are unique; dry-run/missing ids get a position-derived
        # id inside create_position_with_order (the old "dry_run" PK collapsed
        # all paper orders onto one row).
        "id": result.order_id,
        "positionId": None,  # assigned with the position id
        "opportunityId": opp["id"],
        "tokenId": token_id,
        "side": side,
        "price": price,
        "sizeShares": shares,
        "sizeDollars": size,
        # PD-351 M1 honest status: "live" = RESTING on the book, not filled.
        "status": {"matched": "FILLED", "dry_run": "FILLED", "live": "LIVE",
                   "delayed": "DELAYED"}.get(result.status, (result.status or "SUBMITTED").upper()),
        "filledAmount": result.filled_amount,
        "avgPrice": result.avg_price,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    execution_result = {
        "success": True,
        "order_id": result.order_id,
        "status": result.status,
        "filled_amount": result.filled_amount,
        "avg_price": result.avg_price,
        "price": price,
    }
    try:
        create_position_with_order(position, order_record)
        # Newest-first to match the DB load order (the old append() buried fresh
        # trades at the bottom of an 900-row table).
        state.positions.insert(0, position)
    except Exception as e:
        logger.error(
            f"PERSISTENCE FAILED for placed order {result.order_id}: {e} — "
            f"the order is REAL; reconcile manually."
        )
        return {
            "success": True,
            "position": position,
            "persistenceError": (
                f"{type(e).__name__}: {e} — the order WAS placed "
                f"(id {result.order_id}); it is missing from local records. "
                f"Do NOT re-click; reconcile via Open Orders."
            ),
            "executionResult": execution_result,
        }

    return {
        "success": True,
        "position": position,
        "executionResult": execution_result,
    }


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
    # PD-351 M5: realized pnl is the truth (backfill-populated); unrealizedPnl
    # is a static 0 written at open. The old sum-of-unrealized read ~$0 forever
    # on a book that had lost $901.
    total_pnl = sum(
        (p.get("pnl") if p.get("pnl") is not None else p.get("unrealizedPnl", 0)) or 0
        for p in state.positions
    )
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



# PD-350 single-flight state for default-cities edge-harvest scans. When the
# UI re-requests while a scan is running (its 6-min timeout used to fire mid-
# scan), the new request JOINS the in-flight scan instead of stacking another
# full scan in the threadpool — 3-4 concurrent scans were slowing each other
# and amplifying Cloudflare rate-limiting.
_EH_SCAN_SF = {"mutex": threading.Lock(), "event": None}


@app.post("/api/edge-harvest")
def scan_edge_harvest(request: Optional[ScanRequest] = None):
    """
    Scan for edge harvest opportunities.

    Strategy: Buy NO on buckets far from forecast to collect 0.5-2% returns.
    Returns both CONSERVATIVE (3+ bands) and AGGRESSIVE (2+ bands) opportunities.
    """
    if not MODULES_LOADED:
        raise HTTPException(500, "Trading modules not loaded")

    if request and request.cities:
        # Explicit city subset: run directly, no single-flight (results differ per request).
        return _run_edge_harvest_scan(request.cities)

    sf = _EH_SCAN_SF
    with sf["mutex"]:
        ev = sf["event"]
        leader = ev is None
        if leader:
            ev = threading.Event()
            sf["event"] = ev

    if not leader:
        logger.info("Edge harvest scan already in flight — joining its result")
        if not ev.wait(timeout=600):
            raise HTTPException(503, "Scan in progress; timed out waiting for it")
        payload = getattr(ev, "payload", None)
        if payload is None:
            raise HTTPException(502, f"In-flight scan failed: {getattr(ev, 'error', 'unknown')}")
        return payload

    try:
        payload = _run_edge_harvest_scan(ACTIVE_CITIES)
        ev.payload = payload
        return payload
    except Exception as e:
        ev.payload = None
        ev.error = f"{type(e).__name__}: {e}"
        raise
    finally:
        with sf["mutex"]:
            sf["event"] = None
        ev.set()


def _run_edge_harvest_scan(cities: List[str]):
    """Full edge-harvest scan body (markets → forecasts → opportunities)."""
    logger.info(f"Edge harvest scan for: {cities}")

    scanner = get_scanner()
    forecaster = get_forecaster()
    edge_scanner = get_edge_harvest_scanner()

    # Fetch markets
    markets = scanner.fetch_weather_markets(city_filter=cities)
    logger.info(f"Found {len(markets)} markets for edge harvest")

    # Fetch forecasts — parallel per city (PD-350). The sequential loop was 47
    # cities × 3 dates × ~1.1s Open-Meteo ≈ 159s of scan wall time; 10 workers
    # plus the forecaster's per-city TTL cache bring it to ~10s.
    #
    # Keys come from the markets' own (city, target_date) pairs, NOT a UTC-derived
    # date list: market target_date is the CITY-LOCAL date from the Polymarket
    # slug. The old UTC 0/1/2-day list had no key for US-West "today" markets
    # after 00:00 UTC (nor far-east +2-day markets), so find_opportunities
    # silently dropped them every evening.
    needed: dict = {}
    for m in markets:
        needed.setdefault(m.city_key, set()).add(m.target_date)

    def _city_forecasts(item) -> list:
        city, dates = item
        rows = []
        for target in sorted(dates):
            forecast = forecaster.get_daily_high_forecast(city, target)
            if forecast:
                rows.append(((city, target), forecast))
        return rows

    forecasts = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        for rows in pool.map(_city_forecasts, list(needed.items())):
            forecasts.update(rows)

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
            # PD-340 v3 honest bands (settlement-location correction; display-only)
            "rawBands": getattr(opp, 'raw_bands', opp.bands_away),
            "correctedBands": getattr(opp, 'corrected_bands', None),
            "correctedForecast": getattr(opp, 'corrected_forecast_temp', None),
            "effectiveDeltaC": getattr(opp, 'effective_delta_c', 0.0),
            "marginC": getattr(opp, 'margin_c', None),
            "recommendationStatus": getattr(opp, 'recommendation_status', 'UNCORRECTED'),
            "basisStatus": getattr(opp, 'basis_status', 'uncorrected-no-data'),
            "basisConfidence": getattr(opp, 'basis_confidence', 'UNPROVEN'),
            "basisN": getattr(opp, 'basis_n', 0),
            "basisVersion": getattr(opp, 'basis_version', None),
            "openBucket": bool(getattr(opp, 'open_bucket', False)),
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
            "acceptingOrders": bool(getattr(opp, 'accepting_orders', True)),
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
    
    # Store for trading + persist (PD-326: survive uvicorn reload)
    scan_time = datetime.now(timezone.utc).isoformat()
    state.edge_harvest_opportunities = results
    state.last_scan = scan_time
    _save_opp_cache(results, scan_time)

    return {
        "opportunities": results,
        "scanTime": scan_time,
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
            # V2 SDK: get_open_orders (V1's get_orders doesn't exist post-migration —
            # this call AttributeError'd silently for weeks, PD-351 H2).
            live_orders = state.executor.client.get_open_orders()
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
        # V2 SDK: cancel_order(OrderPayload) — V1's cancel(order_id) doesn't exist.
        from py_clob_client_v2 import OrderPayload
        result = state.executor.client.cancel_order(OrderPayload(orderID=order_id))
        logger.info(f"Cancel order {order_id}: {result}")
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Failed to cancel order {order_id}: {e}")
        raise HTTPException(500, f"Cancel failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    # Loopback only: /api/trade and /api/settings are unauthenticated — on
    # 0.0.0.0 any LAN device could place real orders or flip live mode.
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
