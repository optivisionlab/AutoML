# AutoML
## Dự án nghiên cứu khoa học về MLops

## Quick start backend
```bash
COPY FILE 
# copy ra file riêng nếu update thì sửa file temp.config.yml
# file .config.yml đã được thêm vào .gitignore nên sẽ không đẩy lên github
src/backend/temp.config.yml -> src/backend/.config.yml

# cài đặt môi trường 
pip install -r requirements.txt

# chạy services
cd src/backend
python app.py
```
