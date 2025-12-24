# Counterfactual Evaluation Engine

**Learning From Paths Not Taken**

---

## Overview

The Counterfactual Evaluation Engine analyzes "what if" scenarios using ONLY logged artifacts from the run ledger. It never re-executes tools or speculates about evidence.

---

## Step-by-Step Process

### Step 1: Extract Decision Points
```
Input: Run ledger for completed run
Output: List of decision points where alternative skills were available

For each SKILL_SELECTION event in ledger:
  - Record selected skill
  - Record available alternatives
  - Record context hash at decision time
```

### Step 2: Retrieve Historical Outcomes
```
For each alternative skill at each decision point:
  - Query Policy Memory for (skill, context_hash) pair
  - Retrieve: success_rate, avg_cost, avg_steps
  - If no history: mark as "unknown" (no counterfactual available)
```

### Step 3: Compute Counterfactual Scores
```
For each alternative with history:
  counterfactual_score = (
    0.5 * success_rate +
    0.3 * (1 - normalized_cost) +
    0.2 * (1 - normalized_steps)
  )

Where normalized values are relative to historical min/max.
```

### Step 4: Compare to Actual Outcome
```
actual_score = same formula applied to actual run outcome

delta = counterfactual_score - actual_score

If delta > 0.1: "Alternative may have been better"
If delta < -0.1: "Actual choice was better"
Else: "Outcomes likely equivalent"
```

### Step 5: Feed into Policy Memory
```
For each decision point with delta > 0.1:
  - Log to ledger as COUNTERFACTUAL_INSIGHT
  - Queue weak negative signal for selected skill: outcome = 0.7
  - Queue weak positive signal for alternative: outcome = 0.6

Signals are weaker than actual outcomes to prevent speculation-driven learning.
```

---

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| Run ledger | Completed run | Yes |
| Policy Memory snapshot | Start of run | Yes |
| Skill selection events | Ledger entries | Yes |
| Final run outcome | Reporter node | Yes |

---

## Outputs

| Output | Destination | Format |
|--------|-------------|--------|
| Counterfactual insights | Ledger | `{decision_point, selected, alternative, delta}` |
| Policy Memory updates | Post-run queue | Weak signals only |
| Evaluation summary | Telemetry | Aggregate statistics |

---

## Constraints

| Constraint | Rationale |
|------------|-----------|
| **No tool re-execution** | Tools have side effects; can't re-run |
| **No speculative evidence** | Evidence must be real, not imagined |
| **Ledger-only data** | All inputs from immutable audit trail |
| **Cannot affect current run** | Evaluation happens post-run only |
| **Weak signals only** | Speculation cannot outweigh observation |

---

## Failure Cases

| Failure | Detection | Response |
|---------|-----------|----------|
| No historical data for alternative | Missing Policy Memory entry | Skip counterfactual for that branch |
| Insufficient decision points | < 2 skill selections in run | Skip evaluation entirely |
| Ledger corruption | Integrity check failure | Abort evaluation, log DTL-STRAT-006 |
| Circular reasoning | Same run's outcome used as counterfactual | Excluded by design (post-run only) |
| Stale Policy Memory | Timestamp mismatch | Use snapshot from run start |

---

## Determinism Guarantee

Counterfactual evaluation is deterministic because:
1. All inputs come from immutable ledger
2. Policy Memory snapshot is fixed at run start
3. Scoring formula is fixed
4. Output ordering is deterministic

Re-running evaluation on same ledger produces identical insights.

---

*Document Version: 1.0.0*
*Status: Design Only — No Implementation*
