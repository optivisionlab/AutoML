#!/bin/bash

# --- Default Configuration ---
DEFAULT_WORKERS=1
DEFAULT_PORT=4000
COMPOSE_FILE="worker.docker-compose.yaml"
ENV_FILE=".env" # Shared environment variables (MinIO, Backend Host, etc.)

# Initial states
NUM_WORKERS=$DEFAULT_WORKERS
DO_BUILD=false

# --- Command Line Arguments Processing ---
while getopts "n:bh" opt; do
    case $opt in
        n)
            # Assign the value after -n to NUM_WORKERS
            NUM_WORKERS=$OPTARG
            ;;
        b)
            DO_BUILD=true 
            ;;
        h)
            # Help instructions
            echo "Usage: $0 [-n <number_of_workers>] [-b (force rebuild image)]"
            echo "  -n: Specify the number of workers to run (Default: $DEFAULT_WORKERS)"
            echo "  -b: Force Docker Compose to rebuild the image."
            exit 0
            ;;
         \?)
            # Handle invalid options
            echo "Error: Invalid option -$OPTARG" >&2
            exit 1
            ;;
    esac
done        

echo "--- Generating $NUM_WORKERS Worker Services (Starting Port: $DEFAULT_PORT) ---"

# Initialize the compose file
cat > $COMPOSE_FILE << EOF
services:
EOF

for i in $(seq 1 $NUM_WORKERS); do
    CURRENT_PORT=$((DEFAULT_PORT + i - 1))

    # --- START SERVICE CONFIGURATION ---
    cat >> $COMPOSE_FILE << EOF
  worker-$i:
    image: workers:latest
    build:
      context: .
      dockerfile: worker.dockerfile
    container_name: worker-$i
    restart: unless-stopped
    ports:
      - "$CURRENT_PORT:$CURRENT_PORT"
    volumes:
      - .:/app
    env_file:
      - $ENV_FILE
    environment:
      - WORKER_PORT=$CURRENT_PORT
      - WORKER_INDEX=$i
    command: python -m cluster.worker --host 0.0.0.0 --port $CURRENT_PORT --index $i
EOF
    # --- END SERVICE CONFIGURATION ---
done

echo "Configuration file $COMPOSE_FILE created successfully."
echo "--- Launching Docker Compose ---"

BUILD_FLAG=""
if $DO_BUILD; then
    BUILD_FLAG="--build"
    echo "Force rebuilding images..."
fi

# Execute Docker Compose
docker compose -f $COMPOSE_FILE up -d $BUILD_FLAG

echo "--- Successfully deployed $NUM_WORKERS workers! ---"