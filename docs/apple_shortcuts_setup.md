# DTL Content Ingest - Apple Shortcut Setup

This document explains how to create the Apple Shortcut for cross-platform content ingestion.

## Overview

The shortcut works differently on each platform:
- **Mac**: Runs shell script directly for instant ingestion
- **iOS/iPadOS**: Appends URL to iCloud file, Mac processes later

## Step 1: Create the iCloud Folder

1. Open Finder and navigate to: `~/Library/Mobile Documents/com~apple~CloudDocs/`
2. Create a folder called `DTL`
3. Create an empty file called `inbox.txt` inside it

Or run:
```bash
mkdir -p ~/Library/Mobile\ Documents/com~apple~CloudDocs/DTL
touch ~/Library/Mobile\ Documents/com~apple~CloudDocs/DTL/inbox.txt
```

## Step 2: Create the Shortcut

### Open Shortcuts App
1. Open the **Shortcuts** app on Mac (or iOS)
2. Click **+** to create a new shortcut
3. Name it: **DTL Ingest**

### Add Actions

#### Action 1: Get Clipboard or Input
1. Add action: **Get Clipboard** (or use Shortcut Input for Share Sheet)
2. Set variable name: `ContentURL`

#### Action 2: If Statement (Platform Detection)
1. Add action: **If**
2. Condition: **Device Model** → **contains** → **Mac**

#### Action 3a: Mac Branch - Run Shell Script
1. Add action: **Run Shell Script**
2. Shell: `/bin/zsh`
3. Input: **Shortcut Input**
4. Script:
```bash
cd "/Users/adamc/Documents/001 AI Agents/AI Agent EcoSystem 2.0"
source .venv/bin/activate
python -m src.cli ingest "$1"
```

#### Action 3b: Otherwise Branch - iOS/iPadOS
1. Add action: **Get Contents of Folder**
   - Path: `iCloud Drive/DTL/inbox.txt`
2. Add action: **Append to File**
   - File: `inbox.txt` in `iCloud Drive/DTL`
   - Text: The URL variable + newline

#### Action 4: End If

#### Action 5: Show Notification
1. Add action: **Show Notification**
2. Title: "DTL Ingest"
3. Body: "Content queued for processing"

### Enable Share Sheet

1. Click the **ⓘ** icon (Info)
2. Enable **Show in Share Sheet**
3. Accept **URLs** as input type

## Step 3: Install launchd Watcher (Mac)

The Mac needs to watch the iCloud file for iOS submissions:

```bash
cd "/Users/adamc/Documents/001 AI Agents/AI Agent EcoSystem 2.0"

# Copy plist to LaunchAgents
cp launchd/com.dtl.content-watcher.plist ~/Library/LaunchAgents/

# Load the job
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dtl.content-watcher.plist
```

To verify it's loaded:
```bash
launchctl print gui/$(id -u)/com.dtl.content-watcher
```

## Step 4: Test

### Mac Test
1. Copy a URL to clipboard
2. Run the shortcut
3. Check output with: `dtl browse`

### iOS Test
1. Open Safari on iPhone/iPad
2. Tap Share → DTL Ingest
3. Wait for iCloud sync
4. Check Mac with: `dtl browse`

## Troubleshooting

### Shortcut doesn't appear in Share Sheet
- Ensure "Show in Share Sheet" is enabled
- Ensure "URLs" is accepted as input type

### iOS submissions not processing
1. Check iCloud sync is working
2. Verify inbox.txt exists: `ls ~/Library/Mobile\ Documents/com~apple~CloudDocs/DTL/`
3. Check launchd logs: `cat logs/content_watcher.log`

### Shell script fails
- Ensure GOOGLE_API_KEY is set in `.env`
- Test manually: `python -m src.cli ingest "https://example.com"`
