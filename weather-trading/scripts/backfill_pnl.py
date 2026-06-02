#!/usr/bin/env python3
"""
PD-339 — one-shot realized-P&L backfill from Polymarket gamma-api resolution.

WHY: 807 positions carry pnl=NULL because no resolver loop exists (PD-324 withdrawn).
This recovers REALIZED P&L from Polymarket's own settlement (the authoritative outcome),
which is exactly what the operator's money did.

DESIGN (incorporates PD-324 Codex-review lessons):
  - Keys on MARKET RESOLUTION (city+date+bucket+side), NOT order_id -> sidesteps the
    7 dry_run-order_id rows that would corrupt an order-keyed join (PD-324 B2-2).
  - Event-cached: fetches each unique (city,date,market_type) event ONCE (PD-324 B2-7).
  - Only scores markets Polymarket has actually closed; closed=False -> PENDING, untouched.
  - Dry-run by default. --write backs up the DB before any UPDATE (PD-324 B2-8).

USAGE:
  python scripts/backfill_pnl.py            # dry-run: report only, no writes
  python scripts/backfill_pnl.py --write    # backup + write pnl/status for scored rows
"""
import sqlite3, urllib.request, json, time, re, sys, shutil, os
from datetime import datetime, timezone

DB = os.path.expanduser("~/Documents/Projects/Ecosystem/weather-trading/backend/weather_trading.db")
GAMMA = "https://gamma-api.polymarket.com/events?slug="
UA = {"User-Agent": "Mozilla/5.0"}
MONTHS = ["", "january", "february", "march", "april", "may", "june",
          "july", "august", "september", "october", "november", "december"]

def build_slug(city, date_str, mtype):
    y, m, d = date_str.split("-")
    prefix = "highest" if mtype == "high" else "lowest"
    return f"{prefix}-temperature-in-{city.replace('_','-')}-on-{MONTHS[int(m)]}-{int(d)}-{y}"

def fetch_event(slug, cache, stats):
    if slug in cache:
        return cache[slug]
    result = None
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(GAMMA + slug, headers=UA)
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.load(r)
            result = data[0] if data else None
            break
        except Exception as e:
            if attempt == 2:
                stats["fetch_errors"].append(f"{slug}: {e}")
            time.sleep(1.0)
    cache[slug] = result
    time.sleep(0.25)  # rate limit
    return result

def _norm_price(p):
    try:
        return round(float(p))
    except Exception:
        return None

def canon_title(title):
    """gamma groupItemTitle -> canonical key. e.g. '36-37°F'->('R',36,37,'F'); '36°C'->('S',36,'C')."""
    t = title.replace("°", "°").strip()
    m = re.match(r"(\d+)\s*°?\s*([FC])?\s*or below", t, re.I)
    if m: return ("LTE", int(m.group(1)), (m.group(2) or "").upper())
    m = re.match(r"(\d+)\s*°?\s*([FC])?\s*or higher", t, re.I)
    if m: return ("GTE", int(m.group(1)), (m.group(2) or "").upper())
    m = re.match(r"(\d+)\s*-\s*(\d+)\s*°?\s*([FC])", t, re.I)
    if m: return ("RANGE", int(m.group(1)), int(m.group(2)), m.group(3).upper())
    m = re.match(r"(\d+)\s*°\s*([FC])", t, re.I)
    if m: return ("SINGLE", int(m.group(1)), m.group(2).upper())
    return None

def canon_bucket(bucket):
    """local bucket string -> canonical key. '≤35.0°F'->('LTE',35,'F'); '36.0-37.0°F'->('R',...); '36.0-36.0°C'->('S',36,'C')."""
    b = bucket.replace("°", "°").strip()
    unit = "F" if "F" in b else ("C" if "C" in b else "")
    nums = re.findall(r"(\d+(?:\.\d+)?)", b)
    if not nums: return None
    if "≤" in b or "<=" in b or b.lower().startswith("lte"):
        return ("LTE", int(float(nums[0])), unit)
    if "≥" in b or ">=" in b or b.lower().startswith("gte"):
        return ("GTE", int(float(nums[0])), unit)
    if len(nums) >= 2:
        lo, hi = int(float(nums[0])), int(float(nums[1]))
        if lo == hi:
            return ("SINGLE", lo, unit)
        return ("RANGE", lo, hi, unit)
    return ("SINGLE", int(float(nums[0])), unit)

def market_type_from_opp(opp_id):
    return "low" if "_low_" in (opp_id or "") else "high"

def main():
    write = "--write" in sys.argv
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, opportunity_id, city, bucket, target_date, side, "
        "entry_price, shares, size FROM positions WHERE pnl IS NULL"
    ).fetchall()

    cache = {}
    stats = {"fetch_errors": []}
    results = []   # (id, status, pnl)
    pending = unmatched = scored = 0
    won = lost = 0
    net = 0.0
    unmatched_samples, win_samples, loss_samples = [], [], []

    uniq_events = {(r["city"], r["target_date"], market_type_from_opp(r["opportunity_id"])) for r in rows}
    print(f"Positions with NULL pnl: {len(rows)}  |  unique events to fetch: {len(uniq_events)}")
    print("Fetching gamma-api resolutions (cached per event)...\n")

    done = 0
    for r in rows:
        mtype = market_type_from_opp(r["opportunity_id"])
        slug = build_slug(r["city"], r["target_date"], mtype)
        ev = fetch_event(slug, cache, stats)
        done += 1
        if done % 50 == 0:
            print(f"  ...{done}/{len(rows)} positions processed")

        if ev is None:
            unmatched += 1
            if len(unmatched_samples) < 8: unmatched_samples.append(f"{r['id']} {slug} [no event]")
            continue
        if not ev.get("closed"):
            pending += 1
            continue

        want = canon_bucket(r["bucket"])
        match = None
        for mk in ev.get("markets", []):
            if canon_title(mk.get("groupItemTitle", "") or "") == want:
                match = mk
                break
        if match is None:
            unmatched += 1
            if len(unmatched_samples) < 8:
                unmatched_samples.append(f"{r['id']} bucket={r['bucket']!r} canon={want} [no title match]")
            continue

        op = match.get("outcomePrices")
        try:
            op = json.loads(op) if isinstance(op, str) else op
        except Exception:
            op = None
        if not op or len(op) < 2:
            unmatched += 1
            continue
        yes_p, no_p = _norm_price(op[0]), _norm_price(op[1])
        if {yes_p, no_p} != {0, 1}:
            unmatched += 1
            if len(unmatched_samples) < 8:
                unmatched_samples.append(f"{r['id']} prices={op} [not cleanly resolved]")
            continue

        side = (r["side"] or "").upper()
        win = (yes_p == 1) if side == "YES" else (no_p == 1)
        shares, size = float(r["shares"] or 0), float(r["size"] or 0)
        pnl = round(shares - size, 4) if win else round(-size, 4)
        status = "WON" if win else "LOST"
        results.append((r["id"], status, pnl))
        scored += 1
        net += pnl
        if win:
            won += 1
            if len(win_samples) < 5: win_samples.append((r["id"], r["city"], r["bucket"], side, pnl))
        else:
            lost += 1
            if len(loss_samples) < 5: loss_samples.append((r["id"], r["city"], r["bucket"], side, pnl))

    print("\n" + "=" * 64)
    print("REALIZED P&L BACKFILL — DRY RUN" if not write else "REALIZED P&L BACKFILL — WRITE")
    print("=" * 64)
    print(f"  NULL-pnl positions   : {len(rows)}")
    print(f"  Scored (resolved)    : {scored}   (WON {won} / LOST {lost})")
    print(f"  Pending (not closed) : {pending}")
    print(f"  Unmatched/unresolved : {unmatched}")
    print(f"  Fetch errors         : {len(stats['fetch_errors'])}")
    print(f"  --- NET REALIZED P&L : ${net:,.2f} ---")
    if scored:
        print(f"  avg win ${(sum(p for _,s,p in results if s=='WON')/won if won else 0):.2f} | "
              f"avg loss ${(sum(p for _,s,p in results if s=='LOST')/lost if lost else 0):.2f}")
    print("\n  sample WINS :", win_samples)
    print("  sample LOSS :", loss_samples)
    if unmatched_samples:
        print("\n  unmatched samples:")
        for s in unmatched_samples: print("   ", s)
    if stats["fetch_errors"][:5]:
        print("\n  fetch errors (first 5):")
        for e in stats["fetch_errors"][:5]: print("   ", e)

    if write and results:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bak = f"{DB}.bak-{ts}"
        shutil.copy2(DB, bak)
        print(f"\n  DB backed up -> {bak}")
        now = datetime.now(timezone.utc).isoformat()
        cur = con.cursor()
        for pid, status, pnl in results:
            cur.execute(
                "UPDATE positions SET pnl=?, status=?, closed_at=COALESCE(closed_at,?) WHERE id=?",
                (pnl, status, now, pid),
            )
        con.commit()
        print(f"  WROTE {len(results)} rows (pnl + status). Backup at {bak}")
    elif write:
        print("\n  --write set but nothing scored; no changes.")
    else:
        print("\n  DRY RUN — no DB changes. Re-run with --write to commit.")
    con.close()

if __name__ == "__main__":
    main()
