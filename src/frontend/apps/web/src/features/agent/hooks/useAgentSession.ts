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
  applyWatchState,
  createSeqTracker,
  emptyTrace,
  markJobsLost,
  mergeJobFromApi,
  type JobView,
  type TurnTrace,
} from "../lib/eventAdapter";
import { OrphanTurns, isTurnEnd, turnEnd } from "../lib/orphanTurns";
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
  code: "busy" | "auth" | "server" | "disconnected" | "network" | "noReply" | "maybeReceived";
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
  code: "reply" | "jobStarted" | "jobDone" | "jobFailed" | "jobTimeout";
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
/** Mã lượt chat (server gắn lại vào turn_done / turn_failed). randomUUID chỉ có ở trang https/localhost. */
function newTurnId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `t-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
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
  // Đang chờ /agent/reset (xem reset): tính vào busy.
  const [resetting, setResetting] = useState(false);
  const resettingRef = useRef(false);

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
  // Khôi phục phiên sau tải lại trang KHÔNG tới được server (mạng, quá giờ chờ, 5xx):
  // lượt chat đầu tiên sẽ nhận cả bộ đệm sự kiện cũ (after = 0). `unreplayed` chờ luồng
  // đó báo start_seq; `replayUntil` = mốc đó: sự kiện có seq <= mốc là CŨ, dù tới qua luồng
  // nào (luồng lượt chat có thể đứt giữa phần phát lại, phần còn lại tới qua kênh nền) -
  // chỉ cập nhật job, không chèn thẻ kết quả / thông báo lại.
  const unreplayed = useRef(false);
  const replayUntil = useRef<number | null>(null);
  // Lượt có luồng đứt giữa chừng: turn_id -> số lần kênh nền đã mở lại trong lúc chờ. Lượt
  // vẫn chạy xong trên server và kết thúc bằng turn_done / turn_failed mang ĐÚNG turn_id đó.
  const orphans = useRef(new OrphanTurns());
  // Lượt đang chạy, và kết thúc của nó nếu turn_done / turn_failed đã tới trước khi luồng đứt.
  const currentTurnId = useRef<string | null>(null);
  const activeTurnEnd = useRef<{ reply?: string; error?: string } | null>(null);
  // turn_start của lượt hiện tại đã tới (qua kênh nào cũng được): server chắc chắn đã nhận lượt.
  const currentTurnStarted = useRef(false);
  // Tăng mỗi lần "Cuộc trò chuyện mới": luồng SSE của phiên cũ có thể còn đẩy
  // sự kiện trong khoảng trước khi effect kịp đóng nó - sự kiện đó không được
  // lọt vào phiên mới (sẽ làm seq.last nhảy vọt và bỏ sót sự kiện của phiên mới).
  const generation = useRef(0);
  // session_id đang dùng, đọc được ngay trong callback SSE (state sessionId thì chưa kịp đổi).
  const sessionRef = useRef<string | null>(null);

  const uploading = uploadProgress !== null;
  const busy = sending || uploading || restoring || resetting;

  const push = useCallback((item: NewChatItem): number => {
    const id = nextId.current++;
    setItems((prev) => [...prev, { ...item, at: Date.now(), id } as ChatItem]);
    return id;
  }, []);

  /** Sửa một item đã có (vd bỏ nút "Gửi lại" khi biết server đã nhận lượt đó). */
  const updateItem = useCallback((id: number | undefined, patch: (item: ChatItem) => ChatItem) => {
    if (id === undefined) return;
    setItems((prev) => prev.map((item) => (item.id === id ? patch(item) : item)));
  }, []);

  /** Chèn ngay sau một item (vd kết quả của lượt bị đứt, ngay dưới thông báo đứt của chính nó). */
  const insertAfter = useCallback((afterId: number | undefined, item: NewChatItem) => {
    const id = nextId.current++;
    const entry = { ...item, at: Date.now(), id } as ChatItem;
    setItems((prev) => {
      const index = afterId === undefined ? -1 : prev.findIndex((existing) => existing.id === afterId);
      return index < 0 ? [...prev, entry] : [...prev.slice(0, index + 1), entry, ...prev.slice(index + 1)];
    });
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

  /** Bỏ các lượt đang chờ kết quả (phiên đổi / cuộc trò chuyện mới); notify = báo người dùng. */
  const dropOrphans = useCallback(
    (notify: boolean) => {
      const itemIds = orphans.current.clear();
      if (notify) for (const itemId of itemIds) insertAfter(itemId, { kind: "error", error: { code: "noReply" } });
    },
    [insertAfter],
  );

  /**
   * Server báo một lượt đang chạy mà trang này không gửi (vd vừa tải lại trang giữa lượt): chờ
   * kết quả của nó như lượt bị đứt luồng, giữ kênh nền mở tới khi nó kết thúc.
   */
  const adoptRunningTurn = useCallback(
    (turnId: unknown) => {
      if (typeof turnId !== "string" || !turnId || turnId === currentTurnId.current) return;
      if (orphans.current.has(turnId)) {
        // Lượt lỗi mạng trước khi có phản hồi mà server báo đang chạy / xếp hàng: chắc chắn đã nhận.
        const confirmed = orphans.current.confirm(turnId);
        if (confirmed) {
          updateItem(confirmed.itemId, (item) =>
            item.kind === "error" ? { ...item, retryText: undefined, error: { code: "disconnected" } } : item,
          );
        }
        return;
      }
      orphans.current.add(turnId, undefined, true);
      setProbeEvents(true);
    },
    [updateItem],
  );

  /** Hiện kết quả của một lượt: câu trả lời, hoặc lỗi nếu lượt hỏng trên server. */
  const showTurnEnd = useCallback(
    (end: { reply?: string; error?: string }, trace?: TurnTrace, afterId?: number) => {
      if (end.reply !== undefined) {
        insertAfter(afterId, { kind: "agent", text: end.reply, trace: trace ?? emptyTrace(), agents: [] });
        announce("reply");
      } else {
        insertAfter(afterId, { kind: "error", trace, error: { code: "server", detail: end.error || undefined } });
      }
    },
    [announce, insertAfter],
  );

  /**
   * Bỏ lượt chờ quá lâu. Lượt chưa xác nhận (lỗi mạng trước khi server trả lời, không thấy
   * turn_start) bỏ im lặng - có thể server chưa từng nhận. Gọi mỗi lần kênh nền mở lại
   * HOẶC lỗi, để kênh lỗi liên tục cũng không giữ lượt chờ (và kênh) mãi.
   */
  const expireOrphans = useCallback((): number => {
    const { notify, removed } = orphans.current.expire();
    for (const itemId of notify) insertAfter(itemId, { kind: "error", error: { code: "noReply" } });
    return removed;
  }, [insertAfter]);

  /** Quên phiên hiện tại ở phía trình duyệt: tin nhắn sau sẽ tạo phiên mới. */
  const forgetSession = useCallback(() => {
    generation.current += 1;
    writeStoredSession(userKey, null);
    sessionRef.current = null;
    setSessionId(null);
    setWatching([]);
    setProbeEvents(false);
    seq.current.reset();
    unreplayed.current = false;
    replayUntil.current = null;
    orphans.current.clear();
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
        replayUntil.current = null;
        setWatching([]);
        setProbeEvents(false);
        markSessionLost();
        // Phiên cũ đã mất: lượt đang chờ kết quả sẽ không bao giờ có kết quả nữa.
        dropOrphans(true);
      }
      sessionRef.current = id;
      setSessionId(id);
    },
    [markSessionLost, dropOrphans],
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
      // Sự kiện cũ phát lại không được chèn thẻ kết quả / thông báo lần nữa.
      const until = replayUntil.current;
      const quiet = replaying.current || (until !== null && typeof event.seq === "number" && event.seq <= until);
      if (until !== null && seq.current.last >= until) replayUntil.current = null;

      // Kết thúc lượt: ghép theo turn_id - không thể nhầm lượt, kể cả khi phiên đổi
      // (seq bắt đầu lại) hay có nhiều lượt bị đứt (xem lib/orphanTurns.ts).
      const resolved = orphans.current.onEvent(event);
      if (resolved) {
        // Server đã nhận lượt này: item lỗi của nó không được mời "Gửi lại" nữa (gửi lại =
        // chạy lượt thứ hai, có thể tạo job huấn luyện trùng).
        updateItem(resolved.itemId, (item) =>
          item.kind === "error" ? { ...item, retryText: undefined, error: { code: "disconnected" } } : item,
        );
        if (resolved.kind === "ended") showTurnEnd(resolved.end, undefined, resolved.itemId);
      } else if (event.turn_id && event.turn_id === currentTurnId.current) {
        if (event.type === "turn_start") currentTurnStarted.current = true;
        if (isTurnEnd(event)) activeTurnEnd.current = turnEnd(event);
      }

      setJobs((prev) => applyJobEvent(prev, event));

      const jobId = event.job_id ? String(event.job_id) : null;
      if (!jobId) return;
      // job_watch: job có sẵn được watch_job theo dõi - cũng phải mở kênh nền, kể cả khi phát lại sau tải lại trang.
      if (event.type === "job_started" || event.type === "job_watch") {
        // Job hết giờ chờ (job_watch_timeout) rồi được theo dõi lại: phải báo được kết quả lần nữa.
        finishedJobs.current.delete(jobId);
        setWatching((prev) => (prev.includes(jobId) ? prev : [...prev, jobId]));
        if (event.type === "job_started" && !quiet) announce("jobStarted", { id: jobId.slice(0, 8) });
      } else if (event.type && END_EVENTS.has(event.type)) {
        setWatching((prev) => prev.filter((id) => id !== jobId));
        if (!finishedJobs.current.has(jobId)) {
          finishedJobs.current.add(jobId);
          if (!quiet) {
            push({ kind: "job", jobId });
            // Hết giờ chờ KHÔNG có nghĩa job hỏng - chỉ là watcher thôi theo dõi.
            const code = event.type === "job_done" ? "jobDone" : event.type === "job_watch_timeout" ? "jobTimeout" : "jobFailed";
            announce(code, { id: jobId.slice(0, 8) });
          }
        }
      }
    },
    [announce, push, showTurnEnd, updateItem],
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
            if (name === "hello" || name === "reconnect") {
              if (Array.isArray(data.watching)) setWatching(data.watching);
              setJobs((prev) => applyWatchState(prev, data.watching, data.auto_activate, data.auto_activate_constraints));
              if (name === "hello") adoptRunningTurn(data.turn_id);
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
        // Bị huỷ (cleanup) thì không đụng tới: lần chạy sau của effect có thể đang phát lại.
        if (!cancelled) {
          replaying.current = false;
          setRestoring(false);
        }
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
      } else {
        unreplayed.current = true;
      }
    })();

    return () => {
      cancelled = true;
      replaying.current = false;
      controller.abort();
      setRestoring(false);
    };
  }, [adoptSession, adoptRunningTurn, ingest, push, userKey]);

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
              // Lượt đang chờ kết quả thuộc phiên đã mất: sẽ không bao giờ có kết quả.
              dropOrphans(true);
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
            if (name === "hello") {
              // Vừa tải lại trang mà chưa phát lại được lịch sử: sự kiện tới mốc này là CŨ.
              if (unreplayed.current && typeof data.last_seq === "number") {
                replayUntil.current = data.last_seq;
                unreplayed.current = false;
              }
              setJobs((prev) => applyWatchState(prev, data.watching, data.auto_activate, data.auto_activate_constraints));
              adoptRunningTurn(data.turn_id);
              return;
            }
            if (name === "reconnect") {
              reconnected = true;
              if (Array.isArray(data.watching)) setWatching(data.watching);
              setJobs((prev) => applyWatchState(prev, data.watching, data.auto_activate, data.auto_activate_constraints));
              // Còn chờ kết quả của lượt bị đứt thì giữ kênh mở tiếp - có hạn (expireOrphans).
              expireOrphans();
              if (!orphans.current.size) setProbeEvents(false);
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
          // Kênh lỗi liên tục (5xx, proxy cắt sớm) cũng phải tính vào thời gian chờ. Chỉ đóng kênh
          // khi vừa bỏ lượt cuối - kênh mở để khôi phục phiên thì giữ tới `reconnect` đầu tiên.
          if (expireOrphans() > 0 && !orphans.current.size) setProbeEvents(false);
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
  }, [sessionId, listen, ingest, forgetSession, markSessionLost, dropOrphans, expireOrphans, adoptRunningTurn]);

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
      const turnId = newTurnId();
      currentTurnId.current = turnId;
      activeTurnEnd.current = null;
      currentTurnStarted.current = false;
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
          { message: content, session_id: sessionId, access_token: token, after: seq.current.last, turn_id: turnId },
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
            // Khôi phục không tới được server: luồng này phát lại bộ đệm cũ tới start_seq.
            if (unreplayed.current && turnStartSeq.current !== null) {
              replayUntil.current = turnStartSeq.current;
              unreplayed.current = false;
            }
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
        // Chỉ dataset của tool gọi THÀNH CÔNG mới thành dataset đang làm việc (id sai/bịa thì không).
        const datasetId = traceRef.current.activeDatasetId;
        if (datasetId) setActiveDataset((prev) => (prev?.id === datasetId ? prev : { id: datasetId }));
      } catch (error) {
        if (unmounted.current) return;
        const trace = traceRef.current.steps.length || traceRef.current.jobIds.length ? traceRef.current : undefined;
        // Lượt đã tạo job - hoặc đã GỬI lệnh tạo job (start_training) mà chưa rõ kết quả - rồi
        // lỗi ở bước sau: gửi lại là có thể chạy thêm một job trùng hàng giờ.
        const triedTraining = traceRef.current.steps.some((step) => step.tools.some((tool) => tool.name === "start_training"));
        const retryText = traceRef.current.jobIds.length || triedTraining ? undefined : content;
        // Lỗi mạng, hoặc 502/504 TRƯỚC khi luồng bắt đầu (proxy): không rõ server đã nhận lượt chưa.
        const ambiguous = !started && (!(error instanceof AgentHttpError) || error.status === 502 || error.status === 504);
        if (ambiguous && activeTurnEnd.current) {
          // Kênh nền đã đưa kết thúc của chính lượt này (seq đã được nhận - sẽ không tới lần nữa).
          showTurnEnd(activeTurnEnd.current, traceRef.current);
        } else if (ambiguous && currentTurnStarted.current && sessionRef.current) {
          // Server chắc chắn đã nhận (turn_start đã tới): chờ kết quả, không mời gửi lại.
          const itemId = push({ kind: "error", trace, error: { code: "disconnected" } });
          orphans.current.add(turnId, itemId, true);
          setProbeEvents(true);
        } else if (ambiguous && !sessionRef.current) {
          // Chưa có phiên: gửi lại sẽ mở phiên MỚI không biết gì về lượt có thể đang chạy (có thể tạo
          // job trùng) - không mời gửi lại, nhắc kiểm tra danh sách job trước.
          push({ kind: "error", error: { code: "maybeReceived" } });
        } else if (ambiguous && error instanceof AgentHttpError) {
          // Có phiên: như lỗi mạng - nghe thử kết quả; gửi lại khi lượt đó còn chạy thì bị 409.
          const itemId = push({ kind: "error", error: { code: "server", detail: error.message }, retryText });
          orphans.current.add(turnId, itemId, false);
          setProbeEvents(true);
        } else if (error instanceof AgentHttpError && error.status === 409) {
          push({ kind: "error", trace, error: { code: "busy" } });
        } else if (error instanceof AgentHttpError && (error.status === 401 || error.status === 403)) {
          // Server từ chối token TRƯỚC khi bắt đầu lượt (không có job nào được tạo): thử lại
          // sau khi đăng nhập lại là an toàn, khỏi bắt người dùng gõ lại.
          push({ kind: "error", trace, error: { code: "auth" }, retryText });
        } else if (error instanceof AgentHttpError) {
          push({ kind: "error", trace, error: { code: "server", detail: error.message }, retryText });
        } else if (started && activeTurnEnd.current) {
          // Luồng đứt sau khi lượt đã kết thúc (turn_done / turn_failed đã tới) nhưng trước `reply`.
          showTurnEnd(activeTurnEnd.current, traceRef.current);
        } else if (started && sessionRef.current) {
          const itemId = push({ kind: "error", trace, error: { code: "disconnected" } });
          // Lượt vẫn chạy nốt trên server: mở kênh nền để nhận phần còn lại và kết thúc lượt.
          orphans.current.add(turnId, itemId, true);
          setProbeEvents(true);
        } else if (started) {
          // Đứt trước cả sự kiện `session`: không biết phiên nào để nghe kết quả.
          push({ kind: "error", trace, error: { code: "noReply" } });
        } else if (activeTurnEnd.current) {
          // Fetch lỗi nhưng kênh nền đã đưa kết thúc của chính lượt này: lượt đã xong.
          showTurnEnd(activeTurnEnd.current, traceRef.current);
        } else if (currentTurnStarted.current && sessionRef.current) {
          // Server chắc chắn đã nhận (turn_start đã tới): như mất kết nối giữa chừng, không mời gửi lại.
          const itemId = push({ kind: "error", trace, error: { code: "disconnected" } });
          orphans.current.add(turnId, itemId, true);
          setProbeEvents(true);
        } else {
          const itemId = push({ kind: "error", error: { code: "network" }, retryText });
          // Có thể server đã nhận tin dù trình duyệt không nhận được phản hồi: nghe thử kết quả
          // (chỉ giữ nếu thấy turn_start của lượt này). Gửi lại khi lượt đó còn chạy thì bị 409.
          if (sessionRef.current) {
            orphans.current.add(turnId, itemId, false);
            setProbeEvents(true);
          }
        }
      } finally {
        turnActive.current = false;
        turnStartSeq.current = null;
        currentTurnId.current = null;
        if (sendController.current === controller) sendController.current = null;
        if (!unmounted.current) {
          setSending(false);
          setLiveTrace(null);
        }
      }
    },
    [adoptSession, announce, busy, ingest, push, sessionId, showTurnEnd, token],
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

  const resetInner = useCallback(async () => {
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
        // Câu trả lời muộn của lượt cũ không được rơi vào cuộc trò chuyện mới.
        dropOrphans(false);
        setProbeEvents(false);
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
  }, [dropOrphans, forgetSession, push, sessionId, token]);

  const reset = useCallback(async () => {
    if (busy || resettingRef.current) return;
    // Đang chờ server reset thì khoá gửi / tải lên / reset tiếp: phản hồi tới muộn sẽ xoá mất tin
    // nhắn gửi trong lúc chờ.
    resettingRef.current = true;
    setResetting(true);
    try {
      await resetInner();
    } finally {
      resettingRef.current = false;
      if (!unmounted.current) setResetting(false);
    }
  }, [busy, resetInner]);

  /** Ghép bản ghi job vừa lấy từ backend v1 (nút "Làm mới"). */
  const applyJobFromApi = useCallback((jobId: string, raw: Record<string, any>) => {
    setJobs((prev) => ({ ...prev, [jobId]: mergeJobFromApi(prev[jobId] ?? { jobId, status: "submitted" }, raw, Date.now()) }));
  }, []);

  const setJobActivated = useCallback((jobId: string, activated: boolean) => {
    setJobs((prev) => (prev[jobId] ? { ...prev, [jobId]: { ...prev[jobId], activated } } : prev));
  }, []);

  /**
   * Bật/tắt tự kích hoạt model khi một job đang chạy xong (nút "Huỷ tự kích hoạt" trên thẻ job).
   * Server phát auto_activate_changed cho mọi kênh; cập nhật luôn tại chỗ để thẻ đổi ngay.
   */
  const setAutoActivate = useCallback(async (jobId: string, enabled: boolean): Promise<boolean> => {
    const session = sessionRef.current;
    if (!session) return false;
    const res = await postJson("/agent/auto-activate", {
      session_id: session,
      access_token: tokenRef.current,
      job_id: jobId,
      enabled,
    }).catch(() => null);
    if (!res?.ok || unmounted.current) return false;
    setJobs((prev) =>
      prev[jobId]
        ? { ...prev, [jobId]: { ...prev[jobId], autoActivate: enabled, autoActivateCancelled: enabled ? undefined : true } }
        : prev,
    );
    return true;
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
    setAutoActivate,
  };
}

