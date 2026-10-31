"""Mô tả các biến thể ablation. Tách khỏi variants.py để report không phải import agent."""

VARIANT_DOCS = {
    "full": "Hệ thống đầy đủ: Manager + 4 sub-agent + validate_config + kiểm định của watcher.",
    "single-agent": (
        "Một LLM duy nhất cầm toàn bộ tool nghiệp vụ của Data/Model/Operation Agent, "
        "không có Prompt Agent nên không có R và kiểm định ngưỡng. Các chốt code "
        "(validate_config, Handoff) giữ nguyên; trần bước 36 do benchmark chọn (Manager chỉ có 12)."
    ),
    "no-prompt-agent": "Gỡ Prompt Agent: Manager tự hiểu yêu cầu, không có R chuẩn hoá.",
    "no-data-agent": "Gỡ Data Agent: Model Agent tự đọc schema qua đường dự phòng của Handoff.",
    "no-validate": (
        "Tắt validate_config.py (chốt config bằng code). Kiểm tra loại bài toán trong "
        "prepare_training_config và kiểm tra của backend vẫn còn."
    ),
    "no-verify": (
        "Watcher không nhận R: không kiểm định kết quả job theo ràng buộc của người dùng. "
        "Sự kiện job báo Manager rằng kiểm định bị tắt."
    ),
}
