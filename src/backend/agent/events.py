"""
Kênh sự kiện của một phiên chat: nơi mọi tầng báo "đang làm gì" ra ngoài.

Vì sao cần: pipeline Algorithm 1 gọi LLM 10+ lần trong một lượt, còn job
huấn luyện chạy nền hàng giờ. Người dùng phải thấy được tiến độ, nên mỗi bước
(đổi giai đoạn, sub-agent xong, tool được gọi, job đổi trạng thái) đều phát một
sự kiện vào đây. server.py đẩy các sự kiện này ra frontend qua SSE.

Mỗi sự kiện có `seq` tăng dần. Client nhớ seq cuối đã nhận rồi hỏi tiếp từ đó,
nên mất kết nối giữa chừng cũng không mất sự kiện (trong giới hạn bộ đệm).

Thread-safe: pipeline chạy song song nhiều kế hoạch, watcher theo dõi job chạy
ở thread riêng, cả hai cùng phát sự kiện vào một bus.
"""

# Standard libraries
import threading
import time
from collections import deque


# Đủ cho một lượt pipeline đầy đủ (vài chục sự kiện) cộng nhiều giờ theo dõi job.
_MAX_EVENTS = 500


class EventBus:
    def __init__(self, maxlen: int = _MAX_EVENTS) -> None:
        self._events: deque[dict] = deque(maxlen=maxlen)
        self._seq = 0
        self._cond = threading.Condition()
        # Hàm nhận sự kiện đồng bộ, dùng cho CLI (in tiến độ ra terminal).
        self._listeners: list = []

    @property
    def last_seq(self) -> int:
        with self._cond:
            return self._seq

    def subscribe(self, listener) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def emit(self, type: str, **data) -> dict:
        with self._cond:
            self._seq += 1
            event = {"seq": self._seq, "type": type, "time": time.time(), **data}
            self._events.append(event)
            self._cond.notify_all()

        # Gọi listener NGOÀI khoá: listener chậm (in ra terminal) không được
        # chặn thread khác đang phát sự kiện.
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:  # noqa: BLE001 - listener hỏng không được làm hỏng pipeline
                pass
        return event

    def since(self, seq: int) -> list[dict]:
        with self._cond:
            return [event for event in self._events if event["seq"] > seq]

    def wait(self, seq: int, timeout: float) -> list[dict]:
        """Chờ tới khi có sự kiện mới hơn seq, hoặc hết timeout. Trả về các sự kiện mới."""
        with self._cond:
            self._cond.wait_for(lambda: self._seq > seq, timeout=timeout)
            return [event for event in self._events if event["seq"] > seq]
