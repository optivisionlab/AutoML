"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useApi } from "@/hooks/useApi";

type Props = {
  jobId: string;
  disabled?: boolean;
};

const UploadPredictButton = ({ jobId, disabled }: Props) => {
  const { post } = useApi();
  const [loading, setLoading] = useState(false);

  // Xử lý tải lên và trả về kết quả là 1 file
  const handleUploadAndDownload = async (file: File) => {
    try {
      setLoading(true);

      const formData = new FormData();
      formData.append("file_data", file);

      const response = await post(`/v2/auto/${jobId}/predictions`, formData, {
        isBlob: true,
      });

      const blob = response.data;

      if (!(blob instanceof Blob)) {
        alert("API không trả file");
        return;
      }

      // lấy tên file
      const contentDisposition = response.headers["content-disposition"];
      let fileName = "result.csv";

      if (contentDisposition) {
        const match =
          contentDisposition.match(/filename\*=UTF-8''(.+)/) ||
          contentDisposition.match(/filename="?([^"]+)"?/);

        if (match?.[1]) {
          fileName = decodeURIComponent(match[1]);
        }
      }

      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;

      document.body.appendChild(a);
      a.click();

      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      const blob = err.response?.data;

      if (blob instanceof Blob) {
        const text = await blob.text();
        alert(text);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <label>
      <input
        type="file"
        accept=".csv"
        className="hidden"
        disabled={disabled || loading}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleUploadAndDownload(file);
        }}
      />

      <Button
        className={`px-4 ml-2 cursor-pointer py-2 ${
          disabled
            ? "bg-gray-400 cursor-not-allowed"
            : "bg-green-600 hover:bg-green-700 text-white"
        }`}
        disabled={disabled || loading}
        asChild
      >
        <span>{loading ? <Spinner /> : "Upload & Predict"}</span>
      </Button>
    </label>
  );
};

export default UploadPredictButton;
