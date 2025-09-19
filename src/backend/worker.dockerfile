# Sử dụng một image nền tảng (base image)
FROM python:3.10.12

# Đặt thư mục làm việc trong container
WORKDIR /app

# Sao chép file requirements.txt vào container và cài đặt thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn vào container
COPY . .

# Lệnh mặc định khi container chạy, nhưng chúng ta sẽ ghi đè bằng Docker Compose
CMD [ "uvicorn", "worker:app", "--host", "0.0.0.0" ]