#!/bin/zsh
# DTL Content Ingest Script for Apple Shortcuts
# This script handles environment setup for running outside of terminal

# Log file for debugging
LOG_FILE="/Users/adamc/Documents/001 AI Agents/AI Agent EcoSystem 2.0/data/dtl_ingest.log"

# Get the input argument
INPUT="$1"

# Log the invocation
echo "$(date): Ingest called with arg: '$INPUT'" >> "$LOG_FILE"

# Check if input is a file path (Raycast sometimes passes clipboard as HTML file)
if [[ -f "$INPUT" ]]; then
    echo "$(date): Input is a file, extracting URL..." >> "$LOG_FILE"
    # Extract URL from HTML file - look for x.com or twitter.com links
    EXTRACTED_URL=$(grep -oE 'https?://(x\.com|twitter\.com)/[^"'"'"'<> ]+' "$INPUT" | head -1)
    if [[ -n "$EXTRACTED_URL" ]]; then
        # Clean up URL (remove trailing quotes, newlines, etc)
        INPUT=$(echo "$EXTRACTED_URL" | tr -d '\n\r' | sed 's/["\x27]$//')
        echo "$(date): Extracted URL: '$INPUT'" >> "$LOG_FILE"
    else
        # Try to get any https URL
        EXTRACTED_URL=$(grep -oE 'https?://[^"'"'"'<> ]+' "$INPUT" | head -1)
        if [[ -n "$EXTRACTED_URL" ]]; then
            INPUT=$(echo "$EXTRACTED_URL" | tr -d '\n\r' | sed 's/["\x27]$//')
            echo "$(date): Extracted URL (generic): '$INPUT'" >> "$LOG_FILE"
        else
            echo "$(date): Could not extract URL from file" >> "$LOG_FILE"
        fi
    fi
fi

# Set environment variables
export GOOGLE_API_KEY="AIzaSyC9RYt4uoi8JFf5M8T4QfCeEB9QytMT9qc"
export X_BEARER_TOKEN="AAAAAAAAAAAAAAAAAAAAANXWugEAAAAAn9gHWbq4fLkSp2jKXAqYzC5LbKk=YOpHsHWGkWwelhAdnQjlWUOS7XrMaqHs2VeBp5QtUVM4UnOT9G"

# Change to project directory
cd "/Users/adamc/Documents/001 AI Agents/AI Agent EcoSystem 2.0"

# Run the ingest command with the URL
/Users/adamc/Documents/001\ AI\ Agents/AI\ Agent\ EcoSystem\ 2.0/.venv/bin/python -m src.cli ingest "$INPUT" 2>&1 | tee -a "$LOG_FILE"
exit_code=${PIPESTATUS[0]}

echo "$(date): Exit code: $exit_code" >> "$LOG_FILE"
exit $exit_code

