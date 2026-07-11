"""
SQLite persistence for positions and orders.
"""
import sqlite3
import json
import os
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple

from identifiers import canonical_event_key

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "weather_trading.db")

ACTIVE_ORDER_STATUSES = {
    "PENDING", "SUBMITTED", "LIVE", "DELAYED", "MATCHED", "PARTIALLY_FILLED",
    "PARTIALLY_CONFIRMED", "UNKNOWN",
}
ACTIVE_POSITION_STATUSES = {"OPEN", "RESOLUTION_PENDING"}
TERMINAL_ORDER_STATUSES = {"CONFIRMED", "CANCELED", "CANCELLED", "FAILED", "REJECTED"}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            opportunity_id TEXT,
            order_id TEXT,
            city TEXT NOT NULL,
            bucket TEXT NOT NULL,
            target_date TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            shares REAL NOT NULL DEFAULT 0,
            size REAL NOT NULL,
            current_price REAL,
            unrealized_pnl REAL DEFAULT 0,
            status TEXT DEFAULT 'OPEN',
            threshold_type TEXT,
            hours_remaining REAL,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            pnl REAL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            position_id TEXT,
            opportunity_id TEXT,
            token_id TEXT,
            side TEXT NOT NULL,
            price REAL NOT NULL,
            size_shares REAL NOT NULL,
            size_dollars REAL NOT NULL,
            status TEXT DEFAULT 'PENDING',
            filled_amount REAL DEFAULT 0,
            avg_price REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            error TEXT,
            FOREIGN KEY (position_id) REFERENCES positions(id)
        );

        CREATE TABLE IF NOT EXISTS trade_events (
            trade_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            status TEXT NOT NULL,
            size_shares REAL NOT NULL DEFAULT 0,
            price REAL NOT NULL DEFAULT 0,
            actual_cost REAL NOT NULL DEFAULT 0,
            fees REAL NOT NULL DEFAULT 0,
            rebates REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
        CREATE INDEX IF NOT EXISTS idx_positions_target_date ON positions(target_date);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_trade_events_order_status
            ON trade_events(order_id, status);
    """)
    # Additive, idempotent migrations. SQLite has no portable ADD COLUMN IF NOT
    # EXISTS, so inspect first. Existing money records are never rewritten.
    _add_columns(conn, "positions", {
        "actual_cost": "REAL",
        "fees": "REAL DEFAULT 0",
        "rebates": "REAL DEFAULT 0",
        "resolved_outcome": "TEXT",
        "resolution_source": "TEXT",
        "legacy_status": "TEXT",
        "fill_verified": "INTEGER DEFAULT 0",
    })
    _add_columns(conn, "orders", {
        "city": "TEXT",
        "bucket": "TEXT",
        "target_date": "TEXT",
        "event_key": "TEXT",
        "threshold_type": "TEXT",
        "hours_remaining": "REAL",
        "order_mode": "TEXT DEFAULT 'GTC'",
        "reserved_dollars": "REAL DEFAULT 0",
        "actual_cost": "REAL DEFAULT 0",
        "fees": "REAL DEFAULT 0",
        "rebates": "REAL DEFAULT 0",
        "confirmed_at": "TEXT",
        "canceled_at": "TEXT",
        "raw_status": "TEXT",
    })
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_orders_opportunity_status
            ON orders(opportunity_id, status);
        CREATE INDEX IF NOT EXISTS idx_orders_event_status
            ON orders(event_key, status);
        CREATE INDEX IF NOT EXISTS idx_positions_order
            ON positions(order_id) WHERE order_id IS NOT NULL;
    """)
    conn.execute(
        """UPDATE orders SET reserved_dollars = CASE
               WHEN status='PARTIALLY_CONFIRMED'
                 THEN MAX(0, (size_shares-COALESCE(filled_amount,0))*price)
               ELSE size_dollars END
           WHERE status IN ('PENDING','SUBMITTED','LIVE','DELAYED','MATCHED',
                            'PARTIALLY_FILLED','PARTIALLY_CONFIRMED','UNKNOWN')"""
    )
    # Confirmed provenance is explicit. Rows created by the pre-lifecycle API
    # may claim OPEN, WON, LOST, or EXPIRED even though filled_amount was
    # fabricated. Preserve their original status/P&L for provisional research,
    # but quarantine every unverified row from portfolio and verified stats.
    conn.execute(
        """UPDATE positions SET fill_verified=1
           WHERE EXISTS (
               SELECT 1 FROM orders o
               WHERE o.id=positions.order_id AND o.confirmed_at IS NOT NULL
           )"""
    )
    conn.execute(
        """UPDATE positions
           SET legacy_status=COALESCE(legacy_status, status),
               status='UNCONFIRMED_LEGACY', fill_verified=0
           WHERE status <> 'UNCONFIRMED_LEGACY'
             AND NOT EXISTS (
                 SELECT 1 FROM orders o
                 WHERE o.id=positions.order_id AND o.confirmed_at IS NOT NULL
             )"""
    )
    conn.execute(
        """UPDATE positions SET legacy_status='UNKNOWN'
           WHERE status='UNCONFIRMED_LEGACY' AND legacy_status IS NULL"""
    )
    # Backfill legacy order identity from its preserved position so aggregate
    # event caps include pre-migration resting orders. Normalize older API and
    # automation key formats to the one shared fallback format.
    identity_rows = conn.execute(
        """SELECT o.id, o.opportunity_id, o.event_key,
                  COALESCE(o.city, p.city) city,
                  COALESCE(o.target_date, p.target_date) target_date,
                  COALESCE(o.bucket, p.bucket) bucket
           FROM orders o LEFT JOIN positions p ON p.order_id=o.id"""
    ).fetchall()
    for row in identity_rows:
        city, target = row["city"], row["target_date"]
        if not city or not target:
            continue
        market_type = "low" if "_low_" in str(row["opportunity_id"] or "").lower() else "high"
        event_key = canonical_event_key(city, target, market_type)
        conn.execute(
            """UPDATE orders SET city=COALESCE(city,?), target_date=COALESCE(target_date,?),
                      bucket=COALESCE(bucket,?), event_key=? WHERE id=?""",
            (city, target, row["bucket"], event_key, row["id"]),
        )
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


def _add_columns(conn: sqlite3.Connection, table: str, columns: Dict[str, str]) -> None:
    present = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, declaration in columns.items():
        if name not in present:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def save_position(position: Dict[str, Any]) -> None:
    """Insert or update a position."""
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO positions
        (id, opportunity_id, order_id, city, bucket, target_date, side,
         entry_price, shares, size, current_price, unrealized_pnl,
         status, threshold_type, hours_remaining, opened_at, closed_at, pnl,
         actual_cost, fees, rebates, resolved_outcome, resolution_source,
         legacy_status, fill_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        position["id"],
        position.get("opportunityId"),
        position.get("orderId"),
        position["city"],
        position["bucket"],
        position["targetDate"],
        position["side"],
        position["entryPrice"],
        position.get("shares", 0),
        position["size"],
        position.get("currentPrice"),
        position.get("unrealizedPnl", 0),
        position.get("status", "OPEN"),
        position.get("thresholdType"),
        position.get("hoursRemaining"),
        position["openedAt"],
        position.get("closedAt"),
        position.get("pnl"),
        position.get("actualCost", position.get("size")),
        position.get("fees", 0),
        position.get("rebates", 0),
        position.get("resolvedOutcome"),
        position.get("resolutionSource"),
        position.get("legacyStatus"),
        1 if position.get("fillVerified") else 0,
    ))
    conn.commit()
    conn.close()


def load_positions(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load positions from database."""
    conn = get_connection()
    if status_filter:
        rows = conn.execute(
            "SELECT * FROM positions WHERE status = ? ORDER BY opened_at DESC", (status_filter,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM positions ORDER BY opened_at DESC"
        ).fetchall()
    conn.close()

    return [_row_to_position(row) for row in rows]


def update_position_status(position_id: str, status: str, pnl: Optional[float] = None) -> bool:
    """Update position status (OPEN -> WON/LOST/MANUAL)."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    if pnl is not None:
        conn.execute(
            "UPDATE positions SET status=?, closed_at=?, pnl=? WHERE id=?",
            (status, now, pnl, position_id)
        )
    else:
        conn.execute(
            "UPDATE positions SET status=?, closed_at=? WHERE id=?",
            (status, now, position_id)
        )
    affected = conn.total_changes
    conn.commit()
    conn.close()
    return affected > 0


def resolve_position(position_id: str, outcome: str, pnl: Optional[float] = None,
                     source: str = "manual") -> Dict[str, Any]:
    """Close a confirmed-fill position without inventing economics.

    WON/LOST can be calculated from confirmed shares and actual cost. Any other
    terminal outcome requires an explicit P&L amount.
    """
    outcome = outcome.upper()
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
        if not row:
            raise KeyError(position_id)
        order = conn.execute("SELECT status, confirmed_at FROM orders WHERE id=?", (row["order_id"],)).fetchone()
        if (not order or not order["confirmed_at"]
                or str(order["status"]).upper() not in {"CONFIRMED", "CANCELED", "CANCELLED"}):
            raise ValueError("Position cannot be scored without a confirmed fill")
        prior_outcome = str(row["resolved_outcome"] or row["status"] or "").upper()
        if prior_outcome in {"WON", "LOST", "MANUAL"}:
            if prior_outcome == outcome:
                return _row_to_position(row)
            raise ValueError(f"Position already resolved as {prior_outcome}; refusing outcome flip")
        actual_cost = row["actual_cost"] if row["actual_cost"] is not None else row["size"]
        fees = row["fees"] or 0.0
        rebates = row["rebates"] or 0.0
        if outcome not in {"WON", "LOST", "MANUAL"}:
            raise ValueError("Outcome must be WON, LOST, or MANUAL")
        if outcome == "WON":
            calculated = float(row["shares"]) - float(actual_cost) - float(fees) + float(rebates)
        elif outcome == "LOST":
            calculated = -float(actual_cost) - float(fees) + float(rebates)
        elif pnl is None:
            raise ValueError("Non-binary/manual close requires explicit pnl")
        else:
            calculated = float(pnl)
        if pnl is not None and outcome in {"WON", "LOST"} and abs(float(pnl) - calculated) > 0.01:
            raise ValueError(f"Provided pnl {pnl:.2f} disagrees with calculated pnl {calculated:.2f}")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE positions SET status=?, closed_at=?, pnl=?, resolved_outcome=?, "
            "resolution_source=? WHERE id=?",
            (outcome, now, calculated, outcome, source, position_id),
        )
        conn.commit()
        return _row_to_position(conn.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_order(order: Dict[str, Any]) -> None:
    """Save an order record."""
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO orders
        (id, position_id, opportunity_id, token_id, side, price,
         size_shares, size_dollars, status, filled_amount, avg_price,
         created_at, updated_at, error, city, bucket, target_date, event_key,
         threshold_type, hours_remaining, order_mode, reserved_dollars, actual_cost,
         fees, rebates, confirmed_at, canceled_at, raw_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order["id"],
        order.get("positionId"),
        order.get("opportunityId"),
        order.get("tokenId"),
        order["side"],
        order["price"],
        order["sizeShares"],
        order["sizeDollars"],
        order.get("status", "PENDING"),
        order.get("filledAmount", 0),
        order.get("avgPrice"),
        order["createdAt"],
        order.get("updatedAt"),
        order.get("error"),
        order.get("city"), order.get("bucket"), order.get("targetDate"), order.get("eventKey"),
        order.get("thresholdType"), order.get("hoursRemaining"),
        order.get("orderMode", "GTC"), order.get("reservedDollars", 0),
        order.get("actualCost", 0), order.get("fees", 0), order.get("rebates", 0),
        order.get("confirmedAt"), order.get("canceledAt"), order.get("rawStatus"),
    ))
    conn.commit()
    conn.close()


def load_orders(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load orders from database."""
    conn = get_connection()
    if status_filter:
        rows = conn.execute(
            "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC", (status_filter,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_position_count() -> int:
    """Get total position count for ID generation."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    conn.close()
    return count


def get_exposure(opportunity_id: Optional[str] = None,
                 event_key: Optional[str] = None) -> Tuple[float, float]:
    """Return (filled position cost, live reservation) for a scope.

    Reservations are remaining order notional only; confirmed cost lives on the
    position. This prevents resting GTC orders from inflating filled bankroll
    while still preventing duplicate orders from bypassing caps.
    """
    clauses, params = [], []
    if opportunity_id is not None:
        clauses.append("opportunity_id=?")
        params.append(opportunity_id)
    if event_key is not None:
        clauses.append("event_key=?")
        params.append(event_key)
    where = " AND ".join(clauses) or "1=1"
    conn = get_connection()
    try:
        order_ids = conn.execute(
            f"SELECT position_id, status, reserved_dollars FROM orders WHERE {where}", params
        ).fetchall()
        reservation = sum(
            float(row["reserved_dollars"] or 0)
            for row in order_ids if row["status"] in ACTIVE_ORDER_STATUSES
        )
        position_where = []
        position_params = []
        if opportunity_id is not None:
            position_where.append("opportunity_id=?")
            position_params.append(opportunity_id)
        if event_key is not None:
            # Older positions have no event_key. Orders are the authoritative
            # city/date link for both migrated and new positions.
            position_where.append("order_id IN (SELECT id FROM orders WHERE event_key=?)")
            position_params.append(event_key)
        position_where.append(
            "EXISTS (SELECT 1 FROM orders confirmed_order "
            "WHERE confirmed_order.id=positions.order_id AND confirmed_order.confirmed_at IS NOT NULL)"
        )
        pwhere = " AND ".join(position_where)
        placeholders = ",".join("?" for _ in ACTIVE_POSITION_STATUSES)
        rows = conn.execute(
            f"SELECT actual_cost, size FROM positions WHERE {pwhere} AND status IN ({placeholders})",
            [*position_params, *sorted(ACTIVE_POSITION_STATUSES)],
        ).fetchall()
        filled = sum(float(r["actual_cost"] if r["actual_cost"] is not None else r["size"]) for r in rows)
        return filled, reservation
    finally:
        conn.close()


def update_order_status(order_id: str, status: str, *, filled_amount: Optional[float] = None,
                        avg_price: Optional[float] = None, actual_cost: Optional[float] = None,
                        fees: Optional[float] = None, rebates: Optional[float] = None,
                        raw_status: Optional[str] = None) -> Dict[str, Any]:
    """Idempotently reconcile an order and create/update a position on CONFIRMED.

    MATCHED is deliberately nonterminal. It reserves only the unmatched amount
    until an authenticated lifecycle source reports CONFIRMED.
    """
    status = status.upper()
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            raise KeyError(order_id)
        previous = str(order["status"] or "UNKNOWN").upper()
        if previous == "CONFIRMED" and status != "CONFIRMED":
            # Authenticated REST snapshots can lag the user stream. Never let a
            # stale LIVE/MATCHED event undo confirmed economic truth.
            conn.rollback()
            return dict(order)
        if previous == "PARTIALLY_CONFIRMED" and status in {
            "PENDING", "SUBMITTED", "LIVE", "DELAYED", "MATCHED", "PARTIALLY_FILLED", "UNKNOWN"
        }:
            conn.rollback()
            return dict(order)
        if previous in {"CANCELED", "CANCELLED", "FAILED", "REJECTED"} and status in ACTIVE_ORDER_STATUSES:
            conn.rollback()
            return dict(order)
        existing_filled = float(order["filled_amount"] or 0)
        incoming_filled = float(filled_amount if filled_amount is not None else existing_filled)
        if previous in {"PARTIALLY_CONFIRMED", "CONFIRMED"}:
            # Authenticated lifecycle snapshots are cumulative. Stale or
            # out-of-order events must never shrink confirmed economic truth.
            incoming_filled = max(existing_filled, incoming_filled)
        filled = max(0.0, min(incoming_filled, float(order["size_shares"])))
        price = float(avg_price if avg_price is not None else order["avg_price"] or order["price"])
        if actual_cost is not None:
            cost = float(actual_cost)
        elif filled_amount is None and order["actual_cost"] is not None:
            cost = float(order["actual_cost"])
        else:
            cost = filled * price
        fee_value = float(fees if fees is not None else order["fees"] or 0)
        rebate_value = float(rebates if rebates is not None else order["rebates"] or 0)
        if previous in {"PARTIALLY_CONFIRMED", "CONFIRMED"}:
            cost = max(float(order["actual_cost"] or 0), cost)
            fee_value = max(float(order["fees"] or 0), fee_value)
            rebate_value = max(float(order["rebates"] or 0), rebate_value)
        remaining_shares = max(0.0, float(order["size_shares"]) - filled)
        if status == "PARTIALLY_CONFIRMED":
            reserved = remaining_shares * float(order["price"])
        elif status in ACTIVE_ORDER_STATUSES:
            # Until any fill is explicitly confirmed, the whole requested cash
            # amount remains committed (even when REST reports size_matched).
            reserved = float(order["size_dollars"])
        else:
            reserved = 0.0
        now = datetime.now(timezone.utc).isoformat()
        confirmed_at = now if status in {"CONFIRMED", "PARTIALLY_CONFIRMED"} else order["confirmed_at"]
        canceled_at = now if status in {"CANCELED", "CANCELLED"} else order["canceled_at"]
        conn.execute(
            "UPDATE orders SET status=?, filled_amount=?, avg_price=?, actual_cost=?, fees=?, rebates=?, "
            "reserved_dollars=?, updated_at=?, confirmed_at=?, canceled_at=?, raw_status=? WHERE id=?",
            (status, filled, price, cost, fee_value, rebate_value, reserved, now, confirmed_at,
             canceled_at, raw_status, order_id),
        )
        if status in {"CONFIRMED", "PARTIALLY_CONFIRMED"} and filled > 0:
            _upsert_position_from_confirmed_order(conn, order_id, filled, price, cost, fee_value, rebate_value)
        conn.commit()
        return dict(conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_trade_event(order_id: str, trade_id: str, status: str, *,
                      filled_amount: float, avg_price: float,
                      actual_cost: float, fees: float = 0,
                      rebates: float = 0, raw_status: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate one authenticated user-stream trade event idempotently.

    User-channel ``size`` is the size of one trade, not cumulative order fill.
    MATCHED/MINED therefore reserve the whole order; distinct CONFIRMED trade
    IDs are summed. The order becomes fully CONFIRMED only when that sum reaches
    the requested shares.
    """
    status = status.upper()
    if not trade_id:
        raise ValueError("Authenticated trade event requires a stable trade id")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            raise KeyError(order_id)
        prior_event = conn.execute(
            "SELECT status FROM trade_events WHERE trade_id=? AND order_id=?",
            (trade_id, order_id),
        ).fetchone()
        if prior_event and str(prior_event["status"]).upper() in {"CONFIRMED", "FAILED"}:
            conn.rollback()
            return dict(order)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO trade_events
               (trade_id,order_id,status,size_shares,price,actual_cost,fees,rebates,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(trade_id) DO UPDATE SET
                 status=excluded.status,size_shares=excluded.size_shares,
                 price=excluded.price,actual_cost=excluded.actual_cost,
                 fees=excluded.fees,rebates=excluded.rebates,updated_at=excluded.updated_at""",
            (trade_id, order_id, status, max(0.0, float(filled_amount)),
             float(avg_price or 0), max(0.0, float(actual_cost or 0)),
             max(0.0, float(fees or 0)), max(0.0, float(rebates or 0)), now),
        )
        totals = conn.execute(
            """SELECT COALESCE(SUM(size_shares),0) shares,
                      COALESCE(SUM(actual_cost),0) cost,
                      COALESCE(SUM(fees),0) fees,
                      COALESCE(SUM(rebates),0) rebates
               FROM trade_events WHERE order_id=? AND status='CONFIRMED'""",
            (order_id,),
        ).fetchone()
        shares = min(float(order["size_shares"]), float(totals["shares"] or 0))
        cost = float(totals["cost"] or 0)
        fee_total = float(totals["fees"] or 0)
        rebate_total = float(totals["rebates"] or 0)
        if shares > 0:
            remainder_canceled = str(order["status"] or "").upper() in {"CANCELED", "CANCELLED"}
            new_status = (
                "CANCELED" if remainder_canceled
                else "CONFIRMED" if shares >= float(order["size_shares"]) - 1e-9
                else "PARTIALLY_CONFIRMED"
            )
            reserved = 0.0 if remainder_canceled else max(
                0.0, (float(order["size_shares"]) - shares) * float(order["price"]),
            )
            confirmed_at = order["confirmed_at"] or now
            effective_price = cost / shares if cost > 0 else float(avg_price or order["price"])
        else:
            new_status = "LIVE" if status == "FAILED" else "MATCHED"
            reserved = float(order["size_dollars"])
            confirmed_at = order["confirmed_at"]
            effective_price = float(order["avg_price"] or order["price"])
        conn.execute(
            """UPDATE orders SET status=?,filled_amount=?,avg_price=?,actual_cost=?,
                      fees=?,rebates=?,reserved_dollars=?,updated_at=?,confirmed_at=?,raw_status=?
               WHERE id=?""",
            (new_status, shares, effective_price, cost, fee_total, rebate_total,
             reserved, now, confirmed_at, raw_status, order_id),
        )
        if shares > 0:
            _upsert_position_from_confirmed_order(
                conn, order_id, shares, effective_price, cost, fee_total, rebate_total,
            )
        conn.commit()
        return dict(conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _upsert_position_from_confirmed_order(conn: sqlite3.Connection, order_id: str,
                                          shares: float, price: float, cost: float,
                                          fees: float, rebates: float) -> None:
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    existing = conn.execute("SELECT id FROM positions WHERE order_id=?", (order_id,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE positions SET entry_price=?, shares=?, size=?, actual_cost=?, fees=?, rebates=?, fill_verified=1, "
            "status=CASE WHEN status IN ('WON','LOST') THEN status ELSE 'OPEN' END WHERE id=?",
            (price, shares, cost, cost, fees, rebates, existing["id"]),
        )
        return
    pos_id = _next_position_id(conn)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO positions
        (id, opportunity_id, order_id, city, bucket, target_date, side, entry_price,
         shares, size, current_price, unrealized_pnl, status, threshold_type,
         hours_remaining, opened_at, actual_cost, fees, rebates, fill_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'OPEN', ?, ?, ?, ?, ?, ?, 1)""",
        (pos_id, order["opportunity_id"], order_id, order["city"] or "UNKNOWN", order["bucket"] or "UNKNOWN",
         order["target_date"] or "1970-01-01", order["side"], price, shares, cost, price,
         order["threshold_type"], order["hours_remaining"], now, cost, fees, rebates),
    )
    conn.execute("UPDATE orders SET position_id=? WHERE id=?", (pos_id, order_id))


def _next_position_id(conn) -> str:
    """MAX-based id, not COUNT-based: COUNT+1 collides after any row deletion,
    and INSERT OR REPLACE then silently destroys the old row (PD-351 C2 — the
    orders table provably lost its dry-run history to this exact mechanism)."""
    row = conn.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTR(id, 5) AS INTEGER)), 0) "
        "FROM positions WHERE id LIKE 'pos_%'"
    ).fetchone()
    return f"pos_{row[0] + 1}"


def create_position_with_order(position: Dict[str, Any], order: Dict[str, Any]) -> str:
    """Atomically assign the position id and insert position + order in ONE
    transaction (PD-351 C1/C2). BEGIN IMMEDIATE holds the write lock across the
    MAX read so concurrent trades cannot race the id. Plain INSERTs — a
    collision must error loudly, never overwrite a real-money record.

    Mutates `position["id"]`, `order["positionId"]`, and (if unset/dry-run)
    `order["id"]`; returns the assigned position id.
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        pos_id = _next_position_id(conn)
        position["id"] = pos_id
        order["positionId"] = pos_id
        # Dry-run orders all report order_id="dry_run" — as a PK that collapsed
        # every paper order onto one row. Real CLOB ids are unique; everything
        # else gets a position-derived id.
        if not order.get("id") or order["id"] == "dry_run":
            order["id"] = f"ord_{pos_id}"
        conn.execute("""
            INSERT INTO positions
            (id, opportunity_id, order_id, city, bucket, target_date, side,
             entry_price, shares, size, current_price, unrealized_pnl,
             status, threshold_type, hours_remaining, opened_at, closed_at, pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            position["id"], position.get("opportunityId"), position.get("orderId"),
            position["city"], position["bucket"], position["targetDate"],
            position["side"], position["entryPrice"], position.get("shares", 0),
            position["size"], position.get("currentPrice"),
            position.get("unrealizedPnl", 0), position.get("status", "OPEN"),
            position.get("thresholdType"), position.get("hoursRemaining"),
            position["openedAt"], position.get("closedAt"), position.get("pnl"),
        ))
        conn.execute("""
            INSERT INTO orders
            (id, position_id, opportunity_id, token_id, side, price,
             size_shares, size_dollars, status, filled_amount, avg_price,
             created_at, updated_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order["id"], order.get("positionId"), order.get("opportunityId"),
            order.get("tokenId"), order["side"], order["price"],
            order["sizeShares"], order["sizeDollars"],
            order.get("status", "PENDING"), order.get("filledAmount", 0),
            order.get("avgPrice"), order["createdAt"],
            order.get("updatedAt"), order.get("error"),
        ))
        conn.commit()
        return pos_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_position(row) -> Dict[str, Any]:
    """Convert a database row to a position dict matching the API format."""
    return {
        "id": row["id"],
        "opportunityId": row["opportunity_id"],
        "orderId": row["order_id"],
        "city": row["city"],
        "bucket": row["bucket"],
        "targetDate": row["target_date"],
        "side": row["side"],
        "entryPrice": row["entry_price"],
        "shares": row["shares"],
        "size": row["size"],
        "currentPrice": row["current_price"],
        "unrealizedPnl": row["unrealized_pnl"] or 0,
        "status": row["status"],
        "thresholdType": row["threshold_type"],
        "hoursRemaining": row["hours_remaining"],
        "openedAt": row["opened_at"],
        "closedAt": row["closed_at"],
        "pnl": row["pnl"],
        "actualCost": row["actual_cost"],
        "fees": row["fees"] or 0,
        "rebates": row["rebates"] or 0,
        "resolvedOutcome": row["resolved_outcome"],
        "resolutionSource": row["resolution_source"],
        "legacyStatus": row["legacy_status"],
        "fillVerified": bool(row["fill_verified"]),
    }


def expire_stale_positions(hours: float = 48.0) -> int:
    """Move overdue fills to RESOLUTION_PENDING; never fabricate resolution."""
    conn = get_connection()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    rows = conn.execute(
        "SELECT id, target_date FROM positions WHERE status = 'OPEN'"
    ).fetchall()

    expired_count = 0
    for row in rows:
        try:
            target = datetime.fromisoformat(row["target_date"] + "T23:59:59+00:00")
            if (now - target).total_seconds() > hours * 3600:
                conn.execute(
                    "UPDATE positions SET status='RESOLUTION_PENDING' WHERE id=?",
                    (row["id"],)
                )
                expired_count += 1
        except (ValueError, TypeError):
            continue

    conn.commit()
    conn.close()
    if expired_count > 0:
        logger.info(f"Marked {expired_count} stale positions RESOLUTION_PENDING (>{hours}h past target date)")
    return expired_count
