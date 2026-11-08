"""
Người dùng mô phỏng bấm nút trên thẻ xác nhận (từ protocol v5).

Từ đợt audit 2026-11-08, agent không tự huấn luyện / bật / tắt model: tool chỉ ĐỀ NGHỊ, code tạo thẻ
`PendingAction`, và hành động chỉ chạy khi người dùng bấm Xác nhận (POST /agent/confirm ->
`AgentTeam.confirm_action`). Benchmark đóng vai người dùng đó theo một chính sách CỐ ĐỊNH của từng ca,
suy ra từ đúng câu chữ của prompt - không nhìn kết quả để quyết định:

- `confirm_auto`: bấm "Xác nhận + tự kích hoạt khi xong" (thẻ train có lựa chọn này khi người dùng đã dặn
  kích hoạt sau khi train); thẻ không có lựa chọn này thì bấm Xác nhận thường.
- `confirm`: bấm Xác nhận.
- `reject`: bấm Từ chối - người dùng đã nói không làm việc đó (vd "chưa train", "không kích hoạt").

Người dùng mô phỏng ĐỌC thẻ như người thật:
- Thẻ train chỉ được xác nhận khi cấu hình trên thẻ (do code dựng, không phải chữ LLM) khớp đúng điều người
  dùng đã yêu cầu: dataset, target, tập feature, loại bài toán, metric, thuật toán, max_time. Lệch thì từ chối
  (`config_mismatch`) - không để job sai yêu cầu chạy rồi mới chấm trượt.
- Mỗi ca chỉ đồng ý MỘT lần train (`second_training`).
- Thẻ kích hoạt / tắt / tự kích hoạt chỉ được xác nhận khi job thuộc về chính lượt chạy (`foreign_job`).
Mọi đề nghị, lựa chọn, lý do và kết quả được ghi vào trace để chấm (đề nghị trái ý người dùng là lỗi của
agent, kể cả khi đã bị từ chối).

Không gọi LLM, không đọc token ra ngoài trace (token chỉ dùng trong tiến trình để bấm nút).
"""

from __future__ import annotations

import time

KINDS = ("train", "activate", "deactivate", "auto_activate")
DECISIONS = ("confirm_auto", "confirm", "reject")
# Mặc định: người dùng không đồng ý việc gì chưa nói tới.
DEFAULT_POLICY = {kind: "reject" for kind in KINDS}


def policy_for(case: dict, cases_doc: dict) -> dict:
    """Chính sách của ca: mặc định của bộ ca, ghi đè bởi `consent` của ca."""
    policy = dict(DEFAULT_POLICY)
    policy.update(cases_doc.get("consent_default") or {})
    policy.update(case.get("consent") or {})
    bad = {k: v for k, v in policy.items() if k not in KINDS or v not in DECISIONS}
    if bad:
        raise ValueError(f"consent không hợp lệ ở ca {case.get('id')}: {bad}")
    return policy


def card_mismatch(summary: dict, expected: dict | None) -> list[str]:
    """Các trường của thẻ train lệch so với config người dùng yêu cầu (rỗng = khớp). Thiếu đáp án thì không chặn."""
    if not expected:
        return []
    wrong = [field for field, key in (("dataset_id", "dataset_id"), ("target", "target"), ("problem_type", "problem_type"),
                                      ("metric_sort", "metric_sort"), ("search_algorithm", "search_algorithm"))
             if str(summary.get(field) or "").strip().lower() != str(expected.get(key) or "").strip().lower()]
    try:
        if float(summary.get("max_time")) != float(expected["max_time"]):
            wrong.append("max_time")
    except (TypeError, ValueError, KeyError):
        wrong.append("max_time")
    wanted = {str(f) for f in expected.get("list_feature") or []}
    shown = {str(f) for f in summary.get("features") or []}
    count = summary.get("feature_count")
    # Thẻ chỉ liệt kê tối đa 30 feature: khi bị cắt thì kiểm số lượng + phần hiển thị nằm trong yêu cầu.
    if count != len(wanted) or not (shown == wanted if len(shown) == count else shown <= wanted):
        wrong.append("list_feature")
    return wrong


def _job_of(action: dict) -> str | None:
    summary = action.get("summary") or {}
    return summary.get("job_id")


def process_pending(session, policy: dict, record, own_jobs: set[str], stage: str,
                    expected: dict | None = None) -> list[dict]:
    """
    Bấm nút cho mọi thẻ đang chờ theo chính sách. Trả danh sách quyết định (không có token) để runner
    biết có thẻ nào vừa được XÁC NHẬN (khi đó cần một lượt "tiếp tục" để agent dùng kết quả).

    own_jobs: job tạo trong lượt chạy này (cập nhật tại chỗ khi xác nhận train ra job mới).
    expected: config người dùng đã yêu cầu (task của ca), để đối chiếu thẻ train.
    """
    from agent.actions import ActionError

    decisions = []
    for action in session.team.actions.pending():
        kind = action.get("kind")
        wanted = policy.get(kind, "reject")
        reason = "not_requested" if wanted == "reject" else None
        job_id = _job_of(action)
        mismatch = card_mismatch(action.get("summary") or {}, expected) if kind == "train" else []
        if wanted != "reject" and kind in ("activate", "deactivate", "auto_activate") and job_id not in own_jobs:
            # Người dùng chỉ đồng ý thao tác trên model của chính job họ vừa yêu cầu train.
            wanted, reason = "reject", "foreign_job"
        elif wanted != "reject" and kind == "train" and own_jobs:
            # Mỗi ca chỉ yêu cầu MỘT lần train ("không tạo job mới"): đề nghị train thứ hai bị từ chối.
            wanted, reason = "reject", "second_training"
        elif wanted != "reject" and mismatch:
            wanted, reason = "reject", "config_mismatch"
        offers_auto = bool((action.get("offers") or {}).get("auto_activate"))
        auto = wanted == "confirm_auto" and kind == "train" and offers_auto
        entry = {
            "stage": stage, "action_id": action.get("action_id"), "kind": kind, "decision": wanted, "reason": reason,
            "config_mismatch": mismatch or None,
            "auto_activate_offered": offers_auto, "auto_activate_chosen": auto,
            "summary": action.get("summary"), "job_id": job_id,
        }
        started = time.monotonic()
        try:
            if wanted == "reject":
                session.team.reject_action(action["action_id"], action["token"])
                entry["result"] = {"ok": True, "status": "rejected"}
            else:
                result = session.team.confirm_action(action["action_id"], action["token"], auto_activate=auto)
                entry["result"] = {k: result.get(k) for k in ("ok", "job_id", "error", "auto_activate", "endpoint_url",
                                                               "outcome_unknown", "possible_job_ids")}
                if result.get("ok") and kind == "train" and result.get("job_id"):
                    own_jobs.add(result["job_id"])
        except ActionError as error:
            # Thẻ hết hạn / bị thay giữa lúc đọc và bấm: ghi lại, không coi là quyết định của người dùng.
            entry["result"] = {"ok": False, "error": f"{error.code}: {error}"}
        entry["seconds"] = time.monotonic() - started
        record("consent", entry)
        decisions.append(entry)
    return decisions


def needs_followup(decisions: list[dict]) -> bool:
    """
    Có thẻ bật / tắt model vừa được xác nhận thành công: agent đã dừng lượt để chờ nút (vd định kích hoạt
    rồi predict), người dùng thật sẽ nhắn tiếp. Xác nhận train / tự kích hoạt thì job chạy nền - không cần.
    """
    return any(d["kind"] in ("activate", "deactivate") and d["decision"] != "reject" and (d.get("result") or {}).get("ok")
               for d in decisions)
