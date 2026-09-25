#!/usr/bin/env bash

# Script to start PyMapReduce Head Node natively on bare-metal machines

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env configuration if present
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.env" 2>/dev/null || true
    set +a
fi


PORT=${HEAD_PORT:-7777}
SCHEDULER=${SCHEDULER:-"Adaptive"}
BACKGROUND=false

print_usage() {
    echo "Usage: ./start_head.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -p, --port <PORT>             Port for the Head Node to listen on (Default: 7777)"
    echo "  -s, --scheduler <STRATEGY>    Scheduling strategy (Default: Adaptive [RoundRobin, WeightedCapacity, LeastLoad, LocalityFirst, Adaptive])"
    echo "  -d, --daemon                  Run process in background (Daemon mode)"
    echo "  -h, --help                    Show this help message and exit"
    echo ""
}

# Parse Arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -p|--port) PORT="$2"; shift ;;
        -s|--scheduler) SCHEDULER="$2"; shift ;;
        -d|--daemon) BACKGROUND=true ;;
        -h|--help) print_usage; exit 0 ;;
        *) echo "Invalid parameter: $1"; print_usage; exit 1 ;;
    esac
    shift
done

echo "============================================================"
echo "Starting PyMapReduce Head Node (Bare-Metal)"
echo "  - Port: $PORT"
echo "  - Scheduler: $SCHEDULER"
echo "============================================================"

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3.10+."
    exit 1
fi

# Verify pymapreduce-core installation
if ! python3 -c "import pymapreduce" &> /dev/null; then
    echo "pymapreduce-core library not found. Installing..."
    pip install --no-cache-dir pymapreduce-core==0.1.9
fi

# Ensure log directory exists
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/headnode_${PORT}.log"
PID_FILE="$LOG_DIR/headnode_${PORT}.pid"

if [ "$BACKGROUND" = true ]; then
    echo "Running Head Node in background..."
    nohup mapreduce start --head --port "$PORT" --scheduler "$SCHEDULER" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Head Node started successfully (PID: $(cat "$PID_FILE"))."
    echo "Log file: $LOG_FILE"
    echo "Stop command: kill \$(cat $PID_FILE)"
else
    echo "Running Head Node in foreground (Press Ctrl+C to stop)..."
    exec mapreduce start --head --port "$PORT" --scheduler "$SCHEDULER"
fi
