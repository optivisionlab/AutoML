FROM python:3.10.12

# setup system
RUN apt-get update && apt-get install vim curl -y

# setup nodejs and openclaw
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs
RUN npm install -g openclaw

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
