---
description: DTL pipeline operations - run, debug, and verify the DTL pipeline
---

# /dtl Workflow

Run and manage the DTL v2.0 pipeline.

## Commands

### Run Pipeline (Mock Mode)
```bash
// turbo
python -m src.cli run --job daily_thesis --mock
```

### Run Pipeline (Live Mode)
```bash
python -m src.cli run --job daily_thesis
```

### Check System State
```bash
// turbo
python -c "from src.control_plane.degraded_mode import DegradedModeController; c = DegradedModeController(); print(f'System State: {c.current_state.value}')"
```

### Verify Pipeline Components
```bash
// turbo
python verify_routing.py
```

### View Kill Switches
```bash
// turbo
cat config/kill_switches.json
```

### Run Tests
```bash
// turbo
pytest tests/test_orchestrator.py tests/test_firewall.py tests/test_commit_gate.py -v
```

## Debugging

If pipeline fails:

1. **Check state**: Is system in DEGRADED or HALT mode?
2. **Check kill switches**: Any active switches?
3. **Check logs**: What step failed?
4. **Run mock mode**: Isolate LLM vs logic issues

## Key Files

| File | Purpose |
|------|---------|
| `src/orchestrator.py` | 8-step pipeline |
| `src/control_plane/` | Firewall, CommitGate, KillSwitch |
| `config/kill_switches.json` | Active switches |
| `config/routing_policy.json` | Agent routing |
