# HAutoML
## Dự án nghiên cứu khoa học về HAutoML

## Quick start Backend
```bash
# COPY FILE 
# copy ra file riêng nếu update thì sửa file temp.config.yml
# file .config.yml đã được thêm vào .gitignore nên sẽ không đẩy lên github
# COPY src/backend/temp.config.yml -> src/backend/.config.yml

# Làm tương tự với file temp.env 

# 1. cài đặt môi trường conda python 3.10.12
cd src/backend
pip install -r requirements.txt

# 2. cấu hình môi trường
cp src/backend/temp.config.yml src/backend/.config.yml

cp src/backend/temp.env src/backend/.env

export PYTHONPATH=$(pwd)

# run worker server
python worker.py
# hoặc
./run-worker.sh
# Lý do: vì hệ thống hoạt động theo kiến trúc phân tán

# run hautoml toolkit
python app.py

# run hautoml nano
python automl/demo_gradio.py

```

## Quick start Frontend
```bash
# Trong trường hợp chưa clone dự án:
# 1. Di chuyển vào thư mục frontend
cd automl/src/frontend

# 2. Nếu có thư mục node_modules hoặc file components.json, xóa đi
rm -rf node_modules
rm components.json

# 3. Cài đặt NodeJS, tailwindcss, postcss, shadcn
bash install-nodejs.sh

# 4. Chạy dự án trên môi trường phát triển
cp temp.env .env
npm run dev
```

## Quick start Docker
```bash
# run docker compose
# workdir automl
docker-compose up -d
```

## Quick start Worker
```bash
cd src/backend
# default
./run-worker.sh
# chỉ định số lượng worker sẽ chạy
./run-worker.sh -n 3
# Sau khi docker được build lên, có thể  yêu cầu docker build lại image bằng cờ -b
./run-worker.sh -b
## Mục đích lựa chọn cờ -b khi có thay đổi logic hoặc Dockerfile.
# Xem hướng dẫn
./run-worker.sh -h
```

## Quick start MinIO
```bash
# Dùng để lưu trữ dữ liệu
# https://github.com/minio/minio
# Chỉ định MinIO endpoint (port run server của MinIO) vào .env
```