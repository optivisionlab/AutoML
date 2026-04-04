"use client";

import React, { useState, useRef, useEffect } from "react";
import { Spinner } from "@/components/ui/spinner";
import { useApi } from "@/hooks/useApi";
import { useSession } from "next-auth/react";

type Props = {
  jobId: string;
  disabled?: boolean;
};

const UploadPredictBox = ({ jobId, disabled }: Props) => {
  const { post, remove } = useApi();
  const { data: session } = useSession();

  const [loading, setLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleUploadAndDownload = async (file: File) => {
    try {
      setLoading(true);
      setIsError(false);

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
      setLoading(false);
    } catch (err: any) {
      setIsError(true);
      const blob = err.response?.data;

      if (blob instanceof Blob) {
        const text = await blob.text();
        let message = text;
        try {
          const json = JSON.parse(text);
          message = json.detail || json.message || text;
        } catch {
          setIsError(true);
          // không phải JSON thì giữ nguyên text
        }

        alert("Lỗi: " + message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFile = (file: File) => {
    if (!file) return;

    const validExtensions = [".csv", ".xls", ".xlsx"];
    const isValid = validExtensions.some((ext) =>
      file.name.toLowerCase().endsWith(ext),
    );

    if (!isValid) {
      alert("Chỉ chấp nhận file .csv, .xls, .xlsx");
      return;
    }

    handleUploadAndDownload(file);
  };

  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (loading && jobId) {
        fetch(
          `${process.env.NEXT_PUBLIC_BASE_API}/v2/auto/${jobId}/predictions`,
          {
            method: "DELETE",
            headers: {
              Authorization: `Bearer ${session?.user?.access_token}`,
            },
            keepalive: true,
          },
        );

        e.preventDefault();
        e.returnValue = "";
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [loading, jobId, session]);

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-8 text-center transition cursor-pointer
        ${
          disabled
            ? "bg-gray-100 cursor-not-allowed"
            : "hover:border-green-500 hover:bg-green-50"
        }`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        if (disabled || loading) return;

        const file = e.dataTransfer.files?.[0];
        if (file) handleFile(file);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".csv,.xls,.xlsx"
        disabled={disabled || loading}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />

      {loading && !isError ? (
        <div
          className="fixed inset-0 z-[9999] bg-black/30 flex items-center justify-center"
          onClick={async (e) => {
            e.stopPropagation();

            const confirmLeave = confirm(
              "Tiến trình đang chạy. Nếu thoát sẽ bị hủy. Bạn có chắc không?",
            );

            if (!confirmLeave) return;

            // gọi API cancel
            await remove(`/v2/auto/${jobId}/predictions`);

            // cho reload hoặc quay lại
            window.location.reload();
          }}
        >
          <div
            className="bg-white px-6 py-4 rounded-lg shadow-lg flex flex-col items-center gap-2"
            onClick={(e) => e.stopPropagation()} // chặn click vào box
          >
            <Spinner />
            <p className="text-sm text-gray-600">
              Đang xử lý, vui lòng không rời trang...
            </p>
          </div>
        </div>
      ) : (
        <>
          <p className="text-lg font-semibold">
            Chạy thử mô hình của bạn ngay bây giờ
          </p>

          <p className="text-sm text-gray-500 mt-2">
            Kéo thả hoặc nhấp để chọn tệp
          </p>

          <p className="text-xs text-gray-400 mt-4">
            Chấp nhận tệp .csv, .xls, .xlsx
          </p>
        </>
      )}
    </div>
  );
};

export default UploadPredictBox;
