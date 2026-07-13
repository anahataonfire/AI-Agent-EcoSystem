#!/bin/bash

# Deploy script for DTL Datamart Sync LaunchAgent

SCRIPT_DIR="$(dirname "$0")"
PLIST_NAME="com.adamc.dtl.datamart_sync.plist"
SOURCE_PLIST="$SCRIPT_DIR/$PLIST_NAME"
DEST_DIR="$HOME/Library/LaunchAgents"
DEST_PLIST="$DEST_DIR/$PLIST_NAME"

# 1. Ensure logs directory exists
mkdir -p "$SCRIPT_DIR/../logs"

# 2. Check source plist
if [ ! -f "$SOURCE_PLIST" ]; then
    echo "ERROR: Source plist not found at $SOURCE_PLIST"
    exit 1
fi

# 3. Create LaunchAgents dir if needed
mkdir -p "$DEST_DIR"

# 4. Copy Plist
echo "Deploying $PLIST_NAME to $DEST_DIR..."
cp "$SOURCE_PLIST" "$DEST_PLIST"

# 5. Unload existing (if any)
echo "Unloading existing job (ignore error if not loaded)..."
launchctl check system/$PLIST_NAME 2>/dev/null
launchctl bootout gui/$(id -u) "$DEST_PLIST" 2>/dev/null

# 6. Load new job
echo "Loading new job..."
launchctl bootstrap gui/$(id -u) "$DEST_PLIST"

if [ $? -eq 0 ]; then
    echo "SUCCESS: Job loaded."
    echo "To test manually: launchctl kickstart -k gui/$(id -u)/$PLIST_NAME"
    echo "Logs will appear in: logs/launchd.stdout.log"
else
    echo "ERROR: Failed to load job."
    exit 1
fi
