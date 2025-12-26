# Reporter Agent Capability Manifest

## Identity
- **Agent ID**: `reporter-v0.1`
- **Role**: Output synthesis, validation, and persistence orchestration
- **Domain**: Report generation and commit coordination

## Capabilities

### ALLOWED
- `read_evidence_queue`: Pull evidence candidates from queue
- `build_commit_bundle`: Create CommitBundle for validation
- `create_prewrite`: Create ledger prewrite tokens
- `write_evidence_store`: Write validated evidence (POST CommitGate approval)
- `write_report`: Generate analysis reports

### DENIED
- `fetch_external_data`: Cannot fetch data (Researcher role)
- `execute_trade`: Cannot execute trades
- `bypass_commit_gate`: All writes MUST pass CommitGate
- `modify_identity`: Cannot modify identity store
- `delete_evidence`: Cannot delete from evidence store

## Input Schema
```json
{
  "run_id": {"type": "string", "pattern": "^RUN-[0-9]{8}_[0-9]{6}$"},
  "evidence_candidates": {
    "type": "array",
    "items": {"$ref": "#/definitions/evidence_candidate"}
  },
  "strategist_plan": {
    "type": "object",
    "properties": {
      "plan_id": {"type": "string"},
      "asset_universe": {"type": "array"}
    }
  }
}
```

## Output Schema
```json
{
  "commit_bundle": {
    "type": "object",
    "properties": {
      "run_id": {"type": "string"},
      "agent_id": {"type": "string", "const": "reporter-v0.1"},
      "schema_version": {"type": "string"},
      "timestamp": {"type": "string", "format": "date-time"},
      "content_hash": {"type": "string"},
      "payload": {"type": "object"},
      "evidence_refs": {"type": "array", "items": {"type": "string"}},
      "capability_claims": {"type": "array", "items": {"type": "string"}}
    }
  },
  "report": {
    "type": "object",
    "properties": {
      "summary": {"type": "string", "maxLength": 2000},
      "analysis_items": {"type": "array"},
      "confidence_level": {"type": "string", "enum": ["low", "medium", "high"]}
    }
  }
}
```

## Commit Protocol
1. Pull all evidence from EvidenceCandidateQueue
2. Validate evidence against schema
3. Build CommitBundle with all metadata
4. Create prewrite token (locks intent)
5. Submit to CommitGate for validation
6. On ACCEPTED: promote prewrite, write evidence store
7. On REJECTED: log rejection, do NOT write

## Constraints
- All writes MUST pass through CommitGate
- Must include content_hash covering full bundle
- Must create prewrite BEFORE validation
- Cannot claim capabilities not in this manifest

## Kill Switch Behavior
- **DISABLE_LEARNING**: Block `routing_statistics_write` capability claim
- **DISABLE_WRITES**: Block all writes (CommitGate rejects)
- **DISABLE_REUSE**: Block prior run references

## Error Handling
- On CommitGate rejection: enter Analysis-Only mode
- Generate report even if writes blocked
- Log all rejections to run ledger
