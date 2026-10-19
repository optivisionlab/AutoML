# Phương pháp khoa học

HAutoML tự động hóa toàn bộ quy trình học máy trên dữ liệu dạng bảng: tiền xử lý, chọn chiến lược kiểm định chéo, tối ưu siêu tham số cho nhiều mô hình song song, chọn mô hình tốt nhất và đóng gói để suy luận.

```text
Dataset ─► Tiền xử lý ─► Chọn chiến lược CV ─► Tối ưu siêu tham số (mỗi mô hình một tác vụ)
                                                        │
        Suy luận ◄─ Đóng gói artifact ◄─ Chọn mô hình tốt nhất ◄─ Đánh giá & xếp hạng
```

## 1. Các loại bài toán

| `problem_type` | Mô tả | Metric mặc định để xếp hạng |
|----------------|-------|------------------------------|
| `classification` | Phân loại | `accuracy` |
| `regression` | Hồi quy | `r2` |
| `time_series` | Dự báo chuỗi thời gian một bước | `rmse` |

Danh sách mô hình và lưới siêu tham số của từng loại bài toán được khai báo trong `src/backend/assets/*.yml`.

## 2. Tiền xử lý dữ liệu

Hệ thống tự phát hiện kiểu cột (số, phân loại, văn bản) và dựng `ColumnTransformer` tương ứng. Các dòng thiếu giá trị mục tiêu bị loại bỏ trước khi huấn luyện.

- **Phân loại**: nhãn mục tiêu được mã hóa bằng `LabelEncoder`.
- **Hồi quy**: giá trị mục tiêu liên tục được chia thành các bin theo phân vị để phân tầng khi chia fold.
- **Chuỗi thời gian**: không dùng bộ tiền xử lý chung. Việc điền khuyết, chuẩn hóa và mã hóa nằm trong `Pipeline` của mô hình và được fit riêng trên từng fold huấn luyện, nhằm tránh rò rỉ dữ liệu (data leakage). Xem [Dự báo chuỗi thời gian](time_series.md).

## 3. Chiến lược kiểm định chéo ba bậc (3-Tier CV) { #3-chien-luoc-kiem-dinh-cheo-ba-bac-3-tier-cv }

Chiến lược kiểm định được chọn tự động theo số dòng dữ liệu, để cân bằng giữa độ tin cậy của ước lượng và chi phí tính toán.

=== "Phân loại"

    | Bậc | Số dòng | Chiến lược |
    |-----|---------|-----------|
    | 1 | ≤ 500 | `RepeatedStratifiedKFold` (5 lần lặp) |
    | 2 | 501 – 10.000 | `StratifiedKFold` |
    | 3 | > 10.000 | Tách holdout 80/20 + `StratifiedKFold` |

    Số fold là `max(2, min(5, số mẫu của lớp nhỏ nhất))` để mỗi fold đều có đủ mẫu của mọi lớp.

=== "Hồi quy"

    | Bậc | Số dòng | Chiến lược |
    |-----|---------|-----------|
    | 1 | ≤ 500 | `ContinuousRepeatedStratifiedKFold` (5 lần lặp) |
    | 2 | 501 – 10.000 | `ContinuousStratifiedKFold` |
    | 3 | > 10.000 | Tách holdout 80/20 phân tầng + `ContinuousStratifiedKFold` |

    Các fold được phân tầng trên giá trị mục tiêu đã chia bin. Số fold là 5 (hoặc `n_rows // 4` nếu dưới 20 dòng).

=== "Chuỗi thời gian"

    | Bậc | Số dòng khả dụng | Chiến lược |
    |-----|------------------|-----------|
    | 1 | < 200 | `TimeSeriesSplit` 3 fold, cửa sổ mở rộng |
    | 2 | ≥ 200 | `TimeSeriesSplit` 5 fold, cửa sổ mở rộng |

    Fold luôn theo thứ tự thời gian, không xáo trộn dữ liệu.

Ở bậc 3 (dữ liệu lớn), tập holdout chỉ dùng để đánh giá cuối cùng các mô hình đã tối ưu, không tham gia chọn siêu tham số.

## 4. Tối ưu siêu tham số (HPO)

Mỗi mô hình ứng viên được tối ưu độc lập bằng một trong năm thuật toán: `grid_search`, `random_search`, `bayesian_search`, `genetic_algorithm`, `tpe_search` (mặc định). Tất cả cùng một lớp cơ sở nên có chung cơ chế **dừng sớm** (early stopping) và **cắt tỉa** (pruning). Chi tiết xem [Tối ưu siêu tham số](hpo.md).

## 5. Huấn luyện phân tán

Mỗi cặp (mô hình, lưới siêu tham số) là một tác vụ độc lập, nên có thể chạy song song trên nhiều tiến trình hoặc nhiều máy bằng **PyMapReduce**:

- `MAPREDUCE_MODE=local`: chạy trên máy hiện tại.
- `MAPREDUCE_MODE=cluster`: kết nối tới head node (`MAPREDUCE_HEAD_ADDRESS`) và phân phối tác vụ cho các worker.

Kết quả của các tác vụ được gom về để xếp hạng. Xem luồng đầy đủ ở [Kiến trúc](architecture.md).

## 6. Đánh giá và chọn mô hình

| Loại bài toán | Metric |
|---------------|--------|
| Phân loại | `accuracy`, `balanced_accuracy`, `precision_macro`, `precision_weighted`, `recall_macro`, `recall_weighted`, `f1_macro`, `f1_weighted` |
| Hồi quy | `mse`, `mae`, `mape`, `r2` |
| Chuỗi thời gian | `mse`, `mae`, `rmse`, `r2` |

Mô hình có điểm cao nhất theo `metric_sort` do người dùng chọn là **mô hình tốt nhất**. Điểm của toàn bộ mô hình còn lại được lưu lại thành bảng xếp hạng (`model_scores`) để so sánh.

## 7. Đóng gói và suy luận

Mô hình tốt nhất được đóng gói cùng bộ tiền xử lý, danh sách đặc trưng và cấu hình CV thành một artifact duy nhất, lưu trên MinIO. Từ artifact này, người dùng có thể:

- gọi API dự đoán thời gian thực hoặc theo file,
- xuất Jupyter Notebook, gói Docker microservice hoặc file `.pkl`.

Xem [Tài liệu API](backend_api.md#4-suy-luan-trien-khai-mo-hinh-inference).
