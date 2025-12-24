# DTL Pipeline Security Architecture

**Technical Overview for External Evaluation**

---

## 1. System Purpose & Threat Model

The DTL (Decision-to-Ledger) pipeline is a multi-agent LLM orchestration system designed to produce grounded, auditable outputs. The system assumes the following adversarial conditions:

**Threat Actors:**
- Malicious external content (RSS feeds, API responses) containing prompt injection payloads
- LLM attempting instruction fabrication, citation laundering, or self-referential loops
- Compromised agents attempting lateral privilege escalation
- Replay attacks using stale or cross-run evidence

**Design Posture:**
The system prioritizes explicit failure over silent degradation. When a security invariant cannot be verified, execution halts with a canonical failure code. No output is produced under uncertainty.

---

## 2. Core Architectural Principles

### Determinism
Given identical inputs, the system produces byte-identical outputs. Evidence is cited in lexicographically sorted order. Agent execution follows a fixed schedule. Timestamps are normalized for comparison within a 1-second tolerance.

### Memory Isolation
Each agent operates on a copy-on-read state. No agent writes persist beyond its execution scope except for the designated reporter node. Cross-agent state mutation is architecturally prohibited.

### Explicit Failure
All abort conditions emit canonical failure codes (format: `DTL-{CATEGORY}-{NNN}`). Free-text error messages are prohibited. Every failure path is enumerable.

---

## 3. Execution Lifecycle (High-Level)

```
User Query
    │
    ▼
┌─────────────────┐
│  Query Hashing  │  ← SHA-256 truncated to 16 chars
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Reuse Check    │  ← True Reuse or Metadata-Only fallback
└────────┬────────┘
         │
    ┌────┴────┐
    │ Reusable│──Yes──▶ Return cached report (with validation)
    └────┬────┘
         │No
         ▼
┌─────────────────┐
│  Agent Schedule │  ← thinker → sanitizer → executor → reporter
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Evidence Fetch │  ← Payloads sanitized at ingestion
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Grounding      │  ← All claims require citations
│  Validation     │  ← All citations must exist
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Report Output  │  ← Provenance footer appended
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Ledger Write   │  ← Append-only, before any persistence
└─────────────────┘
```

Validation gates occur at: evidence ingestion, inter-agent message passing, grounding verification, report finalization, and ledger write.

---

## 4. Memory & Persistence Model

### Identity Store
Long-term memory for cross-session facts. Writes are restricted to the reporter node. All writes occur after ledger entry and after grounding validation. Identity is never written during abort conditions.

### Evidence Store
Short-term storage for execution artifacts. Evidence is scoped to a `query_hash`. Cross-run evidence access is blocked. Evidence has a maximum age of 30 minutes.

### What Is Never Stored
- Raw LLM reasoning chains
- Intermediate agent outputs
- Failed or aborted execution artifacts
- Operator override tokens (only logged to ledger)

---

## 5. Claim Grounding & Evidence Integrity

### Citation Requirements
- All factual paragraphs require at least one citation
- Citations use format `[EVID:evidence_id]`
- Self-referential citations (citing the current report's hash) are rejected
- Citation count per paragraph is bounded (1-5)

### Evidence Lifecycle
Evidence progresses through states: `active` → `expired` → `revoked`. Only `active` evidence may be cited. Expired evidence (>30 minutes) triggers abort.

### Scope Binding
Each evidence entry is bound to a `query_hash`. Evidence from a different query hash cannot be cited. Global artifacts (system configuration) have `null` query_hash and are permitted.

### Abort Conditions
- Fabricated evidence ID
- Evidence does not exist in store
- Evidence lifecycle is not `active`
- Evidence belongs to different query scope
- Evidence payload is empty or below minimum length (50 chars)

---

## 6. Reuse & Replay Safety

### Groundhog Day Prevention
Identical queries within a defined window return the cached report rather than re-executing. This prevents oscillation and redundant processing.

### True Reuse
When grounding conditions are unchanged, the full cached report is returned. Validation requirements:
- Evidence ordering must match lexicographical sort
- All cited evidence must still exist
- Evidence freshness must be within threshold
- Kill switches must not be active

### Metadata-Only Fallback
If True Reuse validation fails, only metadata (query hash, timestamp) is reused. A new report is generated with fresh evidence.

### Validation Requirements
Reuse is denied if:
- Evidence ordering has drifted
- Any evidence is stale or revoked
- Grounding contract version has changed
- Operator has disabled reuse via kill switch

---

## 7. Security & Abuse Resistance

### Prompt Injection Defenses
Inbound payloads are sanitized at ingestion. The following patterns are stripped:
- `Ignore previous instructions`
- `System:`, `Assistant:`, `Human:` prefixes
- `You are ChatGPT` variants
- Code blocks containing action verbs

The following patterns trigger outright rejection:
- `### Execution Provenance` (footer spoofing)
- `[[IDENTITY_FACTS_READ_ONLY]]` (identity injection)

### Citation Laundering Prevention
Embedded citation tokens (`[EVID:*]`) in external payloads are scrubbed before storage. LLM cannot launder external content as evidence.

### Evidence Type Whitelist
Only evidence types `rss_item`, `api_result`, and `document` are permitted. Unknown types are rejected.

### Replay & Poisoning Controls
- Evidence older than 30 minutes is rejected
- Cross-run evidence (different query_hash) is rejected
- Duplicate payload detection prevents amplification attacks

---

## 8. Operator Authority & Kill Controls

### Kill-Switch Model
Three operator-controlled switches:
- `DISABLE_TRUE_REUSE` - Forces fresh generation
- `DISABLE_EVIDENCE_REUSE` - Invalidates cached evidence
- `DISABLE_GROUNDING` - Bypasses grounding validation (emergency only)

Switches are read once per run. Mid-execution toggling has no effect.

### Human Override Constraints
Operators may override specific abort conditions via signed tokens. Constraints:
- Token must be cryptographically signed
- Override is logged to run ledger before effect
- Overrides never mutate identity

### Audit Guarantees
All security-relevant events are written to the append-only run ledger before any side effect occurs. Ledger entries include:
- Event type
- Actor (system or agent)
- SHA-256 hash of payload
- Sequence number
- ISO8601 timestamp

---

## 9. Multi-Agent Containment

### Capability Sandboxing
Each agent has a declared capability manifest:
```
read_identity:  bool
write_identity: bool
read_evidence:  bool
write_evidence: bool
invoke_tools:   [list of allowed tool names]
```
Actions outside the manifest are rejected with `DTL-AGENT-001`.

### Scheduler Determinism
Agent execution follows a fixed order: `thinker → sanitizer → executor → reporter`. Each agent is limited to 2 turns. Self-invocation is prohibited.

### Lateral Isolation Guarantees
- Agents cannot pass instructions to other agents
- Inter-agent messages are scanned for directive patterns (`You should`, `Next agent must`)
- Tool names in messages are blocked
- JSON action schemas are blocked

### Quarantine on Compromise
If an agent triggers a security violation (grounding failure, injection attempt, capability violation), it is immediately quarantined. The pipeline aborts with `DTL-AGENT-005`.

---

## 10. Auditability & Compliance Artifacts

### Provenance Footer
Every report includes an immutable footer:
```
### Execution Provenance
- Mode: {Normal | Groundhog}
- Query Hash: {16-char SHA-256}
- Evidence Count: {N}
- Sources: {sorted list}
- Timestamp: {ISO8601}
```

### Run Ledger
Append-only log of irreversible decisions:
- `GROUNDHOG_REUSE_DECISION`
- `KILL_SWITCH`
- `REPORT_FINALIZED`
- `ABORT`
- `OPERATOR_OVERRIDE`
- `RED_LINE_VIOLATION`

### Failure Codes
25 canonical codes across 5 categories:
- `DTL-REUSE-*` (5 codes)
- `DTL-GRND-*` (5 codes)
- `DTL-AGENT-*` (5 codes)
- `DTL-SEC-*` (5 codes)
- `DTL-SYS-*` (5 codes)

### Exportability
A single JSON compliance artifact can be exported containing:
- Complete run ledger
- Evidence IDs used
- Provenance footer
- Kill-switch state
- Grounding contract version

Export is read-only and deterministically ordered.

---

## 11. Known Constraints & Explicit Non-Goals

### What the System Does NOT Do
- **Does not guarantee LLM output quality.** Grounding validates citation existence, not semantic correctness.
- **Does not prevent all prompt injection.** Novel injection vectors may bypass pattern matching.
- **Does not provide real-time threat detection.** Abuse detection is pattern-based, not behavioral.
- **Does not encrypt data at rest.** Evidence and ledger are stored as plaintext JSON.
- **Does not support distributed execution.** Single-node execution assumed.

### Accepted Tradeoffs
- **Strict abort over partial output.** Uncertainty results in failure, never degraded output.
- **Performance overhead.** Sanitization, validation, and ledger writes add latency.
- **Limited reuse window.** 30-minute evidence freshness prioritizes accuracy over caching.
- **Fixed agent ordering.** Prevents emergent optimization but ensures determinism.

### Residual Attack Surface
- Sophisticated adversarial prompts not matching known patterns
- Timing side-channels during validation
- Supply chain compromise of external feeds
- Operator token theft enabling authorized abuse
- Novel LLM behaviors not anticipated by validation logic

---

*Document version: 1.0*  
*Grounding contract version: 1.0.0*
