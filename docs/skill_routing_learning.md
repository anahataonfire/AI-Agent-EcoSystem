# Skill Routing Learning Loop

**Adaptive Routing Without Skill Modification**

---

## Overview

The Skill Routing Learning Loop adjusts which skills are tried first based on historical success rates. It NEVER modifies the skills themselves — only the order in which they are attempted.

---

## Algorithm Description

### Update Rule (Exponential Moving Average)

```
new_weight = α * observed_outcome + (1 - α) * old_weight

Where:
- α = 0.2 (learning rate)
- observed_outcome = 1.0 for success, 0.0 for abort, 0.5 for partial
- old_weight = previous routing weight for skill
- Weights clamped to [0.1, 2.0]
```

### Routing Probability

```
P(skill_i) = weight_i / Σ(all weights)
```

Selection is deterministic given the weights: highest weight skill is tried first, then second-highest, etc.

---

## Cold-Start Behavior

| Condition | Behavior |
|-----------|----------|
| No policy memory | All skills have weight = 1.0 |
| Skill not in memory | Use default weight = 1.0 |
| First run ever | Pure Bounded Autonomy behavior |
| Memory reset | Graceful degradation to defaults |

---

## Degeneration Prevention

| Risk | Prevention |
|------|------------|
| **Runaway bias** | Weights clamped to [0.1, 2.0] |
| **Starvation** | Minimum weight 0.1 ensures all skills get tried |
| **Oscillation** | Low learning rate (α=0.2) dampens swings |
| **Echo chamber** | Decay factor reduces old successes over time |
| **Cold skill lock** | Random exploration 5% of runs |

---

## Example: 3 Skills Over 5 Runs

### Initial State
| Skill | Weight | P(first) |
|-------|--------|----------|
| skill_a | 1.0 | 33% |
| skill_b | 1.0 | 33% |
| skill_c | 1.0 | 33% |

### Run 1: skill_a succeeds
```
new_weight_a = 0.2 * 1.0 + 0.8 * 1.0 = 1.0 (no change, already max outcome)
```
| Skill | Weight | P(first) |
|-------|--------|----------|
| skill_a | 1.0 | 33% |
| skill_b | 1.0 | 33% |
| skill_c | 1.0 | 33% |

### Run 2: skill_b aborts
```
new_weight_b = 0.2 * 0.0 + 0.8 * 1.0 = 0.8
```
| Skill | Weight | P(first) |
|-------|--------|----------|
| skill_a | 1.0 | 37% |
| skill_b | 0.8 | 30% |
| skill_c | 1.0 | 37% |

### Run 3: skill_a succeeds again
```
new_weight_a = 0.2 * 1.0 + 0.8 * 1.0 = 1.0
```
(skill_a now tried first more often)

### Run 4: skill_c succeeds
```
new_weight_c = 0.2 * 1.0 + 0.8 * 1.0 = 1.0
```

### Run 5: skill_b aborts again
```
new_weight_b = 0.2 * 0.0 + 0.8 * 0.8 = 0.64
```

### Final State
| Skill | Weight | P(first) |
|-------|--------|----------|
| skill_a | 1.0 | 38% |
| skill_b | 0.64 | 24% |
| skill_c | 1.0 | 38% |

skill_b is now deprioritized but still available.

---

## Abort Conditions

| Condition | Code | Behavior |
|-----------|------|----------|
| Weight goes negative | DTL-STRAT-002 | Clamp to 0.1, log error |
| All weights below 0.2 | DTL-STRAT-003 | Reset to defaults |
| Update without ledger log | DTL-STRAT-004 | Reject update, preserve old state |
| Learning rate modified | DTL-STRAT-005 | Reject (α is immutable) |

---

## Invariants Preserved

1. **Skills unchanged**: Learning only affects routing order
2. **Abort conditions unchanged**: All hardcoded aborts remain in effect
3. **Determinism**: Given same weights, same routing decision
4. **Operator override**: Kill switches bypass learned routing

---

*Document Version: 1.0.0*
*Status: Design Only — No Implementation*
