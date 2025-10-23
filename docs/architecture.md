# Kiến trúc hệ thống

HAutoML được xây dựng theo kiến trúc microservices, bao gồm các thành phần chính sau:

- **Frontend**: Một ứng dụng Single Page Application (SPA) được xây dựng bằng **Next.js (React)** và **TypeScript**. Giao diện người dùng được thiết kế với **Tailwind CSS** và các thành phần từ **Radix UI**. Quản lý trạng thái bằng **Redux Toolkit**.
- **Backend**: Một hệ thống API mạnh mẽ được xây dựng bằng **Python** với framework **FastAPI**. Backend chịu trách nhiệm xử lý logic nghiệp vụ, xác thực người dùng và điều phối các công việc AutoML.
- **Cơ sở dữ liệu**: Sử dụng **MongoDB** để lưu trữ thông tin người dùng, siêu dữ liệu về các tập dữ liệu và các công việc huấn luyện.
- **Hàng đợi tin nhắn (Message Queue)**: **Apache Kafka** được sử dụng để quản lý hàng đợi các công việc huấn luyện. Khi người dùng yêu cầu huấn luyện một mô hình, một tin nhắn sẽ được gửi đến Kafka.
- **Workers**: Các tiến trình Python độc lập (consumers) lắng nghe các tin nhắn từ Kafka. Mỗi worker sẽ nhận một công việc huấn luyện, thực hiện nó, và cập nhật kết quả vào cơ sở dữ liệu.
- **Lưu trữ đối tượng (Object Storage)**: **Minio** được sử dụng để lưu trữ các tệp dữ liệu lớn (datasets) và các mô hình đã được huấn luyện.

*(Sơ đồ kiến trúc sẽ được cập nhật ở đây)*

## Công nghệ sử dụng

### Backend (Python)
- **Framework**: FastAPI
- **Web Server**: Uvicorn
- **Cơ sở dữ liệu**: MongoDB (với Pymongo)
- **Học máy**: Scikit-learn, Pandas, Numpy
- **Hàng đợi tin nhắn**: Kafka (với kafka-python, aiokafka)
- **Lưu trữ đối tượng**: Minio
- **Xác thực**: Authlib, PyJWT
- **Containerization**: Docker

### Frontend (TypeScript)
- **Framework**: Next.js (v.15), React (v.18)
- **Ngôn ngữ**: TypeScript
- **Quản lý trạng thái**: Redux Toolkit
- **Styling**: Tailwind CSS, Sass
- **Thành phần UI**: Radix UI, Lucide React
- **Biểu đồ**: Recharts
- **Xử lý biểu mẫu**: React Hook Form, Zod
- **Client API**: Axios
- **Xác thực**: NextAuth.js
- **Containerization**: Docker
