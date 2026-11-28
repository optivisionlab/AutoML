/**
 * Lượt chat có luồng đứt giữa chừng ("orphan"): lượt vẫn chạy xong trên server và kết
 * thúc bằng turn_done (kèm reply) hoặc turn_failed mang ĐÚNG turn_id mà frontend đã gửi.
 * Kết quả tới sau qua kênh nền (hoặc phát lại ở lượt sau) - ghép theo turn_id, không theo
 * seq (phiên đổi thì seq bắt đầu lại, và có thể có nhiều lượt cùng đứt).
 *
 * Thuần (không React) để test được; useAgentSession giữ một instance trong useRef.
 */

import type { AgentEvent } from "./events";

// Chờ kết quả tối đa bấy nhiêu lâu: lượt nào cũng kết thúc bằng turn_done / turn_failed,
// đây chỉ là lưới an toàn (vd agent server chết hẳn).
export const ORPHAN_MAX_WAIT_MS = 30 * 60_000;
// Lỗi mạng TRƯỚC khi server trả lời: chưa biết server có nhận tin không. Thấy turn_start của
// lượt đó thì chờ tiếp như thường; không thấy trong ngần này thì coi như chưa gửi được.
export const ORPHAN_UNCONFIRMED_MS = 90_000;

export interface TurnEnd {
  reply?: string;
  error?: string;
}

interface Orphan {
  since: number;
  /** Item "mất kết nối" của lượt đó - kết quả được chèn ngay sau nó. */
  itemId?: number;
  /** false = chưa biết server có nhận lượt này không (chưa thấy turn_start). */
  confirmed: boolean;
}

/** turn_done / turn_failed -> kết quả hiển thị. */
export function turnEnd(event: AgentEvent): TurnEnd {
  return event.type === "turn_done" && typeof event.reply === "string"
    ? { reply: event.reply }
    : { error: typeof event.error === "string" ? event.error : "" };
}

export function isTurnEnd(event: AgentEvent): boolean {
  return event.type === "turn_done" || event.type === "turn_failed";
}

export class OrphanTurns {
  private turns = new Map<string, Orphan>();

  get size(): number {
    return this.turns.size;
  }

  has(turnId: string): boolean {
    return this.turns.has(turnId);
  }

  /**
   * Server xác nhận lượt này có thật (vd `hello` báo nó đang chạy / xếp hàng): lượt "chưa xác
   * nhận" thành đã xác nhận - chờ tới khi xong thay vì bỏ sau 90 giây. Trả itemId nếu vừa đổi.
   */
  confirm(turnId: string): { itemId?: number } | null {
    const orphan = this.turns.get(turnId);
    if (!orphan || orphan.confirmed) return null;
    orphan.confirmed = true;
    return { itemId: orphan.itemId };
  }

  add(turnId: string, itemId: number | undefined, confirmed: boolean, now = Date.now()): void {
    this.turns.set(turnId, { since: now, itemId, confirmed });
  }

  /** Bỏ hết; trả itemId của các lượt đang chờ (để báo ngay dưới item của từng lượt). */
  clear(): (number | undefined)[] {
    const itemIds = [...this.turns.values()].map((orphan) => orphan.itemId);
    this.turns.clear();
    return itemIds;
  }

  /**
   * Áp một sự kiện:
   * - "confirmed": server đã nhận lượt (turn_start) từng chưa chắc - item của nó không được
   *   mời "Gửi lại" nữa (gửi lại = chạy lượt thứ hai, có thể tạo job trùng).
   * - "ended": kết thúc của một lượt đang chờ (và bỏ lượt đó).
   */
  onEvent(
    event: AgentEvent,
  ): { kind: "confirmed"; itemId?: number } | { kind: "ended"; end: TurnEnd; itemId?: number } | null {
    const turnId = typeof event.turn_id === "string" ? event.turn_id : null;
    const orphan = turnId ? this.turns.get(turnId) : undefined;
    if (!turnId || !orphan) return null;
    if (event.type === "turn_start") {
      if (orphan.confirmed) return null;
      orphan.confirmed = true;
      return { kind: "confirmed", itemId: orphan.itemId };
    }
    if (!isTurnEnd(event)) return null;
    this.turns.delete(turnId);
    return { kind: "ended", end: turnEnd(event), itemId: orphan.itemId };
  }

  /**
   * Bỏ lượt chờ quá hạn. Lượt chưa xác nhận bỏ im lặng (có thể server chưa từng nhận).
   * Trả itemId của các lượt cần báo "không nhận được câu trả lời".
   */
  expire(now = Date.now()): { notify: (number | undefined)[]; removed: number } {
    const notify: (number | undefined)[] = [];
    let removed = 0;
    for (const [id, orphan] of this.turns) {
      if (!orphan.confirmed && now - orphan.since > ORPHAN_UNCONFIRMED_MS) {
        this.turns.delete(id);
        removed += 1;
      } else if (now - orphan.since > ORPHAN_MAX_WAIT_MS) {
        this.turns.delete(id);
        removed += 1;
        notify.push(orphan.itemId);
      }
    }
    return { notify, removed };
  }
}
