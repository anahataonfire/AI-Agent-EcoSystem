# Debugging Runbook

> 4-Phase systematic debugging methodology for DTL pipeline and runtime issues.

---

## Quick Reference

```
REPRODUCE → ISOLATE → UNDERSTAND → FIX & VERIFY
```

---

## Phase 1: Reproduce

**Before fixing, reliably reproduce the issue.**

### Reproduction Steps Template

```markdown
## Reproduction Steps
1. [Exact step to reproduce]
2. [Next step]
3. [Expected vs actual result]

## Reproduction Rate
- [ ] Always (100%)
- [ ] Often (50-90%)
- [ ] Sometimes (10-50%)
- [ ] Rare (<10%)
```

### For DTL Issues

1. Check `logs/` for recent run output
2. Identify the failing step (Strategist/Researcher/Reporter)
3. Run with `--mock` mode first to isolate LLM vs logic issues
4. Use `dtl run --job <job_name>` to reproduce specific flows

---

## Phase 2: Isolate

**Narrow down the source.**

### Isolation Questions

| Question | How to Check |
|----------|--------------|
| When did this start? | `git log --oneline -20` |
| What changed recently? | `git diff HEAD~5` |
| All environments? | Test mock vs live mode |
| Minimal reproduction? | Simplify inputs |
| Smallest triggering change? | Binary search commits |

### DTL-Specific Isolation

| Component | Check |
|-----------|-------|
| Firewall | `verify_routing.py` |
| Evidence Store | `tests/test_evidence_store.py` |
| CommitGate | Check prewrite files |
| Kill Switches | `config/kill_switches.json` |

---

## Phase 3: Understand

**Find root cause, not symptoms.**

### The 5 Whys

```markdown
1. Why: [First observation]
   ↓
2. Why: [Deeper reason]
   ↓
3. Why: [Still deeper]
   ↓
4. Why: [Getting closer]
   ↓
5. Why: [Root cause]
```

### Common DTL Root Causes

| Symptom | Common Root Cause |
|---------|------------------|
| "No evidence collected" | RSS feed 403/blocked |
| "Kill switch active" | `config/kill_switches.json` state |
| "CommitGate failed" | Prewrite not created or validation failed |
| "Routing failed" | Policy mismatch in `routing_policy.json` |
| "Empty report" | LLM context overflow or citation failure |

---

## Phase 4: Fix & Verify

**Fix and verify it's truly fixed.**

### Fix Verification Checklist

```markdown
- [ ] Bug no longer reproduces
- [ ] Related functionality still works
- [ ] No new issues introduced
- [ ] Test added to prevent regression
- [ ] Similar code checked for same issue
```

### DTL Verification Commands

```bash
# Run all tests
pytest tests/ -v

# Verify specific component
python verify_routing.py
python verify_live.py

# Run mock pipeline
python -m src.cli run --job daily_thesis --mock

# Check evidence integrity
pytest tests/test_claim_grounding.py -v
```

---

## Debugging Commands Quick Reference

```bash
# Recent git changes
git log --oneline -20
git diff HEAD~5

# Search for pattern in code
grep -r "errorPattern" --include="*.py" src/

# Check logs
tail -100 logs/dtl_*.log

# Find files changed today
find . -mtime 0 -type f -name "*.py"
```

---

## Anti-Patterns (AVOID)

| ❌ Don't | ✅ Do |
|----------|-------|
| Random changes | Follow 4 phases |
| "Maybe if I change this..." | Reproduce first |
| Ignoring evidence | Log everything |
| Assuming without proof | Use 5 Whys |
| Stopping at symptoms | Find root cause |

---

## Escalation

If after 30 minutes you cannot identify root cause:

1. Document what you've tried
2. Capture all relevant logs
3. Create minimal reproduction case
4. Review with fresh perspective (take break)
5. Consider reverting recent changes
