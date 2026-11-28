"""Chạy kịch bản và tổng hợp kết quả theo chiều đánh giá / độ khó."""
from collections import defaultdict
from typing import Callable

from agent.agent_openai import describe_error
from agent.evals.backend import EvalBackend
from agent.evals.scenarios import Outcome, Scenario

# Một bộ đánh giá có mọi kịch bản đạt dưới ngưỡng này thì coi là hồi quy.
DEFAULT_MIN_PASS_RATE = 0.8


def run_scenario(scenario: Scenario, make_session: Callable[[EvalBackend], object]) -> dict:
    """Chạy MỘT lần một kịch bản trên phiên mới. Không raise: lỗi được ghi vào kết quả."""
    backend = EvalBackend()
    session = make_session(backend)
    tool_calls: list[str] = []
    session.events.subscribe(lambda event: tool_calls.append(event["name"]) if event["type"] == "tool_call" else None)
    answers: list[str] = []
    error = None
    try:
        for turn in scenario.turns:
            answers.append(session.send(turn))
    except Exception as exc:  # noqa: BLE001 - lỗi là một kết quả cần chấm, không làm dừng cả bộ
        error = describe_error(exc)
    finally:
        pending = []
        for card in session.team.actions.pending():
            action = session.team.actions.get(card["action_id"])
            pending.append({"kind": card["kind"], "params": dict(getattr(action, "params", {}) or {}),
                            "summary": card.get("summary")})
        outcome = Outcome(
            answers=answers, backend=backend, pending=pending, configs=dict(session.team.handoff.configs),
            tool_calls=tool_calls, llm_calls=session.usage["calls"], total_tokens=session.usage["total_tokens"],
            cached_tokens=session.usage.get("cached_tokens", 0), error=error,
        )
        session.close()
    return score(scenario, outcome)


def score(scenario: Scenario, outcome: Outcome) -> dict:
    checks = []
    for check in scenario.all_checks():
        try:
            passed = bool(check.fn(outcome))
        except Exception:  # noqa: BLE001 - điều kiện kiểm hỏng = không đạt
            passed = False
        checks.append({"name": check.name, "dimension": check.dimension, "passed": passed})
    return {
        "scenario": scenario.id,
        "complexity": scenario.complexity,
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
        "llm_calls": outcome.llm_calls,
        "tool_calls": len(outcome.tool_calls),
        "tools_used": outcome.tool_calls,
        "total_tokens": outcome.total_tokens,
        "cached_tokens": outcome.cached_tokens,
        "error": outcome.error,
        "last_answer": outcome.last[:500],
    }


def summarize(runs: list[dict]) -> dict:
    """Tỉ lệ đạt theo kịch bản, theo chiều, theo độ khó; chi phí trung bình mỗi lần chạy."""
    by_scenario: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        by_scenario[run["scenario"]].append(run)

    def rate(items, predicate) -> float:
        return round(sum(1 for i in items if predicate(i)) / len(items), 3) if items else 0.0

    dimensions: dict[str, list[bool]] = defaultdict(list)
    complexity: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        complexity[run["complexity"]].append(run)
        for dimension in {c["dimension"] for c in run["checks"]}:
            dimensions[dimension].append(all(c["passed"] for c in run["checks"] if c["dimension"] == dimension))

    return {
        "runs": len(runs),
        "pass_rate": rate(runs, lambda r: r["passed"]),
        "by_dimension": {d: round(sum(v) / len(v), 3) for d, v in sorted(dimensions.items())},
        "by_complexity": {k: rate(v, lambda r: r["passed"]) for k, v in sorted(complexity.items())},
        "by_scenario": {
            name: {
                "pass_rate": rate(items, lambda r: r["passed"]),
                "failed_checks": sorted({c["name"] for r in items for c in r["checks"] if not c["passed"]}),
                "avg_llm_calls": round(sum(r["llm_calls"] for r in items) / len(items), 1),
                "avg_tokens": round(sum(r["total_tokens"] for r in items) / len(items)),
            }
            for name, items in sorted(by_scenario.items())
        },
        "avg_tokens_per_run": round(sum(r["total_tokens"] for r in runs) / len(runs)) if runs else 0,
        "cached_token_ratio": round(
            sum(r["cached_tokens"] for r in runs) / max(1, sum(r["total_tokens"] for r in runs)), 3),
    }


def run_suite(scenarios: list[Scenario], make_session: Callable[[EvalBackend], object], repeat: int = 1,
              on_run: Callable[[dict], None] | None = None) -> dict:
    runs = []
    for scenario in scenarios:
        for _ in range(max(1, repeat)):
            result = run_scenario(scenario, make_session)
            runs.append(result)
            if on_run is not None:
                on_run(result)
    return {"summary": summarize(runs), "runs": runs}
