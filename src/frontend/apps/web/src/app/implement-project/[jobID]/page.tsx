"use client";

import React, { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Badge } from "@/shared/components/ui/badge";
import { useToast } from "@/shared/hooks/use-toast";
import {
  Activity,
  ArrowDownToLine,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  Cpu,
  FileCode,
  FileSpreadsheet,
  Gauge,
  Layers,
  Package,
  Play,
  Power,
  RefreshCw,
  Send,
  Server,
  Terminal,
  Upload,
  Zap,
} from "lucide-react";
import {
  useActivateModelMutation,
  useGetModelDeploymentInfoQuery,
  usePredictRealtimeMutation,
} from "@/core/api/inferenceApi";
import { getApiErrorMessage } from "@/core/api/baseApi";
import { downloadApiFile } from "@automl/api";
import BackButton from "@/shared/components/common/BackButton";
import AppLoading from "@/shared/components/common/AppLoading";
import { Spinner } from "@/shared/components/ui/spinner";
import { cn } from "@/shared/lib/utils";

type TabKey = "snippets" | "realtime" | "batch" | "export";

export default function ModelServingWorkbenchPage() {
  const params = useParams();
  const rawId = params?.jobID;
  const jobId = Array.isArray(rawId) ? rawId[0] : rawId || "";

  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<TabKey>("snippets");
  const [selectedSnippetLang, setSelectedSnippetLang] = useState<
    "curl" | "python" | "javascript" | "csharp" | "php"
  >("curl");

  // API hooks
  const {
    data: deploymentResponse,
    isLoading,
    isFetching,
    refetch,
  } = useGetModelDeploymentInfoQuery(jobId, { skip: !jobId });

  const [activateModelMutation, { isLoading: isTogglingActivation }] =
    useActivateModelMutation();
  const [predictRealtimeMutation, { isLoading: isPredictingRealtime }] =
    usePredictRealtimeMutation();

  const deployment = deploymentResponse?.data;
  const isModelActive = deployment?.activate === 1 || deployment?.status === "ACTIVE";

  // Real-time prediction state
  const [predictionMode, setPredictionMode] = useState<"form" | "json">("form");
  const [formInputs, setFormInputs] = useState<Record<string, string>>({});
  const [jsonInput, setJsonInput] = useState<string>("");
  const [predictionResult, setPredictionResult] = useState<any>(null);

  // Batch prediction state
  const [batchFile, setBatchFile] = useState<File | null>(null);
  const [isBatchPredicting, setIsBatchPredicting] = useState(false);

  // Export downloading states
  const [downloadingArtifact, setDownloadingArtifact] = useState<string | null>(null);

  // Copy helper
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleCopy = async (text: string, key = "default") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      toast({
        title: "Đã sao chép!",
        description: "Đoạn mã đã được lưu vào clipboard.",
        className: "bg-green-100 text-green-800 border border-green-300",
      });
      setTimeout(() => setCopiedKey(null), 2000);
    } catch {
      toast({
        title: "Lỗi sao chép",
        description: "Không thể sao chép văn bản.",
        variant: "destructive",
      });
    }
  };

  // Toggle Activation
  const handleToggleActivation = async () => {
    if (!jobId) return;
    const targetState = isModelActive ? 0 : 1;

    try {
      await activateModelMutation({ jobId, activate: targetState }).unwrap();
      await refetch();

      toast({
        title: targetState === 1 ? "🚀 Đã kích hoạt phục vụ API!" : "⏸️ Đã hủy kích hoạt API",
        description:
          targetState === 1
            ? "Mô hình đã sẵn sàng nhận yêu cầu dự đoán Real-time và Batch."
            : "Mô hình đã được giải phóng khỏi RAM Cache.",
        className:
          targetState === 1
            ? "bg-green-100 text-green-800 border border-green-300"
            : "bg-amber-100 text-amber-800 border border-amber-300",
      });
    } catch (err) {
      toast({
        title: "Thao tác thất bại",
        description: getApiErrorMessage(err, "Không thể cập nhật trạng thái phục vụ."),
        variant: "destructive",
      });
    }
  };

  // Initialize form and JSON inputs when deployment data is loaded
  React.useEffect(() => {
    if (!deployment) return;

    const initialMap: Record<string, string> = {};
    if (deployment.features_schema && deployment.features_schema.length > 0) {
      deployment.features_schema.forEach((feat) => {
        initialMap[feat.name] =
          feat.sample_value !== undefined ? String(feat.sample_value) : "1.0";
      });
    } else if (deployment.features && deployment.features.length > 0) {
      deployment.features.forEach((feat) => {
        initialMap[feat] = "1.0";
      });
    }
    setFormInputs(initialMap);

    if (deployment.sample_payload) {
      setJsonInput(JSON.stringify(deployment.sample_payload, null, 2));
    } else if (Object.keys(initialMap).length > 0) {
      const numericPayload: Record<string, number> = {};
      Object.entries(initialMap).forEach(([k, v]) => {
        numericPayload[k] = parseFloat(v) || 0;
      });
      setJsonInput(JSON.stringify({ data: [numericPayload] }, null, 2));
    }
  }, [deployment]);

  // Execute Real-time prediction
  const handleRealtimePredict = async () => {
    if (!jobId) return;

    if (!isModelActive) {
      toast({
        title: "Mô hình chưa kích hoạt",
        description: "Vui lòng bấm nút 'Kích hoạt Serving API' trước khi thực hiện dự đoán.",
        variant: "destructive",
      });
      return;
    }

    try {
      let payloadRecords: Array<Record<string, unknown>> = [];

      if (predictionMode === "form") {
        const record: Record<string, unknown> = {};
        Object.entries(formInputs).forEach(([key, val]) => {
          const num = parseFloat(val);
          record[key] = isNaN(num) ? val : num;
        });
        payloadRecords = [record];
      } else {
        const parsed = JSON.parse(jsonInput);
        if (Array.isArray(parsed)) {
          payloadRecords = parsed;
        } else if (Array.isArray(parsed?.data)) {
          payloadRecords = parsed.data;
        } else {
          payloadRecords = [parsed];
        }
      }

      const res = await predictRealtimeMutation({
        jobId,
        data: payloadRecords,
      }).unwrap();

      setPredictionResult(res.data);

      toast({
        title: "🎉 Dự đoán thành công!",
        description: `Độ trễ xử lý: ${res.data.latency_ms?.toFixed(2)} ms cho ${res.data.total_samples} mẫu.`,
        className: "bg-green-100 text-green-800 border border-green-300",
      });
    } catch (err) {
      toast({
        title: "Lỗi dự đoán",
        description: getApiErrorMessage(err, "Không thể thực thi dự đoán thời gian thực."),
        variant: "destructive",
      });
    }
  };

  // Execute Batch file prediction
  const handleBatchPredict = async () => {
    if (!batchFile || !jobId) return;

    if (!isModelActive) {
      toast({
        title: "Mô hình chưa kích hoạt",
        description: "Vui lòng bấm nút 'Kích hoạt Serving API' trước khi chạy dự đoán theo lô.",
        variant: "destructive",
      });
      return;
    }

    setIsBatchPredicting(true);
    try {
      const formData = new FormData();
      formData.append("file", batchFile);

      const base = process.env.NEXT_PUBLIC_BASE_API || "http://localhost:9999";
      const cleanBase = base.replace(/\/+$/, "");
      const predictUrl = cleanBase.endsWith("/api/v1")
        ? `${cleanBase}/inference/models/${jobId}/predict/file`
        : `${cleanBase}/api/v1/inference/models/${jobId}/predict/file`;

      await downloadApiFile({
        url: predictUrl,
        defaultFileName: `predicted_${batchFile.name}`,
        method: "POST",
        dataPayload: formData,
      });

      toast({
        title: "✅ Xử lý dự đoán theo lô thành công!",
        description: "File kết quả kèm cột dự đoán đã được tải về máy của bạn.",
        className: "bg-green-100 text-green-800 border border-green-300",
      });
    } catch (err) {
      toast({
        title: "Lỗi dự đoán theo lô",
        description: getApiErrorMessage(err, "Không thể xử lý file dự đoán."),
        variant: "destructive",
      });
    } finally {
      setIsBatchPredicting(false);
    }
  };

  // Download artifacts handler
  const handleDownloadArtifact = async (type: "notebook" | "docker" | "model") => {
    if (!jobId) return;
    setDownloadingArtifact(type);

    try {
      const base = process.env.NEXT_PUBLIC_BASE_API || "http://localhost:9999";
      const cleanBase = base.replace(/\/+$/, "");
      const prefix = cleanBase.endsWith("/api/v1") ? cleanBase : `${cleanBase}/api/v1`;

      let endpoint = "";
      let defaultName = "";

      if (type === "notebook") {
        endpoint = `${prefix}/inference/models/${jobId}/export/notebook`;
        defaultName = `hautoml_${deployment?.model_name || "model"}_${jobId.slice(0, 8)}.ipynb`;
      } else if (type === "docker") {
        endpoint = `${prefix}/inference/models/${jobId}/export/docker`;
        defaultName = `hautoml_docker_${deployment?.model_name || "service"}_${jobId.slice(0, 8)}.zip`;
      } else {
        endpoint = `${prefix}/inference/models/${jobId}/export/model`;
        defaultName = `${deployment?.model_name || "model"}_${jobId.slice(0, 8)}.pkl`;
      }

      await downloadApiFile({
        url: endpoint,
        defaultFileName: defaultName,
        method: "GET",
      });

      toast({
        title: "Tải thành công!",
        description: `Tệp ${defaultName} đã được tải về máy.`,
        className: "bg-green-100 text-green-800 border border-green-300",
      });
    } catch (err) {
      toast({
        title: "Lỗi tải artifact",
        description: getApiErrorMessage(err, "Không thể tải tệp xuất khẩu."),
        variant: "destructive",
      });
    } finally {
      setDownloadingArtifact(null);
    }
  };

  const codeSnippets = deployment?.code_snippets || {
    curl: `curl -X POST '${deployment?.endpoint_url || `http://localhost:9999/api/v1/inference/models/${jobId}/predict`}' \\
  -H 'Content-Type: application/json' \\
  -H 'Authorization: Bearer <access_token>' \\
  -d '${JSON.stringify(deployment?.sample_payload || { data: [{ age: 30, income: 50000 }] })}'`,
    python: `import requests

url = "${deployment?.endpoint_url || `http://localhost:9999/api/v1/inference/models/${jobId}/predict`}"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer <access_token>"
}
payload = ${JSON.stringify(deployment?.sample_payload || { data: [{ age: 30, income: 50000 }] }, null, 4)}

response = requests.post(url, json=payload, headers=headers)
print(response.json())`,
    javascript: `const response = await fetch("${deployment?.endpoint_url || `http://localhost:9999/api/v1/inference/models/${jobId}/predict`}", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer <access_token>"
  },
  body: JSON.stringify(${JSON.stringify(deployment?.sample_payload || { data: [{ age: 30, income: 50000 }] }, null, 2)})
});

const result = await response.json();
console.log(result);`,
    csharp: `using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;

class Program {
    static async Task Main() {
        using var client = new HttpClient();
        client.DefaultRequestHeaders.Add("Authorization", "Bearer <access_token>");
        var json = @"${JSON.stringify(deployment?.sample_payload || { data: [{ age: 30, income: 50000 }] })}";
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        var response = await client.PostAsync("${deployment?.endpoint_url || `http://localhost:9999/api/v1/inference/models/${jobId}/predict`}", content);
        var result = await response.Content.ReadAsStringAsync();
        Console.WriteLine(result);
    }
}`,
    php: `<?php
$ch = curl_init("${deployment?.endpoint_url || `http://localhost:9999/api/v1/inference/models/${jobId}/predict`}");
$payload = json_encode(${jsonInput ? jsonInput : `["data" => [["age" => 30]]]`});

curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    'Authorization: Bearer <access_token>'
]);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

$result = curl_exec($ch);
curl_close($ch);
echo $result;`,
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <BackButton fallbackHref="/implement-project" />
        <AppLoading label="Đang nạp thông tin mô hình & Serving Hub..." />
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Top Bar with Back Navigation & Refresh */}
      <div className="flex items-center justify-between">
        <BackButton fallbackHref="/implement-project" />
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
          className="rounded-xl border-slate-200 bg-white dark:border-white/10 dark:bg-white/5 font-semibold text-xs gap-1.5"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
          Làm mới
        </Button>
      </div>

      {/* Model Header Card */}
      <Card className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-automl-navy">
        <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-md">
              <Cpu className="h-8 w-8" />
            </div>
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                  {deployment?.model_name || "AutoML Model"}
                </h1>
                <Badge
                  variant="outline"
                  className={cn(
                    "rounded-full px-3 py-0.5 text-xs font-bold",
                    isModelActive
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                      : "border-amber-200 bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
                  )}
                >
                  {isModelActive ? (
                    <span className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                      ACTIVE (Đang phục vụ)
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-amber-500" />
                      INACTIVE (Tạm dừng)
                    </span>
                  )}
                </Badge>
              </div>

              <div className="flex flex-wrap items-center gap-4 text-xs font-medium text-slate-500 dark:text-slate-400">
                <span>Job ID: <strong className="font-mono text-slate-700 dark:text-slate-200">{jobId}</strong></span>
                {deployment?.best_score !== undefined && (
                  <span>Độ chuẩn xác: <strong className="text-blue-600 dark:text-blue-400 font-bold">{(deployment.best_score * 100).toFixed(2)}%</strong></span>
                )}
                <span>Số thuộc tính: <strong className="text-slate-700 dark:text-slate-200 font-bold">{deployment?.features?.length || 0} features</strong></span>
              </div>
            </div>
          </div>

          {/* Action Deploy / Undeploy Toggle */}
          <div className="flex items-center gap-3">
            <Button
              onClick={handleToggleActivation}
              disabled={isTogglingActivation}
              className={cn(
                "h-12 rounded-2xl px-6 font-black shadow-md transition-all",
                isModelActive
                  ? "bg-rose-600 hover:bg-rose-700 text-white"
                  : "bg-emerald-600 hover:bg-emerald-700 text-white",
              )}
            >
              {isTogglingActivation ? (
                <Spinner className="h-5 w-5 mr-2" />
              ) : (
                <Power className="h-5 w-5 mr-2" />
              )}
              {isModelActive ? "Undeploy Model (Tắt Serving)" : "Deploy Model (Bật Serving)"}
            </Button>
          </div>
        </div>
      </Card>

      {/* Tabs Navigation */}
      <div className="flex flex-wrap gap-2 border-b border-slate-200 dark:border-white/10 pb-3">
        {[
          { key: "snippets" as TabKey, label: "Tích hợp API & Code Snippets", icon: Code2 },
          { key: "realtime" as TabKey, label: "Thử nghiệm Real-time (JSON)", icon: Zap },
          { key: "batch" as TabKey, label: "Dự đoán Batch (Upload File)", icon: FileSpreadsheet },
          { key: "export" as TabKey, label: "Xuất khẩu Artifacts", icon: Package },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              type="button"
              className={cn(
                "flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-bold transition",
                isActive
                  ? "bg-automl-blue text-white shadow-sm"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10",
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* TAB 1: CODE SNIPPETS & API INFO */}
      {activeTab === "snippets" && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2">
          {/* Endpoint URL Box */}
          <Card className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-automl-navy">
            <div className="flex flex-col gap-3">
              <Label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Serving Endpoint URL
              </Label>
              <div className="flex items-center gap-2">
                <div className="flex-1 rounded-2xl bg-slate-100 px-4 py-3 font-mono text-xs sm:text-sm text-slate-800 dark:bg-slate-900 dark:text-slate-200 overflow-x-auto">
                  {deployment?.endpoint_url || `http://localhost:9999/api/v1/inference/models/${jobId}/predict`}
                </div>
                <Button
                  onClick={() =>
                    handleCopy(
                      deployment?.endpoint_url ||
                        `http://localhost:9999/api/v1/inference/models/${jobId}/predict`,
                      "endpoint",
                    )
                  }
                  variant="outline"
                  className="rounded-2xl h-11 px-4 font-bold shrink-0"
                >
                  {copiedKey === "endpoint" ? (
                    <Check className="h-4 w-4 text-emerald-500 mr-1" />
                  ) : (
                    <Copy className="h-4 w-4 mr-1" />
                  )}
                  {copiedKey === "endpoint" ? "Đã copy" : "Copy URL"}
                </Button>
              </div>
            </div>
          </Card>

          {/* Features Schema Table */}
          {deployment?.features_schema && deployment.features_schema.length > 0 && (
            <Card className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-automl-navy">
              <CardHeader className="p-0 pb-4">
                <CardTitle className="text-lg font-black text-slate-900 dark:text-white flex items-center gap-2">
                  <Layers className="h-5 w-5 text-blue-600" />
                  Cấu trúc thuộc tính yêu cầu (Features Schema)
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Danh sách các cột thuộc tính bắt buộc phải có trong payload dự đoán
                </CardDescription>
              </CardHeader>
              <div className="overflow-x-auto rounded-2xl border border-slate-100 dark:border-white/5">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-900/50 font-black text-slate-600 dark:text-slate-300">
                    <tr>
                      <th className="p-3">Tên Feature</th>
                      <th className="p-3">Kiểu dữ liệu</th>
                      <th className="p-3">Giá trị mẫu</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-white/5 font-mono">
                    {deployment.features_schema.map((feat) => (
                      <tr key={feat.name} className="hover:bg-slate-50/50 dark:hover:bg-white/5">
                        <td className="p-3 font-bold text-blue-600 dark:text-blue-400">{feat.name}</td>
                        <td className="p-3 text-slate-500">{feat.data_type}</td>
                        <td className="p-3 text-slate-700 dark:text-slate-300">{String(feat.sample_value ?? "1.0")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* 5 Code Snippets */}
          <Card className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-automl-navy">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100 dark:border-white/5">
              <div className="flex items-center gap-2">
                <Terminal className="h-5 w-5 text-indigo-600" />
                <h3 className="font-black text-slate-900 dark:text-white">
                  Đoạn mã mẫu gọi API (5 Ngôn ngữ)
                </h3>
              </div>

              {/* Language Switcher */}
              <div className="flex flex-wrap gap-1 rounded-2xl bg-slate-100 p-1 dark:bg-slate-900">
                {(["curl", "python", "javascript", "csharp", "php"] as const).map((lang) => (
                  <button
                    key={lang}
                    onClick={() => setSelectedSnippetLang(lang)}
                    type="button"
                    className={cn(
                      "rounded-xl px-3 py-1.5 text-xs font-black uppercase transition",
                      selectedSnippetLang === lang
                        ? "bg-white text-blue-600 shadow-xs dark:bg-slate-800 dark:text-white"
                        : "text-slate-500 hover:text-slate-900 dark:text-slate-400",
                    )}
                  >
                    {lang === "javascript" ? "JS / Node" : lang}
                  </button>
                ))}
              </div>
            </div>

            {/* Snippet Code Viewer */}
            <div className="relative mt-4 rounded-2xl border border-slate-800 bg-slate-950 p-5 shadow-inner">
              <Button
                onClick={() =>
                  handleCopy(codeSnippets[selectedSnippetLang] || "", selectedSnippetLang)
                }
                size="sm"
                variant="outline"
                className="absolute top-4 right-4 rounded-xl border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800 hover:text-white text-xs font-bold"
              >
                {copiedKey === selectedSnippetLang ? (
                  <Check className="h-3.5 w-3.5 text-emerald-400 mr-1" />
                ) : (
                  <Copy className="h-3.5 w-3.5 mr-1" />
                )}
                {copiedKey === selectedSnippetLang ? "Đã copy" : "Sao chép"}
              </Button>

              <pre className="overflow-x-auto text-xs sm:text-sm font-mono text-slate-200 leading-relaxed pr-24">
                <code>{codeSnippets[selectedSnippetLang]}</code>
              </pre>
            </div>
          </Card>
        </div>
      )}

      {/* TAB 2: REAL-TIME ONLINE PREDICTION */}
      {activeTab === "realtime" && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2">
          {!isModelActive && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs font-bold text-amber-800 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-300 flex items-center justify-between">
              <span>⚠️ Mô hình hiện đang INACTIVE. Vui lòng bấm nút &quot;Deploy Model&quot; ở trên để bật Serving API trước khi dự đoán.</span>
              <Button size="sm" onClick={handleToggleActivation} className="bg-amber-600 hover:bg-amber-700 text-white rounded-xl">
                Deploy ngay
              </Button>
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-12">
            {/* Input Form / JSON Panel */}
            <div className="lg:col-span-7 space-y-4">
              <Card className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-automl-navy">
                <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-white/5">
                  <div className="flex items-center gap-2">
                    <Zap className="h-5 w-5 text-blue-600" />
                    <h3 className="font-black text-slate-900 dark:text-white">
                      Dữ liệu đầu vào
                    </h3>
                  </div>

                  <div className="flex items-center rounded-xl bg-slate-100 p-1 dark:bg-slate-900 text-xs font-bold">
                    <button
                      type="button"
                      onClick={() => setPredictionMode("form")}
                      className={cn(
                        "rounded-lg px-3 py-1.5 transition",
                        predictionMode === "form"
                          ? "bg-white text-blue-600 shadow-xs dark:bg-slate-800 dark:text-white"
                          : "text-slate-500",
                      )}
                    >
                      Form UI
                    </button>
                    <button
                      type="button"
                      onClick={() => setPredictionMode("json")}
                      className={cn(
                        "rounded-lg px-3 py-1.5 transition",
                        predictionMode === "json"
                          ? "bg-white text-blue-600 shadow-xs dark:bg-slate-800 dark:text-white"
                          : "text-slate-500",
                      )}
                    >
                      Raw JSON
                    </button>
                  </div>
                </div>

                <div className="mt-4">
                  {predictionMode === "form" ? (
                    <div className="grid gap-3 sm:grid-cols-2 max-h-96 overflow-y-auto pr-1">
                      {Object.keys(formInputs).length === 0 ? (
                        <p className="text-xs text-slate-500 col-span-2">Không tìm thấy danh sách thuộc tính.</p>
                      ) : (
                        Object.keys(formInputs).map((featureName) => (
                          <div key={featureName} className="space-y-1">
                            <Label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                              {featureName}
                            </Label>
                            <Input
                              type="text"
                              value={formInputs[featureName] || ""}
                              onChange={(e) =>
                                setFormInputs({ ...formInputs, [featureName]: e.target.value })
                              }
                              placeholder="1.0"
                              className="h-10 rounded-xl font-mono text-xs"
                            />
                          </div>
                        ))
                      )}
                    </div>
                  ) : (
                    <textarea
                      value={jsonInput}
                      onChange={(e) => setJsonInput(e.target.value)}
                      rows={12}
                      className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-emerald-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  )}
                </div>

                <div className="mt-6">
                  <Button
                    onClick={handleRealtimePredict}
                    disabled={isPredictingRealtime}
                    className="h-12 w-full rounded-2xl bg-automl-blue font-black text-white shadow-md hover:bg-automl-blue-hover"
                  >
                    {isPredictingRealtime ? (
                      <Spinner className="h-5 w-5 mr-2" />
                    ) : (
                      <Play className="h-5 w-5 mr-2 fill-current" />
                    )}
                    {isPredictingRealtime ? "Đang dự đoán..." : "Thực thi dự đoán (Real-time Predict)"}
                  </Button>
                </div>
              </Card>
            </div>

            {/* Output Result Panel */}
            <div className="lg:col-span-5 space-y-4">
              <Card className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-automl-navy h-full flex flex-col">
                <CardHeader className="p-0 pb-4 border-b border-slate-100 dark:border-white/5">
                  <CardTitle className="text-lg font-black text-slate-900 dark:text-white flex items-center gap-2">
                    <Activity className="h-5 w-5 text-emerald-600" />
                    Kết quả dự đoán (Inference Output)
                  </CardTitle>
                </CardHeader>

                <div className="flex-1 flex flex-col justify-center py-6">
                  {predictionResult ? (
                    <div className="space-y-4 animate-in zoom-in-95">
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3.5 dark:border-white/10 dark:bg-white/5 text-center">
                          <span className="text-[11px] font-bold text-slate-500">Độ trễ (Latency)</span>
                          <p className="text-xl font-black text-blue-600 dark:text-blue-400">
                            {predictionResult.latency_ms?.toFixed(2)} ms
                          </p>
                        </div>
                        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3.5 dark:border-white/10 dark:bg-white/5 text-center">
                          <span className="text-[11px] font-bold text-slate-500">Số mẫu</span>
                          <p className="text-xl font-black text-slate-900 dark:text-white">
                            {predictionResult.total_samples}
                          </p>
                        </div>
                      </div>

                      <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4 dark:border-emerald-900/50 dark:bg-emerald-950/20">
                        <span className="text-xs font-bold text-emerald-800 dark:text-emerald-300 block mb-2">
                          Predictions Array:
                        </span>
                        <div className="flex flex-wrap gap-2">
                          {predictionResult.predictions?.map((pred: any, idx: number) => (
                            <span
                              key={idx}
                              className="rounded-xl bg-emerald-600 px-3 py-1.5 font-mono text-sm font-black text-white shadow-xs"
                            >
                              Mẫu #{idx + 1}: {String(pred)}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="rounded-2xl bg-slate-950 p-4 font-mono text-xs text-slate-300 overflow-x-auto max-h-48">
                        <pre>{JSON.stringify(predictionResult, null, 2)}</pre>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center text-slate-400 py-12 space-y-2">
                      <Zap className="h-10 w-10 mx-auto opacity-30 text-slate-400" />
                      <p className="text-sm font-semibold">Chưa có kết quả dự đoán</p>
                      <p className="text-xs text-slate-400">Điền tham số ở khung bên trái và bấm &quot;Thực thi dự đoán&quot;.</p>
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: BATCH INFERENCE VIA FILE */}
      {activeTab === "batch" && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2">
          {!isModelActive && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs font-bold text-amber-800 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-300 flex items-center justify-between">
              <span>⚠️ Mô hình hiện đang INACTIVE. Vui lòng bấm nút &quot;Deploy Model&quot; để kích hoạt trước khi chạy dự đoán theo file.</span>
              <Button size="sm" onClick={handleToggleActivation} className="bg-amber-600 hover:bg-amber-700 text-white rounded-xl">
                Deploy ngay
              </Button>
            </div>
          )}

          <Card className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm dark:border-white/10 dark:bg-automl-navy max-w-2xl mx-auto">
            <div className="text-center space-y-2 mb-6">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 mx-auto">
                <FileSpreadsheet className="h-7 w-7" />
              </div>
              <h2 className="text-xl font-black text-slate-900 dark:text-white">
                Dự đoán hàng loạt theo file (Batch Inference)
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto">
                Tải lên tệp CSV hoặc Excel chứa các dòng thuộc tính. Hệ thống sẽ tự động thêm cột kết quả dự đoán và trả về file đã hoàn tất.
              </p>
            </div>

            {/* Drag & Drop File Zone */}
            <div className="space-y-4">
              <label className="flex flex-col items-center justify-center rounded-3xl border-2 border-dashed border-slate-300 dark:border-white/15 bg-slate-50 dark:bg-slate-900/40 p-8 cursor-pointer hover:border-blue-500 transition">
                <Upload className="h-8 w-8 text-blue-500 mb-2" />
                <span className="text-sm font-bold text-slate-700 dark:text-slate-200">
                  {batchFile ? batchFile.name : "Chọn hoặc kéo thả tệp CSV / Excel vào đây"}
                </span>
                <span className="text-xs text-slate-400 mt-1">
                  {batchFile ? `${(batchFile.size / 1024).toFixed(1)} KB` : "Hỗ trợ định dạng .csv, .xls, .xlsx"}
                </span>
                <input
                  type="file"
                  accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setBatchFile(f);
                  }}
                  className="hidden"
                />
              </label>

              <Button
                onClick={handleBatchPredict}
                disabled={!batchFile || isBatchPredicting}
                className="h-12 w-full rounded-2xl bg-automl-blue font-black text-white shadow-md hover:bg-automl-blue-hover"
              >
                {isBatchPredicting ? (
                  <Spinner className="h-5 w-5 mr-2" />
                ) : (
                  <Send className="h-5 w-5 mr-2" />
                )}
                {isBatchPredicting ? "Đang xử lý & tạo file kết quả..." : "Bắt đầu dự đoán & Tải file kết quả"}
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* TAB 4: EXPORT ARTIFACTS */}
      {activeTab === "export" && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2">
          <div className="grid gap-6 md:grid-cols-3">
            {/* Jupyter Notebook */}
            <Card className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-automl-navy flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">
                  <FileCode className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-black text-slate-900 dark:text-white">
                  Jupyter Notebook (.ipynb)
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                  Xuất tệp Notebook chứa toàn bộ pipeline xử lý dữ liệu, code huấn luyện và tham số tối ưu để bạn có thể chạy độc lập.
                </p>
              </div>

              <Button
                onClick={() => handleDownloadArtifact("notebook")}
                disabled={downloadingArtifact === "notebook"}
                variant="outline"
                className="mt-6 h-11 w-full rounded-2xl border-slate-200 bg-white font-bold text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white"
              >
                {downloadingArtifact === "notebook" ? (
                  <Spinner className="h-4 w-4 mr-2" />
                ) : (
                  <ArrowDownToLine className="h-4 w-4 mr-2 text-amber-600" />
                )}
                Tải Notebook (.ipynb)
              </Button>
            </Card>

            {/* Docker Microservice */}
            <Card className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-automl-navy flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
                  <Server className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-black text-slate-900 dark:text-white">
                  Docker Microservice (.zip)
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                  Gói Microservice độc lập gồm Dockerfile, app.py, requirements.txt và model.pkl để triển khai ngay lên Kubernetes hoặc Cloud VM.
                </p>
              </div>

              <Button
                onClick={() => handleDownloadArtifact("docker")}
                disabled={downloadingArtifact === "docker"}
                variant="outline"
                className="mt-6 h-11 w-full rounded-2xl border-slate-200 bg-white font-bold text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white"
              >
                {downloadingArtifact === "docker" ? (
                  <Spinner className="h-4 w-4 mr-2" />
                ) : (
                  <ArrowDownToLine className="h-4 w-4 mr-2 text-blue-600" />
                )}
                Tải Docker Package (.zip)
              </Button>
            </Card>

            {/* Model Pickle Binary */}
            <Card className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-automl-navy flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400">
                  <Package className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-black text-slate-900 dark:text-white">
                  Model Pickle Binary (.pkl)
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                  Tải trực tiếp tệp nhị phân mô hình máy học đã được serialize để nạp vào các ứng dụng Python khác.
                </p>
              </div>

              <Button
                onClick={() => handleDownloadArtifact("model")}
                disabled={downloadingArtifact === "model"}
                variant="outline"
                className="mt-6 h-11 w-full rounded-2xl border-slate-200 bg-white font-bold text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white"
              >
                {downloadingArtifact === "model" ? (
                  <Spinner className="h-4 w-4 mr-2" />
                ) : (
                  <ArrowDownToLine className="h-4 w-4 mr-2 text-violet-600" />
                )}
                Tải Model Binary (.pkl)
              </Button>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
