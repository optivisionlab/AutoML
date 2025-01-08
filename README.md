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
- Yêu cầu hệ thống
+ Node.js 18.18 or later.
+ NPM
+ macOS, Windows (including WSL), and Linux are supported.

- docs hướng dẫn cài đặt nodejs và NPM: https://www.geeksforgeeks.org/how-to-install-node-run-npm-in-vs-code/

- di chuyển vào thư mục frontend:
```
cd src/frontend
```
- gõ lệnh để install các package cần thiết
```
npm i
```
- chạy dự án trên môi trường dev
```
npm run dev
```