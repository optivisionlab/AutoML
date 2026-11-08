# Chạy benchmark v5 trên server, với tài khoản mới tinh

Quy ước:
- **Laptop**: `~/AutoML`. **Server**: `aic@100.82.158.67`, thư mục `~/hautoml-bench`.
- `PY=src/backend/.venv/bin/python`. Mọi lệnh chạy từ thư mục gốc repo.
- `benchmark_artifacts/` không nằm trong git, nên dữ liệu và kết quả phải chép bằng `rsync`.
- Chỉ lệnh `run` tốn tiền LLM.

Mục tiêu là chạy trên **tài khoản benchmark mới**: không có dataset trùng tên, không có job cũ, không có kết nối cũ. Lệnh `setup-account` tự upload dữ liệu, tạo job fixture và kết nối database, rồi ghi toàn bộ ID vào `bench_config.json`.

## 1. Laptop: chốt code và đẩy lên

```bash
cd ~/AutoML
git status                                  # chỉ benchmark/, benchmark.md (và src/ nếu đã sửa agent)
git add benchmark/ benchmark.md
git commit -m "benchmark v5: người dùng mô phỏng, nhóm S, baseline, thống kê, setup-account"
git push origin feat/benchmark_agent
```

Commit trước khi chạy để `run.json` ghi đúng commit của code. Lock vẫn kiểm hash của từng file.

Chép dữ liệu đã khoá hash (split train/test và file gốc), bảng giá và config v5 lên server:

```bash
rsync -av ~/AutoML/benchmark_artifacts/datasets ~/AutoML/benchmark_artifacts/raw ~/AutoML/benchmark_artifacts/pricing.json \
  aic@100.82.158.67:~/hautoml-bench/benchmark_artifacts/
rsync -av ~/AutoML/benchmark_artifacts/bench_config.json aic@100.82.158.67:~/hautoml-bench/benchmark_artifacts/bench_config.v5-laptop.json
```

## 2. Server: code mới và stack

```bash
ssh aic@100.82.158.67
cd ~/hautoml-bench
git fetch && git checkout feat/benchmark_agent && git pull
src/backend/.venv/bin/pip install -r src/backend/agent/requirements.txt
```

**`src/backend/.env` của server** cần các biến sau:

| Biến | Giá trị |
|---|---|
| `AGENT_USER`, `AGENT_PASSWORD` | Tài khoản benchmark **mới**, tạo ở bước 4 |
| `LLM_PROVIDER` + key | Giống laptop (`fpt`), để model là DeepSeek-V4-Flash |
| `DB_CONNECTION_ENCRYPTION_KEY` | Khoá mới: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DB_SOURCE_SQL_ALLOWED_HOSTS` | `hautoml-test-postgres:5432,hautoml-test-mysql:3306` |

Build lại backend, consumer và agent bằng code mới (theo cách stack đã dựng trên server, ví dụ `docker compose up -d --build`), rồi kiểm tra:

```bash
docker compose ps
curl -s localhost:9999/api/v1/database-connections -o /dev/null -w "%{http_code}\n"   # 401 là đúng (cần đăng nhập); 404 là backend cũ
```

Build image dùng cho baseline offline và cho `load_datasets.py`:

```bash
docker build --target test-runner -t hautoml-backend-test:local -f src/backend/deploy/Dockerfile src/backend
```

## 3. Server: hai database test cho nhóm S

```bash
docker compose -f src/backend/tests/sql_sources/docker-compose.yml up -d --wait
docker run --rm --network host -v "$PWD":/repo:ro -w /repo hautoml-backend-test:local \
    python -I src/backend/tests/sql_sources/load_datasets.py      # nạp 6 bảng TRAIN (kiểm hash trước)
docker network ls | grep -i hautoml                               # tên mạng của app, vd automl_hautoml_net
docker network connect <tên-mạng> hautoml-test-postgres
docker network connect <tên-mạng> hautoml-test-mysql
```

Không chạy `docker compose ... down` cho hai container này, vì dữ liệu nằm trong container. Restart thì không sao.

## 4. Server: tài khoản benchmark mới

Đăng ký một tài khoản thường (không phải admin) trên giao diện web của server, ví dụ `bench-v5@...`. Điền email và mật khẩu đó vào `AGENT_USER` / `AGENT_PASSWORD` trong `.env`.

## 5. Server: dựng tài khoản và kiểm tra

```bash
PY=src/backend/.venv/bin/python
cp benchmark_artifacts/bench_config.v5-laptop.json benchmark_artifacts/bench_config.json   # provider/model, ablation, v5
$PY -m pytest benchmark/test_bench.py benchmark/test_v5.py -q -p no:cacheprovider
$PY benchmark/bench.py setup-account            # ~3–5 phút: 6 upload, 2 job Glass, 2 kết nối
$PY benchmark/bench.py preflight --online
```

`setup-account` làm các việc sau:
- **Từ chối chạy nếu tài khoản không trống**: liệt kê dataset, job, kết nối đang có rồi dừng.
- **Chạy lại được khi bị ngắt giữa chừng**: tiến độ ghi ở `benchmark_artifacts/setup_state.json`, nên không upload trùng.
- **Chỉ upload file `*_train.csv`**, rồi kiểm số dòng và cột so với manifest.
- **Tạo 2 job fixture Glass** theo config của C01: `GLASS_JOB` được bật, `INACTIVE_JOB` để tắt.
- **Tạo 2 kết nối chỉ đọc**, kiểm `/test` và kiểm đủ 6 bảng. Mặc định mật khẩu là `ro-test-password` của server test; đổi bằng biến môi trường `BENCH_DB_PASSWORD`.
- **Ghi ID vào `bench_config.json`**, sao lưu bản cũ thành `bench_config.before-setup-*.json`.

`preflight --online` phải in `Preflight đạt`.

Kiểm đường chấm test bằng backend thật (miễn phí, không gọi LLM):

```bash
$PY benchmark/bench.py engine-baseline --id v5-check --datasets glass,electricity --repeats 1
```

## 6. Server: chạy chính thức

Quyết định **trước** khi lock:
- Có chạy ablation không. Không chạy thì đặt `"ablation": {"enabled": false, ...}` trong `bench_config.json`.
- Có đổi `experiment_id` không. Phải đổi nếu đã sửa agent sau pilot, vd `hautoml-v5-02`.

```bash
$PY benchmark/bench.py lock
tmux new -s bench
$PY benchmark/bench.py run
# Ctrl+B rồi D để rời tmux; xem lại: tmux attach -t bench
```

| Tình huống | Cách xử lý |
|---|---|
| Xem tiến độ (cửa sổ khác) | `$PY benchmark/bench.py report` |
| Dừng an toàn | `touch benchmark_artifacts/runs/<experiment_id>/official/STOP`; xoá file rồi `run` lại để chạy tiếp |
| Runner dừng vì còn job | Chờ job xong, rồi `run` lại |
| Có lượt `INVALID_FIXTURE` | `$PY benchmark/bench.py run --retry-invalid` (trước `score`) |
| **Không được làm** | Ctrl+C giữa lượt; sửa code sau lock; train khác bằng tài khoản benchmark |

Khi đủ lượt:

```bash
$PY benchmark/bench.py score
$PY benchmark/bench.py baselines --mode full --id v5-01              # ~2 giờ, Docker không mạng
$PY benchmark/bench.py engine-baseline --id v5-01 --repeats 5         # sau official
$PY benchmark/bench.py report --baselines v5-01
```

## 7. Kéo kết quả về laptop

```bash
rsync -av aic@100.82.158.67:~/hautoml-bench/benchmark_artifacts/runs/<experiment_id> ~/AutoML/benchmark_artifacts/runs/
rsync -av aic@100.82.158.67:~/hautoml-bench/benchmark_artifacts/report/<experiment_id> ~/AutoML/benchmark_artifacts/report/
rsync -av aic@100.82.158.67:~/hautoml-bench/benchmark_artifacts/baselines/v5-01 ~/AutoML/benchmark_artifacts/baselines/
```

Các lượt `PENDING_REVIEW` cần chấm tay: nhờ Claude đọc và ghi `review.json`, rồi chạy lại `report`.
