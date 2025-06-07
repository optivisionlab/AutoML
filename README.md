# HAutoML
## Dự án nghiên cứu khoa học về HAutoML

## Quick start backend
```bash
# COPY FILE 
# copy ra file riêng nếu update thì sửa file temp.config.yml
# file .config.yml đã được thêm vào .gitignore nên sẽ không đẩy lên github
# COPY src/backend/temp.config.yml -> src/backend/.config.yml

# 1. cài đặt môi trường conda python 3.10.12
cd src/backend
pip install -r requirements.txt

# 2. cấu hình môi trường
cp src/backend/temp.config.yml src/backend/.config.yml
export PYTHONPATH=$(pwd)

# run hautoml toolkit
python app.py

# run hautoml nano
python automl/demo_gradio.py

```
## Quick start frontend
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