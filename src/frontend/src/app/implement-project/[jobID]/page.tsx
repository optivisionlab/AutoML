"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { Copy } from "lucide-react";
import { useParams } from "next/navigation";

const ProjectImplementation = () => {
  const { toast } = useToast();
  const params = useParams();
  const jobID = Array.isArray(params?.jobID) ? params.jobID[0] : params?.jobID;

  const JOB_ID = "<JOB_ID>";
  const URL_API = "<URL_API>";
  const curlCommand = `curl --location '${URL_API}/inference-model/?job_id=${JOB_ID}' \\
--header 'accept: application/json' \\
--form 'file_data=@"/path/to/file"'`;
  const pythonCode = `import requests

url = "<URL_API>/inference-model/?job_id=<JOB_ID>"

payload = {}
files=[
  ('file_data',('file',open('/path/to/file','rb'),'application/octet-stream'))
]
headers = {
  'accept': 'application/json'
}

response = requests.request("POST", url, headers=headers, data=payload, files=files)

print(response.text)`

  const handleCopy = async () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(curlCommand);
        toast({
          title: "Đã sao chép lệnh curl thành công!",
          description: "Bạn có thể dán lệnh này vào terminal để thực hiện.",
          duration: 3000,
        });
      } catch (err) {
        toast({
          title: "Lỗi khi sao chép",
          description: "Trình duyệt không cho phép sử dụng clipboard.",
          variant: "destructive",
          duration: 3000,
        });
      }
    } else {
      toast({
        title: "Clipboard không khả dụng",
        description: "Trình duyệt không hỗ trợ Clipboard API.",
        variant: "destructive",
        duration: 3000,
      });
    }
  };

  return (
    <div className="max-w-4xl mx-auto mt-10 px-4">
      <Card className="shadow-md border border-border">
        <CardHeader>
          <CardTitle className="text-2xl font-bold text-[#3b6cf5] text-center w-full">
            Thông tin tích hợp mô hình
          </CardTitle>
        </CardHeader>

        <CardContent className="space-y-3 text-sm ">
          <div className="flex items-start gap-2">
            <span className="text-green-600">✔</span>
            <span>
              <strong>file_data:</strong> là file dữ liệu cần thử nghiệm
            </span>
          </div>

          <div className="flex items-start gap-2">
            <span className="text-green-600">✔</span>
            <span>
              <strong>JOB_ID:</strong>{jobID ? jobID : "job ID sẽ được cung cấp"}
            </span>
          </div>

          <div className="flex items-start gap-2">
            <span className="text-green-600">✔</span>
            <span>
              <strong>URL_API:</strong> Đường dẫn API sẽ được cung cấp
            </span>
          </div>

          <div className="relative bg-background border border-muted rounded-lg p-4 bg-gray-100">
            <pre className="whitespace-pre-wrap text-xs md:text-sm font-mono text-foreground">
              <code>{curlCommand}</code>
            </pre>
            <Button
              onClick={handleCopy}
              size="sm"
              variant="outline"
              className="absolute top-2 right-2"
            >
              <Copy className="w-4 h-4 mr-1" />
              Sao chép
            </Button>
          </div>


          <div className="flex items-start gap-2">
            <span>
              <strong>Code python minh họa:</strong>
            </span>
          </div>

          <div className="relative bg-background border border-muted rounded-lg p-4 bg-gray-100">
            <pre className="whitespace-pre-wrap text-xs md:text-sm font-mono text-foreground">
              <code>{pythonCode}</code>
            </pre>
            <Button
              onClick={handleCopy}
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
    </div>
  );
};

export default ProjectImplementation;