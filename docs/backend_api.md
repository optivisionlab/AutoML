# Tài liệu API Backend

Tài liệu này cung cấp một cái nhìn tổng quan chi tiết về các điểm cuối (endpoints) API có sẵn trong backend của HAutoML.

## URL cơ sở
Tất cả các điểm cuối đều tương đối so với URL cơ sở nơi backend đang chạy (ví dụ: `http://localhost:8000`).

---

## 1. Quản lý người dùng & Xác thực

### `POST /signup`
- **Mô tả**: Đăng ký một người dùng mới.
- **Request Body**: Một đối tượng JSON chứa thông tin chi tiết của người dùng (`username`, `email`, `password`, v.v.).
- **Response**: Một thông báo xác nhận.

### `POST /login`
- **Mô tả**: Đăng nhập cho người dùng.
- **Request Body**: `{"username": "your_username", "password": "your_password"}`
- **Response**: Một đối tượng JSON chứa thông tin người dùng và một access token.

### `GET /users`
- **Mô tả**: Lấy danh sách tất cả người dùng.
- **Response**: Một mảng JSON chứa các đối tượng người dùng.

### `GET /users/`
- **Mô tả**: Lấy thông tin một người dùng cụ thể bằng tên đăng nhập.
- **Tham số truy vấn (Query Parameter)**: `username` (string).
- **Response**: Một đối tượng JSON của người dùng được chỉ định.

### `PUT /update/{username}`
- **Mô tả**: Cập nhật thông tin hồ sơ của người dùng.
- **Tham số đường dẫn (Path Parameter)**: `username` (string).
- **Request Body**: Một đối tượng JSON chứa các trường cần cập nhật.
- **Response**: Một thông báo xác nhận.

### `DELETE /delete/{username}`
- **Mô tả**: Xóa một người dùng.
- **Tham số đường dẫn (Path Parameter)**: `username` (string).
- **Response**: Một thông báo xác nhận.

### `POST /change_password`
- **Mô tả**: Thay đổi mật khẩu của người dùng.
- **Tham số truy vấn (Query Parameter)**: `username` (string).
- **Request Body**: `{"password": "old_password", "new1_password": "new_password", "new2_password": "confirm_new_password"}`
- **Response**: Một thông báo xác nhận.

### `POST /forgot_password/{email}`
- **Mô tả**: Bắt đầu quy trình đặt lại mật khẩu cho một email nhất định.
- **Tham số đường dẫn (Path Parameter)**: `email` (string).
- **Response**: Một thông báo xác nhận.

### Xác thực với Google
- `GET /login_google`: Bắt đầu luồng đăng nhập Google OAuth2.
- `GET /auth`: URL callback để Google chuyển hướng đến sau khi xác thực.

---

## 2. Quản lý tập dữ liệu (Dataset)

### `POST /upload-dataset`
- **Mô tả**: Tải lên một tập dữ liệu mới.
- **Request Body**: `multipart/form-data` chứa:
    - `user_id` (string)
    - `data_name` (string)
    - `data_type` (string)
    - `file_data` (file)
- **Response**: Một đối tượng JSON chứa siêu dữ liệu của tập dữ liệu mới.

### `GET /get-list-data-user`
- **Mô tả**: Lấy danh sách tất cả các tập dữ liệu từ tất cả người dùng (dành cho quản trị viên).
- **Response**: Một mảng JSON chứa các đối tượng tập dữ liệu.

### `POST /get-list-data-by-userid`
- **Mô tả**: Lấy danh sách các tập dữ liệu cho một người dùng cụ thể.
- **Request Body**: `{"id": "user_id"}`
- **Response**: Một mảng JSON chứa các đối tượng tập dữ liệu.

### `POST /get-data-info`
- **Mô tả**: Lấy siêu dữ liệu cho một tập dữ liệu duy nhất.
- **Request Body**: `{"id": "dataset_id"}`
- **Response**: Một đối tượng JSON chứa siêu dữ liệu của tập dữ liệu.

### `PUT /update-dataset/{dataset_id}`
- **Mô tả**: Cập nhật siêu dữ liệu hoặc tệp của một tập dữ liệu.
- **Tham số đường dẫn (Path Parameter)**: `dataset_id` (string).
- **Request Body**: `multipart/form-data` (các trường tùy chọn: `data_name`, `data_type`, `file_data`).
- **Response**: Một thông báo thành công.

### `DELETE /delete-dataset/{dataset_id}`
- **Mô tả**: Xóa một tập dữ liệu.
- **Tham số đường dẫn (Path Parameter)**: `dataset_id` (string).
- **Response**: Một thông báo thành công.

---

## 3. Tác vụ AutoML & Huấn luyện

### `POST /train-from-requestbody-json/`
- **Mô tả**: Bắt đầu một công việc huấn luyện mới dựa trên cấu hình JSON.
- **Tham số truy vấn (Query Parameters)**: `userId` (string), `id_data` (string).
- **Request Body**: Một đối tượng JSON (`Item`) chứa cấu hình huấn luyện (features, target, models, metrics, v.v.).
- **Response**: Một đối tượng JSON chứa ID và trạng thái của công việc.

### `POST /get-list-job-by-userId`
- **Mô tả**: Lấy danh sách tất cả các công việc huấn luyện cho một người dùng cụ thể.
- **Request Body**: `{"user_id": "user_id"}`
- **Response**: Một mảng JSON chứa các đối tượng công việc.

### `POST /get-job-info`
- **Mô tả**: Lấy thông tin chi tiết cho một công việc huấn luyện duy nhất.
- **Request Body**: `{"id": "job_id"}`
- **Response**: Một đối tượng JSON chứa chi tiết công việc.

### `POST /inference-model/`
- **Mô tả**: Thực hiện suy luận (inference) bằng một mô hình đã được huấn luyện.
- **Tham số truy vấn (Query Parameter)**: `job_id` (string).
- **Request Body**: `multipart/form-data` chứa `file_data` (dữ liệu cần dự đoán).
- **Response**: Kết quả dự đoán.

### `POST /activate-model`
- **Mô tả**: Kích hoạt hoặc vô hiệu hóa một mô hình đã được huấn luyện để suy luận.
- **Tham số truy vấn (Query Parameters)**: `job_id` (string), `activate` (integer, 0 hoặc 1).
- **Response**: Một thông báo xác nhận.
