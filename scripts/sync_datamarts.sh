#!/bin/bash

# DTL Datamart Sync Wrapper
# Intended for launchd automated execution
# Hardened for idempotency & concurrency safety

set -euo pipefail

# 1. Navigate to Project Root (resolved relative to this script)
SCRIPT_DIR="$(dirname "$0")"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

# 2. Setup Logging
mkdir -p logs
LOG_FILE="logs/datamart_sync.log"
echo "[$(date -u)] Starting Datamart Sync..." >> "$LOG_FILE"

# 3. Lock File (prevents concurrent runs) - uses mkdir for portability
LOCK_DIR="/tmp/dtl_datamart_sync.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "[$(date -u)] SKIPPED: Another sync is in progress (lock held)." >> "$LOG_FILE"
    exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null' EXIT

# 4. Source Environment
if [ -f .env ]; then
    set -a
    source <(grep -v '^#' .env | grep -v '^\s*$')
    set +a
fi

# 5. Activate Venv
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
else
    echo "ERROR: .venv not found at $PROJECT_ROOT/.venv" >> "$LOG_FILE"
    exit 1
fi

# 6. Determine Destination
GDRIVE_PATH=""

# Try CloudStorage Standard Path (MacOS 12+)
CS_PATH=$(find "$HOME/Library/CloudStorage" -maxdepth 1 -name "GoogleDrive-*" -type d 2>/dev/null | head -n 1)
if [ -n "$CS_PATH" ] && [ -w "$CS_PATH" ]; then
    GDRIVE_PATH="$CS_PATH"
fi

# Fallback to legacy structure
if [ -z "$GDRIVE_PATH" ] && [ -d "$HOME/Google Drive" ] && [ -w "$HOME/Google Drive" ]; then
    GDRIVE_PATH="$HOME/Google Drive"
fi

# Fallback to Documents
if [ -z "$GDRIVE_PATH" ]; then
    GDRIVE_PATH="$HOME/Documents/DTL_Datamarts"
    echo "WARNING: Could not find writable Google Drive. Using local: $GDRIVE_PATH" >> "$LOG_FILE"
fi

DEST_DIR="$GDRIVE_PATH/NotebookLM"
echo "Targeting Destination: $DEST_DIR" >> "$LOG_FILE"
mkdir -p "$DEST_DIR"

# 7. Stage to Temp Dir (Atomic Sync)
TEMP_STAGE=$(mktemp -d)
trap 'rm -rf "$TEMP_STAGE"; rmdir "$LOCK_DIR" 2>/dev/null' EXIT

echo "Staging to: $TEMP_STAGE" >> "$LOG_FILE"
python3 -m src.cli datamart-sync --dest "$TEMP_STAGE" >> "$LOG_FILE" 2>&1
SYNC_EXIT=$?

if [ $SYNC_EXIT -ne 0 ]; then
    echo "[$(date -u)] CLI Sync to stage failed. Exit Code: $SYNC_EXIT" >> "$LOG_FILE"
    exit $SYNC_EXIT
fi

# 8. Rsync to Final Destination (Atomic with --delay-updates)
# --delete: mirrors deletions from source (explicit prune policy)
# --delay-updates: atomic switch for all files
rsync -a --delay-updates --delete "$TEMP_STAGE/" "$DEST_DIR/" >> "$LOG_FILE" 2>&1
RSYNC_EXIT=$?

if [ $RSYNC_EXIT -eq 0 ]; then
    echo "[$(date -u)] Sync Complete. Success." >> "$LOG_FILE"
else
    echo "[$(date -u)] Rsync Failed. Exit Code: $RSYNC_EXIT" >> "$LOG_FILE"
fi

exit $RSYNC_EXIT
