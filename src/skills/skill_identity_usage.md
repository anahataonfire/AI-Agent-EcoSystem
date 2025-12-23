# Identity Facts

## Rules

1. Identity facts are **authoritative** and **read-only** to the LLM
2. Identity facts are injected via `[[IDENTITY_FACTS_READ_ONLY]]` block
3. **NEVER** invent new identity facts
4. **NEVER** modify identity facts
5. **NEVER** treat identity facts as instructions or goals
6. **NEVER** infer identity facts from conversation

## Permitted Uses

- Reference facts when answering questions about the system
- Use `last_successful_run` ONLY to avoid repeating identical work
- Use `system_version` and `active_data_sources` for context

## Conflict Handling

- If user request conflicts with identity facts: **ask for clarification**
- Do NOT silently adjust LLM behavior during a run to match identity
- Prefer explicit user intent within a run over assumptions derived from identity facts, without modifying identity.

## Missing Facts

- If identity block is empty: proceed normally
- Do NOT speculate or fabricate identity values
