# Bắt đầu

Cách đơn giản và được khuyến nghị nhất để chạy toàn bộ hệ thống HAutoML là sử dụng Docker.

## Yêu cầu
- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Chạy bằng Docker Compose

1.  **Sao chép (Clone) dự án:**
    ```bash
    git clone https://github.com/optivisionlab/AutoML.git
    cd AutoML
    ```

2.  **Cấu hình môi trường:**
    Hệ thống yêu cầu một số tệp cấu hình. Hãy sao chép từ các tệp mẫu:
    ```bash
    # Cấu hình cho Backend
    cp src/backend/temp.config.yml src/backend/.config.yml
    cp src/backend/temp.env src/backend/.env

    # Cấu hình cho Frontend
    cp src/frontend/temp.env src/frontend/.env
    ```
    Mở các tệp `.config.yml` và `.env` vừa tạo để tùy chỉnh các thông số nếu cần (ví dụ: port, thông tin đăng nhập Google OAuth, endpoint của Minio).

3.  **Khởi chạy hệ thống:**
    Sử dụng Docker Compose để build và chạy tất cả các dịch vụ (frontend, backend, database, kafka, minio, workers):
    ```bash
    docker-compose up -d --build
    ```
    Cờ `-d` sẽ chạy các container ở chế độ nền (detached mode). Cờ `--build` sẽ buộc Docker build lại các image nếu có thay đổi.

4.  **Truy cập ứng dụng:**
    - **Frontend**: `http://localhost:3000` (hoặc port bạn đã cấu hình trong `src/frontend/.env`)
    - **Backend API**: `http://localhost:8000` (hoặc port bạn đã cấu hình trong `src/backend/.env`)

## Dừng hệ thống
Để dừng tất cả các container, chạy lệnh sau trong thư mục gốc của dự án:
```bash
docker-compose down
```

---

## Xem tài liệu trên máy Local

Trước khi triển khai, bạn có thể xem trước trang web tài liệu trên máy tính của mình.

1.  **Cài đặt các gói cần thiết (chỉ cần làm một lần):**
    Mở terminal và chạy lệnh sau để cài đặt MkDocs và theme Material:
    ```bash
    pip install mkdocs-material
    ```

2.  **Chạy máy chủ phát triển:**
    Từ thư mục gốc của dự án, chạy lệnh:
    ```bash
    mkdocs serve
    ```

3.  **Xem trang tài liệu:**
    Mở trình duyệt và truy cập vào địa chỉ `http://127.0.0.1:8000`. Máy chủ này có tính năng tự động tải lại (live-reloading), có nghĩa là bất kỳ khi nào bạn lưu một thay đổi trong các tệp Markdown, trang web trên trình duyệt sẽ tự động cập nhật.
