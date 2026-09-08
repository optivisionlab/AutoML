/**
 * =========================================================================
 * CẤU HÌNH QUY TRÌNH HAUTOML (PRODUCTION PIPELINE CONFIG)
 * =========================================================================
 * 
 * HƯỚNG DẪN CẬP NHẬT KHI BẠN CÓ VIDEO:
 * 1. Đặt file video của bạn vào thư mục `public/` (Ví dụ: `public/videos/hautoml-demo.mp4`).
 * 2. Cập nhật biến `DEMO_VIDEO_URL` bên dưới thành đường dẫn tương đối (Ví dụ: `"/videos/hautoml-demo.mp4"`).
 * 3. Chỉnh sửa `startTime` (giây bắt đầu) và `endTime` (giây kết thúc) cho từng bước.
 * 4. Nếu video có nhiều bước hơn (04, 05...), chỉ cần thêm đối tượng mới vào mảng `PIPELINE_STEPS`.
 */

export interface PipelineStep {
  id: string;
  stepNumber: string;
  titleKey: string;
  defaultTitle: string;
  descKey: string;
  defaultDesc: string;
  badge: string;
  startTime: number; // Đơn vị: giây (seconds)
  endTime: number;   // Đơn vị: giây (seconds)
  previewImage?: string;
  visualType: "model_selection" | "distributed_training" | "api_deployment";
}

/**
 * Đường dẫn video demo (mp4/webm).
 * Để trống `""` nếu chưa có video thật (hệ thống sẽ tự động chạy giao diện mô phỏng AI cực đẹp).
 * Khi có video, chỉ cần điền ví dụ: `"/videos/hautoml_pipeline.mp4"`
 */
export const DEMO_VIDEO_URL = "/videos/hautoml-pipeline.mp4";

/**
 * Danh sách 4 bước chuẩn hóa theo video thực tế HAutoML:
 * - Bước 1: Tải dữ liệu lên (00:00 – 00:08)
 * - Bước 2: Chọn mục tiêu và biến tác động (00:08 – 00:18)
 * - Bước 3: HAutoML tự động huấn luyện (00:18 – 00:27)
 * - Bước 4: Kích hoạt triển khai mô hình (00:27 – 00:31)
 */
export const PIPELINE_STEPS: PipelineStep[] = [
  {
    id: "step-1",
    stepNumber: "01",
    titleKey: "step1Title",
    defaultTitle: "Tải dữ liệu lên",
    descKey: "step1Desc",
    defaultDesc:
      "Vào mục Bộ dữ liệu của tôi, chọn tải lên tệp bảng dữ liệu (ENB2012_data.xlsx) và xác nhận lưu.",
    badge: "Tải dữ liệu • ENB2012_data.xlsx",
    startTime: 0,
    endTime: 8,
    visualType: "model_selection",
  },
  {
    id: "step-2",
    stepNumber: "02",
    titleKey: "step2Title",
    defaultTitle: "Chọn mục tiêu và biến tác động",
    descKey: "step2Desc",
    defaultDesc:
      "Chọn bài toán Hồi quy, thiết lập biến mục tiêu Target (Y1) cùng các biến đặc trưng đầu vào Features (X1 đến X8), sau đó bấm bắt đầu.",
    badge: "Cấu hình Target & Features",
    startTime: 8,
    endTime: 18,
    visualType: "distributed_training",
  },
  {
    id: "step-3",
    stepNumber: "03",
    titleKey: "step3Title",
    defaultTitle: "HAutoML tự động huấn luyện",
    descKey: "step3Desc",
    defaultDesc:
      "Hệ thống tự động chạy quy trình (pipeline), tối ưu tham số và so sánh hiệu suất giữa các thuật toán qua bảng xếp hạng cùng biểu đồ trực quan.",
    badge: "Huấn luyện & So sánh mô hình",
    startTime: 18,
    endTime: 27,
    visualType: "distributed_training",
  },
  {
    id: "step-4",
    stepNumber: "04",
    titleKey: "step4Title",
    defaultTitle: "Kích hoạt triển khai mô hình",
    descKey: "step4Desc",
    defaultDesc:
      "Chọn mô hình có kết quả tốt nhất để triển khai và nhấn Kích hoạt để nhận đường dẫn API/mã tích hợp.",
    badge: "Kích hoạt & Triển khai API",
    startTime: 27,
    endTime: 31.6,
    visualType: "api_deployment",
  },
];
