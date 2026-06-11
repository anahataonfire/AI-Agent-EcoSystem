#!/bin/bash
# run_harvest.sh — launchd wrapper for auto_harvest.py
# Sends iMessage alert if job exits non-zero (covers venv breakage + scan errors)

PYTHON="/Users/adamc/Documents/Projects/Ecosystem/.venv/bin/python"
HARVEST="/Users/adamc/Documents/Projects/Ecosystem/weather-trading/auto_harvest.py"
LOG_DIR="/Users/adamc/Documents/Projects/Ecosystem/weather-trading/logs"
ALERT_TO="adam@bdcllc.io"

# PD-351 H5: live mode requires explicit opt-in (export WT_AUTOHARVEST_LIVE=1).
# The hardcoded --live meant one `launchctl load` + one pip install would re-arm
# invisible real-money auto-trading that bypasses the PD-340/343/351 gates and
# never writes positions to the DB.
if [ "$WT_AUTOHARVEST_LIVE" = "1" ]; then
  "$PYTHON" "$HARVEST" --live
else
  "$PYTHON" "$HARVEST"
fi
EXIT_CODE=$?

if [ "$EXIT_CODE" -ne 0 ]; then
    /usr/bin/osascript -e "tell application \"Messages\" to send \"⚠️ Weather scan failed (exit $EXIT_CODE). Check: $LOG_DIR/auto_harvest_launchd_error.log\" to buddy \"$ALERT_TO\""
fi

exit $EXIT_CODE
