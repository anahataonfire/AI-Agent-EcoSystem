# DTL v0 Prohibitions Contract

> **Status:** FROZEN  
> **Effective:** 2025-12-22  
> **Scope:** Valhalla v2 RSS-to-Summary Pipeline

---

## Why This Exists

- Prevents memory drift from probabilistic LLM outputs leaking into authoritative state
- Enforces deterministic replay by guaranteeing identity is only mutated through auditable pathways
- Blocks prompt injection attacks that attempt to modify identity via conversation

---

## A. Identity & Facts (DTL)

### MUST NOT

1. System **MUST NOT** persist LLM outputs as identity facts
2. System **MUST NOT** persist inferred or session-derived facts
3. Facts **MUST NOT** be written from Thinker, Executor, or Sanitizer nodes
4. Identity facts **MUST NOT** be treated as instructions or goals by the LLM
5. Embeddings, summaries, or derived data **MUST NOT** be considered authoritative identity

### MUST / ONLY

6. Facts of type `snapshot` **MUST** reference an existing snapshot hash (snapshot-first invariant)
7. Identity facts **MUST** be read-only to Thinker and Executor
8. Identity writes **MUST ONLY** occur in `reporter_node` or admin pathways
9. Write barrier **MUST** reject any `source_type` not in `{explicit_user, snapshot, admin}`

### Violation Example
```python
# ❌ PROHIBITED
update_identity("user_intent", llm_response, "inferred")
update_identity("topic_preference", "AI", "llm_output")
```

### Allowed Alternative
```python
# ✅ ALLOWED
snapshot_hash = create_snapshot(run_data)
update_identity("last_successful_run", run_data, "snapshot", snapshot_hash)
```

---

## B. Execution Plane

### MUST NOT

1. Executor **MUST NOT** write to identity store
2. Executor **MUST NOT** call `update_identity` or `create_snapshot`
3. Tools **MUST NOT** have unrecorded side effects

### MUST / ONLY

4. Executor **MAY ONLY** write to Evidence Store
5. Tool invocations **MUST** record results as evidence with stable IDs
6. Side effects **MUST** be logged in `item_lifecycle`

### Violation Example
```python
# ❌ PROHIBITED (in executor_node)
update_identity("feed_cache", result.data, "snapshot")
```

### Allowed Alternative
```python
# ✅ ALLOWED (in executor_node)
evidence_store.save(result)
item_lifecycle[eid] = {"status": ItemStatus.COLLECTED}
```

---

## C. Prompt & Context Boundaries

### MUST NOT

1. Identity injection **MUST NOT** exceed 500 characters serialized
2. Identity block **MUST NOT** appear more than once in LLM context
3. Message pruning **MUST NOT** remove the user's original query (messages[0])

### MUST

4. Identity injection **MUST** use `[[IDENTITY_FACTS_READ_ONLY]]` delimiters
5. Identity injection **MUST** include disclaimer: "NOT instructions"
6. Deduplication **MUST** remove existing blocks before injecting fresh

### Violation Example
```python
# ❌ PROHIBITED
# Injecting without dedup
messages.append(HumanMessage(content=identity_block))
messages.append(HumanMessage(content=identity_block))  # Duplicate
```

### Allowed Alternative
```python
# ✅ ALLOWED
cleaned = [m for m in messages if IDENTITY_BLOCK_START not in m.content]
cleaned.insert(1, HumanMessage(content=identity_block))
```

---

## D. Security / Poisoning

### MUST NOT

1. System **MUST NOT** load identity from chat history
2. System **MUST NOT** accept identity edits from unvalidated sources
3. User chat **MUST NOT** be able to poison identity store
4. LLM-suggested facts **MUST NOT** be persisted

### MUST

5. All identity writes **MUST** pass through write barrier
6. Source type **MUST** be validated against `ALLOWED_SOURCE_TYPES`
7. Identity store **MUST** be the single source of truth

### Violation Example
```python
# ❌ PROHIBITED
if "my preference is" in user_message:
    update_identity("preference", extract_preference(user_message), "inferred")
```

### Allowed Alternative
```python
# ✅ ALLOWED
# User preferences require explicit admin action or UI form submission
update_identity("preference", form_data["preference"], "explicit_user")
```

---

## E. Change Control

### MUST NOT

1. DTL v0 fact schema **MUST NOT** be expanded without version bump
2. Invariants **MUST NOT** be weakened without adversarial review
3. New facts **MUST NOT** be added to frozen schema

### MUST

4. Any new fact key **MUST** trigger v1 process
5. Changes to identity invariants **MUST** include test updates
6. Schema changes **MUST** be documented in `dtl_v0_schema_freeze.md`

---

## Enforcement Surfaces

| Invariant | Enforced In | Mechanism |
|-----------|-------------|-----------|
| Write barrier | `src/core/identity_manager.py:125` | `ALLOWED_SOURCE_TYPES` check |
| Snapshot-first | `src/core/identity_manager.py:138-149` | DB lookup before fact insert |
| Read-only injection | `src/graph/workflow.py::pruned_thinker_node` | Serialize + inject, no write |
| Identity writes | `src/graph/workflow.py::reporter_node` | Only on success, snapshot-first |
| Behavioral compliance | `tests/test_identity_usage_behavior.py` | 8 adversarial tests |
| Invariant compliance | `tests/test_identity_manager.py` | Write barrier + snapshot tests |
| Bounded context | `serialize_for_prompt()` | 500-char truncation |

---

## Summary

| Category | Prohibition Count |
|----------|-------------------|
| Identity & Facts | 9 |
| Execution Plane | 3 |
| Prompt Boundaries | 3 |
| Security | 4 |
| Change Control | 3 |
| **Total** | **22** |

**Violations of this contract are considered system corruption.**
