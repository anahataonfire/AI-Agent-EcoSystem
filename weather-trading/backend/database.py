"""
SQLite persistence for positions and orders.
"""
import sqlite3
import json
import os
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "weather_trading.db")


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

        CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
        CREATE INDEX IF NOT EXISTS idx_positions_target_date ON positions(target_date);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
    """)
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


def save_position(position: Dict[str, Any]) -> None:
    """Insert or update a position."""
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO positions
        (id, opportunity_id, order_id, city, bucket, target_date, side,
         entry_price, shares, size, current_price, unrealized_pnl,
         status, threshold_type, hours_remaining, opened_at, closed_at, pnl)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def save_order(order: Dict[str, Any]) -> None:
    """Save an order record."""
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO orders
        (id, position_id, opportunity_id, token_id, side, price,
         size_shares, size_dollars, status, filled_amount, avg_price,
         created_at, updated_at, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    }


def expire_stale_positions(hours: float = 48.0) -> int:
    """Mark OPEN positions as EXPIRED if their targetDate is more than `hours` hours in the past."""
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
                    "UPDATE positions SET status='EXPIRED', closed_at=? WHERE id=?",
                    (now_iso, row["id"])
                )
                expired_count += 1
        except (ValueError, TypeError):
            continue

    conn.commit()
    conn.close()
    if expired_count > 0:
        logger.info(f"Auto-expired {expired_count} stale positions (>{hours}h past target date)")
    return expired_count

