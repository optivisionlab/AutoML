#!/usr/bin/env bash

# ==========================================================
# Start Ray Worker Node (Bare-Metal)
# ==========================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default settings
HEAD_ADDR="127.0.0.1:7777"
CPUS=""
BACKGROUND=false

print_usage() {
    echo "Usage: ./start_worker.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -a, --head-addr <IP:PORT>  Head Node address to connect to (Default: 127.0.0.1:7777)"
    echo "  -c, --cpus <NUM>           Number of CPU cores to allocate (Default: auto-detect)"
    echo "  -D, --daemon               Run in background (Daemon mode)"
    echo "  -h, --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./start_worker.sh -a 127.0.0.1:7777"
    echo "  ./start_worker.sh -a 192.168.1.50:7777 -c 4 -D"
}

# Parse CLI arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -a|--head-addr) HEAD_ADDR="$2"; shift ;;
        -c|--cpus) CPUS="$2"; shift ;;
        -D|--daemon) BACKGROUND=true ;;
        -h|--help) print_usage; exit 0 ;;
        *) echo "Invalid parameter: $1"; print_usage; exit 1 ;;
    esac
    shift
done

# Check Ray installation
if ! command -v ray &> /dev/null; then
    echo "Error: 'ray' command not found. Please install: pip install 'ray[default]==2.60.0'"
    exit 1
fi

CMD=(ray start --address="$HEAD_ADDR")
[ -n "$CPUS" ] && CMD+=(--num-cpus="$CPUS")

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
TAG=$(echo "$HEAD_ADDR" | tr ':.' '_')
PID_FILE="$LOG_DIR/worker_${TAG}.pid"
LOG_FILE="$LOG_DIR/worker_${TAG}.log"

echo "Starting Ray Worker Node (Connecting to: $HEAD_ADDR)..."

if [ "$BACKGROUND" = true ]; then
    nohup "${CMD[@]}" --block > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Worker Node is running in background (PID: $(cat "$PID_FILE"))."
    echo "Log file: $LOG_FILE"
    echo "Stop:     ./stop_cluster.sh"
else
    exec "${CMD[@]}" --block
fi
