# Skill: Parameter Validation

Rules for validating action parameters before execution.

## URL Validation

### Format Requirements
- Must be valid HTTPS URL
- Must match allowlist prefix
- No query strings with sensitive data
- No localhost or private IPs

### Allowlist
```
https://rss.nytimes.com
https://feeds.bbci.co.uk
https://feeds.reuters.com
https://techcrunch.com
https://www.reddit.com/r/*/top.rss
```

## Budget-Conscious Parameters

### Rate Limits
| Parameter | Max Value | Default |
|-----------|-----------|---------|
| `max_items` | 25 | 10 |
| `timeout_sec` | 30 | 10 |
| `retry_count` | 3 | 1 |

### Token Budgets
| Operation | Max Tokens |
|-----------|------------|
| RSS fetch | 0 (no LLM) |
| Normalize | 1000 |
| Summarize | 2000 |

## Rejection Criteria

Reject if:
- URL not in allowlist
- `max_items` > 25
- Missing required params
- Duplicate fingerprint (loop)
