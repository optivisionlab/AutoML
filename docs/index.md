# Chào mừng đến với HAutoML

**HAutoML** là nền tảng **tự động hóa học máy (Automated Machine Learning - AutoML)** mã nguồn mở được phát triển bởi [OptiVisionLab](https://optivisionlab.fit-haui.edu.vn/), Trường Công nghệ Thông tin và Truyền thông, Đại học Công nghiệp Hà Nội.

Nền tảng này tự động hóa toàn bộ quy trình xây dựng mô hình học máy - từ tiền xử lý dữ liệu, lựa chọn mô hình, tinh chỉnh siêu tham số, cho đến triển khai mô hình - cho phép người dùng dễ dàng tải dữ liệu lên và tự động tạo ra các mô hình học máy chất lượng cao **mà không cần kiến thức sâu về lập trình hay khoa học dữ liệu**.

## 🎯 Tầm nhìn

HAutoML được thiết kế để **dân chủ hóa học máy** - giúp bất cứ ai (dù là sinh viên, nhân viên kinh doanh, hoặc chuyên gia) có thể xây dựng các mô hình học máy hiệu quả mà không cần phải thành thạo các chi tiết kỹ thuật phức tạp.

## ✨ Tính năng chính

- **Quản lý người dùng & Xác thực**: Hệ thống đăng ký/đăng nhập an toàn với hỗ trợ OAuth 2.0 (Google)
- **Quản lý tập dữ liệu**: Giao diện trực quan để tải lên, xem, cập nhật và xóa các tập dữ liệu
- **Quy trình AutoML tự động**: 
  - 🔄 **Tiền xử lý dữ liệu thông minh**: Tự động phát hiện kiểu dữ liệu (số, phân loại, văn bản) và áp dụng các kỹ thuật xử lý phù hợp
  - 🔍 **Tìm kiếm siêu tham số**: Tự động tìm sự kết hợp siêu tham số tốt nhất (Grid Search, Random Search, ...)
  - 🎯 **Lựa chọn mô hình**: So sánh hiệu suất và chọn mô hình tối ưu
- **Xử lý công việc không đồng bộ**: Sử dụng Apache Kafka để xử lý các tác vụ huấn luyện song song (scalable)
- **Theo dõi công việc thời gian thực**: Giám sát trạng thái của các công việc huấn luyện
- **Triển khai & Suy luận (Inference)**: API đơn giản để đưa ra dự đoán trên dữ liệu mới
- **Giao diện hiện đại**: Được xây dựng bằng Next.js + TypeScript + Tailwind CSS

## 🔬 Phương pháp khoa học

HAutoML sử dụng các phương pháp khoa học hiện đại trong AutoML:

### Tiền xử lý dữ liệu thông minh
- Phát hiện tự động kiểu dữ liệu (numeric, categorical, text)
- Xử lý giá trị thiếu (imputation) phù hợp cho từng loại dữ liệu
- Chuẩn hóa (normalization) và mã hóa (encoding)
- Pipeline xử lý để tránh data leakage

### Tìm kiếm siêu tham số
- Grid Search và Random Search
- Kiểm định chéo k-fold (k-fold cross-validation)
- Đánh giá dựa trên multiple metrics

### Đánh giá mô hình
- **Phân loại**: Accuracy, Precision, Recall, F1-Score, Balanced Accuracy
- **Hồi quy**: MAE, MSE, RMSE, R²
- Xác thực generalization để tránh overfitting

Xem chi tiết tại [Phương pháp khoa học](scientific_approach.md).

## 🏗️ Kiến trúc hệ thống

HAutoML sử dụng kiến trúc **microservices** hiện đại:

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│                  Giao diện người dùng web                    │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP/REST
┌────────────────────────────▼────────────────────────────────┐
│                  Backend (FastAPI)                          │
│              API, Business Logic, Orchestration              │
└─┬────────────┬──────────────┬─────────────┬────────────────┘
  │            │              │             │
  │            │              │             │
┌─▼─┐    ┌────▼────┐    ┌────▼─────┐  ┌──▼───────┐
│   │    │ MongoDB  │    │ Apache    │  │  Minio   │
│   │    │          │    │ Kafka     │  │ (Storage)│
│   │    │(Database)│    │ (Queue)   │  │          │
│   │    └──────────┘    └─────┬────┘  └──────────┘
│   │                          │
│   └──────────────────────────┼───────────────────┐
│                              │                   │
└──────────────────────────────┼───────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │      Workers       │
                    │ (Process Training  │
                    │   Jobs from Kafka) │
                    └───────────────────┘
```

Xem chi tiết tại [Kiến trúc hệ thống](architecture.md).

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

- Giao diện người dùng: [http://localhost:3000](http://localhost:3000)

- Backend API: [http://localhost:8000](http://localhost:8000)


---

### Triển khai qua docker
> **Tự động hóa việc thiết lập và khởi chạy toàn bộ môi trường**
> 
> Tại thư mục: AutoML/
```bash
docker-compose up -d --build
```

> **Để dừng hệ thống**
```bash
docker-compose down
```

Chi tiết đầy đủ xem tại [Bắt đầu](getting_started.md).

## � Các phiên bản đã phát hành

| Phiên bản | Ngày | Đặc điểm chính | Trạng thái |
|----------|------|----------------|-----------|
| **v2.2.0** | 11/04/2026 | 🚀 Distributed Computing, Smart Scheduling, Account Classification | ✅ Latest |
| **v2.1.0** | 05/12/2025 | 🔍 Optima Search (GA, Bayesian Optimization) | ✅ Supported |
| **v2.0.0** | 19/10/2025 | 🏗️ MapReduce 1.0, MinIO, Async API | ✅ Stable |
| **v1.1.2** | 21/06/2025 | 🎨 UI Updates + Security Fixes | ⚠️ Supported |
| **v1.1.0** | 03/06/2025 | 🚀 Model Deployment & Inference API | ⚠️ Supported |
| **v1.0.0** | 17/05/2025 | 🎉 Initial Release | ❌ EOL |

**→ [Xem chi tiết tất cả các phiên bản](releases.md)**

## �📚 Tài liệu

| Trang | Nội dung |
|------|---------|
| [Bắt đầu](getting_started.md) | Hướng dẫn cài đặt và chạy hệ thống |
| [Kiến trúc](architecture.md) | Các thành phần hệ thống và công nghệ |
| [Phương pháp khoa học](scientific_approach.md) | Chi tiết về quá trình AutoML, tiền xử lý, tuning, v.v. |
| [Backend API](backend_api.md) | Tài liệu API endpoints |
| [Lịch sử phát hành](releases.md) | Các phiên bản đã phát hành và hướng phát triển |
| [Ghi nhận & Giấy phép](citation_license.md) | Cách trích dẫn và thông tin giấy phép |

## 👥 Người đóng góp

Chúng tôi xin chân thành cảm ơn tất cả những người đã đóng góp cho dự án HAutoML.

<a href="https://github.com/optivisionlab/AutoML/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=optivisionlab/AutoML" />
</a>

## 📖 Trích dẫn

### Bài báo khoa học (Recommended) 📄

Nếu bạn sử dụng HAutoML trong **nghiên cứu hoặc công bố công khai**, xin vui lòng trích dẫn bài báo sau:

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

**Full Citation:**
> Do, M. Q., Chu, T. A., Ngo, C. B., Bui, H. N., Nguyen, T. M. K., Nguyen, T. M., & Vu, V. T. (2026). HAutoML: Open-Source for Automated Machine Learning. In Proceedings of the Fifth International Conference on Intelligent Systems and Networks (pp. 415–423). Springer Nature Singapore. https://doi.org/10.1007/978-981-95-1746-6_46

### Phần mềm (Software Citation) 💻

Ngoài ra, bạn cũng có thể trích dẫn phần mềm trực tiếp:

```bibtex
@software{hautoml2024,
  title = {HAutoML: Open-source Automated Machine Learning Platform},
  author = {OptiVisionLab},
  url = {https://github.com/optivisionlab/AutoML},
  year = {2024},
  license = {CC BY-NC 4.0}
}
```

Xem chi tiết tại [Ghi nhận & Giấy phép](citation_license.md).
