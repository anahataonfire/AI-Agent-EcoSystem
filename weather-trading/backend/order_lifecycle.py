"""Authenticated order lifecycle adapter boundary.

Network clients translate their payloads into OrderSnapshot; this module owns
the persistence transition. Tests can feed snapshots without network access.
"""
from typing import Dict, Any

from database import apply_trade_event, update_order_status
from executor import OrderSnapshot, normalize_order_snapshot, normalize_trade_event


def apply_snapshot(snapshot: OrderSnapshot) -> Dict[str, Any]:
    return update_order_status(
        snapshot.order_id,
        snapshot.status,
        filled_amount=snapshot.filled_amount,
        avg_price=snapshot.avg_price,
        actual_cost=snapshot.actual_cost,
        fees=snapshot.fees,
        rebates=snapshot.rebates,
        raw_status=snapshot.raw_status,
    )


def apply_authenticated_event(order_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a REST/user-stream event after its transport authenticated it."""
    return apply_snapshot(normalize_order_snapshot(order_id, payload))


def apply_authenticated_trade_event(order_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Apply an authenticated user-stream MATCHED/MINED/CONFIRMED/FAILED event."""
    snapshot = normalize_trade_event(order_id, payload)
    return apply_trade_event(
        order_id, snapshot.event_id or "", snapshot.status,
        filled_amount=snapshot.filled_amount, avg_price=snapshot.avg_price,
        actual_cost=snapshot.actual_cost, fees=snapshot.fees,
        rebates=snapshot.rebates, raw_status=snapshot.raw_status,
    )


def apply_trade_snapshot(snapshot: OrderSnapshot) -> Dict[str, Any]:
    """Persist a normalized authenticated trade snapshot."""
    return apply_trade_event(
        snapshot.order_id, snapshot.event_id or "", snapshot.status,
        filled_amount=snapshot.filled_amount, avg_price=snapshot.avg_price,
        actual_cost=snapshot.actual_cost, fees=snapshot.fees,
        rebates=snapshot.rebates, raw_status=snapshot.raw_status,
    )
