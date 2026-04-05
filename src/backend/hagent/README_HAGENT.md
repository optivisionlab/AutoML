# HAgent - HAgent Integration for HAutoML

Đây là package tích hợp HAgent AI Agent vào hệ thống HAutoML.

## Cấu trúc thư mục

```
HAgent/
├── AGENTS.md           # Hướng dẫn tổng quan về agent system
├── SOUL.md             # Định nghĩa identity và rules của HAgent
├── USER.md             # Thông tin về người dùng
├── TOOLS.md            # Ghi chú về tools và môi trường
├── proxy.py            # HAgent Proxy - nhận request từ Bridge
├── chat_router.py      # Router cho chat endpoints
├── chat_store.py       # Lưu trữ conversation history
├── hagent.yaml         # Cấu hình HAgent Gateway
├── bridge/             # HAgent Bridge - kết nối Frontend với Gateway
│   ├── app.py
│   ├── auth.py
│   ├── config.py
│   └── ...
└── skills/             # HAgent Skills
    └── hautoml/        # HAutoML skill với tools
        ├── SKILL.md
        ├── tools.yaml
        └── scripts/
            └── hautoml_tools.py
```

## Kiến trúc

```
Frontend (Next.js)
    ↓ HTTP POST /api/v1/chat/
HAgent Bridge (FastAPI) - Port 8900
    ↓ HTTP POST /hooks/agent
HAgent Proxy (Python HTTP Server) - Port 18790
    ↓ CLI: HAgent agent --message "..." --session-id "..."
HAgent Gateway (Node.js) - Port 18789
    ↓ Execute tools from skills/hautoml/
HAutoML Backend API - Port 8585
```

## Các file quan trọng

### SOUL.md
Định nghĩa "linh hồn" của HAgent:
- **QUY TẮC TUYỆT ĐỐI**: CHỈ gọi tools, KHÔNG viết code
- Cách trả lời người dùng
- Xử lý khi không có tool phù hợp

### skills/hautoml/SKILL.md
Định nghĩa các tools có sẵn:
- `health` - Kiểm tra hệ thống
- `list_datasets` - Liệt kê datasets
- `get_features` - Lấy features của dataset
- `start_training` - Bắt đầu training job
- `get_job_info` - Xem kết quả training
- ... và nhiều tools khác

### skills/hautoml/scripts/hautoml_tools.py
CLI tool thực thi các API calls đến HAutoML Backend.

## Cách hoạt động

1. User gửi message qua chat widget
2. Frontend gọi Bridge API
3. Bridge forward đến Proxy
4. Proxy inject SOUL.md vào message và gọi HAgent Gateway
5. Gateway parse message, chọn tool phù hợp từ hautoml skill
6. Tool (hautoml_tools.py) gọi HAutoML API
7. Kết quả trả về qua chuỗi ngược lại

## Environment Variables

Các biến môi trường cần thiết:
- `HAUTOML_BASE_URL` - URL của HAutoML Backend (default: http://localhost:8585)
- `USER_TOKEN` - JWT token của user (tự động truyền từ Bridge)
- `USER_ID` - ID của user (tự động truyền từ Bridge)

## Deployment

Tất cả chạy trong Docker container `toolkit`:
- HAutoML Backend (FastAPI)
- HAgent Proxy (Python)
- HAgent Gateway (Node.js - global install)

Bridge chạy trong container riêng `HAgent_bridge`.

## Testing

Test agent trực tiếp:
```bash
docker exec toolkit openclaw agent \
  --message "Liệt kê các dataset" \
  --session-id test123 \
  --json
```

Test tool trực tiếp:
```bash
docker exec toolkit bash -c \
  "export HAUTOML_BASE_URL=http://localhost:8585 && \
   python3 /app/HAgent/skills/hautoml/scripts/hautoml_tools.py health"
```

## Troubleshooting

### Agent tự viết code thay vì gọi tools
- Kiểm tra SOUL.md có được load không
- Xem logs: `docker logs toolkit --tail 50`
- Verify skill được nhận diện: `docker exec toolkit openclaw skills list | grep hautoml`

### Tools không được gọi
- Kiểm tra skill path: `/app/HAgent/skills/hautoml/`
- Verify HAUTOML_BASE_URL environment variable
- Test tool trực tiếp (xem phần Testing)

### API calls thất bại
- Kiểm tra HAutoML Backend đang chạy: `curl http://localhost:8585/docs`
- Verify JWT token hợp lệ
- Xem logs Backend: `docker logs toolkit | grep "POST\|GET"`
