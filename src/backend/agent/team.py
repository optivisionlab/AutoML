"""
Agent Manager uỷ thác cho 4 sub-agent - các mũi tên trong sơ đồ trang 1.

    Manager ──ask_prompt_agent──▶ ① Prompt Agent   → R (JSON 6 khoá)
            ──ask_data_agent────▶ ② Data Agent     → hồ sơ dữ liệu ──┐ "dữ liệu"
            ──ask_model_agent───▶ ③ Model Agent  ◀───────────────────┘
                                       │ submit_config
                                       ▼
                               validate_config.py (CODE)
                                       │ "config hợp lệ" → config_id
            ──ask_operation_agent─▶ ④ Operation Agent → start_training(config_id)
                                       │
                                       ▼ JobWatcher: get_job_info tới khi status ≠ 0

Mỗi sub-agent là một vòng LLM riêng: system prompt riêng (SKILL.md của nó),
tập tool riêng, và KHÔNG thấy lịch sử hội thoại. Thứ duy nhất đi giữa các agent
là Handoff - dữ liệu có cấu trúc do CODE chuyển, không phải LLM chép lại. Nhờ
vậy Model Agent nhận đúng schema mà Data Agent đã đọc, và Operation Agent chỉ
chạy được config đã qua validate_config (nó chỉ cầm config_id, không tự điền).
"""

# Standard libraries
import json
import uuid
from dataclasses import dataclass, field

# Local modules
from agent import prompts, skills as skills_module, tools, tracing
from agent.agent_openai import (
    SUBAGENT_MAX_STEPS,
    _DISPATCH,
    _accumulate_usage,
    run_tool_loop,
    schemas_for,
)
from agent.prompts import DATA_AGENT, MANAGER, MODEL_AGENT, OPERATION_AGENT, PROMPT_AGENT


PROBLEM_TYPES = ("classification", "regression")
REQUIREMENT_KEYS = ("user", "problem", "dataset", "model", "knowledge", "service")
SEARCH_ALGORITHMS = ("grid_search", "genetic_algorithm", "bayesian_search")
_CONSTRAINT_OPS = (">=", ">", "<=", "<")

# Dataset rộng hàng trăm cột thì hồ sơ đầy đủ quá dài cho prompt Model Agent.
_MAX_PROFILE_COLUMNS = 60
_SAMPLES_PER_COLUMN = 3
# Prompt Agent không thấy lịch sử, chỉ thấy vài câu gần nhất của người dùng -
# đủ để không mất chi tiết như "target là cột Type" nói ở lượt trước.
_RECENT_USER_MESSAGES = 6


class AgentOutputError(RuntimeError):
    """Model không trả được JSON hợp lệ kể cả sau khi được nhắc sửa."""


def parse_json(text: str) -> dict:
    """
    Bóc object JSON đầu tiên khỏi câu trả lời của model.

    Không dùng response_format: các provider hỗ trợ không giống nhau, có bên trả
    400 khi gặp tham số lạ. Model hay bọc JSON trong ```json ... ``` hoặc thêm
    câu dẫn kể cả khi đã được dặn, nên lấy từ { đầu tiên tới } cuối cùng.
    """
    cleaned = (text or "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("không tìm thấy object JSON trong câu trả lời")

    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("JSON phải là một object")
    return value


def profile_brief(schema: dict) -> dict:
    """Hồ sơ dữ liệu gọn cho prompt: bỏ sample_rows, cắt bớt giá trị mẫu và số cột."""
    columns = schema.get("columns") or []
    return {
        "dataset_id": schema.get("dataset_id"),
        "data_name": schema.get("data_name"),
        "problem_type": schema.get("problem_type"),
        "total_rows": schema.get("total_rows"),
        "column_count": schema.get("column_count"),
        "target_candidates": schema.get("target_candidates"),
        "columns": [
            {
                "name": c.get("name"),
                "type": c.get("python_type"),
                "distinct": c.get("distinct_in_preview"),
                "missing": c.get("missing_in_preview"),
                "can_be_target": c.get("can_be_target"),
                "samples": (c.get("sample_values") or [])[:_SAMPLES_PER_COLUMN],
            }
            for c in columns[:_MAX_PROFILE_COLUMNS]
        ],
        "columns_truncated": len(columns) > _MAX_PROFILE_COLUMNS,
        "note": "distinct/missing tính trên 50 dòng preview, không phải toàn bộ dataset.",
    }


def _intish(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_requirements(raw: dict, datasets: list[dict]) -> tuple[dict, list, list]:
    """
    Soát R do Prompt Agent sinh ra bằng code.

    LLM có thể chép sai ID, bịa loại bài toán, hoặc viết ràng buộc lung tung.
    Hàm này ép R về đúng 6 khoá, chỉ giữ dataset ID có thật trong kho của người
    dùng, và chỉ giữ ràng buộc có dạng so sánh được.

    Returns:
        (R, missing, notes) - missing là câu cần hỏi lại người dùng, notes là
        những gì code đã tự sửa/suy ra (để Manager nói lại cho người dùng).
    """
    requirements = {
        key: dict(raw.get(key)) if isinstance(raw.get(key), dict) else {}
        for key in REQUIREMENT_KEYS
    }
    missing = [str(item).strip() for item in raw.get("missing") or [] if str(item).strip()]
    notes: list[str] = []

    by_id = {d["id"]: d for d in datasets if d.get("id")}
    dataset = requirements["dataset"]
    intent = str(requirements["user"].get("intent") or "").lower()

    # --- dataset: chỉ nhận ID có thật ---
    dataset_id = dataset.get("id")
    if dataset_id and dataset_id not in by_id:
        name = str(dataset.get("name") or "").strip().lower()
        matches = [d for d in datasets if name and str(d.get("name") or "").lower() == name]
        if len(matches) == 1:
            dataset["id"] = matches[0]["id"]
            notes.append(f"Sửa dataset id theo tên '{matches[0]['name']}'.")
        else:
            dataset["id"] = None
            notes.append(f"Bỏ dataset id '{dataset_id}' vì không có trong kho của người dùng.")

    if not dataset.get("id") and intent in ("train", "analyze"):
        if not datasets:
            missing.append("Người dùng chưa có dataset nào - cần tải dataset lên trước.")
        elif len(datasets) == 1:
            dataset["id"] = datasets[0]["id"]
            notes.append(f"Người dùng chỉ có một dataset nên dùng '{datasets[0]['name']}'.")
        elif not any("dataset" in item.lower() for item in missing):
            names = ", ".join(f"'{d['name']}'" for d in datasets[:10])
            missing.append(f"Dùng dataset nào? Người dùng đang có: {names}.")

    known = by_id.get(dataset.get("id"))
    if known:
        dataset["name"] = known.get("name")
        dataset.setdefault("type", known.get("type"))

    # --- problem ---
    problem = requirements["problem"]
    problem_type = str(problem.get("type") or "").strip().lower()
    if problem_type not in PROBLEM_TYPES:
        fallback = (known or {}).get("type")
        problem["type"] = fallback if fallback in PROBLEM_TYPES else None
        if problem_type and problem["type"]:
            notes.append(f"Loại bài toán '{problem_type}' không hỗ trợ, dùng '{problem['type']}' theo dataset.")
    else:
        problem["type"] = problem_type

    constraints = []
    for item in problem.get("constraints") or []:
        if not isinstance(item, dict):
            continue
        metric = str(item.get("metric") or "").strip().lower()
        op = str(item.get("op") or "").strip()
        try:
            value = float(item.get("value"))
        except (TypeError, ValueError):
            value = None
        if metric and op in _CONSTRAINT_OPS and value is not None:
            constraints.append({"metric": metric, "op": op, "value": value})
        else:
            notes.append(f"Bỏ ràng buộc không so sánh được: {item}.")
    problem["constraints"] = constraints

    max_time = _intish(problem.get("max_time"))
    problem["max_time"] = max_time if max_time and 60 <= max_time <= 86400 else None

    algorithm = requirements["model"].get("search_algorithm")
    if algorithm not in SEARCH_ALGORITHMS:
        requirements["model"]["search_algorithm"] = None

    return requirements, missing, notes


@dataclass
class Handoff:
    """Dữ liệu đi giữa các agent trong một phiên chat."""

    # R mới nhất từ Prompt Agent.
    requirements: dict | None = None
    # dataset_id -> kết quả get_dataset_schema mà Data Agent đã đọc.
    profiles: dict = field(default_factory=dict)
    # config_id -> config đã qua validate_config, do Model Agent chốt.
    configs: dict = field(default_factory=dict)
    # job_id -> config_id đã sinh ra job đó.
    jobs: dict = field(default_factory=dict)


class AgentTeam:
    """
    Dựng tool cho từng agent và chạy sub-agent khi Manager giao việc.

    Sống trong ChatSession: dùng chung client API (token người dùng), client
    LLM, bộ đếm token và kênh sự kiện của phiên.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.handoff = Handoff()

    def reset(self) -> None:
        self.handoff = Handoff()

    # ------------------------------------------------------------------ dispatch

    def tools_for(self, agent: str) -> tuple[list, dict]:
        """Schema + hàm của đúng các tool khai trong SKILL.md của agent."""
        names = skills_module.get_skill(agent).tools
        bound = {
            "ask_prompt_agent": self.ask_prompt_agent,
            "ask_data_agent": self.ask_data_agent,
            "ask_model_agent": self.ask_model_agent,
            "ask_operation_agent": self.ask_operation_agent,
            "get_dataset_schema": self.get_dataset_schema,
            "submit_config": self.submit_config,
            "start_training": self.start_training,
            "watch_job": self.watch_job,
        }
        dispatch = {
            name: bound.get(name) or _DISPATCH[name]
            for name in names
            if name in bound or name in _DISPATCH
        }
        return schemas_for(names), dispatch

    def _emit(self, type: str, **data) -> None:
        self.session.events.emit(type, **data)

    # ------------------------------------------------------------ chạy sub-agent

    def _run_subagent(self, agent: str, task: str, context: str = "") -> dict:
        """Chạy một sub-agent tới khi nó báo cáo xong. Không raise."""
        schemas, dispatch = self.tools_for(agent)
        messages = [
            {"role": "system", "content": prompts.agent_prompt(agent, context)},
            {"role": "user", "content": task},
        ]

        self._emit("agent_start", agent=agent, task=task[:300])
        with tracing.observe(agent, as_type="agent", input={"task": task, "context": context}) as observation:
            result = self._run_loop(agent, messages, schemas, dispatch)
            tracing.end(observation, output=result.get("report"), error=result.get("error"))
        return result

    def _run_loop(self, agent: str, messages: list, schemas: list, dispatch: dict) -> dict:
        try:
            report = run_tool_loop(
                self.session.llm,
                self.session.config.model,
                messages,
                schemas,
                dispatch,
                self.session.api,
                self.session.usage,
                agent=agent,
                emit=self.session.events.emit,
                max_steps=SUBAGENT_MAX_STEPS,
            )
        except Exception as error:  # noqa: BLE001 - sub-agent hỏng không được làm chết Manager
            message = f"{prompts.title(agent)} lỗi khi gọi LLM: {type(error).__name__}: {error}"
            self._emit("agent_done", agent=agent, ok=False, error=message)
            return {"ok": False, "agent": agent, "error": message}

        if report is None:
            message = f"{prompts.title(agent)} chạy quá {SUBAGENT_MAX_STEPS} bước mà chưa xong."
            self._emit("agent_done", agent=agent, ok=False, error=message)
            return {"ok": False, "agent": agent, "error": message}

        self._emit("agent_done", agent=agent, ok=True)
        return {"ok": True, "agent": agent, "report": report}

    def _ask_json(self, agent: str, system: str, user: str) -> dict:
        """Một lượt LLM không tool, bắt buộc trả JSON. Hỏng thì nhắc sửa đúng một lần."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        for attempt in range(2):
            response = self.session.llm.chat.completions.create(
                model=self.session.config.model, messages=messages,
            )
            _accumulate_usage(self.session.usage, response.usage)
            if response.usage is not None:
                self._emit(
                    "llm_call",
                    agent=agent,
                    prompt_tokens=response.usage.prompt_tokens or 0,
                    completion_tokens=response.usage.completion_tokens or 0,
                    total_tokens=response.usage.total_tokens or 0,
                )

            text = response.choices[0].message.content or ""
            try:
                return parse_json(text)
            except ValueError as error:
                if attempt:
                    raise AgentOutputError(f"{prompts.title(agent)} không trả JSON hợp lệ: {error}") from error
                messages += [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": (
                        f"Câu trả lời không phải JSON hợp lệ ({error}). Trả lại DUY NHẤT một "
                        "object JSON đúng định dạng đã yêu cầu, không kèm chữ nào khác."
                    )},
                ]
        raise AgentOutputError(f"{prompts.title(agent)} không trả JSON hợp lệ")

    # ------------------------------------------------- tool của Agent Manager

    def ask_prompt_agent(self, api, request: str) -> dict:
        """① Prompt Agent: chuẩn hoá yêu cầu thành R. Không tool, một lượt JSON."""
        listing = tools.list_my_datasets(api)
        datasets = [
            {"id": d.get("_id"), "name": d.get("dataName"), "type": d.get("dataType")}
            for d in (listing.get("datasets") or [])
        ] if listing.get("ok") else []

        context = json.dumps(
            {
                "datasets_of_user": datasets,
                "recent_user_messages": self.session.recent_user_messages(_RECENT_USER_MESSAGES),
            },
            ensure_ascii=False,
            indent=1,
        )

        self._emit("agent_start", agent=PROMPT_AGENT, task=request[:300])
        with tracing.observe(PROMPT_AGENT, as_type="agent", input={"request": request, "context": context}) as observation:
            try:
                raw = self._ask_json(PROMPT_AGENT, prompts.agent_prompt(PROMPT_AGENT, context), request)
            except Exception as error:  # noqa: BLE001
                message = f"Prompt Agent lỗi: {type(error).__name__}: {error}"
                self._emit("agent_done", agent=PROMPT_AGENT, ok=False, error=message)
                tracing.end(observation, error=message)
                return {"ok": False, "agent": PROMPT_AGENT, "error": message}

            requirements, missing, notes = normalize_requirements(raw, datasets)
            # Ghi cả bản LLM trả lẫn bản sau khi code soát, để thấy code đã sửa gì.
            tracing.end(observation, output={"raw": raw, "requirements": requirements, "missing": missing, "notes": notes})

        self.handoff.requirements = requirements
        self._emit("agent_done", agent=PROMPT_AGENT, ok=True, missing=missing)

        return {
            "ok": True,
            "agent": PROMPT_AGENT,
            "requirements": requirements,
            "missing": missing,
            "notes": notes,
            "clear": not missing,
        }

    def ask_data_agent(self, api, task: str, dataset_id: str = "") -> dict:
        """② Data Agent: tra cứu dataset. Schema nó đọc được giữ lại cho Model Agent."""
        if dataset_id:
            task = f"{task}\n\ndataset_id: {dataset_id}"

        context = ""
        requirements = self.handoff.requirements
        if requirements and requirements["problem"].get("type"):
            context = f"Loại bài toán người dùng nhắm tới: {requirements['problem']['type']}."

        before = set(self.handoff.profiles)
        result = self._run_subagent(DATA_AGENT, task, context)
        result["profiled_datasets"] = sorted(set(self.handoff.profiles) - before)
        return result

    def ask_model_agent(self, api, task: str, dataset_id: str) -> dict:
        """③ Model Agent: ra quyết định config từ R + hồ sơ dữ liệu. Không bấm chạy."""
        requirements = self.handoff.requirements or {}
        wanted_type = (requirements.get("problem") or {}).get("type") or ""

        profile = self.handoff.profiles.get(dataset_id)
        # Chưa có hồ sơ (Manager bỏ qua Data Agent) hoặc hồ sơ đọc theo loại bài
        # toán khác - target_candidates phụ thuộc loại bài toán nên phải đọc lại.
        if profile is None or (wanted_type and profile.get("problem_type") != wanted_type):
            profile = self.get_dataset_schema(api, dataset_id=dataset_id, problem_type=wanted_type)
            if not profile.get("ok"):
                return {"ok": False, "agent": MODEL_AGENT, "error": profile.get("error")}

        context = "\n\n".join([
            "## Yêu cầu đã chuẩn hoá (R, từ Prompt Agent)",
            json.dumps(requirements or "Chưa có - Manager chưa gọi Prompt Agent.", ensure_ascii=False, indent=1),
            "## Hồ sơ dữ liệu (từ Data Agent)",
            json.dumps(profile_brief(profile), ensure_ascii=False, indent=1),
        ])

        before = set(self.handoff.configs)
        result = self._run_subagent(MODEL_AGENT, f"{task}\n\ndataset_id: {dataset_id}", context)
        result["configs"] = [
            {key: self.handoff.configs[cid][key] for key in ("config_id", "config", "warnings")}
            for cid in self.handoff.configs
            if cid not in before
        ]
        if result["ok"] and not result["configs"]:
            result["note"] = "Model Agent chưa chốt config nào - đọc report để biết còn thiếu gì."
        return result

    def ask_operation_agent(self, api, task: str) -> dict:
        """④ Operation Agent: chạy config đã kiểm, theo dõi job, kích hoạt, dự đoán."""
        ready = [
            {
                "config_id": entry["config_id"],
                "dataset_id": entry["dataset_id"],
                "config": entry["config"],
                "already_started_job": entry.get("job_id"),
            }
            for entry in self.handoff.configs.values()
        ]
        context = "\n\n".join([
            "## Config đã qua validate_config (chỉ chạy được các config_id này)",
            json.dumps(ready, ensure_ascii=False, indent=1) if ready else "Chưa có config nào.",
            "## Job đang được theo dõi nền",
            ", ".join(self.session.watcher.active()) or "Không có.",
        ])

        before = set(self.handoff.jobs)
        result = self._run_subagent(OPERATION_AGENT, task, context)
        result["jobs_started"] = sorted(set(self.handoff.jobs) - before)
        result["watching"] = self.session.watcher.active()
        return result

    # ------------------------------------------------- tool của sub-agent

    def get_dataset_schema(self, api, dataset_id: str, problem_type: str = "", sample_rows: int = 3) -> dict:
        """get_dataset_schema của Data Agent, giữ kết quả lại làm hồ sơ cho Model Agent."""
        result = tools.get_dataset_schema(api, dataset_id=dataset_id, problem_type=problem_type, sample_rows=sample_rows)
        if result.get("ok"):
            self.handoff.profiles[dataset_id] = result
        return result

    def submit_config(
        self,
        api,
        dataset_id: str,
        target: str,
        list_feature: list,
        metric_sort: str,
        problem_type: str = "",
        search_algorithm: str = tools.DEFAULT_SEARCH_ALGORITHM,
        max_time: int = tools.DEFAULT_MAX_TIME,
        rationale: str = "",
    ) -> dict:
        """Model Agent chốt config. Kiểm bằng validate_config.py; hợp lệ mới có config_id."""
        if not problem_type and self.handoff.requirements:
            problem_type = self.handoff.requirements["problem"].get("type") or ""

        with tracing.observe(
            "validate_config",
            as_type="guardrail",
            input={"dataset_id": dataset_id, "target": target, "list_feature": list_feature,
                   "metric_sort": metric_sort, "search_algorithm": search_algorithm, "max_time": max_time},
        ) as observation:
            prepared = tools.prepare_training_config(
                api,
                dataset_id=dataset_id,
                target=target,
                list_feature=list_feature,
                metric_sort=metric_sort,
                problem_type=problem_type,
                search_algorithm=search_algorithm,
                max_time=max_time,
            )
            tracing.end(
                observation,
                output={k: prepared.get(k) for k in ("ok", "config", "errors", "warnings")},
                warning=None if prepared.get("ok") else "Config bị chặn",
            )
        self._emit(
            "config_checked",
            agent=MODEL_AGENT,
            ok=bool(prepared.get("ok")),
            errors=prepared.get("errors") or ([prepared.get("error")] if not prepared.get("ok") else []),
        )
        if not prepared.get("ok"):
            return prepared

        config_id = f"cfg_{uuid.uuid4().hex[:6]}"
        self.handoff.configs[config_id] = {
            "config_id": config_id,
            "dataset_id": dataset_id,
            "config": prepared["config"],
            "warnings": prepared["warnings"],
            "rationale": rationale,
        }
        return {
            "ok": True,
            "config_id": config_id,
            "config": prepared["config"],
            "warnings": prepared["warnings"],
            "note": (
                "Config đã qua validate_config. Báo config_id này cho Manager để chuyển "
                "Operation Agent chạy - bạn KHÔNG bấm chạy."
            ),
        }

    def start_training(self, api, config_id: str) -> dict:
        """Operation Agent chạy config theo config_id. Không nhận config tự điền."""
        entry = self.handoff.configs.get(config_id)
        if entry is None:
            return {
                "ok": False,
                "error": (
                    f"Không có config '{config_id}'. Chỉ chạy được config đã được Model Agent "
                    "chốt qua submit_config (đã kiểm bằng validate_config)."
                ),
                "available_config_ids": sorted(self.handoff.configs),
            }
        if entry.get("job_id"):
            return {
                "ok": False,
                "error": f"Config '{config_id}' đã chạy thành job {entry['job_id']}. Không chạy lại trùng.",
                "job_id": entry["job_id"],
            }

        config = entry["config"]
        result = tools.start_training(
            api,
            dataset_id=entry["dataset_id"],
            target=config["target"],
            list_feature=config["list_feature"],
            metric_sort=config["metric_sort"],
            problem_type=config["problem_type"],
            search_algorithm=config["search_algorithm"],
            max_time=config["max_time"],
        )
        if not result.get("ok") or not result.get("job_id"):
            return result

        job_id = result["job_id"]
        entry["job_id"] = job_id
        self.handoff.jobs[job_id] = config_id
        self._emit("job_started", agent=OPERATION_AGENT, job_id=job_id, config_id=config_id, config=config)
        self.session.watcher.watch(
            job_id,
            max_time=config.get("max_time"),
            requirements=self.handoff.requirements,
            trace_context=tracing.current_context(),
        )

        result["watching"] = True
        result["note"] = (
            "Job đã vào hàng đợi và chạy nền. Hệ thống tự theo dõi tới khi xong và báo "
            "cho người dùng - KHÔNG có kết quả ngay."
        )
        return result

    def watch_job(self, api, job_id: str) -> dict:
        """Bật theo dõi nền cho một job có sẵn của người dùng."""
        job, problem = tools.find_own_job(api, job_id)
        if problem:
            return problem

        status = job.get("status")
        if status != 0:
            return {
                "ok": True,
                "job_id": job_id,
                "status": status,
                "note": "Job đã kết thúc, không cần theo dõi. Dùng get_job_info để xem kết quả.",
            }

        # Ràng buộc trong R chỉ áp cho job do chính phiên này khởi tạo.
        requirements = self.handoff.requirements if job_id in self.handoff.jobs else None
        started = self.session.watcher.watch(
            job_id,
            max_time=(job.get("config") or {}).get("max_time"),
            requirements=requirements,
            trace_context=tracing.current_context(),
        )
        return {"ok": True, "job_id": job_id, "status": 0, "watching": True, "already_watching": not started}


__all__ = ["AgentTeam", "Handoff", "MANAGER", "normalize_requirements", "parse_json", "profile_brief"]
