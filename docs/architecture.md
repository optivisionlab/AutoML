# Kiến trúc hệ thống

HAutoML được xây dựng theo kiến trúc **microservices**, gồm các thành phần sau:

- **Frontend**: SPA **Next.js (React)** + **TypeScript**, **Tailwind CSS**, **Radix UI**, **Redux Toolkit**
- **Backend**: **FastAPI** — API, business logic, điều phối AutoML
- **MongoDB**: Metadata người dùng, dataset, job
- **Apache Kafka**: Hàng đợi công việc huấn luyện
- **Master + Workers**: Scheduler và cluster huấn luyện phân tán
- **MinIO**: Lưu trữ dataset, cache và model

<div class="flow-heading">Luồng dữ liệu tổng thể</div>

--8<-- "flow-platform.html"

<div class="flow-heading">Thành phần hệ thống</div>

--8<-- "flow-architecture-grid.html"

Chi tiết từng bước huấn luyện: **[Quy trình HAutoML](hautoml-workflow.md)**.

<div class="flow-heading">Luồng huấn luyện chi tiết</div>

--8<-- "flow-training-pipeline.html"

## Công nghệ sử dụng

### Backend (Python)
- **Framework**: FastAPI
- **Web Server**: Uvicorn
- **Cơ sở dữ liệu**: MongoDB (Pymongo)
- **Học máy**: Scikit-learn, Pandas, Numpy
- **Hàng đợi**: Kafka (aiokafka)
- **Lưu trữ**: MinIO
- **Xác thực**: Authlib, PyJWT
- **Containerization**: Docker

### Frontend (TypeScript)
- **Framework**: Next.js (v.15), React (v.18)
- **Styling**: Tailwind CSS, Sass
- **UI**: Radix UI, Lucide React
- **Biểu đồ**: Recharts
- **Form**: React Hook Form, Zod
- **Auth**: NextAuth.js