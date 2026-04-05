FROM python:3.12-slim

LABEL maintainer="HAutoML Team"
LABEL description="HAgent Bridge — Lớp trung gian giữa frontend và HAgent Gateway"

WORKDIR /app

# Cài đặt thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn bridge
COPY . /app/hagent/bridge/

# Tạo __init__.py cho package hagent
RUN echo "# HAgent" > /app/hagent/__init__.py

# Mở port 9900
EXPOSE 9900

# hagent.yaml sẽ được mount qua docker-compose volume
# ENV HAGENT_CONFIG sẽ được set qua docker-compose environment
ENV BRIDGE_HOST=0.0.0.0
ENV BRIDGE_PORT=9900
ENV PYTHONPATH=/app

# Chạy bridge service
CMD ["uvicorn", "hagent.bridge.app:hagent_bridge", "--host", "0.0.0.0", "--port", "9900"]
