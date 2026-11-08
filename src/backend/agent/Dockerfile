# Agent server (POST /agent/chat, /agent/chat/stream, /agent/events, /agent/upload).
# Build context là thư mục agent/: agent không import code backend, chỉ gọi
# backend qua HTTP (HAUTOML_BASE_URL), nên ảnh gọn và build lại nhanh.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /tmp/agent-requirements.txt
RUN pip install --no-cache-dir -r /tmp/agent-requirements.txt

# Code nằm ở /app/agent để chạy được `python -m agent.server` như ngoài Docker.
COPY . /app/agent

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGENT_HOST=0.0.0.0 \
    AGENT_PORT=9500

# Không chạy bằng root (audit AG-06): agent không ghi file nào ngoài /tmp (file tạm của form upload), nên một
# user thường là đủ - lỗi RCE trong agent hay dependency không còn quyền root trong container.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin agent
USER agent

EXPOSE 9500

CMD ["python", "-m", "agent.server"]
