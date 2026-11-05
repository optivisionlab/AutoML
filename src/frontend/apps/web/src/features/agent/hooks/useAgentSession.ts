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
  markJobsLost,
  mergeJobFromApi,
  type JobView,
  type TurnTrace,
} from "../lib/eventAdapter";
import type { AgentEvent, ChatReply, HealthInfo, UploadedDataset } from "../lib/events";

// Cùng danh sách PROBLEM_TYPES của agent (src/backend/agent/tools.py).
export const PROBLEM_TYPES = ["classification", "regression", "time_series"] as const;
export type ProblemType = (typeof PROBLEM_TYPES)[number];
export const isProblemType = (value: unknown): value is ProblemType =>
  typeof value === "string" && (PROBLEM_TYPES as readonly string[]).includes(value);

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
  | { id: number; kind: "restored"; at: number; jobIds: string[] }
  /** Agent server đã mất phiên cũ (khởi động lại / quá hạn): agent không còn nhớ phần hội thoại phía trên. */
  | { id: number; kind: "notice"; at: number; code: "sessionLost" };

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
// Chờ phản hồi ĐẦU TIÊN của /agent/events khi khôi phục: server còn kiểm token qua
// backend (/me) trước khi trả lời, nên không gộp vào 4 giây đọc sự kiện ở trên.
const RESTORE_CONNECT_MS = 15_000;
// /agent/token thất bại (mạng chập chờn, agent khởi động lại) thì thử lại vài lần.
const TOKEN_RETRY_DELAYS_MS = [3_000, 10_000, 30_000];

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
  // Vừa khôi phục phiên sau khi tải lại trang: mở kênh nền một lần kể cả khi chưa
  // biết job nào đang chạy - sự kiện `reconnect` cuối kênh mang danh sách watching
  // thật (job cũ có thể đã trôi khỏi bộ đệm 500 sự kiện nên không phát lại được).
  const [probeEvents, setProbeEvents] = useState(false);

  const nextId = useRef(1);
  // Trang đã rời đi: không cập nhật state nữa, và huỷ luồng lượt chat đang đọc.
  const unmounted = useRef(false);
  const sendController = useRef<AbortController | null>(null);
  // Token mới nhất cho kênh sự kiện nền: kênh mở lại mỗi phút và phải gửi token
  // còn hạn, để watcher theo dõi job hàng giờ không bị 401.
  const tokenRef = useRef(token);
  tokenRef.current = token;
  // Hai luồng SSE (lượt chat và kênh nền) cùng đọc một EventBus nên một sự kiện
  // có thể tới hai lần - xử lý mỗi seq đúng một lần.
  const seq = useRef(createSeqTracker());
  const turnActive = useRef(false);
  // seq cuối của server lúc lượt chat đang chạy bắt đầu (sự kiện `session`, start_seq).
  // null = chưa biết / server cũ: mọi sự kiện trong lúc lượt chạy thuộc về lượt đó.
  const turnStartSeq = useRef<number | null>(null);
  const traceRef = useRef<TurnTrace>(emptyTrace());
  const finishedJobs = useRef(new Set<string>());
  // Đang phát lại sự kiện cũ sau khi tải lại trang: job xong hiện trong thẻ khôi
  // phục, không chèn từng thẻ kết quả riêng.
  const replaying = useRef(false);
  // Tăng mỗi lần "Cuộc trò chuyện mới": luồng SSE của phiên cũ có thể còn đẩy
  // sự kiện trong khoảng trước khi effect kịp đóng nó - sự kiện đó không được
  // lọt vào phiên mới (sẽ làm seq.last nhảy vọt và bỏ sót sự kiện của phiên mới).
  const generation = useRef(0);
  // session_id đang dùng, đọc được ngay trong callback SSE (state sessionId thì chưa kịp đổi).
  const sessionRef = useRef<string | null>(null);

  const uploading = uploadProgress !== null;
  const busy = sending || uploading || restoring;

  const push = useCallback((item: NewChatItem) => {
    setItems((prev) => [...prev, { ...item, at: Date.now(), id: nextId.current++ } as ChatItem]);
  }, []);

  const announce = useCallback((code: Announcement["code"], values?: Record<string, string>) => {
    setAnnouncement((prev) => ({ code, values, n: (prev?.n ?? 0) + 1 }));
  }, []);

  /**
   * Server không còn phiên cũ: job đang chạy không còn ai theo dõi (đánh dấu để
   * thẻ không quay mãi) và agent không nhớ phần hội thoại phía trên - báo rõ,
   * nhưng giữ nguyên các tin cũ trên màn hình.
   */
  const markSessionLost = useCallback(() => {
    setJobs((prev) => markJobsLost(prev));
    push({ kind: "notice", code: "sessionLost" });
  }, [push]);

  /** Quên phiên hiện tại ở phía trình duyệt: tin nhắn sau sẽ tạo phiên mới. */
  const forgetSession = useCallback(() => {
    generation.current += 1;
    writeStoredSession(userKey, null);
    sessionRef.current = null;
    setSessionId(null);
    setWatching([]);
    setProbeEvents(false);
    seq.current.reset();
  }, [userKey]);

  /**
   * Nhận session_id server trả về. Khác phiên đang dùng nghĩa là server đã cấp
   * phiên mới (phiên cũ quá hạn, bị dọn, hoặc agent khởi động lại): seq của phiên
   * mới bắt đầu lại từ 1, nên phải quên seq cũ - không thì mọi sự kiện mới bị coi
   * là trùng. Job của phiên cũ cũng không còn ai theo dõi trên server.
   */
  const adoptSession = useCallback(
    (id: string) => {
      if (!id) return;
      if (sessionRef.current && id !== sessionRef.current) {
        generation.current += 1;
        seq.current.reset();
        setWatching([]);
        setProbeEvents(false);
        markSessionLost();
      }
      sessionRef.current = id;
      setSessionId(id);
    },
    [markSessionLost],
  );

  /**
   * Điểm vào DUY NHẤT cho mọi sự kiện có seq, bất kể tới từ luồng nào.
   *
   * Sự kiện có seq <= start_seq của lượt đang chạy là sự kiện CŨ server phát lại
   * ở đầu luồng lượt chat (kênh nền đã bỏ lỡ chúng): vẫn cập nhật job, nhưng
   * không gắn vào timeline của lượt này. Không phân loại theo luồng: sự kiện của
   * lượt có thể tới qua kênh nền trước, bản trên luồng lượt chat bị coi là trùng.
   */
  const ingest = useCallback(
    (event: AgentEvent) => {
      if (!seq.current.accept(event.seq)) return;

      const start = turnStartSeq.current;
      const replayed = start !== null && typeof event.seq === "number" && event.seq <= start;
      if (turnActive.current && !replayed) {
        const next = applyTurnEvent(traceRef.current, event);
        if (next !== traceRef.current) {
          traceRef.current = next;
          setLiveTrace(next);
        }
      }

      setJobs((prev) => applyJobEvent(prev, event));

      const jobId = event.job_id ? String(event.job_id) : null;
      if (!jobId) return;
      // job_watch: job có sẵn được watch_job theo dõi - cũng phải mở kênh nền, kể cả khi phát lại sau tải lại trang.
      if (event.type === "job_started" || event.type === "job_watch") {
        // Job hết giờ chờ (job_watch_timeout) rồi được theo dõi lại: phải báo được kết quả lần nữa.
        finishedJobs.current.delete(jobId);
        setWatching((prev) => (prev.includes(jobId) ? prev : [...prev, jobId]));
        if (event.type === "job_started" && !replaying.current) announce("jobStarted", { id: jobId.slice(0, 8) });
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
      // Hai mốc riêng: chờ phản hồi đầu (server còn kiểm token), rồi mới tới 4 giây đọc phát lại.
      let timer = window.setTimeout(() => controller.abort(), RESTORE_CONNECT_MS);
      let outcome: "restored" | "gone" | "unreachable" = "unreachable";
      try {
        const res = await postJson(
          "/agent/events",
          { session_id: stored, access_token: tokenRef.current, after: 0 },
          controller.signal,
        );
        if (res.status === 404 || res.status === 403) {
          // 404: server đã dọn phiên (khởi động lại / quá hạn) hoặc phiên không phải
          // của người này (server trả 404 cho cả hai). 401 thì KHÔNG bỏ: chỉ là token
          // hết hạn - đăng nhập lại là dùng tiếp được đúng phiên đó.
          outcome = "gone";
        } else if (res.ok) {
          window.clearTimeout(timer);
          timer = window.setTimeout(() => controller.abort(), RESTORE_REPLAY_MS);
          outcome = "restored";
          await readSSE(res, (name, data) => {
            if (gen !== generation.current) return;
            if (name === "reconnect") {
              if (Array.isArray(data.watching)) setWatching(data.watching);
              return;
            }
            if (data.job_id && (data.type === "job_started" || data.type === "job_watch")) replayed.add(String(data.job_id));
            ingest(data);
          }).catch(() => undefined); // abort sau RESTORE_REPLAY_MS là bình thường
        }
        // Còn lại là 5xx (vd proxy báo agent đang khởi động lại): chưa chắc phiên đã mất - giữ lại.
      } catch {
        // Không tới được agent server (mạng, quá giờ chờ): giữ session_id, coi như chưa biết.
        outcome = "unreachable";
      } finally {
        window.clearTimeout(timer);
        replaying.current = false;
        if (!cancelled) setRestoring(false);
      }
      if (cancelled) return;
      if (outcome === "gone") {
        writeStoredSession(userKey, null);
        return;
      }
      // Kể cả khi chưa tới được server: dùng tiếp session_id đã lưu. Server thật sự mất
      // phiên thì lượt chat sau nhận session_id mới và adoptSession báo cho người dùng.
      adoptSession(stored);
      if (outcome === "restored") {
        push({ kind: "restored", jobIds: [...replayed] });
        setProbeEvents(true);
      }
    })();

    return () => {
      cancelled = true;
      replaying.current = false;
      controller.abort();
      setRestoring(false);
    };
  }, [adoptSession, ingest, push, userKey]);

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

  // Kênh sự kiện nền: chỉ mở khi có job đang được theo dõi (hoặc vừa khôi phục phiên).
  const hasWatching = watching.length > 0;
  const listen = hasWatching || probeEvents;
  useEffect(() => {
    if (!sessionId || !listen) {
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
            // Phiên đã bị dọn trên server (agent khởi động lại / quá hạn): không còn
            // ai theo dõi job, agent cũng không còn nhớ hội thoại - báo người dùng.
            if (!stopped && gen === generation.current) {
              setStream("idle");
              forgetSession();
              markSessionLost();
            }
            return;
          }
          if (!res.ok) throw new AgentHttpError(res.status, `HTTP ${res.status}`);

          setStream("live");
          let reconnected = false;
          await readSSE(res, (name, data) => {
            if (gen !== generation.current) return;
            if (name === "reconnect") {
              reconnected = true;
              if (Array.isArray(data.watching)) setWatching(data.watching);
              setProbeEvents(false);
              return;
            }
            ingest(data);
          });
          // Luồng đóng mà không có `reconnect` (proxy cắt, server trả 200 rồi đóng ngay):
          // coi là lỗi để còn chờ lâu dần - không mở lại liên tục.
          if (!reconnected) throw new Error("stream closed early");
          failures = 0;
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
  }, [sessionId, listen, ingest, forgetSession, markSessionLost]);

  // NextAuth làm mới access token (sống 15 phút) khi gần hết hạn. Báo ngay cho
  // agent: token chỉ tới agent theo request, nên một lượt chat dài qua lúc hết
  // hạn mà kênh nền chưa mở sẽ dùng token cũ và nhận 401 giữa lượt.
  // Chỉ coi là đã gửi khi server nhận: gửi hỏng thì thử lại vài lần.
  const sentToken = useRef(token);
  useEffect(() => {
    if (!sessionId || !token || token === sentToken.current) return;
    const controller = new AbortController();
    let timer: number | undefined;
    const attempt = (n: number) => {
      postJson("/agent/token", { session_id: sessionId, access_token: token }, controller.signal)
        .then((res) => {
          // 404: server không còn phiên này - gửi lại cũng vô ích; lượt chat sau mang token mới.
          if (res.ok || res.status === 404) {
            sentToken.current = token;
            return;
          }
          throw new AgentHttpError(res.status, `HTTP ${res.status}`);
        })
        .catch(() => {
          if (controller.signal.aborted || n >= TOKEN_RETRY_DELAYS_MS.length) return;
          timer = window.setTimeout(() => attempt(n + 1), TOKEN_RETRY_DELAYS_MS[n]);
        });
    };
    attempt(0);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [sessionId, token]);

  // Rời trang: huỷ luồng lượt chat đang đọc (lượt vẫn chạy nốt trên server).
  useEffect(() => {
    unmounted.current = false;
    return () => {
      unmounted.current = true;
      sendController.current?.abort();
    };
  }, []);

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (!content || busy) return;

      push({ kind: "user", text: content });
      setSending(true);
      turnActive.current = true;
      turnStartSeq.current = null;
      traceRef.current = emptyTrace();
      setLiveTrace(traceRef.current);
      const controller = new AbortController();
      sendController.current = controller;

      // Đã nhận được phản hồi từ server chưa: mất kết nối SAU mốc này thì lượt
      // chat có thể vẫn chạy trên server, gửi lại có thể tạo job trùng.
      let started = false;
      try {
        // after: seq cuối đã nhận - server phát lại sự kiện nền kênh nền bỏ lỡ (vd job_done lúc đang chờ kết nối lại).
        const res = await postJson(
          "/agent/chat/stream",
          { message: content, session_id: sessionId, access_token: token, after: seq.current.last },
          controller.signal,
        );
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new AgentHttpError(res.status, typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
        }
        started = true;

        let reply: ChatReply | null = null;
        let failure: AgentHttpError | null = null;
        await readSSE(res, (name, data) => {
          if (unmounted.current) return;
          if (name === "session") {
            adoptSession(data.session_id);
            turnStartSeq.current = typeof data.start_seq === "number" ? data.start_seq : null;
          } else if (name === "reply") reply = data as ChatReply;
          else if (name === "error") failure = new AgentHttpError(data.status_code ?? 502, data.detail || "");
          else ingest(data);
        });
        if (unmounted.current) return;

        if (failure) throw failure;
        if (!reply) throw new Error("disconnected");
        const done = reply as ChatReply;
        if (done.session_id) adoptSession(done.session_id);
        push({ kind: "agent", text: done.reply, trace: traceRef.current, agents: done.agents ?? [] });
        announce("reply");
        if (Array.isArray(done.watching)) setWatching(done.watching);
        const datasetId = traceRef.current.datasetId;
        if (datasetId) setActiveDataset((prev) => (prev?.id === datasetId ? prev : { id: datasetId }));
      } catch (error) {
        if (unmounted.current) return;
        const trace = traceRef.current.steps.length || traceRef.current.jobIds.length ? traceRef.current : undefined;
        // Lượt đã tạo job mà lỗi ở bước sau: gửi lại là chạy thêm một job trùng hàng giờ.
        const retryText = traceRef.current.jobIds.length ? undefined : content;
        if (error instanceof AgentHttpError && error.status === 409) {
          push({ kind: "error", trace, error: { code: "busy" } });
        } else if (error instanceof AgentHttpError && (error.status === 401 || error.status === 403)) {
          push({ kind: "error", trace, error: { code: "auth" } });
        } else if (error instanceof AgentHttpError) {
          push({ kind: "error", trace, error: { code: "server", detail: error.message }, retryText });
        } else if (started) {
          push({ kind: "error", trace, error: { code: "disconnected" } });
        } else {
          push({ kind: "error", error: { code: "network" }, retryText });
        }
      } finally {
        turnActive.current = false;
        turnStartSeq.current = null;
        if (sendController.current === controller) sendController.current = null;
        if (!unmounted.current) {
          setSending(false);
          setLiveTrace(null);
        }
      }
    },
    [adoptSession, announce, busy, ingest, push, sessionId, token],
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
        const { status, body } = await uploadWithProgress(form, (percent) => {
          if (!unmounted.current) setUploadProgress(percent);
        });
        // Rời trang khi đang tải lên: dataset vẫn vào kho, chỉ không cập nhật giao diện nữa.
        if (unmounted.current) return null;
        if (status === 401 || status === 403) return { code: "auth" };
        if (status !== 200) return { code: "server", detail: typeof body?.detail === "string" ? body.detail : `HTTP ${status}` };
        const dataset = body.dataset as UploadedDataset;
        adoptSession(body.session_id);
        push({ kind: "upload", dataset });
        setActiveDataset({ id: dataset.id, name: dataset.name, problemType: dataset.type });
        return null;
      } catch {
        return { code: "network" };
      } finally {
        if (!unmounted.current) setUploadProgress(null);
      }
    },
    [adoptSession, busy, push, sessionId, token],
  );

  const reset = useCallback(async () => {
    if (busy) return;
    // /agent/reset xoá lịch sử nhưng GIỮ phiên và job đang theo dõi. Dùng tiếp phiên
    // đó: job đang chạy vẫn báo về, và token mới vẫn tới watcher qua /agent/token.
    // Bỏ phiên đi thì watcher của nó chạy tiếp tới 26 giờ với token đã hết hạn.
    // Vì vậy CHỈ bỏ phiên khi server nói rõ không còn phiên đó (200 + ok:false);
    // mọi lỗi khác (409 đang chạy lượt, 401, 5xx, mất mạng) giữ nguyên tất cả.
    if (sessionId) {
      const res = await postJson("/agent/reset", { message: "reset", session_id: sessionId, access_token: token }).catch(() => null);
      if (unmounted.current) return;
      if (!res) {
        push({ kind: "error", error: { code: "network" } });
        return;
      }
      if (res.status === 409) {
        // Lượt trước vẫn chạy trên server (vd luồng lượt chat đã đứt giữa chừng).
        push({ kind: "error", error: { code: "busy" } });
        return;
      }
      if (res.status === 401 || res.status === 403) {
        push({ kind: "error", error: { code: "auth" } });
        return;
      }
      const body = res.ok ? await res.json().catch(() => null) : null;
      if (body?.ok === true) {
        setItems([]);
        setActiveDataset(null);
        return;
      }
      if (body?.ok !== false) {
        push({ kind: "error", error: { code: "server", detail: `HTTP ${res.status}` } });
        return;
      }
    }

    // Server không còn phiên này (hoặc chưa có phiên): tin nhắn sau tạo phiên mới.
    setItems([]);
    setActiveDataset(null);
    forgetSession();
    setJobs({});
    finishedJobs.current.clear();
  }, [busy, forgetSession, push, sessionId, token]);

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

