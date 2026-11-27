# Khắc phục lỗi Critical/Important từ agent-review: Kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sửa 1 lỗi Critical (C-01) và 19 lỗi Important (I-01 … I-19) trong `docs/agent-review.md`, mỗi lỗi có test hồi quy riêng.

**Architecture:** Năm phần độc lập, mỗi phần có thể là một PR riêng:

| Phần | Nội dung | Nơi sửa |
|---|---|---|
| A | Độ đúng trạng thái job và thực thi train | `src/backend/src` |
| B | Context của agent | `agent/tools.py`, `agent_openai.py`, `chat.py`, `team.py` |
| C | Điều khiển vòng lặp | `agent_openai.py`, `team.py` |
| D | Watcher bền vững | `agent/watcher.py`, file mới `agent/watch_store.py` |
| E | Hardening server agent | `agent/server.py`, kèm 2 file frontend |

Thứ tự thực hiện theo thứ tự task bên dưới. A4 phải xong trước A5, vì heartbeat cần event loop không bị chặn.

**Tech Stack:** Python 3.12, FastAPI, pymongo async, aiokafka, scikit-learn/optuna/skopt, OpenAI-compatible SDK, pytest, sqlite3 (stdlib), TypeScript/Next.js.

**Spec:** `docs/agent-review.md`

## Global Constraints

- Không thêm dependency mới. Chỉ dùng stdlib: `sqlite3`, `difflib`, `collections.OrderedDict`.
- Ngôn ngữ thông điệp theo đúng quy ước đang có:
  - Câu hiển thị cho LLM hoặc người dùng trong `agent/` viết bằng tiếng Việt.
  - Thông điệp lỗi và log của backend `src/backend/src` viết bằng tiếng Anh.
- Mọi lời gọi tool vẫn phải có tool message trả lời, để lịch sử hội thoại luôn hợp lệ: không được có `tool_calls` mồ côi.
- Không đổi tên tool mà LLM đang thấy. Chỉ được thêm tham số tuỳ chọn có mặc định.
- `JobStatus`: `RUNNING=0`, `SUCCESS=1`, `FAILED=-1`, `CANCELLED=-2` (`src/core/constants.py:48-52`).
- `MAX_TOOL_RESULT_CHARS = 40_000` giữ nguyên.
- Commit sau mỗi task. Thông điệp commit kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Làm việc trên nhánh mới `fix/agent-review-critical-important`, tách từ `feat/agent_adapter`.
- Lệnh test: chạy từ `src/backend`, dùng venv của Task 0.
  - Backend: `.venv/bin/pytest tests/ -c tests/pytest.ini`
  - Agent: `.venv/bin/pytest agent/tests -c agent/tests/pytest.ini`

## Review Focus

1. **Lệnh huỷ tới khi message train còn nằm trong Kafka** (chưa có task chạy). Lúc consumer nhận message, job phải bị bỏ qua chứ không được train rồi ghi SUCCESS. Test: A1 `test_job_no_longer_running_is_skipped`.
2. **Reaper đánh FAILED nhầm một job vẫn đang chạy** ở consumer khác (event loop bị chặn làm trễ heartbeat). Phải chạy A4 trước A5. Trong cùng một tick, job đang chạy được touch trước khi reap. Test: A5 `test_tick_touches_before_reaping`.
3. **Provider báo vượt context bằng câu chữ hoặc mã khác nhau** (`context_length_exceeded`, `maximum context length`, `prompt is too long`, HTTP 413) vẫn phải được nhận ra. Test: B5 `test_is_context_overflow_variants`.
4. **Tên cột tiếng Việt hoặc khác hoa thường bị gõ sai** vẫn phải được gợi ý đúng. Test: B4 `test_unknown_column_suggestion_handles_case_and_unicode`.
5. **Bản ghi watch mồ côi tồn tại mãi** khi người dùng không bao giờ quay lại. Store phải dọn bản ghi cũ hơn 7 ngày lúc khởi động. Test: D2 `test_store_purges_records_older_than_ttl`.

---

### Task 0: Môi trường và baseline

**Files:** không sửa file nào.

- [ ] **Step 1: Tạo nhánh và venv**

```bash
cd /home/hoang/Projects/Personal/AutoML && git switch -c fix/agent-review-critical-important
cd src/backend && uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt -r tests/requirements.txt -r agent/requirements.txt -r agent/tests/requirements.txt
```

- [ ] **Step 2: Chạy baseline và ghi lại số test pass/fail**

Chạy 2 lệnh test trong Global Constraints. Các test đỏ sẵn từ trước được ghi vào mô tả PR. Không sửa chúng trong kế hoạch này.

`.venv/` đã nằm trong `.gitignore`. Nếu chưa có thì thêm vào và commit riêng.

---

## Phần A: Backend

### Task A1: Ghi trạng thái kết thúc có điều kiện, huỷ ra CANCELLED (C-01)

**Files:**
- Modify: `src/backend/src/modules/trainings/repository.py:19-120`
- Modify: `src/backend/src/modules/trainings/service.py:519-531` (nhánh `CancelledError`), phần đầu `process_training_job` (khoảng `:455`), `_on_job_success`
- Modify: `src/backend/src/modules/inference/service.py:447-448` (`cancel_job`)
- Test: `src/backend/tests/unit/modules/test_trainings.py`, `src/backend/tests/unit/modules/test_inference.py`

**Interfaces:**
- Produces:
  - `TrainingRepository._job_query(job_id: str) -> dict`: gom khối try `ObjectId` đang lặp lại ở nhiều chỗ.
  - `update_success`, `update_failure`, `update_cancelled` đều trả `-> bool`. Query thêm `"status": constants.JobStatus.RUNNING`. Giá trị trả về là `result.matched_count > 0`.
  - `TrainingService._on_job_cancelled(job_id: str, user_id: str, dataset_name: str, reason: str) -> None`
  - `process_training_job(...)` trả `{"skipped": True, "status": <int>}` khi job không còn RUNNING.

- [ ] **Step 1: Viết test (đỏ)**

```python
# test_trainings.py, class TestTrainingRepository
async def test_terminal_writes_only_touch_running_jobs(self):
    job_oid = ObjectId()
    self.mock_jobs.update_one.return_value = MagicMock(matched_count=0)
    assert await self.repo.update_failure(str(job_oid), "x") is False
    assert await self.repo.update_cancelled(str(job_oid), "x") is False
    assert await self.repo.update_success(str(job_oid), {...payload của test_update_success...}) is False
    for call in self.mock_jobs.update_one.call_args_list:
        assert call.args[0] == {"_id": job_oid, "status": constants.JobStatus.RUNNING}

# class TestTrainingPipelineTracking
async def test_cancelled_task_marks_job_cancelled_not_failed(self):
    mock_repo = AsyncMock()
    mock_repo.get_job_by_id.return_value = {"status": constants.JobStatus.RUNNING}
    service = TrainingService(repo=mock_repo, notif_service=AsyncMock())
    with patch.object(service, "_load_dataset_df", AsyncMock(side_effect=asyncio.CancelledError())):
        with self.assertRaises(asyncio.CancelledError):
            await service.process_training_job("job_1", "ds_1", "user_1", {"problem_type": "classification", "target": "t"})
    mock_repo.update_cancelled.assert_awaited_once()
    mock_repo.update_failure.assert_not_awaited()

async def test_job_no_longer_running_is_skipped(self):
    mock_repo = AsyncMock()
    mock_repo.get_job_by_id.return_value = {"status": constants.JobStatus.CANCELLED}
    service = TrainingService(repo=mock_repo, notif_service=AsyncMock())
    result = await service.process_training_job("job_1", "ds_1", "user_1", {"problem_type": "classification", "target": "t"})
    assert result == {"skipped": True, "status": constants.JobStatus.CANCELLED}
    mock_repo.update_pipeline.assert_not_awaited()
```

```python
# test_inference.py: theo mẫu test cancel_job đang có trong file
async def test_cancel_of_job_that_just_finished_is_rejected(...):
    # get_job_by_id trả RUNNING, nhưng repo.update_cancelled trả False (job vừa kết thúc)
    # -> CustomException với status_code 409, không gửi Kafka cancel
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

`.venv/bin/pytest tests/unit/modules/test_trainings.py tests/unit/modules/test_inference.py -c tests/pytest.ini -k "running_jobs or cancelled_task or no_longer_running or just_finished"`

Kết quả mong đợi: 4 FAIL.

- [ ] **Step 3: Cài đặt**
  - **Repository:** dùng `_job_query` cho mọi hàm. Ba hàm ghi trạng thái kết thúc lọc theo RUNNING và trả bool.
  - **Bỏ qua job hết RUNNING:** đầu `process_training_job` đọc `get_job_by_id`. Chỉ khi `isinstance(job, dict)` và `job.get("status") != RUNNING` thì log rồi trả `{"skipped": True, "status": ...}`. Kiểm `isinstance` là bắt buộc: các test cũ dùng `AsyncMock` repo nên trả về MagicMock, không phải dict.
  - **Nhánh `CancelledError`:** gọi `_on_job_cancelled` thay cho `_on_job_failure`. Hàm này gọi `update_cancelled` và chỉ đẩy thông báo khi hàm đó trả True.
  - **`_on_job_success`:** nếu `update_success` trả False thì `logger.warning` (job đã bị huỷ hoặc fail trong lúc chạy; artifact vẫn giữ) và không đẩy thông báo thành công.
  - **`cancel_job`:** `update_cancelled` trả False thì raise `CustomException(status_code=409, detail="Job already finished; nothing to cancel", error_code=BAD_REQUEST)` trước khi gửi Kafka.

- [ ] **Step 4: Chạy lại 4 test (xanh), sau đó chạy toàn bộ suite backend (không có test hồi quy mới bị đỏ)**

- [ ] **Step 5: Commit** `fix(trainings): ghi trạng thái kết thúc có điều kiện, huỷ job ra CANCELLED (C-01)`

---

### Task A2: Validate `TrainingConfig`: metric theo loại bài toán, kẹp timeout (I-04, một phần I-02)

**Files:**
- Modify: `src/backend/src/modules/datasets/schemas.py:74-81`
- Modify: `src/backend/src/core/constants.py` (thêm hằng)
- Test: `src/backend/tests/unit/modules/test_datasets.py`

**Interfaces:**
- Produces:
  - `constants.DEFAULT_TRAINING_TIMEOUT_SECONDS = 3600`
  - `constants.MIN_TRAINING_TIMEOUT_SECONDS = 60`
  - `constants.MAX_TRAINING_TIMEOUT_SECONDS = 86400` (khớp `MIN_MAX_TIME` và `MAX_MAX_TIME` trong `validate_config.py`)
  - Sau khi validate: `TrainingConfig.metric_sort` đã chuẩn hoá (lowercase, `-` thành `_`), `TrainingConfig.timeout` luôn là `int` nằm trong khoảng cho phép.

- [ ] **Step 1: Viết test (đỏ)**

```python
def test_training_config_rejects_metric_not_in_problem_list():
    with pytest.raises(ValidationError) as err:
        TrainingConfig(problem_type="regression", metric_sort="rmse", list_feature=["a"], target="y")
    assert "mse" in str(err.value)          # thông báo liệt kê metric hợp lệ

def test_training_config_normalizes_metric_name():
    cfg = TrainingConfig(problem_type="classification", metric_sort="F1-Macro", list_feature=["a"], target="y")
    assert cfg.metric_sort == "f1_macro"

@pytest.mark.parametrize("given,expected", [(None, 3600), (10, 60), (10**9, 86400), (900, 900)])
def test_training_config_timeout_defaults_and_clamps(given, expected):
    cfg = TrainingConfig(problem_type="regression", metric_sort="mse", list_feature=["a"], target="y", timeout=given)
    assert cfg.timeout == expected

def test_training_config_rejects_unknown_problem_type():
    with pytest.raises(ValidationError):
        TrainingConfig(problem_type="clustering", metric_sort="mse", list_feature=["a"], target="y")
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

- [ ] **Step 3: Cài đặt**
  - Một `@model_validator(mode="after")` lấy danh sách metric từ `src.core.search_space`: `CLASSIFICATION_METRIC_LIST`, `REGRESSION_METRIC_LIST`, `TIME_SERIES_METRIC_LIST`.
  - `problem_type` không hợp lệ thì `ValueError`. FastAPI tự trả 422.

- [ ] **Step 4: Chạy lại test (xanh) và toàn bộ suite backend.** Các test integration gửi metric lạ phải được sửa lại cho đúng metric. Ghi các chỗ sửa vào commit.

- [ ] **Step 5: Commit** `fix(datasets): validate metric_sort theo problem_type, kẹp timeout huấn luyện (I-04)`

---

### Task A3: Trial HPO lỗi được ghi lại, tìm kiếm không có trial nào thành công thì báo lỗi (I-03)

**Files:**
- Modify: `src/backend/src/modules/hpo/base.py`:
  - `:29` (thêm exception)
  - `:206-290` (`_evaluate_candidate`, bọc `fit` ở cả nhánh không có split lẫn vòng fold)
  - `:294-332` (`_record_trial`)
  - `:334-343` (`_finalize_search`)
- Modify (các chỗ bắt lỗi):
  - `grid_search.py:72`
  - `random_search.py:78`
  - `genetic_algorithm.py:186`
  - `bayesian_search.py:111,149,180`
  - `tpe_search.py:84,128`
  - `src/modules/hpo/__init__.py` (export)
- Test: `src/backend/tests/unit/modules/test_hpo.py`

**Interfaces:**
- Produces:
  - `class TrialFailed(TrialPruned)`: subclass, nên mọi `except TrialPruned` sẵn có vẫn bắt được.
  - `class HPOSearchFailed(RuntimeError)`
  - `_record_trial(..., is_pruned: bool, error: str | None = None)`
  - Mỗi phần tử `trials_history_` có thêm khoá `"error"`.

- [ ] **Step 1: Viết test (đỏ)**

```python
class _FailOn(BaseEstimator, ClassifierMixin):
    def __init__(self, fail=False): self.fail = fail
    def fit(self, X, y):
        if self.fail: raise ValueError("solver clash")
        self.classes_ = np.unique(y); return self
    def predict(self, X): return np.full(len(X), self.classes_[0])

@pytest.mark.parametrize("searcher_cls", [GridSearch, RandomSearch, TPESearch])
def test_failing_candidate_is_recorded_and_search_continues(searcher_cls):
    s = searcher_cls(estimator=_FailOn(), param_grid={"fail": [True, False]}, cv=..., scoring=..., refit="accuracy", n_jobs=1, verbose=0)  # cùng tham số như các test hiện có
    s.fit(X_cls, y_cls)
    assert s.best_params_ == {"fail": False}
    assert any("ValueError" in (t.get("error") or "") for t in s.trials_history_)

@pytest.mark.parametrize("searcher_cls", [GridSearch, TPESearch])
def test_all_candidates_failing_raises(searcher_cls):
    s = searcher_cls(estimator=_FailOn(), param_grid={"fail": [True]}, ...)
    with pytest.raises(HPOSearchFailed, match="solver clash"):
        s.fit(X_cls, y_cls)
```

Các test hiện có dùng `unittest.TestCase`. Có thể viết test mới thành các method trong `TestHPOAlgorithms`, dùng `self.X_cls` và `self.cls_scoring`, với `subTest` thay cho `parametrize`.

- [ ] **Step 2: Chạy, xác nhận đỏ**

- [ ] **Step 3: Cài đặt**
  - **Gói lỗi fit:** `fit` lỗi thì `raise TrialFailed(f"{type(exc).__name__}: {str(exc)[:300]}") from exc`.
  - **Chỗ bắt lỗi:** mỗi chỗ bắt dùng `except TrialPruned as exc` rồi truyền `error=str(exc) if isinstance(exc, TrialFailed) else None`.
  - **`_finalize_search`:** nếu có trial nhưng không trial nào có `is_pruned=False`, và có ít nhất một trial có `error`, thì `raise HPOSearchFailed(f"All {n} trials failed; first error: {first}")`. Nhánh `cv_results_["params"]` rỗng (grid rỗng) giữ nguyên.
  - **TPE và Bayesian:** đổi `logger.warning` trong `except Exception` thành `logger.error`.
  - Không sửa gì ở tầng gọi: `service.py:130-133` đã bỏ qua model có task lỗi.

- [ ] **Step 4: Chạy lại test (xanh) và toàn bộ `test_hpo.py`, `test_trainings.py`**

- [ ] **Step 5: Commit** `fix(hpo): ghi nhận trial lỗi, báo lỗi khi mọi trial đều hỏng (I-03)`

---

### Task A4: Tiền xử lý rời event loop, `driver.get` có hạn (I-02)

**Files:**
- Modify: `src/backend/src/modules/trainings/service.py:115-145` và `:232` (lời gọi `cls._prepare_pipeline_inputs`)
- Test: `src/backend/tests/unit/modules/test_trainings.py`

**Interfaces:**
- Produces: `TrainingService._resolve_outputs(driver, raw_outputs: list, deadline: float | None) -> list[dict]` (staticmethod async).
  - `deadline` tính theo `asyncio.get_running_loop().time()`.
  - Output lỗi hoặc quá hạn thì bị bỏ, kèm `logger.warning`.

- [ ] **Step 1: Viết test (đỏ)**

```python
async def test_resolve_outputs_skips_failed_and_slow_refs(self):
    ref = lambda: SimpleNamespace(object_id="x")
    async def get(r):
        if r is slow: await asyncio.sleep(5)
        if r is bad: raise RuntimeError("worker died")
        return {"model": "ok"}
    good, bad, slow = ref(), ref(), ref()
    driver = SimpleNamespace(get=get)
    loop = asyncio.get_running_loop()
    started = loop.time()
    out = await TrainingService._resolve_outputs(driver, [good, bad, slow, {"model": "inline"}], loop.time() + 0.2)
    assert out == [{"model": "ok"}, {"model": "inline"}]
    assert loop.time() - started < 1.0

async def test_preprocessing_runs_off_event_loop(self):
    # patch "src.modules.trainings.service.asyncio.to_thread" bằng AsyncMock trả đúng tuple 6 phần tử
    # mà các test pipeline đang dựng; assert to_thread được gọi với TrainingService._prepare_pipeline_inputs
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

- [ ] **Step 3: Cài đặt**
  - `deadline = loop.time() + wait_timeout`, chỉ khi `wait_timeout` có giá trị.
  - Vòng `raw_outputs` (`:136-142`) chuyển sang `_resolve_outputs`. Mỗi `driver.get` được bọc trong `asyncio.wait_for(..., max(1.0, deadline - loop.time()))` và có try riêng.
  - `:232` đổi thành `await asyncio.to_thread(cls._prepare_pipeline_inputs, ...)`.
  - Huỷ tác vụ từ xa trên PyMapReduce: ngoài phạm vi kế hoạch (chưa kiểm chứng API). Ghi TODO trong mô tả PR.

- [ ] **Step 4: Chạy lại test (xanh) và `test_trainings.py`**

- [ ] **Step 5: Commit** `fix(trainings): tiền xử lý chạy ngoài event loop, driver.get tuân theo timeout (I-02)`

---

### Task A5: Heartbeat, reaper job mồ côi, shutdown có trật tự (I-01)

**Files:**
- Modify: `src/backend/src/modules/trainings/repository.py` (3 hàm mới)
- Modify: `src/backend/src/kafka_consumer.py`
- Test: tạo mới `src/backend/tests/unit/test_kafka_consumer.py`, thêm vào `tests/unit/modules/test_trainings.py`

**Interfaces:**
- Consumes: các hàm ghi có điều kiện của A1.
- Produces (repository):
  - `TrainingRepository.touch_heartbeat(job_ids: list[str]) -> None`: `update_many({"_id": {"$in": ...}, "status": RUNNING}, {"$set": {"heartbeat_at": <epoch float>}})`
  - `TrainingRepository.fail_stale_jobs(cutoff: float, reason: str) -> int`: `update_many({"status": RUNNING, "heartbeat_at": {"$lt": cutoff}}, {"$set": {"status": FAILED, "infor": reason}})`, trả `modified_count`.
  - `TrainingRepository.fail_jobs(job_ids: list[str], reason: str) -> int`: chỉ chạm job còn RUNNING.
- Produces (`kafka_consumer.py`):
  - Hằng: `HEARTBEAT_SECONDS = 60`, `STALE_AFTER_SECONDS = 300`, `SHUTDOWN_WAIT_SECONDS = 30`
  - `async def heartbeat_tick(repo, active_jobs: dict[str, asyncio.Task], stale_after: float = STALE_AFTER_SECONDS) -> int`
  - `async def shutdown_active_jobs(repo, active_jobs: dict[str, asyncio.Task], timeout: float = SHUTDOWN_WAIT_SECONDS) -> None`

- [ ] **Step 1: Viết test (đỏ)**

```python
async def test_tick_touches_before_reaping():
    repo = AsyncMock(); order = []
    repo.touch_heartbeat.side_effect = lambda ids: order.append(("touch", ids))
    repo.fail_stale_jobs.side_effect = lambda cutoff, reason: order.append(("reap", cutoff)) or 0
    task = asyncio.create_task(asyncio.sleep(10))
    await heartbeat_tick(repo, {"j1": task}, stale_after=300)
    assert order[0] == ("touch", ["j1"]) and order[1][0] == "reap"
    assert abs(order[1][1] - (time.time() - 300)) < 5
    task.cancel()

async def test_shutdown_fails_running_jobs_before_cancelling():
    repo = AsyncMock(); task = asyncio.create_task(asyncio.sleep(10))
    await shutdown_active_jobs(repo, {"j1": task}, timeout=1)
    repo.fail_jobs.assert_awaited_once()
    assert repo.fail_jobs.await_args.args[0] == ["j1"] and task.cancelled()

# test_trainings.py
async def test_fail_stale_jobs_query(self):
    self.mock_jobs.update_many.return_value = MagicMock(modified_count=2)
    assert await self.repo.fail_stale_jobs(100.0, "worker lost") == 2
    q = self.mock_jobs.update_many.call_args.args[0]
    assert q == {"status": constants.JobStatus.RUNNING, "heartbeat_at": {"$lt": 100.0}}
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

- [ ] **Step 3: Cài đặt**
  - **Touch khi nhận job:** khi nhận message train, gọi `await training_repo.touch_heartbeat([job_id])` trước `create_task`.
  - **Vòng heartbeat:** chạy nền, gọi `heartbeat_tick` mỗi `HEARTBEAT_SECONDS`, nuốt và log lỗi. Vòng này được huỷ trong `finally`.
  - **Lý do khi reap:** `"Training worker stopped unexpectedly (worker lost); please start the job again."`
  - **Shutdown:** trong `finally`, trước khi ngắt Kafka/DB, gọi `shutdown_active_jobs` với lý do `"Training worker was shut down (deploy/restart) while the job was running."`. Vì job đã thành FAILED trước khi bị huỷ, `update_cancelled` có điều kiện của A1 sẽ không ghi đè thành CANCELLED.
  - **Job chưa từng được nhận** (không có `heartbeat_at`) không bao giờ bị reaper chạm. Trường hợp này do D1 xử lý (trần pha queued).

- [ ] **Step 4: Chạy lại test (xanh) và toàn bộ suite backend**

- [ ] **Step 5: Commit** `fix(consumer): heartbeat + reaper cho job mồ côi, shutdown đánh dấu job đang chạy (I-01)`

---

### Task A6: Payload lỗi và phân bố lớp có trần (I-11, phía backend)

**Files:**
- Modify: `src/backend/src/core/utils.py` (hàm mới)
- Modify: `src/backend/src/modules/trainings/service.py:82-83` và `:533`
- Modify: `src/backend/src/modules/inference/service.py:188`
- Test: `src/backend/tests/unit/core/test_utils.py`, `src/backend/tests/unit/modules/test_trainings.py`

**Interfaces:**
- Produces:
  - `short_error(exc: BaseException, limit: int = 1000) -> str`: dạng `"{Type}: {msg}"`, cắt kèm `"… (truncated N chars)"`.
  - `trainings.service._class_distribution(labels: pd.Series, limit: int = 20) -> dict[str, int]`: lấy top `limit` theo số lượng, phần còn lại gộp vào khoá `"__other__"`.

- [ ] **Step 1: Viết test (đỏ)**

```python
def test_short_error_truncates():
    msg = short_error(KeyError("c" * 5000), limit=1000)
    assert msg.startswith("KeyError: ") and len(msg) < 1100 and "truncated" in msg

def test_class_distribution_is_capped():
    s = pd.Series([str(i) for i in range(100)] + ["0"] * 5)
    d = _class_distribution(s, limit=20)
    assert len(d) == 21 and d["0"] == 6 and d["__other__"] == 80
```

- [ ] **Step 2–4: Đỏ, cài đặt, xanh.** Dùng `short_error` tại `service.py:533` (`f"Training failure: {short_error(e)}"`) và tại `inference/service.py:188`.

- [ ] **Step 5: Commit** `fix(backend): cắt thông điệp lỗi và class_distribution trả cho client (I-11)`

---

## Phần B: Context của agent

### Task B1: Cắt kết quả tool mà vẫn giữ trường có cấu trúc; giới hạn report sub-agent (I-06)

**Files:**
- Modify: `src/backend/agent/agent_openai.py:934-957`
- Modify: `src/backend/agent/team.py:745-764` (`_run_loop`)
- Test: `src/backend/agent/tests/test_agent.py`

**Interfaces:**
- Produces:
  - `agent_openai._shrink_strings(value: dict, limit: int) -> dict | None`: trả bản sao đã thu nhỏ, hoặc `None` khi không thu được xuống dưới `limit`.
  - `team.REPORT_MAX_CHARS = 8_000`
  - `_bounded_tool_content(result: dict) -> str` giữ chữ ký cũ.

- [ ] **Step 1: Viết test (đỏ)**

Đầu `test_agent.py` thêm `import threading` và `from agent import team`. Các task B và C dùng chung 2 import này.

```python
def test_oversized_tool_result_keeps_structured_fields():
    result = {"ok": True, "report": "x" * 100_000,
              "configs": [{"config_id": "cfg-1"}], "awaiting_confirmation": [{"action_id": "a1"}]}
    content = agent_openai._bounded_tool_content(result)
    parsed = json.loads(content)
    assert len(content) <= agent_openai.MAX_TOOL_RESULT_CHARS
    assert parsed["configs"][0]["config_id"] == "cfg-1" and parsed["awaiting_confirmation"][0]["action_id"] == "a1"
    assert parsed["result_truncated"] is True and "partial" not in parsed

def test_many_small_items_fall_back_to_partial():
    content = agent_openai._bounded_tool_content({"ok": True, "rows": [{"a": i} for i in range(20_000)]})
    assert len(content) <= agent_openai.MAX_TOOL_RESULT_CHARS and "partial" in json.loads(content)

def test_subagent_report_is_clipped(session):
    create = Mock(side_effect=[
        response(tool="ask_data_agent", arguments={"task": "Mô tả dataset"}),
        response("y" * 20_000), response("Xong"),
    ])
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    session.send("Mô tả dataset")
    tool_msg = next(m for m in session.messages if m["role"] == "tool")
    assert len(json.loads(tool_msg["content"])["report"]) <= team.REPORT_MAX_CHARS + 50
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

`.venv/bin/pytest agent/tests -c agent/tests/pytest.ini -k "oversized or small_items or report_is_clipped"`

- [ ] **Step 3: Cài đặt**
  - `_shrink_strings`:
    - Lặp tối đa 40 lần. Mỗi lần tìm lá chuỗi dài nhất (đệ quy qua dict và list) và cắt còn một nửa, tối thiểu 200 ký tự, kèm `f"…(lược {n} ký tự)"`.
    - Dừng khi `json.dumps` vừa `limit - 500`.
  - `_bounded_tool_content`:
    - Thử `_shrink_strings` trước. Thành công thì thêm `result_truncated: True` và `note` (câu note giữ như cũ).
    - Không thành công thì dùng đường `partial` sẵn có.
  - `_run_loop`: cắt `report` bằng `REPORT_MAX_CHARS` trước khi trả về.

- [ ] **Step 4: Chạy lại test (xanh) và toàn bộ suite agent**

- [ ] **Step 5: Commit** `fix(agent): cắt kết quả tool giữ trường handoff, giới hạn report sub-agent (I-06)`

---

### Task B2: Kết quả gọn cho `get_job_info` và `list_my_datasets`, mô tả `job_id` (I-11, I-12, I-14)

**Files:**
- Modify: `src/backend/agent/tools.py:139-156` (`list_my_datasets`, `get_dataset_info`) và `:542-555` (`get_job_info`)
- Modify: `src/backend/agent/watcher.py:44` (`LOWER_IS_BETTER` chuyển sang tools)
- Modify: `src/backend/agent/team.py:806, 930, 1278` (chuyển sang `all_my_datasets`)
- Modify: `src/backend/agent/agent_openai.py:220-229` và schema của `list_my_datasets`, `get_job_info` (khoảng `:312`, `:464`)
- Test: `src/backend/agent/tests/test_agent.py`

**Interfaces:**
- Produces:
  - `tools.LOWER_IS_BETTER = {"mse", "mae", "mape", "rmse"}`. Watcher dùng `tools.LOWER_IS_BETTER`.
  - `tools.JOB_STATUS_LABELS = {0: "running", 1: "succeeded", -1: "failed", -2: "cancelled"}`
  - `tools.all_my_datasets(client) -> dict`: hành vi cũ, giữ bản ghi thô, chỉ cho code nội bộ dùng.
  - `tools.list_my_datasets(client, search: str = "", limit: int = 20) -> dict`. Trả về:
    - `{"ok", "total", "shown", "datasets": [{"dataset_id", "name", "created", "description"}], "hint"?}`
    - Sắp xếp theo `createDate` mới nhất trước. `description` qua `_trim_cell` (≤200). `limit` kẹp trong 1..100.
  - `tools.get_job_info(client, job_id: str, include_all_models: bool = False) -> dict`. Trả về:
    - `{"ok", "job_id", "status", "status_label", "dataset_id", "dataset_name", "config": {"target", "problem_type", "metric_sort", "search_algorithm", "max_time", "feature_count"}, "best_model", "best_score", "activate", "create_at", "leaderboard": [{"model", "score"}] (≤5, sắp theo hướng metric), "models_total", "error"?, "score_source"?, "score_note"?, "all_models"?}`
    - `error` chỉ có khi status là failed/cancelled. Lấy từ `infor`, cắt còn 1000 ký tự.
  - Mô tả mới của `_JOB_ID`: `"job_id thật, lấy từ list_my_jobs (mục 'Job do chính phiên chat này tạo') hoặc từ sự kiện xác nhận huấn luyện. start_training KHÔNG trả job_id; đừng đoán."`

- [ ] **Step 1: Viết test (đỏ)**

```python
class OneJobBackend(Backend):
    """list_jobs luôn trả đúng một job (dùng chung cho B2 và D1)."""
    def __init__(self, job): super().__init__(); self.job = job
    def list_jobs(self): return [self.job]
    def activate_model(self, job_id, activate): return {}

def _scored_job(**over):
    base = {"_id": "job-1", "user": {"id": "user-1"}, "status": -1, "infor": "E" * 5000,
            "data": {"id": "dataset-1", "name": "demo"},
            "config": {"target": "y", "problem_type": "regression", "metric_sort": "mse", "list_feature": [f"f{i}" for i in range(500)]},
            "orther_model_scores": [{"model_name": f"M{i}", "scores": {"mse": float(i)}, "best_params": {"a": i}} for i in range(12, 0, -1)]}
    return {**base, **over}

def test_get_job_info_is_compact_by_default():
    info = tools.get_job_info(OneJobBackend(_scored_job()), "job-1")
    text = json.dumps(info)
    assert "list_feature" not in text and info["config"]["feature_count"] == 500
    assert len(info["leaderboard"]) == 5 and info["models_total"] == 12
    assert info["leaderboard"][0]["model"] == "M1"          # mse nhỏ nhất đứng đầu
    assert info["status_label"] == "failed" and len(info["error"]) <= 1020

def test_get_job_info_include_all_models_returns_full_scores():
    info = tools.get_job_info(OneJobBackend(_scored_job()), "job-1", include_all_models=True)
    assert len(info["all_models"]) == 12 and "best_params" in info["all_models"][0]

def test_list_my_datasets_is_brief_limited_and_searchable():
    # Backend.list_datasets trả 100 dataset, mỗi cái description "d"*5000, createDate tăng dần, dataName f"ds{i}"
    out = tools.list_my_datasets(api)
    assert out["total"] == 100 and out["shown"] == 20 and out["datasets"][0]["name"] == "ds99"
    assert set(out["datasets"][0]) == {"dataset_id", "name", "created", "description"}
    assert len(out["datasets"][0]["description"]) <= 220
    assert [d["name"] for d in tools.list_my_datasets(api, search="DS5")["datasets"]][:2] == ["ds59", "ds58"]

def test_job_id_description_does_not_point_to_start_training():
    assert "start_training KHÔNG trả job_id" in agent_openai._JOB_ID["description"]
```

`test_get_job_info_and_activation_card_carry_the_score_source` đang có phải tiếp tục xanh mà không cần sửa.

- [ ] **Step 2: Chạy, xác nhận đỏ**

- [ ] **Step 3: Cài đặt** theo Interfaces.
  - Schema `list_my_datasets` có thêm `search` (string) và `limit` (integer, minimum 1, maximum 100, default 20).
  - Schema `get_job_info` có thêm `include_all_models` (boolean, default false).
  - Mô tả tham số `_DATASET_ID` đổi `"lấy từ trường _id"` thành `"lấy từ trường dataset_id của list_my_datasets"`.
  - Ba chỗ trong `team.py` gọi `tools.all_my_datasets(api)`.

- [ ] **Step 4: Chạy lại test (xanh) và toàn bộ suite agent**

- [ ] **Step 5: Commit** `fix(agent): get_job_info / list_my_datasets trả bản gọn, sửa mô tả job_id (I-11, I-12, I-14)`

---

### Task B3: `get_dataset_schema` có trần cho Data Agent (I-10)

**Files:**
- Modify: `src/backend/agent/tools.py`: thêm `schema_for_llm` gần `get_dataset_schema` (`:254`), dùng chung `_cap_items` với `team.profile_brief` (`team.py:381-392`)
- Modify: `src/backend/agent/team.py:1082-1087`, `:369-392`
- Modify: `src/backend/agent/agent_openai.py`: mô tả tool `get_dataset_schema` (khoảng `:333`)
- Test: `src/backend/agent/tests/test_agent.py`

**Interfaces:**
- Produces:
  - `tools.MAX_COLUMNS_FOR_LLM = 60`. `team._MAX_PROFILE_COLUMNS` trỏ về hằng này.
  - `tools._cap_items(items: list, budget: int) -> tuple[list, int]`: bỏ từng mục không vừa ngân sách, không cắt cả phần đuôi. Thay cho vòng lặp ở `team.py:383-392`.
  - `tools.schema_for_llm(schema: dict) -> dict`, gồm:
    - `columns`: ≤ `MAX_COLUMNS_FOR_LLM`, tên ≤ 128 ký tự
    - `all_column_names`: qua `_fit_names`
    - `columns_truncated: bool`, `columns_hidden: int`, `all_column_names_hidden: int`
    - `time_columns`: qua `_cap_items(…, 4_000)`
  - `AgentTeam.get_dataset_schema(...)` vẫn lưu bản đầy đủ vào `handoff.profiles`, nhưng trả `tools.schema_for_llm(result)` khi `ok`.

- [ ] **Step 1: Viết test (đỏ)**

```python
class WideBackend(Backend):
    NAMES = [f"col_{i}" for i in range(300)] + ["x" * 1000, "y"]
    def get_dataset_preview(self, dataset_id):
        return {"rows": 10, "records": [{n: i for n in self.NAMES} for i in range(10)]}
    def get_dataset_features(self, dataset_id, problem_type):
        return {n: n == "y" for n in self.NAMES}

def test_wide_schema_result_for_llm_is_bounded(session):
    session.api = WideBackend()
    result = session.team.get_dataset_schema(session.api, dataset_id="dataset-1")
    text = json.dumps(result, ensure_ascii=False)
    assert len(text) < 30_000 and "x" * 1000 not in text
    assert result["columns_truncated"] is True and len(result["columns"]) == tools.MAX_COLUMNS_FOR_LLM
    assert session.team.handoff.profiles["dataset-1"]["column_count"] == 302
```

`test_wide_dataset_profile_lists_every_column_name` đang có phải tiếp tục xanh.

- [ ] **Step 2–4: Đỏ, cài đặt, xanh** (cả suite agent)

- [ ] **Step 5: Commit** `fix(agent): get_dataset_schema trả bản có trần cho Data Agent (I-10)`

---

### Task B4: Lỗi `validate_config` chỉ nêu cột sai kèm gợi ý; `valid_columns` có trần (I-13)

**Files:**
- Modify: `src/backend/agent/skills/model-agent/scripts/validate_config.py:63-96`
- Modify: `src/backend/agent/tools.py:838-850`
- Test: `src/backend/agent/tests/test_agent.py`

**Interfaces:**
- Produces:
  - `validate_config._unknown_columns_message(kind: str, unknown: list[str], columns: list[str]) -> str`. Hàm này:
    - liệt kê tối đa 10 tên sai;
    - mỗi tên kèm `difflib.get_close_matches(name, columns, n=3, cutoff=0.6)`, so sánh trên chữ thường và map ngược về tên gốc;
    - kết thúc bằng câu "Xem all_column_names trong kết quả get_dataset_schema để có danh sách đầy đủ."
  - Kết quả lỗi của `submit_config` có `valid_columns` qua `_fit_names` và `valid_columns_hidden: int`.

- [ ] **Step 1: Viết test (đỏ)**

```python
validate = tools._load_skill_script("model-agent", "validate_config")

def test_unknown_feature_error_suggests_close_names_without_listing_all():
    cols = [f"col_{i}" for i in range(300)]
    msg = validate._unknown_columns_message("đặc trưng", ["col_1O"], cols)
    assert "col_10" in msg and "col_299" not in msg and len(msg) < 600

def test_unknown_column_suggestion_handles_case_and_unicode():
    msg = validate._unknown_columns_message("mục tiêu", ["doanh_thu"], ["Doanh_Thu", "Chi_phí"])
    assert "Doanh_Thu" in msg

def test_invalid_config_result_is_bounded_for_wide_dataset(session):
    session.api = WideBackend()   # từ B3
    session.team.get_dataset_schema(session.api, dataset_id="dataset-1")
    result = session.team.submit_config(session.api, dataset_id="dataset-1", target="y",
                                        list_feature=["col_1O"], metric_sort="accuracy", problem_type="classification")
    assert result["ok"] is False and len(json.dumps(result, ensure_ascii=False)) < 20_000
```

- [ ] **Step 2–4: Đỏ, cài đặt, xanh.** Thay 2 thông điệp ở `:68` và `:94` bằng `_unknown_columns_message`.

- [ ] **Step 5: Commit** `fix(agent): lỗi validate_config gợi ý cột gần đúng, không liệt kê toàn bộ cột (I-13)`

---

### Task B5: Compaction theo token, che kết quả tool cũ, phục hồi khi vượt context (I-05)

**Files:**
- Modify: `src/backend/agent/agent_openai.py:757-770` (tách `estimate_tokens`), thêm `is_context_overflow`, `ContextOverflow`
- Modify: `src/backend/agent/chat.py:72-105` (hằng, helper), `:218-250` (`compact_history`), `:382-470` (`_send`)
- Test: `src/backend/agent/tests/test_agent.py`

**Interfaces:**
- Produces:
  - `agent_openai.estimate_tokens(messages: list) -> int`: chars/3. `usage_or_estimate` dùng lại hàm này.
  - `agent_openai.is_context_overflow(error: Exception) -> bool`, đúng khi:
    - `status_code == 413`, hoặc
    - `status_code == 400` và thông điệp (lowercase) chứa một trong `"context_length_exceeded"`, `"maximum context length"`, `"context window"`, `"prompt is too long"`, `"too many tokens"`.
  - `class ContextOverflow(RuntimeError)`
  - `chat._history_token_budget() -> int`: env `AGENT_HISTORY_TOKEN_BUDGET`, mặc định `60_000`.
  - `chat._tool_digest(content: str) -> str`: JSON giữ:
    - `ok`, `status_code`, `result_truncated`;
    - `error` (≤300 ký tự);
    - mọi khoá cấp 1 có tên kết thúc bằng `_id` hoặc `_ids`, và `configs[*].config_id`;
    - thêm `"masked": true` và `"note": "Kết quả đầy đủ đã lược khỏi lịch sử; gọi lại tool nếu cần."`
  - `ChatSession.compact_history(full_turns: int | None = None, force_mask: bool = False) -> None`

- [ ] **Step 1: Viết test (đỏ)**

```python
def _turn_with_big_tool(i):
    return [
        {"role": "user", "content": f"Câu {i}"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": f"c{i}", "type": "function",
            "function": {"name": "ask_model_agent", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": f"c{i}", "content": json.dumps(
            {"ok": True, "config_id": f"cfg-{i}", "report": "x" * 20_000})},
        {"role": "assistant", "content": f"Trả lời {i}"},
    ]

def test_history_over_token_budget_masks_old_tool_results(session, monkeypatch):
    monkeypatch.setenv("AGENT_HISTORY_TOKEN_BUDGET", "3000")
    session.messages = session.messages[:1] + sum((_turn_with_big_tool(i) for i in range(3)), [])
    session.compact_history()
    tools_msgs = [m for m in session.messages if m["role"] == "tool"]
    assert tools_msgs and all(len(m["content"]) < 1000 for m in tools_msgs)
    assert json.loads(tools_msgs[-1]["content"])["config_id"] == "cfg-2"
    assert json.loads(tools_msgs[-1]["content"])["masked"] is True
    for i, m in enumerate(session.messages):
        if m["role"] == "tool":
            assert session.messages[i - 1].get("tool_calls")

@pytest.mark.parametrize("status,text,expected", [
    (400, "This model's maximum context length is 128000 tokens", True),
    (400, "Error code: context_length_exceeded", True),
    (400, "prompt is too long: 210000 tokens > 200000 maximum", True),
    (413, "Request Entity Too Large", True),
    (400, "Invalid tool schema", False),
    (500, "maximum context length", False),
])
def test_is_context_overflow_variants(status, text, expected):
    error = type("BadRequestError", (Exception,), {})(text); error.status_code = status
    assert agent_openai.is_context_overflow(error) is expected

def test_context_overflow_is_retried_after_aggressive_compaction(session):
    overflow = type("BadRequestError", (Exception,), {})("maximum context length is 128000 tokens")
    overflow.status_code = 400
    session.messages += sum((_turn_with_big_tool(i) for i in range(2)), [])
    create = Mock(side_effect=[overflow, response("ok")])
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert session.send("Tiếp") == "ok"
    assert all(len(m["content"]) < 1000 for m in session.messages if m["role"] == "tool")

def test_context_overflow_twice_raises_friendly_error(session):
    # create luôn raise overflow -> session.send raise ContextOverflow; thông điệp có "Cuộc trò chuyện mới"
    # và lịch sử không còn tin user của lượt lỗi
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

- [ ] **Step 3: Cài đặt**
  - **`compact_history`:**
    - (a) chạy logic theo lượt như cũ;
    - (b) nếu `force_mask` hoặc `estimate_tokens(self.messages) > _history_token_budget()`, thay `content` của mọi tool message bằng `_tool_digest`;
    - (c) nếu vẫn vượt, giảm `keep` từng bước xuống 1 rồi lặp lại (a).
  - **`_send`:** khi `except Exception as error` gặp `is_context_overflow(error)` và chưa thử lại lần nào:
    - `del self.messages[before:]`, rồi `self.compact_history(full_turns=1, force_mask=True)`;
    - thêm lại đúng tin user, chạy lại `run_tool_loop` đúng một lần.
  - **Lần overflow thứ hai:** rollback như nhánh lỗi chung, rồi raise `ContextOverflow("Cuộc trò chuyện đã quá dài so với giới hạn của mô hình, kể cả sau khi rút gọn. Bấm 'Cuộc trò chuyện mới' để tiếp tục.")`.
  - Nên tách phần chạy Manager thành `_run_manager(tool_schemas, dispatch, user_message) -> str` để gọi lại được mà không lặp code.

- [ ] **Step 4: Chạy lại test (xanh) và toàn bộ suite agent.** `test_old_turns_are_compacted_and_history_stays_valid` phải giữ xanh.

- [ ] **Step 5: Commit** `fix(agent): compaction theo token, che kết quả tool cũ, phục hồi khi vượt context (I-05)`

---

## Phần C: Điều khiển vòng lặp

### Task C1: Nút Dừng có hiệu lực giữa các tool và trong lúc chờ thử lại (I-08)

**Files:**
- Modify: `src/backend/agent/agent_openai.py:160-209` (`create_completion`) và `:811-931` (`run_tool_loop`)
- Modify: `src/backend/agent/chat.py:419-432`, `src/backend/agent/team.py:717-730, 776-779` (truyền `cancel_event`)
- Test: `src/backend/agent/tests/test_agent.py`

**Interfaces:**
- Produces:
  - `create_completion(llm, time_left=None, cancel_event: threading.Event | None = None, **request)`: chờ retry bằng `cancel_event.wait(delay)`. Nếu event được set thì raise `TurnCancelled("người dùng đã bấm Dừng trong lúc chờ thử lại LLM")`.
  - `run_tool_loop(..., cancel_event: threading.Event | None = None)`:
    - Trước **mỗi** tool call, nếu `cancel_event.is_set()` thì không chạy tool đó. Trả tool message `{"ok": False, "cancelled": True, "error": "Người dùng đã bấm Dừng. Tool này KHÔNG được chạy."}`.
    - Sau vòng tool, nếu có tool bị bỏ qua và `check_budget is None` thì raise `TurnCancelled`.
  - Chỗ truyền `cancel_event`:
    - `ChatSession` truyền `self.cancel_requested`.
    - `AgentTeam._run_loop` và `_ask_json` truyền `self.session.cancel_requested`, dùng `getattr` với mặc định `None`.

- [ ] **Step 1: Viết test (đỏ)**

```python
def response_calls(calls):
    """Một bước LLM gọi nhiều tool: calls = [(name, args), ...]."""
    tool_calls = [SimpleNamespace(id=f"call-{i}", function=SimpleNamespace(name=n, arguments=json.dumps(a)), model_extra={})
                  for i, (n, a) in enumerate(calls)]
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=tool_calls, model_extra={}))],
                           usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2))

def test_stop_during_step_skips_remaining_tools():
    stop = threading.Event(); ran = []
    def first(api): ran.append("t1"); stop.set(); return {"ok": True}
    def other(api): ran.append("other"); return {"ok": True}
    llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=Mock(side_effect=[response_calls([("t1", {}), ("t2", {}), ("t3", {})])]))))
    schemas = [agent_openai._tool(n, "d") for n in ("t1", "t2", "t3")]
    messages = [{"role": "user", "content": "x"}]
    with pytest.raises(agent_openai.TurnCancelled):
        agent_openai.run_tool_loop(llm, "m", messages, schemas, {"t1": first, "t2": other, "t3": other},
                                   None, agent_openai._new_usage(), cancel_event=stop)
    assert ran == ["t1"]
    answered = {m["tool_call_id"] for m in messages if m["role"] == "tool"}
    assert answered == {"call-0", "call-1", "call-2"}

def test_stop_interrupts_llm_retry_wait(monkeypatch):
    monkeypatch.setattr(agent_openai, "_retry_delay", lambda error, attempt: 30.0)
    busy = type("APIStatusError", (Exception,), {})("busy"); busy.status_code = 503
    llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=busy))))
    stop = threading.Event(); threading.Timer(0.1, stop.set).start()
    started = time.time()
    with pytest.raises(agent_openai.TurnCancelled):
        agent_openai.create_completion(llm, cancel_event=stop, model="m", messages=[])
    assert time.time() - started < 2
```

Lưu ý: `_call_tool` gọi `dispatch[name](api, **arguments)`. Kiểm lại chữ ký `_call_tool` (`agent_openai.py:687`) và chỉnh hàm giả trong test cho khớp.

- [ ] **Step 2–4: Đỏ, cài đặt, xanh** (cả suite agent)

- [ ] **Step 5: Commit** `fix(agent): nút Dừng có hiệu lực giữa các tool và khi chờ thử lại LLM (I-08)`

---

### Task C2: Ngân sách uỷ thác mỗi lượt; báo cáo dở dang khi sub-agent chạm trần (I-09, I-07)

**Files:**
- Modify: `src/backend/agent/team.py:631-634` (`begin_turn`), `:701-713` (`_run_subagent`), `:745-749` (`_run_loop`), `:804` (`ask_prompt_agent`)
- Test: `src/backend/agent/tests/test_agent.py`

**Interfaces:**
- Produces:
  - Hằng: `team.MAX_DELEGATIONS_PER_TURN = 6`, `team.MAX_SAME_DELEGATION = 2`
  - `AgentTeam._delegation_refusal(agent: str, task: str) -> dict | None`:
    - So sánh task sau khi chuẩn hoá (gộp khoảng trắng, lowercase).
    - Trả `{"ok": False, "agent", "error", "retryable": False}` khi đã đủ 6 lần trong lượt, hoặc khi 2 lần gần nhất đều là đúng `(agent, task)` này.
    - Trường hợp còn lại: ghi nhận lần uỷ thác và trả `None`.
  - `AgentTeam._partial_report(agent: str, messages: list, schemas: list) -> str | None`:
    - Gọi LLM thêm đúng 1 lần với `tool_choice="none"`.
    - Lỗi bất kỳ, kể cả `TurnBudgetExceeded`, thì trả `None`.
  - Khi chạm trần bước, `_run_loop` trả `{"ok": False, "agent", "error", "partial": bool, "report"?}`. `report` được cắt theo `REPORT_MAX_CHARS` của B1.
  - Câu lỗi:
    - Quá 6 lần: `"Đã uỷ thác {N} lần trong lượt này. Tổng hợp kết quả đã có và trả lời người dùng; đừng uỷ thác thêm."`
    - Lặp lại: `"Đã giao đúng việc này cho {title} {K} lần liên tiếp. Đổi cách làm hoặc trả lời người dùng với thông tin đang có."`
  - Prompt xin báo cáo dở dang: `"Bạn đã dùng hết số bước. KHÔNG gọi tool nữa. Viết báo cáo dở dang: đã làm được gì, các ID đã có (dataset_id, config_id, job_id, preview_id), còn thiếu gì."`

- [ ] **Step 1: Viết test (đỏ)**

```python
def test_seventh_delegation_in_a_turn_is_refused(session, monkeypatch):
    monkeypatch.setattr(session.team, "_run_loop", lambda *a, **k: {"ok": True, "agent": "data-agent", "report": "ok"})
    session.team.begin_turn()
    results = [session.team.ask_data_agent(session.api, f"việc {i}") for i in range(7)]
    assert all(r["ok"] for r in results[:6]) and results[6]["ok"] is False and "6 lần" in results[6]["error"]

def test_same_task_three_times_in_a_row_is_refused(session, monkeypatch):
    # tương tự, cùng task "Liệt kê dataset" 3 lần -> lần 3 ok False, error chứa "liên tiếp"

def test_subagent_step_cap_returns_partial_report(session):
    calls = [response(tool="list_my_datasets") for _ in range(team.SUBAGENT_MAX_STEPS)]
    create = Mock(side_effect=calls + [response("Báo cáo dở: đã đọc dataset-1, chưa chọn target")])
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    session.team.begin_turn()
    result = session.team.ask_data_agent(session.api, "Phân tích dataset-1")
    assert result["ok"] is False and result["partial"] is True and "dataset-1" in result["report"]
    assert create.call_args.kwargs["tool_choice"] == "none"
```

- [ ] **Step 2–4: Đỏ, cài đặt, xanh.** Gọi `_delegation_refusal` ở đầu `_run_subagent` (áp cho data/model/operation/sql) và ở đầu `ask_prompt_agent`. Chạy cả suite agent.

- [ ] **Step 5: Commit** `fix(agent): ngân sách uỷ thác mỗi lượt, báo cáo dở dang khi sub-agent chạm trần (I-09, I-07)`

---

## Phần D: Watcher

### Task D1: Trần pha queued; mất đăng nhập thì tạm dừng có backoff, giữ lời hứa (I-17, I-15)

**Files:**
- Modify: `src/backend/agent/watcher.py`:
  - `:30-40` (hằng)
  - `:446-480` (`_run`: thời gian chờ, lý do hết giờ)
  - `:568-580` (nhánh 401, `_note_phase`)
  - thêm `resume_paused`
- Modify: `src/backend/agent/chat.py:263-330` (`_on_job_finished`: câu báo theo `reason`)
- Modify: `src/backend/agent/server.py:263-273` (`_adopt_token`) và `/agent/token` (`:913-930`): gọi `resume_paused()` sau khi nhận token
- Test: `src/backend/agent/tests/test_agent.py`

**Interfaces:**
- Produces:
  - Hằng: `watcher.MAX_QUEUED_SECONDS = 2 * 60 * 60`, `watcher.AUTH_LOST_AFTER_SECONDS = 15 * 60`, `watcher.MAX_BACKOFF_SECONDS = 300`
  - `JobWatcher._backoff(wait: float | None, poll: float) -> float` (staticmethod): `min(MAX_BACKOFF_SECONDS, (wait or poll) * 2)`
  - Sự kiện `job_watch_timeout` có thêm `reason`, nhận một trong 3 giá trị:

    | `reason` | `error` |
    |---|---|
    | `"deadline"` | câu cũ |
    | `"queued"` | `"Job nằm trong hàng đợi quá 2 giờ mà chưa chạy (worker hoặc Kafka có thể đang hỏng). Kiểm tra lại sau hoặc huỷ và tạo lại job."` |
    | `"auth_lost"` | `"Mất phiên đăng nhập nên chưa theo dõi tiếp được. Job có thể đã xong; mở lại trang để cập nhật kết quả."` |

    Frontend đã coi `job_watch_timeout` là sự kiện kết thúc (`useAgentSession.ts:86`), nên không cần sửa frontend.
  - Với `reason == "auth_lost"`: **không** gọi `drop_promise`. Lưu kwargs của lần `watch` vào `self._paused[job_id]`, không đặt `auto_activate_skipped`.
  - `JobWatcher.resume_paused() -> list[str]`: gọi lại `watch(**kwargs)` cho từng job đang tạm dừng, trả các job_id đã theo dõi lại. Trạng thái `_auto` giữ nguyên (`"pending"`).

- [ ] **Step 1: Viết test (đỏ)**

```python
def test_job_stuck_in_queue_times_out_with_queued_reason(monkeypatch):
    from agent import watcher as w
    monkeypatch.setattr(w, "MAX_QUEUED_SECONDS", 0.05)
    monkeypatch.setattr(tools, "job_pipeline_phase", lambda api, job_id: "queued")
    events, finished = _watch_until_done(OneJobBackend({**SUCCESS_JOB, "status": 0}))
    assert events[-1]["type"] == "job_watch_timeout" and events[-1]["reason"] == "queued"

class LoggedOutBackend(Backend):
    def __init__(self): super().__init__(); self.logged_in = False
    def list_jobs(self):
        if not self.logged_in: raise ApiError(401, "token expired")
        return [SUCCESS_JOB]
    def activate_model(self, job_id, activate): return {}

def test_lost_login_pauses_watch_and_keeps_promise(monkeypatch):
    from agent import watcher as w
    from agent.watcher import JobWatcher
    monkeypatch.setattr(w, "AUTH_LOST_AFTER_SECONDS", 0.05)
    api = LoggedOutBackend(); events = []
    watcher = JobWatcher(api, lambda type, **d: events.append({"type": type, **d}), lambda s: None, poll=0.01)
    watcher.watch("job-1", max_time=60, auto_activate=True)
    watcher._threads["job-1"].join(timeout=5)
    assert events[-1]["type"] == "job_watch_timeout" and events[-1]["reason"] == "auth_lost"
    assert watcher.auto_state("job-1") == "pending"
    api.logged_in = True
    assert watcher.resume_paused() == ["job-1"]
    watcher._threads["job-1"].join(timeout=5)
    assert events[-1]["type"] == "job_done" and events[-1].get("activation", {}).get("ok")

def test_auth_backoff_doubles_and_caps():
    from agent.watcher import JobWatcher, MAX_BACKOFF_SECONDS
    assert JobWatcher._backoff(None, 20) == 40 and JobWatcher._backoff(40, 20) == 80
    assert JobWatcher._backoff(10_000, 20) == MAX_BACKOFF_SECONDS
```

`SUCCESS_JOB` cần thêm `"activate": 0` nếu bước kích hoạt đòi khoá này. Theo mẫu của `test_watcher_activates_model_when_user_asked`.

- [ ] **Step 2–4: Đỏ, cài đặt, xanh.**
  - `_note_phase`:
    - Pha `queued`: đặt `queued_since` nếu chưa có. Quá `MAX_QUEUED_SECONDS` thì `deadline = now` và `timeout_reason = "queued"`, không gia hạn nữa.
    - Pha `running`: xoá `queued_since`.
  - Lần poll thành công: xoá `auth_failing_since` và `wait`.
  - `_run`: chờ bằng `self._stopped.wait(state.get("wait") or self._poll)`.
  - Chạy cả suite agent.

- [ ] **Step 5: Commit** `fix(agent): watcher có trần pha queued, mất đăng nhập thì tạm dừng có backoff và giữ lời hứa (I-17, I-15)`

---

### Task D2: Lưu trạng thái watch, khôi phục cho chủ phiên, lifespan shutdown (I-16)

**Files:**
- Create: `src/backend/agent/watch_store.py`
- Modify: `src/backend/agent/watcher.py`: `attach_store`, `_persist`, `_forget`, `resume`. Gọi `_persist` trong `watch`, `set_auto_activate`, `drop_promise`, khi tạm dừng (D1). Gọi `_forget` khi `_run` kết thúc bằng một kết quả cuối (không phải tạm dừng hay `stop()`).
- Modify: `src/backend/agent/server.py`: `_WATCH_STORE`, `_resume_orphaned_watches`, gọi trong cả hai nhánh của `_get_session` (`:379-409`), FastAPI `lifespan`
- Modify: `docker-compose.yaml` (service agent: `AGENT_STATE_DIR=/app/state`, named volume `agent_state:/app/state`), `src/backend/agent/Dockerfile` (`RUN mkdir -p /app/state && chown agent /app/state`, đặt trước `USER agent`)
- Test: `src/backend/agent/tests/test_agent.py`

**Interfaces:**
- Consumes: `JobWatcher.resume_paused`, `self._paused` (D1).
- Produces:
  - `class WatchStore(path: str | os.PathLike)`. Dùng sqlite3 với `check_same_thread=False` cộng `threading.Lock`. Bảng:
    ```sql
    watches(owner TEXT, job_id TEXT, session_id TEXT, record TEXT, updated_at REAL,
            PRIMARY KEY(owner, job_id))
    ```
    Phương thức:
    - `save(owner: str, job_id: str, session_id: str, record: dict) -> None`
    - `remove(owner: str, job_id: str) -> None`
    - `for_owner(owner: str) -> list[dict]`: mỗi phần tử là `{"job_id", "session_id", **record}`
    - `purge(older_than_seconds: float = 7 * 24 * 3600) -> int`
  - `watch_store.default_store() -> WatchStore | None`:
    - Đọc env `AGENT_STATE_DIR`. Không đặt thì trả `None` (tắt lưu trữ; CLI và test giữ nguyên hành vi).
    - Có đặt thì mở `<dir>/watches.sqlite3` rồi `purge()`.
  - Schema `record`: `{"max_time", "requirements", "dataset_id", "problem_type", "auto_state", "added_constraints", "paused": bool}`
  - Phương thức mới của `JobWatcher`:
    - `attach_store(store: WatchStore, owner: str, session_id: str) -> None`
    - `resume(records: list[dict]) -> list[str]`: khôi phục `_auto`, `_promise_requirements`, `_added_constraints` từ record, rồi gọi `watch(...)`, đổi `session_id` của record sang phiên hiện tại.
  - Trong `server.py`:
    - `_resume_orphaned_watches(session_id: str, session: ChatSession, owner: str) -> list[str]`: chỉ nhận record có `session_id == session_id` hoặc `session_id not in _sessions`.
    - `lifespan`, chạy khi shutdown: với mọi entry gọi `request_cancel()` và `watcher.stop()`; sau đó `_TURN_POOL.shutdown(wait=False, cancel_futures=True)`, `_UPLOAD_POOL.shutdown(wait=False, cancel_futures=True)`.

- [ ] **Step 1: Viết test (đỏ)**

```python
def test_watch_store_roundtrip_and_owner_isolation(tmp_path):
    from agent.watch_store import WatchStore
    store = WatchStore(tmp_path / "w.sqlite3")
    store.save("u1", "job-1", "s1", {"auto_state": "pending"})
    store.save("u2", "job-2", "s2", {"auto_state": "off"})
    assert [r["job_id"] for r in store.for_owner("u1")] == ["job-1"]
    store.remove("u1", "job-1"); assert store.for_owner("u1") == []

def test_store_purges_records_older_than_ttl(tmp_path, monkeypatch):
    # save, rồi monkeypatch time.time trả +8 ngày -> purge() == 1 và for_owner rỗng

def test_finished_watch_is_forgotten(tmp_path):
    # JobWatcher với OneJobBackend(SUCCESS_JOB), attach_store(store, "user-1", "s1"), watch, join
    # -> store.for_owner("user-1") == []

def test_stopped_watch_is_kept_and_resumed_by_a_new_watcher(tmp_path):
    # backend RUNNING: watch(auto_activate=True), watcher.stop(), join -> record auto_state "pending"
    # JobWatcher mới trên backend SUCCESS: attach_store(..., "s2"); resume(store.for_owner("user-1"))
    # -> join; sự kiện cuối là job_done có activation ok; store rỗng

def test_new_session_resumes_orphaned_watches_only(tmp_path, monkeypatch):
    store = WatchStore(tmp_path / "w.sqlite3"); monkeypatch.setattr(server, "_WATCH_STORE", store)
    store.save("user-1", "job-a", "dead-session", {"auto_state": "off"})
    store.save("user-1", "job-b", "live", {"auto_state": "off"})
    monkeypatch.setitem(server._sessions, "live", Mock(owner="user-1"))
    watched = []
    monkeypatch.setattr("agent.watcher.JobWatcher.watch", lambda self, job_id, **kw: watched.append(job_id) or True)
    server._get_session(None, "tok", "user-1")
    assert watched == ["job-a"]
```

- [ ] **Step 2–4: Đỏ, cài đặt, xanh.** Chạy cả suite agent, rồi `docker compose config` để chắc file compose vẫn hợp lệ.

- [ ] **Step 5: Commit** `feat(agent): lưu trạng thái watch vào SQLite, khôi phục cho chủ phiên, lifespan shutdown (I-16)`

---

## Phần E: Server agent

### Task E1: Cache xác thực kiểu TTL-LRU, loại token không có dạng JWT, pool riêng (I-19)

**Files:**
- Modify: `src/backend/agent/server.py:278-346`
- Test: `src/backend/agent/tests/test_agent.py`

**Interfaces:**
- Produces:
  - `server._looks_like_jwt(token: str) -> bool`: khớp regex `^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$`.
  - `server._OwnerCache(maxsize: int = 1000)`, dùng OrderedDict:
    - `get(token: str, now: float) -> str | None`: trả `None` khi chưa có hoặc đã hết hạn; `""` nghĩa là token đã bị backend từ chối.
    - `put(token: str, owner: str, expires: float) -> None`: chèn và bỏ mục ít dùng nhất khi đầy.
  - `server._AUTH_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-auth")`. `_resolve_owner` dùng `loop.run_in_executor(_AUTH_POOL, _owner_of, token)`.
  - `_owner_of` trả `None` ngay, không gọi `/me`, khi `not _looks_like_jwt(token)`. Kiểm ở đây chứ không ở `_resolve_owner`, để các test đang monkeypatch `_owner_of` không bị ảnh hưởng.
  - Rate-limit theo IP để ngoài phạm vi (ghi trong PR). Kiểm dạng JWT cộng pool riêng đã chặn được kịch bản flood.

- [ ] **Step 1: Viết test (đỏ)**

```python
def test_non_jwt_token_is_rejected_without_backend_call(monkeypatch):
    get_me = Mock()
    monkeypatch.setattr(HAutoMLClient, "get_me", get_me)
    assert server._owner_of("garbage-token") is None and not get_me.called

def test_owner_cache_evicts_least_recently_used_not_everything():
    cache = server._OwnerCache(maxsize=3)
    for key in "abc": cache.put(key, key.upper(), expires=10**10)
    cache.get("a", now=0); cache.put("d", "D", expires=10**10)
    assert cache.get("a", now=0) == "A" and cache.get("b", now=0) is None and cache.get("d", now=0) == "D"
```

Các test đang gọi `_owner_of` với token như `"test-token"` phải đổi sang token có dạng JWT, ví dụ `"a.b.c"`. Tìm chúng bằng `grep -n "_owner_of\|access_token" agent/tests/test_agent.py`.

- [ ] **Step 2–4: Đỏ, cài đặt, xanh** (cả suite agent)

- [ ] **Step 5: Commit** `fix(agent): cache xác thực TTL-LRU, loại token không có dạng JWT, pool xác thực riêng (I-19)`

---

### Task E2: Upload xác thực bằng header trước khi đọc body, có hạn đọc body (I-18)

**Files:**
- Modify: `src/backend/agent/server.py:466-474` (CORS `allow_headers` thêm `"Authorization"`), `:785-860` (`upload`, `_read_and_store_upload`, `_store_upload`)
- Modify: `src/frontend/apps/web/src/features/agent/lib/agentApi.ts:59-80`, `src/frontend/apps/web/src/features/agent/hooks/useAgentSession.ts:779-790`
- Test: `src/backend/agent/tests/test_agent.py`

**Interfaces:**
- Consumes: `_resolve_owner` (E1).
- Produces:
  - `server._bearer_token(request: Request) -> str | None`
  - `server.UPLOAD_READ_SECONDS = 120`
  - `_store_upload(form, owner: str, access_token: str) -> dict`: không đọc `access_token` từ form nữa.
  - Frontend:
    - `uploadWithProgress(form: FormData, accessToken: string, onProgress: (percent: number) => void)` đặt header `Authorization: Bearer <token>`.
    - `useAgentSession` thôi `form.append("access_token", ...)`.
  - Thứ tự trong `upload()`:
    1. Kiểm Content-Length.
    2. `owner = await _resolve_owner(_bearer_token(request))`.
    3. Kiểm semaphore.
    4. `await asyncio.wait_for(request.form(...), UPLOAD_READ_SECONDS)`. Hết giờ thì `HTTPException(408, "Tải tệp quá chậm, thử lại.")`.

- [ ] **Step 1: Viết test (đỏ)**

```python
def test_upload_without_bearer_is_rejected_before_body_is_read(monkeypatch):
    read = Mock()
    monkeypatch.setattr(server, "_read_and_store_upload", read)
    result = request("POST", "/agent/upload", files={"file": ("a.csv", b"x,y\n1,2\n")})
    assert result.status_code == 401 and not read.called

def test_upload_body_read_has_deadline(monkeypatch):
    monkeypatch.setattr(server, "UPLOAD_READ_SECONDS", 0.05)
    monkeypatch.setattr(server, "_owner_of", lambda token: "user-1")
    async def slow_form(self, **kw): await asyncio.sleep(1)
    monkeypatch.setattr("starlette.requests.Request.form", slow_form)
    result = request("POST", "/agent/upload", headers={"Authorization": "Bearer a.b.c"},
                     files={"file": ("a.csv", b"x,y\n1,2\n")})
    assert result.status_code == 408
```

Cập nhật `test_too_many_concurrent_uploads_are_refused` (`:2794`): gửi kèm header Bearer và monkeypatch `_owner_of`. Các test upload khác đang gửi token trong form cũng đổi sang header.

- [ ] **Step 2–4: Đỏ, cài đặt, xanh.** Sau đó chạy test frontend: `cd src/frontend && npm run test:agent`. Kiểm kiểu bằng `npx tsc --noEmit -p apps/web` nếu dự án có cấu hình sẵn. Không có thì ghi rõ đã bỏ qua bước này.

- [ ] **Step 5: Commit** `fix(agent): upload xác thực bằng header trước khi đọc body, có hạn đọc (I-18)`

---

## Kết thúc

- [ ] Chạy toàn bộ suite backend, suite agent và `npm run test:agent`. Ghi số liệu so với baseline của Task 0.
- [ ] Cập nhật `docs/agent-review.md`: thêm cột hoặc dòng "Trạng thái" ghi task đã sửa từng mục C/I, kèm commit SHA.
- [ ] Mở PR theo từng phần (A, B+C, D, E) hoặc một PR duy nhất, tuỳ người duyệt chọn. Mô tả PR liệt kê các TODO ngoài phạm vi:
  - huỷ tác vụ từ xa trên PyMapReduce;
  - rate-limit theo IP;
  - tự kích hoạt nền bằng credential dịch vụ.
