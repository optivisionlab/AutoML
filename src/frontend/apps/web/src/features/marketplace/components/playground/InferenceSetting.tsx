"use client";

import Slider from "@/shared/components/common/Slider";
import { useState } from "react";

export default function InferenceSettings() {
  const [temperature, setTemperature] = useState(1);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [topP, setTopP] = useState(1);
  const [topK, setTopK] = useState(40);
  const [repeatPenalty, setRepeatPenalty] = useState(0);
  const [wordPenalty, setWordPenalty] = useState(0);
  const [streaming, setStreaming] = useState(false);

  const inputStyle =
    "w-full rounded-xl border border-slate-200 bg-slate-50/75 px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:bg-white dark:border-white/10 dark:bg-white/5 dark:text-white placeholder:text-slate-400";

  return (
    <aside className="w-full lg:w-80 shrink-0 rounded-2xl border border-slate-200/80 bg-white p-5 space-y-6 overflow-auto shadow-sm dark:border-white/10 dark:bg-[#0b121e]">
      <h2 className="text-lg font-bold text-slate-900 dark:text-white">Thiết lập</h2>

      {/* Model */}
      <div className="space-y-2">
        <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Mô hình AI</label>
        <select className={inputStyle}>
          <option>GPT-4 Turbo</option>
          <option>DeepSeek OCR</option>
        </select>
      </div>

      {/* System Prompt */}
      <div className="space-y-2">
        <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Prompt hệ thống</label>
        <textarea
          placeholder="Bạn là một trợ lý AI hữu ích..."
          className={`${inputStyle} h-24 resize-none`}
        />
      </div>

      {/* Streaming */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">Bật streaming</span>
        <input
          type="checkbox"
          checked={streaming}
          onChange={() => setStreaming(!streaming)}
          className="h-4 w-4 rounded accent-blue-600 cursor-pointer"
        />
      </div>

      {/* Parameters */}
      <div className="space-y-4">
        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">Tham số</h3>

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
        <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Chuỗi dừng</label>
        <input
          placeholder="###"
          className={inputStyle}
        />
      </div>

      {/* Advanced */}
      <details className="text-sm">
        <summary className="cursor-pointer font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition">
          Tinh chỉnh chuyên sâu
        </summary>
        <div className="mt-2 text-slate-500 dark:text-slate-400">
          Các tham số nâng cao sẽ được bổ sung.
        </div>
      </details>
    </aside>
  );
}
