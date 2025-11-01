# Sử dụng một image nền tảng (base image)
FROM python:3.10.12

# setup system
RUN apt-get update && apt-get install vim -y

# Đặt thư mục làm việc trong container
WORKDIR /app

# Sao chép file requirements.txt vào container và cài đặt thư viện
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
ENV PYTHONPATH="/app"

# Lệnh mặc định khi container chạy, nhưng sẽ ghi đè bằng Docker Compose
CMD [ "python", "worker.py" ]