"""
Hành động thật chờ NGƯỜI DÙNG xác nhận (audit AG-01, AG-12).

LLM - và mọi dữ liệu nó đọc (tên cột, ô dữ liệu, bảng database, lỗi job) - không tự thực hiện được hành
động thật: huấn luyện, bật / tắt model, bật tự kích hoạt. Tool chỉ ĐỀ NGHỊ: code kiểm điều kiện rồi tạo một
PendingAction; frontend hiện thẻ xác nhận dựng từ `summary` (do CODE viết, không phải chữ LLM); hành động chỉ
chạy khi người dùng bấm Xác nhận (POST /agent/confirm) kèm đúng token của thẻ.

Thay cho cách cũ đoán ý người dùng bằng regex từ khoá ("tôi không muốn huấn luyện" vẫn lọt): đồng ý gắn với
MỘT hành động cụ thể (loại, job / config, điều kiện) chứ không suy từ câu chữ.

- `token` chỉ đi ra frontend qua sự kiện `action_pending` (EventBus -> SSE). Kết quả tool trả cho LLM dùng
  `public()` - không có token - nên LLM không có cách nào tự xác nhận, kể cả khi bị dữ liệu điều khiển.
- Dùng một lần: pending -> executing -> done / failed; bấm lại hay bấm thẻ đã hết hạn đều bị từ chối.
- Có hạn (AGENT_ACTION_TTL_SECONDS, mặc định 30 phút): thẻ cũ bấm khi bối cảnh đã đổi là nguy hiểm. Khi thực
  thi, team vẫn kiểm lại mọi điều kiện lần nữa.
- Cùng `key` (vd cùng job) thì đề nghị mới THAY đề nghị cũ - không còn hai thẻ mâu thuẫn cùng chờ.
"""

# Standard libraries
import hmac
import os
import secrets
import threading
import time
from dataclasses import dataclass, field


DEFAULT_TTL_SECONDS = 30 * 60
# Thẻ đang chờ tối đa mỗi phiên: LLM (bị dữ liệu lái) đề nghị dồn dập thì thẻ cũ nhất bị thay.
MAX_PENDING = 10
# Hành động đã xử lý còn giữ lại (để bấm lại thẻ cũ nhận lỗi rõ ràng thay vì "không tìm thấy").
_MAX_RESOLVED = 50

KINDS = ("train", "activate", "deactivate", "auto_activate")
FINAL_STATUSES = ("done", "failed", "rejected", "expired", "superseded")


def action_ttl() -> float:
    """AGENT_ACTION_TTL_SECONDS trong .env (giây), không đặt hoặc sai thì 30 phút."""
    raw = os.getenv("AGENT_ACTION_TTL_SECONDS", "").strip()
    try:
        value = float(raw) if raw else DEFAULT_TTL_SECONDS
    except ValueError:
        return DEFAULT_TTL_SECONDS
    return value if value > 0 else DEFAULT_TTL_SECONDS


class ActionError(Exception):
    """Không xác nhận / từ chối được. `code`: not_found | bad_token | expired | resolved | bad_option."""

    def __init__(self, code: str, message: str, status: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass
class PendingAction:
    action_id: str
    token: str
    kind: str
    key: str
    params: dict
    summary: dict
    offers: dict
    created_at: float
    expires_at: float
    status: str = "pending"
    result: dict | None = None
    error: str | None = None
    # Lựa chọn của người dùng lúc xác nhận (vd có tự kích hoạt không) - để báo lại đúng điều đã chọn.
    choice: dict = field(default_factory=dict)
    # Client API lúc đề nghị (chính client của phiên) - không gửi ra ngoài, không có trong public().
    api: object = field(default=None, repr=False)

    def public(self) -> dict:
        """Cho LLM và log: KHÔNG có token."""
        return {
            "action_id": self.action_id,
            "kind": self.kind,
            "status": self.status,
            "summary": self.summary,
            "offers": self.offers,
            "expires_at": round(self.expires_at),
        }

    def for_client(self) -> dict:
        """Cho frontend (sự kiện action_pending, hello): có token để bấm xác nhận."""
        return {**self.public(), "token": self.token}


class PendingActions:
    """Kho hành động chờ xác nhận của MỘT phiên chat. Thread-safe (lượt chat, watcher, request xác nhận)."""

    def __init__(self, emit) -> None:
        self._emit = emit
        self._lock = threading.Lock()
        self._actions: dict[str, PendingAction] = {}

    def propose(self, kind: str, key: str, params: dict, summary: dict, offers: dict | None = None,
                api=None) -> PendingAction:
        """Tạo thẻ chờ xác nhận và phát `action_pending`. Đề nghị cũ cùng key bị thay (superseded)."""
        if kind not in KINDS:
            raise ValueError(f"loại hành động lạ: {kind}")
        now = time.time()
        action = PendingAction(
            action_id=f"act-{secrets.token_hex(6)}",
            token=secrets.token_urlsafe(24),
            kind=kind,
            key=key,
            params=dict(params),
            summary=dict(summary),
            offers=dict(offers or {}),
            created_at=now,
            expires_at=now + action_ttl(),
            api=api,
        )
        with self._lock:
            self._expire_locked(now)
            for other in self._actions.values():
                if other.status == "pending" and other.key == key:
                    self._resolve_locked(other, "superseded", error="Đã có đề nghị mới hơn cho cùng việc này.")
            waiting = sorted((a for a in self._actions.values() if a.status == "pending"), key=lambda a: a.created_at)
            for other in waiting[: max(0, len(waiting) - MAX_PENDING + 1)]:
                self._resolve_locked(other, "superseded", error="Quá nhiều đề nghị đang chờ - thẻ cũ nhất bị thay.")
            self._actions[action.action_id] = action
            self._prune_locked()
            # Phát trong khoá: thứ tự sự kiện khớp thứ tự đổi trạng thái (thay thẻ cũ rồi mới có thẻ mới).
            self._emit("action_pending", **action.for_client())
        return action

    def claim(self, action_id: str, token: str) -> PendingAction:
        """Nhận việc thực thi (pending -> executing) - đúng MỘT lần. Raise ActionError nếu không được."""
        with self._lock:
            action = self._checked_locked(action_id, token)
            action.status = "executing"
            return action

    def reject(self, action_id: str, token: str) -> PendingAction:
        """Người dùng bấm Từ chối."""
        with self._lock:
            action = self._checked_locked(action_id, token)
            self._resolve_locked(action, "rejected")
            return action

    def resolve(self, action: PendingAction, ok: bool, result: dict | None = None, error: str | None = None) -> None:
        """Kết thúc việc thực thi đã claim: done hoặc failed, phát `action_resolved`."""
        with self._lock:
            self._resolve_locked(action, "done" if ok else "failed", result=result, error=error)

    def pending(self) -> list[dict]:
        """Thẻ đang chờ, kèm token - cho hello / reconnect của frontend."""
        with self._lock:
            self._expire_locked(time.time())
            return [a.for_client() for a in self._waiting_locked()]

    def pending_public(self) -> list[dict]:
        """Thẻ đang chờ, KHÔNG token - cho ngữ cảnh của LLM."""
        with self._lock:
            self._expire_locked(time.time())
            return [a.public() for a in self._waiting_locked()]

    def get(self, action_id: str) -> PendingAction | None:
        with self._lock:
            return self._actions.get(action_id)

    def drop_all(self, reason: str) -> None:
        """Reset phiên: mọi thẻ đang chờ hết hiệu lực (config / R mà chúng dựa vào đã bị xoá)."""
        with self._lock:
            for action in self._waiting_locked():
                self._resolve_locked(action, "superseded", error=reason)

    # ------------------------------------------------------------------ nội bộ

    def _waiting_locked(self) -> list[PendingAction]:
        return sorted((a for a in self._actions.values() if a.status == "pending"), key=lambda a: a.created_at)

    def _checked_locked(self, action_id: str, token: str) -> PendingAction:
        action = self._actions.get(str(action_id or ""))
        if action is None:
            raise ActionError("not_found", "Không tìm thấy yêu cầu xác nhận này (có thể phiên đã được làm mới).")
        if not hmac.compare_digest(action.token.encode(), str(token or "").encode()):
            raise ActionError("bad_token", "Mã xác nhận không đúng.")
        self._expire_locked(time.time())
        if action.status != "pending":
            if action.status == "expired":
                raise ActionError("expired", "Yêu cầu xác nhận đã hết hạn - nhờ agent đề nghị lại.", action.status)
            raise ActionError("resolved", f"Yêu cầu này đã được xử lý ({action.status}).", action.status)
        return action

    def _expire_locked(self, now: float) -> None:
        for action in self._actions.values():
            if action.status == "pending" and now >= action.expires_at:
                self._resolve_locked(action, "expired", error="Hết hạn xác nhận.")

    def _resolve_locked(self, action: PendingAction, status: str, result: dict | None = None,
                        error: str | None = None) -> None:
        action.status = status
        action.result = result
        action.error = error
        self._emit(
            "action_resolved", action_id=action.action_id, kind=action.kind, status=status,
            summary=action.summary, result=result, error=error, choice=action.choice or None,
        )

    def _prune_locked(self) -> None:
        resolved = sorted(
            (a for a in self._actions.values() if a.status in FINAL_STATUSES), key=lambda a: a.created_at,
        )
        for action in resolved[: max(0, len(resolved) - _MAX_RESOLVED)]:
            self._actions.pop(action.action_id, None)
