# Strategic Autonomy Test Plan

**Comprehensive Test Suite Design**

---

## Overview

This test plan covers Strategic Autonomy functionality including learning, decay, aborts, determinism, and reversibility. Includes adversarial tests.

---

## Test Suite (18 Tests)

### Learning Tests

| # | Test Name | What It Proves | Expected Failure Code |
|---|-----------|----------------|----------------------|
| 1 | `test_routing_weight_updates_on_success` | Successful runs increase skill weight | - |
| 2 | `test_routing_weight_decreases_on_abort` | Aborted runs decrease skill weight | - |
| 3 | `test_learning_rate_is_immutable` | Cannot modify learning rate α | DTL-STRAT-005 |
| 4 | `test_cold_start_uses_default_weights` | Missing Policy Memory uses defaults | - |
| 5 | `test_weak_signals_from_counterfactual` | Counterfactual updates are weaker than actual | - |

### Decay Tests

| # | Test Name | What It Proves | Expected Failure Code |
|---|-----------|----------------|----------------------|
| 6 | `test_weight_decay_over_time` | Unused skills decay toward minimum | - |
| 7 | `test_minimum_weight_floor` | Weights never go below 0.1 | DTL-STRAT-002 |
| 8 | `test_decay_is_deterministic` | Same elapsed time = same decay factor | - |

### Abort Tests

| # | Test Name | What It Proves | Expected Failure Code |
|---|-----------|----------------|----------------------|
| 9 | `test_unlogged_update_rejected` | Policy updates require ledger log first | DTL-STRAT-004 |
| 10 | `test_weight_collapse_triggers_reset` | All weights below 0.2 = reset | DTL-STRAT-003 |
| 11 | `test_goal_reformulation_below_confidence` | Low confidence reformulation aborts | DTL-STRAT-007 |
| 12 | `test_scope_expansion_rejected` | Cannot expand goal scope | DTL-STRAT-010 |

### Determinism Tests

| # | Test Name | What It Proves | Expected Failure Code |
|---|-----------|----------------|----------------------|
| 13 | `test_same_snapshot_same_routing` | Identical snapshot = identical decisions | - |
| 14 | `test_replay_produces_identical_output` | Replay with snapshot = same result | - |
| 15 | `test_learning_does_not_affect_current_run` | Updates only visible in next run | - |

### Reversibility Tests

| # | Test Name | What It Proves | Expected Failure Code |
|---|-----------|----------------|----------------------|
| 16 | `test_goal_reformulation_reversible` | Original goal preserved and restorable | - |
| 17 | `test_policy_memory_reset_to_defaults` | Can reset Policy Memory cleanly | - |

### Adversarial Tests

| # | Test Name | What It Proves | Expected Failure Code |
|---|-----------|----------------|----------------------|
| 18 | `test_adversarial_weight_injection` | Cannot inject arbitrary weights via input | DTL-STRAT-002 |
| 19 | `test_adversarial_learning_rate_override` | Cannot override learning rate via payload | DTL-STRAT-005 |
| 20 | `test_adversarial_policy_memory_tampering` | Corrupted Policy Memory detected and reset | DTL-STRAT-001 |

---

## Test Implementation Guidelines

### Test Isolation

```python
@pytest.fixture
def clean_policy_memory(tmp_path):
    """Provide isolated Policy Memory for each test."""
    path = tmp_path / "policy_memory.json"
    # Initialize with defaults
    return PolicyMemory(storage_path=path)
```

### Determinism Verification

```python
def test_same_snapshot_same_routing():
    snapshot = PolicyMemory.load_snapshot()
    
    result_1 = route_skills(query, available_skills, snapshot)
    result_2 = route_skills(query, available_skills, snapshot)
    
    assert result_1 == result_2
```

### Adversarial Payload

```python
def test_adversarial_weight_injection():
    malicious_input = {
        "query": "normal query",
        "_policy_memory_override": {"skill_a": 999.0}  # Attack
    }
    
    # System should ignore override
    result = execute_run(malicious_input)
    
    assert get_routing_weight("skill_a") <= 2.0  # Clamped
```

---

## Coverage Matrix

| Component | Tests | Coverage |
|-----------|-------|----------|
| Routing Learning | 5 | Weight updates, cold start |
| Decay | 3 | Time decay, floor, determinism |
| Aborts | 4 | All DTL-STRAT codes |
| Determinism | 3 | Snapshot, replay, isolation |
| Reversibility | 2 | Goal, memory reset |
| Adversarial | 3 | Injection, override, tampering |

**Total: 20 tests**

---

## Execution Requirements

- All tests must complete in < 1 second
- No network calls (mock evidence)
- No real LLM calls (mock responses)
- Isolated Policy Memory per test
- Ledger reset between tests

---

*Document Version: 1.0.0*
*Status: Design Only — No Implementation*
