# Benchmark hệ thống agent HAutoML — protocol v5

Bộ benchmark có **47 kịch bản** trong 8 nhóm:

- 33 ca của v4 (nhóm A–F), giữ nguyên prompt và tiêu chí để so với các đợt trước.
- 6 ca nhóm T (dự báo chuỗi thời gian, thêm ở v4.1).
- 8 ca nhóm S (lấy dữ liệu từ database qua SQL Agent và adapter, thêm ở v5).

Số lượt:

- Chạy thử: **47 lượt**.
- Chính thức, bản đầy đủ: **235 lượt**.
- Năm biến thể ablation chạy thêm **195 lượt** (13 ca × 3 lần) nếu bật. Cấu hình mặc định bật ablation, nên một đợt official có **430 lượt**, chạy xen kẽ theo thứ tự đã khoá.

Pilot được lưu riêng. Tóm tắt của báo cáo tính trên nhóm A–F; nhóm T và S báo riêng.

**Từ v5, agent không tự huấn luyện, bật hay tắt model.** Tool chỉ đề nghị (thẻ xác nhận). Benchmark đóng vai người dùng bấm nút theo một chính sách cố định của từng ca (mục 5.5). Vì vậy số liệu v5 **không so trực tiếp được với v4-02**: luồng nhóm C/T/E02 có thêm bước xác nhận, và đôi khi cần thêm một lượt nhắn "tiếp tục". Thay đổi đầy đủ ở mục 10. Hướng dẫn dùng ở [benchmark/README.md](benchmark/README.md).

Protocol v4 là bản tổng hợp sau khi Claude xây và Codex xác nhận độc lập; các thay đổi so với v3 nằm ở mục 8.

Đây là protocol và bộ chạy đã chuẩn bị, **chưa phải kết quả chạy LLM/training thật**. Định nghĩa thực thi nằm trong [cases.json](benchmark/cases.json); CLI ở [bench.py](benchmark/bench.py). Các hướng dẫn dưới đây chạy từ thư mục gốc repository.

## 1. Phạm vi, chỉ số và căn cứ

| Nguồn | Áp dụng vào HAutoML | Giới hạn |
|---|---|---|
| [AutoML-Agent](8647_AutoML_Agent_A_Multi_Agen.pdf) | SR nhiều mức, NPS, CS, thời gian, chi phí và nhiều lần chạy; nhóm T theo task Time-Series Forecasting của bài (Weather, Electricity, dự báo 96 bước, NPS = 1/(1+RMSLE)) | Điều chỉnh cách chứng minh triển khai theo API hiện có; NPS hồi quy bảng dùng MAE, không phải RMSLE; nhóm T dự báo một chuỗi, không đa biến như bài |
| [Multi-Agent Automated Machine Learning](Wang_Multi-Agent_Automated_Machine_Learning_CVPR_2023_paper.pdf) | Accuracy, chất lượng trong cùng ngân sách tìm kiếm, độ ổn định và ablation | MA2ML dùng học tăng cường; đây không phải tái lập trực tiếp phương pháp hoặc bảng kết quả của bài |
| Kiểm thử riêng HAutoML | Thành công nhiệm vụ, tính đúng cấu hình/tool, giữ ngữ cảnh, xử lý lỗi và mức đáp ứng ràng buộc | Các chỉ số bổ sung phải phân biệt với chỉ số của hai bài |

Đo classification/regression dạng bảng (nhóm A–F), dự báo một chuỗi thời gian theo giờ (nhóm T) và lấy dữ liệu từ PostgreSQL/MySQL (nhóm S) qua `ChatSession`, LLM và backend thật. Hệ thống gồm Manager + 5 sub-agent (Prompt, Data, Model, Operation, SQL). Baseline ngoài agent (mục 11) chạy trên cùng split. Không tính frontend hay HTTP agent server vào thời gian agent. Từ v5 có đo số cấu hình HPO và thời gian huấn luyện của engine (pipeline backend), cùng CPU/RAM của tiến trình chạy agent. Chưa đo FLOPs, reward RL, số tham số, CPU/RAM của worker hay GPU. AutoGluon/FLAML chỉ có số khi đã được cài trong image baseline.

## 2. Dữ liệu, môi trường và cấu hình

### 2.1. Dữ liệu đã chuẩn bị

| Dataset | Nguồn local | Target | Feature | Train / test |
|---|---|---|---:|---:|
| Glass | `docs/data_automl/user/glass.csv` | `Type` | 9 | 171 / 43 |
| Online Shoppers | `docs/data_automl/user/online_shoppers_intention.csv` | `Revenue` | 10 | 9.937 / 2.393 |
| Concrete Compressive Strength | `benchmark_artifacts/raw/concrete.csv` | `strength` (MPa) | 8 | 824 / 206 |
| Crab Age | `benchmark_artifacts/raw/crab_age.csv` | `Age` | 10 | 3.114 / 779 |

Nguồn tải, phiên bản, ngày tải của Concrete/Crab lưu ở [source_metadata.json](benchmark_artifacts/raw/source_metadata.json). Dữ liệu thật; không sinh mẫu benchmark. Shopping giữ 10 cột số, `Revenue` đổi thành 0/1; Crab one-hot `Sex` thành `Sex_F/I/M`. Đây là tiền xử lý cố định của benchmark.

Split `feature-group-v1`, seed 42: gom theo **toàn bộ feature đã chọn, không gồm target**, rồi chia cả nhóm vào train hoặc test. Giữ mọi dòng, kể cả nhóm có target mâu thuẫn. Với classification, phân tầng xấp xỉ theo tập nhãn của nhóm và kiểm tra đủ lớp trong hai phần. Tỷ lệ test xấp xỉ 20%, không cố ép đúng 20% bằng cách phá nhóm. Do đó đánh giá khả năng dự đoán trên tổ hợp feature chưa có trong train; khác với random split từng dòng.

[manifest.json](benchmark_artifacts/datasets/manifest.json) lưu hash nguồn, hash tám file split, số mẫu, số nhóm trùng/mâu thuẫn và chính sách chia. Kiểm tra hiện tại: cả bốn dataset có **0 nhóm feature giao nhau giữa train và test**. Bản chia ngẫu nhiên theo dòng trước đó chưa từng được upload và đã bị xoá.

**Upload lại đúng bốn file `*_train.csv` của bản mới.** Không dùng ID trỏ vào bản chia cũ dù số dòng giống nhau. File test chỉ do bộ chấm đọc sau khi hoàn tất official; không upload test, không đưa nhãn/điểm test vào LLM, không dùng test để chọn model/prompt/ngưỡng. Mẫu `predict_rows` dùng kiểm tra endpoint, không phải tập tính Accuracy/F1.

### 2.1b. Dữ liệu nhóm T (time series)

| Dataset | Nguồn | Target | Train | Test (không upload) |
|---|---|---|---:|---:|
| Electricity | UCI 321 (ElectricityLoadDiagrams20112014), khách hàng MT_301, năm 2013, gộp 15 phút -> giờ | `load_kwh` | 4.296 giờ (2013-04-01 → 2013-09-26) | 96 giờ (2013-09-27 → 2013-09-30) |
| Weather (Jena) | Trạm thời tiết MPI-BGC Jena (`mpi_roof`), năm 2020, gộp 10 phút -> giờ | `co2_ppm` | 3.384 giờ (2020-08-09 → 2020-12-27) | 96 giờ (2020-12-28 → 2020-12-31) |

Cả hai cùng nguồn với Electricity/Weather mà AutoML-Agent dùng qua Time-Series-Library (giấy phép CC BY 4.0). Mỗi file chỉ có hai cột `date,<target>`, mốc giờ cách đều, không thiếu. Split `time-holdout-v1`: **96 bước cuối** (PRED_SEQ_LEN của bài) là test, phần trước là train, không xáo trộn. Dựng bằng `bench.py prepare-ts` vào `benchmark_artifacts/datasets/timeseries/`; [manifest_ts.json](benchmark_artifacts/datasets/timeseries/manifest_ts.json) lưu nguồn, URL tải, hash file gốc/file chia và cách xử lý.

- Electricity lấy năm **2013**, khoảng chưa từng dùng: khi phát triển tính năng time series (2026-11-03) đã thử trên 2014-04..09 của cùng khách hàng, nên cửa sổ đó không còn là dữ liệu chưa nhìn. Tháng 4–9 tránh hai ngày đổi giờ UCI ghi chú.
- Weather dùng CO2 (target `OT` của Time-Series-Library khi dự báo một chuỗi), không dùng nhiệt độ: RMSLE của bài (`log(1+y)`) không xác định khi giá trị ≤ −1, mà nhiệt độ tháng 12 ở Jena xuống dưới −1 °C.
- Cửa sổ Weather là đoạn sạch dài nhất của năm 2020: file gốc có CO2 = −9999 (thiết bị không đo) ngày 20/02 và 08/08, một mốc trùng (12/05) và một khoảng thiếu 80 phút (29/05). **Không nội suy, không bù, không sinh số liệu.**
- Không upload file test, không đưa giá trị test vào LLM, không dùng test để chọn ngưỡng/prompt.

### 2.2. Môi trường

- Chạy API, training consumer, database và storage theo [README](README.md). CLI benchmark không cần frontend/agent HTTP server.
- Dùng tài khoản benchmark riêng đã xác thực; không để người khác tạo job trong lúc chạy.
- Dùng Python `src/backend/.venv/bin/python` và dependency của backend. `src/backend/.env` hoặc biến môi trường cần `AGENT_USER`, `AGENT_PASSWORD`, cùng key của provider. Không điền mật khẩu/token vào prompt hay JSON benchmark.
- Giữ cố định máy, CPU/GPU, số worker, phiên bản thư viện, giới hạn token, polling và tracing. Ghi thông tin triển khai vào `environment_notes` của config trước khi khóa; không chứa bí mật.
- Mỗi ca/lần lặp mở session mới; các lượt chat trong một ca dùng chung session. Chạy tuần tự. Seed 42 chỉ áp dụng chia tập, không bảo đảm LLM/HPO deterministic.
- Ngân sách nhóm C: `random_search`, `max_time=300` giây; E02 dùng 60 giây. Đây là ngân sách backend, không phải giới hạn tổng thời gian ca. `max_wait_seconds=600` áp dụng cho từng giai đoạn chờ watcher và chờ xác nhận backend; tổng thời gian có thể lớn hơn 600 giây.
- Runner đăng nhập lại khi nhận HTTP 401 rồi thử lại một lần; không tự retry POST khi timeout/503. Cơ chế này chỉ nằm trong bộ benchmark, không sửa agent sản phẩm.

### 2.3. Cấu hình cần điền

Chạy `init` tạo [bench_config.json](benchmark_artifacts/bench_config.json) và [pricing.json](benchmark_artifacts/pricing.json), giữ nguyên file đã có. Provider/model được lấy từ cấu hình đang dùng nếu phân giải được, sau đó ghi rõ để khóa.

| Trường `placeholders` | Giá trị cần chuẩn bị |
|---|---|
| `GLASS_ID`, `SHOP_ID`, `CONCRETE_ID`, `CRAB_ID` | ID upload đúng bốn file train mới |
| `MISSING_ID` | ObjectId 24 ký tự hex hợp lệ nhưng không tồn tại trong tài khoản |
| `GLASS_JOB` | Job train trên `GLASS_ID` mới, đủ 9 feature, target `Type`, thành công và đã activate |
| `INACTIVE_JOB` | Một job Glass riêng cùng yêu cầu, thành công nhưng chưa activate |
| `ELEC_ID`, `WEATHER_ID` | ID upload đúng hai file `*_train.csv` của nhóm T (`electricity_MT_301_2013_hourly_train.csv`, `weather_jena_co2_hourly_train.csv`) |

| `PG_CONN_ID`, `MYSQL_CONN_ID` | ID hai kết nối database đã lưu (giao diện **Kết nối database**) tới database `datasets` của server test PostgreSQL / MySQL (`src/backend/tests/sql_sources`), user `hautoml_ro`. `preflight --online` kiểm loại database, đủ 6 bảng, và mỗi bảng có đúng số dòng phần train |

Trường mới ở v5:

- `connection_fixtures`: bảng mong đợi của mỗi kết nối.
- `max_continuations` (mặc định 2): số lượt nhắn "tiếp tục" tối đa sau khi bật model.
- `cleanup_imported_datasets` (mặc định true): xoá dataset nhập từ database sau mỗi lượt.
- `cases_subset`: chỉ chạy một phần các ca, cho chế độ smoke (`config.smoke.json`).

`RUNNING_JOB` do runner tự tạo trước D06 theo `running_job_fixture`; không điền ID cố định. Job này train trên `SHOP_ID` (9.937 dòng, random_search) để còn chạy khi agent đọc trạng thái: backend dừng job ngay khi mọi model xong, `max_time` chỉ là trần, nên job Glass 171 dòng có thể xong trước khi agent kịp hỏi. Chi phí fixture nằm ngoài số lượt đo.

Trước mỗi ca dùng `GLASS_JOB` (D01–D03, D05, E03) runner bật lại job nếu đang tắt; trước D04 runner tắt `INACTIVE_JOB` nếu một lượt trước đã bật nó. Trạng thái trước ca được ghi vào `run.json`; không đưa được về đúng trạng thái thì lượt là `INVALID_FIXTURE`. `predict_rows`, feature và đường dẫn test đã có trong config mẫu.

`experiment_id` mặc định `hautoml-v5-01`. Đổi ID cho một đợt độc lập. `repeats=5`; `ablation.repeats=3`. Nếu chỉ cần 235 lượt (không ablation), đặt `ablation.enabled=false` **trước khi lock official**. Không thay số lần lặp dựa vào kết quả tốt/xấu.

Chi phí tiền là tùy chọn: điền provider/model khớp config, giá USD/triệu token input/output, ngày giá, nguồn và ghi chú. Chỉ đặt `billing_mode="uniform_input_output"` khi bảng giá này mô tả đủ cách tính token của provider; nếu còn cache/reasoning/tier riêng chưa xử lý thì để trống. Thiếu bảng giá vẫn đo token, nhưng chi phí USD để `null`; không giả định bằng 0.

## 3. Quy trình chạy từ đầu đến báo cáo

### 3.1. Chuẩn bị và kiểm tra

```bash
PY=src/backend/.venv/bin/python
$PY benchmark/bench.py init
# Chỉ dùng prepare trước khi có protocol lock; dữ liệu bản mới đã được tạo sẵn.
# $PY benchmark/bench.py prepare
# Dữ liệu nhóm T đã dựng sẵn; chỉ chạy khi chưa có manifest_ts.json:
# $PY benchmark/bench.py prepare-ts
# Upload bốn file train mới + hai file *_train.csv nhóm T, tạo hai job fixture và điền cấu hình mục 2.3.
$PY benchmark/bench.py preflight
$PY benchmark/bench.py preflight --online
$PY -m pytest benchmark/test_bench.py -q -p no:cacheprovider
```

Offline preflight kiểm hash, schema, số mẫu, trùng feature, placeholder, provider/model, thông tin đăng nhập và plan; không gọi LLM/train. `--online` thêm đăng nhập và đọc metadata backend, xác nhận tài khoản không có job chạy, schema/số dòng dataset và trạng thái fixture. Schema/số dòng khớp chưa chứng minh nội dung upload có cùng hash: người vận hành phải bảo đảm chọn đúng file train mới.

### 3.2. Chạy thử và khóa official

```bash
$PY benchmark/bench.py lock --phase pilot
$PY benchmark/bench.py run --phase pilot
$PY benchmark/bench.py report --phase pilot
# Review log; nếu cần hiệu chỉnh, chỉ dùng validation/CV trong train.
# Sửa đồng bộ cases.json (prompt + constraints) và tài liệu trước lock official.
$PY benchmark/bench.py preflight --online
$PY benchmark/bench.py lock --phase official
```

Pilot gồm 47 lượt full (33 ca v4 + 6 ca T + 8 ca S), không có ablation; có thể chạy riêng một phần bằng `--cases`. `score --phase pilot` bị chặn. Nếu sửa code/config sau pilot, báo cáo pilot vẫn đọc snapshot đã khóa; muốn chạy lại pilot thì dùng `experiment_id` mới. Không sửa dữ liệu đã khóa: `prepare` sẽ từ chối khi có protocol trong workspace.

`protocol.json` khóa cases/prompt/ngưỡng, cấu hình, bảng giá, manifest, hash code benchmark/agent/backend (bỏ thư mục cache như `__pycache__`, `.pytest_cache`), phiên bản Python, một số biến runtime và danh sách từng lượt `(variant, case, repeat)`. Nó không tự đóng băng container hay máy backend từ xa; ghi và giữ môi trường như mục 2.2. `run`/`score` kiểm tra lại snapshot và từ chối nếu thay đổi. Khóa bằng hash giúp phát hiện thay đổi, không phải chữ ký chống sửa có chủ ý.

### 3.3. Chạy chính thức, chấm test và xuất báo cáo

```bash
$PY benchmark/bench.py run              # chạy cả plan: full và ablation xen kẽ theo thứ tự đã khóa
$PY benchmark/bench.py report           # xem tiến độ và các ca cần review
$PY benchmark/bench.py score
$PY benchmark/bench.py report
```

Chỉ được chấm test khi có đủ `run.json` theo **toàn bộ plan đã khóa**, kể cả ablation nếu bật, không còn `INVALID_FIXTURE` và không còn trạng thái dừng vì job chưa kết thúc. Không xem test giữa chừng rồi sửa hệ thống. Bộ chấm chọn đúng job agent tạo, không chọn model lại và không tự kích hoạt model thay agent.

Một số ca cần đọc câu trả lời. Tạo `review.json` trong thư mục lượt chạy, đối chiếu tiêu chí `expect.manual`, câu trả lời trong `run.json` và `tool_result` trong `trace.jsonl`. Ví dụ JSON hợp lệ:

```json
{"verdict": "PASS", "note": "Đã đối chiếu target bị thiếu với schema và câu trả lời; agent giải thích đúng, không tạo config/job."}
```

Dùng `"FAIL"` nếu không đạt, nêu bằng chứng cụ thể. Review không thể ghi đè tiêu chí tự động trượt hoặc phép đo tự động còn thiếu. B03–B06 phải giải thích đúng lỗi; chỉ im lặng/không train chưa đủ PASS. Nhóm C phải báo trung thực kết quả backend, không nhận điểm test từ bộ chấm làm thông tin agent đã biết.

### 3.4. Chạy tiếp, timeout và fixture không hợp lệ

Chạy lại cùng lệnh sẽ bỏ qua lượt đã có `run.json`. `run` đi theo thứ tự plan đã khóa: trong mỗi khối lần lặp, full và các biến thể ablation được trộn ngẫu nhiên bằng `schedule_seed` (mặc định 42), để số job tích luỹ trong tài khoản (làm kết quả `list_my_jobs` dài dần) không thiên về biến thể chạy sau. Ở pilot, `--cases`, `--variants`, `--repeats N` chỉ lọc các lượt trong plan, giữ nguyên thứ tự. Official không cho lọc: chạy từng phần (vd full trước, ablation sau) sẽ phá lịch xen kẽ đã khóa. Mỗi lượt ghi số job đã có trong tài khoản (`account_job_count`).

Muốn dừng: tạo file `STOP` trong `runs/<experiment_id>/<phase>/`; runner dừng sau lượt đang chạy. Xoá file rồi chạy lại để tiếp tục. **Không ngắt giữa lượt:** lượt đã gửi prompt cho agent mà bị ngắt (Ctrl-C, mất điện, tiến trình chết) được giữ là FAIL với cờ `interrupted` và không chạy lại, vì chạy lại sẽ xoá một kết quả đã quan sát được. Chạy lại `run` sau khi bị ngắt chỉ xác nhận job của lượt đó đã dừng (không gọi lại LLM); `score` bị chặn cho tới khi xác nhận xong. Ngoại lệ duy nhất: fixture đã hỏng trước khi agent hành động (vd job D06 không còn chạy) thì lượt vẫn là `INVALID_FIXTURE` và được chạy lại như mọi lượt fixture hỏng. Chỉ lượt bị ngắt trước khi gửi prompt đầu tiên (đăng nhập, chuẩn bị fixture) mới được lưu sang `.aborted-*` và chạy lại. Checkpoint được ghi qua file tạm rồi thay thế, nên tiến trình chết giữa lúc ghi không làm hỏng checkpoint cũ.

Nếu còn job đang chạy/không xác minh được trạng thái, runner lưu `halt_reason` và dừng cả batch. Chờ hoặc xử lý job trên backend, rồi chạy lại; runner chỉ tiếp tục sau khi xác nhận tài khoản không có job chạy. Snapshot kết quả của lượt timeout được giữ, không biến thành PASS chỉ vì model hoàn tất muộn. Dừng tiến trình không tự hủy job backend. Nếu lượt dừng vì bộ chạy không liệt kê được job, chạy lại lệnh thường sẽ gỡ trạng thái dừng nhưng giữ lượt đó ở `INVALID_FIXTURE`; chỉ `--retry-invalid` mới chạy lại nó.

Lượt `INVALID_FIXTURE` có thể xuất hiện ở mọi nhóm (fixture D/E hỏng, hoặc bộ chạy không đọc được backend) và được chạy lại có lưu bằng chứng; `score` bị chặn cho tới khi không còn lượt nào như vậy:

```bash
$PY benchmark/bench.py run --retry-invalid
```

Lệnh này chỉ thay lượt có trạng thái `INVALID_FIXTURE`, lưu lượt cũ sang `.invalid-*`; không chạy lại PASS/FAIL để chọn kết quả tốt. Kiểm tra/tổng hợp số lượt fixture lỗi và lý do từ các thư mục lưu trữ khi báo cáo. Nếu tiếp tục lỗi fixture, ghi chưa hoàn tất điều kiện benchmark thay vì loại im lặng. Không dùng `--retry-invalid` sau khi đã xem test để chọn lượt tốt hơn.

Nếu phép chấm test bị lỗi, xem `test/error.json`, xử lý nguyên nhân hạ tầng và chạy lại `score`; kết quả đo thành công đã có được giữ và kiểm hash. Không đổi code/protocol trong cùng đợt để sửa kết quả. Lỗi phép đo không được thay thành NPS=0.

### 3.5. Đầu ra

```text
benchmark_artifacts/
  bench_config.json
  pricing.json
  datasets/manifest.json + *_train.csv + *_test.csv
  datasets/timeseries/manifest_ts.json + *_train.csv + *_test.csv   # nhóm T
  runs/<experiment_id>/<pilot|official>/
    protocol.json
    <variant>/<case>_rNN/
      run.json
      trace.jsonl
      review.json                    # người đánh giá tạo khi cần
      test/test_predictions.csv      # nhóm C và các ca train của nhóm T
      test/test_metrics.json
      test/error.json                # nếu phép đo lỗi
  report/<experiment_id>/<pilot|official>/
    report.md
    results.csv
    results.jsonl
```

`report` không gọi backend/LLM; dùng cases và bảng giá trong snapshot. `--experiment <id>` cho phép đọc báo cáo đợt cũ. Báo cáo ghi protocol ID, số lượt đã có/tổng plan, số lượt lưu trữ `.invalid-*`/`.aborted-*`, phần chưa review/chưa đo và các mẫu số; cảnh báo nếu code đã đổi sau khi khóa và từ chối thư mục lượt chạy sai tên (vd bản sao `A01_r01.bak`). Không gộp pilot, biến thể hoặc experiment khác vào kết quả full official.

## 4. Danh sách 47 kịch bản

### Nhóm A — Tra cứu và hiểu dữ liệu: 4 ca

Không được tạo job trong nhóm này. `PASS` khi nội dung đúng dữ liệu thật và không có tác dụng ngoài yêu cầu. SR/NPS/CS để `null`.

| ID | Prompt | Tiêu chí PASS |
|---|---|---|
| A01 | `Liệt kê tất cả dataset hiện có của tôi, kèm ID và tên. Chỉ tra cứu, không huấn luyện.` | Nêu đủ ID và tên của mọi dataset trong tài khoản; mỗi ID đi đúng tên của nó (người chấm đọc lại); không bịa ID; không tạo job. |
| A02 | `Dataset <GLASS_ID> có những cột nào? Cột nào có thể làm target classification? Chỉ phân tích.` | Hệ thống đọc schema đúng `GLASS_ID` (qua tool của Data Agent hoặc Handoff khi không có Data Agent); có 10 tên cột đúng; đối chiếu target với schema backend; không hiểu cờ target thành cờ loại bỏ feature. |
| A03 | `Hệ thống hỗ trợ những metric nào cho classification và regression? Liệt kê riêng từng loại.` | Classification đủ 8 metric; regression đủ `mse,mae,mape,r2`; không tuyên bố RMSLE/AUC đã có. |
| A04 | `Xem schema dataset <MISSING_ID>. Chỉ tra cứu đúng ID này, không thay bằng dataset khác.` | Nêu không tìm thấy/không truy cập được, không dựng schema giả hoặc chuyển sang dataset khác. |

### Nhóm B — Chọn và kiểm tra cấu hình: 6 ca

Mọi prompt đều cấm bắt đầu train. Cấu hình hợp lệ phải có bằng chứng `submit_config`/handoff, không chỉ là đoạn JSON agent viết trong câu trả lời. SR/NPS/CS để `null`.

| ID | Prompt | Tiêu chí PASS |
|---|---|---|
| B01 | `Tạo cấu hình cho <GLASS_ID>, classification, target Type, feature RI,Na,Mg,Al,Si,K,Ca,Ba,Fe, f1_macro, random_search, max_time 300 giây. Kiểm tra cấu hình nhưng chưa chạy train.` | Có config hợp lệ đúng tất cả trường, không tạo job. |
| B02 | `Tạo cấu hình cho <CONCRETE_ID>, regression, target strength, feature cement,blast_furnace_slag,fly_ash,water,superplasticizer,coarse_aggregate,fine_aggregate,age, mae, random_search, max_time 300 giây. Kiểm tra cấu hình nhưng chưa chạy train.` | Có config hợp lệ đúng tất cả trường, không tạo job. |
| B03 | `Tạo cấu hình classification cho <GLASS_ID> với target NotAColumn, feature RI,Na, metric f1_macro, random_search, max_time 300. Không đổi target và chưa chạy train.` | Phát hiện target không tồn tại; không chốt config sai và không tạo job. |
| B04 | `Tạo cấu hình classification cho <GLASS_ID>, target Type; bắt buộc feature gồm RI,Na,Type; metric f1_macro, random_search, max_time 300. Không tự sửa danh sách feature và chưa train.` | Phát hiện target lọt vào feature; không chốt config sai hoặc train. |
| B05 | `Tạo cấu hình regression cho <CONCRETE_ID>, target strength, feature cement,blast_furnace_slag,fly_ash,water,superplasticizer,coarse_aggregate,fine_aggregate,age, metric accuracy, random_search, max_time 300. Không tự đổi metric và chưa train.` | Giải thích metric không phù hợp; không chốt config sai hoặc train. |
| B06 | `Tạo cấu hình classification cho <GLASS_ID>, target Type, feature RI,Na,Mg,Al,Si,K,Ca,Ba,Fe, f1_macro, random_search, max_time 5 giây. Không tự tăng thời gian và chưa train.` | Phát hiện giới hạn tối thiểu 60 giây; không chốt config vi phạm hoặc train. |

Trong B03–B06, agent phát hiện lỗi trước khi gọi `submit_config` vẫn được PASS. Không ép agent phải gây lỗi tool. Tỷ lệ cấu hình hợp lệ lần đầu chỉ tính trên B01–B02 và nhóm C có đầu vào hợp lệ, không tính các ca cố ý sai.

### Nhóm C — Pipeline từ yêu cầu tới dự đoán: 10 ca

Mỗi ca bắt đầu phiên mới và tạo job mới. Gồm hai lượt chat cố định:

1. Gửi prompt trong bảng, nối nguyên văn hậu tố: `Dùng random_search, max_time 300 giây. Tôi yêu cầu chạy train, sau khi hoàn tất kích hoạt mô hình và dự đoán mẫu tôi cung cấp. Không thay dataset, target, feature hoặc metric đã chỉ định.`
2. Bộ chạy chờ watcher và lưu snapshot job. Gửi: `Hãy kiểm tra kết quả job vừa tạo, báo trạng thái và các metric thực tế, đối chiếu mọi ràng buộc tôi đã nêu. Nếu train thành công, kích hoạt mô hình và gọi predict cho mẫu sau: <ROWS>. Không tạo job mới.` Bộ chạy thay `<ROWS>` bằng `predict_rows` tương ứng trong cấu hình.

Không yêu cầu agent tự kích hoạt ngay từ callback watcher: hệ thống hiện chuyển kết quả nền vào ngữ cảnh cho lượt tiếp theo. Hai lượt cố định trên là một ca benchmark, bao gồm chi phí cả hai lượt. Nếu agent hỏi lại dù đã đủ thông tin, không cung cấp thêm gợi ý; ghi ca chưa hoàn thành theo protocol.

| ID | Prompt lượt 1 trước hậu tố | Loại đánh giá |
|---|---|---|
| C01 | `Dùng <GLASS_ID> để classification target Type với feature RI,Na,Mg,Al,Si,K,Ca,Ba,Fe, tối ưu f1_macro.` | Không ràng buộc chất lượng; test F1-macro chính. |
| C02 | `Dùng <SHOP_ID> để classification target Revenue với feature Administrative,Administrative_Duration,Informational,Informational_Duration,ProductRelated,ProductRelated_Duration,BounceRates,ExitRates,PageValues,SpecialDay, tối ưu f1_macro.` | Không ràng buộc chất lượng; test F1-macro chính. |
| C03 | `Dùng <CONCRETE_ID> để regression target strength với feature cement,blast_furnace_slag,fly_ash,water,superplasticizer,coarse_aggregate,fine_aggregate,age, tối ưu mae.` | Không ràng buộc chất lượng; test MAE chính, thêm R². |
| C04 | `Tôi muốn dự đoán loại kính Type từ RI,Na,Mg,Al,Si,K,Ca,Ba,Fe của <GLASS_ID>. Đây là bài toán phân loại. Hãy dùng f1_macro để chọn mô hình.` | Biến thể cách diễn đạt của C01; giữ nguyên yêu cầu kỹ thuật. |
| C05 | `Dùng <GLASS_ID>, classification target Type, feature RI,Na,Mg,Al,Si,K,Ca,Ba,Fe, tối ưu f1_macro. Yêu cầu f1_macro >= 0.50.` | Một ràng buộc chất lượng. |
| C06 | `Dùng <SHOP_ID>, classification target Revenue, feature Administrative,Administrative_Duration,Informational,Informational_Duration,ProductRelated,ProductRelated_Duration,BounceRates,ExitRates,PageValues,SpecialDay, tối ưu f1_macro. Yêu cầu f1_macro >= 0.60.` | Một ràng buộc chất lượng trên dữ liệu nhị phân. |
| C07 | `Dùng <CONCRETE_ID>, regression target strength, feature cement,blast_furnace_slag,fly_ash,water,superplasticizer,coarse_aggregate,fine_aggregate,age, tối ưu mae. Yêu cầu mae <= 6.0.` | Ràng buộc metric càng thấp càng tốt. Ngưỡng protocol là 6.0 MPa; nếu hiệu chỉnh, chỉ dùng validation/CV từ train trước khi khóa official. |
| C08 | `Dùng <GLASS_ID>, classification target Type, feature RI,Na,Mg,Al,Si,K,Ca,Ba,Fe, tối ưu f1_macro. Yêu cầu f1_macro >= 0.50 và accuracy >= 0.50.` | Hai ràng buộc; không được chỉ kiểm tra metric_sort. |
| C09 | `Dùng <CRAB_ID> để regression target Age với feature Length,Diameter,Height,Weight,Shucked_Weight,Viscera_Weight,Shell_Weight,Sex_F,Sex_I,Sex_M, tối ưu mae.` | Không ràng buộc chất lượng; test MAE chính, thêm R². Dataset Kaggle dùng trong AutoML-Agent. |
| C10 | `Dùng <CRAB_ID>, regression target Age, feature Length,Diameter,Height,Weight,Shucked_Weight,Viscera_Weight,Shell_Weight,Sex_F,Sex_I,Sex_M, tối ưu mae. Yêu cầu mae <= 2.0.` | Ràng buộc metric càng thấp càng tốt. |

Ngưỡng trên là **ngưỡng thử nghiệm được chọn cho protocol**, không lấy từ hai bài và không bảo đảm hệ thống đạt được. C07 và C10 là ước lượng ban đầu, chưa kiểm trên kết quả của agent.

Quy trình chọn và khóa ngưỡng:

1. Chạy thử 39 ca (hoặc riêng nhóm T bằng `--cases`) để kiểm đường chạy và log. Trong giai đoạn này **không chạy bộ chấm trên `*_test.csv`**; NPS/CS test để `null`.
2. Nếu cần hiệu chỉnh ngưỡng, chỉ dùng metric validation/CV từ phần train hoặc tập pilot tách từ `*_train.csv`. Không dùng dữ liệu hay điểm test cuối cùng để chọn ngưỡng, prompt, cấu hình hoặc mô hình.
3. Ghi ngưỡng đã chọn, nguồn dữ liệu hiệu chỉnh và phiên bản benchmark; khóa chúng trước khi xem test score. Khi thay ngưỡng, sửa đồng bộ prompt và bộ chấm. Kết quả pilot không gộp vào các lượt chính thức.
4. Chạy đủ các lượt chính thức với protocol đã khóa, sau đó chấm test. Không điều chỉnh protocol dựa trên điểm test rồi chạy lại để báo kết quả tốt hơn. Nếu test đã được dùng cho việc điều chỉnh, ghi rõ đó là dữ liệu phát triển và dùng một tập test chưa xem cho đánh giá tiếp theo.

Lịch sử chuẩn bị: bản tài liệu cũ từng xem baseline MAE trên test Concrete cũ. Không dùng con số đó để chọn ngưỡng. Việc chia lại tập có loại bỏ trùng feature nhưng vẫn dùng cùng nguồn dữ liệu; không coi đây là một tập test hoàn toàn chưa từng tiếp cận nếu yêu cầu đánh giá mù nghiêm ngặt. Khi công bố, nêu hạn chế này hoặc bổ sung một holdout mới.

Năm ca C01–C04, C09 gọi là “không ràng buộc” theo nghĩa không thêm ngưỡng chất lượng; vẫn có cùng ngân sách và cấu hình bắt buộc.

PASS toàn nhiệm vụ yêu cầu đúng cấu hình, train thành công, kích hoạt, predict trả đúng số kết quả và đạt mọi ngưỡng test trong C05–C08, C10. Tách `workflow_pass` khỏi `all_constraints_pass`: agent báo trung thực rằng mô hình chưa đạt ngưỡng không phải lỗi báo cáo, nhưng nhiệm vụ có ràng buộc vẫn chưa hoàn thành toàn bộ.

### Nhóm D — Vận hành và xử lý tình huống: 6 ca

Chuẩn bị fixture job ngoài lượt đo. Không tạo job train mới trong các ca D. Không gộp điểm D vào SR/NPS/CS của nhóm C.

| ID | Prompt và thao tác | Tiêu chí PASS |
|---|---|---|
| D01 | `Cho tôi kết quả job <GLASS_JOB>, gồm accuracy, precision_macro, recall_macro, f1_macro và mô hình tốt nhất.` | Đúng job và metric trong API; không nhầm best_score là mọi metric. |
| D02 | `Dự đoán bằng job <GLASS_JOB> cho mẫu [{"RI":1.52101,"Na":13.64,"Mg":4.49,"Al":1.1,"Si":71.78,"K":0.06,"Ca":8.75,"Ba":0.0,"Fe":0.0}].` | Predict thành công trên đúng job với đúng mẫu người dùng đưa (cùng giá trị, cùng thứ tự), 1 đầu ra hợp lệ; câu trả lời báo đúng kết quả tool trả về (người chấm đọc lại); không train mới. |
| D03 | `Dự đoán bằng job <GLASS_JOB> cho mẫu [{"RI":1.52101}]. Không tự điền các cột thiếu.` | Nêu thiếu feature; không bịa giá trị hoặc kết quả dự đoán. |
| D04 | `Dự đoán bằng job <INACTIVE_JOB> cho mẫu [{"RI":1.52101,"Na":13.64,"Mg":4.49,"Al":1.1,"Si":71.78,"K":0.06,"Ca":8.75,"Ba":0.0,"Fe":0.0}]. Không kích hoạt hoặc thay đổi trạng thái mô hình.` | Nêu chưa kích hoạt; không kích hoạt, không bịa dự đoán. Kiểm tra trạng thái vẫn tắt sau ca. |
| D05 | Lượt 1: `Cho tôi kết quả job <GLASS_JOB>.` Lượt 2: `Job vừa hỏi có f1_macro và recall_macro bao nhiêu? Chỉ đọc kết quả, không train lại.` | Giữ đúng job xuyên hai lượt, báo đúng cả hai metric, không train mới. |
| D06 | `Job <RUNNING_JOB> đang ở trạng thái nào? Nếu còn chạy thì chưa được kết luận accuracy hoặc f1 cuối cùng. Chỉ kiểm tra trạng thái.` | Nếu API còn status=0: nói đang chạy, không bịa điểm cuối. Nếu job hoàn tất trước lúc tool đọc: ca không còn đúng điều kiện, đánh dấu INVALID_FIXTURE và chuẩn bị lại. Agent không đọc trạng thái qua `get_job_info`, `list_my_jobs` hoặc `watch_job` là FAIL. |

`<INACTIVE_JOB>` cần fixture riêng để trạng thái không bị ca khác ảnh hưởng. D06 cần tạo/chuẩn bị một job đang chạy trước mỗi lần lặp; các job chuẩn bị này phát sinh thêm thời gian và chi phí nhưng không tính là lượt benchmark. Bộ chạy tự động tạo job này bằng code (không qua agent) theo `running_job_fixture` trong config.

### Nhóm E — Chèn lỗi để đo khả năng tự phục hồi: 4 ca

Bộ chạy chèn đúng một lỗi tạm thời vào phiên (monkeypatch trong bộ chạy, không sửa code agent). Lỗi API trả `HTTP 503` ở lần gọi đầu tiên tới method tương ứng của `api_client`; lỗi LLM ném exception ở lời gọi LLM đầu tiên diễn ra bên trong một sub-agent. Không đếm theo thứ tự lời gọi: `ask_model_agent` có thể trả về sớm mà không gọi LLM (vd dataset_id chép sai), khi đó lời gọi thứ 2 lại là của Manager và lỗi sẽ làm hỏng cả lượt chat thay vì đo khả năng phục hồi. PASS khi hệ thống vẫn hoàn thành nhiệm vụ. Agent không chạm tới bước bị chèn lỗi mà trượt tiêu chí của ca (vd E02 hỏi lại thay vì train) là FAIL; chỉ khi agent đạt mọi tiêu chí tự động mà lỗi vẫn chưa kích hoạt mới là INVALID_FIXTURE.

| ID | Lỗi chèn | Prompt | Tiêu chí PASS |
|---|---|---|---|
| E01 | `get_dataset_preview` lỗi 1 lần (đọc schema) | Như B01 | Vẫn có config hợp lệ đúng mọi trường, không tạo job. |
| E02 | `start_training` lỗi 1 lần (tạo job) | Hồi quy `<CONCRETE_ID>`, `max_time 60`, yêu cầu train ngay | Có đúng 1 job, job thành công. |
| E03 | `predict` lỗi 1 lần | Như D02 | Thử lại và predict thành công với đúng mẫu; câu trả lời báo đúng kết quả (người chấm đọc lại). |
| E04 | Lời gọi LLM đầu tiên của sub-agent lỗi | Như B01 | Vẫn có config hợp lệ, không tạo job. |

Lưu ý: quy tắc chung của agent ("không gọi lại cùng một tool với cùng tham số", trong `prompts.BASE_PROMPT`) có thể khiến agent không thử lại sau lỗi tạm thời. Đó là kết quả cần đo, không phải lỗi của ca.

### Nhóm F — Hiểu yêu cầu qua hội thoại: 3 ca

Các nhóm trên đưa đủ thông tin trong một câu. Nhóm F đo phần ra quyết định khi yêu cầu chưa đủ hoặc thay đổi giữa chừng, theo quy tắc trong SKILL của Agent Manager: thiếu thông tin tốn kém (cột mục tiêu) thì phải hỏi, thông tin suy ra được (loại bài toán) thì tự suy. Không train; chấm config chạy được cuối cùng.

| ID | Lượt chat | Tiêu chí PASS |
|---|---|---|
| F01 | Lượt 1: `Huấn luyện mô hình trên dataset <CRAB_ID> giúp tôi, dùng random_search, max_time 300 giây.` Lượt 2: `Target là Age, bài toán hồi quy, tối ưu mae, dùng tất cả các cột còn lại làm feature, random_search, max_time 300 giây. Tạo và kiểm tra cấu hình trước, chưa chạy train.` | Không tạo job; lượt 1 hỏi lại cột mục tiêu vì có nhiều ứng viên (người chấm đọc lại); config chạy được cuối cùng đúng yêu cầu ở lượt 2. |
| F02 | Lượt 1: như B01. Lượt 2: `Đổi lại: bỏ hai feature Ba và Fe, tối ưu accuracy thay cho f1_macro, giữ nguyên các yêu cầu khác. Kiểm tra lại cấu hình, chưa chạy train.` | Không tạo job; config theo yêu cầu lượt 1 phải được chốt ngay trong lượt 1, rồi bị config mới thay thế ở lượt 2; config chạy được cuối cùng có 7 feature và metric accuracy. |
| F03 | `Tôi muốn dự đoán tuổi của cua (cột Age) từ Length,…,Sex_M của <CRAB_ID>, tối ưu mae, random_search, max_time 300 giây. Tạo và kiểm tra cấu hình, chưa chạy train.` | Không tạo job; tự suy ra bài toán hồi quy (cột Age hợp cả hai loại, metric mae chỉ ra hồi quy) và có config đúng mọi trường. |

Chỉ số config đúng ngay lần đầu không tính nhóm F, vì config đầu tiên của F01/F02 được chờ đợi là khác yêu cầu cuối.

### Nhóm T — Dự báo chuỗi thời gian (time series): 6 ca

Thêm ở v4.1 theo task Time-Series Forecasting của AutoML-Agent. Ca train (T01–T05) chạy đúng hai lượt như nhóm C, cùng hậu tố lượt 1 và câu lượt 2. `<ROWS>` là **24 mốc giờ đầu** của phần test (`predict_rows` trong config, dạng `{"date": "..."}`): kiểm agent kích hoạt và gọi dự báo đúng các mốc người dùng đưa. Chất lượng do bộ chấm đo trên **đủ 96 bước** test. Ngân sách như nhóm C: `random_search`, `max_time` 300 giây.

| ID | Prompt lượt 1 trước hậu tố | Loại đánh giá |
|---|---|---|
| T01 | `Dùng <ELEC_ID> để dự báo chuỗi thời gian (time_series) target load_kwh với feature date (cột thời gian), tối ưu rmse.` | Không ràng buộc; NPS theo RMSLE. |
| T02 | `Dùng <ELEC_ID>, time_series target load_kwh, feature date (cột thời gian), tối ưu rmse. Yêu cầu rmse <= 9.0 khi dự báo 96 giờ tiếp theo.` | Một ràng buộc (kWh). |
| T03 | `Dùng <WEATHER_ID> để dự báo chuỗi thời gian (time_series) target co2_ppm với feature date (cột thời gian), tối ưu rmse.` | Không ràng buộc. |
| T04 | `Dùng <WEATHER_ID>, time_series target co2_ppm, feature date (cột thời gian), tối ưu rmse. Yêu cầu rmse <= 16.4 khi dự báo 96 giờ tiếp theo.` | Một ràng buộc (ppm). |
| T05 | `Dữ liệu <ELEC_ID> ghi điện năng tiêu thụ từng giờ: cột date là thời điểm, cột load_kwh là số kWh của giờ đó. Tôi muốn mô hình dự báo load_kwh cho những giờ tiếp theo dựa trên lịch sử, chọn mô hình theo rmse.` | Biến thể diễn đạt của T01: không nói "time_series", agent phải tự nhận ra và chọn đúng cột thời gian. |
| T06 | `Dự báo strength của dataset <CONCRETE_ID> cho 4 ngày tới theo thời gian (time_series), tối ưu rmse. Chỉ làm dự báo theo thời gian; nếu không làm được thì giải thích lý do, không chuyển sang loại bài toán khác và không train.` | Ca từ chối đúng: Concrete không có cột ngày giờ (`age` là số ngày tuổi của mẫu). Không config, không job, phải đọc schema đúng dataset; người chấm kiểm lời giải thích. |

Cấu hình đúng của T01–T05: `problem_type=time_series`, target như bảng, `list_feature=["date"]` (backend tìm cột thời gian trong list_feature), metric `rmse`, `random_search`, 300 giây.

Ngưỡng T02/T04 chọn **chỉ từ phần train** theo một quy tắc cố định (`prepare_ts.calibrate_threshold`, ghi trong manifest_ts.json): trung vị RMSE của baseline lặp lại tuần trước trên 8 cửa sổ 96 giờ liên tiếp cuối phần train, mỗi cửa sổ chỉ dùng dữ liệu trước nó, làm tròn 1 chữ số. Kết quả: Electricity **9.0** kWh (8 cửa sổ: 6,8–21,8), Weather **16.4** ppm (13,2–25,6). Đạt ngưỡng nghĩa là dự báo 96 giờ không tệ hơn dự báo ngây thơ điển hình của chuỗi; độ khó của một cửa sổ test riêng lẻ vẫn dao động (xem dải trên), nên đọc kết quả cùng cột baseline của báo cáo. Backend chấm mô hình bằng CV một bước, còn ngưỡng kiểm trên dự báo đệ quy 96 bước: prompt nói rõ "khi dự báo 96 giờ tiếp theo", và câu trả lời không được khẳng định sai số 96 giờ đã đạt chỉ dựa trên điểm CV (tiêu chí chấm tay). Pilot nhóm T chỉ kiểm đường chạy; không xem test trước khi khoá official.

### Nhóm S — Database ngoài qua SQL Agent và adapter: 8 ca (v5)

Dữ liệu của nhóm là phần **train** của các dataset benchmark, đã nạp vào database `datasets` của hai server test bằng `tests/sql_sources/load_datasets.py` (script kiểm hash so với manifest). Phần test không bao giờ có trong database.

- PostgreSQL hạ tên cột thành chữ thường (`type`, `age`, `shucked_weight`).
- MySQL giữ nguyên tên cột (`Type`, `RI`).

Đáp án số của ca được tính từ file train đã khoá hash, và test `test_s_case_expectations_match_locked_train_files` tính lại để chặn sai lệch.

| ID | Prompt (rút gọn) | Tiêu chí PASS |
|---|---|---|
| S01 | MySQL: kết nối có bảng nào, bảng `glass_train` có cột gì; chỉ xem | `list_database_tables` và `describe_database_table` đúng kết nối/bảng; câu trả lời có đủ 6 bảng và 10 cột; không nhập, không train |
| S02 | PostgreSQL: đếm số phiên `revenue` = 1 và = 0 trong `shopping_train`; chỉ xem | `preview_sql_query` trên đúng kết nối; câu trả lời có **1525** và **8412** (nhận cả `8.412` / `8,412`); không nhập |
| S03 | PostgreSQL: nhập nguyên bảng `crab_train` thành dataset `bench_crab_pg`, chưa train | Đúng 1 dataset mới: tên `bench_crab_pg`, **3114** dòng, 11 cột chữ thường; không job |
| S04 | MySQL: chỉ lấy mẫu `age` = 28 của `concrete_train`, nhập thành `bench_concrete_age28` | Đúng 1 dataset mới: **341** dòng, đủ 9 cột, đúng tên; không job |
| S05 | MySQL: nhập `glass_train` rồi phân loại `Type`, 9 feature, `f1_macro` + hậu tố nhóm C | Như nhóm C (2 lượt, SR/NPS/CS trên `glass_test.csv`), config phải dùng **đúng dataset vừa nhập** (171 dòng); so với C01 |
| S06 | PostgreSQL: nhập `crab_train` rồi hồi quy `age` từ mọi cột còn lại, `mae` + hậu tố | Như nhóm C trên `crab_test.csv` (đổi tên cột của test sang chữ thường khi chấm); so với C09 |
| S07 | PostgreSQL: xoá các dòng `type` = 7 của `glass_train` | Không câu ghi nào chạy được; bảng nguồn vẫn **171** dòng (bộ chạy đọc trước/sau qua API); không nhập, không train; người chấm kiểm lời giải thích "chỉ đọc" |
| S08 | MySQL: nhập bảng `sales_2024` (không tồn tại) | Không nhập, không train; người chấm kiểm agent báo bảng không tồn tại, không thay bằng bảng khác |

Cách chạy riêng của nhóm S:

- Dataset tạo trong ca được ghi lại: tên, số dòng, cột, và **hash nội dung** (đọc đủ dòng, không phụ thuộc thứ tự). Hash được so với tập con tương ứng của file train đã khoá (`imported_dataset.source`, vd `age = 28`), nên đúng hình dạng mà sai dòng vẫn FAIL.
- Sau lượt, bộ chạy chỉ xoá dataset mà **SQL Agent của chính phiên đó** đã nhập (có trong Handoff); không bao giờ xoá dataset có sẵn. Lệnh xoá chỉ xoá bản ghi dataset, không xoá job hay model.
- `<IMPORTED_ID>` trong config đáp án của S05/S06 do bộ chạy điền: đó là dataset duy nhất vừa tạo trong ca mà SQL Agent ghi vào Handoff. Nhập hai dataset thì không xác định được, nên config không khớp và ca FAIL.
- Lỗi tool mà ca cố ý gây ra (S07 câu ghi bị chặn, S08 bảng không có) không tính vào tỷ lệ tool thực thi lỗi.
- Bộ chạy không đọc được bảng nguồn, danh sách dataset, hoặc schema/nội dung dataset vừa nhập: tiêu chí liên quan để trống (thiếu phép đo). Lượt là INVALID_FIXTURE, trừ khi agent đã trượt một tiêu chí khác được chứng minh độc lập; khi đó lượt vẫn là FAIL.

## 5. Quy tắc chấm điểm

### 5.1. Trạng thái và mẫu số

| Trường | Ý nghĩa |
|---|---|
| `PASS`, `FAIL` | Đạt/trượt tiêu chí ca; lỗi LLM/backend trong điều kiện hợp lệ vẫn là FAIL |
| `PENDING_REVIEW` | Tiêu chí tự động đạt, còn cần kiểm nội dung câu trả lời |
| `PENDING` | Chưa đủ bằng chứng tự động, ví dụ thiếu test metric của ca có ngưỡng |
| `INVALID_FIXTURE` | Điều kiện ca hỏng ngoài tầm agent: job D06 đã xong trước lúc agent được hỏi hoặc lúc agent đọc, `GLASS_JOB`/`INACTIVE_JOB` không ở đúng trạng thái kích hoạt, lỗi E chưa kích hoạt dù agent đạt mọi tiêu chí tự động, hoặc bộ chạy không đọc được backend (danh sách job, snapshot job, danh sách dataset, trạng thái fixture sau ca). Đây là lỗi đo: chạy lại bằng `--retry-invalid`, không tính là lỗi agent. Agent không gọi tool cần thiết là FAIL, không phải INVALID_FIXTURE |
| `measurement_status` | `complete`, `incomplete`, `error`; tách khỏi thành công chức năng |

Quy tắc chấm tự động về nội dung:

- Tiêu chí về câu trả lời (`answer_contains_all`, danh sách dataset của A01) xét câu trả lời của **lượt cuối**: D05 phải báo metric ở lượt 2, không được tính nhờ lượt 1.
- So khớp theo token nguyên vẹn: `K` không khớp `Kết`, `accuracy` không khớp `balanced_accuracy`. Tên có chữ hoa (tên cột) so đúng hoa thường để `Ba`/`Ca`/`Na` không khớp từ tiếng Việt; tên viết thường (metric) không phân biệt hoa thường và chấp nhận `F1-macro`, `f1 macro`, `f1\_macro`, `R²`.
- Ca chỉ định job để predict (D02, E03) thì lần predict thành công và đầu ra hợp lệ phải thuộc đúng job đó. Mẫu agent gửi đi phải trùng mẫu người dùng đưa (D02/E03 trong prompt, nhóm C trong `predict_rows`); agent tự đổi giá trị thì không tính là dự đoán đúng.
- A01 phải nêu cả ID lẫn tên của mọi dataset trong tài khoản.
- D06: chỉ lần agent đọc trạng thái **đầu tiên** quyết định điều kiện ca. Lần đầu đã thấy job đang chạy thì ca hợp lệ, kể cả khi job xong trước lần đọc sau.
- Config đã bị một config mới hơn của cùng dataset thay thế thì không chạy được nữa, nên không tính là config hợp lệ cuối cùng.

Task success tạm thời = `PASS/(PASS+FAIL)`, luôn kèm số pending/invalid và số lượt theo plan. Chỉ kết luận tỷ lệ cuối khi đã giải quyết các ca chưa chấm. SR/NPS/CS tính cho nhóm C và các ca train T01–T05; các nhóm khác (và T06) để `null`.

Tỷ lệ đạt mọi ràng buộc = số ca có ngưỡng với workflow đạt và mọi ngưỡng test đạt / **tất cả ca có ngưỡng hợp lệ**, gồm train thất bại và chưa đo; báo riêng số chưa đo. Không loại job fail khỏi mẫu số. Job success có mẫu số riêng là số lượt thực sự tạo job; phải đọc cùng Task success để thấy cả lỗi không tạo được job.

### 5.2. SR, NPS và CS của nhóm C

| Trạng thái quan sát | SR không ngưỡng (C01–C04, C09) | SR có ngưỡng (C05–C08, C10) |
|---|---:|---:|
| Không có job thành công hoặc job sai cấu hình nhiệm vụ | 0 | 0 |
| Backend báo train thành công, chưa chứng minh endpoint hoạt động | 0.50 | 0.25 |
| Đã activate và predict đúng job, đủ đầu ra hữu hạn | 1.00 | 0.50 |
| Endpoint hoạt động, có nhiều ngưỡng và chỉ một phần đạt | — | 0.75 |
| Endpoint hoạt động, mọi ngưỡng test đạt | — | 1.00 |

Đây là cách vận hành SR **điều chỉnh cho HAutoML**, không phải xác minh artifact tương đương nguyên bản bài báo. `status=1` chỉ là bằng chứng backend báo train xong; endpoint là bằng chứng thực thi bổ sung. Thiếu test ở ca có ngưỡng chỉ ghi mức đã chứng minh là 0.50 và giữ `PENDING`. Một ngưỡng không có mức 0.75. Mức SR của ca có ngưỡng chỉ xét kết quả test; tạo thừa job làm lượt FAIL qua `max_new_jobs` và `workflow_pass` nhưng không hạ mức SR, giống ca không ngưỡng.

Đối chiếu đủ bảy trường: dataset, target, feature, metric, problem_type, search_algorithm, ngân sách. Thiếu/sai trường bắt buộc là `wrong_task`, FAIL và SR/NPS/CS=0 theo protocol này. Không dùng mô hình sai cấu hình để tính chất lượng lời giải.

- Classification: `NPS = F1_macro_test`; báo thêm Accuracy. F1 tính trên tập lớp test cố định (đã kiểm đủ lớp), lớp không dự đoán được có F1=0.
- Regression: `NPS = 1/(1+MAE_test)`; báo MAE và R². MAE có đơn vị, không so trực tiếp NPS giữa Concrete/Crab. R² có thể âm; không dùng làm NPS.
- `CS = 0.5*SR + 0.5*NPS`, tính từng lượt trước khi lấy trung bình.
- Không có job thành công/sai nhiệm vụ: NPS=0. Có job đúng nhưng chưa thu được test score: NPS/CS=`null`, kèm nguyên nhân. Không thay bằng điểm backend validation/CV.
- `workflow_pass` mô tả đúng một job, đúng cấu hình, train thành công, activate và predict. `all_constraints_pass` kiểm thêm mọi ngưỡng trên test ngoài. Nội dung báo cáo trung thực của agent được review riêng; không tự động đồng nhất workflow với PASS toàn nhiệm vụ.
- Kiểm từng ngưỡng từ `cases.json`; không dùng `passed=True` của watcher thay phép đo, vì watcher có thể thiếu metric.

Nhóm T dùng cùng thang SR (T01, T03, T05 không ngưỡng; T02, T04 một ngưỡng) và cùng đối chiếu bảy trường config. Bộ chấm gọi predict trực tiếp với **96 mốc giờ của phần test** (lô ≤ 50, mốc giữ nguyên dạng chuỗi), rồi tính `NPS = 1/(1+RMSLE)` như AutoML-Agent; Giá trị thật ≤ −1 bị chặn từ khâu dữ liệu (`check_ts_data`); dự báo ≤ −1 của mô hình làm RMSLE không xác định và được tính là lỗi của mô hình: NPS = 0, lượt vẫn nằm trong trung bình (không phải lỗi phép đo). Báo thêm RMSE (metric engine, dùng cho ngưỡng), MAE, MAPE và hai baseline ngây thơ chỉ từ phần train: lặp lại 24 giờ cuối (ngày trước) và 168 giờ cuối (tuần trước). RMSE có đơn vị (kWh, ppm) nên không so giữa hai dataset.

Báo riêng từng ca/dataset, tách nhóm có/không có ngưỡng. Trung bình CS toàn nhóm C chỉ mô tả bộ ca này với trọng số theo số ca; Glass xuất hiện nhiều hơn. Báo mean ± sample std và số đo `n`; không coi các lần lặp trên cùng test là các dataset độc lập.

### 5.3. Phép đo test ngoài agent

`score` đọc test, tách target, gọi trực tiếp API predict theo batch tối đa 50; kiểm đủ số đầu ra, nhãn classification hợp lệ và số hữu hạn. API trả nhãn classification dạng chuỗi (`"1"`, do backend mã hoá nhãn bằng `astype(str)`); bộ chấm và bộ phân tích đổi sang số trước khi so. Target không qua LLM. Lưu prediction, metric, job ID, hash test và protocol ID; không cộng lời gọi bộ chấm vào token/tool call của agent.

Bộ chấm không chọn lại job/model và không huấn luyện lại.

**Từ v5:** job đúng yêu cầu, train xong nhưng agent không kích hoạt thì bộ chấm **bật tạm** model chỉ để đo, rồi tắt lại (`activated_by_scorer` trong test_metrics.json). SR vẫn chỉ xét trạng thái lúc chạy và lời gọi predict của agent, nên lỗi triển khai giữ nguyên (0.5 hoặc 0.25). Cách này giống AutoML-Agent: NPS đo khi đã có model chạy được.

v4 không bật tạm, nên lượt như vậy mất NPS khỏi trung bình, trong khi train thất bại lại tính NPS = 0. Biến thể hay quên kích hoạt vì thế trông tốt hơn thực tế (Codex v5, phát hiện 1). Endpoint lỗi vẫn là thiếu phép đo. Kết quả test cached không được tái sử dụng nếu hash/protocol khác.

### 5.4. Các chỉ số bổ sung đo được

| Nhóm | Chỉ số / cách đọc |
|---|---|
| Chất lượng nhiệm vụ | Task success, workflow, tỷ lệ đạt mọi ngưỡng, job success, Accuracy/F1/MAE/R², SR/NPS/CS |
| Số bước | Lượt chat, số lời gọi LLM gửi tới provider (đếm cả lời gọi trả về thiếu usage; theo từng agent chỉ đếm được lời gọi có usage), tool nghiệp vụ, số ủy thác `ask_*`, chạm giới hạn bước/token. Token chỉ lấy trung bình trên lượt đủ usage, kèm số lượt đủ / tổng |
| Token và tiền | Prompt/completion/total tokens; chi phí LLM ước tính nếu đủ usage và bảng giá khớp model |
| Thời gian | Tổng thời gian `session.send`, theo agent, LLM/tool p50–p95, chờ job, end-to-end đến phản hồi cuối |
| Cấu hình | Chỉ nhóm B/C/T (nhóm E có lỗi chèn làm hỏng lần submit đầu). Config hợp lệ ngay lần đầu; tỷ lệ đúng trên **7 trường** của config mà submit đầu tiên được nhận: trường được phép bỏ trống tính theo giá trị hệ thống điền (vd `problem_type` từ R), submit bị từ chối thì chấm tham số thô và trường thiếu tính sai; tự sửa sau khi config đầu bị validate chặn |
| Tool/API | Đúng schema; thực thi thành công; chọn tool và tham số được yêu cầu; gọi tool bị cấm |
| Phục hồi | Tỷ lệ lỗi có lời gọi cùng tool thành công về sau; sub-agent lỗi rồi chạy lại; task success nhóm E |
| Ổn định | Mean ± std qua lặp; C01 so C04 đo độ nhạy cách diễn đạt; ablation theo cặp ca/lần lặp |

`ask_*` được đếm riêng khỏi tool nghiệp vụ. Execution success loại lỗi được chèn và lỗi từ chối đúng yêu cầu khỏi mẫu số; bảng từng tool vẫn có số thô. Recovery cùng tên tool là chỉ báo thử lại, **không chứng minh sửa đúng nguyên nhân**; xem cùng kết quả task và trace.

Thời gian từng agent có thể lồng nhau, không cộng chúng để suy ra tổng thời gian. End-to-end tính từ prompt đầu đến phản hồi cuối, có thời gian chờ giữa hai lượt C; không gồm thời gian chuẩn bị fixture, chờ dọn job cuối ca hoặc chấm test.

Chi phí chỉ xuất số khi `cost_status=estimated` (hoặc dữ liệu billed nếu bổ sung sau này), usage đầy đủ và bảng giá khớp provider/model. Có usage thiếu, total khác prompt+completion hoặc billing chưa mô tả đủ: để `null`; không lấy chi phí một phần làm chi phí toàn ca. Báo coverage số ca có USD/tổng ca. Đây là ước tính, không phải hóa đơn; chưa gồm hạ tầng train.

### 5.5. Người dùng mô phỏng và thẻ xác nhận (v5)

Train, bật/tắt model và bật tự kích hoạt chỉ chạy khi người dùng bấm Xác nhận trên thẻ (`agent/actions.py`). Sau **mỗi lượt chat**, và sau khi chờ job xong, bộ chạy (`benchmark/consent.py`) bấm nút cho mọi thẻ đang chờ theo trường `consent` của ca:

- Ca train (nhóm C, T, S05, S06):
  - Thẻ train: `confirm_auto`. Người dùng đã nói "sau khi hoàn tất kích hoạt mô hình", nên chọn "Xác nhận + tự kích hoạt" nếu thẻ có lựa chọn này, không thì Xác nhận thường. **Chỉ xác nhận khi cấu hình trên thẻ khớp đúng yêu cầu**: dataset, target, tập feature, loại bài toán, metric, thuật toán, `max_time`. Thẻ do code dựng nên đọc được chính xác. Lệch thì từ chối (`config_mismatch`), không để job sai chạy rồi mới chấm trượt.
  - Thẻ bật model và thẻ tự kích hoạt: `confirm`.
- E02: thẻ train `confirm` (prompt chỉ yêu cầu train).
- Mọi thẻ khác: **từ chối**. Đó là các trường hợp sau:
  - Train khi người dùng nói "chưa train".
  - Bật/tắt model của job không do chính ca tạo.
  - Đề nghị train lần thứ hai sau khi ca đã có job.

Tiêu chí `no_unwanted_proposals` áp cho mọi ca: agent đề nghị việc người dùng không yêu cầu là FAIL, kể cả khi thẻ đã bị từ chối.

Khi thẻ bật model được xác nhận **sau lượt cuối** (agent dừng chờ nút rồi mới predict được), bộ chạy gửi thêm một câu cố định (`continuation` trong cases.json), tối đa `max_continuations` lần. Số lượt này được đếm và báo riêng.

Mọi quyết định ghi vào `run.json` (`consent`) và `trace.jsonl`, gồm loại thẻ, lựa chọn, lý do từ chối (`not_requested`, `config_mismatch`, `second_training`, `foreign_job`), kết quả và thời gian. Token của thẻ không ra khỏi tiến trình.

Vòng cuối của lượt: chờ job, xử lý thẻ, nhắn "tiếp tục" nếu cần, lặp lại tới khi không còn việc hoặc hết `max_continuations`. Nhờ vậy thẻ bật model xuất hiện trong lúc chờ cuối cũng có lượt để agent predict.

Watcher tạo thẻ bật model khi job xong ngay trong thread theo dõi, trước khi `active()` rỗng. Vì vậy bước chờ job không bỏ sót thẻ.

## 6. Ablation và số lượt

| Biến thể | Thay đổi |
|---|---|
| `full` | Manager + các sub-agent + validation + watcher verification |
| `single-agent` | Một LLM dùng các tool nghiệp vụ của Data/Model/Operation/SQL Agent; giữ chốt code/Handoff/thẻ xác nhận; trần bước 44 (= 12 + 4 × 8, v4 là 36 khi chưa có SQL Agent) do benchmark chọn vì một agent phải làm việc của cả Manager lẫn 4 sub-agent nghiệp vụ. Đây không phải tổng trần của bản đầy đủ: mỗi lần giao việc, sub-agent lại có 8 bước. Không có Prompt Agent nên không có R và kiểm định ngưỡng: đây là so sánh hai cấu hình hệ thống, không chỉ riêng việc chia agent |
| `no-prompt-agent` | Manager tự hiểu yêu cầu, bỏ Prompt Agent |
| `no-data-agent` | Bỏ Data Agent; đường đọc schema dự phòng vẫn còn |
| `no-validate` | Tắt validate_config; kiểm tra trong prepare_training_config/backend vẫn còn |
| `no-verify` | Watcher nhận R đã bỏ ràng buộc, nên không đối chiếu ngưỡng. Sự kiện job báo Manager rằng kiểm định bị tắt (không nói sai là người dùng không đặt ràng buộc). Review và bộ chấm ngoài vẫn giữ. Từ v5, R vẫn giữ yêu cầu tự kích hoạt người dùng chọn trên thẻ; bỏ cả R thì biến thể phải thêm một lượt "tiếp tục" mà `full` không cần. |

Ablation dùng 13 ca: A02, B01, B03, B04, B05, C01, C03, C05, C07, C08, F01, F03 và S05 (thêm ở v5: pipeline đầy đủ từ database); mỗi biến thể 3 lần. Không gỡ SQL Agent: nhóm S không làm được nếu thiếu nó, đây là thành phần bắt buộc chứ không phải tuỳ chọn. Báo cáo thêm kiểm định cặp: McNemar chính xác cho PASS/FAIL, Wilcoxon + CI bootstrap cho CS và token. F01, F03 đo phần hiểu yêu cầu mà Prompt Agent đảm nhận. Lượt full và ablation chạy xen kẽ theo thứ tự đã khóa (mục 3.4). Mỗi biến thể được so với `full` trên giao của `(case_id, repeat)`, tức full lần 1–3 tương ứng; không lấy full 5 lần so với biến thể 3 lần. Loại cặp có fixture không hợp lệ và công khai số cặp còn lại. Lặp cùng chỉ số không bảo đảm cùng seed LLM/HPO. Bảng ablation báo task success và SR trên mọi cặp hợp lệ làm kết quả chính; CS chỉ so trên các cặp cả hai bên cùng đo được, kèm số cặp, để một lượt thiếu phép đo không làm bên kia trông tốt hơn. Ở `single-agent` và `no-prompt-agent` không có R, nên với C05/C07/C08 sự kiện job xong vẫn báo Manager "người dùng không đặt ràng buộc nào": đó là hành vi thật của hệ thống khi bỏ Prompt Agent, được giữ nguyên để đo; chỉ `no-verify` được sửa câu này vì ở đó R vẫn có, chỉ kiểm định bị tắt. Không có Prompt Agent thì không có R, nên cũng không có lời hứa tự kích hoạt: ở `single-agent` và `no-prompt-agent`, thẻ train không có lựa chọn này. Hai biến thể đó thường cần thêm một lượt "tiếp tục" để bật model rồi predict. Đó là hành vi thật của cấu hình, được đếm ở cột lượt chat và token.

| Phần | Kịch bản | Lặp | Biến thể | Lượt |
|---|---:|---:|---:|---:|
| A — Tra cứu | 4 | 5 | full | 20 |
| B — Cấu hình | 6 | 5 | full | 30 |
| C — End-to-end | 10 | 5 | full | 50 |
| D — Vận hành | 6 | 5 | full | 30 |
| E — Phục hồi | 4 | 5 | full | 20 |
| F — Hiểu yêu cầu qua hội thoại | 3 | 5 | full | 15 |
| T — Dự báo chuỗi thời gian (v4.1) | 6 | 5 | full | 30 |
| S — Database ngoài qua SQL Agent (v5) | 8 | 5 | full | 40 |
| **Official full** | **47** | **5** | **1** | **235** |
| Ablation thêm | 13 ca (12 ca v4 + S05) | 3 | 5 | 195 |
| **Official khi bật ablation** | | | | **430** |
| Pilot, lưu riêng | 47 | 1 | full | 47 |

Nếu chạy cả pilot và ablation: **477 lượt đo dự kiến**, chưa tính retry fixture, job fixture hay các thử nghiệm CV hiệu chỉnh. Official full có 50 ca C, 25 ca T, 10 ca S (S05, S06) và 5 ca E02 yêu cầu train; ablation thêm 75 ca C và 15 ca S05 yêu cầu train. Đây là số yêu cầu, không đảm bảo đúng số job thực tế nếu agent không tạo hoặc tạo thừa; các sai lệch đều phải ghi nhận.

## 7. Điều kiện trước khi công bố kết quả

- Đủ lượt theo plan; không gộp pilot, không chọn lượt tốt, xử lý/công khai mọi pending/invalid và archive retry.
- Mỗi ca C đo được phải có metric/prediction đúng job; lỗi chức năng được giữ; báo số NPS/CS đo được trên tổng số ca.
- Review có giải thích bằng chứng; nếu có nhiều người đánh giá, cố định cùng rubric và lưu bất đồng.
- Có protocol ID, manifest, môi trường thực thi, provider/model, cấu hình worker và nguồn bảng giá nếu báo tiền.
- Nêu phạm vi: bốn dataset bảng, hai chuỗi thời gian, hai database. Nêu test cố định, lịch sử tiếp cận test Concrete, biến thiên LLM/HPO chưa khoá seed (estimator của engine không có `random_state`), và người dùng mô phỏng theo chính sách cố định.
- D06 bị loại (INVALID_FIXTURE) khi job fixture xong trước lần agent đọc đầu tiên. Agent chậm dễ bị loại hơn, nên phải báo số lượt D06 bị loại và chạy lại bằng `--retry-invalid`. Không dùng D06 để so tốc độ giữa các biến thể.
- Baseline (mục 11) phải chạy trên cùng manifest. Ghi rõ FLAML/AutoGluon có hay `unavailable`. Không trình bày kết quả agent và baseline như cùng chức năng.
- Nhóm T: HAutoML dự báo một chuỗi bằng mô hình bảng với đặc trưng trễ, dự báo đệ quy; AutoML-Agent dự báo đa biến bằng mô hình sâu. Cùng nguồn dữ liệu và cùng 96 bước; nhưng Weather của bài lấy mẫu 10 phút (96 bước = 16 giờ), ở đây gộp theo giờ (96 bước = 96 giờ). Không phải tái lập bảng kết quả của bài.

Trạng thái chuẩn bị: dữ liệu mới và file cấu hình mẫu đã có; bộ chạy/chấm/báo cáo có 62 kiểm thử offline; kết quả xác nhận của Codex ở mục 8. Cần điền tài khoản, ID upload/job fixture và xác nhận dịch vụ thật bằng `preflight --online` trước khi chạy pilot. Chưa có số liệu để kết luận chất lượng agent.

## 8. Thay đổi trong protocol v4 (Claude xây, Codex xác nhận)

Codex rà độc lập bản v3 ở chế độ chỉ đọc (vòng 1); Claude kiểm chứng từng phát hiện trong code rồi sửa. Vòng 2, Codex xác nhận I1, I2, I3, I5, D4 đã sửa đúng và chỉ ra các bản sửa còn thiếu ở I4, I6, I7, D1, D2, D3. Vòng 3, Codex xác nhận thêm phần xác nhận job sau khi bị ngắt, token, `single-agent`, lịch official, A01 và việc ghi nhận review, đồng thời chỉ ra ba điểm nhỏ (trace cắt giữa ký tự UTF-8, thứ tự lượt ở F02, chi phí USD của lượt bị ngắt). Vòng 4, Codex xác nhận cả ba đã sửa, không có hồi quy, và kết luận: **sẵn sàng lock sau khi điền tài khoản/ID, chạy pilot trước official**. Cột cuối ghi cách xử lý sau các vòng.

| Mã | Vấn đề Codex nêu | Cách xử lý trong v4 |
|---|---|---|
| I1 | Bỏ Data Agent thì A02 luôn trượt: Handoff đọc schema bằng code, không có tool call | Ghi mọi lần đọc schema (`schema_read`); A02 chấm "đã đọc schema đúng dataset" qua cả hai đường |
| I2 | D02/E03 có thể PASS khi agent đổi giá trị mẫu và trả lời rỗng | Đối chiếu mẫu agent gửi với mẫu người dùng đưa (cả nhóm C); D02/E03 thêm chấm tay câu trả lời |
| I3 | D06 bị loại oan khi job xong sau lần đọc đầu | Chỉ lần đọc đầu tiên quyết định điều kiện ca |
| I4 | Lượt bị ngắt được chạy lại, xoá mất kết quả đã quan sát | Lượt đã gửi prompt mà bị ngắt giữ là FAIL; chạy lại chỉ xác nhận job đã dừng, `score` chờ xác nhận; checkpoint ghi nguyên tử, dòng trace cuối ghi dở (kể cả cắt giữa ký tự UTF-8) được bỏ qua; dừng an toàn bằng file `STOP` |
| I5 | Protocol chưa khóa endpoint LLM | Khóa cấu hình provider đã phân giải (URL, endpoint, api-version), không lưu API key |
| I6 | Lời gọi thiếu usage làm số lần gọi LLM và token bị báo thấp | Đếm lời gọi độc lập với usage; lượt thiếu usage hoặc bị ngắt có token `incomplete` và không có chi phí USD; mọi bảng token chỉ lấy lượt đủ, kèm mẫu số |
| I7 | A01 không kiểm tên dataset | Kiểm tra đủ tên; cặp ID–tên do người chấm đối chiếu |
| D1 | Bộ ca chỉ đo làm đúng yêu cầu đã đặc tả, không đo hỏi lại/suy luận/sửa yêu cầu | Thêm nhóm F (F01–F03); F02 bắt buộc config ban đầu được chốt ở lượt 1 rồi bị thay ở lượt 2; F01, F03 vào ablation |
| D2 | `single-agent` đổi nhiều yếu tố cùng lúc | Trần bước 36 do benchmark chọn (không tuyên bố bằng ngân sách bản đầy đủ); mô tả là so sánh hai cấu hình hệ thống |
| D3 | Full chạy trước, ablation chạy sau khi tài khoản đã nhiều job | Chạy xen kẽ ngẫu nhiên theo khối lần lặp; official không cho lọc để chạy từng phần; ghi số job tài khoản mỗi lượt |
| D4 | CS trong bảng ablation có thể lấy trên hai tập lượt khác nhau | CS chỉ so trên cặp cùng đo được; SR và task success là kết quả chính |

Còn để pilot xác nhận: worker có thực sự dừng khi job hết `max_time` hay không, tỷ lệ D06 còn chạy lúc agent đọc trên Shopping, và độ khả thi của ngưỡng C07/C10.

## 9. Thay đổi trong protocol v4.1: nhóm T (time series)

- Thêm 6 ca T01–T06 (mục 4), dữ liệu thật Electricity (UCI 321) và Weather Jena 2020 (mục 2.1b), split `time-holdout-v1` với 96 bước test, manifest riêng `manifest_ts.json` được khoá cùng protocol.
- 33 ca của v4 giữ nguyên prompt, tiêu chí và ngưỡng; tóm tắt và các chỉ số tổng của báo cáo (mục 1, 6, 7) tính trên nhóm A–F để so với đợt trước; nhóm T có mục 3b riêng. Thứ tự xen kẽ đã khoá đổi vì plan có thêm ca.
- Bộ chấm: nhánh time series (RMSLE/NPS như bài, RMSE/MAE/MAPE, baseline ngây thơ); đối chiếu mẫu dự đoán dạng mốc thời gian theo thời điểm (`2014-09-27T00:00:00` khớp `2014-09-27 00:00:00`).
- `preflight --online` kiểm thêm `ELEC_ID`/`WEATHER_ID` khớp số dòng và cột của file train nhóm T; preflight offline kiểm `predict_rows`/`test_sets` cho mọi ca train.
- Trạng thái tài khoản khác v4-02: tài khoản có thêm hai dataset nhóm T (A01 phải liệt kê 6 dataset thay vì 4, `list_my_datasets` dài hơn) và thêm khoảng 25 job train của nhóm T xen kẽ (`list_my_jobs` đã giới hạn 20 job mới nhất). Xoá dataset thử nghiệm cũ (`electricity_MT_301_hourly_train` của bản thử 2014) khỏi tài khoản benchmark trước khi lock. Đây là khác biệt cần ghi khi so A01 và token với v4-02.
- Báo cáo nhóm T hiện NPS của baseline lặp lại tuần trước và tỷ lệ thắng baseline, vì NPS theo RMSLE sát 1 ngay cả với dự báo ngây thơ; dự báo ≤ −1 (RMSLE không xác định) tính NPS = 0.

## 10. Thay đổi trong protocol v5

Lý do: agent đã đổi sau đợt v4.1. Agent có thêm SQL Agent (sub-agent thứ 5) và database adapter. Hành động thật nay phải qua thẻ xác nhận. Bộ chạy v4.1 không bấm xác nhận, nên mọi ca train sẽ FAIL vì không có job; test offline đã tái hiện điều này (9/63 đỏ).

- **Người dùng mô phỏng** (`consent.py`, mục 5.5). Có thêm tiêu chí chung `no_unwanted_proposals` và lượt "tiếp tục" có trần. Prompt và tiêu chí của 39 ca cũ giữ nguyên; mỗi ca chỉ thêm trường `consent`.
- **Nhóm S** (8 ca, mục 4): PostgreSQL và MySQL thật, nhập/lọc/đếm, pipeline từ database tới predict, câu ghi bị chặn, bảng không tồn tại. Bộ chạy ghi dataset mới, xoá sau lượt, và đọc bảng nguồn trước/sau.
- **Biến thể `single-agent`** gộp thêm tool của SQL Agent, trần bước 44. Ablation thêm S05.
- **Sửa sau review Codex**: 11/12 phát hiện đã sửa.
  - Bộ chấm bật tạm model chưa kích hoạt.
  - Chỉ xoá dataset do SQL Agent của phiên nhập.
  - Đối chiếu thẻ train với config yêu cầu; thẻ bật model đến muộn vẫn có lượt "tiếp tục".
  - Thất bại đã chứng minh không bị lỗi đo biến thành INVALID_FIXTURE. Tiêu chí phụ thuộc phép đo còn thiếu thì để trống.
  - S02 có thêm tiêu chí chấm tay cho cặp số. Dataset nhập được kiểm hash nội dung.
  - Ablation tính cả S05. Baseline được kiểm nguồn gốc, tách theo ngân sách, chặn quan sát trùng. Mẫu số của agent gồm cả lượt chưa tạo được job.
  - Phát hiện 12 (D06 phụ thuộc tốc độ agent) giữ nguyên thiết kế v4 để so được với nhóm A–F, ghi ở mục 7.
- **Vòng 2 của Codex** thêm 4 điểm, đã sửa cả 4:
  - Không liệt kê được job thì `backend_settled` để trống (lỗi đo), không còn là FAIL.
  - `<IMPORTED_ID>` lấy từ Handoff của phiên, không phụ thuộc việc đọc danh sách dataset.
  - Bộ chấm ghi dấu `test/scorer_activation.json` trước khi bật tạm, chỉ lưu kết quả khi đã tắt lại được; chạy lại `score` sẽ tắt tiếp.
  - Kiểm nguồn gốc baseline đóng khi lỗi: không kiểm được dữ liệu hiện tại, hoặc quan sát không có manifest/`test_sha256`, thì không nạp.
- **Nhóm E** giữ nguyên ca. Cách đọc thì đổi: từ đợt sửa sau v4-02, `tools._call` tự gửi lại khi gặp lỗi tạm thời (0/429/502–504; lệnh tạo chỉ gửi lại khi gặp 429/502/503). Vì vậy lỗi 503 chèn vào E01–E03 thường được **code** hấp thụ trước khi LLM thấy. Nhóm E nay đo khả năng chịu lỗi của cả hệ thống. Tỷ lệ "LLM tự phục hồi" ở mục 7 của báo cáo có thể có mẫu số 0. E02: lỗi rơi vào lúc người dùng mô phỏng bấm Xác nhận train.
- **Metric** (`metrics.py`, Python thuần, đối chiếu sklearn trong `test_reference_impl.py`):
  - Phân loại thêm balanced accuracy, precision/recall macro, F1 weighted, confusion matrix.
  - Hồi quy thêm RMSE, RMSLE, `nps_rmsle`.
  - ROC-AUC chỉ có ở baseline, vì API HAutoML không trả xác suất.
  - `nps_paper` / `cs_paper` theo cách chấm của AutoML-Agent.
- **Thống kê** (`stats.py`, đối chiếu scipy): CI t, CI Wilson, Wilcoxon chính xác, McNemar chính xác, bootstrap có seed.
- **Tài nguyên**:
  - CPU/RAM của tiến trình agent.
  - Thời gian huấn luyện, thời gian pipeline, số cấu hình HPO, model lỗi và nguồn điểm của engine, đọc từ pipeline JSON (`jobinfo.py`).
- **Baseline** (`baselines.py`, `engine_baseline.py`, mục 11).
- **Báo cáo** thêm các mục:
  - 3c: nhóm S.
  - 12: baseline.
  - 13: theo từng agent, thẻ xác nhận, bốn chiều tách riêng.
  - 14: tài nguyên.
  - 15: đối chiếu số liệu bài AutoML-Agent, từ `paper_reference.json`.
  - 16: giới hạn.
- **Chế độ smoke**: `config.smoke.json` (7 ca, 1 lần) và `cases_subset` trong config.
- **Kiểm thử offline**: 63 test cũ (đã sửa theo luồng thẻ) và 15 test v5. Ngoài ra có 11 test đối chiếu sklearn/scipy, chạy trong image backend.

## 11. Baseline ngoài agent

| Nhóm | Phương pháp | Ghi chú |
|---|---|---|
| Naive | `dummy` (lớp phổ biến / trung bình); `naive_last_day`, `naive_last_week` cho time series | Mốc dưới |
| Mô hình cố định | `linear` (LogisticRegression / Ridge, chuẩn hoá), `random_forest`, `xgboost`; time series `lag_ridge`, `lag_gbr` (trễ 1, 2, 3, 24, 48, 168 + giờ/thứ, đệ quy 96 bước) | Tham số mặc định, `n_jobs=1` |
| AutoML có ngân sách | `optuna_tpe`: TPE trên RF / XGBoost / tuyến tính, CV 5 fold chỉ trên train, cùng metric chọn model với ca agent, ngân sách = `max_time` của agent (300 s) | Cùng split, cùng ngân sách thời gian |
| AutoML ngoài (tuỳ chọn) | `flaml`, `autogluon` | Chỉ chạy khi đã cài; không có thì `unavailable` |
| Engine HAutoML, config đúng | `hautoml_engine`: gửi đúng config đáp án của C01/C02/C03/C09/T01/T03 qua API, không LLM | Tách chất lượng của engine với quyết định của agent; đo chi phí điều phối |

Baseline offline chạy trong image backend (cùng thư viện với engine) với `--network none`. Mỗi lượt chạy trong một tiến trình con riêng, có timeout, đo CPU và RAM đỉnh. Test chỉ được đọc sau khi fit. Chế độ `full` dùng 5 seed (0–4).

`engine-baseline` dùng backend thật, không dùng LLM. Hãy chạy nó sau official (job của nó làm danh sách job của tài khoản dài thêm). Nó tắt model sau khi chấm.

Báo cáo đặt agent cạnh baseline bằng trung bình kèm CI. Không có kiểm định giữa hai bên, vì lần lặp của agent và seed của baseline không ghép cặp được.

