# Cách đọc kết quả get_dataset_schema và chọn cột cho huấn luyện

Tài liệu này không nằm trong system prompt. Chỉ đọc khi cần chọn `target` /
`list_feature`, hoặc khi người dùng hỏi sâu về ý nghĩa các con số.

## Các trường trả về

| Trường | Ý nghĩa |
|---|---|
| `total_rows` | Tổng số dòng của cả dataset |
| `column_count` | Số cột |
| `target_candidates` | Các cột làm biến mục tiêu được, với `problem_type` đang xét |
| `columns[].can_be_target` | Cột này có làm mục tiêu được không |
| `columns[].python_type` | Kiểu suy ra từ dòng preview: `float`, `int`, `str` |
| `columns[].distinct_in_preview` | Số giá trị khác nhau, **tính trên 50 dòng đầu** |
| `columns[].missing_in_preview` | Số giá trị thiếu, **tính trên 50 dòng đầu** |
| `columns[].sample_values` | Tối đa 5 giá trị mẫu |
| `sample_rows` | 3 dòng dữ liệu đầu |

## Hiểu đúng `can_be_target`

`false` KHÔNG có nghĩa là cột vô dụng. Phần lớn cột `can_be_target: false`
chính là **đặc trưng đầu vào** tốt.

Backend đánh `false` trong các trường hợp:

- Tên cột khớp mẫu ID (`id`, `stt`, `no`, `key`, `uuid`, `*_id`, `ID_*`)
- Cột toàn giá trị rỗng, hoặc chỉ có một giá trị duy nhất
- Kiểu dữ liệu không hợp với `problem_type` đang xét — ví dụ cột số thực liên
  tục thì không làm target cho classification

Lưu ý quan trọng: cột bị đánh `false` vì **là ID** thì cũng không nên dùng làm
đặc trưng đầu vào — nó không mang thông tin dự đoán, chỉ gây nhiễu. Nhìn tên cột
để phân biệt hai trường hợp.

## Chọn cột cho huấn luyện

**Chọn `target`:**
1. Người dùng nói rõ cột nào → dùng cột đó, nhưng kiểm tra nó có trong
   `target_candidates` không. Không có thì báo lại kèm danh sách hợp lệ.
2. Người dùng không nói → nếu `target_candidates` chỉ có đúng một cột, dùng nó
   và nói rõ. Nếu nhiều hơn một, HỎI người dùng chọn.

**Chọn `list_feature`:**
1. Mặc định: mọi cột trừ `target`, và trừ các cột trông như ID.
2. Bỏ thêm cột có `missing_in_preview` cao — thiếu quá nửa số dòng preview thì
   nêu cho người dùng biết trước khi dùng.
3. Không bao giờ đưa `target` vào `list_feature`.

## Vì sao thống kê chỉ tính trên 50 dòng

Endpoint `/v2/auto/data` trả tối đa 50 dòng preview. Đọc cả dataset để thống kê
sẽ chậm và tốn bộ nhớ. Hệ quả: `distinct_in_preview` của một dataset lớn có thể
thấp hơn nhiều so với thực tế. Khi báo cáo con số này cho người dùng, luôn nói
rõ là tính trên preview.
