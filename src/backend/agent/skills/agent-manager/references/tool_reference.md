# Bảng tra toàn bộ tool của hệ thống HAutoML

Tài liệu tổng hợp cho người phát triển, không nằm trong system prompt.

## account

| Tool | Endpoint | Ghi chú |
|---|---|---|
| `signup` | `POST /signup` | Tài khoản mới luôn `is_verified = false` |
| `login` | `POST /login` | Token giữ trong client, không trả ra LLM |
| `get_me` | `GET /me` | Cache `user_id` cho các tool sau |
| `logout` | `POST /logout` | Xoá token và `user_id` |
| `resend_verification_email` | `POST /auth/token/verifications` | Gửi lại link xác thực |
| `verify_email` | `POST /auth/verifications` | Nhận token thuần hoặc nguyên link |
| `dev_verify_account` | `POST /auth/verifications` | Chỉ khi `AGENT_DEV_TOOLS=1` |

## data-agent

| Tool | Endpoint | Ghi chú |
|---|---|---|
| `list_my_datasets` | `POST /get-list-data-by-userid` | Tự lấy `user_id` |
| `get_dataset_info` | `GET /get-data-info` | Metadata, **không có tên cột** |
| `get_dataset_schema` | `/get-data-info` + `/v2/auto/features` + `/v2/auto/data` | Gộp 3 lời gọi |

## model-agent

| Tool | Endpoint | Ghi chú |
|---|---|---|
| `list_my_jobs` | `POST /get-list-job-by-userId` | Tự lấy `user_id` |
| `get_job_info` | `POST /get-job-info` | Cần `job_id` từ bước liệt kê |

## agent-manager

| Tool | Ghi chú |
|---|---|
| `read_reference` | Đọc file trong `references/` của skill, tối đa 6000 ký tự |

## Tool chưa viết

Những endpoint đã có ở backend nhưng chưa bọc thành tool:

| Endpoint | Tool dự kiến | Thuộc skill |
|---|---|---|
| `POST /upload-dataset` | `upload_dataset` | data-agent |
| `GET /v2/auto/data` | `preview_dataset` | data-agent |
| `DELETE /delete-dataset/{id}` | `delete_dataset` | data-agent |
| `POST /get-data-from-uci` | `import_uci_dataset` | data-agent |
| `GET /v2/auto/metrics` | `list_metrics` | model-agent |
| `POST /v2/auto/jobs/training` | `start_training` | model-agent |
| `POST /activate-model` | `activate_model` | operation-agent |
| `POST /inference-model` | `predict` | operation-agent |
| `POST /v2/auto/{job_id}/predictions` | `batch_predict` | operation-agent |

Lưu ý: `api_client.upload_dataset` và `api_client.get_dataset_preview` đã tồn
tại, chỉ thiếu hàm bọc trong `tools.py` và schema trong `TOOL_SCHEMAS`.
