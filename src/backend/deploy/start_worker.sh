#!/usr/bin/env bash

# Script to start PyMapReduce Worker Node natively on bare-metal machines

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env configuration if present
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.env" 2>/dev/null || true
    set +a
fi


HEAD_ADDR=${HEAD_ADDR:-"127.0.0.1:7777"}
CPUS=${WORKER_CPUS:-""}
IDLE_TIMEOUT=${IDLE_TIMEOUT:-0}
BACKGROUND=false

print_usage() {
    echo "Usage: ./start_worker.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -a, --head-addr <IP:PORT>     Head Node IP address and port (Default: 127.0.0.1:7777)"
    echo "  -c, --cpus <NUM_CPUS>         Number of CPU cores to allocate (Default: Auto-detect all cores)"
    echo "  -t, --timeout <MINUTES>       Idle timeout in minutes before exit (Default: 0 - disabled)"
    echo "  -d, --daemon                  Run process in background (Daemon mode)"
    echo "  -h, --help                    Show this help message and exit"
    echo ""
    echo "Examples:"
    echo "  ./start_worker.sh -a 192.168.1.50:7777"
    echo "  ./start_worker.sh -a 192.168.1.50:7777 -c 4 -d"
}

# Parse Arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -a|--head-addr) HEAD_ADDR="$2"; shift ;;
        -c|--cpus) CPUS="$2"; shift ;;
        -t|--timeout) IDLE_TIMEOUT="$2"; shift ;;
        -d|--daemon) BACKGROUND=true ;;
        -h|--help) print_usage; exit 0 ;;
        *) echo "Invalid parameter: $1"; print_usage; exit 1 ;;
    esac
    shift
done

echo "============================================================"
echo "Starting PyMapReduce Worker Node (Bare-Metal)"
echo "  - Connecting to Head Node: $HEAD_ADDR"
if [ -n "$CPUS" ]; then
    echo "  - CPU Cores: $CPUS"
else
    echo "  - CPU Cores: Auto-detected (all available cores)"
fi
echo "============================================================"

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3.10+."
    exit 1
fi

REQ_FILE="$SCRIPT_DIR/requirements.txt"

# Install or verify machine learning dependencies
if [ -f "$REQ_FILE" ]; then
    echo "Checking and installing dependencies from requirements.txt..."
    pip install --no-cache-dir -r "$REQ_FILE"
fi

# Ensure log directory exists
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
WORKER_TAG=$(echo "$HEAD_ADDR" | tr ':.' '_')
LOG_FILE="$LOG_DIR/worker_${WORKER_TAG}.log"
PID_FILE="$LOG_DIR/worker_${WORKER_TAG}.pid"

# Construct execution command
CMD=(mapreduce start --worker --head-addr "$HEAD_ADDR" --idle-timeout "$IDLE_TIMEOUT")

if [ -n "$CPUS" ]; then
    CMD+=(--cpus "$CPUS")
fi

if [ "$BACKGROUND" = true ]; then
    echo "Running Worker Node in background..."
    nohup "${CMD[@]}" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Worker Node started successfully (PID: $(cat "$PID_FILE"))."
    echo "Log file: $LOG_FILE"
    echo "Stop command: kill \$(cat $PID_FILE)"
else
    echo "Running Worker Node in foreground (Press Ctrl+C to stop)..."
    exec "${CMD[@]}"
fi
