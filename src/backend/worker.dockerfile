# Sử dụng một image nền tảng (base image)
FROM python:3.10.12

# setup system
RUN apt-get update && apt-get install vim -y

# setup project
WORKDIR /app

# Sao chép file requirements.txt vào container và cài đặt thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir  -r requirements.txt

COPY . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"

# Lệnh mặc định khi container chạy, nhưng sẽ ghi đè bằng Docker Compose
# CMD [ "python", "worker.py" ]
