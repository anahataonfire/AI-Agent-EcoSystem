---
name: dtl-patterns
description: DTL v2.0 pipeline patterns and debugging. Use when working with the DTL orchestrator, control plane, or agent coordination.
allowed-tools: Read, Glob, Grep
---

# DTL Patterns

> Domain-specific patterns for the DTL (Data/Think/Learn) v2.0 pipeline.

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DTL v2.0 Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│  Step 1  │  Step 2   │  Step 3      │  Step 4-6  │  Step 7-8  │
│  Policy  │  Manifests│  Kill Switch │  Agents    │  CommitGate│
│  Load    │  Load     │  Enforce     │  Execute   │  & Write   │
└──────────┴───────────┴──────────────┴────────────┴────────────┘
            ↓           ↓               ↓            ↓
         Firewall    Firewall       Firewall    CommitGate
         (Schema)   (Schema)       (Schema)    (7 Checks)
```

---

## Core Patterns

### 1. Deterministic Timestamps

**Pattern:** Mint `run_ts` ONCE at pipeline start, pass to all agents.

```python
# ✅ CORRECT - Single source of truth
config = RunConfig.create()  # run_ts minted here
agent.process(run_id=config.run_id, run_ts=config.run_ts)

# ❌ WRONG - Multiple timestamps
agent.process(run_ts=datetime.now().isoformat())  # Different per agent!
```

### 2. Envelope Wrapping

**Pattern:** All agent outputs wrapped in ProposalEnvelope.

```python
return self.wrap_output(
    payload={'result': data},
    capability_claims=['read_evidence', 'write_report']
)
```

### 3. Firewall Before Forward

**Pattern:** Validate envelope before passing to next agent.

```python
result = self.firewall.validate(envelope.to_dict(), 'proposal_envelope')
if not result.valid:
    # Enter degraded mode, do not forward
    self.degraded_controller.enter_degraded_mode(...)
    return None
```

### 4. Prewrite Lifecycle

**Pattern:** Only create prewrite after eligibility check.

```python
# Step 7a: Check eligibility FIRST
eligibility = commit_gate.validate_prewrite_eligibility(bundle, ...)
if not eligibility.accepted:
    return  # No prewrite created

# Step 7b: Create prewrite (now safe)
prewrite_path = commit_gate.create_prewrite(bundle)

# Step 7c: Full validation
result = commit_gate.validate(bundle, ...)

# Step 7d: Promote or delete
if result.accepted:
    commit_gate.promote_to_committed(bundle)
else:
    commit_gate.delete_prewrite(bundle)  # Clean up
```

### 5. Capability Claims

**Pattern:** Agents declare capabilities, manifests enforce limits.

```python
# In agent .skill.md
allowed:
  - read_evidence
  - write_report

# In agent code
capability_claims=['read_evidence', 'write_report']

# CommitGate checks
if claim not in manifest_capabilities[agent_id]:
    reject("CAPABILITY_DENIED")
```

---

## Control Plane Integration

### Kill Switch Pattern

```python
result = kill_switch_enforcer.enforce(['run_agents', 'write_evidence'])
if not result.can_proceed:
    log(f"Blocked: {result.blocked_operations}")
    return False
```

### Degraded Mode Pattern

```python
# Check before writes
if not degraded_controller.can_write():
    return {'success': False, 'reason': 'DEGRADED_MODE'}

# Enter degraded mode on failures
degraded_controller.enter_degraded_mode(
    run_id, run_ts, TriggerCondition.COMMIT_GATE_REJECTION, details
)
```

---

## Debugging Patterns

### Issue Localization

| Symptom | Likely Step | Debug Command |
|---------|-------------|---------------|
| "Policy not loaded" | Step 1 | Check `config/adk_determinism.json` |
| "Manifest missing" | Step 2 | Check `src/agents/*.skill.md` |
| "Kill switch active" | Step 3 | Check `config/kill_switches.json` |
| "Envelope rejected" | Step 4-6 | Check `config/schemas/` |
| "CommitGate failed" | Step 7 | Check prewrite validation |
| "Writes blocked" | Step 8 | Check `DegradedModeController` |

### 5 Whys Template

```
Why: [Observation]
→ Why: [Deeper]
  → Why: [Still deeper]
    → Why: [Getting close]
      → Why: [Root cause]
```

---

## Anti-Patterns

| ❌ Anti-Pattern | ✅ Correct Pattern |
|-----------------|-------------------|
| Minting timestamps in agents | Use orchestrator's run_ts |
| Skipping firewall validation | Always validate between hops |
| Creating prewrite before eligibility | Check eligibility first |
| Catching and ignoring errors | Fail-secure, enter degraded mode |
| Hardcoding capabilities | Declare in manifest |
