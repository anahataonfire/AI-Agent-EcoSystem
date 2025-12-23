# Skill: Basic Planning

Break user queries into structured RSS pipeline actions.

## Workflow

1. **Analyze** the user query to identify:
   - Target topic/domain (news, tech, finance)
   - Desired output format (summary, bullet points, analysis)
   - Time constraints (latest, past week)

2. **Plan Actions** in sequence:
   - `DataFetchRSS`: Retrieve feed from allowed sources
   - `CompleteTask`: Signal completion when evidence is collected

## Output Format

Return ONLY valid JSON matching this schema:

```json
{
  "action_type": "tool_call",
  "tool_name": "<DataFetchRSS|CompleteTask>",
  "params": {
    "// For DataFetchRSS": "...",
    "url": "<feed_url>",
    "max_items": 10,
    
    "// For CompleteTask": "...",
    "executive_summary": "High-level overview suitable for slides...",
    "key_entities": ["Person A", "Company B", "Topic C"],
    "sentiment_score": 7,
    "source_ids": ["ev_123", "ev_456"],
    "report_body_markdown": "# Full Report\n\nDetails..."
  },
  "success_criteria": ["..."],
  "plan_fingerprint": "<sha256>"
}
```

## Allowed Sources

**Static Feeds** (general news):
- `https://rss.nytimes.com/*`
- `https://feeds.bbci.co.uk/*`
- `https://feeds.reuters.com/*`
- `https://techcrunch.com/feed/`

**Dynamic Search** (topic-specific queries):
When the user asks for a specific topic (e.g., "Epstein files", "Tesla earnings", "Bitcoin crash"):
- Use `url: "google_news"` with `search_query: "<topic>"` to search Google News
- Alternatively use `url: "reddit_search"` for Reddit discussions
- Add `keywords: ["<keyword1>", "<keyword2>"]` to filter results

### DataFetchRSS Parameters

```json
{
  "url": "google_news",
  "search_query": "Epstein files release",
  "keywords": ["epstein", "files", "release"],
  "max_items": 10
}
```

## Constraints

- Max 10 items per fetch
- Prefer recent articles (24h window)
- Keep summaries under 500 words
- **IMPORTANT**: For specific topics, ALWAYS use `google_news` with `search_query` instead of generic homepage feeds

