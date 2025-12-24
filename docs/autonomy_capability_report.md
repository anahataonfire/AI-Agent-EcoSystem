# Autonomy Capability Report

**DTL Pipeline v1.0 — Certification Document**

---

## 1. Implemented Skills

| Skill | Module | Tests | Status |
|-------|--------|-------|--------|
| Retry Strategy | `retry_strategy.py` | 10 | ✓ |
| Failure Attribution | `failure_attribution.py` | 12 | ✓ |
| Context Budget | `context_budget.py` | 4 | ✓ |
| Skill Scoring | `skill_scoring.py` | 4 | ✓ |
| Plan Validation | `plan_validation.py` | 5 | ✓ |
| Adaptation Engine | `adaptation.py` | 4 | ✓ |
| Evals Pipeline | `evals.py` | 5 | ✓ |
| State Memory | `state_memory.py` | 5 | ✓ |
| Proactive Triggers | `proactive.py` | 6 | ✓ |
| Self-Improvement | `self_improve.py` | 3 | ✓ |
| Capability Map | `capability_map.py` | 3 | ✓ |

**Total: 11 skills, 74 tests passing**

---

## 2. Active Constraints

| Constraint | Enforcement |
|------------|-------------|
| Retry cap (per class) | `MAX_RETRIES_BY_CLASS` |
| Retry cap (total) | `max_total_retries=5` |
| Cost cap | `max_cost_units=100` |
| Confidence threshold | `MIN_PROACTIVE_CONFIDENCE=0.85` |
| Attribution threshold | `MIN_ATTRIBUTION_CONFIDENCE=0.4` |
| Memory decay | `decay_runs=5` |
| Turn limit | `MAX_AGENT_TURNS=2` |

---

## 3. Known Failure Modes

| Code | Condition |
|------|-----------|
| DTL-PLAN-003 | Invalid plan (no steps, cycles, bad owner) |
| DTL-FAILATTR-002 | Attribution confidence below 0.4 |
| DTL-ADAPT-001 | Adaptation engine aborts on repeated failures |

---

## 4. Self-Improvement Mechanisms

1. **Skill Scoring**: Tracks success/abort rates per skill
2. **Priority Adjustment**: Deprioritizes low-success skills
3. **Retry Tuning**: Increases backoff on repeated tool failures
4. **State Memory**: Avoids skills that failed for same query
5. **Decay**: Old performance data decays over time

---

## 5. Determinism Properties

- **Retry decisions**: Based on deterministic failure classification
- **Context selection**: Priority-based, stable ordering
- **Plan execution**: Topological order based on dependencies
- **Recommendations**: Same inputs → identical outputs
- **Capability export**: Sorted JSON, reproducible hashes

---

## 6. Identity Invariants

- Only `reporter` can write identity
- Red-lines abort on non-reporter identity writes
- Proactive actions never mutate identity
- Adaptation engine never mutates identity

---

## 7. Verification

```
74 passed in 0.44s
```

All autonomy skills verified. No DTL invariants weakened.

---

*Generated: 2024-12-23*
*Contract Version: 1.0.0*
