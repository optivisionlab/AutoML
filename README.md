# HAutoML - Nền tảng AutoML mã nguồn mở

[![Documentation Status](https://img.shields.io/badge/docs-latest-blue.svg)](https://optivisionlab.github.io/AutoML/docs/)

HAutoML là một dự án nghiên cứu khoa học mã nguồn mở được phát triển bởi OptiVisionLab. Đây là một nền tảng AutoML toàn diện cho phép người dùng dễ dàng xây dựng, huấn luyện và triển khai các mô hình học máy.

## 📚 Tài liệu

Tài liệu chi tiết về dự án, bao gồm kiến trúc, hướng dẫn cài đặt, và tài liệu API, có thể được tìm thấy tại trang web tài liệu của chúng tôi:

**[https://optivisionlab.github.io/AutoML/docs/](https://optivisionlab.github.io/AutoML/docs/)**

## 🚀 Bắt đầu nhanh

Cách đơn giản nhất để chạy toàn bộ hệ thống là sử dụng Docker. Vui lòng xem [hướng dẫn bắt đầu](https://optivisionlab.github.io/AutoML/docs) trong tài liệu của chúng tôi.

```bash
# Sao chép dự án
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML

# Cấu hình môi trường (xem chi tiết trong tài liệu)
cp src/backend/temp.config.yml src/backend/.config.yml
cp src/backend/temp.env src/backend/.env
cp src/frontend/temp.env src/frontend/.env

# Khởi chạy với Docker Compose
docker-compose up -d --build
```

## 👥 Người đóng góp

Chúng tôi xin chân thành cảm ơn tất cả những người đã đóng góp cho dự án HAutoML.

<a href="https://github.com/optivisionlab/AutoML/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=optivisionlab/AutoML" />
</a>

## ✍️ Trích dẫn & Giấy phép

Vui lòng xem mục [Ghi nhận & Giấy phép](https://optivisionlab.github.io/AutoML/docs/citation_license/) trong tài liệu của chúng tôi để biết thông tin chi tiết về cách trích dẫn dự án và giấy phép sử dụng.
