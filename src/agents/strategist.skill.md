# Strategist Agent Capability Manifest

## Identity
- **Agent ID**: `strategist-v0.1`
- **Role**: Strategic planning and asset selection
- **Domain**: Financial market analysis

## Capabilities

### ALLOWED
- `read_market_data`: Read market prices, volumes, indicators
- `read_evidence`: Read validated evidence from evidence store
- `propose_plan`: Create research plans for Researcher agent
- `select_assets`: Determine asset universe for analysis
- `read_routing_stats`: Read (not write) routing statistics

### DENIED
- `write_evidence`: Cannot write directly to evidence store
- `execute_trade`: Cannot execute trades
- `write_routing_stats`: Cannot update routing statistics
- `modify_identity`: Cannot modify any identity store data

## Input Schema
```json
{
  "market_context": {
    "type": "object",
    "properties": {
      "date": {"type": "string", "format": "date"},
      "market_status": {"type": "string", "enum": ["pre_market", "open", "closed"]},
      "available_assets": {"type": "array", "items": {"type": "string"}}
    }
  }
}
```

## Output Schema
```json
{
  "plan_id": {"type": "string", "pattern": "^PLAN-[A-Z0-9]{8}$"},
  "asset_universe": {
    "type": "array", 
    "items": {"type": "string"},
    "maxItems": 10
  },
  "evidence_requests": {
    "type": "array",
    "items": {
      "query_type": {"type": "string", "enum": ["price", "news", "sentiment", "catalyst", "technical"]},
      "max_sources": {"type": "integer", "minimum": 1, "maximum": 5}
    }
  },
  "priority": {"type": "string", "enum": ["low", "normal", "high"]}
}
```

## Constraints
- Maximum 10 assets per plan
- Maximum 20 evidence requests per plan
- Must output via ProposalEnvelope wrapper
- All outputs validated by InterAgentFirewall

## Kill Switch Behavior
- **DISABLE_LEARNING**: No impact (Strategist does not learn)
- **DISABLE_WRITES**: No impact (Strategist only proposes)
- **DISABLE_REUSE**: Cannot reference prior run outputs

## Error Handling
- Return empty plan on market data failure
- Escalate to DEGRADED_MODE after 3 consecutive failures
