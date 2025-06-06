# AutoML
## Dự án nghiên cứu khoa học về MLops

## Quick start backend
```bash
# COPY FILE 
# copy ra file riêng nếu update thì sửa file temp.config.yml
# file .config.yml đã được thêm vào .gitignore nên sẽ không đẩy lên github
# COPY src/backend/temp.config.yml -> src/backend/.config.yml

# cài đặt môi trường 
pip install -r requirements.txt

# chạy services
cp src/backend/temp.config.yml src/backend/.config.yml # only use linux
cd src/backend
python app.py
```
## Quick start frontend
```bash
# Trong trường hợp chưa clone dự án:
# 1. Di chuyển vào thư mục frontend
cd src/frontend

# 2. Nếu có thư mục node_modules hoặc file components.json, xóa đi
rm -rf node_modules
rm components.json

# 3. Cài đặt các package cần thiết
npm i --force

# 4. Khởi tạo dự án với shadcn UI
npx shadcn@latest init

# Nếu chưa cài Tailwind CSS, cài theo hướng dẫn (shadcn UI dựa trên Tailwind)
# Link hướng dẫn: https://tailwindcss.com/docs/guides/nextjs

# 5. Chạy dự án trên môi trường phát triển
npm run dev

# Trong trường hợp đã clone dự án:
# 1. Di chuyển vào thư mục frontend
cd src/frontend
# 2. Chạy dự án trên môi trường phát triển
npm run dev