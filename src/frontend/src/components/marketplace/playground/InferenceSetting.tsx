"use client";

import Slider from "@/components/common/Slider";
import { useState } from "react";

export default function InferenceSettings() {
  const [temperature, setTemperature] = useState(1);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [topP, setTopP] = useState(1);
  const [topK, setTopK] = useState(40);
  const [repeatPenalty, setRepeatPenalty] = useState(0);
  const [wordPenalty, setWordPenalty] = useState(0);
  const [streaming, setStreaming] = useState(false);

  return (
    <aside className="w-80 border-l bg-white p-4 space-y-6 overflow-auto">
      <h2 className="text-lg font-semibold">Thiết lập</h2>

      {/* Model */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Mô hình AI</label>
        <select className="w-full border rounded-md px-3 py-2 text-sm">
          <option>GPT-4 Turbo</option>
          <option>DeepSeek OCR</option>
        </select>
      </div>

      {/* System Prompt */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Prompt hệ thống</label>
        <textarea
          placeholder="Bạn là một trợ lý AI hữu ích..."
          className="w-full border rounded-md px-3 py-2 text-sm h-24 resize-none"
        />
      </div>

      {/* Streaming */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Bật streaming</span>
        <input
          type="checkbox"
          checked={streaming}
          onChange={() => setStreaming(!streaming)}
          className="accent-blue-600"
        />
      </div>

      {/* Parameters */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-700">Tham số</h3>

        {/* Temperature */}
        <Slider
          label="Mức độ sáng tạo"
          value={temperature}
          min={0}
          max={2}
          step={0.1}
          onChange={setTemperature}
        />

        {/* Max Tokens */}
        <Slider
          label="Số token đầu ra tối đa"
          value={maxTokens}
          min={64}
          max={4096}
          step={64}
          onChange={setMaxTokens}
        />

        {/* Top P */}
        <Slider
          label="Top P"
          value={topP}
          min={0}
          max={1}
          step={0.05}
          onChange={setTopP}
        />

        {/* Top K */}
        <Slider
          label="Top K"
          value={topK}
          min={0}
          max={100}
          step={1}
          onChange={setTopK}
        />

        {/* Repeat */}
        <Slider
          label="Giới hạn lặp ý"
          value={repeatPenalty}
          min={0}
          max={2}
          step={0.1}
          onChange={setRepeatPenalty}
        />

        {/* Word */}
        <Slider
          label="Giới hạn lặp từ"
          value={wordPenalty}
          min={0}
          max={2}
          step={0.1}
          onChange={setWordPenalty}
        />
      </div>

      {/* Stop sequences */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Chuỗi dừng</label>
        <input
          placeholder="###"
          className="w-full border rounded-md px-3 py-2 text-sm"
        />
      </div>

      {/* Advanced */}
      <details className="text-sm">
        <summary className="cursor-pointer font-medium text-gray-700">
          Tinh chỉnh chuyên sâu
        </summary>
        <div className="mt-2 text-gray-600">
          Các tham số nâng cao sẽ được bổ sung.
        </div>
      </details>
    </aside>
  );
}
