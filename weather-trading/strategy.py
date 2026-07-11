"""Profit-strategy primitives shared by scanners, automation and backtests.

The helpers in this module are deliberately side-effect free. Live execution
must layer reservation and re-quote checks around the returned signals.
"""

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ReturnMetrics:
    price: float
    gross_profit_per_share: float
    gross_return_pct: float
    estimated_fee_per_share: Optional[float]
    estimated_fee_pct: Optional[float]
    net_profit_per_share: Optional[float]
    net_win_return_pct: Optional[float]
    fee_enabled: Optional[bool]
    fee_rate_bps: Optional[int]
    fee_known: bool
    fee_model: str
    liquidity_role: str


def calculate_return_metrics(
    price: float,
    *,
    fee_enabled: Optional[bool] = None,
    fee_rate_bps: Optional[int] = None,
    liquidity_role: str = "taker",
) -> ReturnMetrics:
    """Return gross and fee-net payoff for one winning binary share.

    Current Polymarket dynamic fees are ``shares * feeRate * p * (1-p)``.
    This function reports the one-share fee. Maker/post-only orders have zero
    platform fee; a GTC that crosses is a taker and must use the market's rate.
    A fee-enabled market without a rate remains unknown rather than silently
    calling gross return net.
    """
    if not 0 < price < 1:
        raise ValueError("price must be between 0 and 1")
    gross_profit = 1.0 - price
    gross_pct = gross_profit / price * 100.0
    role = liquidity_role.lower().replace("post_only", "maker").replace("post-only", "maker")
    if role not in {"maker", "taker"}:
        raise ValueError("liquidity_role must be maker/post-only or taker")
    if role == "maker":
        fee_rate_bps = 0
        fee_enabled = False
    if fee_enabled is False:
        fee_rate_bps = 0
    if fee_rate_bps is not None:
        fee_rate_bps = max(0, int(fee_rate_bps))
        fee = (fee_rate_bps / 10_000.0) * price * (1.0 - price)
        fee_pct = fee / price * 100.0
        net_profit = gross_profit - fee
        net_pct = net_profit / price * 100.0
        return ReturnMetrics(
            price, gross_profit, gross_pct, fee, fee_pct, net_profit, net_pct,
            fee_enabled if fee_enabled is not None else fee_rate_bps > 0,
            fee_rate_bps, True, "polymarket-dynamic-p-times-one-minus-p", role,
        )
    if fee_enabled is True:
        return ReturnMetrics(
            price, gross_profit, gross_pct, None, None, None, None,
            True, None, False, "unknown-enabled-market-fee", role,
        )
    # Metadata absent is different from a known zero-fee market.
    return ReturnMetrics(
        price, gross_profit, gross_pct, None, None, None, None,
        fee_enabled, None, False, "unknown-fee-metadata", role,
    )


@dataclass(frozen=True)
class ArbitrageLeg:
    market_id: str
    bucket: str
    token_id: Optional[str]
    ask_price: float
    fee_rate_bps: Optional[int]
    estimated_cost: float


@dataclass(frozen=True)
class CompleteEventArbitrage:
    event_key: str
    legs: Tuple[ArbitrageLeg, ...]
    complete_coverage: bool
    raw_cost: float
    guarded_cost: float
    guaranteed_payout: float
    profit_per_set: float
    profit_pct: float
    fee_known: bool
    signal_only: bool = True
    reasons: Tuple[str, ...] = field(default_factory=tuple)


def _bucket_label(market) -> str:
    lo, hi = getattr(market, "bucket_low", None), getattr(market, "bucket_high", None)
    unit = getattr(market, "bucket_unit", "F")
    if lo is None or lo == float("-inf"):
        return f"≤{hi}°{unit}"
    if hi is None or hi == float("inf"):
        return f"≥{lo}°{unit}"
    return f"{lo}-{hi}°{unit}"


def has_complete_bucket_coverage(markets: Sequence) -> Tuple[bool, str]:
    """Prove integer-outcome bucket coverage: both open tails, no gap/overlap."""
    if len(markets) < 2:
        return False, "fewer-than-two-buckets"
    units = {getattr(m, "bucket_unit", "F") for m in markets}
    if len(units) != 1:
        return False, "mixed-units"
    ordered = sorted(
        markets,
        key=lambda m: float("-inf") if getattr(m, "bucket_low", None) in (None, float("-inf"))
        else float(getattr(m, "bucket_low")),
    )
    first_lo = getattr(ordered[0], "bucket_low", None)
    last_hi = getattr(ordered[-1], "bucket_high", None)
    if first_lo not in (None, float("-inf")):
        return False, "missing-lower-tail"
    if last_hi not in (None, float("inf")):
        return False, "missing-upper-tail"
    for left, right in zip(ordered, ordered[1:]):
        left_hi = getattr(left, "bucket_high", None)
        right_lo = getattr(right, "bucket_low", None)
        if left_hi in (None, float("inf")) or right_lo in (None, float("-inf")):
            return False, "interior-open-bucket"
        # Settlement is integer degrees; consecutive inclusive buckets meet at +1.
        if abs((float(left_hi) + 1.0) - float(right_lo)) > 1e-6:
            return False, "gap-or-overlap"
    return True, "complete"


def detect_complete_event_arbitrage(
    markets: Iterable,
    *,
    min_profit_pct: float = 0.25,
    slippage_bps: int = 20,
    allow_unknown_fees: bool = False,
    signal_only: bool = True,
    quote_provider=None,
) -> List[CompleteEventArbitrage]:
    """Detect buy-all-YES complete-set arbitrage for weather bucket events.

    A signal is emitted only when the supplied markets prove complete mutually
    exclusive integer coverage. Fee-enabled legs with unknown rates are rejected
    by default, as are books whose slippage/fee guarded cost removes the edge.
    """
    grouped = {}
    for market in markets:
        key = (
            getattr(market, "city_key", ""),
            getattr(market, "target_date", ""),
            getattr(market, "market_type", "high"),
        )
        grouped.setdefault(key, []).append(market)
    signals: List[CompleteEventArbitrage] = []
    for group_key, group in grouped.items():
        event_ids = {str(getattr(m, "event_id", "") or "") for m in group}
        if len(event_ids) != 1 or "" in event_ids:
            # City/date/type similarity is not authoritative event identity.
            # Never buy a "complete set" assembled across different events.
            continue
        complete, reason = has_complete_bucket_coverage(group)
        if not complete:
            continue
        legs: List[ArbitrageLeg] = []
        raw_cost = 0.0
        guarded_cost = 0.0
        fee_known = True
        valid = True
        for market in group:
            quoted = quote_provider(market) if quote_provider else None
            ask = float(quoted or getattr(market, "yes_best_ask", 0)
                        or getattr(market, "yes_price", 0) or 0)
            if not 0 < ask < 1 or not getattr(market, "accepting_orders", True):
                valid = False
                break
            enabled = getattr(market, "fee_enabled", None)
            rate = getattr(market, "fee_rate_bps", None)
            metrics = calculate_return_metrics(
                ask, fee_enabled=enabled, fee_rate_bps=rate, liquidity_role="taker"
            )
            if not metrics.fee_known:
                fee_known = False
                if not allow_unknown_fees:
                    valid = False
                    break
            fee = metrics.estimated_fee_per_share or 0.0
            slip = ask * max(0, int(slippage_bps)) / 10_000.0
            raw_cost += ask
            guarded_cost += ask + fee + slip
            tokens = getattr(market, "clob_token_ids", (None, None)) or (None, None)
            legs.append(ArbitrageLeg(
                market_id=str(getattr(market, "market_id", "")),
                bucket=_bucket_label(market), token_id=tokens[0] if tokens else None,
                ask_price=ask, fee_rate_bps=rate, estimated_cost=ask + fee + slip,
            ))
        if not valid or guarded_cost <= 0:
            continue
        profit = 1.0 - guarded_cost
        profit_pct = profit / guarded_cost * 100.0
        if profit_pct + 1e-12 < min_profit_pct:
            continue
        event_key = next(iter(event_ids))
        signals.append(CompleteEventArbitrage(
            event_key=event_key, legs=tuple(legs), complete_coverage=True,
            raw_cost=raw_cost, guarded_cost=guarded_cost, guaranteed_payout=1.0,
            profit_per_set=profit, profit_pct=profit_pct, fee_known=fee_known,
            signal_only=signal_only, reasons=(reason, "fees-and-slippage-guarded"),
        ))
    return sorted(signals, key=lambda s: s.profit_pct, reverse=True)
