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
| Model Agent → Operation Agent | `config_id` | chỉ có `config_id` khi config qua `validate_config.py` |
| Operation Agent → backend | `start_training(config_id)` | không nhận config tự điền, không chạy trùng |
| Watcher → Manager | `[Sự kiện] Job ... đã huấn luyện xong` + kiểm định | so `best_score` với ràng buộc trong R |

```
agent/
├── server.py          ← HTTP + SSE cho khung chat trên frontend
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
| `LLM_PROVIDER` | `openrouter` (mặc định), `google`, `openai`, `azure` |
| `LLM_MODEL` | Slug model, mặc định theo provider |
| `OPENROUTER_API_KEY` | Key OpenRouter |
| `GEMINI_API_KEY` | Key Google AI Studio (hoặc `GOOGLE_API_KEY`) |
| `ANTHROPIC_API_KEY` | Key Anthropic |
| `HAUTOML_BASE_URL` | URL backend, mặc định `http://localhost:9996` |
| `AGENT_USER` / `AGENT_PASSWORD` | Chỉ cho chat ở terminal (`agent.chat`, `agent.cli`): tài khoản agent tự đăng nhập. Server cho frontend KHÔNG dùng - luôn dùng token của người đang đăng nhập web |
| `AGENT_CORS_ORIGINS` | Website được gọi agent từ trình duyệt, cách nhau dấu phẩy. Mặc định `http://localhost:3000` |
| `AGENT_TURN_TOKEN_BUDGET` | Trần token cho một lượt chat (Manager + sub-agent cộng lại), mặc định 150000. Vượt trần thì agent dừng và báo người dùng |
| `AGENT_JOB_POLL_SECONDS` | Chu kỳ watcher hỏi trạng thái job, mặc định 20 giây |
| `HAUTOML_SYSTEM_MODELS_DIR` | Thư mục chứa `classification.yml` / `regression.yml` khi agent chạy tách khỏi backend. Mặc định tự tìm trong `src/backend/assets/` (rồi `assets/system_models/` của cấu trúc cũ) |

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

```bash
docker compose up -d --build        # ở thư mục gốc repo
```

Service `hautoml_agent` chạy agent server ở cổng 9500, gọi backend qua
`http://hautoml-toolkit:9996`. Mở http://localhost:3000, đăng nhập, bấm nút
chat ở góc phải dưới. Khung chat chỉ hiện khi đã đăng nhập: agent thao tác bằng
token của chính phiên web đó.

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
| Manager | `ask_prompt_agent` `ask_data_agent` `ask_model_agent` `ask_operation_agent` | Uỷ thác, không gọi API trực tiếp |
| Prompt Agent | *(không tool)* | Một lượt LLM trả JSON R |
| Data Agent | `list_my_datasets` | `POST /get-list-data-by-userid`, tự lấy `user_id` |
| | `get_dataset_info` | `GET /get-data-info` - metadata, **không có tên cột** |
| | `get_dataset_schema` | `/get-data-info` + `/v2/auto/features` + `/v2/auto/data`. Kết quả tự chuyển cho Model Agent |
| Model Agent | `list_metrics` | `GET /v2/auto/metrics` |
| | `list_models` | Đọc `assets/classification.yml` / `regression.yml` qua `scripts/model_catalog.py` |
| | `submit_config` | Dựng config + `validate_config.py`. Hợp lệ → `config_id`. **Không train** |
| Operation Agent | `start_training` | `POST /v2/auto/jobs/training`, chỉ nhận `config_id`. Tự bật watcher |
| | `watch_job` | Bật theo dõi nền cho job đang chạy |
| | `list_my_jobs` | `POST /get-list-job-by-userId` |
| | `get_job_info` | `POST /get-job-info`, có kiểm quyền sở hữu |
| | `activate_model` | `POST /activate-model`, chỉ job của mình và đã xong |
| | `predict` | `POST /inference-model`, tối đa 50 mẫu, soát đủ cột trước khi gửi |
| Data + Model | `read_reference` | Đọc `skills/<tên>/references/*.md` |

## HTTP API (`agent/server.py`, cổng 9500)

| Endpoint | Dùng cho |
|---|---|
| `POST /agent/chat` | Một lượt chat, trả JSON `{reply, agents, tools, watching, ...}` |
| `POST /agent/chat/stream` | Như trên nhưng SSE: sự kiện tiến độ (`agent_start`, `tool_call`, `config_checked`, `job_started`...) rồi `reply` |
| `POST /agent/events` | SSE sự kiện nền (`job_status`, `job_done`, `job_failed`). Đóng sau ~55 giây bằng `reconnect`; frontend mở lại kèm token mới |
| `POST /agent/upload` | Tải dataset từ khung chat (trang 4 của sơ đồ) |
| `POST /agent/reset` | Xoá lịch sử, giữ đăng nhập và job đang theo dõi |

SSE dùng POST thay vì `EventSource` để token nằm trong body, không lên URL.
`/agent/events` đóng định kỳ có chủ đích: token người dùng chỉ sống 15 phút
(`ACCESS_EXPIRE`) trong khi job chạy hàng giờ - mỗi lần frontend mở lại, token
mới được gán vào client mà watcher đang dùng.

Mọi lượt chat chạy trong thread (`asyncio.to_thread`), không chạy thẳng trong
event loop - một lượt gọi LLM hàng chục lần, chạy trong loop là mọi request
khác (kể cả SSE) đứng chờ.

## Lỗi phía backend mà agent đang lách

Backend được giữ nguyên, nên agent phải tự che chắn:

| Endpoint | Vấn đề | Agent xử lý |
|---|---|---|
| `POST /activate-model` | Không kiểm quyền sở hữu - ai đăng nhập cũng bật/tắt được job của người khác | `tools.activate_model` kiểm job thuộc người dùng trước |
| `POST /get-job-info` | Chỉ kiểm người gọi có *một* job bất kỳ | `tools.get_job_info` kiểm job thuộc người dùng trước |
| `POST /inference-model` | So `job.get("user_id")` nhưng job v2 lưu chủ ở `user.id` → **luôn 403** | `predict` trả lỗi kèm `note` giải thích. Sửa ở `app.py`: `job.get("user", {}).get("id")` |

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

Tool này gộp ba endpoint vì không có endpoint nào trả đủ một mình: `/get-data-info`
cho metadata, `/v2/auto/features` cho danh sách cột, `/v2/auto/data` cho preview.

**Bẫy 1 - `features` không phải danh sách đặc trưng.** `/v2/auto/features` trả
`{tên_cột: bool}` với key là *tất cả* cột, còn value là "cột này làm **biến mục
tiêu** được không". Với `glass.csv` + classification, kết quả là
`{"RI": false, ..., "Type": true}` - nghĩa là chỉ `Type` làm target được, chứ
KHÔNG phải `RI` vô dụng. Đọc sai chỗ này là loại bỏ hết đặc trưng đầu vào. Vì
thế output của tool có trường `note` nói rõ điều đó cho LLM.

**Bẫy 2 - đừng đổ cả preview vào context.** `/v2/auto/data` trả 50 dòng. Dataset
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
