import axios, { AxiosRequestConfig } from "axios";

export interface DownloadApiFileOptions {
  url: string;
  defaultFileName: string;
  method?: "GET" | "POST" | "PUT" | "DELETE" | string;
  dataPayload?: unknown;
  token?: string | null;
  baseUrl?: string;
  onProgress?: (progressPercent: number) => void;
}

/**
 * Tải file nhị phân từ API Backend và lưu về máy tính người dùng (Binary Streams)
 * Theo chuẩn tài liệu Frontend Playbook Section 5.5
 */
export async function downloadApiFile({
  url,
  defaultFileName,
  method = "GET",
  dataPayload,
  token,
  baseUrl = "",
  onProgress,
}: DownloadApiFileOptions): Promise<void> {
  const fullUrl = url.startsWith("http://") || url.startsWith("https://")
    ? url
    : `${baseUrl.replace(/\/+$/, "")}/${url.replace(/^\/+/, "")}`;

  const authToken =
    token ??
    (typeof window !== "undefined"
      ? localStorage.getItem("access_token")
      : null);

  const config: AxiosRequestConfig = {
    url: fullUrl,
    method,
    data: dataPayload,
    responseType: "blob",
    withCredentials: true,
    headers: {
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    },
    onDownloadProgress: (progressEvent) => {
      if (progressEvent.total && onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total,
        );
        onProgress(percentCompleted);
      }
    },
  };

  const response = await axios(config);

  // Trích xuất filename từ Content-Disposition header nếu có
  let filename = defaultFileName;
  const disposition = response.headers["content-disposition"];
  if (disposition && disposition.includes("filename")) {
    const utf8Match = disposition.match(/filename\*=UTF-8''(.+)/);
    const standardMatch = disposition.match(/filename="?([^"]+)"?/);
    if (utf8Match?.[1]) {
      filename = decodeURIComponent(utf8Match[1]);
    } else if (standardMatch?.[1]) {
      filename = standardMatch[1];
    }
  }

  // Tạo blob và kích hoạt download qua virtual anchor link
  const blob = new Blob([response.data], {
    type: response.headers["content-type"] || "application/octet-stream",
  });
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();

  // Dọn dẹp DOM và Object URL
  link.remove();
  window.URL.revokeObjectURL(downloadUrl);
}
