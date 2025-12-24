# Policy Memory Design

**Cross-Run Learning Without Identity Violation**

---

## Overview

Policy Memory enables strategic learning across runs while preserving identity invariants. It stores ONLY strategy effectiveness data — never facts, beliefs, or identity attributes.

---

## Data Schema

```json
{
  "policy_memory": {
    "version": "1.0.0",
    "last_updated": "ISO8601 timestamp",
    "entries": [
      {
        "entry_id": "uuid",
        "skill_name": "string",
        "context_hash": "sha256 of query type",
        "success_count": "int",
        "failure_count": "int",
        "avg_cost_units": "float",
        "avg_steps": "float",
        "last_used": "ISO8601 timestamp",
        "decay_factor": "float (0-1)",
        "created_at": "ISO8601 timestamp"
      }
    ],
    "routing_weights": {
      "skill_name": "float (0-1)"
    },
    "retry_adjustments": {
      "failure_class": {
        "backoff_multiplier": "float",
        "max_attempts_override": "int or null"
      }
    }
  }
}
```

---

## Read/Write Rules

### Write Rules

| Rule | Description |
|------|-------------|
| **W1: Post-run only** | Policy Memory is written ONLY after `reporter_node` completes |
| **W2: Ledger-logged** | Every write is logged to run ledger BEFORE persistence |
| **W3: Append-style** | Updates increment counters; never delete or overwrite history |
| **W4: Bounded updates** | Single run can only affect one entry per skill |
| **W5: Decay on read** | Decay factor applied when reading, not writing |

### Read Rules

| Rule | Description |
|------|-------------|
| **R1: Start-of-run snapshot** | Policy Memory read once at run start; immutable during run |
| **R2: Deterministic ordering** | Entries read in sorted order by skill_name |
| **R3: Decay application** | `effective_weight = base_weight * decay_factor` |
| **R4: Cold-start default** | Missing entries use default weights (1.0) |
| **R5: Never affects grounding** | Policy Memory NEVER influences evidence selection or citation |

---

## Decay Mechanism

```
decay_factor = initial_factor * (0.95 ^ days_since_last_use)

Where:
- initial_factor = 1.0 for new entries
- Minimum decay_factor = 0.1 (never fully forgotten)
- Entries with decay_factor < 0.1 are archived, not deleted
```

---

## Failure Modes

| Failure | Detection | Response |
|---------|-----------|----------|
| **Corrupted policy file** | Schema validation failure | Reset to defaults, log DTL-STRAT-001 |
| **Stale snapshot** | Timestamp check | Refresh at next run start |
| **Runaway bias** | Weight outside [0.1, 2.0] | Clamp to bounds, log warning |
| **Circular learning** | Same decision repeated despite failures | Break after 3 identical outcomes |
| **Ledger desync** | Policy state not in ledger | Reject write, abort learning for run |

---

## Policy Memory vs Identity Store

| Dimension | Policy Memory | Identity Store |
|-----------|---------------|----------------|
| **Purpose** | Strategy effectiveness | Core system beliefs |
| **Contents** | Routing weights, retry tuning | Facts, traits, directives |
| **Mutability** | Updated after every run | Immutable at runtime |
| **Affects grounding** | Never | Yes (system facts appear in reports) |
| **Decay** | Yes (time-based) | No |
| **Cross-run persistence** | Yes | Yes |
| **Who can write** | Learning system only | Reporter node only (identity writes) |
| **Ledger requirement** | Every update logged | Every update logged |
| **Reset behavior** | Resets to defaults | Never reset |
| **Failure response** | Degrade to Bounded behavior | Abort run |

---

## Determinism Guarantee

Given:
- Same input query
- Same policy memory snapshot (at run start)
- Same evidence availability

The system produces **identical outputs**.

Policy Memory updates happen AFTER the run, so they cannot affect the current run's determinism.

---

*Document Version: 1.0.0*
*Status: Design Only — No Implementation*
