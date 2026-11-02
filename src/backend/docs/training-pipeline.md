# JSON pipeline huấn luyện (kèm trials)

Mỗi job huấn luyện lưu một JSON `pipeline` trong `tbl_Job`, mô tả trạng thái từng bước và, với mỗi mô hình,
**mọi bộ tham số đã đánh giá** (`trials`) cùng điểm cross-validation của từng bộ.
JSON được cập nhật trong lúc job chạy, nên frontend có thể gọi lại API để hiển thị tiến độ.

Code: [`src/modules/trainings/pipeline.py`](../src/modules/trainings/pipeline.py) (`PipelineTracker`, `build_trials`),
được gọi từ `TrainingService.process_training_job()` và `train_single_model_task()`.

## API

```
GET /api/v1/inference/jobs/{job_id}/pipeline
Authorization: Bearer <token>
```

| HTTP | Khi nào |
| --- | --- |
| `200` | `data` là JSON pipeline của job, ở mọi trạng thái |
| `403` | Job không thuộc người dùng (trừ admin) |
| `404` | Không có job |

Job không lưu sẵn pipeline vẫn trả `200`, JSON được dựng từ thông tin của job (`pipeline_from_job()`):

- Job đang chờ worker nhận: `status` gốc là `queued`, mọi node `queued`.
- Job huấn luyện trước khi có tính năng này (`source: "legacy"`): mỗi mô hình chỉ có **một** trial là bộ tham số tốt nhất,
  node không có thời gian, `select_best.output.score_source` là `null`. Job lỗi/hủy có mọi node `skipped`, lý do ở `error` gốc.

Frontend gọi lại API này cho tới khi `status` ở cấp gốc là `succeeded`, `failed` hoặc `cancelled`.
`GET /api/v1/inference/jobs` không trả `pipeline` để danh sách job vẫn nhẹ.

## Cấu trúc

Cấp gốc gồm thông tin job và 7 node; key của node là định danh để nối đồ thị qua `depends_on`.

```text
read_dataset → split_holdout_data → preprocessing → model_selection → train → select_best → save_result
```

| Key gốc | Ý nghĩa |
| --- | --- |
| `job_id` | ID job |
| `version` | Phiên bản cấu trúc JSON, hiện là `"2.0.0"` |
| `mode` | `"automl"` |
| `source` | `"tracked"`: ghi trong lúc huấn luyện, đủ trials; `"legacy"`: dựng lại từ kết quả cũ |
| `status` | Trạng thái cả job |
| `error` | `null`, hoặc `{"message": ...}` khi job lỗi/bị hủy |
| `updated_at` | Lần cập nhật gần nhất, ISO 8601 UTC |

Mọi node có cùng các key: `name`, `kind`, `depends_on`, `status`, `started_at`, `finished_at`, `error`, `params`, `output`.
`error` là `null` hoặc `{"message": "..."}`.

`status` (job, node, mô hình): `queued`, `running`, `succeeded`, `failed`, `skipped`, `cancelled`.
Khi job lỗi hoặc bị hủy, `error` gốc và node đang chạy nhận `failed`/`cancelled` kèm `error`, các node chưa chạy thành `skipped`.

### Biến riêng của từng node

| Node | `params` | `output` |
| --- | --- | --- |
| `read_dataset` | `id_data`, `format` | `data_url` (`bucket/object` trong MinIO), `n_rows`, `n_columns` |
| `split_holdout_data` | `method`, `test_size` (chỉ khi có holdout) | `train_rows`, `holdout_rows` |
| `preprocessing` | `target`, `list_feature` | `dropped_rows`, `n_features` (sau biến đổi), `column_types` (`numeric`, `categorical`, `text`), `class_distribution` |
| `model_selection` | `problem_type`, `search_algorithm`, `metric_sort`, `timeout`, `model_names`, `metrics`, `cv` | `{}` |
| `train` | `{}` | `models` |
| `select_best` | `{}` | `best_model`, `score_source` |
| `save_result` | `bucket_name` | `object_name` |

- `split_holdout_data` là `skipped` khi chiến lược CV không tách holdout (≤ 10.000 dòng); khi đó `holdout_rows` là `0`.
- `class_distribution`: số dòng của từng nhãn (dạng chuỗi) với classification, `null` với bài toán khác.
- `model_selection.params.metrics` là `{metric: "minimize" | "maximize"}`; `cv` gồm `name`, `n_splits`, `n_repeats`, `description`.

### Khác biệt theo loại bài toán

Cấu trúc JSON giống nhau cho mọi loại bài toán; chỉ khác mô hình, metric và chiến lược CV (`model_selection.params.cv.name`):

| | Regression | Classification |
| --- | --- | --- |
| Mô hình (`assets/*.yml`) | 8 | 6: DecisionTree, RandomForest, KNeighbors, SVC, LogisticRegression, GaussianNB |
| Metric | `r2` (maximize), `mse`, `mae`, `mape` (minimize) | `accuracy`, `balanced_accuracy`, `precision/recall/f1` `_macro` và `_weighted`; đều maximize |
| ≤ 500 dòng | `ContinuousRepeatedStratifiedKFold` | `RepeatedStratifiedKFold` |
| ≤ 10.000 dòng | `ContinuousStratifiedKFold` | `StratifiedKFold` |
| > 10.000 dòng | holdout 80/20 + `ContinuousStratifiedKFold` | holdout 80/20 (stratify) + `StratifiedKFold` |

Với classification, `cv.n_splits` = min(5, số dòng của lớp ít nhất), tối thiểu 2 (`determine_classification_cv_tier()`).

### `train.output.models.<model_name>`

| Key | Ý nghĩa |
| --- | --- |
| `status` | Trạng thái mô hình; `failed` khi task lỗi hoặc quá `timeout` |
| `error` | `{"message": ...}` khi `failed` |
| `best_trial` | Vị trí (từ `0`) của bộ tham số tốt nhất trong `trials` |
| `trials` | Mọi bộ tham số đã đánh giá; `null` khi chưa có kết quả |
| `holdout_scores` | Điểm của mô hình tốt nhất trên tập holdout; `null` khi không có holdout |

Mỗi phần tử của `trials`:

| Key | Ý nghĩa |
| --- | --- |
| `params` | Bộ tham số (đã bỏ tiền tố `model__` của pipeline time series) |
| `status` | `succeeded`, hoặc `pruned` khi bị dừng sớm giữa các fold (median pruning) |
| `scores` | Điểm CV trung bình theo từng metric trong `model_selection.params.metrics` |

Quy ước điểm:

- Metric "càng nhỏ càng tốt" (`mse`, `mae`, `mape`, `rmse`) ghi giá trị dương, dù scorer của sklearn trả số âm.
- `mape` là tỉ lệ (`0.05` = 5%), không nhân 100.
- `null`: trial bị `pruned`, metric không tính được, hoặc giá trị NaN/vô cực.
- Mỗi bộ tham số xuất hiện một lần, theo thứ tự đánh giá lần đầu (genetic algorithm có thể đánh giá lại cùng một bộ).
  Thứ tự không phải thứ hạng; vị trí trong mảng là định danh của nhánh.

### Đọc kết quả

| Cần hiển thị | Đọc từ |
| --- | --- |
| Tham số và điểm CV tốt nhất của một mô hình | `models.<m>.trials[best_trial]` |
| Mô hình được chọn | `select_best.output.best_model` |
| Điểm dùng để chọn mô hình | `holdout_scores` nếu `score_source` là `"holdout"`, ngược lại `trials[best_trial].scores` |
| Tiến độ huấn luyện | `status` của từng node; kết quả các mô hình được ghi cùng lúc khi bước `train` kết thúc |

`orther_model_scores`, `best_model`, `best_params`, `best_score` của job vẫn được ghi như trước để không ảnh hưởng frontend hiện tại.

## Ví dụ

Phản hồi API đầy đủ cho mọi trường hợp (regression, classification, đang chờ, đang chạy, lỗi, job cũ, 401/403/404):
[training-pipeline-examples.md](training-pipeline-examples.md).

Job regression thật trên Glass (214 dòng, target `RI`, `grid_search`, `metric_sort: "r2"`), rút gọn:

```json
{
  "job_id": "6adc7487b78fd5cd1dc9853a",
  "version": "2.0.0",
  "mode": "automl",
  "source": "tracked",
  "status": "succeeded",
  "error": null,
  "updated_at": "2026-10-24T09:04:18Z",
  "split_holdout_data": {
    "name": "Split holdout data", "kind": "data_splitting", "depends_on": ["read_dataset"],
    "status": "skipped", "started_at": "2026-10-24T09:04:07Z", "finished_at": "2026-10-24T09:04:07Z", "error": null,
    "params": {}, "output": {"train_rows": 214, "holdout_rows": 0}
  },
  "train": {
    "name": "Train models", "kind": "model_training", "depends_on": ["model_selection"],
    "status": "succeeded", "...": "...",
    "output": {
      "models": {
        "RandomForestRegressor": {
          "status": "succeeded", "error": null, "best_trial": 3, "holdout_scores": null,
          "trials": [
            {"params": {"max_features": "sqrt", "n_estimators": 50}, "status": "succeeded",
             "scores": {"mse": 2.6464e-06, "mae": 0.00095777, "mape": 0.00063027, "r2": 0.71201}},
            "..."
          ]
        },
        "DecisionTreeRegressor": {
          "status": "succeeded", "error": null, "best_trial": 0, "holdout_scores": null,
          "trials": [
            {"params": {"max_depth": 5, "min_samples_split": 2}, "status": "succeeded",
             "scores": {"mse": 3.3709e-06, "mae": 0.0011936, "mape": 0.00078566, "r2": 0.62316}},
            "...",
            {"params": {"max_depth": 10, "min_samples_split": 10}, "status": "pruned",
             "scores": {"mse": null, "mae": null, "mape": null, "r2": null}}
          ]
        }
      }
    }
  },
  "select_best": {"...": "...", "output": {"best_model": "Ridge", "score_source": "cv"}}
}
```

Số liệu trong ví dụ được rút gọn chữ số; API trả đủ độ chính xác của `float`.
