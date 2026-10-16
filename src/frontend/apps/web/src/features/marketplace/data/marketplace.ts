export type MarketplaceModelStatus = "ready" | "beta" | "internal";

export type MarketplaceModel = {
  id: string;
  slug: string;
  name: string;
  shortName: string;
  category: string;
  status: MarketplaceModelStatus;
  owner: string;
  useCase: string;
  shortDescription: string;
  description: string;
  tags: string[];
  inputs: string[];
  outputs: string[];
  metrics: {
    accuracy: string;
    latency: string;
    runs: string;
  };
  updatedAt: string;
  endpoint: string;
  features: string[];
  checklist: string[];
};

export const marketplaceCategories = [
  { id: "all", name: "Tất cả" },
  { id: "classification", name: "Phân loại" },
  { id: "regression", name: "Hồi quy" },
  { id: "vision", name: "Thị giác máy" },
  { id: "forecast", name: "Dự báo" },
];

export const marketplaceStatusLabels: Record<MarketplaceModelStatus, string> = {
  ready: "Sẵn sàng dùng",
  beta: "Đang thử nghiệm",
  internal: "Nội bộ",
};

export const marketplaceModels: MarketplaceModel[] = [
  {
    id: "tpl-glass-classification",
    slug: "phan-loai-glass-dataset",
    name: "Phân loại Glass Dataset",
    shortName: "GL",
    category: "classification",
    status: "ready",
    owner: "HAutoML Lab",
    useCase: "Phân loại vật liệu kính theo đặc trưng hóa học",
    shortDescription:
      "Quy trình AutoML mẫu cho dữ liệu dạng bảng, có sẵn tiền xử lý, huấn luyện và đánh giá.",
    description:
      "Template này tái sử dụng pipeline Glass Dataset hiện có trong hệ thống: kiểm tra schema, chuẩn hóa đặc trưng, huấn luyện nhiều thuật toán phân loại và chọn mô hình tốt nhất theo độ chính xác. Phù hợp để bắt đầu nhanh với dữ liệu bảng có nhãn phân loại.",
    tags: ["Bảng", "Phân loại", "KNN", "Auto train"],
    inputs: ["CSV", "Excel", "Bảng có nhãn"],
    outputs: ["Mô hình tốt nhất", "Báo cáo metric", "File dự đoán"],
    metrics: {
      accuracy: "92%",
      latency: "42ms",
      runs: "34",
    },
    updatedAt: "16/07/2026",
    endpoint: "/v2/automl/templates/glass-classification/run",
    features: [
      "Tự động nhận diện cột mục tiêu và cột đặc trưng",
      "So sánh KNN, RandomForest, XGBoost và Logistic Regression",
      "Xuất bảng metric và cấu hình mô hình tốt nhất",
      "Sẵn sàng triển khai endpoint dự đoán sau khi huấn luyện",
    ],
    checklist: [
      "Dataset có cột nhãn phân loại",
      "Tối thiểu 50 dòng dữ liệu hợp lệ",
      "Không cần cấu hình code thủ công",
    ],
  },
  {
    id: "tpl-credit-approval",
    slug: "duyet-tin-dung-tu-dong",
    name: "Duyệt tín dụng tự động",
    shortName: "CR",
    category: "classification",
    status: "ready",
    owner: "Risk Studio",
    useCase: "Ước lượng khả năng phê duyệt hồ sơ tín dụng",
    shortDescription:
      "Template phân loại nhị phân cho hồ sơ tín dụng, kèm giải thích đặc trưng và kiểm tra rủi ro.",
    description:
      "Quy trình này dành cho bài toán phê duyệt tín dụng dạng bảng. Hệ thống xử lý missing value, mã hóa biến phân loại, huấn luyện model nhị phân và tạo báo cáo các yếu tố ảnh hưởng mạnh nhất tới kết quả.",
    tags: ["Rủi ro", "Phân loại nhị phân", "Giải thích mô hình"],
    inputs: ["CSV", "Excel", "Dữ liệu khách hàng"],
    outputs: ["Điểm duyệt", "Xác suất rủi ro", "Báo cáo đặc trưng"],
    metrics: {
      accuracy: "89%",
      latency: "55ms",
      runs: "21",
    },
    updatedAt: "15/07/2026",
    endpoint: "/v2/automl/templates/credit-approval/run",
    features: [
      "Tiền xử lý biến số và biến phân loại",
      "Tự động chọn ngưỡng phân loại",
      "Báo cáo precision, recall, F1 và confusion matrix",
      "Gợi ý nhóm đặc trưng cần kiểm tra trước khi deploy",
    ],
    checklist: [
      "Có cột nhãn duyệt/từ chối",
      "Ẩn hoặc mã hóa dữ liệu định danh nhạy cảm",
      "Review báo cáo fairness trước khi triển khai",
    ],
  },
  {
    id: "tpl-medical-risk",
    slug: "du-doan-rui-ro-y-te",
    name: "Dự đoán rủi ro y tế",
    shortName: "MR",
    category: "classification",
    status: "beta",
    owner: "Clinical AI",
    useCase: "Phân tầng nguy cơ từ dữ liệu khám chữa bệnh",
    shortDescription:
      "Pipeline thử nghiệm cho dữ liệu y tế dạng bảng, ưu tiên recall và kiểm soát missing value.",
    description:
      "Template y tế tập trung vào việc phát hiện nhóm rủi ro cao. Quy trình ưu tiên recall, xử lý dữ liệu thiếu cẩn trọng và tách rõ phần đánh giá để người dùng review trước khi sử dụng thực tế.",
    tags: ["Y tế", "Recall", "Dữ liệu bảng"],
    inputs: ["CSV", "Excel", "Thông tin khám bệnh"],
    outputs: ["Mức rủi ro", "Bảng giải thích", "Chỉ số an toàn"],
    metrics: {
      accuracy: "84%",
      latency: "61ms",
      runs: "12",
    },
    updatedAt: "12/07/2026",
    endpoint: "/v2/automl/templates/medical-risk/run",
    features: [
      "Kiểm tra missing value theo nhóm trường",
      "Ưu tiên recall cho nhóm nguy cơ cao",
      "Tạo cảnh báo khi dữ liệu đầu vào thiếu trường quan trọng",
      "Không cho deploy trực tiếp khi chưa review",
    ],
    checklist: [
      "Chỉ dùng cho hỗ trợ quyết định, không thay thế chuyên môn y tế",
      "Cần kiểm tra quyền truy cập dữ liệu nhạy cảm",
      "Nên chạy validation trên dữ liệu nội bộ trước",
    ],
  },
  {
    id: "tpl-ocr-document",
    slug: "ocr-tai-lieu",
    name: "OCR tài liệu",
    shortName: "OC",
    category: "vision",
    status: "beta",
    owner: "Document AI",
    useCase: "Trích xuất văn bản và bảng từ ảnh/PDF",
    shortDescription:
      "Quy trình OCR cho ảnh và PDF, hỗ trợ xuất text, markdown và bảng dữ liệu.",
    description:
      "Template OCR giúp người dùng đưa ảnh/PDF vào hệ thống, trích xuất nội dung, giữ cấu trúc bảng cơ bản và chuyển kết quả sang định dạng có thể dùng cho bước dự đoán hoặc phân tích tiếp theo.",
    tags: ["OCR", "PDF", "Ảnh", "Trích xuất"],
    inputs: ["PNG", "JPG", "PDF"],
    outputs: ["Text", "Markdown", "CSV bảng"],
    metrics: {
      accuracy: "87%",
      latency: "1.8s",
      runs: "18",
    },
    updatedAt: "10/07/2026",
    endpoint: "/v2/automl/templates/ocr-document/run",
    features: [
      "Nhận ảnh hoặc PDF nhiều trang",
      "Giữ cấu trúc bảng ở mức cơ bản",
      "Xuất kết quả để dùng cho pipeline kế tiếp",
      "Có bước review thủ công trước khi lưu dữ liệu",
    ],
    checklist: [
      "File dưới 10MB",
      "Ảnh rõ chữ và ít nghiêng",
      "Cần kiểm tra lại bảng trước khi huấn luyện",
    ],
  },
  {
    id: "tpl-sales-forecast",
    slug: "du-bao-doanh-so",
    name: "Dự báo doanh số",
    shortName: "SF",
    category: "forecast",
    status: "internal",
    owner: "Forecast Lab",
    useCase: "Dự báo chuỗi thời gian theo ngày hoặc tháng",
    shortDescription:
      "Template dự báo cho dữ liệu thời gian, kèm kiểm tra mùa vụ và khoảng tin cậy.",
    description:
      "Quy trình dự báo doanh số xử lý dữ liệu thời gian, tự động phát hiện chu kỳ, tạo tập train/test theo thời gian và xuất dự báo kèm khoảng tin cậy cho từng mốc.",
    tags: ["Dự báo", "Chuỗi thời gian", "Doanh số"],
    inputs: ["CSV", "Excel", "Cột thời gian"],
    outputs: ["Dự báo", "Khoảng tin cậy", "Biểu đồ xu hướng"],
    metrics: {
      accuracy: "MAPE 9.8%",
      latency: "74ms",
      runs: "9",
    },
    updatedAt: "08/07/2026",
    endpoint: "/v2/automl/templates/sales-forecast/run",
    features: [
      "Kiểm tra khoảng thời gian bị thiếu",
      "Tách train/test theo trục thời gian",
      "Hiển thị xu hướng, mùa vụ và sai số",
      "Xuất dự báo theo ngày, tuần hoặc tháng",
    ],
    checklist: [
      "Cần cột thời gian hợp lệ",
      "Nên có ít nhất 3 chu kỳ dữ liệu",
      "Không trộn dữ liệu tương lai vào tập train",
    ],
  },
];

export const getMarketplaceModelBySlug = (slug: string) =>
  marketplaceModels.find((model) => model.slug === slug);
