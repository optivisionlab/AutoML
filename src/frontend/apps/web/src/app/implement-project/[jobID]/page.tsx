"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { useToast } from "@/shared/hooks/use-toast";
import { Copy } from "lucide-react";
import { useParams } from "next/navigation";
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
  AlertDialogDescription,
} from "@/shared/components/ui/alert-dialog";
import { useActivateModelMutation } from "@/core/api/inferenceApi";
import { getApiErrorMessage } from "@/core/api/baseApi";
import BackButton from "@/shared/components/common/BackButton";

const ProjectImplementation = () => {
  const { toast } = useToast();
  const [activateModel] = useActivateModelMutation();
  const params = useParams();
  const [actionType, setActionType] = React.useState<
    "enable" | "disable" | null
  >(null);
  const [modelActivated, setModelActivated] = React.useState<boolean>(true);
  const jobID = Array.isArray(params?.jobID) ? params.jobID[0] : params?.jobID;

  const JOB_ID = "<JOB_ID>";
  const URL_API = "<URL_API>";
  const curlCommand = `curl --location '${URL_API}/inference-model/?job_id=${JOB_ID}' \\
--header 'accept: application/json' \\
--form 'file_data=@"/path/to/file"'`;

  const pythonCode = `import requests

url = "<URL_API>/inference-model/?job_id=<JOB_ID>"

payload = {}
files=[('file_data', ('file', open('/path/to/file', 'rb'), 'application/octet-stream'))]
headers = {'accept': 'application/json'}

response = requests.post(url, headers=headers, data=payload, files=files)

print(response.text)`;

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast({
        title: "Đã sao chép!",
        description: "Lệnh đã được sao chép vào clipboard.",
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 3000,
      });
    } catch {
      toast({
        title: "Lỗi khi sao chép",
        description: "Không thể sao chép lệnh.",
        variant: "destructive",
        duration: 3000,
      });
    }
  };

  const handleToggleModel = async (activate: 0 | 1) => {
    if (!jobID) {
      toast({
        title: "Thiếu Job ID",
        description: "Không thể gửi yêu cầu vì thiếu Job ID.",
        variant: "destructive",
      });
      return;
    }

    try {
      await activateModel({ jobId: jobID, activate }).unwrap();
      setModelActivated(activate === 1);

      toast({
        title:
          activate === 1
            ? "Mô hình đã được kích hoạt!"
            : "Mô hình đã bị vô hiệu hóa!",
        className:
          activate === 1
            ? "bg-green-100 text-green-800 border border-green-300"
            : "bg-yellow-100 text-yellow-800 border border-yellow-300",
      });
    } catch (err) {
      toast({
        title: "Lỗi",
        description: getApiErrorMessage(err, "Không thể thực hiện yêu cầu."),
        variant: "destructive",
      });
      console.log("Toggle model error:", err);
    }
  };

  return (
    <div className="mt-2 w-full space-y-4">
      <BackButton fallbackHref="/implement-project" />
      <Card className="rounded-3xl border border-slate-200/80 bg-white p-2 shadow-sm dark:border-white/10 dark:bg-[#0b121e] text-slate-900 dark:text-white">
        <CardHeader className="space-y-4">
          <CardTitle className="text-2xl font-black tracking-tight text-slate-900 dark:text-white text-center w-full">
            Thông tin tích hợp mô hình
          </CardTitle>

          <div className="flex justify-end gap-2">
            {modelActivated ? (
              <Button
                variant="destructive"
                className="rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold"
                onClick={() => setActionType("disable")}
              >
                Hủy kích hoạt
              </Button>
            ) : (
              <Button
                className="rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold"
                onClick={() => setActionType("enable")}
              >
                Kích hoạt
              </Button>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-700 dark:text-slate-300">Trạng thái mô hình:</span>
            {modelActivated ? (
              <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400">
                Đã kích hoạt
              </span>
            ) : (
              <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-bold text-amber-700 dark:bg-amber-500/10 dark:text-amber-400">
                Chưa kích hoạt
              </span>
            )}
          </div>

          <div className="flex items-start gap-2 text-slate-700 dark:text-slate-300">
            <span className="text-emerald-600 dark:text-emerald-400 font-bold">✔</span>
            <span>
              <strong className="text-slate-900 dark:text-white">file_data:</strong> là file dữ liệu cần thử nghiệm
            </span>
          </div>

          <div className="flex items-start gap-2 text-slate-700 dark:text-slate-300">
            <span className="text-emerald-600 dark:text-emerald-400 font-bold">✔</span>
            <span>
              <strong className="text-slate-900 dark:text-white">JOB_ID:</strong> {jobID || "job ID sẽ được cung cấp"}
            </span>
          </div>

          <div className="flex items-start gap-2 text-slate-700 dark:text-slate-300">
            <span className="text-emerald-600 dark:text-emerald-400 font-bold">✔</span>
            <span>
              <strong className="text-slate-900 dark:text-white">URL_API:</strong> Đường dẫn API sẽ được cung cấp
            </span>
          </div>

          <div className="relative rounded-2xl border border-slate-800 bg-slate-900 p-4 shadow-inner">
            <pre className="whitespace-pre-wrap text-xs md:text-sm font-mono text-slate-200">
              <code>{curlCommand}</code>
            </pre>
            <Button
              onClick={() => handleCopy(curlCommand)}
              size="sm"
              variant="outline"
              className="absolute top-3 right-3 rounded-xl border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700 hover:text-white"
            >
              <Copy className="w-4 h-4 mr-1" />
              Sao chép
            </Button>
          </div>

          <div className="flex items-start gap-2 pt-2">
            <span className="font-bold text-slate-900 dark:text-white">
              Code Python minh họa:
            </span>
          </div>

          <div className="relative rounded-2xl border border-slate-800 bg-slate-900 p-4 shadow-inner">
            <pre className="whitespace-pre-wrap text-xs md:text-sm font-mono text-slate-200">
              <code>{pythonCode}</code>
            </pre>
            <Button
              onClick={() => handleCopy(pythonCode)}
              size="sm"
              variant="outline"
              className="absolute top-3 right-3 rounded-xl border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700 hover:text-white"
            >
              <Copy className="w-4 h-4 mr-1" />
              Sao chép
            </Button>
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={!!actionType} onOpenChange={() => setActionType(null)}>
        <AlertDialogTrigger asChild>
          <span />
        </AlertDialogTrigger>
        <AlertDialogContent className="bg-white dark:bg-[#171717] text-gray-900 dark:text-gray-100">
          <AlertDialogHeader>
            <AlertDialogTitle>
              {actionType === "enable"
                ? "Bạn có chắc chắn muốn kích hoạt mô hình này không?"
                : "Bạn có chắc chắn muốn hủy kích hoạt mô hình này không?"}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-gray-600 dark:text-gray-300">
              Hành động này sẽ cập nhật trạng thái hoạt động của mô hình.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800">
              Hủy
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => handleToggleModel(actionType === "enable" ? 1 : 0)}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              Xác nhận
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default ProjectImplementation;
