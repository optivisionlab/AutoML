#!/usr/bin/env bash

# ==========================================================
# Stop Ray Cluster (Head Node & Worker Nodes)
# ==========================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

echo "Stopping Ray cluster..."

# 1. Stop background processes tracked by PID files
if [ -d "$LOG_DIR" ]; then
    for pid_file in "$LOG_DIR"/*.pid; do
        if [ -f "$pid_file" ]; then
            PID=$(cat "$pid_file" 2>/dev/null || true)
            if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
                kill "$PID" 2>/dev/null || true
            fi
            rm -f "$pid_file"
        fi
    done
fi

# 2. Terminate any remaining Ray daemon processes
if command -v ray &> /dev/null; then
    ray stop --force 2>/dev/null || true
fi

echo "Ray cluster stopped successfully."
