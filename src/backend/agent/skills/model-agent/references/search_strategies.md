# Năm thuật toán tìm kiếm siêu tham số và cách chọn

Chỉ đọc khi cần tư vấn sâu cho người dùng về việc chọn thuật toán.

Nguồn: `src/modules/hpo/` và `SearchAlgorithm` trong `src/shared/constants.py`
của backend. Không gian tham số là các lưới khai trong `assets/classification.yml`
/ `regression.yml`; mọi thuật toán đều chỉ chọn TRONG lưới đó.

## grid_search — mặc định của agent

Duyệt **toàn bộ** tổ hợp tham số của lưới.

- **Ưu**: chắc chắn tìm được tổ hợp tốt nhất trong lưới. Kết quả lặp lại được,
  dễ giải thích — hợp cho báo cáo và nghiên cứu.
- **Nhược**: chi phí bằng `grid_size` (xem `list_models`) nhân số fold
  cross-validation. LogisticRegression có 1 × 2 × 4 × 2 = 16 tổ hợp.
- **Dùng khi**: lưới nhỏ, hoặc cần kết quả tái lập được.

## random_search

Lấy ngẫu nhiên tối đa 20 tổ hợp trong lưới.

- **Ưu**: rẻ và đoán trước được chi phí, dù lưới lớn tới đâu.
- **Nhược**: có thể bỏ sót tổ hợp tốt nhất; hai lần chạy ra khác nhau.
- **Dùng khi**: cần kết quả nhanh để so sánh sơ bộ.

## tpe_search — mặc định của backend khi config không ghi thuật toán

Tree-structured Parzen Estimator (Optuna), tối đa 30 lần thử: học từ các lần
thử trước để chọn tổ hợp tiếp theo.

- **Ưu**: thường đạt gần kết quả của grid với ít lần thử hơn nhiều.
- **Nhược**: ngẫu nhiên; khó giải thích vì sao dừng ở tổ hợp đó.
- **Dùng khi**: lưới lớn và thời gian eo hẹp - lựa chọn cân bằng nhất.

## bayesian_search

Gaussian Process (scikit-optimize), tối đa 25 lần thử.

- **Ưu / nhược**: giống tpe_search; mỗi lần thử tốn thêm thời gian dựng mô
  hình thay thế nên thường chậm hơn tpe một chút.
- **Dùng khi**: người dùng yêu cầu đích danh.

## genetic_algorithm

Tiến hoá quần thể 10 tổ hợp qua 5 thế hệ: chọn lọc, lai ghép, đột biến.

- **Ưu**: xử lý tốt lưới lớn và không liên tục.
- **Nhược**: số lần fit nhiều nhất trong nhóm thuật toán thông minh; ngẫu nhiên.
- **Dùng khi**: lưới rất lớn và có nhiều thời gian.

## Bảng chọn nhanh

| Tình huống | Nên chọn |
|---|---|
| Dataset nhỏ, muốn kết quả tái lập | `grid_search` |
| `max_time` dưới 15 phút, dataset vừa hoặc lớn | `tpe_search` |
| Chỉ cần so sánh sơ bộ thật nhanh | `random_search` |
| Lưới rất lớn, nhiều thời gian | `genetic_algorithm` |
| Người dùng không có ý kiến | `grid_search` |

## Về max_time

`max_time` (backend gọi là `timeout`) là ngân sách **toàn cục** cho cả job.
Các model được train **song song** trên các worker; hết giờ thì model nào chưa
xong bị huỷ và không có trong kết quả. Không model nào xong kịp thì job thất bại.

Hệ quả: `max_time` quá nhỏ thì bảng xếp hạng thiếu model (so số model trong
`orther_model_scores` với `list_models`), hoặc job thất bại hẳn. Khi thấy vậy,
nêu cho người dùng biết và đề nghị tăng `max_time` hoặc đổi sang `tpe_search`.
