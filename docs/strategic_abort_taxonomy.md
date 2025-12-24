# Strategic Abort Taxonomy

**Failure Codes for Strategic Autonomy**

---

## Overview

This taxonomy extends the DTL failure code system to cover Strategic Autonomy failures. Each code maps to a single invariant violation and explicitly halts LEARNING, not necessarily execution.

---

## New Category: DTL-STRAT-*

| Code | Name | Trigger | Severity | Halts |
|------|------|---------|----------|-------|
| **DTL-STRAT-001** | Policy Memory Corruption | Schema validation failure on policy file | CRITICAL | Learning |
| **DTL-STRAT-002** | Weight Bound Violation | Routing weight outside [0.1, 2.0] | WARNING | Learning for skill |
| **DTL-STRAT-003** | Total Weight Collapse | All weights below 0.2 | CRITICAL | Learning, reset |
| **DTL-STRAT-004** | Unlogged Learning Update | Policy update attempted without ledger log | CRITICAL | Learning |
| **DTL-STRAT-005** | Learning Rate Mutation | Attempt to modify learning rate | CRITICAL | Learning |
| **DTL-STRAT-006** | Counterfactual Ledger Corruption | Integrity check failure during counterfactual eval | CRITICAL | Learning |
| **DTL-STRAT-007** | Low Confidence Reformulation | Goal reformulation confidence < 0.9 | WARNING | Reformulation |
| **DTL-STRAT-008** | Intent Drift | Reformulation similarity < 0.95 | WARNING | Reformulation |
| **DTL-STRAT-009** | Ungrounded Reformulation | Goal reformulation without evidence support | WARNING | Reformulation |
| **DTL-STRAT-010** | Scope Expansion | Reformulation expands original goal | WARNING | Reformulation |
| **DTL-STRAT-011** | Unlogged Reformulation | Reformulation executed before ledger log | CRITICAL | Execution |
| **DTL-STRAT-012** | Circular Learning | Same decision repeated 3+ times despite failures | WARNING | Learning for context |

---

## Failure Details

### DTL-STRAT-001: Policy Memory Corruption

**Trigger**: Policy Memory file fails JSON schema validation or has invalid data types.

**Invariant Violated**: Policy Memory integrity

**Response**:
1. Log error to run ledger
2. Reset Policy Memory to defaults
3. Continue run with Bounded Autonomy behavior
4. Queue corruption for operator review

---

### DTL-STRAT-002: Weight Bound Violation

**Trigger**: Routing weight calculated outside [0.1, 2.0] range.

**Invariant Violated**: Bounded learning

**Response**:
1. Clamp weight to valid range
2. Log warning to run ledger
3. Continue run
4. Flag skill for review

---

### DTL-STRAT-003: Total Weight Collapse

**Trigger**: Sum of all routing weights falls below critical threshold.

**Invariant Violated**: System functionality

**Response**:
1. Log critical error
2. Reset all weights to 1.0
3. Continue run
4. Queue for operator review

---

### DTL-STRAT-004: Unlogged Learning Update

**Trigger**: Policy Memory update attempted without prior ledger entry.

**Invariant Violated**: Audit completeness

**Response**:
1. Reject the update
2. Preserve previous state
3. Log violation to run ledger
4. Continue run without learning for this update

---

### DTL-STRAT-005: Learning Rate Mutation

**Trigger**: Code attempts to change the learning rate (α).

**Invariant Violated**: Algorithm immutability

**Response**:
1. Reject the change
2. Log critical error
3. Use hardcoded learning rate
4. Queue security review

---

### DTL-STRAT-006: Counterfactual Ledger Corruption

**Trigger**: Run ledger fails integrity check during counterfactual evaluation.

**Invariant Violated**: Audit integrity

**Response**:
1. Abort counterfactual evaluation
2. Log critical error
3. Skip Policy Memory updates for this run
4. Continue execution (learning fails gracefully)

---

## Severity Definitions

| Severity | Meaning | Learning Impact |
|----------|---------|-----------------|
| **CRITICAL** | Invariant violation that could corrupt system | Halt all learning |
| **WARNING** | Constraint violation that is recoverable | Halt specific learning path |
| **INFO** | Unusual condition worth logging | No impact on learning |

---

## Key Principle

> Learning failures NEVER halt execution. The system degrades gracefully to Bounded Autonomy behavior.

---

*Document Version: 1.0.0*
*Status: Design Only — No Implementation*
