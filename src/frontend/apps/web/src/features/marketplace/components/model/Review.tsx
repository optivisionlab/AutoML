export default function Review() {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Đánh giá</h2>

      <div className="border rounded-lg p-4 space-y-3">
        <div className="flex justify-between">
          <span className="font-medium">Nguyễn Văn A</span>
          <span className="text-sm text-gray-500">★★★★★</span>
        </div>
        <p className="text-gray-700 text-sm">
          Model OCR rất tốt, nhận dạng chính xác cả tài liệu scan mờ.
        </p>
      </div>

      <div className="border rounded-lg p-4 space-y-3">
        <div className="flex justify-between">
          <span className="font-medium">Trần Thị B</span>
          <span className="text-sm text-gray-500">★★★★☆</span>
        </div>
        <p className="text-gray-700 text-sm">
          Tốc độ xử lý nhanh, dễ tích hợp API.
        </p>
      </div>
    </div>
  );
}
