# Agent HAutoML

Hệ thống đa agent cho AutoML: *"người dùng nhập prompt → các agent thao tác
ngầm → chỉ trả kết quả cuối"*. Đi được trọn vòng: dataset → phân tích →
chọn config → huấn luyện → theo dõi job → kích hoạt → dự đoán.

Sơ đồ: `docs/hautoml-multi-agent-detailed.drawio`, trang **1 · Tổng quan**.

## Kiến trúc

Agent Manager nói chuyện với người dùng và uỷ thác cho 4 sub-agent chuyên trách.
Mỗi agent là **một vòng LLM riêng**: system prompt riêng (SKILL.md của nó), tập
tool riêng, và chỉ Manager thấy lịch sử hội thoại.

```
                         Agent Manager   phân tích · uỷ thác · kiểm định
                               │
      ┌───────────────┬────────┴───────┬──────────────────┐
      ▼               ▼                ▼                  ▼
 ① Prompt Agent  ② Data Agent  ──▶ ③ Model Agent    ④ Operation Agent
   R = JSON 6 khoá  hồ sơ dữ liệu    submit_config     start_training(config_id)
                                         │                  ▲        │
                                         ▼                  │        ▼
                                 validate_config.py ──config hợp lệ  JobWatcher
                                   (kiểm bằng CODE)                  get_job_info
                                                                     tới khi status ≠ 0
```

Dữ liệu đi giữa các agent (`team.Handoff`) do **code** chuyển, không phải LLM
chép lại:

| Mũi tên | Cái gì đi qua | Chốt bằng code |
|---|---|---|
| Prompt Agent → Manager | R: `user, problem, dataset, model, knowledge, service` + `missing` | `normalize_requirements`: chỉ giữ dataset ID có thật, ràng buộc so sánh được |
| Data Agent → Model Agent | kết quả `get_dataset_schema` | tự đọc lại nếu Manager bỏ qua Data Agent |
| Model Agent → Operation Agent | `config_id` | chỉ có `config_id` khi config qua `validate_config.py`, và cột mục tiêu do người dùng chọn (trong R, hoặc tin nhắn nói rõ "target X" / "dự đoán X" - chỉ nhắc tên cột thì không tính) hoặc là ứng viên duy nhất |
| Operation Agent → backend | `start_training(config_id)` | không nhận config tự điền, không chạy trùng; mọi tool tự thử lại lỗi tạm thời của backend (`tools._call`) |
| Watcher → Manager | `[Sự kiện] Job ... đã huấn luyện xong` + kiểm định | so `best_score` với ràng buộc trong R |

```
agent/
├── server.py          ← HTTP + SSE cho trang /agent trên frontend
├── chat.py            ← ChatSession: Agent Manager + lịch sử + phiên đăng nhập
├── cli.py             ← chạy một lượt rồi thoát
│      │
│      ▼
├── team.py            ← uỷ thác cho 4 sub-agent, Handoff giữa các agent
├── agent_openai.py    ← sổ đăng ký tool + vòng tool-calling dùng chung
├── watcher.py         ← theo dõi job nền, kiểm định kết quả theo R
├── events.py          ← kênh sự kiện (tiến độ, job) → SSE
├── prompts.py         ← system prompt riêng cho từng agent
├── skills.py          ← nạp SKILL.md, references/, scripts/
├── providers.py       ← dựng client theo provider, bật Langfuse
│      │
│      ▼
├── tools.py           ← Python thuần. Chuẩn hoá kết quả, che token, không raise
│      │
│      ▼
├── api_client.py      ← chỗ DUY NHẤT gửi HTTP tới FastAPI backend
│
├── skills/            ← mỗi thư mục là MỘT agent
│   ├── agent-manager/ │ prompt-agent/ │ data-agent/ │ model-agent/ │ operation-agent/
│   └── <tên>/SKILL.md + references/ + scripts/
├── requirements.txt   ← thư viện riêng của agent
└── Dockerfile         ← service hautoml_agent trong docker-compose.yaml
```

`skills/<tên>/SKILL.md` của mỗi agent: phần thân là system prompt của agent
đó, `tools:` là tập tool **duy nhất** agent đó được gọi. `references/` nạp theo
nhu cầu qua tool `read_reference`, `scripts/` là code gọi từ `tools.py`.

Các tầng tách rời có chủ đích: `tools.py` + `api_client.py` là Python thuần,
gọi trực tiếp được mà không cần LLM hay API key. Agent không import code
backend - chỉ gọi qua HTTP - nên backend đổi cấu trúc thư mục thì chỉ phải sửa
`api_client.py`.

Các quy tắc được cài sẵn trong `tools.py`:

1. **Token không bao giờ đi qua LLM.** Token nằm trong client, các tool tự dùng.
2. **`user_id` cũng không đi qua LLM.** Các endpoint dữ liệu cần `user_id`, và
   backend trả 403 nếu nó không khớp token. LLM không biết ID thật nên sẽ bịa ra
   -> `_ensure_user_id()` tự gọi `/me` một lần rồi cache trong client.
3. **Tool không raise.** Lỗi thành `{"ok": false, "status_code": ..., "error": ...}`
   để agent đọc được và tự xử lý, thay vì làm vỡ vòng lặp.
4. **Tự kiểm quyền sở hữu job.** `get_job_info`, `activate_model`, `predict` chỉ
   chạy trên job nằm trong danh sách job của chính người dùng - backend kiểm rất
   lỏng (xem "Lỗi phía backend" bên dưới).

## Cài đặt

Chỉ cần cài SDK của nhà cung cấp bạn thực sự dùng:

```bash
pip install openai pyyaml
```

Muốn dùng model của Anthropic thì đi qua OpenRouter với
`LLM_MODEL=anthropic/claude-sonnet-4.6` - không cần SDK riêng.

`httpx`, `python-dotenv`, `pymongo` đã có trong `requirements.txt` của backend.

## Cấu hình

Viết thẳng vào `src/backend/.env` - `providers.py` gọi `load_dotenv()` nên tự
tìm và nạp file này, **không cần `export`**:

```dotenv
LLM_PROVIDER=google
GEMINI_API_KEY=...
```

Nên **để trống `LLM_MODEL`** - khi đó mỗi provider tự dùng model mặc định đúng
của mình. Nếu đặt cứng, slug phải thuộc về provider đang chọn, nếu không sẽ gửi
slug của bên này tới endpoint của bên kia:

```dotenv
# đúng
LLM_PROVIDER=openrouter
LLM_MODEL=anthropic/claude-sonnet-4.6
# sai - slug Claude gửi tới endpoint Google
LLM_PROVIDER=google
LLM_MODEL=anthropic/claude-sonnet-4.6
```

Xem mục "Agent" trong `src/backend/.env.example` để biết đủ các biến. `.env` đã nằm trong `.gitignore` nên key
thật không bị commit.

| Biến | Ý nghĩa |
|---|---|
| `LLM_PROVIDER` | `openrouter` (mặc định), `google`, `openai`, `fpt`, `azure` |
| `LLM_MODEL` | Slug model, mặc định theo provider |
| `OPENROUTER_API_KEY` | Key OpenRouter |
| `GEMINI_API_KEY` | Key Google AI Studio (hoặc `GOOGLE_API_KEY`) |
| `FPT_API_KEY` | Key FPT AI. Provider `fpt` không có model mặc định - bắt buộc đặt `LLM_MODEL` |
| `FPT_BASE_URL` | URL API của FPT, mặc định `https://token-api.fpt.ai/v1`. Đặt đúng URL ghi ở trang lấy key nếu khác |
| `ANTHROPIC_API_KEY` | Key Anthropic |
| `HAUTOML_BASE_URL` | URL backend v1 (không kèm `/api/v1`), mặc định `http://localhost:9999` |
| `HAUTOML_API_PREFIX` | Tiền tố API, mặc định `/api/v1` |
| `AGENT_USER` / `AGENT_PASSWORD` | Chỉ cho chat ở terminal (`agent.chat`, `agent.cli`): tài khoản agent tự đăng nhập. Server cho frontend KHÔNG dùng - luôn dùng token của người đang đăng nhập web |
| `AGENT_CORS_ORIGINS` | Website được gọi agent từ trình duyệt, cách nhau dấu phẩy. Mặc định `http://localhost:3000` |
| `AGENT_TURN_TOKEN_BUDGET` | Trần token cho một lượt chat (Manager + sub-agent cộng lại), mặc định 150000. Vượt trần thì agent dừng và báo người dùng |
| `AGENT_JOB_POLL_SECONDS` | Chu kỳ watcher hỏi trạng thái job, mặc định 20 giây |
| `AGENT_LLM_TIMEOUT` | Thời gian chờ tối đa của MỘT lời gọi LLM (giây), mặc định 300. SDK vẫn tự thử lại lỗi tạm thời |
| `AGENT_HISTORY_FULL_TURNS` | Số lượt chat gần nhất Manager giữ đủ các bước tool, mặc định 4. Lượt cũ hơn chỉ còn câu hỏi và câu trả lời cuối, để phiên dài không vượt trần token |
| `AGENT_MAX_CONCURRENT_TURNS` | Số lượt chat chạy song song tối đa trên server (pool thread riêng), mặc định 32. Lượt vượt mức xếp hàng chờ |
| `HAUTOML_SYSTEM_MODELS_DIR` | Thư mục chứa `classification.yml` / `regression.yml` / `time_series.yml` khi agent chạy tách khỏi backend. Mặc định tự tìm trong `src/backend/assets/` (rồi `assets/system_models/` của cấu trúc cũ) |

### Azure OpenAI

Azure là ngoại lệ so với ba provider kia: xác thực bằng header `api-key` chứ
không phải `Authorization: Bearer`, cần `api-version`, và **"model" thực chất là
tên deployment** bạn tự đặt trên portal. Vì vậy nó dùng class `AzureOpenAI`
riêng - `providers.build_client()` lo việc này, tầng agent không cần biết.

Chỉ có key là chưa đủ, cần 3 thứ nữa:

```dotenv
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<tên-resource>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=<tên-deployment-của-bạn>
# AZURE_OPENAI_API_VERSION=   # bỏ trống -> dùng bản GA 2024-10-21
```

| Biến | Bắt buộc | Ghi chú |
|---|---|---|
| `AZURE_OPENAI_API_KEY` | ✅ | hoặc `AZURE_API_KEY` |
| `AZURE_OPENAI_ENDPOINT` | ✅ | hoặc `AZURE_ENDPOINT` |
| `AZURE_OPENAI_DEPLOYMENT` | ✅ | hoặc `LLM_MODEL`, hoặc `--model` |
| `AZURE_OPENAI_API_VERSION` | — | hoặc `OPENAI_API_VERSION`; mặc định `2024-10-21` |

Thiếu cái nào thì `providers.resolve()` báo rõ cái đó ngay từ đầu, không để đến
lúc gọi API mới lỗi.

Hai lưu ý:

- Biến đã `export` ngoài shell **thắng** giá trị trong `.env` (`load_dotenv()`
  mặc định không ghi đè). Sửa `.env` mà không thấy tác dụng thì kiểm tra
  `echo $LLM_MODEL` xem có biến cũ còn sót không.
- `src/backend/.env` cũng được `docker-compose.yaml` nạp vào container backend,
  nên key LLM sẽ có mặt trong đó. Chạy cục bộ thì không sao, nhưng đừng dùng
  file này cho môi trường production dùng chung.

Slug model thay đổi theo thời gian - tra tại [openrouter.ai/models](https://openrouter.ai/models)
hoặc [ai.google.dev](https://ai.google.dev/gemini-api/docs/models). Nếu gặp lỗi
`model not found`, gần như chắc chắn là slug đã cũ.

## Chạy

### Cách chính - cùng cả hệ thống bằng Docker

Docker Compose cần hỗ trợ `include`. File ở thư mục gốc dùng lại stack API v1
trong `src/backend/deploy/docker-compose.yml`: backend + training consumer,
MongoDB, MinIO, Kafka và MQTT. Frontend được build từ workspace `apps/web`.
Các biến kết nối của stack backend được nạp từ `src/backend/.env` để mật khẩu
MinIO/MQTT khớp với backend. Gradio là tuỳ chọn (`--profile demo`).

```bash
docker compose up -d --build        # ở thư mục gốc repo
```

Service `hautoml_agent` chạy agent server ở cổng 9500, gọi backend qua
`HAUTOML_BASE_URL`. Agent dùng API v1 (`/api/v1/...`, chạy bằng
`src/backend/deploy/docker-compose.yml`, cổng 9999) - image cũ
`optivisionlab/hautoml:v2.2` ở cổng 9996 KHÔNG còn tương thích. Mở http://localhost:3000, đăng nhập, chọn
**Agent AI** ở thanh bên trái (trang `/agent`). Trang chỉ dùng được khi đã đăng nhập: agent thao tác bằng
token của chính phiên web đó.

URL mặc định khi chạy Docker: frontend `http://localhost:3000`, backend
`http://localhost:9999`, agent `http://localhost:9500`. Khi mở web từ máy khác,
đặt `NEXT_PUBLIC_BASE_API`, `NEXT_PUBLIC_AGENT_API`, `NEXTAUTH_URL` theo địa chỉ
mà trình duyệt truy cập được trước khi chạy Compose; đặt `AGENT_CORS_ORIGINS`
trong `src/backend/.env` tương ứng với website đó. NextAuth trong container dùng `INTERNAL_API_URL` để đăng nhập và làm
mới token; phiên web tự kiểm tra token mỗi 60 giây để watcher tiếp tục chạy.

Code agent được mount vào container, sửa xong chỉ cần:

```bash
docker compose restart hautoml_agent     # sửa code
docker compose up -d hautoml_agent       # sửa .env (restart không nạp lại .env)
```

### Chat ở terminal - không cần frontend

```bash
cd src/backend
python -m agent.chat
```

Terminal không có phiên web nên agent tự đăng nhập bằng `AGENT_USER` /
`AGENT_PASSWORD` trong `.env` (tài khoản phải đã xác thực email). Terminal hiện
từng bước: agent nào được giao việc gì, nó gọi tool nào:

```
Bạn > dataset của tôi có những cột gì
  ▸ Data Agent: Liệt kê dataset rồi phân tích cột của dataset duy nhất
      · list_my_datasets({}) ✓
      · get_dataset_schema({"dataset_id": "6ac4be1f..."}) ✓
Agent > Dataset aus_credit_train có 552 dòng, 15 cột: A1 ... A15.
```

Lệnh trong lúc chat: `/cost` (token đã dùng), `/tools` (tool của từng agent),
`/jobs` (job đang theo dõi), `/reset` (xoá lịch sử, giữ đăng nhập), `/exit`.

Chạy một lượt rồi thoát, hoặc đổi provider/model ngay trên dòng lệnh:

```bash
python -m agent.cli "tôi có dataset nào"
python -m agent.cli --provider google "..."
```

## Tool theo agent

| Agent | Tool | Endpoint / ghi chú |
|---|---|---|
| Manager | `ask_prompt_agent` `ask_data_agent` `ask_model_agent` `ask_operation_agent` `ask_sql_agent` | Uỷ thác, không gọi API trực tiếp |
| Prompt Agent | *(không tool)* | Một lượt LLM trả JSON R |
| Data Agent | `list_my_datasets` | `GET /datasets` (lật hết các trang) |
| | `get_dataset_info` | `GET /datasets/{id}` - metadata, **không có tên cột** |
| | `get_dataset_schema` | `/datasets/{id}` + `/data` + `/features` cho cả classification lẫn regression; cột ngày giờ đọc được thì thêm `time_columns` và ứng viên target time_series. Kết quả tự chuyển cho Model Agent |
| Model Agent | `list_metrics` | Đọc `metric_list` trong yml (backend v1 không có endpoint metric) |
| | `list_models` | Đọc `assets/classification.yml` / `regression.yml` / `time_series.yml` qua `scripts/model_catalog.py` |
| | `submit_config` | Dựng config + `validate_config.py`. Hợp lệ → `config_id`. Chặn cột mục tiêu người dùng chưa chọn khi có nhiều ứng viên. **Không train** |
| Operation Agent | `start_training` | `POST /datasets/{id}/training`, chỉ nhận `config_id`. Tự bật watcher |
| | `watch_job` | Bật theo dõi nền cho job đang chạy |
| | `list_my_jobs` | `GET /inference/jobs`, chỉ job của chính người dùng |
| | `get_job_info` | Tìm trong `GET /inference/jobs` (không có endpoint xem một job) |
| | `activate_model` | `PUT /inference/models/{id}/activation`, chỉ job của mình và đã xong |
| | `predict` | `POST /inference/models/{id}/predict`, tối đa 50 mẫu, soát đủ cột trước khi gửi |
| Data + Model | `read_reference` | Đọc `skills/<tên>/references/*.md` |
| SQL Agent | `list_database_connections` | `GET /database-connections` - chỉ id, tên, loại; không host / mật khẩu |
| | `list_database_tables` `describe_database_table` | `/database-connections/{id}/tables`, `/describe` - metadata + vài dòng mẫu |
| | `preview_sql_query` `preview_mongo_query` | `/database-connections/{id}/preview` - truy vấn chỉ-đọc đã kiểm, ≤ 100 dòng (LLM thấy 20), trả `preview_id` |
| | `import_database_query` | `/database-connections/{id}/import` - kết quả thành dataset riêng (trần 50.000 dòng), ghi `Handoff.imported_datasets` |

## Nguồn dữ liệu ngoài: SQL Agent và Database Adapter

Ứng với khối "Database Adapter → SubAgent Generate SQL/NoSQL → Super Agent" của hướng nghiên
cứu HAgent + AutoML. Hỗ trợ **SQLite, DuckDB, PostgreSQL, MySQL, MongoDB**; các engine SQL khác
của `src/adapters/` vẫn dùng được cho tính năng nhập nguyên bảng cũ, chưa mở cho truy vấn tự do.

```
Người dùng tạo kết nối (giao diện / API, có mật khẩu)  ──▶  tbl_DatabaseConnection (mật khẩu mã hoá Fernet)
Manager ──ask_sql_agent──▶ SQL Agent:
   list_database_connections → list_database_tables → describe_database_table   (metadata)
   → preview_sql_query / preview_mongo_query   (backend: query_policy kiểm + query_runner chạy chỉ-đọc)
   → import_database_query                      (parquet → MinIO → tbl_Data, trả dataset_id thật)
Manager nhận imported_datasets ──▶ Prompt → Data → Model → Operation Agent (luồng AutoML có sẵn)
```

An toàn, theo lớp (mỗi lớp tự đứng được nếu lớp khác sót):

1. **Không lộ bí mật**: LLM chỉ cầm `connection_id` / `preview_id`. Mật khẩu mã hoá bằng
   `DB_CONNECTION_ENCRYPTION_KEY` (thiếu khoá = tính năng tắt), không bao giờ trả qua API.
   Kết nối của người khác trả 404.
2. **Bộ kiểm truy vấn** (`src/adapters/query_policy.py`): phân tích cú pháp bằng sqlglot, đúng
   một câu SELECT/UNION/CTE không đệ quy; chặn mọi lệnh ghi (kể cả trong CTE), `INTO`, `ATTACH`,
   `PRAGMA`, `COPY`, hàm đọc file/extension (`read_csv`, `load_extension`...), hàm bảng, bảng
   ngoài kết nối, schema khác. Câu được sqlglot sinh lại rồi bọc `SELECT * FROM (...) LIMIT n` -
   chạy câu chuẩn hoá, không chạy chuỗi gốc. MongoDB: chỉ `find` và stage
   `$match/$project/$sort/$limit/$skip/$group/$unwind/$count`; cấm `$where/$function/$out/$merge/$lookup`... ở mọi độ sâu.
3. **Bộ chạy chỉ-đọc** (`src/adapters/query_runner.py`): mỗi truy vấn chạy trong TIẾN TRÌNH CON
   có trần bộ nhớ (`DB_SOURCE_WORKER_MEMORY_MB`) và bị kill khi quá hạn - hàm như
   `repeat('x', 2e9)` cấp phát GB trong một dòng, `memory_limit` của DuckDB không chặn được.
   SQLite mở `mode=ro` + `query_only` + authorizer chặn ghi, catalog (`sqlite_master`...),
   database khác `main` và hàm nguy hiểm (danh sách bảng được phép do bộ kiểm ở bước 2 bảo đảm);
   DuckDB `read_only` + tắt truy cập file/mạng ngoài + khoá cấu hình. Kết quả vượt trần dung lượng
   (preview 8 MiB, import 64 MiB) bị từ chối. File database chỉ trong `DB_SOURCE_FILES_DIR` (chặn
   `..`, đường dẫn tuyệt đối, symlink). Endpoint cũ `/datasets/database/*` (giao diện còn dùng) với
   SQLite/DuckDB cũng đi qua bộ chạy này - view `read_csv('/file-ngoài')` không đọc được.
   MongoDB **mặc định tắt**: chỉ host trong `DB_SOURCE_MONGO_ALLOWED_HOSTS`, và database của chính
   HAutoML (`MONGODB.NAME`) luôn bị chặn (nó chứa tài khoản của mọi người).
   **PostgreSQL / MySQL** (`src/adapters/sql_server.py`, cũng trong tiến trình con) **mặc định tắt**:
   chỉ `host` / `host:port` trong `DB_SOURCE_SQL_ALLOWED_HOSTS` (ghim cả port; chuỗi nhiều host
   hay unix socket không lọt); database / schema hệ thống bị chặn. Ở server: transaction CHỈ ĐỌC,
   `statement_timeout` / `max_execution_time` (server tự dừng truy vấn khi bị huỷ), ép chế độ chuỗi
   khớp với sqlglot (Postgres `standard_conforming_strings=on`; MySQL bỏ `ANSI_QUOTES`,
   `NO_BACKSLASH_ESCAPES`, `PIPES_AS_CONCAT`) rồi đọc lại để xác nhận; MySQL tắt `LOAD DATA LOCAL`
   và nhiều câu một lần. Bộ kiểm thêm cho hai dialect này: cấm hint `/*+ */`, `@@biến` / `@biến`,
   `$1`, tiền tố bảng mã, hàm đọc file / ngủ / khoá / thông tin server (`pg_read_file`, `pg_sleep`,
   `dblink`, `query_to_xml`, `LOAD_FILE`, `SLEEP`, `BENCHMARK`, `version()`...) và `REPEAT`/`LPAD`
   (DoS bộ nhớ server). Tham số `:ten` được gắn thành literal trong cây cú pháp; mọi bảng được viết
   lại thành đúng tên trong metadata (Postgres kèm schema) để server không phân giải nhầm sang
   `pg_catalog`. Lỗi đăng nhập không lộ host / tài khoản; IP trong thông báo lỗi bị che.
4. **Giới hạn và toàn vẹn**: preview ≤ 100 dòng, import ≤ 50.000 dòng; vượt trần thì import trả 409
   `RESULT_TRUNCATED`. Agent KHÔNG tự gửi `allow_truncated` (LLM không được tự cấp lời đồng ý): người
   dùng muốn lấy phần đầu thì truy vấn được thêm `LIMIT 50000` (thấy rõ trong bản xem trước); API
   cho người dùng (giao diện) vẫn có `allow_truncated`. Mỗi preview gắn sẵn một
   `dataset_id`: gửi lại, hay tiến trình chết giữa chừng rồi thử lại, đều trả đúng dataset cũ;
   khoá nhập có hạn (10 phút). Ghi metadata báo lỗi thì tra lại theo `_id` trước khi xoá file.
   Kiểu dữ liệu giữ đúng: số nguyên có NULL dùng Int64, DECIMAL đổi sang số thực có ghi chú,
   cột trộn kiểu / nhị phân / lồng bị báo rõ. Preview hết hạn sau 15 phút hoặc khi kết nối đổi.
   Kết quả tối đa 200 cột, tên cột ≤ 128 ký tự (mô tả bảng thì bỏ cột vượt trần và báo
   `omitted_columns`). Phần đưa vào context LLM còn bị rút gọn thêm: 20 dòng, ô ≤ 200 ký tự, lồng
   ≤ 3 tầng / 10 phần tử, tổng dòng ≤ 12.000 ký tự, danh sách cột / bảng ≤ 6.000 ký tự; tên cột
   không bao giờ bị cắt hay đổi - cột không vừa thì ẩn và đếm.

Cấu hình backend (`src/backend/.env`): `DB_CONNECTION_ENCRYPTION_KEY`, `DB_SOURCE_FILES_DIR`,
`DB_SOURCE_MONGO_ALLOWED_HOSTS` (trống = tắt MongoDB), `DB_SOURCE_SQL_ALLOWED_HOSTS` (trống = tắt
PostgreSQL / MySQL; vd `pg.lab.local,mysql.lab.local:3307`), `DB_SOURCE_QUERY_TIMEOUT_SECONDS`,
`DB_SOURCE_WORKER_MEMORY_MB`. Tài khoản database **phải chỉ có quyền SELECT** trên đúng các bảng
muốn chia sẻ - bộ kiểm cú pháp không thay được quyền của database; view được cấp quyền chạy với
quyền của chủ view, nên chỉ cấp view mà bạn muốn agent đọc.

Test với PostgreSQL 16 / MySQL 8.4 thật (dữ liệu Glass thật, user chỉ-đọc, user có quyền ghi để
kiểm transaction chỉ-đọc, bảng canary không cấp quyền, server cố ý để chế độ chuỗi bất lợi):

```bash
docker compose -f src/backend/tests/sql_sources/docker-compose.yml up -d --wait
docker run --rm --network host -v $PWD:/repo -w /repo/src/backend/tests hautoml-backend-test:local \
    python -m pytest integration/test_sql_server_sources.py   # HAUTOML_REQUIRE_SQL_SERVERS=1: bắt buộc có server
docker compose -f src/backend/tests/sql_sources/docker-compose.yml down -v
```

## HTTP API (`agent/server.py`, cổng 9500)

| Endpoint | Dùng cho |
|---|---|
| `GET /health` | HTTP 200 khi server đang chạy; `llm_ready` cho biết cấu hình LLM đã đủ. Thiếu cấu hình trả `status: degraded` + `configuration_error`, không làm hỏng upload. Không gọi LLM để kiểm tra key/quota |
| `POST /agent/chat` | Một lượt chat, trả JSON `{reply, agents, tools, watching, ...}` |
| `POST /agent/chat/stream` | Như trên nhưng SSE: `session` (`session_id`, `start_seq`), các sự kiện tiến độ (`agent_start`, `tool_call`, `config_checked`, `job_started`...), rồi `reply` hoặc `error`. Body nhận thêm `after` (seq cuối frontend đã nhận - phát lại sự kiện bị lỡ) và `turn_id` (server gắn lại vào `turn_start` / `turn_done` (kèm `reply`) / `turn_failed`, để luồng đứt giữa chừng vẫn nhận được kết quả qua `/agent/events`). Im lặng lâu thì gửi `: ping` |
| `POST /agent/events` | SSE sự kiện nền, mở đầu bằng `hello` (`last_seq` hiện tại) (`job_watch`, `job_status`, `job_done`, `job_failed`, `job_watch_timeout`, `job_watch_warning` / `job_watch_resumed`, `auto_activate_changed`, `turn_done` / `turn_failed`). Đóng sau ~55 giây bằng `reconnect`; frontend mở lại kèm token mới. `hello` / `reconnect` kèm `watching`, `auto_activate` và `auto_activate_constraints` (job -> điều kiện sẽ kiểm trước khi tự kích hoạt; rỗng = bất kể điểm), `job_watch` / `job_status` / `auto_activate_changed` cũng mang `auto_activate_constraints` |
| `POST /agent/auto-activate` | Bật/tắt TỰ kích hoạt model khi một job đang chạy xong (`job_id`, `enabled`) - nút "Huỷ tự kích hoạt" trên thẻ job. Operation Agent có tool `set_auto_activate` cùng tác dụng khi người dùng đổi ý qua chat (bật kèm `constraints` = điều kiện người dùng nêu, được kiểm lúc job xong; phần trăm đổi sang tỉ lệ 0-1; điều kiện không kiểm được thì không bật và huỷ lời hứa đang bật; kết quả - kể cả khi lỗi - trả `checked_constraints`) |
| `POST /agent/upload` | Tải dataset từ trang /agent (trang 4 của sơ đồ) |
| `POST /agent/reset` | Xoá lịch sử, giữ đăng nhập và job đang theo dõi |
| `POST /agent/token` | Frontend gửi access token mới ngay khi NextAuth làm mới, kể cả giữa một lượt chat |

SSE dùng POST thay vì `EventSource` để token nằm trong body, không lên URL.
`/agent/events` đóng định kỳ có chủ đích: token người dùng chỉ sống 15 phút
(`ACCESS_EXPIRE`) trong khi job chạy hàng giờ - mỗi lần frontend mở lại, token
mới được gán vào client mà watcher đang dùng. Nhưng kênh này chỉ mở khi có job
được theo dõi, nên token mới còn đi qua `/agent/token`: thiếu nó, một lượt chat
dài qua lúc token hết hạn sẽ nhận 401 giữa lượt.

Mọi lượt chat chạy trong thread (`asyncio.to_thread`), không chạy thẳng trong
event loop - một lượt gọi LLM hàng chục lần, chạy trong loop là mọi request
khác (kể cả SSE) đứng chờ.

### Hạn mức và chốt an toàn (review bảo mật 2026-11-08, Codex + Claude)

| Chốt | Giá trị |
|---|---|
| Body JSON (mọi endpoint trừ upload), chặn TRƯỚC khi parse và kiểm token | 256 KB; `message` ≤ 20.000 ký tự |
| Phiên / người dùng; lượt đang chạy hoặc chờ / người dùng | 8 phiên (vượt thì dọn phiên rảnh cũ nhất của CHÍNH người đó, không dọn được thì 429); 2 lượt (429) |
| Toàn server | 200 phiên, lượt chờ ≤ 4 × số worker (503). Không bao giờ dọn phiên đang theo dõi job của người khác để nhường chỗ |
| Upload | 8 upload xử lý cùng lúc (503), pool riêng 4 thread gọi backend; .xlsx giải nén ≤ 300 MB / 10.000 thành phần (chặn zip bomb, backend kiểm lại) |
| ID do LLM truyền vào URL (dataset / kết nối / job) | chỉ `[A-Za-z0-9_-]{1,64}`, escape - không thoát sang endpoint khác bằng `../` |
| Hành động thật cần người dùng nói ra | bật / tắt model (`activate_model`), tự kích hoạt, chạy lại đúng cấu hình đã chạy, cột mục tiêu khi có nhiều ứng viên. Dữ liệu (tên cột, ô, lỗi job) chỉ là dữ liệu - ngữ cảnh của sub-agent nằm ở tin user, không ở system prompt |
| Context LLM | mỗi kết quả tool ≤ 40.000 ký tự; ô dữ liệu ≤ 200 ký tự; ≤ 8 tool / bước; lượt cũ ≤ 30, mỗi tin cũ ≤ 2.000 ký tự; sự kiện job ≤ 8.000 ký tự; provider không trả `usage` thì ước lượng token để trần lượt vẫn có hiệu lực |

**Chốt ý định (train / bật / tắt model / chạy lại cấu hình trùng)** nhận ra yêu cầu của người dùng bằng
từ khoá tiếng Việt / Anh trong 6 tin gần nhất (bỏ dòng `[Sự kiện]`), bắt thêm phủ định đứng sát ("đừng
train", "không kích hoạt", "hủy kích hoạt"). Mục đích là chặn prompt injection - hành động chỉ do dữ liệu
/ kết quả tool ra lệnh. Câu ghép nhiều mệnh đề và chọn job nào trong số job người dùng đã biết là việc của
LLM. Cách nói lạ mà từ khoá không bắt được thì agent chỉ DỪNG và hỏi lại người dùng, không làm sai.
Trả lời "Có" / "OK" một mình KHÔNG đủ: người dùng phải nói rõ hành động ("Kích hoạt model", "Train lại") -
Manager được dặn gợi ý đúng câu xác nhận đó. Mỗi lời "chạy lại" chỉ cho MỘT lần chạy lại (phải mới hơn job
trùng gần nhất; mốc này được dời theo khi lịch sử bị lược / lượt lỗi bị bỏ / reset).

**Giới hạn đã biết:** phiên, job đang theo dõi và lời hứa "train xong tự kích hoạt"
chỉ nằm trong RAM của agent server. Server khởi động lại thì mất - job vẫn chạy trên
backend nhưng không ai tự kích hoạt; trang `/agent` báo "phiên mới" khi tải lại. Lưu
bền các trạng thái này (vào MongoDB) là việc riêng chưa làm.

## Kiểm tra hồi quy

Bộ test agent chạy độc lập, không cần cài thư viện ML của backend, không gọi
LLM thật và không tạo job train:

```bash
cd src/backend
python -m pip install -r agent/tests/requirements.txt
python -m pytest -c agent/tests/pytest.ini agent/tests
```

Các ca kiểm tra gồm đăng ký tool/skill, Manager uỷ thác cho Data Agent, payload
API v1, quyền sở hữu job, chặn target không hợp lệ (kể cả khi không có target
nào hợp lệ), chặn target lọt vào feature, lưu câu trả lời khi hết số bước và
HTTP health/auth. Kiểm tra trọn luồng train/predict vẫn cần backend, consumer,
storage và tài khoản thật.

## Khác biệt của backend v1 mà agent phải xử lý

| Backend v1 | Agent xử lý |
|---|---|
| Dataset chỉ có `dataType = "table"`, không ghi loại bài toán | `get_dataset_schema` lấy ứng viên target cho cả hai loại; loại bài toán suy từ cột mục tiêu (`tools.infer_problem_type`) hoặc lấy từ lời người dùng |
| Config train dùng `timeout`, không phải `max_time` | Agent vẫn gọi là `max_time`; đổi tên lúc gửi (`tools._backend_training_config`) |
| Không có endpoint metric | Đọc `metric_list` trong yml, dự phòng bằng `tools.DEFAULT_METRICS` |
| Không có endpoint xem một job | Tìm trong danh sách job |
| Tài khoản admin nhận job của mọi người ở `GET /inference/jobs` | `tools._own_jobs` lọc theo `user.id` |
| Mọi response bọc trong `{success, data, meta}` | `api_client` tự bóc và tự lật trang |

## Lỗi thường gặp

| Triệu chứng | Nguyên nhân & cách xử lý |
|---|---|
| `RuntimeError: Chưa có API key cho provider 'openrouter'` | `.env` có key của provider khác nhưng thiếu `LLM_PROVIDER`. Mặc định là `openrouter`. |
| `error: externally-managed-environment` khi `pip install` | Debian/Ubuntu chặn pip vào system Python (PEP 668). Dùng venv: `python3 -m venv .venv && source .venv/bin/activate`. |
| `command not found: python` | Hệ thống chỉ có `python3`. Activate venv thì `python` mới tồn tại. |
| `400 ... missing a thought_signature in functionCall parts` | Gemini gắn `thought_signature` vào từng tool call và bắt buộc nhận lại ở lượt sau. `_assistant_message()` đã copy `model_extra` để giữ field này - đừng rebuild tool call mà bỏ nó đi. |
| `503 UNAVAILABLE / high demand` | Model quá tải, lỗi tạm thời. Client đã đặt `max_retries=5`; nếu vẫn lỗi thì đợi hoặc đổi model. |
| Model trả về `content=None` | Model có thinking (như `gemini-3.8-flash`) tiêu hết `max_tokens` vào suy luận nội bộ. Đừng đặt `max_tokens` thấp - code hiện không set nên dùng mặc định của provider. |
| Azure: `DeploymentNotFound` | `LLM_MODEL`/`AZURE_OPENAI_DEPLOYMENT` phải là **tên deployment**, không phải tên model (`gpt-4o`). Xem đúng tên trong Azure portal. |
| Azure: lỗi liên quan `api-version` hoặc model không được hỗ trợ | Model mới cần `api-version` mới hơn mặc định `2024-10-21`. Đặt `AZURE_OPENAI_API_VERSION`. |

## Theo dõi chi phí

### Đếm token - luôn bật, không cần cài gì

Mỗi lượt chạy in ra tổng token của **toàn bộ** lượt, không phải của lời gọi cuối:

```
[cost] 3 lượt gọi LLM | prompt 5545 + completion 192 + thinking 219 = 5956 token
```

Ba điều đọc được từ dòng này:

- **Một lượt agent = nhiều lời gọi LLM.** Mỗi vòng lặp một lần, nên nhìn con số
  của lời gọi cuối là sai hoàn toàn.
- **`prompt` thường áp đảo.** 5545 so với 192 completion, vì 12 schema tool +
  system prompt + toàn bộ lịch sử được gửi lại *mỗi vòng*. Muốn giảm tiền thì
  giảm số tool hoặc rút gọn schema, chứ không phải rút gọn câu trả lời.
- **`thinking` được tách riêng.** Model có thinking (như `gemini-3.8-flash`)
  có `total > prompt + completion`. Phần chênh là token suy luận nội bộ, và nó
  **vẫn bị tính tiền**.

### Langfuse - biểu đồ chi phí, tuỳ chọn

```bash
pip install langfuse
```

Thêm vào `src/backend/.env` (lấy key miễn phí ở [cloud.langfuse.com](https://cloud.langfuse.com)
→ Project Settings → API Keys):

```dotenv
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

Có đủ **cả hai** key thì tự bật, thiếu thì agent chạy như cũ và không cần cài
`langfuse`. Khi bật, mỗi lượt in thêm link trace:

```
[cost] Langfuse: https://cloud.langfuse.com/project/.../traces/...
```

Toàn bộ lời gọi LLM của một lượt được gộp vào **một trace** qua
`start_as_current_observation`, nếu không thì mỗi lời gọi thành một trace rời và
không thấy được tổng chi phí của cả lượt.

**Cảnh báo về giá tiền.** Langfuse tính tiền bằng cách tra bảng giá theo tên
model. Các model mới hoặc slug lạ (`gemini-3.8-flash`, slug OpenRouter dạng
`anthropic/...`) có thể **không có trong bảng giá** → trace vẫn ghi token đầy đủ
nhưng cột cost hiện 0. Khi đó vào Langfuse → Settings → Models để tự khai giá
cho model đó. Token thì luôn chính xác vì lấy trực tiếp từ response.

**Chi tiết cần biết:** `langfuse.openai` không trả về class con - nó
monkey-patch `chat.completions.create` của thư viện openai ngay lúc import. Nên
`type(client)` vẫn là `openai.OpenAI`; đừng dùng tên class để kiểm tra tracing
có bật. Cũng vì thế `build_client()` import có điều kiện: không cấu hình
Langfuse thì không patch gì cả.

## `get_dataset_schema` - hai cái bẫy

Tool này gộp bốn lời gọi vì không có endpoint nào trả đủ một mình:
`/datasets/{id}` cho metadata, `/datasets/{id}/data` cho preview, và
`/datasets/{id}/features` hai lần (classification, regression) cho danh sách cột.
Không gọi lần thứ ba cho time_series: backend chọn target time_series theo đúng
luật của regression, nên ứng viên được suy từ regression trừ cột thời gian.

**Bẫy 1 - `features` không phải danh sách đặc trưng.** `/datasets/{id}/features` trả
`{tên_cột: bool}` với key là *tất cả* cột, còn value là "cột này làm **biến mục
tiêu** được không". Với `glass.csv` + classification, kết quả là
`{"RI": false, ..., "Type": true}` - nghĩa là chỉ `Type` làm target được, chứ
KHÔNG phải `RI` vô dụng. Đọc sai chỗ này là loại bỏ hết đặc trưng đầu vào. Vì
thế output của tool có trường `note` nói rõ điều đó cho LLM.

**Bẫy 2 - đừng đổ cả preview vào context.** `/datasets/{id}/data` trả 50 dòng. Dataset
rộng vài trăm cột thì 50 dòng là quá nhiều token. Tool chỉ trả `sample_rows`
(mặc định 3 dòng) cộng thống kê từng cột (kiểu, số giá trị khác nhau, số giá trị
thiếu, 5 giá trị mẫu) - đủ để LLM chọn `target`/`list_feature` mà không phình
context. Thống kê tính trên 50 dòng preview, không phải toàn bộ dataset.

## Mở rộng

Thêm tool cho một agent:

1. Thêm method vào `HAutoMLClient` (`api_client.py`).
2. Thêm hàm bọc vào `tools.py` - trả dict, không raise.
3. Khai schema bằng `_tool(...)` trong `TOOL_SCHEMAS` và một dòng vào `_DISPATCH`
   (`agent_openai.py`). Tool cần trạng thái phiên thì viết method trong
   `team.AgentTeam` và thêm tên vào `SESSION_TOOLS`.
4. Thêm tên tool vào `tools:` trong SKILL.md của **đúng agent** dùng nó. Không
   khai ở đâu thì validator báo mồ côi:

```bash
python -c "from agent import skills, agent_openai; print(skills.validate(skills.load_skills(), agent_openai.known_tools()))"
```

Thêm một sub-agent: tạo `skills/<tên>/SKILL.md`, thêm tên vào `SUBAGENTS`
(`prompts.py`), thêm tool `ask_<tên>` cho Manager và method tương ứng trong
`AgentTeam`.

## Chi phí

Một lượt huấn luyện trọn luồng gọi LLM khoảng **15 lần** (Manager 5, Prompt 1,
Data 2, Model 3-4, Operation 2-3) thay vì ~5 lần như khi mọi skill nằm chung một
vòng lặp. Đổi lại, mỗi lời gọi gửi đi ít chữ hơn: mỗi agent chỉ mang SKILL.md và
schema tool của chính nó (2.5-3.8 nghìn ký tự prompt), Prompt Agent không gửi
schema tool nào. Câu hỏi tra cứu đơn giản đi Manager → một sub-agent → Manager,
khoảng 4 lời gọi. Số đo thật in ở dòng `[cost]` sau mỗi lượt.
