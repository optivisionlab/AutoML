# HAutoML - Nền tảng AutoML mã nguồn mở

[![Documentation Status](https://img.shields.io/badge/docs-latest-blue.svg)](https://optivisionlab.github.io/AutoML/docs/)

**HAutoML** là một nền tảng tự động hóa học máy (Automated Machine Learning - AutoML) mã nguồn mở được phát triển bởi [OptiVisionLab](https://optivisionlab.fit-haui.edu.vn/) tại Trường Công nghệ Thông tin và Truyền thông, Đại học Công nghiệp Hà Nội.

Đây là một hệ thống toàn diện cho phép người dùng (bao gồm cả những người không có chuyên môn sâu về học máy) dễ dàng tải lên dữ liệu, tự động hóa toàn bộ quy trình xây dựng mô hình học máy (từ tiền xử lý dữ liệu, lựa chọn mô hình, tinh chỉnh siêu tham số) và triển khai mô hình để đưa ra dự đoán trên dữ liệu mới.

## 📋 Tóm tắt khoa học

HAutoML là một hệ thống AutoML phân tán, được thiết kế để **tự động hóa toàn bộ pipeline học máy** từ tiền xử lý dữ liệu đến triển khai mô hình. Hệ thống sử dụng:

- **Kỹ thuật tiền xử lý thông minh**: Tự động phát hiện kiểu dữ liệu (số học, phân loại, văn bản) và áp dụng các kỹ thuật xử lý thích hợp (chuẩn hóa, mã hóa one-hot, TF-IDF, điền giá trị thiếu).
- **Tìm kiếm siêu tham số**: Sử dụng các chiến lược tối ưu hóa (Grid Search, Random Search, hoặc các phương pháp tiên tiến) để tìm sự kết hợp siêu tham số tốt nhất cho mô hình.
- **Xử lý công việc không đồng bộ**: Tích hợp Apache Kafka để quản lý hàng đợi công việc, cho phép xử lý các tác vụ huấn luyện nặng nề song song trên nhiều worker.
- **Kiến trúc microservices**: Tách biệt rõ ràng giữa frontend (giao diện người dùng), backend (logic xử lý), workers (huấn luyện mô hình), và các dịch vụ hỗ trợ (cơ sở dữ liệu, lưu trữ, hàng đợi).

Hệ thống hỗ trợ cả **bài toán phân loại (Classification)** lẫn **bài toán hồi quy (Regression)**, với các chỉ số hiệu suất phù hợp cho từng loại bài toán.

## ✨ Tính năng chính

| Tính năng | Mô tả |
|-----------|--------|
| ✅ **Quản lý người dùng & Xác thực** | Hệ thống đăng ký/đăng nhập an toàn với hỗ trợ OAuth 2.0 (Google) và phân loại tài khoản |
| ✅ **Quản lý tập dữ liệu** | Giao diện trực quan để tải lên, xem, cập nhật và xóa dữ liệu |
| ✅ **Tiền xử lý dữ liệu thông minh** | Tự động phát hiện kiểu dữ liệu, điền giá trị thiếu, chuẩn hóa |
| ✅ **Tìm kiếm siêu tham số tự động** | Grid Search, Random Search, BO, GA, Cross-Validation |
| ✅ **Lựa chọn mô hình tối ưu** | So sánh và chọn mô hình tốt nhất dựa trên hiệu suất |
| ✅ **Xử lý công việc không đồng bộ** | Apache Kafka cho xử lý các tác vụ huấn luyện song song |
| ✅ **Distributed Computing** | Kiến trúc MapReduce nâng cao, song song hóa dữ liệu theo mô hình trên nhiều máy |
| ✅ **Smart Scheduling** | Lập lịch thông minh dựa trên Locality + Capacity + Cost + băng thông mạng |
| ✅ **Fault Tolerance** | Tự động thử lại công việc, quản lý timeout, giám sát nền tảng |
| ✅ **Theo dõi công việc thời gian thực** | Giám sát trạng thái các công việc huấn luyện |
| ✅ **Triển khai & Suy luận (Inference)** | API đơn giản để đưa ra dự đoán trên dữ liệu mới |
| ✅ **Giao diện hiện đại** | Xây dựng bằng Next.js + TypeScript + Tailwind CSS, bao gồm Marketplace Interface |

## 📚 Tài liệu

Tài liệu chi tiết về dự án, bao gồm kiến trúc, hướng dẫn cài đặt, phương pháp khoa học, và tài liệu API, có thể được tìm thấy tại trang web tài liệu của chúng tôi:

**[https://optivisionlab.github.io/AutoML/docs/](https://optivisionlab.github.io/AutoML/docs/)**

## 🚀 Bắt đầu nhanh

### Cách đơn giản nhất: Sử dụng Docker

Cách được khuyến nghị nhất để chạy toàn bộ hệ thống là sử dụng Docker và Docker Compose.

**Yêu cầu**: [Docker](https://www.docker.com/get-started) và [Docker Compose](https://docs.docker.com/compose/install/)

---

### Triển khai từ mã nguồn

**1. Tải mã nguồn dự án**
```bash
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML
```

**2. Cấu hình môi trường**
```bash
cp src/backend/temp.env src/backend/.env
cp src/frontend/temp.env src/frontend/.env
```

**3. Khởi chạy các thành phần hệ thống**
> **Backend & Worker cluster**
> 
> Tại thư mục: AutoML/src/backend
```bash
pip install -r requirements.txt # Cài đặt các thư viện cần thiết

python app.py # Khởi chạỵ API server
python -m cluster.worker # Kích hoạt worker xử lý tác vụ
```

> **Frontend**
> 
> Tại thư mục: AutoML/src/frontend
```bash
npm install # Cài đặt các gói phụ thuộc
npm run dev # Chạy ứng dụng ở chế độ phát triển
```

**4. Địa chỉ truy cập**
- Giao diện người dùng: http://localhost:3000
- Backend API: http://localhost:8000


---

### Triển khai qua docker
> **Tự động hóa việc thiết lập và khởi chạy toàn bộ môi trường**
> 
> Tại thư mục: AutoML/
```bash
# Hệ thống có dùng MinIO, yêu cầu thông tin tài khoản mật khẩu đồng nhất giữa .env và docker-compose.yaml
docker-compose up -d --build
```

> **Để dừng hệ thống**
```bash
docker-compose down
```

Chi tiết đầy đủ xem tại [Hướng dẫn bắt đầu](https://optivisionlab.github.io/AutoML/docs/getting_started/) trong tài liệu.

## 🏗️ Kiến trúc hệ thống

HAutoML được xây dựng theo kiến trúc **microservices**, bao gồm:

| Thành phần | Công nghệ | Vai trò |
|-----------|-----------|--------|
| **Frontend** | Next.js, React, TypeScript, Tailwind CSS | Giao diện người dùng SPA |
| **Backend** | FastAPI, Python | API REST, logic xử lý, điều phối công việc |
| **Cơ sở dữ liệu** | MongoDB | Lưu trữ thông tin người dùng, metadata, kết quả huấn luyện |
| **Hàng đợi tin nhắn** | Apache Kafka | Quản lý hàng đợi công việc huấn luyện |
| **Workers** | Python | Tiến trình độc lập xử lý công việc huấn luyện |
| **Lưu trữ đối tượng** | Minio | Lưu trữ datasets và mô hình đã huấn luyện |

Chi tiết về kiến trúc xem tại [Kiến trúc hệ thống](https://optivisionlab.github.io/AutoML/docs/architecture/) và [Phương pháp khoa học](https://optivisionlab.github.io/AutoML/docs/scientific_approach/).

## � Các phiên bản đã phát hành

| Phiên bản | Ngày | Đặc điểm chính | Trạng thái |
|----------|------|----------------|-----------|
| **v2.2.0** | 11/04/2026 | 🚀 Distributed Computing, Smart Scheduling, Account Classification | ✅ Latest |
| **v2.1.0** | 05/12/2025 | 🔍 Optima Search (GA, Bayesian Optimization) | ✅ Supported |
| **v2.0.0** | 19/10/2025 | 🏗️ MapReduce 1.0, MinIO, Async API | ✅ Stable |
| **v1.1.2** | 21/06/2025 | 🎨 UI Updates + Security Fixes | ⚠️ Supported |
| **v1.1.0** | 03/06/2025 | 🚀 Model Deployment & Inference API | ⚠️ Supported |
| **v1.0.0** | 17/05/2025 | 🎉 Initial Release | ❌ EOL |

**→ [Xem chi tiết tất cả các phiên bản](https://optivisionlab.github.io/AutoML/docs/releases/)**

## �👥 Người đóng góp

Chúng tôi xin chân thành cảm ơn tất cả những người đã đóng góp cho dự án HAutoML.

<a href="https://github.com/optivisionlab/AutoML/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=optivisionlab/AutoML" />
</a>

## ✍️ Trích dẫn & Giấy phép

Nếu bạn sử dụng HAutoML trong nghiên cứu hoặc dự án của mình, xin hãy trích dẫn bài báo sau:

### BibTeX Citation

```bibtex
@InProceedings{Do2026HAutoML,
  author="Do, Manh Quang
  and Chu, Thi Anh
  and Ngo, Cong Binh
  and Bui, Huy Nam
  and Nguyen, Thi My Khanh
  and Nguyen, Thi Minh
  and Vu, Viet Thang",
  editor="Thi Dieu Linh, Nguyen
  and Yu, Shiqi
  and Selamat, Ali
  and Tran, Duc-Tan",
  title="HAutoML: Open-Source for Automated Machine Learning",
  booktitle="Proceedings of the Fifth International Conference on Intelligent Systems and Networks",
  year="2026",
  publisher="Springer Nature Singapore",
  address="Singapore",
  pages="415--423",
  isbn="978-981-95-1746-6"
}
```

### Thông tin chi tiết

**Bài báo**: Do, M. Q., Chu, T. A., Ngo, C. B., Bui, H. N., Nguyen, T. M. K., Nguyen, T. M., & Vu, V. T. (2026). HAutoML: Open-Source for Automated Machine Learning. In Proceedings of the Fifth International Conference on Intelligent Systems and Networks (pp. 415–423). Springer Nature Singapore.

**DOI**: 10.1007/978-981-95-1746-6_46

**Mã nguồn**: https://github.com/optivisionlab/AutoML

---

Vui lòng xem mục [Ghi nhận & Giấy phép](https://optivisionlab.github.io/AutoML/docs/citation_license/) trong tài liệu của chúng tôi để biết thông tin chi tiết về giấy phép sử dụng.
