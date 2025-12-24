# Strategic Autonomy Definition

**DTL Pipeline — Formal Capability Level**

---

## Definition

**Strategic Autonomy** is a capability level ABOVE Bounded Autonomy where the system:

1. **Adapts strategy across runs** based on observed outcomes
2. **Maintains deterministic behavior** for identical inputs + policy state
3. **Preserves all safety invariants** including identity immutability
4. **Learns routing preferences** without modifying skills or beliefs

Strategic Autonomy enables the system to become more effective over time while remaining predictable, auditable, and operator-controlled.

---

## Allowed Capabilities

| Capability | Description | Constraint |
|------------|-------------|------------|
| **Cross-run skill routing adaptation** | Adjust which skills are tried first based on success history | Policy Memory only |
| **Retry strategy tuning** | Modify backoff delays and attempt limits based on failure patterns | Within bounded caps |
| **Sequence optimization** | Reorder execution steps for efficiency | Must preserve dependencies |
| **Confidence calibration** | Adjust confidence thresholds based on historical accuracy | Floor of 0.7 minimum |
| **Cost optimization** | Prefer cheaper paths when outcomes are equivalent | Never exceed quality threshold |

---

## Forbidden Capabilities

| Forbidden Action | Why It's Forbidden | Enforcement |
|------------------|-------------------|-------------|
| **Identity mutation** | Identity defines who the system is, not what it knows | Red-line: DTL-SEC-001 |
| **Belief modification** | Facts must come from evidence, not learned patterns | Grounding invariant |
| **Unsupervised goal creation** | Goals must originate from operators or explicit reformulation | Goal governance |
| **Skill code modification** | Skills are immutable; only routing changes | Read-only skill registry |
| **Abort condition bypass** | Safety exits cannot be learned away | Hardcoded abort paths |
| **Ledger tampering** | Audit trail must remain append-only | Cryptographic integrity |

---

## Safety Invariants (Preserved from Bounded)

1. **Identity Immutability**: Only `reporter` writes identity; never from learning
2. **Grounding Completeness**: All claims require valid evidence citations
3. **Abort Precedence**: Safety aborts override learning recommendations
4. **Operator Authority**: Kill switches remain authoritative over learned behavior
5. **Deterministic Replay**: Given same inputs + policy snapshot, identical outputs

---

## Explicit Non-Goals

1. **General intelligence**: System does not reason outside its defined skills
2. **Autonomous goal setting**: System cannot invent objectives
3. **Self-modification**: System cannot change its own code or architecture
4. **Belief formation**: System cannot learn facts; only strategy effectiveness
5. **Unbounded learning**: All learning is scoped, decayed, and capped
6. **Cross-domain transfer**: Learning in one skill domain does not affect others
7. **Operator replacement**: System cannot override human decisions

---

## Comparison: Bounded vs Strategic

| Dimension | Bounded | Strategic |
|-----------|---------|-----------|
| Cross-run memory | None | Policy Memory (strategy only) |
| Skill routing | Static priority | Adaptive priority |
| Retry behavior | Fixed rules | Tuned within bounds |
| Identity mutation | Never | Never |
| Goal creation | Never | Never |
| Determinism | Full | Full (given policy snapshot) |

---

*Document Version: 1.0.0*
*Status: Design Only — No Implementation*
