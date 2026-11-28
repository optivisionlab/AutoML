#!/usr/bin/env bash

# ==========================================================
# Start Ray Head Node (Bare-Metal)
# ==========================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default settings
PORT=7776
CLIENT_PORT=7777
BACKGROUND=false

print_usage() {
    echo "Usage: ./start_head.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -p, --port <PORT>        GCS port for Head Node (Default: 7776)"
    echo "  -c, --client-port <PORT> Ray Client server port (Default: 7777)"
    echo "  -D, --daemon             Run in background (Daemon mode)"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./start_head.sh"
    echo "  ./start_head.sh -p 7776 -c 7777 -D"
}

# Parse CLI arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -p|--port) PORT="$2"; shift ;;
        -c|--client-port) CLIENT_PORT="$2"; shift ;;
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

# Build start command
CMD=(ray start --head
    --port="$PORT"
    --ray-client-server-port="$CLIENT_PORT"
    --include-dashboard=false
)


LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
PID_FILE="$LOG_DIR/headnode_${PORT}.pid"
LOG_FILE="$LOG_DIR/headnode_${PORT}.log"

echo "Starting Ray Head Node (Port: $PORT, Client Port: $CLIENT_PORT)..."

if [ "$BACKGROUND" = true ]; then
    nohup "${CMD[@]}" --block > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Head Node is running in background (PID: $(cat "$PID_FILE"))."
    echo "Log file: $LOG_FILE"
    echo "Stop:     ./stop_cluster.sh"
else
    exec "${CMD[@]}" --block
fi
