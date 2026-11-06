import type { AgentEvent, HealthInfo } from "./events";

export const AGENT_API = process.env.NEXT_PUBLIC_AGENT_API || "http://localhost:9500";

// Giới hạn này cũng được server (agent/uploads.py) áp lại. Kiểm tra ở đây chỉ
// để báo lỗi NGAY, không phải chờ tải lên xong mới biết - chốt thật nằm ở server.
export const MAX_UPLOAD_MB = 20;
const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".csv", ".xlsx", ".xls"];
export const ACCEPT_ATTR =
  ".csv,.xlsx,.xls,text/csv,application/vnd.ms-excel," +
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

/** Lỗi HTTP giữ lại status để giao diện báo đúng (409 phiên bận, 401 hết hạn). */
export class AgentHttpError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function extensionOf(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot >= 0 ? filename.slice(dot).toLowerCase() : "";
}

export interface FileProblem {
  code: "unsupported" | "empty" | "tooLarge";
  values: Record<string, string | number>;
}

/** Trả về lỗi (mã + tham số để dịch), hoặc null nếu file hợp lệ. */
export function validateFile(file: File): FileProblem | null {
  const ext = extensionOf(file.name);
  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return { code: "unsupported", values: { name: file.name, ext: ACCEPTED_EXTENSIONS.join(", ") } };
  }
  if (file.size === 0) return { code: "empty", values: { name: file.name } };
  if (file.size > MAX_UPLOAD_BYTES) {
    return { code: "tooLarge", values: { name: file.name, size: formatSize(file.size), mb: MAX_UPLOAD_MB } };
  }
  return null;
}

export function defaultDatasetName(filename: string): string {
  const ext = extensionOf(filename);
  return (ext ? filename.slice(0, -ext.length) : filename).trim() || "dataset";
}

/**
 * Tải lên bằng XHR thay vì fetch: fetch không báo được tiến độ upload, mà file
 * 20 MB có thể mất vài giây - người dùng cần thấy thanh tiến độ chạy.
 */
export function uploadWithProgress(
  form: FormData,
  onProgress: (percent: number) => void,
): Promise<{ status: number; body: any }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${AGENT_API}/agent/upload`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let body: any = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        body = { detail: xhr.responseText.slice(0, 200) };
      }
      resolve({ status: xhr.status, body });
    };
    xhr.onerror = () => reject(new Error("network"));
    xhr.send(form);
  });
}

/** POST JSON. Token luôn nằm trong body, không bao giờ trên URL (URL hay bị ghi log). */
export function postJson(path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  return fetch(`${AGENT_API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthInfo> {
  const res = await fetch(`${AGENT_API}/health`, { signal, cache: "no-store" });
  if (!res.ok) throw new AgentHttpError(res.status, `HTTP ${res.status}`);
  return res.json();
}

/**
 * Đọc luồng SSE từ một response fetch.
 *
 * Không dùng EventSource: nó chỉ gửi được GET, mà token phải nằm trong body
 * POST chứ không phải trên URL.
 */
export async function readSSE(res: Response, onEvent: (event: string, data: AgentEvent) => void) {
  if (!res.body) return;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let end: number;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);

      let event = "message";
      const data: string[] = [];
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data.push(line.slice(6));
      }
      if (!data.length) continue; // comment giữ kết nối (": ping")
      try {
        onEvent(event, JSON.parse(data.join("\n")));
      } catch {
        // Một sự kiện hỏng không được làm dừng cả luồng.
      }
    }
  }
}
