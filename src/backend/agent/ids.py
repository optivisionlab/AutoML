"""
Chuẩn hoá ID mà LLM chép lại vào văn bản (giao việc cho sub-agent, câu trả lời cho người dùng).

LLM thỉnh thoảng chép sai ID 24 ký tự hex (ObjectId của MongoDB) khi viết lại: rơi, thừa hoặc đổi một ký tự.
Hậu quả: sub-agent gọi tool với ID không tồn tại, hoặc người dùng nhận một ID sai. Hàm ở đây sửa tất định,
không gọi LLM: chuỗi trông như ID mà không khớp ID thật nào nhưng gần DUY NHẤT một ID thật (khoảng cách sửa
nhỏ nhất, không hoà, tối đa MAX_DISTANCE) thì được thay bằng ID thật. Mơ hồ hay quá xa thì để nguyên.
"""
from __future__ import annotations

import re

# Chuỗi hex đứng riêng, độ dài quanh 24 (ObjectId bị rơi / thừa tối đa vài ký tự).
_ID_LIKE = re.compile(r"(?<![0-9A-Za-z_])([0-9a-f]{21,27})(?![0-9A-Za-z_])")
_REAL_ID = re.compile(r"(?<![0-9A-Za-z_])([0-9a-f]{24})(?![0-9A-Za-z_])")
MAX_DISTANCE = 2


def id_like_tokens(text: str) -> list[str]:
    """Các chuỗi trông như ID trong văn bản (theo thứ tự, không trùng)."""
    return list(dict.fromkeys(_ID_LIKE.findall(text or "")))


def real_ids(text: str) -> set[str]:
    """Các ObjectId đúng 24 ký tự hex trong văn bản."""
    return set(_REAL_ID.findall(text or ""))


def _distance(a: str, b: str, limit: int = MAX_DISTANCE) -> int:
    """Khoảng cách Levenshtein, dừng sớm khi chắc chắn vượt `limit` (trả limit + 1)."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        if min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


def closest_id(token: str, known: set[str]) -> str | None:
    """ID thật gần `token` nhất nếu duy nhất và trong MAX_DISTANCE; không thì None."""
    best, best_distance, tie = None, MAX_DISTANCE + 1, False
    for candidate in known:
        distance = _distance(token, candidate)
        if distance < best_distance:
            best, best_distance, tie = candidate, distance, False
        elif distance == best_distance:
            tie = True
    if best is None or tie or best_distance == 0:
        return None
    return best


def canonicalize_ids(text: str, known: set[str]) -> tuple[str, list[tuple[str, str]]]:
    """
    Thay chuỗi giống ID bị chép sai bằng ID thật gần nhất (duy nhất).

    Returns:
        (văn bản đã sửa, danh sách (chuỗi sai, ID thật)) - danh sách rỗng nếu không sửa gì.
    """
    if not text or not known:
        return text, []
    fixes = []
    for token in id_like_tokens(text):
        if token in known:
            continue
        real = closest_id(token, known)
        if real:
            fixes.append((token, real))
    for wrong, real in fixes:
        text = re.sub(rf"(?<![0-9A-Za-z_]){re.escape(wrong)}(?![0-9A-Za-z_])", real, text)
    return text, fixes
