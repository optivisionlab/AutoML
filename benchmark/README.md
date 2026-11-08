# Bộ benchmark agent HAutoML (protocol v5)

Bộ này đo hệ thống multi-agent của HAutoML (`src/backend/agent`) trên LLM và backend thật. Kết quả đặt cạnh baseline không dùng LLM, và cạnh số liệu bài AutoML-Agent (Trirat và cs., ICML 2025).

Protocol chi tiết (định nghĩa từng ca, quy tắc chấm, lịch sử thay đổi) nằm ở [benchmark.md](../benchmark.md). File này là hướng dẫn dùng.

## 1. Hệ thống được đo

Phần này chỉ ghi những gì đã kiểm trong code ngày 2026-11-08, nhánh `feat/benchmark_agent`, commit 493a69a. Điểm nào còn là giả định thì có ghi rõ.

| Thành phần | Thực tế trong code | Điểm benchmark đo |
|---|---|---|
| Agent Manager | Vòng LLM riêng, chỉ có tool `ask_*` (uỷ thác) - `skills/agent-manager/SKILL.md` | Số lần uỷ thác, uỷ thác thành công, trần bước |
| Prompt Agent | Một lời gọi LLM trả JSON R (`team.ask_prompt_agent`), code chuẩn hoá (`normalize_requirements`) | R có/không, ràng buộc trong R → watcher kiểm định |
| Data Agent | Đọc dataset, schema (`get_dataset_schema`) | Đọc đúng dataset (A02, T06), không bịa schema (A04) |
| Model Agent | Chốt config qua `submit_config` → `validate_config.py` | Config hợp lệ lần đầu, đúng 7 trường, chặn config sai (B03–B06) |
| Operation Agent | Đề nghị train / bật model, theo dõi job, predict | Thẻ đề nghị, predict đúng job và đúng mẫu |
| SQL Agent (mới) | Kết nối đã lưu → bảng → truy vấn chỉ đọc → nhập thành dataset | Nhóm S: bảng/cột đúng, số liệu đúng, dataset nhập đúng, không ghi |
| Database adapter (mới) | `src/backend/src/adapters`, API `/database-connections`; sqlglot + tiến trình con chỉ đọc | S07 (câu ghi bị chặn, bảng không đổi), số dòng import |
| Thẻ xác nhận (mới) | Train / bật / tắt / tự kích hoạt chỉ chạy khi người dùng bấm (`actions.py`) | Người dùng mô phỏng, đề nghị trái ý |
| Engine AutoML | Kafka consumer, sklearn: 6 model phân loại, 8 hồi quy, 3 time series; HPO grid/random/bayes/TPE/GA | Thời gian train, số cấu hình HPO, model lỗi (pipeline JSON) |

Các điểm đã kiểm trong code và ảnh hưởng tới cách diễn giải kết quả:

- `random_search` thử 20 cấu hình cho mỗi model. `max_time` là trần thời gian của cả lô model, không phải thời gian chạy cố định.
- Dataset ≤ 10.000 dòng được chấm bằng CV ngay trên dữ liệu dùng để chọn model (`score_source=cv`). Vì vậy benchmark luôn chấm lại trên test riêng.
- Estimator phân loại/hồi quy của engine không cố định `random_state`. Lặp lại cùng config vẫn có thể cho kết quả khác.
- Tiền xử lý dạng bảng được fit trên toàn bộ phần không giữ lại trước khi CV. Điểm CV của backend vì thế hơi lạc quan. Điểm test của benchmark không bị ảnh hưởng.
- API dự đoán chỉ trả nhãn, không trả xác suất. Vì vậy agent không có ROC-AUC; chỉ baseline có.
- Giả định chưa kiểm: thời gian chờ worker phụ thuộc số worker của máy chạy, nên phải ghi lại trong `environment_notes`.

## 2. Đo gì và đo bằng cách nào

| Chiều (báo riêng, không gộp điểm) | Chỉ số chính | Nguồn |
|---|---|---|
| Đúng chức năng | Config hợp lệ lần đầu, % trường đúng, tool bắt buộc đúng tham số, đề nghị trái ý, dataset nhập đúng | `analyze.py` |
| Độ tin cậy luồng | Task success (PASS/(PASS+FAIL), CI Wilson), workflow train → bật → predict, lượt lỗi, hồi phục sau lỗi chèn (nhóm E) | `analyze.py`, `report.py` |
| Chất lượng ML | Trên test riêng, không qua LLM. Phân loại: accuracy, balanced acc, precision/recall/F1 macro, F1 weighted, confusion matrix. Hồi quy: MAE, RMSE, R², RMSLE, MAPE. Time series: RMSE, MAE, RMSLE. Thêm SR / NPS / CS như AutoML-Agent | `scoring.py`, `metrics.py` |
| Hiệu quả | Token, USD ước tính, thời gian agent/LLM/tool (p50/p95), end-to-end, CPU/RAM tiến trình, thời gian train và số cấu hình HPO của engine | `analyze.py`, `jobinfo.py` |

- Thống kê nằm ở `stats.py`, viết bằng Python thuần và đã đối chiếu với scipy:
  - Trung bình kèm CI 95% theo phân phối t.
  - Tỷ lệ kèm CI Wilson.
  - Ablation so có cặp theo (ca, lần lặp): McNemar chính xác cho PASS/FAIL, Wilcoxon signed-rank và CI bootstrap cho CS và token.
  - Cặp ghép theo lịch chạy, không chung seed LLM/HPO. Báo cáo không khẳng định "tốt hơn có ý nghĩa thống kê".
- Ca train vẫn chấm SR/NPS/CS như bài báo. Hồi quy có thêm `nps_paper` = 1/(1+RMSLE) để đặt cạnh bảng của bài (mục 15 của báo cáo).

## 3. Cài đặt

| Thứ cần | Dùng cho |
|---|---|
| `src/backend/.venv` (Python của agent) | `run`, `score`, `report`, test offline |
| Docker image `hautoml-backend-test:local` (cùng sklearn 1.5.1 / xgboost 3.1.2 / optuna 5.0.0 với engine) | `baselines`, `test_reference_impl.py` |
| Backend HAutoML đang chạy, tài khoản benchmark riêng (`AGENT_USER`, `AGENT_PASSWORD` trong `src/backend/.env`) | `preflight --online`, `run`, `score`, `engine-baseline` |
| Key LLM của provider đã chọn | Chỉ cho `run` |
| Server test PostgreSQL/MySQL có database `datasets` (nhóm S) | `run` ca S |

Dựng database cho nhóm S. Database chỉ chứa phần TRAIN; `load_datasets.py` kiểm hash file trước khi nạp.

```bash
docker compose -f src/backend/tests/sql_sources/docker-compose.yml up -d --wait
docker run --rm --network host -v "$PWD":/repo:ro -w /repo hautoml-backend-test:local \
    python -I src/backend/tests/sql_sources/load_datasets.py
docker network connect automl_hautoml_net hautoml-test-postgres
docker network connect automl_hautoml_net hautoml-test-mysql
```

Trên giao diện **Kết nối database**, dùng tài khoản benchmark để tạo hai kết nối:

- PostgreSQL: host `hautoml-test-postgres`, database `datasets`, user `hautoml_ro`.
- MySQL: host `hautoml-test-mysql`, database `datasets`, user `hautoml_ro`.

Backend cần `DB_SOURCE_SQL_ALLOWED_HOSTS=hautoml-test-postgres:5432,hautoml-test-mysql:3306`. Sau đó điền ID của hai kết nối vào `placeholders.PG_CONN_ID` và `placeholders.MYSQL_CONN_ID`.

## 4. Chạy

Mọi lệnh chạy từ gốc repo, với `PY=src/backend/.venv/bin/python`.

| Lệnh | Tốn tiền LLM? | Dùng backend? |
|---|---|---|
| `$PY -m pytest benchmark/test_bench.py benchmark/test_v5.py` | Không (LLM giả) | Không |
| `$PY benchmark/bench.py baselines --mode smoke\|full` | Không | Không (Docker, `--network none`) |
| `$PY benchmark/bench.py preflight [--online]` | Không | `--online`: chỉ đọc |
| `$PY benchmark/bench.py run` | **CÓ** | Có (train thật) |
| `$PY benchmark/bench.py score` | Không | Có (predict) |
| `$PY benchmark/bench.py engine-baseline --id X` | Không | Có (train thật) |
| `$PY benchmark/bench.py report [--baselines X]` | Không | Không |

### Nâng cấp `bench_config.json` từ v4.1

`init` không ghi đè file đã có. Từ `benchmark/config.example.json`, chép sang file cũ các mục sau:

- `connection_fixtures`.
- `predict_rows.crab_pg`.
- `max_continuations`, `cleanup_imported_datasets`, `cases_subset`.
- `"S05"` trong `ablation.cases`.

Sau đó điền `PG_CONN_ID` / `MYSQL_CONN_ID` và đổi `experiment_id`. Không dùng lại ID đợt cũ: protocol khác thì `lock` từ chối. Chạy `preflight` sẽ liệt kê đúng các mục còn thiếu.

### Smoke

Smoke có 7 ca: A02, B01, C01, D02, S01, S05, T01. Mỗi ca chạy 1 lần, không có ablation. Có 3 job train, khoảng 15–25 phút.

```bash
cp benchmark/config.smoke.json benchmark_artifacts/bench_config.json   # rồi điền placeholders/provider/model
$PY benchmark/bench.py preflight --online
$PY benchmark/bench.py lock --phase pilot
$PY benchmark/bench.py run --phase pilot
$PY benchmark/bench.py baselines --mode smoke --id v5-smoke
$PY benchmark/bench.py report --phase pilot --baselines v5-smoke
```

Pilot không chấm test, theo đúng quy tắc khoá ngưỡng. Muốn có đủ số trên test cho smoke thì khoá `--phase official` với config smoke, dùng một `experiment_id` riêng.

### Đầy đủ

Có 47 ca × 5 lần = 235 lượt, cộng 13 ca × 5 biến thể × 3 lần = 195 lượt ablation, tổng 430 lượt.

```bash
$PY benchmark/bench.py init                    # bench_config.json từ config.example.json
$PY benchmark/bench.py preflight --online
$PY benchmark/bench.py lock --phase pilot && $PY benchmark/bench.py run --phase pilot   # kiểm đường chạy
$PY benchmark/bench.py lock                    # khoá official (cases, config, hash code, dữ liệu, plan)
$PY benchmark/bench.py run                     # dừng an toàn: tạo file runs/<id>/official/STOP
$PY benchmark/bench.py score
$PY benchmark/bench.py baselines --mode full --id v5-01
$PY benchmark/bench.py engine-baseline --id v5-01 --repeats 5   # sau official: job thêm vào tài khoản
$PY benchmark/bench.py report --baselines v5-01
```

Ước lượng tải: lượt train tốn khoảng 5 phút mỗi lượt, gồm 90 lượt full và 75 lượt ablation. Chi phí LLM phụ thuộc provider; đợt v4-02 tốn khoảng 52k–62k token mỗi ca.

## 5. Đầu ra

- `benchmark_artifacts/runs/<experiment>/<phase>/<variant>/<case>_rNN/`: `run.json` (lượt chat, thẻ xác nhận, job, dataset, tài nguyên, pipeline engine), `trace.jsonl` (mọi sự kiện), `test/` (dự đoán và metric trên test).
- `benchmark_artifacts/report/<experiment>/<phase>/`: `report.md` (16 mục), `results.csv`, `results.jsonl`, `baselines.json`.
- `benchmark_artifacts/baselines/<id>/<method>/<dataset>_sNN/`: `metrics.json`, `predictions.csv`. Ở `<id>/` có `baselines_manifest.json` ghi môi trường, hash dữ liệu/code và ngân sách.

Không file nào bị ghi đè. Lượt đã có thì được bỏ qua. Muốn chạy đợt mới thì đặt `experiment_id` hoặc `--id` mới.

## 6. Mở rộng

Thêm dataset bảng:

1. Tải dữ liệu thật, ghi nguồn vào `benchmark_artifacts/raw/source_metadata.json`. Không sinh dữ liệu bằng script.
2. Thêm vào `prepare_data.py`. Lưu ý: `prepare` từ chối khi đã có protocol khoá, nên phải dùng một đợt mới.
3. Thêm ca vào `cases.json` (`task`, `expect`, `consent`), thêm `predict_rows` / `test_sets` vào config, và thêm tên dataset vào `baselines.TABULAR`.
4. Chạy `test_cases_file_is_consistent`.

Thêm baseline:

1. Viết một nhánh trong `baselines._run_tabular` hoặc `_run_time_series`. Nhánh đó trả `{"metrics": metrics.compute(...), "fit_seconds": ...}`.
2. Thêm tên vào `TABULAR_METHODS` / `TS_METHODS`, và vào `METHOD_ORDER` / `METHOD_KIND` trong `report_sections.py`.
3. Baseline chỉ được fit và chọn mô hình trên train. Chỉ đọc test sau khi fit.

Thêm ca agent:

- Mỗi ca cần chính sách `consent` khớp đúng câu chữ của prompt. Người dùng mô phỏng không được đồng ý điều prompt không nói tới.
- Tiêu chí tự động nằm trong `expect`. Phần cần người đọc lại đặt vào `expect.manual`, chấm bằng file `review.json`.

## 7. Đọc kết quả

- **SR** chấm theo thang của AutoML-Agent. Ca không ràng buộc: 0.5 khi train xong, 1.0 khi đã bật model và predict được. Ca có ràng buộc: 0.25 / 0.5 / 0.75 / 1.0. Thang điều chỉnh cho HAutoML, chi tiết ở benchmark.md mục 5.2.
- **NPS** ở mục 3 của báo cáo tính theo protocol v4: phân loại dùng F1-macro, hồi quy dùng 1/(1+MAE), time series dùng 1/(1+RMSLE). **`nps_paper`** theo cách của bài báo: hồi quy dùng 1/(1+RMSLE).
- Time series có NPS sát 1 ngay cả với dự báo ngây thơ. Vì vậy hãy đọc NPS cùng tỷ lệ thắng baseline lặp lại tuần trước.
- **Đo được / lượt** trong bảng baseline: lượt agent hỏng không có metric. Phải đọc cột này cùng SR, không chỉ đọc trung bình metric.
- Khoảng tin cậy rộng là bình thường khi n = 5. Không có kiểm định giữa agent và baseline, vì hai bên không ghép cặp được.

## 8. Tái lập

`lock` khoá cases, config, bảng giá, manifest dữ liệu, hash code benchmark/agent/backend, cấu hình provider (không có key) và plan có thứ tự xen kẽ seed 42. Sau đó `run` và `score` từ chối chạy nếu bất kỳ thứ gì đã đổi. Baseline khoá ngân sách, hash dữ liệu và hash code trong `baselines_manifest.json`.

LLM và engine không deterministic: lặp lại chỉ cho cùng phân phối, không cho cùng con số.

## 9. Giới hạn đã biết

- Quy mô nhỏ: 4 dataset bảng, 2 chuỗi thời gian, 2 database. Test cố định, mỗi dataset một split.
- Người dùng mô phỏng đi theo chính sách cố định và chỉ xác nhận thẻ train khi cấu hình trên thẻ đúng yêu cầu. Người thật có thể bấm khác. Lượt "tiếp tục" là một câu cố định.
- Model train xong mà agent không bật: bộ chấm bật tạm để đo NPS, rồi tắt lại. SR vẫn ghi lỗi triển khai.
- D06 có thể bị loại khi job fixture xong sớm; agent chậm dễ bị loại hơn.
- Agent và baseline có chức năng khác nhau: agent phải tự hiểu yêu cầu tiếng Việt, baseline nhận đúng nhiệm vụ. Thời gian agent gồm suy luận LLM; baseline chạy `n_jobs=1`, còn engine chạy song song.
- FLAML và AutoGluon chưa được cài trong image, nên status là `unavailable`, không có số liệu.
- Nhóm S chưa đo MongoDB, SQLite/DuckDB qua kết nối đã lưu, hay database lớn. `glass.sqlite` có cả dòng test nên không dùng.
- Không đo CPU/RAM của worker train, không đo GPU.
- So với bài AutoML-Agent: chỉ trùng nguồn dữ liệu ở Crab, Weather, Electricity, và khác bản dữ liệu, khác cách dự báo (đơn biến so với đa biến). Bài báo sinh code, HAutoML gọi engine có sẵn. Xem `paper_reference.json`, mục `protocol_differences`.
