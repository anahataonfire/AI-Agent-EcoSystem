# Break-Glass Procedure: Allow Destructive Operations

> **WARNING**: This procedure temporarily unlocks protected databases.
> Follow ALL steps in order. Do not skip the re-locking step.

---

## When to Use

Use this procedure ONLY for:
- Database migrations (schema changes via Alembic/raw SQL)
- Bulk data cleanup (removing corrupted entries)
- Emergency recovery operations

**Do NOT use for**: routine operations, testing, or verification.

---

## Prerequisites

1. Ensure you have a recent backup:
   ```bash
   mkdir -p backups/$(date +%Y-%m-%d)
   cp data/content/content.db backups/$(date +%Y-%m-%d)/
   cp data/evidence_store.db backups/$(date +%Y-%m-%d)/
   cp data/advisor_learning.db backups/$(date +%Y-%m-%d)/
   ```

2. Record the current row counts:
   ```bash
   sqlite3 data/content/content.db "SELECT COUNT(*) FROM content;"
   sqlite3 data/evidence_store.db "SELECT COUNT(*) FROM evidence;"
   ```

---

## Procedure

### Step 1: Unlock filesystem protection

```bash
# Unlock specific DB(s) you need to modify
chflags nouchg data/content/content.db
chflags nouchg data/evidence_store.db
chflags nouchg data/advisor_learning.db
chflags nouchg data/authoritative_identity_store.db
```

### Step 2: Set environment override

```bash
export DTL_ALLOW_DESTRUCTIVE=YES_I_KNOW_WHAT_IM_DOING
```

### Step 3: Run the specific migration command

```bash
# Example: run a migration script
python scripts/migrate_some_schema.py

# Example: CLI command
dtl datamart-rebuild --topic some-topic
```

### Step 4: Unset environment variable

```bash
unset DTL_ALLOW_DESTRUCTIVE
```

### Step 5: Re-lock databases

```bash
chflags uchg data/content/content.db
chflags uchg data/evidence_store.db
chflags uchg data/advisor_learning.db
chflags uchg data/authoritative_identity_store.db
```

### Step 6: Verify integrity

```bash
# Check row counts haven't unexpectedly dropped
sqlite3 data/content/content.db "SELECT COUNT(*) FROM content;"
sqlite3 data/evidence_store.db "SELECT COUNT(*) FROM evidence;"

# Check file hashes match expected
shasum -a 256 data/content/content.db
```

### Step 7: Record incident

Add entry to ledger:
```bash
cat >> data/ledger/$(date +%Y/%m/%d)/break_glass.json << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "operation": "break-glass",
  "reason": "<describe why>",
  "operator": "$(whoami)",
  "databases_modified": ["content.db"],
  "verification_passed": true
}
EOF
```

---

## Emergency: If You Forget to Re-Lock

Run this immediately:
```bash
cd /Users/adamc/Documents/001\ AI\ Agents/AI\ Agent\ EcoSystem\ 2.0
chflags uchg data/content/content.db data/evidence_store.db data/advisor_learning.db data/authoritative_identity_store.db
unset DTL_ALLOW_DESTRUCTIVE
```

---

## Full DB List and Lock Status Check

```bash
# View lock status (uchg = locked)
ls -lO data/*.db data/content/*.db

# Lock all critical DBs
chflags uchg \
  data/content/content.db \
  data/evidence_store.db \
  data/advisor_learning.db \
  data/authoritative_identity_store.db
```

**DBs NOT typically locked** (derived/caches):
- `data/planner_tasks.db` - regenerable from content
- `data/claim_entailment.db` - cache
- `data/query_cache.db` - cache

---

## Contact

If you're unsure whether to proceed, stop and ask in the team channel first.
