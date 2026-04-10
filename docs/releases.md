# Lịch sử phát hành (Releases)

Trang này liệt kê tất cả các phiên bản của HAutoML đã được phát hành, cùng với các tính năng và cải tiến chính.

---

## v2.1.0 (05 Tháng 12, 2025) - Optima Search 🔍

**Cập nhập thuật toán tìm kiếm siêu tham số nâng cao**

### Tính năng chính

- ✅ **Advanced Hyperparameter Tuning**:
  - Genetic Algorithm (GA) - tìm kiếm dựa trên tiến hóa
  - Bayesian Optimization (BO) - tối ưu xác suất
- ✅ Cập nhật thuật toán quản lý các worker
- ✅ Tiền xử lý dữ liệu string cơ bản (basic string preprocessing)
- ✅ Cập nhật lại giao diện người dùng
- ✅ Cập nhật Dockerfile & Docker Compose

### Hotfixes

- 🐛 Fix lỗi không thể training trên page model (training page errors)

### Nhóm phát triển

- 🧑‍💼 Backend: @VanAnh-13, @xuanndong
- 🎨 Frontend: @vanhdz74
- 👮 PM: @DoManhQuang

### Downloads

- **GitHub**: [v2.1.0 Release](https://github.com/optivisionlab/AutoML/releases/tag/v2.1.0)

---

## v2.0.0 (19 Tháng 10, 2025) - MapReduce 1.0 🏗️

**Phiên bản được công bố tại ISINC 2026**

### Tính năng chính

- ✅ **Kiến trúc MapReduce 1.0**: Xây dựng kiến trúc xử lý phân tán (distributed processing)
- ✅ **MinIO Object Storage**: Lưu trữ dữ liệu, mô hình AI (tiến đến HCloud 1.0)
- ✅ **Async API**: Thêm xử lý bất đồng bộ cho các API
- ✅ **Admin Frontend**: Phân trang (pagination) cho quản trị viên

### Hotfixes & Tối ưu

- 🐛 Xử lý dữ liệu NULL trong quá trình huấn luyện
- ⚡ Tối ưu lại truy vấn dữ liệu trong quá trình huấn luyện

### Nhóm phát triển

- 🧑‍💼 Backend: @xuanndong
- 🎨 Frontend: @vanhdz74
- 👮 PM: @DoManhQuang

### Downloads

- **GitHub**: [v2.0.0 Release](https://github.com/optivisionlab/AutoML/releases/tag/v2.0.0)

### Tài liệu

- 📄 Bài báo: [ISINC 2026 Proceedings](https://doi.org/10.1007/978-981-95-1746-6_46)

---

## v1.1.2 (21 Tháng 6, 2025) - UI Update 🎨

**Cải tiến giao diện & bảo mật**

### Tính năng

- ✅ Frontend phân trang (pagination) - hiển thị theo trang
- ✅ Thanh loading (progress bar) - hiển thị tiến độ
- ✅ Thông tin về lab
- ✅ Chuẩn hóa Docker - có thể chạy trên localhost với docker-compose

### Hotfixes & Bảo mật

- 🔒 **Security Hotfix**: Ngăn chặn chiếm quyền admin qua API signup
- 🔒 Maintain lại class User với chức năng signup

### Nhóm phát triển

- 🔒 Security: @l3eol3eo
- 🎨 Frontend: @nguyenkhanh0310
- 🧑‍💼 Hotfix: @BuiHuyNam
- 👮 PM: @DoManhQuang

### Downloads

- **GitHub**: [v1.1.2 Release](https://github.com/optivisionlab/AutoML/releases/tag/v1.1.2)

---

## v1.1.1 (07 Tháng 6, 2025) - Quick Hotfix 🔧

**Sửa chữa nhanh cho vấn đề Kafka**

### Hotfixes

- 🐛 Fix lỗi gọi API push Kafka
- 🔧 Tạo Dockerfile và Docker Compose mới

### Nhóm phát triển

- 🧑‍💼 Hotfix: @DoManhQuang

### Downloads

- **GitHub**: [v1.1.1 Release](https://github.com/optivisionlab/AutoML/releases/tag/v1.1.1)

---

## v1.1.0 (03 Tháng 6, 2025) - Big Update 🚀

**Cập nhập lớn - Thêm khả năng triển khai mô hình**

### Tính năng chính

- ✅ **Model Deployment**: Triển khai mô hình với API cho end-user
- ✅ **API Inference**: API suy luận, kích hoạt và vô hiệu hóa mô hình
- ✅ **Docker Compose**: Nano, Toolkit, Kafka, MongoDB
- ✅ **Model Storage**: Lưu base64 model best vào MongoDB
- ✅ **Code Refactor**: Tái cấu trúc frontend, backend và fix lỗi

### Fixes

- 🐛 Fix lỗi không thể kết nối từ HAutoML Toolkit ↔ Kafka

### Nhóm phát triển

- 🛠️ Backend: @BuiHuyNam, @MinhSky17
- 🎨 Frontend: @nguyenkhanh0310
- 🗄️ Data: @chuanh1214
- 🔄 Automation: @CongBinh05
- 👮 PM: @DoManhQuang

### Downloads

- **GitHub**: [v1.1.0 Release](https://github.com/optivisionlab/AutoML/releases/tag/v1.1.0)

---

## v1.0.0 (17 Tháng 5, 2025) - Initial Release 🎉

**Phiên bản đầu tiên - Foundation**

### Các thành phần chính

- ✅ **HAutoML Nano**: No-code interface với Gradio
- ✅ **HAutoML Toolkits**: API server với FastAPI  
- ✅ **HAutoML Pro**: Giao diện thương mại

### Tính năng

- ✅ Huấn luyện No-Code với dữ liệu cá nhân (bài toán bảng)
- ✅ Quản trị thông tin dữ liệu cá nhân, tài khoản
- ✅ Bộ dữ liệu có sẵn
- ✅ Quản trị màn hình Admin
- ✅ Lịch sử huấn luyện mô hình

### Các mô hình hỗ trợ

- SVM (Support Vector Machine)
- Decision Tree
- Random Forest
- k-NN (k-Nearest Neighbors)
- Logistic Regression
- Gaussian Naive Bayes

### Nhóm phát triển

- 🛠️ Backend: @BuiHuyNam, @MinhSky17
- 🎨 Frontend: @nguyenkhanh0310
- 🗄️ Data: @chuanh1214
- 🔄 Automation: @CongBinh05
- 👮 PM: @DoManhQuang
- 🌟 Contributor: @MinhSky17

### Downloads

- **GitHub**: [v1.0.0 Release](https://github.com/optivisionlab/AutoML/releases/tag/v1.0.0)

---

## Hướng phát triển tương lai 🚀

Các tính năng dự kiến cho các phiên bản sắp tới:

### Sắp ra mắt (Planned)

- [ ] Hỗ trợ Deep Learning (TensorFlow, PyTorch)
- [ ] Time Series Forecasting
- [ ] Ensemble Methods nâng cao
- [ ] Auto Feature Engineering
- [ ] Explainability tools (SHAP, LIME)
- [ ] Hỗ trợ GPU acceleration
- [ ] Multi-language support
- [ ] Advanced monitoring & logging

### Đang xem xét (Under consideration)

- Federated Learning
- Reinforcement Learning support
- Mobile app
- GraphQL API
- Real-time collaboration features
- Advanced visualization tools

---

## Hỗ trợ các phiên bản (Version Support)

| Phiên bản | Trạng thái | Kết thúc hỗ trợ |
|-----------|-----------|-----------------|
| v2.0.0 | ✅ LTS (Long-term Support) | Oct 2027 |
| v1.0.0 | ❌ End-of-Life | Oct 2024 |

**LTS (Long-term Support)**: Nhận bản vá lỗi bảo mật và cập nhật quan trọng

---

## Cách nâng cấp

Để nâng cấp từ phiên bản cũ:

```bash
# Pull phiên bản mới nhất
git pull origin main

# Cập nhật dependencies
pip install -r requirements.txt

# Rebuild Docker images nếu cần
docker-compose down
docker-compose up -d --build
```

Xem [hướng dẫn nâng cấp](getting_started.md) để chi tiết hơn.

---

## Báo cáo lỗi & Yêu cầu tính năng

Nếu bạn tìm thấy lỗi hoặc muốn yêu cầu tính năng mới:

- 🐛 **Báo cáo lỗi**: [GitHub Issues](https://github.com/optivisionlab/AutoML/issues)
- 💡 **Yêu cầu tính năng**: [GitHub Discussions](https://github.com/optivisionlab/AutoML/discussions)
- 📧 **Email**: [optivisionlab@fit-haui.edu.vn](mailto:optivisionlab@fit-haui.edu.vn)

---

*Trang này được cập nhật lần cuối: 13 Tháng 10, 2025*
