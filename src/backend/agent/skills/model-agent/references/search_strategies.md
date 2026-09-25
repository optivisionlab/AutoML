# Ba thuật toán tìm kiếm siêu tham số và cách chọn

Chỉ đọc khi cần tư vấn sâu cho người dùng về việc chọn thuật toán.

Nguồn: `automl/search/strategy/` và `automl/search/factory/search_strategy_factory.py`

## grid_search — mặc định

Duyệt **toàn bộ** tổ hợp tham số khai trong `assets/system_models/*.yml`.

- **Ưu**: chắc chắn tìm được tổ hợp tốt nhất trong không gian đã khai. Kết quả
  lặp lại được, dễ giải thích — hợp cho báo cáo và nghiên cứu.
- **Nhược**: chi phí tăng theo cấp số nhân với số tham số. RandomForest có
  `n_estimators` 3 giá trị × `max_features` 4 giá trị = 12 lần fit, mỗi lần còn
  nhân với số fold cross-validation.
- **Dùng khi**: không gian tham số nhỏ, hoặc cần kết quả tái lập được.

## bayesian_search

Dùng `scikit-optimize`: xây mô hình thay thế từ các lần thử trước để đoán vùng
tham số đáng thử tiếp.

- **Ưu**: tìm được kết quả tốt với ít lần fit hơn hẳn grid. Hợp khi mỗi lần
  huấn luyện tốn thời gian.
- **Nhược**: có yếu tố ngẫu nhiên nên hai lần chạy có thể ra khác nhau. Khó giải
  thích vì sao dừng ở tổ hợp đó.
- **Dùng khi**: không gian tham số lớn, hoặc `max_time` eo hẹp so với dataset.

## genetic_algorithm

Tiến hoá quần thể tổ hợp tham số qua các thế hệ: chọn lọc, lai ghép, đột biến.

- **Ưu**: xử lý tốt không gian tham số lớn và không liên tục.
- **Nhược**: cần nhiều lần fit nhất trong ba cách, do phải duy trì cả quần thể
  qua nhiều thế hệ. Cũng ngẫu nhiên như bayesian.
- **Dùng khi**: không gian rất lớn và có nhiều thời gian.

## Bảng chọn nhanh

| Tình huống | Nên chọn |
|---|---|
| Dataset nhỏ, muốn kết quả tái lập | `grid_search` |
| `max_time` dưới 15 phút, dataset vừa | `bayesian_search` |
| Không gian tham số rất lớn, nhiều thời gian | `genetic_algorithm` |
| Người dùng không có ý kiến | `grid_search` |

## Về max_time

`max_time` là ngân sách **toàn cục** cho cả job, không phải cho từng model.
Backend kiểm tra trước mỗi model; hết giờ thì bỏ qua các model còn lại và đánh
dấu `time_limit_reached`.

Hệ quả: `max_time` quá nhỏ thì job vẫn xong nhưng chỉ thử được vài model đầu,
kết quả không phản ánh đủ. Khi thấy `time_limit_reached: true` trong kết quả
job, hãy nêu cho người dùng biết và đề nghị tăng `max_time` rồi chạy lại.
