"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AgentHttpError,
  defaultDatasetName,
  fetchHealth,
  postJson,
  readSSE,
  uploadWithProgress,
} from "../lib/agentApi";
import {
  applyJobEvent,
  applyTurnEvent,
  createSeqTracker,
  emptyTrace,
  mergeJobFromApi,
  type JobView,
  type TurnTrace,
} from "../lib/eventAdapter";
import type { AgentEvent, ChatReply, HealthInfo, UploadedDataset } from "../lib/events";

export type ProblemType = "classification" | "regression";

export interface PendingUpload {
  file: File;
  name: string;
  dataType: ProblemType;
}

/** Lỗi hiển thị cho người dùng: mã để dịch (Agent.errors.*) + chi tiết từ server nếu có. */
export interface AgentError {
  code: "busy" | "auth" | "server" | "disconnected" | "network";
  detail?: string;
}

export type ChatItem =
  | { id: number; kind: "user"; at: number; text: string }
  | { id: number; kind: "agent"; at: number; text: string; trace: TurnTrace; agents: string[] }
  | { id: number; kind: "upload"; at: number; dataset: UploadedDataset }
  | { id: number; kind: "error"; at: number; error: AgentError; retryText?: string; trace?: TurnTrace }
  /** Job vừa kết thúc - hiện thẻ kết quả ở cuối hội thoại. */
  | { id: number; kind: "job"; at: number; jobId: string }
  /** Trang vừa tải lại và nối lại được phiên cũ trên agent server. */
  | { id: number; kind: "restored"; at: number; jobIds: string[] };

// Omit không phân phối qua union - cần bản này để push() nhận đúng từng loại item.
type NewChatItem = ChatItem extends infer T ? (T extends ChatItem ? Omit<T, "id" | "at"> : never) : never;

export type HealthState =
  | { state: "checking" }
  | { state: "ok"; info: HealthInfo }
  | { state: "degraded"; info: HealthInfo }
  | { state: "offline" };

/** Kênh sự kiện nền: chỉ mở khi có job đang được theo dõi. */
export type StreamState = "idle" | "live" | "reconnecting";

export interface ActiveDataset {
  id: string;
  name?: string;
  problemType?: ProblemType;
}

/** Thông báo cho trình đọc màn hình (aria-live). `n` tăng để đọc lại cùng nội dung. */
export interface Announcement {
  code: "reply" | "jobStarted" | "jobDone" | "jobFailed";
  values?: Record<string, string>;
  n: number;
}

const HEALTH_INTERVAL_MS = 60_000;
const END_EVENTS = new Set(["job_done", "job_failed", "job_watch_timeout"]);
// Sự kiện cũ nằm sẵn trong bộ đệm server và tới gần như ngay - đợi chừng này là đủ.
const RESTORE_REPLAY_MS = 4_000;

/**
 * Chỉ lưu session_id (không bao giờ lưu token), trong sessionStorage của tab:
 * tải lại trang vẫn nối lại được phiên, đóng tab là hết. Mọi truy cập đều có
 * thể ném lỗi (chế độ riêng tư, chặn storage) nên luôn bọc try/catch.
 */
function storageKey(userKey: string) {
  return `hautoml:agent-session:${userKey}`;
}
function readStoredSession(userKey: string): string | null {
  try {
    return window.sessionStorage.getItem(storageKey(userKey));
  } catch {
    return null;
  }
}
function writeStoredSession(userKey: string, sessionId: string | null) {
  try {
    if (sessionId) window.sessionStorage.setItem(storageKey(userKey), sessionId);
    else window.sessionStorage.removeItem(storageKey(userKey));
  } catch {
    // Không lưu được thì chỉ mất khả năng khôi phục sau khi tải lại.
  }
}

/**
 * Toàn bộ trạng thái một phiên chat với agent. Giao diện chỉ đọc state và gọi
 * action - không tự gọi API agent hay đọc SSE.
 *
 * Tin nhắn chỉ nằm trong bộ nhớ trang: tải lại trang thì nối lại được phiên
 * (agent vẫn nhớ ngữ cảnh, job vẫn được theo dõi) nhưng không hiện lại được
 * tin nhắn cũ - agent server không có API lấy lịch sử.
 */
export function useAgentSession(token: string, userKey: string) {
  const [items, setItems] = useState<ChatItem[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [liveTrace, setLiveTrace] = useState<TurnTrace | null>(null);
  const [jobs, setJobs] = useState<Record<string, JobView>>({});
  const [watching, setWatching] = useState<string[]>([]);
  const [stream, setStream] = useState<StreamState>("idle");
  const [health, setHealth] = useState<HealthState>({ state: "checking" });
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [activeDataset, setActiveDataset] = useState<ActiveDataset | null>(null);
  const [announcement, setAnnouncement] = useState<Announcement | null>(null);

  const nextId = useRef(1);
  // Token mới nhất cho kênh sự kiện nền: kênh mở lại mỗi phút và phải gửi token
  // còn hạn, để watcher theo dõi job hàng giờ không bị 401.
  const tokenRef = useRef(token);
  tokenRef.current = token;
  // Hai luồng SSE (lượt chat và kênh nền) cùng đọc một EventBus nên một sự kiện
  // có thể tới hai lần - xử lý mỗi seq đúng một lần.
  const seq = useRef(createSeqTracker());
  const turnActive = useRef(false);
  const traceRef = useRef<TurnTrace>(emptyTrace());
  const finishedJobs = useRef(new Set<string>());
  // Đang phát lại sự kiện cũ sau khi tải lại trang: job xong hiện trong thẻ khôi
  // phục, không chèn từng thẻ kết quả riêng.
  const replaying = useRef(false);
  // Tăng mỗi lần "Cuộc trò chuyện mới": luồng SSE của phiên cũ có thể còn đẩy
  // sự kiện trong khoảng trước khi effect kịp đóng nó - sự kiện đó không được
  // lọt vào phiên mới (sẽ làm seq.last nhảy vọt và bỏ sót sự kiện của phiên mới).
  const generation = useRef(0);

  const uploading = uploadProgress !== null;
  const busy = sending || uploading || restoring;

  const push = useCallback((item: NewChatItem) => {
    setItems((prev) => [...prev, { ...item, at: Date.now(), id: nextId.current++ } as ChatItem]);
  }, []);

  const announce = useCallback((code: Announcement["code"], values?: Record<string, string>) => {
    setAnnouncement((prev) => ({ code, values, n: (prev?.n ?? 0) + 1 }));
  }, []);

  /** Điểm vào DUY NHẤT cho mọi sự kiện có seq, bất kể tới từ luồng nào. */
  const ingest = useCallback(
    (event: AgentEvent) => {
      if (!seq.current.accept(event.seq)) return;

      if (turnActive.current) {
        const next = applyTurnEvent(traceRef.current, event);
        if (next !== traceRef.current) {
          traceRef.current = next;
          setLiveTrace(next);
        }
      }

      setJobs((prev) => applyJobEvent(prev, event));

      const jobId = event.job_id ? String(event.job_id) : null;
      if (!jobId) return;
      if (event.type === "job_started") {
        setWatching((prev) => (prev.includes(jobId) ? prev : [...prev, jobId]));
        if (!replaying.current) announce("jobStarted", { id: jobId.slice(0, 8) });
      } else if (event.type && END_EVENTS.has(event.type)) {
        setWatching((prev) => prev.filter((id) => id !== jobId));
        if (!finishedJobs.current.has(jobId)) {
          finishedJobs.current.add(jobId);
          if (!replaying.current) {
            push({ kind: "job", jobId });
            announce(event.type === "job_done" ? "jobDone" : "jobFailed", { id: jobId.slice(0, 8) });
          }
        }
      }
    },
    [announce, push],
  );

  // session_id theo tab: lưu mỗi khi đổi để tải lại trang còn nối lại được.
  useEffect(() => {
    if (sessionId) writeStoredSession(userKey, sessionId);
  }, [sessionId, userKey]);

  // Tải lại trang: nối lại phiên cũ nếu agent server còn giữ nó.
  useEffect(() => {
    const stored = readStoredSession(userKey);
    if (!stored) return;

    const controller = new AbortController();
    let cancelled = false;
    const gen = generation.current;
    const replayed = new Set<string>();
    setRestoring(true);
    replaying.current = true;

    (async () => {
      const timer = window.setTimeout(() => controller.abort(), RESTORE_REPLAY_MS);
      try {
        const res = await postJson(
          "/agent/events",
          { session_id: stored, access_token: tokenRef.current, after: 0 },
          controller.signal,
        );
        if (!res.ok) {
          // 404: server đã dọn phiên (khởi động lại / quá hạn). 401/403: không phải chủ phiên.
          if (!cancelled) writeStoredSession(userKey, null);
          return;
        }
        await readSSE(res, (name, data) => {
          if (name === "reconnect" || gen !== generation.current) return;
          if (data.job_id && (data.type === "job_started" || data.type === "job_watch")) replayed.add(String(data.job_id));
          ingest(data);
        }).catch(() => undefined); // abort sau RESTORE_REPLAY_MS là bình thường
      } catch {
        // Không tới được agent server: giữ session_id, lần tải sau thử lại.
        return;
      } finally {
        window.clearTimeout(timer);
        replaying.current = false;
        if (!cancelled) setRestoring(false);
      }
      if (cancelled) return;
      setSessionId(stored);
      push({ kind: "restored", jobIds: [...replayed] });
    })();

    return () => {
      cancelled = true;
      replaying.current = false;
      controller.abort();
      setRestoring(false);
    };
  }, [ingest, push, userKey]);

  // Trạng thái agent server. Upload vẫn chạy được khi LLM chưa cấu hình.
  useEffect(() => {
    const controller = new AbortController();
    const check = () =>
      fetchHealth(controller.signal)
        .then((info) => setHealth(info.llm_ready ? { state: "ok", info } : { state: "degraded", info }))
        .catch(() => {
          if (!controller.signal.aborted) setHealth({ state: "offline" });
        });
    check();
    const timer = window.setInterval(check, HEALTH_INTERVAL_MS);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, []);

  // Kênh sự kiện nền: chỉ mở khi có job đang được theo dõi.
  const hasWatching = watching.length > 0;
  useEffect(() => {
    if (!sessionId || !hasWatching) {
      setStream("idle");
      return;
    }
    const controller = new AbortController();
    let stopped = false;
    const gen = generation.current;

    (async () => {
      let failures = 0;
      while (!stopped) {
        try {
          const res = await postJson(
            "/agent/events",
            { session_id: sessionId, access_token: tokenRef.current, after: seq.current.last },
            controller.signal,
          );
          if (res.status === 404) {
            // Phiên đã bị dọn trên server: không còn gì để theo dõi.
            setStream("idle");
            setWatching([]);
            return;
          }
          if (!res.ok) throw new AgentHttpError(res.status, `HTTP ${res.status}`);

          failures = 0;
          setStream("live");
          await readSSE(res, (name, data) => {
            if (gen !== generation.current) return;
            if (name === "reconnect") {
              if (Array.isArray(data.watching)) setWatching(data.watching);
              return;
            }
            ingest(data);
          });
        } catch {
          if (stopped) return;
          failures += 1;
          setStream("reconnecting");
          // Agent API khởi động lại hoặc mất mạng: chờ lâu dần rồi thử lại.
          await new Promise((resolve) => setTimeout(resolve, Math.min(30_000, 2_000 * failures)));
        }
      }
    })();

    return () => {
      stopped = true;
      controller.abort();
    };
  }, [sessionId, hasWatching, ingest]);

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (!content || busy) return;

      push({ kind: "user", text: content });
      setSending(true);
      turnActive.current = true;
      traceRef.current = emptyTrace();
      setLiveTrace(traceRef.current);

      // Đã nhận được phản hồi từ server chưa: mất kết nối SAU mốc này thì lượt
      // chat có thể vẫn chạy trên server, gửi lại có thể tạo job trùng.
      let started = false;
      try {
        const res = await postJson("/agent/chat/stream", { message: content, session_id: sessionId, access_token: token });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new AgentHttpError(res.status, typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
        }
        started = true;

        let reply: ChatReply | null = null;
        let failure: AgentHttpError | null = null;
        await readSSE(res, (name, data) => {
          if (name === "session") setSessionId(data.session_id);
          else if (name === "reply") reply = data as ChatReply;
          else if (name === "error") failure = new AgentHttpError(data.status_code ?? 502, data.detail || "");
          else ingest(data);
        });

        if (failure) throw failure;
        if (!reply) throw new Error("disconnected");
        const done = reply as ChatReply;
        if (done.session_id) setSessionId(done.session_id);
        push({ kind: "agent", text: done.reply, trace: traceRef.current, agents: done.agents ?? [] });
        announce("reply");
        if (Array.isArray(done.watching)) setWatching(done.watching);
        const datasetId = traceRef.current.datasetId;
        if (datasetId) setActiveDataset((prev) => (prev?.id === datasetId ? prev : { id: datasetId }));
      } catch (error) {
        const trace = traceRef.current.steps.length ? traceRef.current : undefined;
        if (error instanceof AgentHttpError && error.status === 409) {
          push({ kind: "error", trace, error: { code: "busy" } });
        } else if (error instanceof AgentHttpError && (error.status === 401 || error.status === 403)) {
          push({ kind: "error", trace, error: { code: "auth" } });
        } else if (error instanceof AgentHttpError) {
          push({ kind: "error", trace, error: { code: "server", detail: error.message }, retryText: content });
        } else if (started) {
          push({ kind: "error", trace, error: { code: "disconnected" } });
        } else {
          push({ kind: "error", error: { code: "network" }, retryText: content });
        }
      } finally {
        turnActive.current = false;
        setSending(false);
        setLiveTrace(null);
      }
    },
    [announce, busy, ingest, push, sessionId, token],
  );

  /** Trả về lỗi, hoặc null nếu tải lên thành công. */
  const upload = useCallback(
    async (pending: PendingUpload): Promise<AgentError | null> => {
      // Không trả null ở đây: null nghĩa là "đã tải lên", ô nhập sẽ bỏ file đi.
      if (busy) return { code: "busy" };
      const form = new FormData();
      form.append("file", pending.file);
      form.append("data_name", pending.name.trim() || defaultDatasetName(pending.file.name));
      form.append("data_type", pending.dataType);
      form.append("access_token", token);
      if (sessionId) form.append("session_id", sessionId);

      setUploadProgress(0);
      try {
        const { status, body } = await uploadWithProgress(form, setUploadProgress);
        if (status === 401 || status === 403) return { code: "auth" };
        if (status !== 200) return { code: "server", detail: typeof body?.detail === "string" ? body.detail : `HTTP ${status}` };
        const dataset = body.dataset as UploadedDataset;
        setSessionId(body.session_id);
        push({ kind: "upload", dataset });
        setActiveDataset({ id: dataset.id, name: dataset.name, problemType: dataset.type });
        return null;
      } catch {
        return { code: "network" };
      } finally {
        setUploadProgress(null);
      }
    },
    [busy, push, sessionId, token],
  );

  const reset = useCallback(async () => {
    if (busy) return;
    if (sessionId) {
      await postJson("/agent/reset", { message: "reset", session_id: sessionId, access_token: token }).catch(() => undefined);
    }
    generation.current += 1;
    writeStoredSession(userKey, null);
    setItems([]);
    setSessionId(null);
    // Job vẫn chạy trên backend, chỉ là cuộc trò chuyện mới không theo dõi nữa.
    setWatching([]);
    setJobs({});
    setActiveDataset(null);
    seq.current.reset();
    finishedJobs.current.clear();
  }, [busy, sessionId, token, userKey]);

  /** Ghép bản ghi job vừa lấy từ backend v1 (nút "Làm mới"). */
  const applyJobFromApi = useCallback((jobId: string, raw: Record<string, any>) => {
    setJobs((prev) => ({ ...prev, [jobId]: mergeJobFromApi(prev[jobId] ?? { jobId, status: "submitted" }, raw, Date.now()) }));
  }, []);

  const setJobActivated = useCallback((jobId: string, activated: boolean) => {
    setJobs((prev) => (prev[jobId] ? { ...prev, [jobId]: { ...prev[jobId], activated } } : prev));
  }, []);

  return {
    items,
    sending,
    restoring,
    busy,
    liveTrace,
    jobs,
    watching,
    stream,
    health,
    uploadProgress,
    activeDataset,
    announcement,
    setActiveDataset,
    send,
    upload,
    reset,
    applyJobFromApi,
    setJobActivated,
  };
}

