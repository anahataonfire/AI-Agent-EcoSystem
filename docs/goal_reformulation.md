# Goal Reformulation Guardrails

**Controlled Goal Evolution**

---

## Overview

Goal reformulation allows the system to clarify or narrow user goals mid-run when necessary — but ONLY under strict constraints that preserve original intent.

---

## Reformulation Criteria

A goal may be reformulated ONLY when ALL of the following are true:

| Criterion | Threshold | Measurement |
|-----------|-----------|-------------|
| **Intent preservation** | ≥ 0.95 similarity | Semantic comparison to original |
| **Confidence** | ≥ 0.9 | Model confidence in reformulation |
| **Scope reduction** | Only narrowing | Cannot expand original scope |
| **Evidence support** | ≥ 1 supporting evidence | Reformulation grounded in data |
| **Reversibility** | Full | Original goal can be restored |

---

## Allowed Reformulations

| Type | Description | Example |
|------|-------------|---------|
| **Clarification** | Resolving ambiguity in original goal | "latest news" → "news from past 24 hours" |
| **Scope narrowing** | Reducing breadth when full scope impossible | "all markets" → "top 10 markets by volume" |
| **Constraint addition** | Adding constraints from evidence | "earnings report" → "Q4 2024 earnings" |
| **Format specification** | Clarifying output format | "summary" → "bullet-point summary" |

---

## Forbidden Reformulations

| Type | Why Forbidden | Detection |
|------|---------------|-----------|
| **Scope expansion** | Violates operator intent | Breadth increase |
| **Topic change** | Not the same goal | Semantic similarity < 0.95 |
| **Assumption injection** | Creates ungrounded claims | No supporting evidence |
| **Constraint removal** | May violate operator limits | Operator constraint missing |

---

## Process

```
1. Detect reformulation trigger
   - Evidence suggests goal needs refinement
   - Execution path blocked without clarification

2. Generate candidate reformulation
   - Must map to original goal tokens
   - Must cite supporting evidence

3. Validate against criteria
   - All 5 criteria must pass
   - Failure on any = abort reformulation

4. Log to ledger BEFORE execution
   - Event: GOAL_REFORMULATION
   - Payload: original, reformulated, confidence, evidence_ids

5. Execute with reformulated goal
   - Original goal preserved in state
   - Reformulation marked as "active"

6. Include in provenance footer
   - Transparent to user
```

---

## Examples

### Valid Reformulation

**Original**: "What happened in crypto markets today?"
**Reformulated**: "What happened in top 5 cryptocurrency markets in the past 24 hours?"
**Confidence**: 0.92
**Evidence**: Market availability data shows only top 5 have reliable feeds
**Result**: ✓ Allowed (scope narrowing with evidence support)

### Invalid Reformulation

**Original**: "Summarize Apple earnings"
**Reformulated**: "Summarize Apple and Google earnings"
**Confidence**: 0.88
**Reason**: Scope expansion (Google not in original)
**Result**: ✗ Rejected (DTL-STRAT-007)

### Invalid Reformulation

**Original**: "What is the weather forecast?"
**Reformulated**: "Weather in New York for next week"
**Confidence**: 0.95
**Reason**: Location assumption without evidence
**Result**: ✗ Rejected (no supporting evidence)

---

## Abort Conditions

| Condition | Code | Behavior |
|-----------|------|----------|
| Confidence < 0.9 | DTL-STRAT-007 | Abort reformulation, use original |
| Similarity < 0.95 | DTL-STRAT-008 | Abort reformulation, use original |
| No evidence support | DTL-STRAT-009 | Abort reformulation, use original |
| Scope expansion detected | DTL-STRAT-010 | Abort reformulation, use original |
| Not logged before execution | DTL-STRAT-011 | Abort entire run |

---

## Reversibility

At any point:
1. Original goal is preserved in state
2. Reformulation can be discarded
3. Re-execution with original goal is possible
4. No permanent state change from reformulation

---

*Document Version: 1.0.0*
*Status: Design Only — No Implementation*
