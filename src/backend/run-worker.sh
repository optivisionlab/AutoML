#!/bin/bash

# --- Cấu hình Mặc định ---
DEFAULT_WORKERS=1
DEFAULT_PORT=4000
COMPOSE_FILE="worker.docker-compose.yaml"

# Thiết lập số lượng worker bằng flag
NUM_WORKERS=$DEFAULT_WORKERS
DO_BUILD=false

# --- Xử lý tham số dòng lệnh ---
while getopts "n:bh" opt; do
    case $opt in
        n)
            # Gán giá trị sau cờ -n cho NUM_WORKERS
            NUM_WORKERS=$OPTARG
            ;;
        b)
            DO_BUILD=true 
            ;;
        h)
            # Hiển thị hướng dẫn
            echo "Sử dụng: $0 [-n <số lượng worker>] [-b (buộc build lại image)]"
            echo "  -n: Chỉ định số lượng worker cần chạy (Mặc định: $DEFAULT_WORKERS)"
            echo "  -b: Yêu cầu Docker Compose build lại image."
            exit 0
            ;;
         \?)
            # Xử lý tham số không hợp lệ
            echo "Lỗi: Tham số không hợp lệ -$OPTARG" >&2
            exit 1
            ;;
    esac
done        

echo "--- Start creating $NUM_WORKERS Worker Services (Start Port: $DEFAULT_PORT) ---"

cat > $COMPOSE_FILE << EOF
services:
EOF

for i in $(seq 1 $NUM_WORKERS); do
    CURRENT_PORT=$((DEFAULT_PORT + i - 1))

    # --- BẮT ĐẦU KHỐI CẤU HÌNH ---
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
    environment:
      MINIO_ENDPOINT: '0.0.0.0:9000'
      MINIO_ACCESS_KEY: ''
      MINIO_SECRET_KEY: ''
      PORT_BACK_END: 80
      HOST_BACK_END: '0.0.0.0'
      WORKER_HOST: '0.0.0.0'
      WORKER_PORT: $CURRENT_PORT
      WORKER_INDEX: $i
EOF
    # --- KẾT THÚC KHỐI CẤU HÌNH ---
done

echo "Configuration file $COMPOSE_FILE created successfully"
echo "--- Launch Docker Compose ---"

BUILD_FLAG=""
if $DO_BUILD; then
    BUILD_FLAG="--build"
    echo "Thực hiện build lại image"
fi

# Chạy Docker Compose
docker compose -f $COMPOSE_FILE up -d $BUILD_FLAG

echo "--- Successfully deployed $NUM_WORKERS worker! ---"