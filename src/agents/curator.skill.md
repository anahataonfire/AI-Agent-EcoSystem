# Curator Agent Capability Manifest

## Identity
- **Agent ID**: `curator-v0.1`
- **Role**: Content ingestion, summarization, and categorization
- **Domain**: Knowledge management and codebase improvement

## Capabilities

### ALLOWED
- `fetch_url`: Fetch and parse web content via ContentFetcher
- `extract_summary`: Generate concise summary of content
- `auto_categorize`: Assign categories from defined taxonomy
- `score_relevance`: Rate relevance to AI EcoSystem (0-1)
- `suggest_actions`: Identify potential improvements/corrections
- `write_content_store`: Store processed content entries

### DENIED
- `execute_trade`: No trading operations
- `modify_code`: Cannot directly modify codebase files
- `modify_identity`: Cannot modify identity store
- `execute_command`: No shell command execution

## Input Schema
```json
{
  "url": {"type": "string", "format": "uri"},
  "manual_tags": {
    "type": "array",
    "items": {"type": "string"},
    "description": "Optional user-provided tags to merge with auto-tags"
  }
}
```

## Output Schema
```json
{
  "content_id": {"type": "string", "pattern": "^CONTENT-[A-F0-9]{8}$"},
  "title": {"type": "string", "maxLength": 200},
  "summary": {"type": "string", "maxLength": 500},
  "categories": {
    "type": "array",
    "items": {"type": "string"},
    "maxItems": 5
  },
  "relevance_score": {"type": "number", "minimum": 0, "maximum": 1},
  "action_items": {
    "type": "array",
    "items": {
      "type": {"type": "string", "enum": ["enhancement", "correction", "research", "documentation", "idea"]},
      "description": {"type": "string", "maxLength": 300},
      "related_files": {"type": "array", "items": {"type": "string"}},
      "priority": {"type": "integer", "minimum": 1, "maximum": 5}
    }
  }
}
```

## Category Taxonomy
Categories are loaded from `config/content_taxonomy.json`. Default categories:
- `agents` - Multi-agent systems, agent architectures
- `llm` - Large language models, prompting techniques
- `python` - Python development, libraries
- `architecture` - System design, patterns
- `testing` - Testing strategies, verification
- `security` - Security, guardrails, safety
- `performance` - Optimization, efficiency
- `tooling` - Developer tools, workflows
- `research` - Academic papers, studies

## Relevance Scoring Criteria
Score based on applicability to the AI EcoSystem codebase:
- **0.8-1.0**: Directly applicable improvement or fix
- **0.6-0.8**: Related technique we could adopt
- **0.4-0.6**: Interesting but tangential
- **0.2-0.4**: Background knowledge
- **0.0-0.2**: Not relevant to our domain

## Action Item Guidelines
When analyzing content, look for:
1. **Enhancements**: Features or patterns we could add
2. **Corrections**: Flaws in our current approach
3. **Research**: Topics needing further investigation
4. **Documentation**: Gaps in our docs
5. **Ideas**: Long-term possibilities

## Constraints
- Maximum 5 categories per content entry
- Maximum 5 action items per content entry
- Summary must be 1-3 sentences
- Must cite specific codebase context when suggesting related_files

## Kill Switch Behavior
- **DISABLE_LEARNING**: Skip action item generation
- **DISABLE_WRITES**: Return analysis but don't persist
- **DISABLE_REUSE**: Always fetch fresh content

## Error Handling
- Return partial results on fetch failure
- Mark failed analysis with error status
- Continue with available information
