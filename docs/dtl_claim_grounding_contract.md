# DTL Claim Grounding Contract

**Version:** 1.0  
**Status:** ACTIVE  
**Last Updated:** 2025-12-23  

---

## 1. Scope

This contract governs how factual claims in all generated reports bind to evidence.

**Applies to:**
- Normal successful reports
- Reused reports (True Reuse path)
- Fallback/Metadata-Only summaries

---

## 2. Definitions

| Term | Definition |
|------|------------|
| **Claim** | Any factual assertion in the report body. |
| **Evidence Item** | A payload stored in Evidence Store with a unique ID (`ev_*` or `report:*`). |
| **Citation** | Explicit reference to an Evidence ID in the report. |
| **Ungrounded Claim** | A factual assertion lacking ≥1 citation. |

---

## 3. Hard Rules

> [!IMPORTANT]
> These rules are non-negotiable.

| # | Rule |
|---|------|
| 1 | Every factual claim **MUST** be supported by ≥1 Evidence ID. |
| 2 | Every Evidence ID cited **MUST** exist in Evidence Store. |
| 3 | Evidence IDs **MUST** appear verbatim (no paraphrased sources). |
| 4 | Claims without evidence are **PROHIBITED**. |

---

## 4. Formatting Contract

### Citation Syntax

```
[EVID:abc123def456]
```

- Prefix: `EVID:`
- ID: The exact Evidence Store ID (e.g., `ev_abc123def456`)
- Brackets: Square brackets `[ ]`

### Placement Rules

| Rule | Requirement |
|------|-------------|
| Proximity | Citation MUST appear in the same paragraph as the claim. |
| Multiplicity | Multiple citations allowed per claim. |
| Ordering | Citations appear at end of sentence, before punctuation. |

### Example

```markdown
Global tech stocks rose 3.2% [EVID:ev_abc123] following the Fed announcement [EVID:ev_def456].
```

---

## 5. Prohibited Behaviors

| # | Prohibition |
|---|-------------|
| 1 | No "general knowledge" claims without citation. |
| 2 | No synthesis across evidence without citing ALL sources. |
| 3 | No speculative language unless labeled `[SPECULATION]`. |
| 4 | No fabricated or hallucinated Evidence IDs. |
| 5 | No citation of deleted/missing evidence. |

---

## 6. Failure Handling

If grounding validation fails:

| Severity | Action |
|----------|--------|
| Missing citation for claim | Report generation **MUST** abort OR downgrade to "Unverified Summary". |
| Cited ID not in store | Remove claim OR abort. |
| Partial grounding | **PROHIBITED** — no silent omission. |

### Downgrade Label

If downgrading to unverified:

```markdown
> [!WARNING]
> This is an **Unverified Summary**. Claims may lack evidence grounding.
```

---

## 7. Reuse Interaction

| Scenario | Requirement |
|----------|-------------|
| True Reuse | Reused report **MUST** already satisfy this contract. |
| Retroactive grounding | **PROHIBITED** — cannot add citations post-hoc. |
| Stale evidence | If cited evidence expired/deleted, reuse MUST fail. |

---

## 8. Test References

| Test Suite | Coverage |
|------------|----------|
| `tests/test_claim_grounding.py` | *(Placeholder — to be implemented)* |
| [test_groundhog_reuse_safety.py](file:///Users/adamc/Documents/001%20AI%20Agents/AI%20Agent%20EcoSystem%202.0/tests/test_groundhog_reuse_safety.py) | Reuse validation |
| [test_identity_usage_behavior.py](file:///Users/adamc/Documents/001%20AI%20Agents/AI%20Agent%20EcoSystem%202.0/tests/test_identity_usage_behavior.py) | Behavioral compliance |

---

*End of Contract*
