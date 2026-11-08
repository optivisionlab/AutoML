/**
 * Thẻ xác nhận hành động thật (audit AG-01) - khớp với src/backend/agent/actions.py.
 *
 * Agent không tự huấn luyện, bật / tắt model hay bật tự kích hoạt: tool chỉ ĐỀ NGHỊ, server phát
 * `action_pending` (kèm token một lần) và hành động chỉ chạy khi người dùng bấm Xác nhận
 * (POST /agent/confirm). Nội dung thẻ lấy từ `summary` do CODE phía server dựng - không phải chữ LLM viết.
 */
import type { AgentEvent, ActivationConstraint } from "./events";

export type ActionKind = "train" | "activate" | "deactivate" | "auto_activate";
export type ActionStatus = "pending" | "submitting" | "done" | "failed" | "rejected" | "expired" | "superseded";

export interface ActionSummary {
  dataset_id?: string;
  dataset_name?: string | null;
  target?: string;
  features?: string[];
  feature_count?: number;
  problem_type?: string;
  metric_sort?: string;
  search_algorithm?: string;
  max_time?: number;
  auto_activate_constraints?: ActivationConstraint[];
  duplicate_of?: string[];
  job_id?: string;
  best_model?: string;
  best_score?: number | null;
  score_source?: string | null;
  currently_active?: boolean;
  constraints?: ActivationConstraint[];
  unconditional?: boolean;
  [key: string]: unknown;
}

export interface PendingActionView {
  actionId: string;
  kind: ActionKind;
  token: string;
  status: ActionStatus;
  summary: ActionSummary;
  offersAutoActivate: boolean;
  expiresAt?: number;
  error?: string;
  result?: Record<string, unknown>;
  /** Thứ tự xuất hiện - thẻ hiện theo thứ tự tạo. */
  order: number;
  /** seq của sự kiện action_pending (nếu thẻ đến từ sự kiện) - để không bị một danh sách CŨ hơn coi là đã hết. */
  seq?: number;
  /** Bị reconcile đánh dấu hết hiệu lực (không phải server báo) - danh sách sau còn thẻ này thì hồi sinh. */
  reconciled?: boolean;
}

const KINDS = new Set<ActionKind>(["train", "activate", "deactivate", "auto_activate"]);
const FINAL = new Set<ActionStatus>(["done", "failed", "rejected", "expired", "superseded"]);

export function isFinal(status: ActionStatus): boolean {
  return FINAL.has(status);
}

/** Một thẻ từ payload server (sự kiện action_pending hoặc phần tử pending_actions của hello / reply). */
export function parseAction(raw: any, order: number): PendingActionView | null {
  if (!raw || typeof raw.action_id !== "string" || typeof raw.token !== "string" || !KINDS.has(raw.kind)) return null;
  return {
    actionId: raw.action_id,
    kind: raw.kind,
    token: raw.token,
    status: "pending",
    summary: raw.summary && typeof raw.summary === "object" ? raw.summary : {},
    offersAutoActivate: raw.offers?.auto_activate === true,
    expiresAt: typeof raw.expires_at === "number" ? raw.expires_at : undefined,
    order,
    seq: typeof raw.seq === "number" ? raw.seq : undefined,
  };
}

function nextOrder(actions: Record<string, PendingActionView>): number {
  return Object.values(actions).reduce((max, a) => Math.max(max, a.order), 0) + 1;
}

/** Áp sự kiện action_pending / action_resolved. Trả về chính `actions` nếu không liên quan. */
export function applyActionEvent(
  actions: Record<string, PendingActionView>,
  event: AgentEvent,
): Record<string, PendingActionView> {
  if (event.type === "action_pending") {
    const current = actions[String(event.action_id)];
    // Phát lại sự kiện cũ (tải lại trang) không được hồi sinh thẻ đã xử lý.
    if (current) return actions;
    const parsed = parseAction(event, nextOrder(actions));
    return parsed ? { ...actions, [parsed.actionId]: parsed } : actions;
  }
  if (event.type === "action_resolved") {
    const current = actions[String(event.action_id)];
    if (!current) return actions;
    const status = event.status as ActionStatus;
    if (!FINAL.has(status) || current.status === status) return actions;
    return {
      ...actions,
      [current.actionId]: {
        ...current,
        status,
        error: typeof event.error === "string" ? event.error : undefined,
        result: event.result && typeof event.result === "object" ? event.result : current.result,
      },
    };
  }
  return actions;
}

/**
 * Đồng bộ với danh sách thẻ ĐANG CHỜ mà server báo (hello, reconnect, reply của lượt chat): thẻ mới thì
 * thêm; thẻ đang chờ ở đây mà server không còn thì đã được xử lý lúc mất kết nối - coi là hết hiệu lực
 * (không để nút Xác nhận của thẻ chết).
 *
 * asOfSeq: seq của EventBus lúc server chụp danh sách. Thẻ có action_pending MỚI hơn mốc đó không bị coi là đã
 * hết (danh sách chụp trước khi thẻ ra đời, vd thẻ kích hoạt watcher tạo ngay trước câu trả lời); thẻ bị đánh
 * dấu hết vì một danh sách cũ mà danh sách sau vẫn còn thì hồi sinh.
 */
export function reconcileActions(
  actions: Record<string, PendingActionView>,
  pending: unknown,
  asOfSeq?: number,
): Record<string, PendingActionView> {
  if (!Array.isArray(pending)) return actions;
  let next = actions;
  let order = nextOrder(actions);
  const live = new Set<string>();
  for (const raw of pending) {
    const parsed = parseAction(raw, order);
    if (!parsed) continue;
    live.add(parsed.actionId);
    const current = next[parsed.actionId];
    if (!current) {
      next = { ...next, [parsed.actionId]: parsed };
      order += 1;
    } else if (current.status === "expired" && current.reconciled) {
      next = { ...next, [parsed.actionId]: { ...current, status: "pending", reconciled: undefined, error: undefined } };
    }
  }
  for (const action of Object.values(next)) {
    const newer = typeof asOfSeq === "number" && typeof action.seq === "number" && action.seq > asOfSeq;
    if (action.status === "pending" && !live.has(action.actionId) && !newer) {
      next = { ...next, [action.actionId]: { ...action, status: "expired", reconciled: true } };
    }
  }
  return next;
}

/** Số thẻ đã xử lý còn hiện (để người dùng thấy cú bấm có tác dụng, không chất đống cả phiên). */
export const MAX_RESOLVED_VISIBLE = 3;

/**
 * Thẻ hiện ở cuối khung chat: mọi thẻ đang chờ / đang gửi, cộng vài thẻ vừa xử lý gần nhất. Thẻ bị thay bằng đề
 * nghị mới hơn (superseded) thì ẩn - thẻ mới đã thay chỗ nó.
 */
export function visibleActions(actions: Record<string, PendingActionView>): PendingActionView[] {
  const sorted = Object.values(actions).sort((a, b) => a.order - b.order);
  const resolved = sorted.filter((a) => isFinal(a.status) && a.status !== "superseded");
  const keep = new Set(resolved.slice(-MAX_RESOLVED_VISIBLE).map((a) => a.actionId));
  return sorted.filter((a) => !isFinal(a.status) || keep.has(a.actionId));
}
