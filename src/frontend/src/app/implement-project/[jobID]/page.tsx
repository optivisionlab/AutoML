"use client";

import React from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
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
} from "@/components/ui/alert-dialog";

const ProjectImplementation = () => {
  const { toast } = useToast();
  const params = useParams();
  const [actionType, setActionType] = React.useState<"enable" | "disable" | null>(null);
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

    const url = `${process.env.NEXT_PUBLIC_BASE_API}/activate-model?job_id=${jobID}&activate=${activate}`;

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          accept: "application/json",
        },
      });

      if (!res.ok) throw new Error("API call failed");
      setModelActivated(activate === 1);

      toast({
        title: activate === 1 ? "Mô hình đã được kích hoạt!" : "Mô hình đã bị vô hiệu hóa!",
        className:
          activate === 1
            ? "bg-green-100 text-green-800 border border-green-300"
            : "bg-yellow-100 text-yellow-800 border border-yellow-300",
      });
    } catch (err) {
      toast({
        title: "Lỗi",
        description: "Không thể thực hiện yêu cầu.",
        variant: "destructive",
      });
      console.log("Toggle model error:", err);
    }
  };

  return (
    <div className="max-w-4xl mx-auto mt-10 px-4">
      <Card className="shadow-md border border-border bg-white dark:bg-[#1e1e1e] text-gray-900 dark:text-gray-100">
        <CardHeader className="space-y-2">
          <CardTitle className="text-2xl font-bold text-[#3b6cf5] dark:text-[#6587f5] text-center w-full">
            Thông tin tích hợp mô hình
          </CardTitle>

          <div className="flex justify-end gap-2">
            {modelActivated ? (
              <Button
                variant="destructive"
                className="bg-red-600 hover:bg-red-700 text-white"
                onClick={() => setActionType("disable")}
              >
                Hủy kích hoạt
              </Button>
            ) : (
              <Button
                variant="default"
                className="bg-green-600 hover:bg-green-700 text-white"
                onClick={() => setActionType("enable")}
              >
                Kích hoạt
              </Button>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-3 text-sm">
          <span>
            <strong>Trạng thái mô hình:</strong>{" "}
            {modelActivated ? (
              <span className="text-green-500 font-medium">Đã kích hoạt</span>
            ) : (
              <span className="text-yellow-500 font-medium">Chưa kích hoạt</span>
            )}
          </span>

          <div className="flex items-start gap-2">
            <span className="text-green-500">✔</span>
            <span><strong>file_data:</strong> là file dữ liệu cần thử nghiệm</span>
          </div>

          <div className="flex items-start gap-2">
            <span className="text-green-500">✔</span>
            <span><strong>JOB_ID:</strong> {jobID || "job ID sẽ được cung cấp"}</span>
          </div>

          <div className="flex items-start gap-2">
            <span className="text-green-500">✔</span>
            <span><strong>URL_API:</strong> Đường dẫn API sẽ được cung cấp</span>
          </div>

          <div className="relative bg-gray-100 dark:bg-[#2a2a2a] border border-muted rounded-lg p-4">
            <pre className="whitespace-pre-wrap text-xs md:text-sm font-mono text-foreground">
              <code>{curlCommand}</code>
            </pre>
            <Button
              onClick={() => handleCopy(curlCommand)}
              size="sm"
              variant="outline"
              className="absolute top-2 right-2"
            >
              <Copy className="w-4 h-4 mr-1" />
              Sao chép
            </Button>
          </div>

          <div className="flex items-start gap-2">
            <span><strong>Code python minh họa:</strong></span>
          </div>

          <div className="relative bg-gray-100 dark:bg-[#2a2a2a] border border-muted rounded-lg p-4">
            <pre className="whitespace-pre-wrap text-xs md:text-sm font-mono text-foreground">
              <code>{pythonCode}</code>
            </pre>
            <Button
              onClick={() => handleCopy(pythonCode)}
              size="sm"
              variant="outline"
              className="absolute top-2 right-2"
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