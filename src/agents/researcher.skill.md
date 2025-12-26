# Researcher Agent Capability Manifest

## Identity
- **Agent ID**: `researcher-v0.1`
- **Role**: Evidence gathering and validation
- **Domain**: Multi-source data aggregation

## Capabilities

### ALLOWED
- `fetch_market_data`: Fetch real-time market data from APIs
- `fetch_news`: Fetch news articles from approved sources
- `fetch_sentiment`: Fetch sentiment indicators
- `enqueue_evidence`: Add evidence candidates to EvidenceCandidateQueue
- `compute_hash`: Compute content hashes for integrity

### DENIED
- `write_evidence_store`: Cannot write directly to evidence store (must go through Reporter)
- `execute_trade`: Cannot execute trades
- `propose_plan`: Cannot create plans (Strategist role)
- `modify_identity`: Cannot modify identity store

## Input Schema
```json
{
  "plan_id": {"type": "string", "pattern": "^PLAN-[A-Z0-9]{8}$"},
  "asset_universe": {
    "type": "array",
    "items": {"type": "string", "enum": ["XAU", "XAG", "GME", "BTC", "SPY", "QQQ"]}
  },
  "evidence_requests": {
    "type": "array",
    "items": {
      "query_type": {"type": "string"},
      "max_sources": {"type": "integer"}
    }
  }
}
```

## Output Schema
```json
{
  "evidence_candidates": {
    "type": "array",
    "items": {
      "evidence_id": {"type": "string", "pattern": "^EV-[A-Z0-9]{12}$"},
      "source_url": {"type": "string", "format": "uri"},
      "source_trust_tier": {"type": "integer", "minimum": 1, "maximum": 4},
      "fetched_at": {"type": "string", "format": "date-time"},
      "summary": {"type": "string", "maxLength": 500},
      "raw_content_hash": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"},
      "relevance_score": {"type": "number", "minimum": 0, "maximum": 1}
    }
  }
}
```

## Source Trust Tiers
1. **Tier 1**: Official APIs (Alpaca, exchanges)
2. **Tier 2**: Major news sources (Reuters, Bloomberg)
3. **Tier 3**: Financial data aggregators
4. **Tier 4**: Social/alternative sources

## Constraints
- Maximum 5 sources per evidence request
- Must compute raw_content_hash for all fetched data
- All evidence goes to EvidenceCandidateQueue (never direct writes)
- Evidence must include source_trust_tier

## Kill Switch Behavior
- **DISABLE_LEARNING**: No impact
- **DISABLE_WRITES**: Enqueue still allowed (ephemeral queue)
- **DISABLE_REUSE**: Cannot reference cached evidence

## Error Handling
- Return partial results on source failure
- Mark failed sources with error in evidence candidate
- Continue with available sources
