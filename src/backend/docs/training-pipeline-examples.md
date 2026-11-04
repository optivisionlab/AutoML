# Ví dụ phản hồi API pipeline JSON (dữ liệu thật)

Mọi phản hồi trong tài liệu này được gọi thật tới `GET /api/v1/inference/jobs/{job_id}` trên image `dutamoi/hautoml-backend:pipeline-json` (Docker Hub), DB trống, huấn luyện trên bộ dữ liệu thật của scikit-learn. Bảng và đoạn JSON được sinh tự động từ phản hồi, không chỉnh tay.

Định nghĩa từng trường: [training-pipeline.md](training-pipeline.md). Phản hồi đầy đủ của từng trường hợp: thư mục [`examples/pipeline/`](examples/pipeline/).

## Tóm tắt

| Trường hợp | HTTP | `status` gốc | `source` | Ghi chú | File đầy đủ |
| --- | --- | --- | --- | --- | --- |
| Regression thành công | 200 | `succeeded` | `tracked` | Diabetes (442 dòng), 8 mô hình, 36 trials | [regression_succeeded.json](examples/pipeline/regression_succeeded.json) |
| Classification thành công | 200 | `succeeded` | `tracked` | Iris (150 dòng), 6 mô hình, 58 trials | [classification_succeeded.json](examples/pipeline/classification_succeeded.json) |
| Job đang chờ worker | 200 | `queued` | `tracked` | Job đã tạo, worker chưa nhận | [queued.json](examples/pipeline/queued.json) |
| Job đang huấn luyện | 200 | `running` | `tracked` | Đang ở bước `train` | [running.json](examples/pipeline/running.json) |
| Job lỗi | 200 | `failed` | `tracked` | Cột mục tiêu không tồn tại | [failed.json](examples/pipeline/failed.json) |
| Job lưu theo dạng cũ | 200 | `succeeded` | `legacy` | Job lưu bởi backend cũ, chỉ có trial tốt nhất | [legacy.json](examples/pipeline/legacy.json) |
| Thiếu token | 401 | `—` | `—` | Not authenticated | [error_401_no_token.json](examples/pipeline/error_401_no_token.json) |
| Job của người khác | 403 | `—` | `—` | You do not have permission to access this job. | [error_403_other_user.json](examples/pipeline/error_403_other_user.json) |
| Job không tồn tại | 404 | `—` | `—` | Model training job '000000000000000000000000' not found. | [error_404_unknown_job.json](examples/pipeline/error_404_unknown_job.json) |

Mọi phản hồi thành công có dạng `{"success": true, "message": "...", "data": <pipeline>, "meta": null}`; các đoạn dưới chỉ trích `data`.

## 1. Regression thành công

Job `6ae5a5402ebdf7162486abf5`: Diabetes, cột mục tiêu `target`, `grid_search`, `metric_sort: "r2"`.

### Cấp gốc và các node

```json
{
  "job_id": "6ae5a5402ebdf7162486abf5",
  "version": "2.0.0",
  "mode": "automl",
  "source": "tracked",
  "status": "succeeded",
  "error": null,
  "updated_at": "2026-10-31T08:22:40Z"
}
```

| Node | `status` | `started_at` | `finished_at` | `error` |
| --- | --- | --- | --- | --- |
| `read_dataset` | `succeeded` | 2026-10-31T08:22:24Z | 2026-10-31T08:22:24Z | null |
| `split_holdout_data` | `skipped` | 2026-10-31T08:22:24Z | 2026-10-31T08:22:24Z | null |
| `preprocessing` | `succeeded` | 2026-10-31T08:22:24Z | 2026-10-31T08:22:24Z | null |
| `model_selection` | `succeeded` | 2026-10-31T08:22:24Z | 2026-10-31T08:22:24Z | null |
| `train` | `succeeded` | 2026-10-31T08:22:24Z | 2026-10-31T08:22:40Z | null |
| `select_best` | `succeeded` | 2026-10-31T08:22:40Z | 2026-10-31T08:22:40Z | null |
| `save_result` | `succeeded` | 2026-10-31T08:22:40Z | 2026-10-31T08:22:40Z | null |

`split_holdout_data` là `skipped` vì dữ liệu ≤ 10.000 dòng nên không tách holdout.

```json
{
  "read_dataset": {
    "name": "Read dataset",
    "kind": "data_loading",
    "depends_on": [],
    "status": "succeeded",
    "started_at": "2026-10-31T08:22:24Z",
    "finished_at": "2026-10-31T08:22:24Z",
    "error": null,
    "params": {
      "id_data": "6ae5a5402ebdf7162486abf3",
      "format": "parquet"
    },
    "output": {
      "data_url": "dataset/6ae5a53d2ebdf7162486abef/91158fe9-9f15-41f7-a5d4-bfc1b18ffbbf.parquet",
      "n_rows": 442,
      "n_columns": 11
    }
  },
  "split_holdout_data": {
    "name": "Split holdout data",
    "kind": "data_splitting",
    "depends_on": [
      "read_dataset"
    ],
    "status": "skipped",
    "started_at": "2026-10-31T08:22:24Z",
    "finished_at": "2026-10-31T08:22:24Z",
    "error": null,
    "params": {},
    "output": {
      "train_rows": 442,
      "holdout_rows": 0
    }
  },
  "preprocessing": {
    "name": "Preprocessing",
    "kind": "preprocessing",
    "depends_on": [
      "split_holdout_data"
    ],
    "status": "succeeded",
    "started_at": "2026-10-31T08:22:24Z",
    "finished_at": "2026-10-31T08:22:24Z",
    "error": null,
    "params": {
      "target": "target",
      "list_feature": [
        "age",
        "sex",
        "bmi",
        "bp",
        "s1",
        "s2",
        "s3",
        "s4",
        "s5",
        "s6"
      ]
    },
    "output": {
      "dropped_rows": 0,
      "n_features": 10,
      "column_types": {
        "numeric": [
          "age",
          "sex",
          "bmi",
          "bp",
          "s1",
          "s2",
          "s3",
          "s4",
          "s5",
          "s6"
        ],
        "categorical": [],
        "text": []
      },
      "class_distribution": null
    }
  },
  "model_selection": {
    "name": "Model selection",
    "kind": "model_selection",
    "depends_on": [
      "preprocessing"
    ],
    "status": "succeeded",
    "started_at": "2026-10-31T08:22:24Z",
    "finished_at": "2026-10-31T08:22:24Z",
    "error": null,
    "params": {
      "problem_type": "regression",
      "search_algorithm": "grid_search",
      "metric_sort": "r2",
      "timeout": 600,
      "model_names": [
        "LinearRegression",
        "DecisionTreeRegressor",
        "RandomForestRegressor",
        "GradientBoostingRegressor",
        "KNeighborsRegressor",
        "Ridge",
        "Lasso",
        "SVR"
      ],
      "metrics": {
        "mse": "minimize",
        "mae": "minimize",
        "mape": "minimize",
        "r2": "maximize"
      },
      "cv": {
        "name": "ContinuousRepeatedStratifiedKFold",
        "n_splits": 5,
        "n_repeats": 5,
        "description": "Tier 1 (<= 500 rows): Continuous Repeated Stratified K-Fold (5 splits, 5 repeats)"
      }
    },
    "output": {}
  }
}
```

### Kết quả từng mô hình

★ là mô hình được chọn (`select_best.output.best_model`).

| Mô hình | `status` | Số trial | `pruned` | `best_trial` | r2 của trial tốt nhất | Tham số tốt nhất |
| --- | --- | --- | --- | --- | --- | --- |
| `LinearRegression` | `succeeded` | 2 | 0 | 0 | 0.4927 | `{"fit_intercept": true}` |
| `DecisionTreeRegressor` | `succeeded` | 9 | 4 | 2 | 0.2635 | `{"max_depth": 5, "min_samples_split": 10}` |
| `RandomForestRegressor` | `succeeded` | 4 | 0 | 3 | 0.4497 | `{"max_features": "log2", "n_estimators": 100}` |
| `GradientBoostingRegressor` | `succeeded` | 4 | 0 | 0 | 0.4447 | `{"learning_rate": 0.05, "n_estimators": 50}` |
| `KNeighborsRegressor` | `succeeded` | 8 | 0 | 7 | 0.4323 | `{"n_neighbors": 9, "weights": "distance"}` |
| `Ridge` | `succeeded` | 3 | 0 | 2 | 0.4936 | `{"alpha": 10.0}` |
| `Lasso` ★ | `succeeded` | 3 | 0 | 1 | 0.4948 | `{"alpha": 1.0}` |
| `SVR` | `succeeded` | 3 | 0 | 2 | 0.4771 | `{"C": 10, "kernel": "rbf"}` |

```json
{
  "select_best": {
    "name": "Select best model",
    "kind": "model_selection",
    "depends_on": [
      "train"
    ],
    "status": "succeeded",
    "started_at": "2026-10-31T08:22:40Z",
    "finished_at": "2026-10-31T08:22:40Z",
    "error": null,
    "params": {},
    "output": {
      "best_model": "Lasso",
      "score_source": "cv"
    }
  },
  "save_result": {
    "name": "Save result",
    "kind": "result_storage",
    "depends_on": [
      "select_best"
    ],
    "status": "succeeded",
    "started_at": "2026-10-31T08:22:40Z",
    "finished_at": "2026-10-31T08:22:40Z",
    "error": null,
    "params": {
      "bucket_name": "models"
    },
    "output": {
      "object_name": "6ae5a53d2ebdf7162486abef/6ae5a5402ebdf7162486abf5/Lasso_1.pkl"
    }
  }
}
```

### Các nhánh trials của `DecisionTreeRegressor`

Mỗi dòng là một phần tử của `trials`; ★ là `best_trial`. Metric sai số (`mse`, `mae`, `mape`) ghi số dương; trial `pruned` có điểm `null`.

| # | Tham số | `status` | mse | mae | mape | r2 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | `{"max_depth": 5, "min_samples_split": 2}` | `succeeded` | 4444.8781 | 53.0867 | 0.4502 | 0.2485 |
| 1 | `{"max_depth": 5, "min_samples_split": 5}` | `succeeded` | 4407.5966 | 52.8743 | 0.4484 | 0.2549 |
| 2 ★ | `{"max_depth": 5, "min_samples_split": 10}` | `succeeded` | 4355.7426 | 52.5750 | 0.4469 | 0.2635 |
| 3 | `{"max_depth": 10, "min_samples_split": 2}` | `succeeded` | 6483.2585 | 63.2560 | 0.5467 | -0.0949 |
| 4 | `{"max_depth": 10, "min_samples_split": 5}` | `succeeded` | 6302.2372 | 62.5294 | 0.5404 | -0.0638 |
| 5 | `{"max_depth": 10, "min_samples_split": 10}` | `pruned` | null | null | null | null |
| 6 | `{"max_depth": 15, "min_samples_split": 2}` | `pruned` | null | null | null | null |
| 7 | `{"max_depth": 15, "min_samples_split": 5}` | `pruned` | null | null | null | null |
| 8 | `{"max_depth": 15, "min_samples_split": 10}` | `pruned` | null | null | null | null |

```json
{
  "DecisionTreeRegressor": {
    "status": "succeeded",
    "error": null,
    "best_trial": 2,
    "trials": [
      {
        "params": {
          "max_depth": 5,
          "min_samples_split": 2
        },
        "status": "succeeded",
        "scores": {
          "mse": 4444.878144861765,
          "mae": 53.08674864889275,
          "mape": 0.45023605862574234,
          "r2": 0.24853673604732202
        }
      },
      {
        "params": {
          "max_depth": 5,
          "min_samples_split": 5
        },
        "status": "succeeded",
        "scores": {
          "mse": 4407.596607556821,
          "mae": 52.87429371059862,
          "mape": 0.448422908071473,
          "r2": 0.25493286964796724
        }
      },
      {
        "params": {
          "max_depth": 5,
          "min_samples_split": 10
        },
        "status": "succeeded",
        "scores": {
          "mse": 4355.742614706832,
          "mae": 52.57495998510129,
          "mape": 0.4469149802875876,
          "r2": 0.26354165359780124
        }
      },
      {
        "params": {
          "max_depth": 10,
          "min_samples_split": 2
        },
        "status": "succeeded",
        "scores": {
          "mse": 6483.258505616225,
          "mae": 63.25600842004128,
          "mape": 0.54667527437889,
          "r2": -0.09493428987901618
        }
      },
      {
        "params": {
          "max_depth": 10,
          "min_samples_split": 5
        },
        "status": "succeeded",
        "scores": {
          "mse": 6302.237232037163,
          "mae": 62.529440496804575,
          "mape": 0.540364118638074,
          "r2": -0.06380285714021686
        }
      },
      {
        "params": {
          "max_depth": 10,
          "min_samples_split": 10
        },
        "status": "pruned",
        "scores": {
          "mse": null,
          "mae": null,
          "mape": null,
          "r2": null
        }
      },
      {
        "params": {
          "max_depth": 15,
          "min_samples_split": 2
        },
        "status": "pruned",
        "scores": {
          "mse": null,
          "mae": null,
          "mape": null,
          "r2": null
        }
      },
      {
        "params": {
          "max_depth": 15,
          "min_samples_split": 5
        },
        "status": "pruned",
        "scores": {
          "mse": null,
          "mae": null,
          "mape": null,
          "r2": null
        }
      },
      {
        "params": {
          "max_depth": 15,
          "min_samples_split": 10
        },
        "status": "pruned",
        "scores": {
          "mse": null,
          "mae": null,
          "mape": null,
          "r2": null
        }
      }
    ],
    "holdout_scores": null
  }
}
```

## 2. Classification thành công

Job `6ae5a5402ebdf7162486abf6`: Iris, cột mục tiêu `species`, `grid_search`, `metric_sort: "f1_macro"`. Khác regression ở metric (đều `maximize`), CV phân tầng theo lớp và `class_distribution`.

```json
{
  "preprocessing": {
    "name": "Preprocessing",
    "kind": "preprocessing",
    "depends_on": [
      "split_holdout_data"
    ],
    "status": "succeeded",
    "started_at": "2026-10-31T08:22:24Z",
    "finished_at": "2026-10-31T08:22:24Z",
    "error": null,
    "params": {
      "target": "species",
      "list_feature": [
        "sepal length (cm)",
        "sepal width (cm)",
        "petal length (cm)",
        "petal width (cm)"
      ]
    },
    "output": {
      "dropped_rows": 0,
      "n_features": 4,
      "column_types": {
        "numeric": [
          "sepal length (cm)",
          "sepal width (cm)",
          "petal length (cm)",
          "petal width (cm)"
        ],
        "categorical": [],
        "text": []
      },
      "class_distribution": {
        "setosa": 50,
        "versicolor": 50,
        "virginica": 50
      }
    }
  },
  "model_selection": {
    "name": "Model selection",
    "kind": "model_selection",
    "depends_on": [
      "preprocessing"
    ],
    "status": "succeeded",
    "started_at": "2026-10-31T08:22:24Z",
    "finished_at": "2026-10-31T08:22:24Z",
    "error": null,
    "params": {
      "problem_type": "classification",
      "search_algorithm": "grid_search",
      "metric_sort": "f1_macro",
      "timeout": 600,
      "model_names": [
        "DecisionTreeClassifier",
        "RandomForestClassifier",
        "KNeighborsClassifier",
        "SVC",
        "LogisticRegression",
        "GaussianNB"
      ],
      "metrics": {
        "accuracy": "maximize",
        "balanced_accuracy": "maximize",
        "precision_macro": "maximize",
        "precision_weighted": "maximize",
        "recall_macro": "maximize",
        "recall_weighted": "maximize",
        "f1_macro": "maximize",
        "f1_weighted": "maximize"
      },
      "cv": {
        "name": "RepeatedStratifiedKFold",
        "n_splits": 5,
        "n_repeats": 5,
        "description": "Tier 1 (30 - 500 rows): RepeatedStratifiedKFold (5 splits, 5 repeats)"
      }
    },
    "output": {}
  }
}
```

| Mô hình | `status` | Số trial | `pruned` | `best_trial` | f1_macro của trial tốt nhất | Tham số tốt nhất |
| --- | --- | --- | --- | --- | --- | --- |
| `DecisionTreeClassifier` | `succeeded` | 9 | 2 | 2 | 0.9451 | `{"max_depth": 5, "min_samples_split": 10}` |
| `RandomForestClassifier` | `succeeded` | 12 | 7 | 1 | 0.9518 | `{"max_features": "sqrt", "n_estimators": 100}` |
| `KNeighborsClassifier` | `succeeded` | 8 | 2 | 5 | 0.9612 | `{"n_neighbors": 7, "weights": "distance"}` |
| `SVC` ★ | `succeeded` | 9 | 2 | 8 | 0.9705 | `{"C": 10, "kernel": "linear", "max_iter": 2000}` |
| `LogisticRegression` | `succeeded` | 16 | 1 | 12 | 0.9572 | `{"C": 1, "max_iter": 500, "penalty": "l1", "solver": "saga"}` |
| `GaussianNB` | `succeeded` | 4 | 0 | 0 | 0.9532 | `{"var_smoothing": 1e-09}` |

### Các nhánh trials của `RandomForestClassifier`

Bảng chỉ hiện 4 trong 8 metric; JSON bên dưới có đủ.

| # | Tham số | `status` | accuracy | balanced_accuracy | f1_macro | f1_weighted |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | `{"max_features": "sqrt", "n_estimators": 50}` | `succeeded` | 0.9507 | 0.9507 | 0.9504 | 0.9504 |
| 1 ★ | `{"max_features": "sqrt", "n_estimators": 100}` | `succeeded` | 0.9520 | 0.9520 | 0.9518 | 0.9518 |
| 2 | `{"max_features": "sqrt", "n_estimators": 200}` | `succeeded` | 0.9520 | 0.9520 | 0.9518 | 0.9518 |
| 3 | `{"max_features": "log2", "n_estimators": 50}` | `succeeded` | 0.9520 | 0.9520 | 0.9518 | 0.9518 |
| 4 | `{"max_features": "log2", "n_estimators": 100}` | `succeeded` | 0.9520 | 0.9520 | 0.9518 | 0.9518 |
| 5 | `{"max_features": "log2", "n_estimators": 200}` | `pruned` | null | null | null | null |
| 6 | `{"max_features": 0.5, "n_estimators": 50}` | `pruned` | null | null | null | null |
| 7 | `{"max_features": 0.5, "n_estimators": 100}` | `pruned` | null | null | null | null |
| 8 | `{"max_features": 0.5, "n_estimators": 200}` | `pruned` | null | null | null | null |
| 9 | `{"max_features": 1, "n_estimators": 50}` | `pruned` | null | null | null | null |
| 10 | `{"max_features": 1, "n_estimators": 100}` | `pruned` | null | null | null | null |
| 11 | `{"max_features": 1, "n_estimators": 200}` | `pruned` | null | null | null | null |

```json
{
  "RandomForestClassifier": {
    "status": "succeeded",
    "error": null,
    "best_trial": 1,
    "trials": [
      {
        "params": {
          "max_features": "sqrt",
          "n_estimators": 50
        },
        "status": "succeeded",
        "scores": {
          "accuracy": 0.9506666666666667,
          "balanced_accuracy": 0.9506666666666667,
          "precision_macro": 0.9543030303030303,
          "precision_weighted": 0.9543030303030303,
          "recall_macro": 0.9506666666666667,
          "recall_weighted": 0.9506666666666667,
          "f1_macro": 0.9504484443431813,
          "f1_weighted": 0.9504484443431813
        }
      },
      {
        "params": {
          "max_features": "sqrt",
          "n_estimators": 100
        },
        "status": "succeeded",
        "scores": {
          "accuracy": 0.9520000000000001,
          "balanced_accuracy": 0.9519999999999998,
          "precision_macro": 0.9551380471380472,
          "precision_weighted": 0.9551380471380472,
          "recall_macro": 0.9519999999999998,
          "recall_weighted": 0.9520000000000001,
          "f1_macro": 0.9518323080428344,
          "f1_weighted": 0.9518323080428343
        }
      },
      {
        "params": {
          "max_features": "sqrt",
          "n_estimators": 200
        },
        "status": "succeeded",
        "scores": {
          "accuracy": 0.9520000000000001,
          "balanced_accuracy": 0.9519999999999998,
          "precision_macro": 0.9551380471380472,
          "precision_weighted": 0.9551380471380472,
          "recall_macro": 0.9519999999999998,
          "recall_weighted": 0.9520000000000001,
          "f1_macro": 0.9518323080428343,
          "f1_weighted": 0.9518323080428343
        }
      },
      {
        "params": {
          "max_features": "log2",
          "n_estimators": 50
        },
        "status": "succeeded",
        "scores": {
          "accuracy": 0.9520000000000001,
          "balanced_accuracy": 0.9519999999999998,
          "precision_macro": 0.9558114478114479,
          "precision_weighted": 0.9558114478114479,
          "recall_macro": 0.9519999999999998,
          "recall_weighted": 0.9520000000000001,
          "f1_macro": 0.9517918027391711,
          "f1_weighted": 0.9517918027391711
        }
      },
      {
        "params": {
          "max_features": "log2",
          "n_estimators": 100
        },
        "status": "succeeded",
        "scores": {
          "accuracy": 0.9520000000000001,
          "balanced_accuracy": 0.9520000000000001,
          "precision_macro": 0.9555420875420875,
          "precision_weighted": 0.9555420875420875,
          "recall_macro": 0.9520000000000001,
          "recall_weighted": 0.9520000000000001,
          "f1_macro": 0.9517918027391711,
          "f1_weighted": 0.9517918027391711
        }
      },
      {
        "params": {
          "max_features": "log2",
          "n_estimators": 200
        },
        "status": "pruned",
        "scores": {
          "accuracy": null,
          "balanced_accuracy": null,
          "precision_macro": null,
          "precision_weighted": null,
          "recall_macro": null,
          "recall_weighted": null,
          "f1_macro": null,
          "f1_weighted": null
        }
      },
      {
        "params": {
          "max_features": 0.5,
          "n_estimators": 50
        },
        "status": "pruned",
        "scores": {
          "accuracy": null,
          "balanced_accuracy": null,
          "precision_macro": null,
          "precision_weighted": null,
          "recall_macro": null,
          "recall_weighted": null,
          "f1_macro": null,
          "f1_weighted": null
        }
      },
      {
        "params": {
          "max_features": 0.5,
          "n_estimators": 100
        },
        "status": "pruned",
        "scores": {
          "accuracy": null,
          "balanced_accuracy": null,
          "precision_macro": null,
          "precision_weighted": null,
          "recall_macro": null,
          "recall_weighted": null,
          "f1_macro": null,
          "f1_weighted": null
        }
      },
      {
        "params": {
          "max_features": 0.5,
          "n_estimators": 200
        },
        "status": "pruned",
        "scores": {
          "accuracy": null,
          "balanced_accuracy": null,
          "precision_macro": null,
          "precision_weighted": null,
          "recall_macro": null,
          "recall_weighted": null,
          "f1_macro": null,
          "f1_weighted": null
        }
      },
      {
        "params": {
          "max_features": 1,
          "n_estimators": 50
        },
        "status": "pruned",
        "scores": {
          "accuracy": null,
          "balanced_accuracy": null,
          "precision_macro": null,
          "precision_weighted": null,
          "recall_macro": null,
          "recall_weighted": null,
          "f1_macro": null,
          "f1_weighted": null
        }
      },
      {
        "params": {
          "max_features": 1,
          "n_estimators": 100
        },
        "status": "pruned",
        "scores": {
          "accuracy": null,
          "balanced_accuracy": null,
          "precision_macro": null,
          "precision_weighted": null,
          "recall_macro": null,
          "recall_weighted": null,
          "f1_macro": null,
          "f1_weighted": null
        }
      },
      {
        "params": {
          "max_features": 1,
          "n_estimators": 200
        },
        "status": "pruned",
        "scores": {
          "accuracy": null,
          "balanced_accuracy": null,
          "precision_macro": null,
          "precision_weighted": null,
          "recall_macro": null,
          "recall_weighted": null,
          "f1_macro": null,
          "f1_weighted": null
        }
      }
    ],
    "holdout_scores": null
  }
}
```

## 3. Job đang chờ worker (`queued`)

Job vừa tạo, worker chưa nhận (chụp khi tạm dừng worker). Backend chưa lưu pipeline nên API dựng JSON từ thông tin job: mọi node `queued`, chưa có thời gian, `models` rỗng.

```json
{
  "job_id": "6ae5b7e5b92061eaa3f0a4fd",
  "version": "2.0.0",
  "mode": "automl",
  "source": "tracked",
  "status": "queued",
  "error": null,
  "updated_at": "2026-10-31T09:41:57Z",
  "read_dataset": {
    "name": "Read dataset",
    "kind": "data_loading",
    "depends_on": [],
    "status": "queued",
    "started_at": null,
    "finished_at": null,
    "error": null,
    "params": {
      "id_data": "6ae5a5402ebdf7162486abf4",
      "format": "parquet"
    },
    "output": {}
  },
  "...": "6 node còn lại cùng dạng, status \"queued\""
}
```

## 4. Job đang huấn luyện

| Node | `status` | `started_at` | `finished_at` | `error` |
| --- | --- | --- | --- | --- |
| `read_dataset` | `succeeded` | 2026-10-31T09:41:30Z | 2026-10-31T09:41:30Z | null |
| `split_holdout_data` | `skipped` | 2026-10-31T09:41:30Z | 2026-10-31T09:41:30Z | null |
| `preprocessing` | `succeeded` | 2026-10-31T09:41:30Z | 2026-10-31T09:41:30Z | null |
| `model_selection` | `succeeded` | 2026-10-31T09:41:30Z | 2026-10-31T09:41:30Z | null |
| `train` | `running` | 2026-10-31T09:41:30Z | null | null |
| `select_best` | `queued` | null | null | null |
| `save_result` | `queued` | null | null | null |

```json
{
  "job_id": "6ae5b7cab92061eaa3f0a4fc",
  "version": "2.0.0",
  "mode": "automl",
  "source": "tracked",
  "status": "running",
  "error": null,
  "updated_at": "2026-10-31T09:41:30Z",
  "train": {
    "name": "Train models",
    "kind": "model_training",
    "depends_on": [
      "model_selection"
    ],
    "status": "running",
    "started_at": "2026-10-31T09:41:30Z",
    "finished_at": null,
    "error": null,
    "params": {},
    "output": {
      "models": {
        "LinearRegression": {
          "status": "running",
          "error": null,
          "best_trial": null,
          "trials": null,
          "holdout_scores": null
        },
        "DecisionTreeRegressor": {
          "status": "running",
          "error": null,
          "best_trial": null,
          "trials": null,
          "holdout_scores": null
        },
        "RandomForestRegressor": {
          "status": "running",
          "error": null,
          "best_trial": null,
          "trials": null,
          "holdout_scores": null
        },
        "GradientBoostingRegressor": {
          "status": "running",
          "error": null,
          "best_trial": null,
          "trials": null,
          "holdout_scores": null
        },
        "KNeighborsRegressor": {
          "status": "running",
          "error": null,
          "best_trial": null,
          "trials": null,
          "holdout_scores": null
        },
        "Ridge": {
          "status": "running",
          "error": null,
          "best_trial": null,
          "trials": null,
          "holdout_scores": null
        },
        "Lasso": {
          "status": "running",
          "error": null,
          "best_trial": null,
          "trials": null,
          "holdout_scores": null
        },
        "SVR": {
          "status": "running",
          "error": null,
          "best_trial": null,
          "trials": null,
          "holdout_scores": null
        }
      }
    }
  }
}
```

> Kết quả các mô hình chỉ được ghi **một lần khi tất cả mô hình train xong**; trong lúc chạy mọi mô hình đều `running` với `trials: null`. Vì vậy hiện chưa hiển thị được tiến độ theo từng mô hình, chỉ theo từng node.

## 5. Job lỗi

Job `6ae5a5402ebdf7162486abf7` tạo với `target: "no_such_column"`. Node gây lỗi (`preprocessing`) nhận `failed` kèm `error`; mọi node chưa chạy thành `skipped`, kể cả `split_holdout_data` vì node này chỉ được ghi sau khi tiền xử lý xong. `error` gốc chứa cùng thông báo.

| Node | `status` | `started_at` | `finished_at` | `error` |
| --- | --- | --- | --- | --- |
| `read_dataset` | `succeeded` | 2026-10-31T08:22:24Z | 2026-10-31T08:22:24Z | null |
| `split_holdout_data` | `skipped` | null | null | null |
| `preprocessing` | `failed` | 2026-10-31T08:22:24Z | 2026-10-31T08:22:24Z | Training failure: Target column 'no_such_column' not found i… |
| `model_selection` | `skipped` | null | null | null |
| `train` | `skipped` | null | null | null |
| `select_best` | `skipped` | null | null | null |
| `save_result` | `skipped` | null | null | null |

```json
{
  "job_id": "6ae5a5402ebdf7162486abf7",
  "version": "2.0.0",
  "mode": "automl",
  "source": "tracked",
  "status": "failed",
  "error": {
    "message": "Training failure: Target column 'no_such_column' not found in dataset columns: ['sepal length (cm)', 'sepal width (cm)', 'petal length (cm)', 'petal width (cm)', 'species']"
  },
  "updated_at": "2026-10-31T08:22:24Z",
  "preprocessing": {
    "name": "Preprocessing",
    "kind": "preprocessing",
    "depends_on": [
      "split_holdout_data"
    ],
    "status": "failed",
    "started_at": "2026-10-31T08:22:24Z",
    "finished_at": "2026-10-31T08:22:24Z",
    "error": {
      "message": "Training failure: Target column 'no_such_column' not found in dataset columns: ['sepal length (cm)', 'sepal width (cm)', 'petal length (cm)', 'petal width (cm)', 'species']"
    },
    "params": {
      "target": "no_such_column",
      "list_feature": []
    },
    "output": {}
  }
}
```

## 6. Job lưu theo dạng cũ (`source: "legacy"`)

Bản ghi job được chèn vào MongoDB đúng như backend cũ (`automl/engine.py` trên nhánh `main`) từng lưu: model nhị phân nằm trong trường `model`, `best_model` là chuỗi `RandomForestClassifier(max_depth=5)`, không có `pipeline`. Phần JSON dưới là phản hồi thật của API cho bản ghi đó. Mỗi mô hình chỉ có 1 trial (bộ tham số tốt nhất), node không có thời gian, `score_source` là `null`.

```json
{
  "job_id": "6ae5b3a2ea0bbfef998a52fe",
  "version": "2.0.0",
  "mode": "automl",
  "source": "legacy",
  "status": "succeeded",
  "error": null,
  "updated_at": "2026-10-31T09:40:56Z",
  "train": {
    "output": {
      "models": {
        "DecisionTreeClassifier": {
          "status": "succeeded",
          "error": null,
          "best_trial": 0,
          "trials": [
            {
              "params": {
                "max_depth": 3
              },
              "status": "succeeded",
              "scores": {
                "accuracy": 0.9,
                "f1": 0.88
              }
            }
          ],
          "holdout_scores": null
        },
        "RandomForestClassifier": {
          "status": "succeeded",
          "error": null,
          "best_trial": 0,
          "trials": [
            {
              "params": {
                "max_depth": 5
              },
              "status": "succeeded",
              "scores": {
                "accuracy": 0.93,
                "f1": 0.92
              }
            }
          ],
          "holdout_scores": null
        }
      }
    }
  },
  "select_best": {
    "output": {
      "best_model": "RandomForestClassifier",
      "score_source": null
    }
  }
}
```

## 7. Phản hồi lỗi

**Thiếu token**: HTTP 401

```json
{
  "detail": "Not authenticated"
}
```

**Job của người khác**: HTTP 403

```json
{
  "success": false,
  "error_code": "FORBIDDEN",
  "detail": "You do not have permission to access this job.",
  "extra": {}
}
```

**Job không tồn tại**: HTTP 404

```json
{
  "success": false,
  "error_code": "NOT_FOUND",
  "detail": "Model training job '000000000000000000000000' not found.",
  "extra": {}
}
```

## Lưu ý khi dùng dữ liệu

- Điểm được trả với đủ độ chính xác của `float`; bảng ở trên làm tròn 4 chữ số.
- Thứ tự trong `trials` là thứ tự đánh giá, không phải thứ hạng; vị trí là định danh của nhánh.
- `job_id`, `data_url` là của môi trường chạy thử, không tồn tại trên production.
- `GET /api/v1/inference/jobs` (danh sách job, ngoài phạm vi JSON pipeline) trả **500** nếu DB có job từ backend cũ, vì bản ghi cũ thiếu trường `activate` mà `JobItemResponse` bắt buộc.
