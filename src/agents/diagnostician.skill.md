# Diagnostician Agent Capability Manifest

## Identity
- **Agent ID**: `diagnostician-v0.1`
- **Role**: System health monitoring and self-improvement analysis
- **Domain**: Operational diagnostics

## Capabilities

### ALLOWED
- `read_run_ledger`: Read historical run data
- `read_system_state`: Read current system state (NORMAL/DEGRADED/HALTED)
- `read_routing_stats`: Read routing statistics (read-only)
- `read_evidence_store`: Read evidence for analysis
- `generate_diagnostics`: Create diagnostic reports
- `propose_improvements`: Suggest system improvements (no direct action)

### DENIED
- `write_routing_stats`: Cannot update routing stats (DISABLE_LEARNING enforced)
- `execute_trade`: Cannot execute trades
- `modify_system_state`: Cannot change system state (operator only)
- `modify_identity`: Cannot modify identity store
- `write_evidence`: Cannot write to evidence store

## Input Schema
```json
{
  "analysis_window": {
    "type": "object",
    "properties": {
      "start_date": {"type": "string", "format": "date"},
      "end_date": {"type": "string", "format": "date"},
      "run_ids": {"type": "array", "items": {"type": "string"}}
    }
  },
  "focus_areas": {
    "type": "array",
    "items": {"type": "string", "enum": ["performance", "errors", "latency", "evidence_quality"]}
  }
}
```

## Output Schema
```json
{
  "diagnostic_report": {
    "type": "object",
    "properties": {
      "report_id": {"type": "string", "pattern": "^DIAG-[0-9]{8}$"},
      "generated_at": {"type": "string", "format": "date-time"},
      "system_health": {"type": "string", "enum": ["healthy", "degraded", "critical"]},
      "metrics": {
        "type": "object",
        "properties": {
          "total_runs": {"type": "integer"},
          "success_rate": {"type": "number"},
          "avg_latency_ms": {"type": "integer"},
          "evidence_quality_score": {"type": "number"}
        }
      },
      "issues_detected": {
        "type": "array",
        "items": {
          "issue_id": {"type": "string"},
          "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
          "description": {"type": "string", "maxLength": 500}
        }
      },
      "improvement_suggestions": {
        "type": "array",
        "items": {
          "suggestion_id": {"type": "string"},
          "category": {"type": "string"},
          "description": {"type": "string", "maxLength": 500},
          "estimated_impact": {"type": "string", "enum": ["low", "medium", "high"]}
        }
      }
    }
  }
}
```

## Analysis Categories
- **Performance**: Run success rates, execution times
- **Errors**: Failure patterns, rejection reasons
- **Latency**: API response times, pipeline bottlenecks
- **Evidence Quality**: Source reliability, freshness

## Constraints
- Read-only access to all stores
- Improvement suggestions are proposals only (human approval required)
- Cannot trigger system state changes
- All outputs are advisory, not actionable

## Kill Switch Behavior
- **DISABLE_LEARNING**: No write capability anyway
- **DISABLE_WRITES**: No impact (read-only agent)
- **DISABLE_REUSE**: Can still read historical data

## Error Handling
- Return partial diagnostics on data access failure
- Note incomplete analysis in report
- Always include timestamp and scope of analysis
