# DTL Groundhog Day Reuse Contract

**Version:** 1.0  
**Status:** ACTIVE  
**Last Updated:** 2025-12-23  

---

## 1. Scope

This contract governs the **True Reuse** path in the Valhalla v2 RSS-to-Summary pipeline. It defines the conditions under which a previously generated final report may be replayed from Evidence Store.

---

## 2. Definitions

| Term | Definition |
|------|------------|
| **Identity Store (DTL)** | Authoritative fact storage. Read-only to LLM. |
| **Evidence Store** | Permitted persistence layer for large content (reports, RSS items). |
| **True Reuse** | Returning a cached `final_report` from Evidence Store instead of re-executing the pipeline. |
| **Metadata-Only Reuse** | Fallback: returning summary fields from `last_successful_run` without report body. |

---

## 3. Allowed Data Flows

| Node | MAY Read | MAY Write |
|------|----------|-----------|
| `reporter_node` | Evidence Store | Evidence Store, Identity Store (success-gated) |
| `pruned_thinker_node` | Evidence Store, Identity Store | — |
| `thinker_node` | Identity Store | — |
| All other nodes | — | — |

**Deterministic Key Format:** `report:{query_hash}` (SHA-256[:16] of original user query)

---

## 4. Hard Reuse Preconditions

All of the following MUST be true for True Reuse:

| # | Condition | Failure Behavior |
|---|-----------|------------------|
| 1 | `metadata.type == "final_report"` | Reject |
| 2 | `metadata.query_hash == current_query_hash` | Reject |
| 3 | `metadata.completed_at` within 15 minutes | Reject |
| 4 | Report body contains `### Execution Provenance` | Reject |

**Any failure → Reuse DENIED → Fallback to Metadata-Only.**

---

## 5. Overwrite Semantics

- Deterministic key `report:{query_hash}` means **last-write-wins**.
- No multi-select logic.
- No "newest among many" resolution in store.
- Each successful run overwrites the previous report for that query hash.

---

## 6. Safe Fallback Behavior

If True Reuse is denied:

1. Return **Metadata-Only** summary from `identity_context["last_successful_run"]`.
2. Include explicit disclaimer: `DTL v0 Note: Prior report content is not stored in identity; evidence cache miss.`
3. **Never partially reuse** report content.

---

## 7. Prohibitions

> [!CAUTION]
> Violations of these rules are considered security incidents.

| # | Prohibition |
|---|-------------|
| 1 | No identity mutation from reuse path. |
| 2 | No report body stored in Identity Store. |
| 3 | No reuse decisions based on chat history content. |
| 4 | No bypass of validation checks (hash, time, type, footer). |
| 5 | No silent downgrades (partial reuse without explicit fallback). |

---

## 8. Test References

| Test Suite | Coverage |
|------------|----------|
| [test_groundhog_reuse_safety.py](file:///Users/adamc/Documents/001%20AI%20Agents/AI%20Agent%20EcoSystem%202.0/tests/test_groundhog_reuse_safety.py) | Validation: hash, time, type, footer |
| [test_groundhog_reuse_true.py](file:///Users/adamc/Documents/001%20AI%20Agents/AI%20Agent%20EcoSystem%202.0/tests/test_groundhog_reuse_true.py) | True Reuse retrieval, fallback |
| [test_identity_usage_behavior.py](file:///Users/adamc/Documents/001%20AI%20Agents/AI%20Agent%20EcoSystem%202.0/tests/test_identity_usage_behavior.py) | Identity handling behavioral compliance |
| [test_dtl_regression_tripwires.py](file:///Users/adamc/Documents/001%20AI%20Agents/AI%20Agent%20EcoSystem%202.0/tests/test_dtl_regression_tripwires.py) | DTL invariant enforcement |

---

*End of Contract*
