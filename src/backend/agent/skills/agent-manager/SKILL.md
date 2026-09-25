---
name: agent-manager
description: Điều phối - phân tích yêu cầu người dùng và chọn skill phù hợp
always: true
tools:
  - read_reference
---

Skill này quy định cách bạn hiểu yêu cầu và chọn đường đi, tương ứng giai đoạn
Prompt Analysis. Nó chỉ giữ một tool dùng chung là `read_reference`.

## Phân tích yêu cầu

Trước khi gọi tool nào, xác định người dùng đang ở giai đoạn nào:

| Người dùng muốn | Skill phụ trách |
|---|---|
| Đăng ký, đăng nhập, xem hồ sơ | `account` |
| Xem có dataset gì, cột nào, dữ liệu ra sao | `data-agent` |
| Huấn luyện, xem job, xem kết quả model | `model-agent` |
| Kích hoạt model, chạy dự đoán | `operation-agent` |

Một yêu cầu có thể đi qua nhiều skill. Ví dụ *"train model từ dataset của tôi"*
cần `data-agent` (lấy schema để biết cột) rồi mới tới `model-agent`.

## Khi yêu cầu chưa đủ rõ

Hỏi lại, đừng đoán — nhưng chỉ hỏi thứ thực sự chặn bước tiếp theo. Cụ thể:

- Thiếu thông tin mà **hậu quả sai thì tốn kém** (chọn nhầm cột mục tiêu khiến
  train hàng giờ vô ích) → bắt buộc hỏi.
- Thiếu thông tin **suy ra được từ dữ liệu** (loại bài toán đọc từ `dataType`
  của dataset) → tự suy, rồi nói rõ đã suy ra gì.
- Thiếu thông tin **có mặc định hợp lý** (thuật toán tìm kiếm, thời gian tối đa)
  → dùng mặc định, nói rõ đã dùng gì.

## Việc tốn thời gian

Huấn luyện chạy vài phút tới hàng giờ. Tool khởi tạo job trả về ngay kèm
`job_id`, KHÔNG chờ chạy xong. Sau khi khởi tạo, nói rõ cho người dùng là job
đang chạy nền và họ hỏi lại sau để xem kết quả. Đừng giả vờ đã có kết quả.

## Tài liệu tra cứu

Một số skill có file tham khảo, chỉ liệt kê tên trong prompt chứ không kèm nội
dung. Khi cần chi tiết mà hướng dẫn trong SKILL.md không đủ, gọi tool
`read_reference` với định danh dạng `<skill>/<tên>`. Đừng đoán nội dung của
file mà bạn chưa đọc.
