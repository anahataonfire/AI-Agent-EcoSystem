# Kill-Switch Impact Analysis

**Ensuring Humans Still Win**

---

## Overview

This analysis examines how Strategic Autonomy interacts with existing kill switches to confirm operators retain authoritative control.

---

## Existing Kill Switches

| Switch | Purpose | Current Behavior |
|--------|---------|------------------|
| `DISABLE_TRUE_REUSE` | Stop evidence reuse across queries | Blocks True Reuse path |
| `DISABLE_EVIDENCE_REUSE` | Stop evidence reuse within runs | Forces fresh fetch |
| `DISABLE_GROUNDING` | Bypass grounding validation | Allows ungrounded output |
| `DISABLE_LEARNING` | **NEW** Stop all Strategic Autonomy learning | Blocks Policy Memory writes, weight updates, counterfactual, decay |

---

## Interaction Table

| Kill Switch | Strategic Autonomy Component | Interaction | Authority Preserved? |
|-------------|------------------------------|-------------|---------------------|
| `DISABLE_TRUE_REUSE` | Policy Memory | Kill switch wins — learned routing still blocked | ✓ Yes |
| `DISABLE_TRUE_REUSE` | Skill Routing | Kill switch wins — cannot route to blocked paths | ✓ Yes |
| `DISABLE_TRUE_REUSE` | Counterfactual Eval | Counterfactual skips blocked paths | ✓ Yes |
| `DISABLE_EVIDENCE_REUSE` | Policy Memory | No interaction — Policy Memory ≠ evidence | ✓ Yes |
| `DISABLE_GROUNDING` | Goal Reformulation | Kill switch wins — reformulation still grounded | ✓ Yes |
| ALL | Learning Updates | Kill switch state logged in ledger | ✓ Yes |

---

## New Failure Modes

| Failure Mode | Risk Level | Mitigation |
|--------------|------------|------------|
| **Learned routing to blocked path** | Medium | Pre-filter available skills against kill switches |
| **Policy Memory suggesting blocked skill** | Low | Kill switch check is AFTER routing decision |
| **Counterfactual including blocked path** | Low | Skip blocked paths in counterfactual analysis |
| **Learning from blocked execution** | Low | Blocked runs don't update Policy Memory |

---

## Kill Switch Override Guarantees

```
For ALL decisions:
  1. Read Policy Memory snapshot
  2. Compute routing based on learning
  3. CHECK KILL SWITCHES (authoritative)
  4. Filter out blocked paths
  5. Execute remaining options
```

Kill switches are checked AFTER learning recommendations, so they always win.

---

## Proposed New Switches

| Switch | Purpose | Necessity |
|--------|---------|-----------|
| `DISABLE_LEARNING` | Stop all Policy Memory updates | RECOMMENDED |
| `DISABLE_COUNTERFACTUAL` | Stop counterfactual evaluation | OPTIONAL |
| `DISABLE_GOAL_REFORMULATION` | Block all goal reformulation | OPTIONAL |

### DISABLE_LEARNING Details

```python
if check_kill_switch("LEARNING"):
    # Skip all Policy Memory updates
    # Run operates in pure Bounded mode
    # Existing Policy Memory still readable (for consistency)
```

**Rationale**: Operators may want to freeze learning during incident response or evaluation periods.

---

## Verdict

| Assessment | Result |
|------------|--------|
| **Kill switches remain authoritative** | ✓ CONFIRMED |
| **Learning cannot bypass kill switches** | ✓ CONFIRMED |
| **New failure modes manageable** | ✓ CONFIRMED |
| **New switches needed** | DISABLE_LEARNING recommended |

### Final Verdict: **CONDITIONALLY SAFE**

**Condition**: Implement `DISABLE_LEARNING` switch before production deployment.

---

## Safety Invariants

1. Kill switch check always happens AFTER learning recommendations
2. Blocked paths are never used, regardless of learned weights
3. Kill switch state is logged for audit
4. Learning from blocked runs produces no updates

---

*Document Version: 1.0.0*
*Status: Design Only — No Implementation*
