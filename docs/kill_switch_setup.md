# Global Kill Switch Setup

## Overview
The global kill switch system provides runtime control over critical system operations without requiring code deployments.

## Setup Instructions

### 1. Create Kill Switch Configuration File

```bash
# Copy the template to data/ directory
cp config/kill_switches.json.template data/kill_switches.json
```

### 2. Configuration Format

The `data/kill_switches.json` file has the following structure:

```json
{
  "version": "1.0.0",
  "switches": {
    "GLOBAL_SHUTDOWN": false,
    "TRUE_REUSE": false,
    "EVIDENCE_REUSE": false,
    "GROUNDING": false,
    "LEARNING": false,
    "LLM_CALLS": false
  },
  "last_updated": "2026-01-04T12:00:00Z",
  "updated_by": "operator_name"
}
```

### 3. Available Switches

| Switch | Effect | Use Case |
|--------|--------|----------|
| `GLOBAL_SHUTDOWN` | Halts ALL operations | Emergency stop |
| `TRUE_REUSE` | Disables Groundhog Day report reuse | Force fresh data fetching |
| `EVIDENCE_REUSE` | Disables evidence caching | Debugging evidence issues |
| `GROUNDING` | Disables grounding validation | Bypass strict validation (dangerous) |
| `LEARNING` | Disables Strategic Autonomy learning | Prevent automated learning |
| `LLM_CALLS` | Disables all LLM calls | Cost control / testing |

### 4. Activating a Kill Switch

To activate a switch, set its value to `true`:

```json
{
  "switches": {
    "GLOBAL_SHUTDOWN": true,  // ← System halted
    ...
  }
}
```

### 5. Caching Behavior

- Kill switches are **cached for 60 seconds**
- Changes take effect within 1 minute
- No restart required
- Falls back to hardcoded constants if file is missing/invalid

### 6. Usage Example

#### Emergency Shutdown

```bash
# Edit the kill switch file
echo '{"version": "1.0.0", "switches": {"GLOBAL_SHUTDOWN": true, ...}}' > data/kill_switches.json

# All operations will halt within 60 seconds
```

#### Disable LLM Calls (Cost Control)

```bash
# Temporarily disable expensive LLM calls
# Edit data/kill_switches.json:
{
  "switches": {
    "LLM_CALLS": true,
    ...
  }
}
```

### 7. Verification

Check current switch states programmatically:

```python
from src.core.kill_switches import get_all_switch_states

states = get_all_switch_states()
print(states)
# {'GLOBAL_SHUTDOWN': False, 'TRUE_REUSE': False, ...}
```

Check a specific switch:

```python
from src.core.kill_switches import check_kill_switch

halted, reason = check_kill_switch("LLM_CALLS")
if halted:
    print(f"LLM calls are disabled: {reason}")
```

### 8. Security Notes

> [!CAUTION]
> - The `data/kill_switches.json` file is **gitignored** to prevent accidental commits
> - Only trusted operators should have write access
> - Disabling `GROUNDING` validation is dangerous and should only be done for debugging

### 9. Troubleshooting

**Switches not taking effect:**
- Wait up to 60 seconds for cache refresh
- Check file exists at `data/kill_switches.json`
- Verify JSON is valid (`python -m json.tool data/kill_switches.json`)

**File not found error:**
- System will fall back to hardcoded constants (all `false`)
- Create file using template: `cp config/kill_switches.json.template data/kill_switches.json`

## Integration Points

The kill switch system is checked at the following points:

1. **Groundhog Day Reuse** (`TRUE_REUSE`) - `src/graph/workflow.py:pruned_thinker_node()`
2. **Evidence Reuse** (`EVIDENCE_REUSE`) - Evidence store operations
3. **Grounding Validation** (`GROUNDING`) - `src/graph/workflow.py:reporter_node()`
4. **Strategic Autonomy Learning** (`LEARNING`) - Learning feedback loops
5. **LLM Calls** (`LLM_CALLS`) - Before any model invocation
6. **Global Shutdown** (`GLOBAL_SHUTDOWN`) - Checked first in all operations
