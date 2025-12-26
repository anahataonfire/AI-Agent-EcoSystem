#!/bin/bash
# DTL v2.0 LaunchAgent Management Script
# Usage: ./manage_launchd.sh [install|uninstall|reload|status]

USER_ID=$(id -u)
PLIST_DIR="$HOME/Library/LaunchAgents"
PROJECT_DIR="/Users/adamc/Documents/001 AI Agents/AI Agent EcoSystem 2.0"
JOBS=("com.dtl.quant-premarket" "com.dtl.realitycheck-eod")

install() {
    echo "Installing DTL LaunchAgents..."
    mkdir -p "$PLIST_DIR"
    mkdir -p "$PROJECT_DIR/logs"
    
    for job in "${JOBS[@]}"; do
        cp "$PROJECT_DIR/launchd/$job.plist" "$PLIST_DIR/"
        # Modern launchctl (macOS 10.11+)
        launchctl bootstrap gui/$USER_ID "$PLIST_DIR/$job.plist" 2>/dev/null || true
        launchctl enable gui/$USER_ID/$job
        echo "  Installed: $job"
    done
    
    echo "Done. Use './manage_launchd.sh status' to verify."
}

uninstall() {
    echo "Removing DTL LaunchAgents..."
    
    for job in "${JOBS[@]}"; do
        launchctl bootout gui/$USER_ID/$job 2>/dev/null || true
        rm -f "$PLIST_DIR/$job.plist"
        echo "  Removed: $job"
    done
    
    echo "Done."
}

reload() {
    echo "Reloading DTL LaunchAgents..."
    
    for job in "${JOBS[@]}"; do
        launchctl kickstart -k gui/$USER_ID/$job 2>/dev/null || echo "  $job: not running"
        echo "  Reloaded: $job"
    done
}

status() {
    echo "DTL LaunchAgent Status:"
    echo "------------------------"
    
    for job in "${JOBS[@]}"; do
        if launchctl print gui/$USER_ID/$job 2>/dev/null | grep -q "state"; then
            state=$(launchctl print gui/$USER_ID/$job 2>/dev/null | grep "state" | head -1)
            echo "  $job: $state"
        else
            echo "  $job: not loaded"
        fi
    done
}

case "$1" in
    install)
        install
        ;;
    uninstall)
        uninstall
        ;;
    reload)
        reload
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {install|uninstall|reload|status}"
        exit 1
        ;;
esac
