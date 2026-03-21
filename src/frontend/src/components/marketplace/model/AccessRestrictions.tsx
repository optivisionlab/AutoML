export default function AccessRestrictions() {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Giới hạn truy cập</h2>

      <div className="border rounded-lg divide-y">
        <div className="flex justify-between px-4 py-3 text-sm">
          <span className="text-gray-600">Xác thực</span>
          <span className="font-medium">API Key</span>
        </div>

        <div className="flex justify-between px-4 py-3 text-sm">
          <span className="text-gray-600">Rate limit</span>
          <span className="font-medium">60 req / phút</span>
        </div>

        <div className="flex justify-between px-4 py-3 text-sm">
          <span className="text-gray-600">Dung lượng file</span>
          <span className="font-medium">≤ 10MB</span>
        </div>

        <div className="flex justify-between px-4 py-3 text-sm">
          <span className="text-gray-600">Concurrent requests</span>
          <span className="font-medium">5</span>
        </div>
      </div>
    </div>
  );
}
