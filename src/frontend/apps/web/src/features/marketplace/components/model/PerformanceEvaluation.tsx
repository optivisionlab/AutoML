export default function PerformanceEvaluation() {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Đánh giá hiệu năng</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="border rounded-lg p-4">
          <p className="text-sm text-gray-500">Độ chính xác</p>
          <p className="text-2xl font-semibold text-gray-900">98%</p>
        </div>

        <div className="border rounded-lg p-4">
          <p className="text-sm text-gray-500">Độ trễ trung bình</p>
          <p className="text-2xl font-semibold text-gray-900">1.8s</p>
        </div>

        <div className="border rounded-lg p-4">
          <p className="text-sm text-gray-500">Throughput</p>
          <p className="text-2xl font-semibold text-gray-900">120 req/min</p>
        </div>
      </div>

      <p className="text-gray-600 text-sm">
        * Số liệu dựa trên bài test nội bộ với tập dữ liệu tiêu chuẩn.
      </p>
    </div>
  );
}
