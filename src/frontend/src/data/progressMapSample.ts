export type ProgressMapNodeStatus = "done" | "running" | "pending" | "failed";

export type ProgressMapNode = {
  id: string;
  label: string;
  subtitle?: string;
  status: ProgressMapNodeStatus;
  x: number;
  y: number;
  parentIds?: string[];
  branch?: string;
  startedAt?: string;
  elapsed?: string;
  params?: Record<string, string | number | boolean>;
  result?: Record<string, string | number | boolean>;
  log?: string[];
};

export type ProgressMapPipeline = {
  id: string;
  title: string;
  predictionColumn: string;
  rankBy: string;
  scoreMode: string;
  nodes: ProgressMapNode[];
};

export const progressMapSample: ProgressMapPipeline = {
  id: "hautoml-demo-progress",
  title: "Tiến trình xử lý mô hình",
  predictionColumn: "credit",
  rankBy: "ROC AUC",
  scoreMode: "Cross validation",
  nodes: [
    {
      id: "read-dataset",
      label: "Read dataset",
      subtitle: "Đọc dữ liệu",
      status: "done",
      x: 5,
      y: 50,
      elapsed: "18 giây",
      result: { rows: "12,450", columns: 28, missing_rate: "1.8%" },
      log: ["Nhận file CSV", "Kiểm tra schema", "Chuẩn hóa tên cột"],
    },
    {
      id: "split-holdout",
      label: "Split holdout data",
      subtitle: "Tách tập kiểm thử",
      status: "done",
      x: 16,
      y: 50,
      parentIds: ["read-dataset"],
      params: { test_size: 0.2, random_state: 42, stratify: true },
      result: { train_rows: "9,960", holdout_rows: "2,490" },
      log: ["Tạo holdout set", "Giữ phân phối nhãn mục tiêu"],
    },
    {
      id: "read-training",
      label: "Read training data",
      subtitle: "Nạp tập train",
      status: "done",
      x: 27,
      y: 50,
      parentIds: ["split-holdout"],
      elapsed: "9 giây",
      result: { memory: "148 MB", target: "credit" },
    },
    {
      id: "preprocess",
      label: "Preprocessing",
      subtitle: "Làm sạch dữ liệu",
      status: "done",
      x: 38,
      y: 50,
      parentIds: ["read-training"],
      params: { impute: "median/mode", scale_numeric: true, encode_category: "one-hot" },
      result: { generated_features: 42, dropped_columns: 2 },
      log: ["Điền missing value", "Encode categorical", "Scale numeric"],
    },
    {
      id: "model-selection",
      label: "Model selection",
      subtitle: "Chọn nhóm mô hình",
      status: "done",
      x: 49,
      y: 50,
      parentIds: ["preprocess"],
      params: { metric: "roc_auc", folds: 5, budget: "auto" },
      result: { candidates: 4 },
    },
    {
      id: "xgb",
      label: "XGB Classifier",
      subtitle: "Nhánh P1",
      status: "done",
      x: 60,
      y: 32,
      parentIds: ["model-selection"],
      branch: "Pipeline 1",
      params: { n_estimators: 500, max_depth: 6, learning_rate: 0.05 },
      result: { roc_auc: 0.793, f1: 0.781 },
    },
    {
      id: "gb",
      label: "Gradient Boosting",
      subtitle: "Nhánh P2",
      status: "done",
      x: 60,
      y: 68,
      parentIds: ["model-selection"],
      branch: "Pipeline 2",
      params: { n_estimators: 350, max_depth: 4, learning_rate: 0.08 },
      result: { roc_auc: 0.77, f1: 0.752 },
    },
    {
      id: "xgb-hpo-1",
      label: "Hyperparameter optimization",
      subtitle: "Tối ưu tham số",
      status: "done",
      x: 71,
      y: 32,
      parentIds: ["xgb"],
      branch: "Pipeline 3",
      params: { trials: 32, search: "bayesian", timeout: "25 phút" },
      result: { best_roc_auc: 0.793, selected: true },
    },
    {
      id: "gb-hpo-1",
      label: "Hyperparameter optimization",
      subtitle: "Tối ưu tham số",
      status: "done",
      x: 71,
      y: 68,
      parentIds: ["gb"],
      branch: "Pipeline 4",
      params: { trials: 24, search: "random", timeout: "18 phút" },
      result: { best_roc_auc: 0.77 },
    },
    {
      id: "xgb-fe",
      label: "Feature engineering",
      subtitle: "Sinh đặc trưng",
      status: "running",
      x: 82,
      y: 32,
      parentIds: ["xgb-hpo-1"],
      branch: "Pipeline 3",
      params: { interactions: true, polynomial_degree: 2, selection: "mutual_info" },
      result: { added_features: 12, elapsed: "3 phút" },
      log: ["Started cogito_running stage", "Testing feature interactions"],
    },
    {
      id: "gb-fe",
      label: "Feature engineering",
      subtitle: "Sinh đặc trưng",
      status: "done",
      x: 82,
      y: 68,
      parentIds: ["gb-hpo-1"],
      branch: "Pipeline 4",
      params: { interactions: false, selection: "tree_importance" },
      result: { added_features: 5 },
    },
    {
      id: "xgb-hpo-2",
      label: "Hyperparameter optimization",
      subtitle: "Tinh chỉnh lần 2",
      status: "pending",
      x: 93,
      y: 32,
      parentIds: ["xgb-fe"],
      branch: "Pipeline 3",
      params: { trials: 16, warm_start: true },
    },
    {
      id: "gb-hpo-2",
      label: "Hyperparameter optimization",
      subtitle: "Tinh chỉnh lần 2",
      status: "pending",
      x: 93,
      y: 68,
      parentIds: ["gb-fe"],
      branch: "Pipeline 4",
      params: { trials: 16, warm_start: true },
    },
  ],
};

