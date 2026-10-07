"""
System prompt cho từng agent: phần nền dùng chung + SKILL.md của chính agent đó.

Mỗi agent chỉ thấy skill của mình. Đây là điểm khác với cách cũ (ghép mọi
skill vào một prompt): Data Agent không phải đọc luật huấn luyện, Manager không
phải đọc cách tính thống kê cột - mỗi lời gọi LLM gửi đi ít chữ hơn.

BASE_PROMPT chỉ chứa luật đúng với MỌI agent. Luật thuộc về một lĩnh vực cụ thể
thì viết vào SKILL.md tương ứng, đừng dồn vào đây.
"""

# Local modules
from agent import skills as skills_module


MANAGER = "agent-manager"
PROMPT_AGENT = "prompt-agent"
DATA_AGENT = "data-agent"
MODEL_AGENT = "model-agent"
OPERATION_AGENT = "operation-agent"

SUBAGENTS = (PROMPT_AGENT, DATA_AGENT, MODEL_AGENT, OPERATION_AGENT)


BASE_PROMPT = """Quy tắc chung, đúng với mọi tình huống:

- Chỉ dựa vào kết quả tool. Không bịa ra phản hồi của API, không bịa số liệu.
- Khi một tool trả về {"ok": false}, đọc trường "error" để xử lý. Không gọi lại
  cùng một tool với cùng tham số.
- Không bịa ID. ID phải lấy từ kết quả một tool khác hoặc từ việc được giao.
- Danh sách rỗng là câu trả lời hợp lệ. Đừng suy diễn thành lỗi hệ thống.
- Việc xác thực do hệ thống lo. Không bao giờ hỏi hay truyền token, user_id.
"""

_MANAGER_INTRO = """Bạn là Agent Manager của hệ thống HAutoML. Bạn nói chuyện với
người dùng, phân tích yêu cầu, uỷ thác việc cho 4 sub-agent chuyên trách rồi
kiểm định kết quả trước khi trả lời. Bạn KHÔNG tự gọi API dữ liệu - mọi thao tác
đi qua sub-agent."""

_SUBAGENT_INTRO = """Bạn là {title} trong hệ thống đa agent HAutoML. Agent Manager
giao việc cho bạn; bạn không nói chuyện trực tiếp với người dùng và không thấy
lịch sử hội thoại - mọi ngữ cảnh cần thiết nằm trong việc được giao và phần
"Ngữ cảnh" bên dưới.

Câu trả lời cuối là BÁO CÁO cho Agent Manager: ngắn, có số liệu và ID thật,
nói rõ việc nào xong, việc nào không làm được và vì sao. Thiếu thông tin chặn
việc thì nói rõ thiếu gì, đừng đoán."""

_TITLES = {
    PROMPT_AGENT: "Prompt Agent",
    DATA_AGENT: "Data Agent",
    MODEL_AGENT: "Model Agent",
    OPERATION_AGENT: "Operation Agent",
}


def title(agent: str) -> str:
    return "Agent Manager" if agent == MANAGER else _TITLES.get(agent, agent)


def _roster(loaded: list) -> str:
    """
    Bảng mô tả 4 sub-agent cho Manager, lấy từ `description` trong SKILL.md.

    Đây là chỗ description thực sự được dùng để chọn agent: Manager đọc nó để
    biết việc nào giao cho ai, và việc nào KHÔNG giao cho ai. Sửa phạm vi một
    agent thì sửa description của nó, Manager tự thấy.
    """
    lines = ["# Các sub-agent (chọn đúng agent theo phạm vi dưới đây)", ""]
    for name in SUBAGENTS:
        skill = skills_module.get_skill(name, loaded)
        lines.append(f"- **{title(name)}** (`ask_{name.replace('-agent', '')}_agent`): {skill.description}")
    return "\n".join(lines)


def agent_prompt(agent: str, context: str = "") -> str:
    """
    Ghép system prompt cho một agent.

    Args:
        agent: Tên skill của agent, ví dụ "data-agent".
        context: Dữ liệu chuyển từ agent khác (hồ sơ dữ liệu, R, config đã
            kiểm...). Đặt cuối prompt để phần cố định phía trên giống hệt nhau
            giữa các lần gọi.
    """
    loaded = skills_module.load_skills()
    skill = skills_module.get_skill(agent, loaded)
    intro = _MANAGER_INTRO if agent == MANAGER else _SUBAGENT_INTRO.format(title=title(agent))
    prompt = skills_module.build_prompt(f"{intro}\n\n{BASE_PROMPT}", [skill])

    if agent == MANAGER:
        prompt += "\n\n\n" + _roster(loaded)

    if context:
        prompt += f"\n\n\n# Ngữ cảnh\n\n{context.strip()}"
    return prompt


# System prompt của Agent Manager - agent duy nhất giữ lịch sử hội thoại.
SYSTEM_PROMPT = agent_prompt(MANAGER)
