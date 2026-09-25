#!/usr/bin/env bash

# Script to stop background PyMapReduce processes (Head Node & Worker Nodes)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

echo "Checking and stopping background PyMapReduce processes..."

STOPPED_COUNT=0

if [ -d "$LOG_DIR" ]; then
    for pid_file in "$LOG_DIR"/*.pid; do
        if [ -f "$pid_file" ]; then
            PID=$(cat "$pid_file")
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "  - Stopping PID $PID ($(basename "$pid_file" .pid))..."
                kill "$PID" 2>/dev/null || true
                STOPPED_COUNT=$((STOPPED_COUNT + 1))
            fi
            rm -f "$pid_file"
        fi
    done
fi

# Terminate any remaining mapreduce processes
pkill -f "mapreduce start" 2>/dev/null || true

echo "Stopped $STOPPED_COUNT background PyMapReduce process(es)."
