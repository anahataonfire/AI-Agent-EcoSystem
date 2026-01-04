#!/bin/zsh
# DTL Content Ingest Script for Apple Shortcuts
# This script handles environment setup for running outside of terminal

# Set environment variables
export GOOGLE_API_KEY="AIzaSyC9RYt4uoi8JFf5M8T4QfCeEB9QytMT9qc"
export X_BEARER_TOKEN="AAAAAAAAAAAAAAAAAAAAANXW6gEAAAAAn9gHWbq4fLkSp2jKXAqYzC5LbKk%3DYOpHsHWGkWwelhAdnQjlWUOS7XrMaqHs2VeBp5QtUVM4UnOT9G"

# Change to project directory
cd "/Users/adamc/Documents/001 AI Agents/AI Agent EcoSystem 2.0"

# Run the ingest command with the URL passed as argument
/Users/adamc/Documents/001\ AI\ Agents/AI\ Agent\ EcoSystem\ 2.0/.venv/bin/python -m src.cli ingest "$1"
