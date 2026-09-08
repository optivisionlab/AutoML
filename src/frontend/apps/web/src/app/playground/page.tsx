"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import InferencingSettings from "@/features/marketplace/components/playground/InferenceSetting";
import { Button } from "@/shared/components/ui/button";
import { LogOut } from "lucide-react";

export default function PlaygroundPage() {
  const searchParams = useSearchParams();
  const defaultModel = searchParams?.get("model");

  const [model] = useState(defaultModel);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState("");

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-transparent text-slate-900 dark:text-white">
      <div className="flex items-center justify-between px-6 h-16 border-b border-slate-200/80 dark:border-white/10 bg-white dark:bg-[#0b121e]">
        <h3
          onClick={() => window.location.replace("/market-place")}
          className="flex items-center text-lg font-bold gap-2 cursor-pointer text-slate-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 transition"
        >
          <LogOut className="h-5 w-5" />
          Môi trường thử nghiệm
        </h3>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            className="rounded-xl border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 dark:text-white"
          >
            Lấy API Key
          </Button>
          <Button className="rounded-xl bg-blue-600 text-white hover:bg-blue-500 shadow-sm font-bold">
            Xem mã
          </Button>
        </div>
      </div>
      <div className="min-h-[calc(100vh-64px)] flex flex-col lg:flex-row p-4 lg:p-8 gap-6">
        {/* LEFT SIDEBAR */}
        <InferencingSettings />

        {/* RIGHT MAIN */}
        <main className="flex-1 overflow-auto space-y-6">
          <h1 className="text-2xl font-black text-slate-900 dark:text-white">Playground</h1>

          <div className="grid grid-cols-1 gap-6">
            {/* Input */}
            <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm space-y-4 dark:border-white/10 dark:bg-[#0b121e]">
              <h3 className="text-base font-bold text-slate-900 dark:text-white">Input</h3>

              <label className="block border-2 border-dashed border-slate-200 dark:border-white/15 rounded-xl p-6 text-center cursor-pointer hover:bg-slate-50/70 dark:hover:bg-white/5 transition">
                <input
                  type="file"
                  accept=".png,.jpg,.jpeg,.pdf"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
                  Kéo thả file hoặc click để upload
                </p>
              </label>

              {file && (
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  File: <strong className="font-bold">{file.name}</strong>
                </p>
              )}

              <Button
                onClick={() =>
                  setResult(
                    `OCR RESULT (${model})\n------------------\nHÓA ĐƠN GIÁ TRỊ GIA TĂNG...`
                  )
                }
                className="w-full rounded-xl bg-blue-600 text-white font-bold py-2.5 hover:bg-blue-500 transition shadow-sm"
              >
                Run inference
              </Button>
            </div>

            {/* Output */}
            <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm space-y-4 dark:border-white/10 dark:bg-[#0b121e]">
              <h3 className="text-base font-bold text-slate-900 dark:text-white">Output</h3>

              {result ? (
                <pre className="rounded-xl border border-slate-800 bg-slate-900 p-4 font-mono text-xs md:text-sm text-emerald-400 h-[360px] overflow-auto shadow-inner">
                  {result}
                </pre>
              ) : (
                <div className="h-[360px] flex items-center justify-center text-sm font-medium text-slate-400 dark:text-slate-500 border border-dashed border-slate-200 dark:border-white/10 rounded-xl bg-slate-50/50 dark:bg-white/5">
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
