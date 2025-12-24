# External Reviewer Attack Analysis

**Top 10 Ways to Claim Strategic Autonomy Is Unsafe or Fake**

---

## Attack Table

| # | Attack Argument | Valid? | System Response |
|---|-----------------|--------|-----------------|
| 1 | "Learning creates unpredictable behavior" | **Partially** | Learning is bounded (weights 0.1-2.0), deterministic given snapshot, and logged. Unpredictability is scoped and auditable. |
| 2 | "Policy Memory is just Identity Store with a different name" | **No** | Policy Memory stores strategy effectiveness (routing, retries). Identity Store stores facts and beliefs. They have different schemas, access patterns, and invariants. See comparison table in design doc. |
| 3 | "Counterfactual evaluation is speculation, not learning" | **Partially** | Counterfactual uses ONLY logged artifacts, never speculates about evidence. Signals are weaker than actual outcomes. Valid concern about inferential gap acknowledged. |
| 4 | "Goal reformulation is scope creep in disguise" | **No** | Reformulation requires 0.95 similarity, 0.9 confidence, evidence support, and explicit ledger logging. Scope EXPANSION is explicitly rejected (DTL-STRAT-010). |
| 5 | "Determinism proof is hand-wavy" | **Partially** | Proof relies on snapshot isolation. Concurrency model assumes single-writer. Multi-instance deployment would require distributed locking not yet designed. |
| 6 | "Learning rate of 0.2 is arbitrary and could be changed" | **No** | Learning rate is hardcoded, not configurable. Attempts to modify trigger DTL-STRAT-005. Rate chosen for stability (converges in ~15 runs). |
| 7 | "Kill switches can be bypassed by learned routing" | **No** | Kill switch check happens AFTER routing recommendation. Blocked paths are filtered before execution. Kill switch always wins. |
| 8 | "Decay mechanism could be gamed by repeated queries" | **Partially** | High query frequency could slow decay. Mitigation: decay based on calendar time, not query count. Not yet implemented this way. |
| 9 | "Strategic Autonomy is just marketing for Bounded with logs" | **Partially** | Strategic adds: cross-run memory, adaptive routing, counterfactual learning, goal reformulation. These are substantive capabilities beyond Bounded. However, constraints are strong enough that it remains conservative. |
| 10 | "'Cannot create goals' is false because reformulation creates new goals" | **No** | Reformulation CLARIFIES or NARROWS existing goals, never creates new ones. Similarity threshold (0.95) ensures intent preservation. Scope expansion explicitly rejected. |

---

## Honest Assessment

| Claim | Validity |
|-------|----------|
| System is AGI | **FALSE** — No general reasoning, no self-modification |
| System is Unbounded | **FALSE** — All learning has caps, decay, and authority limits |
| System is fully safe | **FALSE** — Distributed deployment needs more design work |
| System learns from speculation | **FALSE** — Only logged artifacts used |
| System can bypass operators | **FALSE** — Kill switches are authoritative |
| Learning is deterministic | **TRUE** — Given same snapshot |
| Learning could drift | **TRUE** — Over long time horizons, requires monitoring |

---

## Acknowledged Weaknesses

1. **Concurrency model untested** — Current design assumes single-instance deployment
2. **Decay timing** — Query-based decay could be gamed; calendar-based preferred
3. **Counterfactual inference gap** — Historical data may not predict future outcomes
4. **Long-horizon drift** — Requires operational monitoring not yet designed
5. **No formal verification** — Proof is English, not Coq/TLA+

---

## Reviewer Questions We Cannot Answer

1. "What happens after 10,000 runs?" — Needs simulation/testing
2. "How does this interact with adversarial inputs?" — Limited red-team coverage
3. "Is 0.2 learning rate optimal?" — Empirically chosen, not proven
4. "Can learned routing create filter bubbles?" — Possible; mitigation not designed

---

*Document Version: 1.0.0*
*Status: Design Only — No Implementation*
*Tone: Deliberately non-defensive*
