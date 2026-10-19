# Dự báo chuỗi thời gian

HAutoML hỗ trợ dự báo một chuỗi thời gian đơn biến, lấy mẫu đều (ví dụ theo giờ hoặc ngày) bằng các mô hình scikit-learn. Chọn `problem_type = "time_series"` khi [tạo job huấn luyện](backend_api.md#post-datasetsidtraining). Mã nguồn: `modules/preprocessing/time_series.py`.

## Yêu cầu dữ liệu

- Đúng **một cột thời gian** trong `list_feature`: kiểu datetime, hoặc cột văn bản mà mọi giá trị đều đọc được thành ngày giờ. Nếu có không hoặc nhiều hơn một cột thỏa điều kiện, huấn luyện báo lỗi.
- Một chuỗi duy nhất, lấy mẫu đều. Hệ thống không resample và không điền khuyết giá trị mục tiêu.
- Các cột ngoại sinh (exogenous) trong `list_feature` phải biết trước tại thời điểm dự báo.
- Cột mục tiêu là số.

## Đặc trưng được tạo tự động

Đặc trưng chỉ dùng thông tin trong quá khứ (nhân quả), nên không rò rỉ dữ liệu tương lai:

| Đặc trưng | Mô tả |
|-----------|-------|
| Lag | Giá trị mục tiêu ở các bước trước |
| Rolling mean/std | Trung bình và độ lệch chuẩn trượt trên các giá trị mục tiêu trong quá khứ |

Chu kỳ mùa vụ được suy ra từ khoảng cách lấy mẫu trung vị:

| Khoảng cách lấy mẫu | Lag | Cửa sổ rolling |
|---------------------|-----|----------------|
| 1 ngày | 1, 7 | 7 |
| 1 giờ | 1, 24 | 24 |
| Khác | 1 | không có |

## Mô hình và đánh giá

- Mô hình: `Ridge`, `RandomForestRegressor`, `GradientBoostingRegressor` (`assets/time_series.yml`).
- Metric: `mse`, `mae`, `rmse` (mặc định), `r2`.
- Kiểm định chéo: `TimeSeriesSplit` cửa sổ mở rộng, 3 fold nếu dưới 200 dòng, 5 fold nếu từ 200 dòng. Chi tiết xem [Phương pháp khoa học](scientific_approach.md#3-chien-luoc-kiem-dinh-cheo-ba-bac-3-tier-cv).
- Phần tiền xử lý học được (điền khuyết, chuẩn hóa, one-hot) nằm trong `Pipeline` và được fit riêng cho từng fold.

## Dự đoán { #du-doan }

Mô hình được đóng gói thành `TimeSeriesForecaster`, giữ lại phần cuối của chuỗi huấn luyện. Khi dự đoán, bạn gửi các **mốc thời gian tương lai** cần dự báo, cùng giá trị ngoại sinh nếu có:

```json
{
  "data": [
    { "date": "2026-05-01" },
    { "date": "2026-05-02" }
  ]
}
```

Gửi tới [`POST /inference/models/{id}/predict`](backend_api.md#post-inferencemodelsidpredict). Hệ thống dự báo **đệ quy**: mỗi bước dự báo được đưa ngược lại làm lịch sử cho bước kế tiếp.

!!! warning "Giới hạn"
    - Mốc thời gian phải nằm sau mốc cuối của dữ liệu huấn luyện và đúng bội số của khoảng lấy mẫu.
    - Tối đa 365 bước sau mốc cuối của dữ liệu huấn luyện.
    - Độ chính xác giảm dần khi dự báo xa, vì sai số tích lũy qua các bước.
