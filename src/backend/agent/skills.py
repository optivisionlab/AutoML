"""
Nạp skill từ agent/skills/, theo cấu trúc thư mục:

    skills/
    ├── agent-manager/
    │   └── SKILL.md
    ├── data-agent/
    │   ├── SKILL.md
    │   └── references/
    │       └── dataset_schema.md
    └── model-agent/
        ├── SKILL.md
        ├── references/
        │   └── search_strategies.md
        └── scripts/
            └── validate_config.py

Ba thành phần, ba vai trò khác nhau:

  SKILL.md      Frontmatter (name, description, tools) + hướng dẫn.
                Phần hướng dẫn được GHÉP THẲNG vào system prompt -> luôn tốn
                token mỗi lượt. Viết ngắn, chỉ giữ luật hay dùng.

  references/   KHÔNG nạp vào prompt. Agent chỉ thấy tên + mô tả, muốn đọc thì
                gọi tool read_reference. Đây là chỗ để tài liệu dài: bảng tra,
                quy tắc tiền xử lý, danh sách thuật toán. Nhờ vậy tài liệu dài
                bao nhiêu cũng không làm phình prompt.

  scripts/      Code Python, gọi từ tools.py. KHÔNG cho LLM tự chạy.
                Dùng cho việc phải chính xác tuyệt đối: kiểm tra param space,
                validate config trước khi gửi đi train.
"""

# Standard libraries
import re
from dataclasses import dataclass, field
from pathlib import Path

# Third party libraries
import yaml


SKILLS_DIR = Path(__file__).resolve().parent / "skills"

# Frontmatter: bắt buộc mở đầu bằng --- và đóng bằng --- trên dòng riêng.
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

# Dòng đầu tiên không rỗng của file reference được dùng làm mô tả ngắn.
_MAX_REF_SUMMARY = 120


class SkillError(Exception):
    """File skill sai định dạng. Báo sớm còn hơn để agent chạy với hướng dẫn thiếu."""


@dataclass
class Reference:
    skill: str
    name: str
    summary: str
    path: Path

    @property
    def ref_id(self) -> str:
        """Định danh agent dùng để yêu cầu đọc, ví dụ 'data-agent/preprocessing_rules'."""
        return f"{self.skill}/{self.name}"


@dataclass
class Skill:
    name: str
    description: str
    tools: list[str] = field(default_factory=list)
    instructions: str = ""
    # always=true nghĩa là luôn nạp, không phụ thuộc chủ đề hội thoại.
    always: bool = False
    directory: Path | None = None
    references: list[Reference] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)


def parse_skill_md(text: str, source: str = "<string>") -> Skill:
    match = _FRONTMATTER.match(text)
    if not match:
        raise SkillError(f"{source}: thiếu frontmatter YAML giữa hai dòng ---")

    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as error:
        raise SkillError(f"{source}: frontmatter không phải YAML hợp lệ ({error})") from error

    if not isinstance(meta, dict):
        raise SkillError(f"{source}: frontmatter phải là một map key: value")

    for required in ("name", "description"):
        if not meta.get(required):
            raise SkillError(f"{source}: thiếu trường bắt buộc '{required}'")

    tools = meta.get("tools") or []
    if not isinstance(tools, list):
        raise SkillError(f"{source}: 'tools' phải là danh sách")

    return Skill(
        name=str(meta["name"]),
        description=str(meta["description"]),
        tools=[str(t) for t in tools],
        instructions=match.group(2).strip(),
        always=bool(meta.get("always", False)),
    )


def _summarize(path: Path) -> str:
    """Lấy dòng tiêu đề đầu tiên làm mô tả ngắn cho file reference."""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:_MAX_REF_SUMMARY]
    return path.stem


def load_skills(directory: Path | None = None) -> list[Skill]:
    """
    Đọc mọi thư mục con có SKILL.md.

    Sắp theo tên thư mục để thứ tự ghép prompt ổn định giữa các lần chạy.
    """
    root = directory or SKILLS_DIR
    if not root.is_dir():
        return []

    skills = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        skill_md = folder / "SKILL.md"
        if not skill_md.is_file():
            continue

        skill = parse_skill_md(skill_md.read_text(encoding="utf-8"), source=f"{folder.name}/SKILL.md")
        skill.directory = folder

        refs_dir = folder / "references"
        if refs_dir.is_dir():
            skill.references = [
                Reference(skill=folder.name, name=p.stem, summary=_summarize(p), path=p)
                for p in sorted(refs_dir.glob("*.md"))
            ]

        scripts_dir = folder / "scripts"
        if scripts_dir.is_dir():
            skill.scripts = [p.name for p in sorted(scripts_dir.glob("*.py")) if p.name != "__init__.py"]

        skills.append(skill)

    return skills


def build_prompt(base: str, skills: list[Skill]) -> str:
    """
    Ghép system prompt: phần nền + hướng dẫn từng skill.

    File reference KHÔNG được ghép vào - chỉ liệt kê tên và mô tả, để agent biết
    có gì mà gọi read_reference khi cần.
    """
    parts = [base.strip()]

    for skill in skills:
        section = [f"# SKILL: {skill.name}", "", skill.description]

        if skill.instructions:
            section += ["", skill.instructions]

        if skill.references:
            section += ["", "Tài liệu tra cứu thêm (dùng tool read_reference khi cần):"]
            section += [f"- `{ref.ref_id}` — {ref.summary}" for ref in skill.references]

        parts.append("\n".join(section))

    return "\n\n\n".join(parts)


def allowed_tools(skills: list[Skill]) -> set[str]:
    """Tập tool của các skill được nạp. Rỗng nghĩa là không lọc."""
    names: set[str] = set()
    for skill in skills:
        names.update(skill.tools)
    return names


def find_reference(ref_id: str, skills: list[Skill] | None = None) -> Reference | None:
    """Tra một reference theo định danh 'skill/tên'."""
    for skill in skills if skills is not None else load_skills():
        for ref in skill.references:
            if ref.ref_id == ref_id:
                return ref
    return None


def validate(skills: list[Skill], known_tools: set[str]) -> list[str]:
    """
    Soát lỗi thường gặp, trả về danh sách cảnh báo.

    Hai lỗi hay xảy ra nhất: khai tool không tồn tại (gõ sai tên), và tool có
    thật nhưng không skill nào khai - lúc đó nó sẽ không bao giờ được nạp.
    """
    problems = []
    seen_names: set[str] = set()
    declared: set[str] = set()

    for skill in skills:
        if skill.name in seen_names:
            problems.append(f"trùng tên skill: {skill.name}")
        seen_names.add(skill.name)

        for tool in skill.tools:
            if tool not in known_tools:
                problems.append(f"{skill.name}: khai tool không tồn tại '{tool}'")
            declared.add(tool)

    for orphan in sorted(known_tools - declared):
        problems.append(f"tool '{orphan}' không thuộc skill nào, sẽ không được nạp")

    return problems
