# API dữ liệu mẫu pipeline huấn luyện

Code: [mock_api.py](mock_api.py). Ý nghĩa từng trường trong `pipeline`: [profiles/regresion_v1.md](profiles/regresion_v1.md).

Chạy API (không cần MongoDB, Kafka hay backend chính):

```bash
pip install fastapi uvicorn
cd src/backend/docs/examples/training-pipeline
uvicorn mock_api:app --port 8001 --reload
```

Base URL: `http://localhost:8001`.

## Phần 1: lấy dữ liệu pipeline mẫu

FE lấy toàn bộ trạng thái pipeline của một job (mọi node và kết quả từng mô hình) trong một lần gọi,
dùng API `/get-pipeline-sample`, gửi JSON:

```jsonc
{
  "problem_type": "regression",  // Bắt buộc: loại bài toán, hiện chỉ có "regression"
  "job_id": "job-001"            // Tùy chọn: nếu truyền, BE gán vào pipeline.job_id; không truyền thì job_id là null
}
```

Thành công thì BE gửi lại JSON, ví dụ:

```json
{
  "success": true,
  "message": "Lấy dữ liệu mẫu pipeline thành công!",
  "pipeline": {
    "job_id": "job-001",
    "version": "1.0.0",
    "mode": "automl",
    "status": null,
    "updated_at": null,
    "read_dataset": {
      "name": "Read dataset",
      "kind": "data_loading",
      "depends_on": [],
      "status": null,
      "started_at": null,
      "finished_at": null,
      "error": null,
      "params": {
        "id_data": null,
        "format": "parquet"
      },
      "output": {
        "data_url": null,
        "cache_hit": null
      }
    },
    "split_holdout_data": {
      "name": "Split holdout data",
      "kind": "data_splitting",
      "depends_on": [
        "read_dataset"
      ],
      "status": null,
      "started_at": null,
      "finished_at": null,
      "error": null,
      "params": {
        "method": "train_test_split",
        "test_size": 0.2,
        "shuffle": true,
        "random_state": 42
      },
      "output": {
        "train_rows": null,
        "holdout_rows": null
      }
    },
    "read_training_data": {
      "name": "Read training data",
      "kind": "data_loading",
      "depends_on": [
        "split_holdout_data"
      ],
      "status": null,
      "started_at": null,
      "finished_at": null,
      "error": null,
      "params": {
        "split": "train"
      },
      "output": {
        "n_rows": null,
        "n_columns": null
      }
    },
    "preprocessing": {
      "name": "Preprocessing",
      "kind": "preprocessing",
      "depends_on": [
        "read_training_data"
      ],
      "status": null,
      "started_at": null,
      "finished_at": null,
      "error": null,
      "params": {
        "list_feature": [],
        "target": null,
        "transformers": {
          "numeric": [
            "SimpleImputer",
            "StandardScaler"
          ],
          "categorical": [
            "SimpleImputer",
            "OneHotEncoder"
          ],
          "text": [
            "SimpleImputer",
            "TfidfVectorizer"
          ]
        }
      },
      "output": {
        "cache_hit": null,
        "dropped_rows": null,
        "column_types": {
          "numeric": [],
          "categorical": [],
          "text": []
        }
      }
    },
    "model_selection": {
      "name": "Model selection",
      "kind": "model_selection",
      "depends_on": [
        "preprocessing"
      ],
      "status": null,
      "started_at": null,
      "finished_at": null,
      "error": null,
      "params": {
        "problem_type": "regression",
        "model_names": [
          "LinearRegression",
          "DecisionTreeRegressor",
          "RandomForestRegressor",
          "GradientBoostingRegressor",
          "XGBRegressor"
        ],
        "search_algorithm": null,
        "max_time": null,
        "metric_sort": null,
        "metrics": {
          "mse": "minimize",
          "mae": "minimize",
          "mape": "minimize",
          "r2": "maximize"
        },
        "split": {
          "method": "KFold",
          "n_splits": 5,
          "shuffle": true,
          "random_state": 42
        }
      },
      "output": {}
    },
    "train": {
      "name": "Train models",
      "kind": "model_training",
      "depends_on": [
        "model_selection"
      ],
      "status": null,
      "started_at": null,
      "finished_at": null,
      "error": null,
      "params": {},
      "output": {
        "models": {
          "LinearRegression": {
            "status": null,
            "error": null,
            "best_params": null,
            "scores": null
          },
          "DecisionTreeRegressor": {
            "status": null,
            "error": null,
            "best_params": null,
            "scores": null
          },
          "RandomForestRegressor": {
            "status": null,
            "error": null,
            "best_params": null,
            "scores": null
          },
          "GradientBoostingRegressor": {
            "status": null,
            "error": null,
            "best_params": null,
            "scores": null
          },
          "XGBRegressor": {
            "status": null,
            "error": null,
            "best_params": null,
            "scores": null
          }
        }
      }
    },
    "select_best": {
      "name": "Select best model",
      "kind": "model_selection",
      "depends_on": [
        "train"
      ],
      "status": null,
      "started_at": null,
      "finished_at": null,
      "error": null,
      "params": {
        "dependency_policy": "all_terminal"
      },
      "output": {
        "best_model": null,
        "time_limit_reached": null
      }
    },
    "save_result": {
      "name": "Save result",
      "kind": "result_storage",
      "depends_on": [
        "select_best"
      ],
      "status": null,
      "started_at": null,
      "finished_at": null,
      "error": null,
      "params": {
        "bucket_name": "models"
      },
      "output": {
        "object_name": null
      }
    }
  }
}
```

Lỗi thì BE gửi lại:

```json
{
  "detail": "<lý do lỗi cụ thể>"
}
```

| HTTP | Khi nào | Ví dụ `detail` |
| --- | --- | --- |
| `401` | Thiếu header `Authorization: Bearer <token>` | `"Thiếu header Authorization: Bearer <token>"` |
| `404` | `problem_type` chưa có mẫu | `"Không có dữ liệu mẫu cho problem_type 'classification'. Hỗ trợ: ['regression']"` |
| `422` | Body thiếu trường hoặc sai kiểu | `"Dữ liệu gửi lên không hợp lệ: problem_type: Field required"` |

API là `POST`, cần header `Authorization: Bearer <token>`. API mẫu chỉ kiểm tra có token, không xác thực token,
nên dùng được `axiosClient` có sẵn của FE (tự gắn Bearer token của phiên đăng nhập).

## Ghi chú cho FE

- Cạnh của đồ thị dựng từ `depends_on` của từng node, không dựa vào thứ tự key trong JSON.
- `null` là chưa có dữ liệu: hiển thị `—`, không thay bằng `0` hay `false`.
- Mô hình tốt nhất: `pipeline.select_best.output.best_model` là key trong `pipeline.train.output.models`;
  điểm chính là `models[best_model].scores[model_selection.params.metric_sort]`.
- Trong file mẫu, mọi giá trị chạy (`status`, thời gian, `output`) đều là `null`. Muốn thử trạng thái khác,
  sửa [profiles/regresion_v1.json](profiles/regresion_v1.json); API đọc lại file mỗi lần gọi, không cần khởi động lại.
- API job thật dự kiến trả `pipeline` cùng cấu trúc, nên component không phải đổi khi chuyển từ API mẫu sang API thật.
