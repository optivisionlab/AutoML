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

| Tool | Endpoint | Ghi chú |
|---|---|---|
| `list_my_datasets` | `POST /get-list-data-by-userid` | Tự lấy `user_id` |
| `get_dataset_info` | `GET /get-data-info` | Metadata, **không có tên cột** |
| `get_dataset_schema` | `/get-data-info` + `/v2/auto/features` + `/v2/auto/data` | Gộp 3 lời gọi |
| `read_reference` | — | Đọc file trong `references/`, tối đa 6000 ký tự |

## model-agent

| Tool | Endpoint | Ghi chú |
|---|---|---|
| `list_metrics` | `GET /v2/auto/metrics` | |
| `list_models` | — | Đọc `assets/classification.yml` / `regression.yml` |
| `submit_config` | `/get-data-info` + `/v2/auto/features` + `/v2/auto/data` + `/v2/auto/metrics` | Kiểm bằng `validate_config.py`, KHÔNG train |
| `read_reference` | — | |

## operation-agent

| Tool | Endpoint | Ghi chú |
|---|---|---|
| `start_training` | `POST /v2/auto/jobs/training` | Chỉ nhận `config_id`, tự bật watcher |
| `watch_job` | `POST /get-list-job-by-userId` (định kỳ) | Theo dõi nền tới khi `status ≠ 0` |
| `list_my_jobs` | `POST /get-list-job-by-userId` | Tự lấy `user_id` |
| `get_job_info` | `POST /get-job-info` | Kiểm quyền sở hữu trước |
| `activate_model` | `POST /activate-model` | Kiểm quyền sở hữu + job đã xong |
| `predict` | `POST /inference-model` | ≤ 50 mẫu, soát đủ cột. Backend hiện luôn 403 với job v2 |

## Không phơi cho LLM

| Hàm | Ai gọi | Vì sao |
|---|---|---|
| `login` (qua `ensure_login`) | `chat.py` khi chat ở terminal | Xác thực là việc của hạ tầng, LLM không cầm token. Trên web, agent dùng token của phiên đăng nhập |
| `upload_dataset_file` | `server.py` (`POST /agent/upload`) | LLM không cầm được file |

## Tool chưa viết

| Endpoint | Tool dự kiến | Thuộc agent |
|---|---|---|
| `DELETE /delete-dataset/{id}` | `delete_dataset` | data-agent |
| `POST /get-data-from-uci` | `import_uci_dataset` | data-agent |
| `POST /v2/auto/{job_id}/predictions` | `batch_predict` | operation-agent |
