"""
Polymarket Trade Executor
Dry-run mode by default. Set --live flag and POLY_PRIVATE_KEY for real trades.
"""
import os
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal

logger = logging.getLogger(__name__)

@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    filled_amount: float = 0.0
    avg_price: float = 0.0
    error: Optional[str] = None
    # CLOB acceptance status: "matched" = filled, "live" = RESTING on the book,
    # "delayed" = queued; "dry_run" for paper. PD-351 M1: filled_amount used to
    # be fabricated as the requested size for ANY accepted GTC.
    status: Optional[str] = None
    actual_cost: float = 0.0
    fees: float = 0.0
    rebates: float = 0.0
    order_mode: str = "GTC"


@dataclass
class OrderSnapshot:
    """Normalized authenticated order lifecycle snapshot.

    `matched` is intentionally distinct from `confirmed`: an exchange match
    may still fail. Adapters for REST or the authenticated user stream can
    populate this same boundary without coupling persistence to an SDK shape.
    """
    order_id: str
    status: str
    filled_amount: float = 0.0
    avg_price: float = 0.0
    actual_cost: float = 0.0
    fees: float = 0.0
    rebates: float = 0.0
    raw_status: Optional[str] = None
    event_id: Optional[str] = None


def _number(payload: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return default


def normalize_order_snapshot(order_id: str, payload: Dict[str, Any]) -> OrderSnapshot:
    raw = str(payload.get("status") or payload.get("type") or "UNKNOWN")
    key = raw.strip().upper().removeprefix("ORDER_STATUS_")
    aliases = {
        "LIVE": "LIVE", "OPEN": "LIVE", "DELAYED": "DELAYED",
        "MATCHED": "MATCHED", "PARTIALLY_FILLED": "PARTIALLY_FILLED",
        "PARTIAL": "PARTIALLY_FILLED", "CONFIRMED": "CONFIRMED",
        "PARTIALLY_CONFIRMED": "PARTIALLY_CONFIRMED", "CANCELED": "CANCELED",
        "CANCELLED": "CANCELED", "FAILED": "FAILED", "REJECTED": "REJECTED",
        "CANCELED_MARKET_RESOLVED": "CANCELED", "INVALID": "REJECTED",
    }
    status = aliases.get(key, "UNKNOWN")
    filled = _number(payload, "size_matched", "sizeMatched", "filled_amount", "filledAmount")
    price = _number(payload, "avg_price", "avgPrice", "price")
    cost = _number(payload, "actual_cost", "actualCost", default=filled * price)
    return OrderSnapshot(
        order_id=order_id,
        status=status,
        filled_amount=filled,
        avg_price=price,
        actual_cost=cost,
        fees=_number(payload, "fees", "fee"),
        rebates=_number(payload, "rebates", "rebate"),
        raw_status=raw,
    )


def normalize_trade_event(order_id: str, payload: Dict[str, Any]) -> OrderSnapshot:
    """Normalize authenticated user-channel trade lifecycle events.

    MATCHED and MINED are nonterminal. Only CONFIRMED proves a fill; FAILED
    releases the reservation without creating a position.
    """
    raw = str(payload.get("status") or "UNKNOWN").upper()
    normalized_raw = raw.removeprefix("TRADE_STATUS_")
    event_id = str(payload.get("id") or payload.get("trade_id") or "").strip()
    if not event_id:
        raise ValueError("Authenticated trade event is missing its stable trade id")
    status = {
        "MATCHED": "MATCHED",
        "MINED": "MATCHED",
        "CONFIRMED": "CONFIRMED",
        "FAILED": "FAILED",
    }.get(normalized_raw, "UNKNOWN")
    filled = _number(payload, "size", "matched_size", "size_matched", "filled_amount")
    price = _number(payload, "price", "avg_price")
    return OrderSnapshot(
        order_id=order_id,
        status=status,
        filled_amount=filled,
        avg_price=price,
        actual_cost=_number(payload, "actual_cost", default=filled * price),
        fees=_number(payload, "fees", "fee"),
        rebates=_number(payload, "rebates", "rebate"),
        raw_status=raw,
        event_id=event_id,
    )

class PolymarketExecutor:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.client = None
        
        if not dry_run:
            self._init_client()
    
    def _init_client(self):
        try:
            from py_clob_client_v2 import ClobClient
            from dotenv import load_dotenv
            from pathlib import Path

            # Load environment variables from .env (check both current and parent dir)
            env_path = Path(__file__).parent / ".env"
            if not env_path.exists():
                env_path = Path(__file__).parent.parent / ".env"
            load_dotenv(env_path)

            private_key = os.environ.get("POLY_PRIVATE_KEY")
            if not private_key:
                logger.warning("POLY_PRIVATE_KEY not found. Live trading will fail until provided.")
                return

            funder = os.environ.get("POLY_FUNDER_ADDRESS", "0xB90588CE64AD8792019cc494ea815E59b5071640")

            # PD-220 (HOLMES-092): V2 SDK migration post-Polymarket CLOB V2 cutover
            # 2026-04-28 ~11:00 UTC. EIP-712 domain bumped 1->2; V1 SDK incompatible.
            # signature_type=2 retained (POLY_GNOSIS_SAFE / browser-wallet proxy;
            # Codex v1 F1 verified V2 enum mapping unchanged from V1).
            # retry_on_error=True enables SDK transient-retry on POST 5xx/network errors;
            # GET retries not covered (Codex v2 F4 — known limitation).
            # use_server_time NOT set: Codex v1 F3 confirmed it does not affect signed-order
            # timestamp (which is generated locally), only adds latency to L1/L2 headers.
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                chain_id=137,
                key=private_key,
                signature_type=2,
                funder=funder,
                retry_on_error=True,
            )

            # V2: create_or_derive_api_key replaces V1's derive_api_key
            self.client.set_api_creds(self.client.create_or_derive_api_key())
            logger.info("CLOB v2 client initialized with derived API keys")

        except ImportError:
            raise ImportError("Run: pip install py-clob-client-v2 python-dotenv")
    
    def get_balance(self) -> float:
        """
        Check connection and return mock/real balance.
        Note: Real balance fetching via CLOB SDK requires specific parameters.
        Verified connection via get_ok().
        """
        if self.dry_run:
            return 1000.0
        try:
            # Verify connectivity
            if self.client.get_ok() == "OK":
                # For now, return a placeholder or try to implement real balance check
                # Real USDC balance check usually involves calling the ERC20 contract
                return 0.0 # Placeholder for now, connection is verified
            return 0.0
        except Exception as e:
            logger.error(f"Balance check/Connection error: {e}")
            return 0.0
    
    def place_order(self, token_id: str, side: Literal["BUY", "SELL"],
                    size: float, price: float, *, post_only: bool = False) -> OrderResult:
        mode = "POST_ONLY" if post_only else "GTC"
        if self.dry_run:
            logger.info(f"[DRY RUN] {side} {size:.2f} @ {price:.2f}")
            return OrderResult(True, "dry_run", size, price, status="confirmed",
                               actual_cost=size * price, order_mode=mode)

        # Check VPN/connectivity before attempting trade
        try:
            if not self.client:
                return OrderResult(False, error="CLOB client not initialized - check credentials")
            health_check = self.client.get_ok()
            if health_check != "OK":
                return OrderResult(False, error=f"Cannot reach Polymarket - check VPN (status: {health_check})")
        except Exception as e:
            return OrderResult(False, error=f"VPN/connectivity check failed: {str(e)}")

        # CLOB API uses BUY/SELL strings (V2 OrderArgsV2.side: str)
        clob_side = "BUY" if side in ["YES", "NO", "BUY"] else "SELL"

        try:
            from py_clob_client_v2 import OrderArgs, PartialCreateOrderOptions, OrderType
        except ImportError:
            logger.error("py_clob_client_v2 not installed - required for V2 exchange")
            return OrderResult(False, error="py_clob_client_v2 not installed")

        # Fetch market metadata (V2 still has get_tick_size / get_neg_risk)
        try:
            tick_size = self.client.get_tick_size(token_id)
            neg_risk = self.client.get_neg_risk(token_id)
        except Exception as e:
            logger.error(f"Order failed (metadata fetch): token_id={token_id} err={e}")
            return OrderResult(False, error=f"metadata fetch failed: {e}")

        # PD-220 v3 (Codex v2 F5): funder + signature_type are stored on client.builder,
        # not on client. Defensive: try builder first, fall back to client, fall back to env.
        builder = getattr(self.client, "builder", None)
        funder_addr = (
            getattr(builder, "funder", None) if builder else None
        ) or getattr(self.client, "funder", None) or os.environ.get("POLY_FUNDER_ADDRESS", "?")
        sig_type = (
            getattr(builder, "signature_type", None) if builder else None
        )
        if sig_type is None:
            sig_type = getattr(self.client, "signature_type", "?")

        logger.info(
            f"polymarket.sign.pre v2 token_id={token_id} side={clob_side} "
            f"price={price:.4f} size={size:.4f} tick_size={tick_size} "
            f"neg_risk={neg_risk} funder={funder_addr} signature_type={sig_type} "
            f"sdk=py-clob-client-v2 chain_id=137"
        )

        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=clob_side,
        )
        options = PartialCreateOrderOptions(tick_size=tick_size, neg_risk=neg_risk)

        # PD-220 v3 (Codex v2 F2 + F3): use combined create_and_post_order. The SDK's
        # internal loop handles BOTH exception path (raised PolyApiException 400) AND
        # non-exception path (200 with error_message body) via _is_order_version_mismatch
        # check + force-refresh + retry. Splitting the call (v2 attempt) bypassed that
        # logic and introduced silent-success + no-refresh bugs.
        try:
            result = self.client.create_and_post_order(
                order_args=order_args,
                options=options,
                order_type=OrderType.GTC,
                post_only=post_only,
            )
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return OrderResult(False, error=str(e))

        # Defensive result shape check: SDK's combined call typically returns dict on
        # success (with orderID) but may return dict with `error` key on certain failures
        # that did not raise. Treat any dict containing `error` as failure.
        if isinstance(result, dict) and result.get("error"):
            err_msg = result.get("error")
            logger.error(f"Order failed (returned error): token_id={token_id} err={err_msg}")
            return OrderResult(False, error=f"post returned error: {err_msg}")

        order_id = result.get("orderID") if isinstance(result, dict) else None
        if not order_id:
            logger.warning(f"Order placed but no orderID returned: result={result}")
            return OrderResult(False, error=f"no orderID in result: {result}")

        # PD-351 M1 honest fills: a GTC accepted as "live" is RESTING unfilled —
        # reporting filled_amount=size for it booked phantom fills (946/946 orders
        # in the DB said FILLED). Only "matched" means the order traded.
        snapshot = normalize_order_snapshot(order_id, result if isinstance(result, dict) else {})
        # Submission responses frequently omit size_matched. Never infer a fill
        # merely because status is MATCHED; confirmation is a separate event.
        return OrderResult(
            True, order_id, snapshot.filled_amount, snapshot.avg_price or price,
            status=snapshot.status.lower(), actual_cost=snapshot.actual_cost,
            fees=snapshot.fees, rebates=snapshot.rebates, order_mode=mode,
        )

    def get_order_snapshot(self, order_id: str) -> OrderSnapshot:
        if self.dry_run:
            raise RuntimeError("Paper orders are confirmed at submission")
        if not self.client:
            raise RuntimeError("CLOB client not initialized")
        payload = self.client.get_order(order_id)
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected get_order response: {payload!r}")
        return normalize_order_snapshot(order_id, payload)

    def get_order_trade_events(self, order_id: str, token_id: str,
                               trades: Optional[list] = None) -> list[OrderSnapshot]:
        """Return authenticated trade events belonging to one local order.

        The CLOB trade endpoint is filtered by asset, then narrowed to the
        taker order id or an embedded maker order id. Each event keeps the
        exchange trade id so persistence can aggregate distinct fills exactly
        once.
        """
        if self.dry_run or not self.client:
            return []
        from py_clob_client_v2.clob_types import TradeParams
        if trades is None:
            trades = self.client.get_trades(
                TradeParams(asset_id=token_id), only_first_page=False
            ) or []
        snapshots = []
        for trade in trades:
            if not isinstance(trade, dict):
                continue
            size = price = fee = 0.0
            matched = False
            if str(trade.get("taker_order_id") or "") == order_id:
                matched = True
                size = _number(trade, "size", "matched_amount")
                price = _number(trade, "price")
                rate = _number(trade, "fee_rate_bps")
                fee = size * (rate / 10_000.0) * price * (1.0 - price)
            else:
                for maker in trade.get("maker_orders") or []:
                    if isinstance(maker, dict) and str(
                        maker.get("order_id") or maker.get("maker_order_id") or ""
                    ) == order_id:
                        matched = True
                        size = _number(maker, "matched_amount", "size", "size_matched")
                        price = _number(maker, "price", default=_number(trade, "price"))
                        fee = 0.0
                        break
            if not matched:
                continue
            trade_id = trade.get("id") or trade.get("trade_id")
            if not trade_id:
                logger.warning("Skipping authenticated trade without stable id for order %s", order_id)
                continue
            payload = {
                "id": f"{trade_id}:{order_id}",
                "status": trade.get("status"),
                "size": size,
                "price": price,
                "actual_cost": size * price,
                "fees": fee,
            }
            snapshots.append(normalize_trade_event(order_id, payload))
        return snapshots

    def cancel_order(self, order_id: str) -> Any:
        if self.dry_run or not self.client:
            raise RuntimeError("Cannot cancel without a live authenticated client")
        from py_clob_client_v2 import OrderPayload
        return self.client.cancel_order(OrderPayload(orderID=order_id))

    def buy(self, token_id: str, dollar_amount: float, max_price: float) -> OrderResult:
        shares = dollar_amount / max_price
        return self.place_order(token_id, "BUY", shares, max_price)

def execute_opportunity(executor, opp, position_size: float) -> OrderResult:
    """Execute a weather trading opportunity."""
    if opp.recommended_side == "YES":
        token_id = opp.clob_token_ids[0] if hasattr(opp, 'clob_token_ids') else getattr(opp, 'yes_token_id', None)
        price = opp.yes_price if hasattr(opp, 'yes_price') else opp.entry_price
    else:
        token_id = opp.clob_token_ids[1] if hasattr(opp, 'clob_token_ids') else getattr(opp, 'no_token_id', None)
        price = opp.no_price if hasattr(opp, 'no_price') else (1 - opp.entry_price)
    
    if not token_id:
        return OrderResult(False, error="Missing token ID")
    
    limit_price = min(price + 0.01, 0.99)
    return executor.buy(token_id, position_size, limit_price)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Executor Test (DRY RUN)")
    
    ex = PolymarketExecutor(dry_run=True)
    result = ex.buy("test_token", 50.0, 0.35)
    
    print(f"Success: {result.success}")
    print(f"Order ID: {result.order_id}")
    print(f"Balance: ${ex.get_balance():.2f}")
