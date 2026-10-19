# Tối ưu siêu tham số

HAutoML cung cấp năm thuật toán tối ưu siêu tham số (HPO), cài đặt trong `src/backend/src/modules/hpo/`. Thuật toán được chọn qua trường `search_algorithm` khi [tạo job huấn luyện](backend_api.md#post-datasetsidtraining).

| Giá trị `search_algorithm` | Lớp | Ý tưởng |
|----------------------------|-----|---------|
| `grid_search` | `GridSearch` | Duyệt toàn bộ tổ hợp trong lưới |
| `random_search` | `RandomSearch` | Lấy mẫu ngẫu nhiên các tổ hợp |
| `bayesian_search` | `BayesianSearch` | Tối ưu Bayes với mô hình thay thế (scikit-optimize) |
| `genetic_algorithm` | `GeneticAlgorithmSearch` | Tiến hóa quần thể: chọn lọc, lai ghép, đột biến |
| `tpe_search` (mặc định) | `TPESearch` | Tree-structured Parzen Estimator (Optuna) |

Nếu giá trị không khớp, hệ thống dùng `GridSearch`.

## Tham số chính

| Thuật toán | Tham số | Mặc định |
|------------|---------|----------|
| `RandomSearch` | `n_iter` | 20 |
| `BayesianSearch` | `n_calls` | 25 |
| `TPESearch` | `n_trials`, `patience` | 30, 10 |
| `GeneticAlgorithmSearch` | `population_size`, `n_generations`, `mutation_rate`, `crossover_rate`, `elite_size`, `tournament_size`, `patience` | 10, 5, 0.2, 0.8, 2, 3, 2 |

Số lần thử thực tế không vượt quá số tổ hợp có trong lưới.

## Cơ chế chung

Cả năm lớp cùng kế thừa `BaseSearchCV` ([base.py](https://github.com/optivisionlab/AutoML/blob/main/src/backend/src/modules/hpo/base.py)) nên dùng chung:

- **Kiểm định chéo** bằng bộ chia fold do [chiến lược CV ba bậc](scientific_approach.md#3-chien-luoc-kiem-dinh-cheo-ba-bac-3-tier-cv) cung cấp, tính đồng thời nhiều metric.
- **Dừng sớm**: dừng khi điểm tốt nhất không cải thiện quá `min_delta` (mặc định `1e-4`) sau `patience` lần thử liên tiếp.
- **Cắt tỉa** (`enable_pruning`): bỏ một tổ hợp giữa chừng nếu điểm trung bình các fold đã chạy kém rõ rệt so với các lần thử trước. Chỉ áp dụng sau 5 lần thử khởi động (`pruning_startup_trials`).
- **Kết quả**: `best_estimator_`, `best_params_`, `best_score_`, `cv_results_` và `trials_history_`.

## Định dạng lưới siêu tham số

Lưới khai báo trong `src/backend/assets/*.yml`, mỗi mô hình có một danh sách các lưới con:

```yaml
models:
  1:
    model: RandomForestClassifier
    params:
      - n_estimators: [50, 100, 200]
        max_features: ["sqrt", "log2", 0.5, 1]
```

Để thêm mô hình mới: khai báo mục mới trong file YAML tương ứng và đăng ký lớp estimator trong `modules/models/registry.py` (`MODEL_CLASS_MAP`).
