---
name: account
description: Đăng ký, đăng nhập, xác thực email, xem và đổi hồ sơ người dùng
always: true
tools:
  - signup
  - login
  - get_me
  - logout
  - resend_verification_email
  - verify_email
  - dev_verify_account
---

## Quy trình đăng ký - làm đúng 4 bước, không gộp, không bỏ bước

**B1.** Nếu người dùng chưa đưa email và mật khẩu, HỎI hai thứ đó trước. Dừng
lại chờ họ trả lời, đừng tự bịa. Email là bắt buộc vì đó là thứ dùng để đăng
nhập sau này.

**B2.** Có email và mật khẩu rồi thì hỏi thêm: họ tên, giới tính, ngày sinh, số
điện thoại. Nói rõ đây là phần tuỳ chọn - họ có thể bảo "bỏ qua" và bạn sẽ tự
điền. Chỉ hỏi MỘT lần, họ bỏ qua thì đi tiếp ngay.

**B3.** Gọi tool `signup`. Backend bắt buộc đủ cả 7 trường nên phần nào người
dùng không cho, bạn tự điền giá trị hợp lệ rồi NÓI RÕ đã điền gì. Ràng buộc:
username tối thiểu 3 ký tự (suy từ email nếu họ không đặt), number tối thiểu 10
ký tự, date dạng dd/mm/yyyy.

**B4.** Đăng ký xong thì đăng nhập luôn cho người dùng, đừng bắt họ yêu cầu lại.
Cuối cùng xác nhận trạng thái đăng nhập, ví dụ bằng `get_me`.

Khi người dùng đã đưa sẵn đủ thông tin ngay từ đầu thì bỏ qua B1 và B2, vào
thẳng B3.

## Tài khoản chưa xác thực email

Tài khoản vừa đăng ký LUÔN ở trạng thái chưa xác thực, nên gọi `login` ngay sau
`signup` sẽ bị backend trả 403. Đây là hành vi đúng của hệ thống, không phải lỗi
cần thử lại.

Xử lý theo thứ tự ưu tiên:

1. Người dùng đưa token hoặc link xác thực → dùng `verify_email`. Xác thực xong
   là đăng nhập luôn, KHÔNG cần gọi `login` nữa.
2. Có tool `dev_verify_account` và đang thử nghiệm cục bộ → dùng nó với
   `user_id` lấy từ kết quả `signup`, rồi báo rõ đây là đường tắt chỉ dành cho
   môi trường phát triển.
3. Không có cách nào ở trên → dùng `resend_verification_email` rồi hướng dẫn
   người dùng mở email, lấy link đưa lại cho bạn.

Không tự bịa token xác thực. Token phải do người dùng cung cấp, hoặc do
`dev_verify_account` sinh ra.
