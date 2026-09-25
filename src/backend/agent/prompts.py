"""
System prompt: phần nền + các skill nạp từ agent/skills/.

BASE_PROMPT chỉ chứa luật đúng với MỌI skill. Luật thuộc về một lĩnh vực cụ thể
(tài khoản, dataset, huấn luyện...) thì viết vào file skill tương ứng, đừng dồn
vào đây - dồn vào đây là gửi lại toàn bộ trong mọi lượt gọi LLM.

SYSTEM_PROMPT được ghép lúc import từ tất cả skill có trong thư mục. Muốn nạp
chọn lọc theo chủ đề thì dùng build_system_prompt() với danh sách skill đã lọc.
"""

# Local modules
from agent import skills as skills_module


BASE_PROMPT = """Bạn là agent của hệ thống HAutoML. Bạn thao tác thay người dùng
thông qua các tool được cấp.

Quy tắc chung, đúng với mọi tình huống:

- Chỉ dựa vào kết quả tool. Không bịa ra phản hồi của API, không bịa số liệu.
- Khi một tool trả về {"ok": false}, đọc trường "error" và giải thích cho người
  dùng bằng tiếng Việt. Không gọi lại cùng một tool với cùng tham số.
- Không bịa ID. ID phải lấy từ kết quả một tool khác.
- Danh sách rỗng là câu trả lời hợp lệ. Đừng suy diễn thành lỗi hệ thống.
- Câu trả lời cuối cùng phải ngắn gọn: đã làm gì, kết quả ra sao, bước tiếp theo.
"""


def build_system_prompt(active: list | None = None) -> str:
    """
    Ghép system prompt từ phần nền và các skill.

    active = None nghĩa là nạp mọi skill tìm thấy.
    """
    loaded = skills_module.load_skills() if active is None else active
    return skills_module.build_prompt(BASE_PROMPT, loaded)


# Giá trị mặc định, dùng bởi agent_openai.py và chat.py.
SYSTEM_PROMPT = build_system_prompt()
