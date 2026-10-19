# Bảng tra toàn bộ tool của hệ thống HAutoML

Tài liệu tổng hợp cho người phát triển, không nằm trong system prompt. Agent
nào dùng tool nào do `tools:` trong `skills/<agent>/SKILL.md` quyết định.

## agent-manager

| Tool | Ghi chú |
|---|---|
| `ask_prompt_agent` | Chạy Prompt Agent → R (JSON 6 khoá) + `missing` |
| `ask_data_agent` | Chạy Data Agent; schema nó đọc được giữ cho Model Agent |
| `ask_model_agent` | Chạy Model Agent với R + hồ sơ dữ liệu → `configs` có `config_id` |
| `ask_operation_agent` | Chạy Operation Agent với danh sách config đã kiểm |

## prompt-agent

Không có tool. Một lượt LLM trả JSON, code soát lại bằng `team.normalize_requirements`.

## data-agent

Endpoint tính từ `/api/v1` của backend.

| Tool | Endpoint | Ghi chú |
|---|---|---|
| `list_my_datasets` | `GET /datasets` (lật hết các trang) | Backend tự lọc theo token |
| `get_dataset_info` | `GET /datasets/{id}` | Metadata, **không có tên cột** |
| `get_dataset_schema` | `/datasets/{id}` + `/datasets/{id}/data` + `/datasets/{id}/features` × 2 | Ứng viên target cho CẢ classification lẫn regression |
| `read_reference` | — | Đọc file trong `references/`, tối đa 6000 ký tự |

## model-agent

| Tool | Endpoint | Ghi chú |
|---|---|---|
| `list_metrics` | — | Đọc `metric_list` trong `assets/classification.yml` / `regression.yml` (backend v1 không có endpoint metric) |
| `list_models` | — | Đọc cùng hai file yml |
| `submit_config` | như `get_dataset_schema` | Kiểm bằng `validate_config.py`, KHÔNG train. Suy loại bài toán từ cột mục tiêu nếu chưa có |
| `read_reference` | — | |

## operation-agent

| Tool | Endpoint | Ghi chú |
|---|---|---|
| `start_training` | `POST /datasets/{id}/training` | Chỉ nhận `config_id`, tự bật watcher. `max_time` gửi đi dưới tên `timeout` |
| `watch_job` | `GET /inference/jobs` (định kỳ) | Theo dõi nền tới khi `status ≠ 0` |
| `list_my_jobs` | `GET /inference/jobs` | Bản tóm tắt từng job; lọc job của chính người dùng (admin nhận job của mọi người) |
| `get_job_info` | `GET /inference/jobs` | Backend không có endpoint xem một job - tìm trong danh sách |
| `activate_model` | `PUT /inference/models/{id}/activation` | Job của mình và đã xong |
| `predict` | `POST /inference/models/{id}/predict` | ≤ 50 mẫu, soát đủ cột cho mọi mẫu |

## Không phơi cho LLM

| Hàm | Ai gọi | Vì sao |
|---|---|---|
| `login` (qua `ensure_login`) | `chat.py` khi chat ở terminal | Xác thực là việc của hạ tầng, LLM không cầm token. Trên web, agent dùng token của phiên đăng nhập |
| `upload_dataset_file` | `server.py` (`POST /agent/upload`) | LLM không cầm được file |

## Tool chưa viết

| Endpoint | Tool dự kiến | Thuộc agent |
|---|---|---|
| `POST /inference/jobs/{id}/cancel` | `cancel_job` | operation-agent |
| `DELETE /datasets/{id}` | `delete_dataset` | data-agent |
| `POST /inference/models/{id}/predict/file` | `batch_predict` | operation-agent |
