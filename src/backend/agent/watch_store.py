"""
Lưu trạng thái theo dõi job (watch) ra SQLite để sống qua lần restart / deploy của agent server.

Watcher chạy trong RAM: restart là mất job đang theo dõi, lời hứa tự kích hoạt và mọi việc phải báo người dùng.
Mỗi bản ghi là một (owner, job_id) cùng các tham số để theo dõi lại; bản ghi bị xoá khi job có kết quả cuối.
Khi chủ phiên quay lại (phiên mới, hoặc phiên cũ nhận token mới), server theo dõi lại các bản ghi mồ côi.

Bật bằng biến môi trường AGENT_STATE_DIR; không đặt thì tắt (CLI, test giữ hành vi chỉ-RAM như cũ).
"""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

# Bản ghi không ai quay lại nhận sau chừng này thì bỏ: job chắc chắn đã kết thúc từ lâu.
RECORD_TTL_SECONDS = 7 * 24 * 3600


class WatchStore:
    def __init__(self, path: str | os.PathLike) -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        with self._lock, self._db:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS watches ("
                " owner TEXT NOT NULL, job_id TEXT NOT NULL, session_id TEXT NOT NULL,"
                " record TEXT NOT NULL, updated_at REAL NOT NULL,"
                " PRIMARY KEY (owner, job_id))"
            )

    def save(self, owner: str, job_id: str, session_id: str, record: dict) -> None:
        payload = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO watches (owner, job_id, session_id, record, updated_at) VALUES (?, ?, ?, ?, ?)",
                (owner, job_id, session_id, payload, time.time()),
            )

    def remove(self, owner: str, job_id: str) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM watches WHERE owner = ? AND job_id = ?", (owner, job_id))

    def for_owner(self, owner: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT job_id, session_id, record FROM watches WHERE owner = ? ORDER BY updated_at", (owner,),
            ).fetchall()
        return [{**json.loads(record), "job_id": job_id, "session_id": session_id} for job_id, session_id, record in rows]

    def purge(self, older_than_seconds: float = RECORD_TTL_SECONDS) -> int:
        with self._lock, self._db:
            cursor = self._db.execute("DELETE FROM watches WHERE updated_at < ?", (time.time() - older_than_seconds,))
        return cursor.rowcount


def default_store() -> WatchStore | None:
    """Store tại $AGENT_STATE_DIR/watches.sqlite3 (đã dọn bản ghi quá hạn), hoặc None khi không cấu hình."""
    directory = os.getenv("AGENT_STATE_DIR", "").strip()
    if not directory:
        return None
    Path(directory).mkdir(parents=True, exist_ok=True)
    store = WatchStore(Path(directory) / "watches.sqlite3")
    store.purge()
    return store
