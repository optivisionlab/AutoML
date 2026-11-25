"""
Bộ đánh giá hành vi của hệ thống agent (chạy với LLM THẬT, backend GIẢ).

Mỗi kịch bản là vài tin nhắn người dùng + các điều kiện kiểm trên KẾT QUẢ CUỐI (câu trả lời, thẻ chờ xác nhận,
lệnh thật đã gửi tới backend giả, số lời gọi LLM / tool) - không ép agent đi đúng một chuỗi bước. Điều kiện chia
3 chiều: correctness (làm đúng việc), safety (không làm việc không được phép), efficiency (chi phí trong ngân
sách). Chạy: `python -m agent.evals --provider <tên> --model <model> --repeat 3` (xem __main__.py).
"""
