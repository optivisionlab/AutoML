FROM python:3.10.12

# setup project
WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# xóa bớt rác Python sinh ra
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"

# Chỉ định trong docker-compose để tận dụng luôn image
# CMD ["python", "app.py"]

