# Mở rộng benchmark: 6 dataset mới và nhóm ca G — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm 6 dataset (adult, madelon, student, digits, gaming, wilt) và 12 ca nhóm G vào benchmark, không đổi dữ liệu đã khoá của các dataset cũ.

**Architecture:** Dataset mới đi một đường riêng giống nhóm T: `prepare_extra.py` → `datasets/extra/` + `manifest_extra.json` → `protocol.check_extra_data`. Bộ chấm (`scoring.py`) và bộ phân tích (`analyze.py`) được mở rộng để đọc cột chữ / nhãn chữ và có các kiểm tự động mới cho ca G. Ca nằm trong `cases.json`, dataset nối vào `setup_account.py`, config, baseline và báo cáo.

**Tech Stack:** Python 3.12 (venv `src/backend/.venv`), pandas, scikit-learn (đã có trong venv), pytest.

**Spec:** `docs/superpowers/specs/2026-11-27-benchmark-new-datasets-design.md`

## Global Constraints

- Làm trên nhánh `feat/benchmark_agent`; chỉ sửa `benchmark/`, `benchmark_artifacts/` (không trong git), `docs/`. Không sửa `src/backend/agent/` hay `src/backend/src/`.
- **Không commit** (người dùng tự commit). Bước "Commit" trong mỗi task được thay bằng "để nguyên thay đổi, chạy test".
- Không đổi `benchmark_artifacts/datasets/manifest.json`, `datasets/timeseries/`, hay split cũ.
- Split: `feature-group-v1`, seed 42, test ≈ 20%, phân tầng xấp xỉ theo nhãn, 0 nhóm feature giao nhau, đủ mọi lớp ở train và test.
- Giữ nguyên giá trị gốc (kể cả `?` của adult, 14 dòng trùng của wilt); tên cột giữ nguyên.
- Ngưỡng: `floor((cv_rf_score - 0.05) / 0.05) * 0.05`, CV 5-fold `StratifiedKFold(shuffle=True, random_state=42)`, `RandomForestClassifier(random_state=42)` mặc định, cột chữ one-hot (`handle_unknown="ignore"`), chỉ trên phần train. G03 = 0.99; G07 = 0.90.
- Phiên bản ca: `cases.json` `"version"` → `"hautoml-bench-v6"`.
- Lệnh test: `src/backend/.venv/bin/python -m pytest benchmark/test_bench.py benchmark/test_v5.py benchmark/test_extra.py -q -p no:cacheprovider` (từ thư mục gốc repo).

## Review Focus

- Nhãn chữ có khoảng trắng / dấu chấm (adult `income` trong bản gốc có thể là `>50K.` ở phần test UCI): bộ chấm so nhãn theo chuỗi đã `strip()`, không ép float → test trong Task 3.
- Cột chữ bị pandas đọc thành số khi toàn chữ số (`GradeClass` là `4.0`): split giữ nguyên chuỗi gốc khi ghi file (đọc bằng `dtype=str`) → test trong Task 1.
- Dataset rất rộng (Madelon 500 cột) làm câu lệnh và `predict_rows` quá dài: `predict_rows` chỉ 3 dòng, câu lệnh G04 nói "toàn bộ 500 cột còn lại", không liệt kê → kiểm trong Task 6.
- `check_extra_data` chạy khi preflight trên máy chưa có dữ liệu mới: báo lỗi rõ cách tạo (`bench.py prepare-extra` hoặc rsync), không traceback → test trong Task 2.
- Ca G chạy ở biến thể ablation thiếu Prompt Agent (không có R): kiểm `requirement_constraints` của G07 trả `None` (chưa đo) thay vì FAIL giả → test trong Task 4.

---

### Task 1: Chuẩn bị dữ liệu mới (`prepare_extra.py`)

**Files:**
- Create: `benchmark/prepare_extra.py`
- Modify: `benchmark/bench.py` (thêm lệnh `prepare-extra`, cạnh `prepare-ts`)
- Test: `benchmark/test_extra.py`

**Interfaces:**
- Produces: `EXTRA_DIR = ARTIFACTS / "datasets" / "extra"`, `MANIFEST = EXTRA_DIR / "manifest_extra.json"`, `SPLIT_VERSION = "feature-group-v1"`, `SPECS: dict[str, dict]` (khoá → `{"raw": tên file gốc, "target": str, "problem_type": "classification"}`), `split_frame(df: pd.DataFrame, target: str, seed: int = 42, test_ratio: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]`, `cv_threshold(train: pd.DataFrame, target: str, metric: str) -> float`, `main() -> dict` (ghi file + manifest, trả manifest).
- Manifest: `{"split_version", "seed", "datasets": {khoá: {"raw_file", "raw_sha256", "target", "problem_type", "features": [...], "n_train", "n_test", "classes": [...], "train_test_feature_overlap": 0, "n_duplicate_feature_rows", "n_conflicting_target_groups"}}, "sha256": {"<khoá>_train.csv": ..., "<khoá>_test.csv": ...}, "thresholds": {"adult_f1_macro": float, "wilt_f1_macro": float}}`.

- [ ] **Step 1: Write failing tests** in `benchmark/test_extra.py`:
  - `test_split_has_no_feature_overlap_and_all_classes`: DataFrame tổng hợp 200 dòng, 3 lớp, có dòng trùng feature → `split_frame` trả train/test không giao tập tuple feature, mỗi lớp có ở cả hai, `len(test)/200` trong `[0.1, 0.3]`.
  - `test_split_is_deterministic`: gọi hai lần → hai DataFrame bằng nhau.
  - `test_values_kept_as_strings`: cột `"4.0"`, `"?"` đọc bằng `dtype=str` vẫn là `"4.0"`, `"?"` sau split.
  - `test_cv_threshold_rounds_down_to_005`: monkeypatch điểm CV = 0.8734 → 0.80; 0.85 → 0.80.
- [ ] **Step 2: Run** `... -m pytest benchmark/test_extra.py -q` → FAIL (module chưa có).
- [ ] **Step 3: Implement** `prepare_extra.py`: đọc file gốc bằng `pd.read_csv(path, dtype=str, keep_default_na=False)`; `SPECS` = adult/`income`, madelon/`decision`, student/`GradeClass`, digits/`target`, gaming/`EngagementLevel`, wilt/`class` (file `"Student_performance_data _.csv"` có dấu cách); `split_frame` gom nhóm theo tuple toàn bộ feature, phân tầng theo nhãn đa số của nhóm, xáo nhóm bằng `random.Random(seed)`, lấy nhóm vào test tới khi mỗi lớp đạt ≈ 20%; ghi `<khoá>_train.csv` / `<khoá>_test.csv` giữ thứ tự cột gốc (feature theo thứ tự gốc, target cuối); `cv_threshold` theo Global Constraints (đổi cột số sang float trong pipeline, cột chữ one-hot); `main()` không ghi đè manifest đã có nếu hash file gốc khớp (in "đã có"), từ chối nếu khác.
- [ ] **Step 4: Run** test → PASS; rồi chạy thật `... benchmark/bench.py prepare-extra`, kiểm `manifest_extra.json` có 6 dataset, 12 file, 2 ngưỡng; in bảng số dòng train/test.
- [ ] **Step 5:** để nguyên, không commit.

### Task 2: Kiểm dữ liệu mới trong preflight

**Files:**
- Modify: `benchmark/protocol.py` (thêm `EXTRA_DATASETS`, `check_extra_data`, gọi trong `preflight`)
- Test: `benchmark/test_extra.py`

**Interfaces:**
- Consumes: `prepare_extra.MANIFEST`, `EXTRA_DIR`, `SPECS`.
- Produces: `EXTRA_DATASETS = ("adult", "madelon", "student", "digits", "gaming", "wilt")`, `check_extra_data(cfg: dict | None = None) -> None` (raise `ValueError` với thông điệp tiếng Việt).

- [ ] **Step 1: Failing tests:** `test_check_extra_data_missing_manifest_message` (không có manifest → `ValueError` chứa "bench.py prepare-extra"); `test_check_extra_data_detects_hash_change` (sửa 1 byte file train tạm → `ValueError` "Hash không khớp"); `test_check_extra_data_test_set_path` (cfg `test_sets.adult` trỏ sai → `ValueError`). Dùng thư mục tạm + monkeypatch `EXTRA_DIR`/`MANIFEST`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** theo mẫu `check_ts_data`: hash từng file, header = `features + [target]`, số dòng = `n_train`/`n_test`, `cfg["test_sets"][khoá]` trỏ đúng file; **không** ép float. Gọi trong `preflight` cạnh `check_data`, `check_ts_data`.
- [ ] **Step 4: Run** test + `bench.py preflight` (offline) → "Preflight đạt" khi dữ liệu và config đủ (sau Task 5).
- [ ] **Step 5:** không commit.

### Task 3: Bộ chấm đọc cột chữ và nhãn chữ

**Files:**
- Modify: `benchmark/scoring.py:34-47` (`_read_test`), `benchmark/metrics.py` (`compute` cho classification nhận nhãn chuỗi)
- Test: `benchmark/test_extra.py`

**Interfaces:**
- Produces: `_read_test(path, target, time_column=None, column_case=None, problem_type="regression") -> tuple[list[dict], list]`: feature giữ chuỗi nếu không ép được float; với `problem_type == "classification"` nhãn là `str(value).strip()`, ngược lại `float`. `score_run` truyền `problem_type=task["problem_type"]`.

- [ ] **Step 1: Failing tests:** `test_read_test_keeps_text_features` (`workclass="Private"` giữ chuỗi, `age="39"` thành 39.0); `test_read_test_string_labels_for_classification` (nhãn `"<=50K"`, `" >50K "` → `"<=50K"`, `">50K"`); `test_read_test_numeric_labels_unchanged_for_regression`; `test_metrics_classification_with_string_labels` (`compute("classification", ["a","b"], ["a","a"])["accuracy"] == 0.5`); `test_prediction_labels_compared_as_strings` (dự đoán `4.0` so với nhãn `"4.0"` khớp: chuẩn hoá cả hai về chuỗi số chuẩn khi đều là số).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**; các test cũ của `test_bench.py`/`test_v5.py` phải vẫn qua (dataset cũ toàn số, kết quả không đổi).
- [ ] **Step 4: Run** cả bộ test → PASS.
- [ ] **Step 5:** không commit.

### Task 4: Kiểm tự động mới cho ca G (`analyze.py`)

**Files:**
- Modify: `benchmark/analyze.py` (quanh dòng 444–512: kiểm config, kiểm endpoint luồng train)
- Test: `benchmark/test_extra.py`

**Interfaces (khoá mới trong `cases.json`):**
- `case["features_free"]: true` → `_job_matches_task` / `valid_config_matches_task` bỏ qua `list_feature`.
- `expect["features_exclude"]: list[str]` → check `features_exclude`: mọi config chạy được (và job, nếu có) không chứa các cột này.
- `expect["endpoint"]: "inactive"` (G03) → thay check `activated_and_predicted` bằng `stays_inactive` = job thành công, snapshot `activate == 0`, không có `predict` thành công cho job đó; `workflow_pass` dùng check này.
- `expect["auto_activated"]: true` (G02) → check `auto_activated` = snapshot `activate == 1` và trong `run["consent"]` không có thẻ `kind == "activate"` cho job đó.
- `expect["requirement_constraints"]: [{"metric","op","value"}]` (G07) → check so với `run["handoff"]["requirements"]` (ràng buộc đã chuẩn hoá); `None` (chưa đo) nếu không có `requirements` (biến thể không có Prompt Agent).

- [ ] **Step 1: Failing tests** dựng `run.json`/trace tối thiểu như các test trong `test_v5.py` (dùng lại helper ở đó): một test cho mỗi khoá mới, gồm ca đạt và ca trượt; `test_requirement_constraints_unmeasured_without_requirements` (Review Focus).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** các check trên; ca cũ không có khoá mới → hành vi y như cũ.
- [ ] **Step 4: Run** cả bộ test → PASS.
- [ ] **Step 5:** không commit.

### Task 5: Upload dataset mới và cấu hình

**Files:**
- Modify: `benchmark/setup_account.py` (`DATASET_FILES` + kiểm số dòng/cột theo `manifest_extra`), `benchmark/config.example.json`, `benchmark_artifacts/bench_config.json` (placeholder rỗng, `test_sets`, `predict_rows`)
- Test: `benchmark/test_extra.py`

**Interfaces:**
- Produces: placeholder `ADULT_ID`, `MADELON_ID`, `STUDENT_ID`, `DIGITS_ID`, `GAMING_ID`, `WILT_ID`; `DATASET_FILES[...] = ("datasets/extra/<khoá>_train.csv", "<khoá>_train")`; `test_sets.<khoá> = "benchmark_artifacts/datasets/extra/<khoá>_test.csv"`; `predict_rows.<khoá>` = 3 dòng đầu file test, bỏ target, giá trị giữ kiểu như đọc bằng `_read_test` (số thành số, chữ giữ chữ).
- Thêm hàm `prepare_extra.predict_rows(key: str, n: int = 3) -> list[dict]` để sinh `predict_rows` (không chép tay).

- [ ] **Step 1: Failing tests:** `test_setup_account_lists_extra_datasets` (6 khoá mới trong `DATASET_FILES`, đường dẫn tồn tại sau prepare); `test_predict_rows_have_no_target_and_three_rows`; `test_config_example_has_extra_test_sets`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**; cập nhật `bench_config.json` cục bộ bằng script nhỏ (giữ ID cũ; placeholder mới để `null` tới khi `setup-account` điền).
- [ ] **Step 4: Run** test; chạy `setup-account` thật trên máy công ty chỉ khi người dùng đồng ý (tạo dataset mới trên tài khoản benchmark).
- [ ] **Step 5:** không commit.

### Task 6: 12 ca nhóm G và ablation

**Files:**
- Modify: `benchmark/cases.json` (thêm G01–G12, `"version": "hautoml-bench-v6"`), `benchmark/config.example.json` + `bench_config.json` (`ablation.cases` += G03, G05, G06, G07, G08, G10)
- Modify: `benchmark/report.py` / `report_sections.py` (tên nhóm "G - Dataset mở rộng" trong bảng theo nhóm)
- Modify: `benchmark.md` (mục ca nhóm G, số lượt mới)
- Test: `benchmark/test_extra.py`

**Interfaces:** đúng bảng ca trong spec (câu lệnh tiếng Việt, `task`, `constraints`, `expect` với các khoá của Task 4). Ngưỡng G02/G09 lấy từ `manifest_extra.json` `thresholds` (ghi số cụ thể vào `cases.json`, 2 chữ số thập phân). `task.features` của G01 = mọi cột trừ `income`; G04 = 500 cột `V1..V500`; G05/G08 `features_free: true` + `features_exclude` (`["StudentID", "GPA"]`* cho G05 — xem chấm tay; `["PlayerID"]` cho G08); G12 = mọi cột trừ `GradeClass`.
  *G05: `features_exclude: ["StudentID"]` (tự động); GPA kiểm bằng `manual` (loại GPA **hoặc** cảnh báo rõ rò rỉ).

- [ ] **Step 1: Failing tests:** `test_group_g_cases_valid` (12 ca, id G01–G12, mỗi ca qua validator ca hiện có trong `protocol`/`test_bench`); `test_group_g_thresholds_match_manifest`; `test_ablation_includes_targeted_g_cases`; `test_plan_counts` (`protocol.plan` cho config mặc định ra 295 lượt full và 285 lượt ablation).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**; viết câu lệnh theo đúng văn phong ca cũ (xem C05, B05, F01).
- [ ] **Step 4: Run** cả bộ test → PASS; `bench.py preflight` (offline) → đạt.
- [ ] **Step 5:** không commit.

### Task 7: Baseline cho dataset mới

**Files:**
- Modify: `benchmark/baselines.py` (`TABULAR` += 6 khoá, đọc từ `datasets/extra`, cột chữ one-hot trong pipeline baseline), `benchmark/engine_baseline.py` (config đúng của G01, G04, G07, G08, G09 và student với feature bỏ `StudentID`, `GPA`)
- Test: `benchmark/test_extra.py`

- [ ] **Step 1: Failing tests:** `test_baselines_load_extra_dataset` (đọc `wilt` train/test, nhãn chữ, problem_type classification); `test_baseline_pipeline_handles_text_columns` (fit `random_forest` trên 50 dòng adult tổng hợp không lỗi).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** test → PASS; `bench.py baselines --mode smoke --datasets wilt --id extra-smoke` chạy được (không bắt buộc Docker nếu dùng `--no-docker`).
- [ ] **Step 5:** không commit.

### Task 8: Pilot soát lỗi kỹ thuật các ca G (sau khi engine chạy lại được)

- [ ] **Step 1:** Người dùng khởi động lại `hautoml_consumer`/`hautoml_service` (engine trên máy công ty đang treo).
- [ ] **Step 2:** `setup-account` cho 6 dataset mới (Task 5 Step 4), `preflight --online --cases G01,...,G12`.
- [ ] **Step 3:** `lock --phase pilot --experiment hautoml-v6-pilot-g`, `run --phase pilot --cases G01..G12`, `report`.
- [ ] **Step 4:** Chỉ sửa **lỗi kỹ thuật của ca** (câu lệnh mơ hồ, bộ chấm chấm sai, fixture hỏng); không bỏ/đổi ca theo việc bản full thắng hay thua. Ghi lại mọi sửa đổi trong spec.
