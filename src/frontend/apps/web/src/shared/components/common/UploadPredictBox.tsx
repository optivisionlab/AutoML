"use client";

import React, { useState, useRef, useEffect } from "react";
import AppLoading from "@/shared/components/common/AppLoading";
import { useSession } from "next-auth/react";
import {
  useCancelPredictionMutation,
  useRunPredictionMutation,
} from "@/core/api/inferenceApi";
import { getApiErrorMessage } from "@/core/api/baseApi";
import { useTranslations } from "next-intl";

type Props = {
  jobId: string;
  disabled?: boolean;
};

const UploadPredictBox = ({ jobId, disabled }: Props) => {
  const t = useTranslations("UploadPredict");
  const [runPrediction] = useRunPredictionMutation();
  const [cancelPrediction] = useCancelPredictionMutation();
  const { data: session } = useSession();

  const [loading, setLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleUploadAndDownload = async (file: File) => {
    try {
      setLoading(true);
      setIsError(false);

      const { blob, fileName } = await runPrediction({ jobId, file }).unwrap();

      if (!(blob instanceof Blob)) {
        alert(t("apiNoFile"));
        return;
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
      const blob = err?.data;

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

        alert(t("errorWithMessage", { message }));
      } else {
        alert(t("errorWithMessage", { message: getApiErrorMessage(err, t("runFailed")) }));
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
      alert(t("invalidFile"));
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
              t("cancelConfirm"),
            );

            if (!confirmLeave) return;

            // gọi API cancel
            await cancelPrediction(jobId).unwrap();

            // cho reload hoặc quay lại
            window.location.reload();
          }}
        >
          <div onClick={(e) => e.stopPropagation()}>
            <AppLoading label={t("processing")} />
          </div>
        </div>
      ) : (
        <>
          <p className="text-lg font-semibold">
            {t("title")}
          </p>

          <p className="text-sm text-gray-500 mt-2">
            {t("dropHint")}
          </p>

          <p className="text-xs text-gray-400 mt-4">
            {t("acceptedFiles")}
          </p>
        </>
      )}
    </div>
  );
};

export default UploadPredictBox;
