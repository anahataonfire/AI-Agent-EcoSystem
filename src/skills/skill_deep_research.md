# Skill: Deep Research

Conduct thorough multi-source research with structured analysis output.

## Research Protocol

For ANY research query, follow this exact sequence:

### Step 1: Primary Source (Google News)
```json
{
  "action_type": "tool_call",
  "tool_name": "DataFetchRSS",
  "params": {
    "url": "google_news",
    "search_query": "<topic>",
    "keywords": ["<key>", "<terms>"],
    "max_items": 25
  }
}
```

### Step 2: Discussion Source (Reddit)
```json
{
  "action_type": "tool_call",
  "tool_name": "DataFetchRSS",
  "params": {
    "url": "reddit_search",
    "search_query": "<topic>",
    "keywords": ["<key>", "<terms>"],
    "max_items": 15
  }
}
```

### Step 3: Synthesis (CompleteTask)
Only after collecting 30+ pieces of evidence, synthesize into a structured report.

## Required Report Structure

Your `report_body_markdown` MUST include ALL of these sections:

```markdown
# [Topic] Research Report

## Executive Summary
[2-3 sentence overview of key findings]

## Key Developments
[5+ news items with citations, each as a bullet point]
- Development 1 [EVID:ev_xxx]
- Development 2 [EVID:ev_yyy]

## Analysis & Trends
[3+ paragraphs analyzing patterns, each with citations]

## Key Players
[List of companies, people, organizations involved with their roles]
- **Company A**: Role/action [EVID:ev_xxx]
- **Person B**: Role/action [EVID:ev_yyy]

## Risks & Challenges
[Potential issues, controversies, or obstacles identified]

## Outlook & Implications
[Future predictions, what to watch for]

## Sources Summary
[Total evidence count and source breakdown]
```

## Quality Standards

- **Minimum 500 words** in report body
- **Minimum 10 citations** using `[EVID:ev_xxx]` format
- **Every factual claim** must have a citation
- **Diverse sources**: Must cite both news AND Reddit evidence

## Citation Rules (CRITICAL)

1. Use ONLY evidence IDs from the "Evidence Content Preview" 
2. Format: `[EVID:ev_xxxxxxxxxx]`
3. Every paragraph with facts needs at least one citation
4. Cross-reference between sources when possible

**FAILING TO FOLLOW THIS STRUCTURE WILL CAUSE MISSION FAILURE.**
