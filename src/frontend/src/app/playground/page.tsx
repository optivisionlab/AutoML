"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import InferencingSettings from "@/components/marketplace/playground/InferenceSetting";
import { Button } from "@/components/ui/button";
import { LogOut } from "lucide-react";

const MODELS = [
  {
    id: "deepseek-ocr",
    name: "DeepSeek OCR",
    category: "Vision AI",
  },
  {
    id: "gpt-4-turbo",
    name: "GPT-4 Turbo",
    category: "LLM",
  },
];

export default function PlaygroundPage() {
  const searchParams = useSearchParams();
  const defaultModel = searchParams?.get("model");

  const [model, setModel] = useState(defaultModel);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState("");

  return (
    <div>
      <div className="flex items-center justify-between px-6 h-16 border-b">
        <h3
          onClick={() => window.location.replace("/market-place")}
          className="flex items-center text-lg font-semibold gap-2 cursor-pointer"
        >
          <LogOut />
          Môi trường thử nghiệm
        </h3>
        <div>
          <Button className="mr-2 bg-[#fff] text-[black]">Lấy API Key</Button>
          <Button className="bg-[blue] text-[#fff]">Xem mã</Button>
        </div>
      </div>
      <div className="h-[calc(100vh-64px)] flex p-10">
        {/* LEFT SIDEBAR */}
        <InferencingSettings />

        {/* RIGHT MAIN */}
        <main className="flex-1 bg-gray-50 p-6 overflow-auto">
          <h1 className="text-xl font-semibold mb-4">Playground</h1>

          <div className="grid grid-cols-1 xl:grid-cols-1 gap-6">
            {/* Input */}
            <div className="bg-white border rounded-lg p-4 space-y-4">
              <h3 className="font-semibold">Input</h3>

              <label className="block border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:bg-gray-50">
                <input
                  type="file"
                  accept=".png,.jpg,.jpeg,.pdf"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
                <p className="text-sm text-gray-600">
                  Kéo thả file hoặc click để upload
                </p>
              </label>

              {file && (
                <p className="text-sm text-gray-700">
                  File: <strong>{file.name}</strong>
                </p>
              )}

              <button
                onClick={() =>
                  setResult(
                    `OCR RESULT (${model})\n------------------\nHÓA ĐƠN GIÁ TRỊ GIA TĂNG...`
                  )
                }
                className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700"
              >
                Run inference
              </button>
            </div>

            {/* Output */}
            <div className="bg-white border rounded-lg p-4 space-y-4">
              <h3 className="font-semibold">Output</h3>

              {result ? (
                <pre className="bg-gray-900 text-green-200 text-sm rounded-lg p-4 h-[360px] overflow-auto">
                  {result}
                </pre>
              ) : (
                <div className="h-[360px] flex items-center justify-center text-sm text-gray-500 border rounded-lg">
                  Kết quả inference sẽ hiển thị tại đây
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
