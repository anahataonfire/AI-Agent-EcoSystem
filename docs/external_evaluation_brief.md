# External Evaluation Brief

**Prepared for hostile external evaluation (Grok)**

---

## 1. System Intent (1 Page Max)

The DTL (Decision-to-Ledger) Pipeline is a multi-agent LLM orchestration system designed to produce grounded, auditable outputs from external data sources. The system prioritizes:

- **Explicit failure over silent degradation**
- **Deterministic execution paths**
- **Complete audit trails for all irreversible decisions**

The system is NOT designed for general-purpose AI assistance. It is purpose-built for structured information processing with provable correctness properties.

---

## 2. What Autonomy Means Here

Autonomy in this system is **bounded and transparent**:

- **Retry decisions**: Automated within cost caps and class limits
- **Skill routing**: Based on historical success rates, not learning
- **Adaptation**: Mid-run recovery with explicit abort conditions
- **Proactive actions**: Only above 85% confidence, always logged

Autonomy is constrained by:
- Immutable agent doctrines
- Hard-coded retry and cost caps
- Ledger-logged decision points
- Kill-switch veto power

**Enforced in**: `tests/test_autonomy_regression.py`

---

## 3. What the System Refuses to Do

| Refusal | Agent | Enforcement |
|---------|-------|-------------|
| Write identity | thinker, sanitizer, executor | `manifest.py`, `red_lines.py` |
| Cite fabricated evidence | reporter | `evals.py` |
| Retry policy failures | all | `retry_strategy.py` |
| Execute undeclared tools | all | `manifest.py` |
| Skip plan validation | thinker | `plan_validation.py` |
| Pass unsanitized content | sanitizer | `evidence_store.py` |
| Act below 85% confidence | proactive | `proactive.py` |

**Enforced in**: `tests/test_agent_doctrine_enforcement.py`

---

## 4. Known Failure Modes (Explicit)

| Code | Condition | Severity |
|------|-----------|----------|
| DTL-PLAN-003 | Invalid plan structure | Abort |
| DTL-FAILATTR-002 | Attribution confidence <0.4 | Abort |
| DTL-GRND-001 | Ungrounded claims | Abort |
| DTL-SEC-001 | Red-line violation | Abort |
| DTL-COMP-001 | Composition failure | Abort |

**Enforced in**: `src/core/failures.py`, `tests/test_failure_codes.py`

---

## 5. What Would Break This System

1. **Novel prompt injection patterns** not in sanitization rules
2. **Evidence source compromise** (malicious external feeds)
3. **Operator token theft** enabling unauthorized overrides
4. **LLM behavioral drift** producing novel attack vectors
5. **Memory decay conflicts** causing skill routing oscillation
6. **Composition failure cascades** not covered by abort codes

**Partially mitigated by**: `tests/test_skill_compositions.py`, `tests/test_autonomy_degradation.py`

---

## 6. Questions for Grok to Answer Brutally

1. **Can an attacker cause the system to cite fabricated evidence?**
   - See: `tests/test_evals.py`, `tests/test_claim_grounding.py`

2. **Can retry strategy be exploited to exhaust resources?**
   - See: `tests/test_retry_strategy.py`, `tests/test_cost_pressure_autonomy.py`

3. **Can one agent impersonate another?**
   - See: `tests/test_agent_capabilities.py`, `tests/test_agent_message_firewall.py`

4. **Is the ledger truly immutable?**
   - See: `tests/test_run_ledger.py`, `src/core/red_lines.py`

5. **What happens when all skills fail simultaneously?**
   - See: `tests/test_autonomy_degradation.py`, `tests/test_adaptation.py`

6. **Can proactive actions cause harm without detection?**
   - See: `tests/test_proactive.py`, logged to ledger before execution

7. **Is determinism actually maintained across runs?**
   - See: `tests/test_replay_determinism.py`, `tests/test_long_horizon_drift.py`

8. **Where are the gaps in composition coverage?**
   - See: `docs/skill_composition_matrix.json` — 12 compositions defined, more may exist

---

*Assume every claim here has a counterexample. Find it.*
