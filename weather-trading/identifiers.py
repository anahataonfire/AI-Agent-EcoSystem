"""Canonical identities shared by API, automation, persistence, and strategy."""


def canonical_event_key(city: str, target_date: str, market_type: str = "high",
                        event_id: str | None = None) -> str:
    """Return the stable exposure key shared by legacy and current orders.

    Gamma event IDs remain separate arbitrage evidence. Historical reservations
    predate that metadata, so exposure identity intentionally uses the
    derivable city/date/type tuple for continuity.
    """
    city_key = str(city or "unknown").strip().lower().replace(" ", "_")
    kind = str(market_type or "high").strip().lower()
    return f"weather::{city_key}::{target_date}::{kind}"
