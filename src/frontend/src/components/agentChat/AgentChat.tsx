"use client";

import { DragEvent, Fragment, KeyboardEvent, ReactNode, useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  FileSpreadsheet,
  Loader2,
  Paperclip,
  RotateCcw,
  Send,
  Sparkles,
  UploadCloud,
  Users,
  Wrench,
  X,
} from "lucide-react";

const AGENT_API = process.env.NEXT_PUBLIC_AGENT_API || "http://localhost:9500";

// Giới hạn này cũng được server (agent/uploads.py) áp lại. Kiểm tra ở đây chỉ
// để báo lỗi NGAY, không phải chờ tải lên xong mới biết - chốt thật nằm ở server.
const MAX_UPLOAD_MB = 20;
const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".csv", ".xlsx", ".xls"];
const ACCEPT_ATTR =
  ".csv,.xlsx,.xls,text/csv,application/vnd.ms-excel," +
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

type DataType = "classification" | "regression";

interface Message {
  id: number;
  role: "user" | "agent" | "system";
  text: string;
  tools?: string[];
  agents?: string[];
  variant?: "upload" | "error" | "job";
  datasetName?: string;
  job?: JobEvent;
}

/** Sự kiện agent server đẩy qua SSE (xem src/backend/agent/events.py). */
interface AgentEvent {
  seq?: number;
  type?: string;
  agent?: string;
  [key: string]: any;
}

interface JobEvent extends AgentEvent {
  job_id: string;
  status?: number | null;
  best_model?: string;
  best_score?: number;
  metric_sort?: string;
  error?: string;
  verification?: { passed: boolean | null; checks: { metric: string; op: string; value: number; score: number | null }[] };
}

/** Một dòng tiến độ: agent nào đang làm gì trong lượt chat hiện tại. */
interface ProgressStep {
  agent: string;
  label: string;
  status: "running" | "done" | "error";
  details: string[];
}

const AGENT_LABELS: Record<string, string> = {
  "prompt-agent": "Prompt Agent",
  "data-agent": "Data Agent",
  "model-agent": "Model Agent",
  "operation-agent": "Operation Agent",
};

const JOB_END_EVENTS = ["job_done", "job_failed", "job_watch_timeout"];

interface PendingUpload {
  file: File;
  name: string;
  dataType: DataType;
}

const SUGGESTIONS = [
  "Tôi có những dataset nào?",
  "Dataset của tôi có những cột gì?",
  "Huấn luyện mô hình trên dataset của tôi",
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function extensionOf(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot >= 0 ? filename.slice(dot).toLowerCase() : "";
}

/** Trả về thông báo lỗi, hoặc null nếu file hợp lệ. */
function validateFile(file: File): string | null {
  const ext = extensionOf(file.name);
  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return `Chỉ nhận file CSV hoặc Excel (${ACCEPTED_EXTENSIONS.join(", ")}). "${file.name}" không được hỗ trợ.`;
  }
  if (file.size === 0) return `"${file.name}" là file rỗng.`;
  if (file.size > MAX_UPLOAD_BYTES) {
    return `"${file.name}" nặng ${formatSize(file.size)}, vượt giới hạn ${MAX_UPLOAD_MB} MB.`;
  }
  return null;
}

function defaultDatasetName(filename: string): string {
  const ext = extensionOf(filename);
  return (ext ? filename.slice(0, -ext.length) : filename).trim() || "dataset";
}

/**
 * Tải lên bằng XHR thay vì fetch: fetch không báo được tiến độ upload, mà file
 * 20 MB có thể mất vài giây - người dùng cần thấy thanh tiến độ chạy.
 */
function uploadWithProgress(
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
    xhr.onerror = () => reject(new Error("Không kết nối được tới agent API."));
    xhr.send(form);
  });
}

/**
 * Đọc luồng SSE từ một response fetch.
 *
 * Không dùng EventSource: nó chỉ gửi được GET, mà token phải nằm trong body
 * POST chứ không phải trên URL (URL hay bị ghi vào log).
 */
async function readSSE(res: Response, onEvent: (event: string, data: AgentEvent) => void) {
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

function firstLine(text: string, max = 70): string {
  const line = (text || "").split("\n")[0].trim();
  return line.length > max ? `${line.slice(0, max)}…` : line;
}

/** Cập nhật danh sách bước tiến độ theo một sự kiện. Trả về mảng mới (immutable). */
function applyProgress(steps: ProgressStep[], event: AgentEvent): ProgressStep[] {
  const agent = event.agent ?? "";
  const lastIndex = steps.map((s) => s.agent).lastIndexOf(agent);

  const patchLast = (patch: (step: ProgressStep) => ProgressStep) =>
    lastIndex < 0 ? steps : steps.map((step, i) => (i === lastIndex ? patch(step) : step));

  switch (event.type) {
    case "agent_start":
      return [
        ...steps,
        { agent, label: `${AGENT_LABELS[agent] ?? agent}: ${firstLine(event.task)}`, status: "running", details: [] },
      ];
    case "agent_done":
      return patchLast((step) => ({ ...step, status: event.ok ? "done" : "error" }));
    case "tool_call":
      if (!AGENT_LABELS[agent] || String(event.name).startsWith("ask_")) return steps;
      return patchLast((step) => ({ ...step, details: [...step.details, `${event.name} ${event.ok ? "✓" : "✗"}`] }));
    case "config_checked":
      return patchLast((step) => ({
        ...step,
        details: [...step.details, `validate_config: ${event.ok ? "hợp lệ" : "không hợp lệ"}`],
      }));
    case "job_started":
      return patchLast((step) => ({ ...step, details: [...step.details, `đã gửi job ${String(event.job_id).slice(0, 8)}`] }));
    default:
      return steps;
  }
}

/** In đậm **chữ** và `mã` trong một dòng. Dựng React node, KHÔNG dùng innerHTML. */
function renderInline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={i} className="rounded bg-black/5 px-1 py-0.5 font-mono text-[12px] dark:bg-white/10">
          {part.slice(1, -1)}
        </code>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

/**
 * Hiển thị câu trả lời Markdown cơ bản của agent: đoạn văn, gạch đầu dòng,
 * tiêu đề, in đậm, mã. Bảng giữ nguyên dạng chữ đơn cách cho thẳng cột.
 * Tự viết thay vì thêm react-markdown để không kéo thêm dependency.
 */
function RichText({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let list: ReactNode[] = [];
  let table: string[] = [];

  const flushList = () => {
    if (list.length) {
      blocks.push(<ul key={`l${blocks.length}`} className="my-1 list-disc space-y-0.5 pl-5">{list}</ul>);
      list = [];
    }
  };
  const flushTable = () => {
    if (table.length) {
      blocks.push(
        <pre key={`t${blocks.length}`} className="my-1 overflow-x-auto rounded-md bg-black/5 p-2 font-mono text-[11px] leading-snug dark:bg-white/10">
          {table.join("\n")}
        </pre>,
      );
      table = [];
    }
  };

  lines.forEach((raw, i) => {
    const line = raw.trimEnd();
    if (line.trim().startsWith("|")) {
      flushList();
      table.push(line);
      return;
    }
    flushTable();

    const bullet = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (bullet) {
      list.push(<li key={i}>{renderInline(bullet[1])}</li>);
      return;
    }
    flushList();

    if (!line.trim()) return;
    if (/^-{3,}$/.test(line.trim())) {
      blocks.push(<hr key={i} className="my-2 border-black/10 dark:border-white/10" />);
      return;
    }
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    if (heading) {
      blocks.push(<p key={i} className="mt-2 font-semibold">{renderInline(heading[1])}</p>);
      return;
    }
    blocks.push(<p key={i} className="my-1">{renderInline(line)}</p>);
  });
  flushList();
  flushTable();

  return <div className="break-words">{blocks}</div>;
}

export default function AgentChat() {
  const { data: session } = useSession();
  const token = session?.user?.access_token ?? null;

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const [pending, setPending] = useState<PendingUpload | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  // Tiến độ của lượt chat đang chạy: agent nào được giao việc gì.
  const [progress, setProgress] = useState<ProgressStep[]>([]);
  // job_id đang được agent theo dõi nền - có job thì mới mở kênh /agent/events.
  const [watching, setWatching] = useState<string[]>([]);

  const nextId = useRef(1);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Token mới nhất cho kênh sự kiện nền: kênh mở lại mỗi phút và phải gửi token
  // còn hạn, để watcher theo dõi job hàng giờ không bị 401.
  const tokenRef = useRef(token);
  tokenRef.current = token;
  // seq lớn nhất đã nhận, và các sự kiện job đã hiện - hai luồng SSE cùng đọc
  // một kênh nên một sự kiện có thể tới hai lần.
  const lastSeqRef = useRef(0);
  const shownJobEvents = useRef(new Set<number>());

  const uploading = uploadProgress !== null;
  const busy = sending || uploading;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending, pending, uploadProgress, progress]);

  function push(message: Omit<Message, "id">) {
    setMessages((prev) => [...prev, { ...message, id: nextId.current++ }]);
  }

  /** Job kết thúc: hiện thẻ kết quả, bỏ khỏi danh sách đang theo dõi. */
  function handleJobEvent(event: AgentEvent) {
    if (!event.type || !JOB_END_EVENTS.includes(event.type) || event.seq === undefined) return;
    if (shownJobEvents.current.has(event.seq)) return;
    shownJobEvents.current.add(event.seq);

    const job = event as JobEvent;
    push({ role: "system", variant: "job", text: event.type, job });
    setWatching((prev) => prev.filter((id) => id !== job.job_id));
  }

  function trackSeq(event: AgentEvent) {
    if (event.seq !== undefined && event.seq > lastSeqRef.current) lastSeqRef.current = event.seq;
  }

  // Vòng lặp nền sống qua nhiều lần render - gọi bản handleJobEvent mới nhất qua ref.
  const handleJobEventRef = useRef(handleJobEvent);
  handleJobEventRef.current = handleJobEvent;

  // Kênh sự kiện nền: chỉ mở khi có job đang được theo dõi.
  const hasWatching = watching.length > 0;
  useEffect(() => {
    if (!sessionId || !hasWatching) return;
    const controller = new AbortController();
    let stopped = false;

    (async () => {
      let failures = 0;
      while (!stopped) {
        try {
          const res = await fetch(`${AGENT_API}/agent/events`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, access_token: tokenRef.current, after: lastSeqRef.current }),
            signal: controller.signal,
          });
          if (res.status === 404) return; // phiên đã bị dọn trên server
          if (!res.ok) throw new Error(`HTTP ${res.status}`);

          failures = 0;
          await readSSE(res, (name, data) => {
            trackSeq(data);
            handleJobEventRef.current(data);
            if (name === "reconnect" && Array.isArray(data.watching)) setWatching(data.watching);
          });
        } catch {
          if (stopped) return;
          failures += 1;
          // Agent API khởi động lại hoặc mất mạng: chờ lâu dần rồi thử lại.
          await new Promise((resolve) => setTimeout(resolve, Math.min(30_000, 2_000 * failures)));
        }
      }
    })();

    return () => {
      stopped = true;
      controller.abort();
    };
  }, [sessionId, hasWatching]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || busy) return;

    push({ role: "user", text: content });
    setInput("");
    setSending(true);
    setProgress([]);

    try {
      const res = await fetch(`${AGENT_API}/agent/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          session_id: sessionId,
          // Agent dùng luôn token của phiên web, không tự đăng nhập lại.
          access_token: token,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }

      let reply: AgentEvent | null = null;
      let failure: string | null = null;
      await readSSE(res, (name, data) => {
        if (name === "session") setSessionId(data.session_id);
        else if (name === "reply") reply = data;
        else if (name === "error") failure = data.detail || `HTTP ${data.status_code}`;
        else {
          trackSeq(data);
          handleJobEvent(data);
          setProgress((prev) => applyProgress(prev, data));
        }
      });

      if (failure) throw new Error(failure);
      if (!reply) throw new Error("Kết nối bị ngắt trước khi agent trả lời.");
      const done = reply as AgentEvent;
      push({ role: "agent", text: done.reply, tools: done.tools, agents: done.agents });
      if (Array.isArray(done.watching)) setWatching(done.watching);
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      push({ role: "system", variant: "error", text: `Không gọi được agent: ${reason}` });
    } finally {
      setSending(false);
      setProgress([]);
    }
  }

  function pickFile(file: File | undefined) {
    setFileError(null);
    if (!file) return;
    const problem = validateFile(file);
    if (problem) {
      setFileError(problem);
      setPending(null);
      return;
    }
    setPending({ file, name: defaultDatasetName(file.name), dataType: "classification" });
  }

  async function upload() {
    if (!pending || busy) return;
    if (!token) {
      setFileError("Bạn cần đăng nhập để tải dataset lên.");
      return;
    }

    const form = new FormData();
    form.append("file", pending.file);
    form.append("data_name", pending.name.trim() || defaultDatasetName(pending.file.name));
    form.append("data_type", pending.dataType);
    form.append("access_token", token);
    if (sessionId) form.append("session_id", sessionId);

    setFileError(null);
    setUploadProgress(0);
    try {
      const { status, body } = await uploadWithProgress(form, setUploadProgress);
      if (status !== 200) throw new Error(body?.detail || `HTTP ${status}`);

      setSessionId(body.session_id);
      push({
        role: "system",
        variant: "upload",
        datasetName: body.dataset.name,
        text: `${body.dataset.filename} · ${formatSize(body.dataset.size_bytes)} · ${
          body.dataset.type === "regression" ? "Hồi quy" : "Phân loại"
        }`,
      });
      setPending(null);
    } catch (error) {
      setFileError(error instanceof Error ? error.message : String(error));
    } finally {
      setUploadProgress(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function reset() {
    if (sessionId) {
      await fetch(`${AGENT_API}/agent/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "reset", session_id: sessionId }),
      }).catch(() => undefined);
    }
    setMessages([]);
    setSessionId(null);
    setPending(null);
    setFileError(null);
    // Job vẫn chạy trên backend, chỉ là cuộc trò chuyện mới không theo dõi nữa.
    setWatching([]);
    lastSeqRef.current = 0;
    shownJobEvents.current.clear();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter gửi, Shift+Enter xuống dòng. Bỏ qua khi đang gõ tiếng Việt (IME).
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      send(input);
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!busy) pickFile(event.dataTransfer.files?.[0]);
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label="Mở trợ lý HAutoML"
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-500/30 transition hover:scale-105 hover:shadow-xl"
      >
        <Bot className="h-6 w-6" />
      </button>
    );
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        if (!busy && token) setDragging(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false);
      }}
      onDrop={onDrop}
      className="fixed bottom-6 right-6 z-50 flex h-[640px] max-h-[calc(100vh-3rem)] w-[calc(100vw-2rem)] max-w-[440px] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-900"
    >
      {/* Đầu khung */}
      <header className="flex items-center justify-between bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-3 text-white">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/20">
            <Bot className="h-5 w-5" />
          </div>
          <div className="leading-tight">
            <p className="font-semibold">Trợ lý HAutoML</p>
            <p className="flex items-center gap-1.5 text-xs text-white/80">
              <span className={`h-2 w-2 rounded-full ${token ? "bg-emerald-300" : "bg-amber-300"}`} />
              {token ? "Sẵn sàng" : "Chưa đăng nhập"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={reset} title="Cuộc trò chuyện mới" aria-label="Cuộc trò chuyện mới" className="rounded-lg p-2 transition hover:bg-white/15">
            <RotateCcw className="h-4 w-4" />
          </button>
          <button onClick={() => setOpen(false)} title="Thu nhỏ" aria-label="Thu nhỏ" className="rounded-lg p-2 transition hover:bg-white/15">
            <X className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* Nội dung hội thoại */}
      <div className="relative flex-1 space-y-3 overflow-y-auto bg-gray-50 px-4 py-4 dark:bg-gray-950">
        {messages.length === 0 && (
          <div className="flex flex-col items-center pt-6 text-center">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300">
              <Sparkles className="h-6 w-6" />
            </div>
            <p className="font-semibold text-gray-800 dark:text-gray-100">Xin chào!</p>
            <p className="mt-1 max-w-[300px] text-sm text-gray-500 dark:text-gray-400">
              {token
                ? "Tôi giúp bạn tra cứu dataset, chọn cấu hình và huấn luyện mô hình."
                : "Hãy đăng nhập để tôi truy cập được dữ liệu của bạn."}
            </p>

            {token && (
              <>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="mt-4 flex w-full items-center gap-3 rounded-xl border-2 border-dashed border-violet-200 bg-white px-4 py-3 text-left transition hover:border-violet-400 hover:bg-violet-50 dark:border-violet-500/30 dark:bg-gray-900 dark:hover:bg-violet-500/10"
                >
                  <UploadCloud className="h-6 w-6 shrink-0 text-violet-500" />
                  <span>
                    <span className="block text-sm font-medium text-gray-800 dark:text-gray-100">Tải dataset lên</span>
                    <span className="block text-xs text-gray-500 dark:text-gray-400">
                      Kéo thả hoặc bấm để chọn · CSV, Excel · tối đa {MAX_UPLOAD_MB} MB
                    </span>
                  </span>
                </button>

                <div className="mt-3 w-full space-y-2">
                  {SUGGESTIONS.map((text) => (
                    <button
                      key={text}
                      onClick={() => send(text)}
                      className="block w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-left text-sm text-gray-700 transition hover:border-violet-300 hover:text-violet-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:border-violet-500/50"
                    >
                      {text}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {messages.map((message) => {
          if (message.role === "system" && message.variant === "upload") {
            return (
              <div key={message.id} className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-500/30 dark:bg-emerald-500/10">
                <div className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  <div className="min-w-0 text-sm">
                    <p className="font-medium text-emerald-900 dark:text-emerald-100">
                      Đã thêm <strong>{message.datasetName}</strong> vào kho dataset của bạn
                    </p>
                    <p className="mt-0.5 truncate text-xs text-emerald-700 dark:text-emerald-300">{message.text}</p>
                  </div>
                </div>
                <div className="mt-2.5 flex flex-wrap gap-2 pl-7">
                  <button
                    onClick={() => send(`Phân tích dataset "${message.datasetName}" vừa tải lên: có những cột gì, cột nào làm biến mục tiêu được?`)}
                    disabled={busy}
                    className="rounded-full bg-white px-3 py-1 text-xs font-medium text-emerald-800 shadow-sm ring-1 ring-emerald-200 transition hover:bg-emerald-100 disabled:opacity-50 dark:bg-gray-900 dark:text-emerald-200 dark:ring-emerald-500/30"
                  >
                    Phân tích dataset này
                  </button>
                  <button
                    onClick={() => send(`Huấn luyện mô hình trên dataset "${message.datasetName}" vừa tải lên`)}
                    disabled={busy}
                    className="rounded-full bg-white px-3 py-1 text-xs font-medium text-emerald-800 shadow-sm ring-1 ring-emerald-200 transition hover:bg-emerald-100 disabled:opacity-50 dark:bg-gray-900 dark:text-emerald-200 dark:ring-emerald-500/30"
                  >
                    Huấn luyện mô hình
                  </button>
                </div>
              </div>
            );
          }

          if (message.role === "system" && message.variant === "job" && message.job) {
            const job = message.job;
            const succeeded = message.text === "job_done";
            const passed = job.verification?.passed;
            return (
              <div
                key={message.id}
                className={`rounded-xl border p-3 text-sm ${
                  succeeded
                    ? "border-emerald-200 bg-emerald-50 dark:border-emerald-500/30 dark:bg-emerald-500/10"
                    : "border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10"
                }`}
              >
                <div className="flex items-start gap-2.5">
                  {succeeded ? (
                    <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  ) : (
                    <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
                  )}
                  <div className="min-w-0 text-gray-800 dark:text-gray-100">
                    <p className="font-medium">
                      {succeeded ? "Huấn luyện xong" : "Job chưa hoàn tất"}
                      <span className="ml-1.5 font-mono text-[11px] text-gray-500">{String(job.job_id).slice(0, 8)}</span>
                    </p>
                    {succeeded ? (
                      <>
                        <p className="mt-0.5">
                          <strong>{job.best_model}</strong> · {job.metric_sort} = {typeof job.best_score === "number" ? job.best_score.toFixed(4) : job.best_score}
                        </p>
                        {passed !== null && passed !== undefined && (
                          <p className={`mt-0.5 text-xs ${passed ? "text-emerald-700 dark:text-emerald-300" : "text-amber-700 dark:text-amber-300"}`}>
                            {passed ? "Đạt yêu cầu bạn đặt ra" : "Chưa đạt yêu cầu bạn đặt ra"}:{" "}
                            {job.verification!.checks
                              .map((c) => `${c.metric} ${c.op} ${c.value} (thực tế ${c.score ?? "—"})`)
                              .join(", ")}
                          </p>
                        )}
                      </>
                    ) : (
                      <p className="mt-0.5 break-words text-xs">{job.error || "Không rõ lý do."}</p>
                    )}
                  </div>
                </div>
                {succeeded && (
                  <div className="mt-2.5 flex flex-wrap gap-2 pl-7">
                    <button
                      onClick={() => send(`Kích hoạt model của job ${job.job_id} để dùng dự đoán`)}
                      disabled={busy}
                      className="rounded-full bg-white px-3 py-1 text-xs font-medium text-emerald-800 shadow-sm ring-1 ring-emerald-200 transition hover:bg-emerald-100 disabled:opacity-50 dark:bg-gray-900 dark:text-emerald-200 dark:ring-emerald-500/30"
                    >
                      Kích hoạt model
                    </button>
                    <button
                      onClick={() => send(`Giải thích kết quả job ${job.job_id}`)}
                      disabled={busy}
                      className="rounded-full bg-white px-3 py-1 text-xs font-medium text-emerald-800 shadow-sm ring-1 ring-emerald-200 transition hover:bg-emerald-100 disabled:opacity-50 dark:bg-gray-900 dark:text-emerald-200 dark:ring-emerald-500/30"
                    >
                      Giải thích kết quả
                    </button>
                  </div>
                )}
              </div>
            );
          }

          if (message.role === "system") {
            return (
              <div key={message.id} className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span className="break-words">{message.text}</span>
              </div>
            );
          }

          if (message.role === "user") {
            return (
              <div key={message.id} className="flex justify-end">
                <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-violet-600 px-3.5 py-2 text-sm text-white shadow-sm">
                  {message.text}
                </div>
              </div>
            );
          }

          return (
            <div key={message.id} className="flex items-end gap-2">
              <div className="mb-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-100 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300">
                <Bot className="h-4 w-4" />
              </div>
              <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-gray-200 bg-white px-3.5 py-2 text-sm text-gray-800 shadow-sm dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100">
                {message.agents && message.agents.length > 0 && (
                  <div className="mb-1 flex flex-wrap items-center gap-1">
                    <Users className="h-3 w-3 text-violet-400" />
                    {message.agents.map((agent) => (
                      <span key={agent} className="rounded bg-violet-50 px-1.5 py-0.5 text-[10px] font-medium text-violet-600 dark:bg-violet-500/10 dark:text-violet-300">
                        {AGENT_LABELS[agent] ?? agent}
                      </span>
                    ))}
                  </div>
                )}
                {message.tools && message.tools.length > 0 && (
                  <div className="mb-1.5 flex flex-wrap items-center gap-1">
                    <Wrench className="h-3 w-3 text-gray-400" />
                    {message.tools.map((tool, i) => (
                      <span key={i} className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[10px] text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                        {tool}
                      </span>
                    ))}
                  </div>
                )}
                <RichText text={message.text} />
              </div>
            </div>
          );
        })}

        {sending && (
          <div className="flex items-end gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-violet-100 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300">
              <Bot className="h-4 w-4" />
            </div>
            {progress.length === 0 ? (
              <div className="flex gap-1 rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-900">
                {[0, 150, 300].map((delay) => (
                  <span key={delay} className="h-2 w-2 animate-bounce rounded-full bg-violet-400" style={{ animationDelay: `${delay}ms` }} />
                ))}
              </div>
            ) : (
              <div className="max-w-[85%] space-y-1.5 rounded-2xl rounded-bl-md border border-gray-200 bg-white px-3.5 py-2.5 text-xs dark:border-gray-700 dark:bg-gray-900">
                {progress.map((step, i) => (
                  <div key={i}>
                    <div className="flex items-start gap-1.5 text-gray-700 dark:text-gray-200">
                      {step.status === "running" ? (
                        <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-violet-500" />
                      ) : step.status === "done" ? (
                        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                      ) : (
                        <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-500" />
                      )}
                      <span className="break-words">{step.label}</span>
                    </div>
                    {step.details.length > 0 && (
                      <p className="ml-5 font-mono text-[10px] text-gray-400">{step.details.join(" · ")}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        <div ref={bottomRef} />

        {/* Lớp phủ khi kéo file vào khung */}
        {dragging && (
          <div className="pointer-events-none absolute inset-2 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-violet-400 bg-violet-50/90 text-violet-700 dark:bg-violet-950/90 dark:text-violet-200">
            <UploadCloud className="mb-2 h-10 w-10" />
            <p className="font-medium">Thả file vào đây</p>
            <p className="text-xs opacity-80">CSV, Excel · tối đa {MAX_UPLOAD_MB} MB</p>
          </div>
        )}
      </div>

      {/* Thẻ file đang chờ tải lên */}
      {(pending || fileError) && (
        <div className="border-t border-gray-200 bg-white px-3 pt-3 dark:border-gray-700 dark:bg-gray-900">
          {fileError && (
            <div className="mb-2 flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-500/10 dark:text-red-300">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span className="flex-1 break-words">{fileError}</span>
              <button onClick={() => setFileError(null)} aria-label="Đóng thông báo" className="shrink-0 opacity-70 hover:opacity-100">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {pending && (
            <div className="mb-1 rounded-xl border border-violet-200 bg-violet-50/60 p-3 dark:border-violet-500/30 dark:bg-violet-500/10">
              <div className="flex items-center gap-2.5">
                <FileSpreadsheet className="h-8 w-8 shrink-0 text-violet-600 dark:text-violet-300" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-800 dark:text-gray-100">{pending.file.name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{formatSize(pending.file.size)}</p>
                </div>
                {!uploading && (
                  <button onClick={() => setPending(null)} aria-label="Bỏ file" className="rounded-md p-1 text-gray-400 hover:bg-white hover:text-gray-600 dark:hover:bg-gray-800">
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>

              {uploading ? (
                <div className="mt-3">
                  <div className="mb-1 flex justify-between text-xs text-violet-700 dark:text-violet-300">
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      {uploadProgress! < 100 ? "Đang tải lên…" : "Đang xử lý dữ liệu…"}
                    </span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-violet-100 dark:bg-violet-900/50">
                    <div className="h-full rounded-full bg-violet-600 transition-all" style={{ width: `${uploadProgress}%` }} />
                  </div>
                </div>
              ) : (
                <div className="mt-3 space-y-2">
                  <div className="flex gap-2">
                    <input
                      value={pending.name}
                      onChange={(event) => setPending({ ...pending, name: event.target.value })}
                      placeholder="Tên dataset"
                      maxLength={100}
                      className="min-w-0 flex-1 rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-violet-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                    />
                    <select
                      value={pending.dataType}
                      onChange={(event) => setPending({ ...pending, dataType: event.target.value as DataType })}
                      className="rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-sm outline-none focus:border-violet-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                    >
                      <option value="classification">Phân loại</option>
                      <option value="regression">Hồi quy</option>
                    </select>
                  </div>
                  <button
                    onClick={upload}
                    disabled={busy}
                    className="flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600 py-2 text-sm font-medium text-white transition hover:bg-violet-700 disabled:opacity-50"
                  >
                    <UploadCloud className="h-4 w-4" />
                    Thêm vào kho dataset
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Ô nhập */}
      <div className="border-t border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
        <div className="flex items-end gap-2 rounded-xl border border-gray-300 bg-white px-2 py-1.5 transition focus-within:border-violet-500 focus-within:ring-2 focus-within:ring-violet-500/20 dark:border-gray-600 dark:bg-gray-800">
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT_ATTR}
            className="hidden"
            onChange={(event) => pickFile(event.target.files?.[0])}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={busy || !token}
            title={`Tải dataset lên (CSV, Excel · tối đa ${MAX_UPLOAD_MB} MB)`}
            aria-label="Tải dataset lên"
            className="mb-0.5 rounded-lg p-1.5 text-gray-500 transition hover:bg-violet-50 hover:text-violet-600 disabled:cursor-not-allowed disabled:opacity-40 dark:text-gray-400 dark:hover:bg-violet-500/10"
          >
            <Paperclip className="h-5 w-5" />
          </button>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            disabled={busy || !token}
            placeholder={token ? "Hỏi về dataset, huấn luyện mô hình…" : "Đăng nhập để bắt đầu"}
            className="max-h-28 min-h-[36px] flex-1 resize-none bg-transparent py-1.5 text-sm outline-none placeholder:text-gray-400 disabled:cursor-not-allowed dark:text-gray-100"
          />
          <button
            onClick={() => send(input)}
            disabled={busy || !input.trim() || !token}
            aria-label="Gửi"
            className="mb-0.5 rounded-lg bg-violet-600 p-1.5 text-white transition hover:bg-violet-700 disabled:opacity-30"
          >
            {sending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
          </button>
        </div>
        <p className="mt-1.5 text-center text-[11px] text-gray-400">
          Enter để gửi · Shift+Enter xuống dòng · 📎 CSV, Excel tối đa {MAX_UPLOAD_MB} MB
        </p>
      </div>
    </div>
  );
}
