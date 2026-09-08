"use client";

import { useState } from "react";

export default function InferenceAPI({ description }: { description: string }) {
  const [showKey, setShowKey] = useState(false);

  const apiKey = "sk-test-********************";

  return (
    <div className="space-y-8">
      {/* Overview */}
      <section>
        <h2 className="text-xl font-semibold mb-3">Inference API</h2>
        <p className="text-gray-700 leading-relaxed">{description}</p>
      </section>

      {/* API Key */}
      <section className="border rounded-lg p-4 space-y-3">
        <h3 className="font-semibold">API Key</h3>

        <div className="flex items-center justify-between bg-gray-50 px-4 py-3 rounded">
          <code className="text-sm font-mono">
            {showKey ? apiKey : "••••••••••••••••••••••••"}
          </code>

          <button
            onClick={() => setShowKey(!showKey)}
            className="text-sm text-blue-600 hover:underline"
          >
            {showKey ? "Ẩn" : "Hiện"}
          </button>
        </div>

        <p className="text-xs text-gray-500">
          Không chia sẻ API Key của bạn cho người khác.
        </p>
      </section>

      {/* Endpoint */}
      <section className="border rounded-lg p-4 space-y-2">
        <h3 className="font-semibold">Endpoint</h3>
        <code className="block bg-gray-50 px-4 py-2 rounded text-sm">
          POST https://api.marketplace.ai/v1/models/deepseek-ocr/infer
        </code>
      </section>

      {/* Request Example */}
      <section className="space-y-2">
        <h3 className="font-semibold">Request Example</h3>

        <pre className="bg-gray-900 text-gray-100 text-sm rounded-lg p-4 overflow-auto">
          {`{
  "input": {
    "file_url": "https://example.com/invoice.pdf",
    "language": "vi"
  },
  "options": {
    "output_format": "markdown"
  }
}`}
        </pre>
      </section>

      {/* Response Example */}
      <section className="space-y-2">
        <h3 className="font-semibold">Response Example</h3>

        <pre className="bg-gray-900 text-green-200 text-sm rounded-lg p-4 overflow-auto">
          {`{
  "status": "success",
  "data": {
    "text": "HÓA ĐƠN GIÁ TRỊ GIA TĂNG...",
    "tables": [
      {
        "rows": 10,
        "columns": 5
      }
    ]
  },
  "latency_ms": 1820
}`}
        </pre>
      </section>
    </div>
  );
}
