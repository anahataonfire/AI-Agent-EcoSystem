# Ralph CLI

Run Ralph autonomous AI coding agent with a web UI inside Antigravity.

## Quick Start

### 1. Start the UI

```bash
cd ralph-cli/ui/ralph-ui
npm run dev
```

Open http://localhost:3000

### 2. Run the Demo

1. Open the UI at http://localhost:3000
2. Enter project path: `/path/to/ralph-cli/demo`
3. Click **Validate**
4. Select tool: `antigravity-claude`
5. Set max iterations: `3`
6. Click **Run**

Watch the logs stream live as Ralph fixes the bug and marks the story as passing.

## Requirements

### Default Mode (External APIs)

Currently, Ralph uses external API keys by default since Antigravity-native model calls are not directly accessible from Node.js subprocesses.

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes* | Claude API access |
| `GOOGLE_API_KEY` | No | Gemini fallback |

*At least one API key must be provided.

```bash
export ANTHROPIC_API_KEY=your-claude-key
export GOOGLE_API_KEY=your-gemini-key   # Optional fallback
```

### Future: Antigravity-Native Mode

When `ANTIGRAVITY_MODEL_ENDPOINT` is available (future integration), no external API keys will be required. The router will automatically detect and use native providers.

## Tools

Ralph supports three tool backends:

| Tool | Description |
|------|-------------|
| `antigravity-claude` | **Default.** Node.js adapter with auto-failover (Claude → Gemini). |
| `amp` | Amp CLI (requires Amp installed) |
| `claude` | Claude Code CLI (requires Claude Code installed) |

## Model Failover

The `antigravity-claude` adapter automatically handles quota exhaustion:

| Priority | Model | API Identifier |
|----------|-------|----------------|
| 1 | Claude Sonnet | `claude-sonnet-4-20250514` |
| 2 | Gemini Flash | `gemini-2.0-flash` |
| 3 | Gemini Pro | `gemini-1.5-pro` |

**Behavior:**
- When Claude returns 429/quota error → marks Claude exhausted, switches to Gemini
- Probe-based recovery: every 2 minutes, attempts minimal Claude call
- When probe succeeds → switches back to Claude
- Logs show: `[Router] SWITCH: claude -> gemini-flash (reason: api quota error)`

**Recovery uses probes, not fixed timeouts:**
- No assumed "1 hour reset" - recovery is probe-based
- Cockpit hints can accelerate probe timing when reset is imminent

**Simulate failover for testing:**
```bash
export FORCE_FALLBACK=1
cd ralph-cli/demo
../ralph.sh --tool antigravity-claude 3
```

## Antigravity Cockpit Integration

Optionally integrate with the [Antigravity Cockpit](https://github.com/jlcodes99/vscode-antigravity-cockpit) VS Code extension for **proactive quota hints**.

### How It Works

1. Cockpit monitors Claude quota via local process or authorized API
2. Stores quota snapshots in `~/.antigravity_cockpit/cache/quota/`
3. Router reads snapshots as **hints** before making API calls
4. Avoids wasted calls when quota is clearly low

### Behavioral Rules

| Source | Authority | Behavior |
|--------|-----------|----------|
| API error (429/quota) | **Authoritative** | Marks Claude exhausted, triggers fallback |
| Cockpit snapshot | **Hint only** | Switches preference, does NOT mark exhausted |
| Stale snapshot | **Ignored** | Router proceeds normally |
| Probe success | **Overrides all** | Switches back to Claude |
| Probe failure | **Authoritative** | Stays on fallback |

### Enable Cockpit Integration

```bash
export AG_COCKPIT_ENABLE=1
export AG_COCKPIT_EMAIL=your@email.com  # Optional: lookup specific cache
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AG_COCKPIT_ENABLE` | `0` | Set to `1` to enable quota hints |
| `AG_COCKPIT_EMAIL` | (none) | Email to lookup in cache (SHA256 hashed) |
| `AG_COCKPIT_SOURCE` | `local` | Cache source: `local` or `authorized` |
| `AG_COCKPIT_STALE_MS` | `180000` | Snapshot staleness threshold (3 min) |
| `AG_CLAUDE_MIN_SECONDS` | `60` | Min reset seconds to prefer Claude |
| `AG_CLAUDE_MIN_PCT` | `5` | Min remaining % to prefer Claude |

### Cache Location

```
~/.antigravity_cockpit/cache/quota/
├── local/
│   └── {sha256(email)}.json
└── authorized/
    └── {sha256(email)}.json
```

### Failure Modes

- **No cache file found:** Router proceeds normally via API error detection
- **Stale snapshot:** Ignored, router proceeds normally
- **Cockpit read error:** Logged and ignored, falls back to normal behavior

## Security

The adapter enforces a strict command allowlist. Only these test commands are permitted:

- `pytest [args]`
- `python -m pytest [args]`
- `npm test`
- `npm run test`
- `pnpm test` / `pnpm run test`
- `bun test`
- `go test ./...`
- `cargo test`
- `make test`
- `npx jest` / `npx vitest`

**All other shell commands are blocked.**

## Architecture

```
ralph-cli/
├── ralph.sh                    # Main loop script
├── adapters/
│   └── antigravity-claude.js   # LLM adapter with auto-failover
├── lib/
│   ├── antigravity-llm-client.js  # Unified LLM provider interface
│   ├── command-allowlist.js    # Security enforcement
│   ├── diff-applier.js         # Unified diff parser
│   ├── model-router.js         # Claude/Gemini failover router
│   └── quota-sources/
│       └── antigravity-cockpit.js  # Cockpit cache reader
├── tests/
│   ├── quota-source.test.js    # Quota source unit tests
│   └── model-router.test.js    # Router integration tests
├── demo/                       # Test project
│   ├── prd.json
│   ├── progress.txt
│   ├── src/add.js             # File with bug
│   └── test/add.test.js       # Failing test
└── ui/ralph-ui/               # Next.js UI
    ├── app/
    │   ├── page.tsx           # Main dashboard
    │   └── api/               # API routes
    └── ...
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/validate` | Validate project path |
| GET | `/api/prd?path=...` | Read prd.json |
| PUT | `/api/prd?path=...` | Update prd.json |
| GET | `/api/progress?path=...` | Read progress.txt |
| GET | `/api/git?path=...` | Get branch and log |
| POST | `/api/run` | Start Ralph run, returns runId |
| GET | `/api/stream?runId=...` | SSE stream of logs |
| POST | `/api/stop` | Stop running process (SIGTERM → SIGKILL) |

## Stop Semantics

1. **SIGTERM** sent immediately
2. **SIGKILL** sent after 5 seconds if process still running
3. UI displays "Stopped at iteration N"

## PRD Format

```json
{
  "project": "MyApp",
  "branchName": "ralph/feature-name",
  "description": "Feature description",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "description": "Story description",
      "acceptanceCriteria": ["Criterion 1", "Criterion 2"],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
```

## Iteration Flow

Each iteration:
1. Reads `prd.json` to find highest-priority failing story
2. Reads `progress.txt` for context
3. Calls LLM with implementation prompt (auto-failover: Claude → Gemini)
4. Applies unified diff from response
5. Runs allowlisted test command
6. Updates `progress.txt` with learnings
7. Updates `prd.json` story `passes` status
8. Commits changes
9. Emits `<promise>COMPLETE</promise>` when all stories pass

## Validation Commands

**Run tests:**
```bash
cd ralph-cli
npm test
```

**Test failover simulation:**
```bash
cd ralph-cli/demo
FORCE_FALLBACK=1 GOOGLE_API_KEY=your-key ../ralph.sh --tool antigravity-claude 2
```

**Verify logs show:**
- `[Router] FORCE_FALLBACK enabled, simulating Claude quota exhaustion`
- `[Router] Using model: gemini-flash (gemini-2.0-flash)`
- `[Router] SWITCH: ... (reason: ...)`

## License

MIT
