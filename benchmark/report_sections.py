"""
Các mục báo cáo thêm ở protocol v5: nhóm S (SQL Agent + adapter), so sánh baseline, đánh giá theo từng
agent, tài nguyên, đối chiếu bài AutoML-Agent và kiểm định cặp cho ablation.

Nguyên tắc chung: luôn ghi n; khoảng tin cậy 95% (t cho trung bình, Wilson cho tỷ lệ); KHÔNG gộp bốn chiều
(đúng chức năng, độ tin cậy luồng, chất lượng ML, hiệu quả) thành một điểm; không kết luận "tốt hơn có ý
nghĩa thống kê" khi kiểm định không đủ bằng chứng hoặc cặp không chung seed.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark import stats as S
from benchmark.common import ARTIFACTS, BENCH_DIR, load_json

PRIMARY = {"classification": ("f1_macro", "↑"), "regression": ("mae", "↓"), "time_series": ("rmse", "↓")}
SECONDARY = {"classification": ("accuracy", "balanced_accuracy"), "regression": ("rmse", "r2", "rmsle"),
             "time_series": ("mae", "rmsle", "nps")}
METHOD_ORDER = ["hautoml_engine", "optuna_tpe", "flaml", "autogluon", "xgboost", "random_forest", "linear", "dummy",
                "lag_gbr", "lag_ridge", "naive_last_week", "naive_last_day"]
METHOD_KIND = {
    "hautoml_engine": "Engine HAutoML, config đúng, không LLM", "optuna_tpe": "AutoML tối ưu (TPE, cùng ngân sách)",
    "flaml": "AutoML (FLAML)", "autogluon": "AutoML (AutoGluon)", "xgboost": "Mô hình cố định", "random_forest": "Mô hình cố định",
    "linear": "Mô hình cố định", "dummy": "Naive", "lag_gbr": "Mô hình cố định (trễ, đệ quy)",
    "lag_ridge": "Mô hình cố định (trễ, đệ quy)", "naive_last_week": "Naive theo mùa", "naive_last_day": "Naive theo mùa",
}
AGENT_ORDER = ["agent-manager", "prompt-agent", "data-agent", "model-agent", "operation-agent", "sql-agent"]


def _table(header, rows):
    from benchmark.report import _table as table
    return table(header, rows)


def _ci(values, digits=3) -> str:
    return S.fmt_ci(S.describe(values), digits)


def _ratio(pairs: list[list[int]]) -> str:
    ok = sum(p[0] for p in pairs)
    total = sum(p[1] for p in pairs)
    return S.fmt_rate(ok, total)


# ------------------------------------------------------------------------------ dữ liệu

BUDGETED = {"optuna_tpe", "flaml", "autogluon", "hautoml_engine"}


def current_data_hashes() -> dict | None:
    """Hash các file split hiện tại (manifest đã kiểm); None khi máy này không có dữ liệu."""
    from benchmark import protocol
    try:
        return {**protocol.check_data()["sha256"], **protocol.check_ts_data()["sha256"]}
    except (ValueError, OSError, KeyError):
        return None


def load_baselines(ids: list[str] | None) -> list[dict]:
    """
    metrics.json của các đợt baseline (offline + engine), có kiểm nguồn gốc:
    - dữ liệu của đợt (baselines_manifest.json / test_sha256 của engine) phải trùng split hiện tại;
    - không có hai quan sát cùng (method, dataset, seed, ngân sách) từ hai đợt khác nhau.
    Ngân sách khác nhau (vd smoke 20 s và full 300 s) được tách thành hàng riêng ở báo cáo (`label`).
    """
    records, seen = [], {}
    if not ids:
        return records
    hashes = current_data_hashes()
    if hashes is None:
        # Đóng khi lỗi: không kiểm được split hiện tại thì không đặt baseline cạnh kết quả agent.
        raise ValueError("Không kiểm được dữ liệu benchmark trên máy này (manifest/hash) - không nạp baseline.")
    for baseline_id in ids:
        root = ARTIFACTS / "baselines" / baseline_id
        if not root.is_dir():
            raise ValueError(f"Không có đợt baseline {baseline_id} ({root}).")
        manifest_path = root / "baselines_manifest.json"
        manifest = load_json(manifest_path) if manifest_path.exists() else None
        recorded = (manifest.get("data_sha256") if isinstance(manifest, dict) else None) or {}
        if manifest_path.exists():
            stale = sorted(k for k, v in recorded.items() if hashes.get(k) != v)
            if stale or not recorded:
                raise ValueError(f"Đợt baseline {baseline_id} chạy trên dữ liệu khác split hiện tại: {stale[:4] or 'manifest rỗng'}.")
        for path in sorted(root.glob("*/*/metrics.json")):
            record = load_json(path)
            # File split của dataset này (train + test) trong manifest hiện tại.
            files = [k for k in hashes if k.startswith(f"{record['dataset']}_") and k.endswith(("_train.csv", "_test.csv"))]
            if not files:
                raise ValueError(f"{path}: dataset {record['dataset']} không có trong split hiện tại.")
            if record.get("test_sha256"):
                test_name = next((k for k in files if k.endswith("_test.csv")), None)
                if not test_name or hashes[test_name] != record["test_sha256"]:
                    raise ValueError(f"{path}: chấm trên file test khác split hiện tại.")
            elif not all(recorded.get(k) == hashes[k] for k in files):
                # Quan sát không mang hash riêng thì manifest của đợt phải phủ ĐÚNG file train/test của dataset đó.
                raise ValueError(f"{path}: không có test_sha256 và manifest của đợt không phủ dữ liệu {record['dataset']}.")
            budget = record.get("time_budget_seconds")
            key = (record["method"], record["dataset"], record.get("seed"), budget if record["method"] in BUDGETED else None)
            if key in seen:
                raise ValueError(f"Quan sát baseline trùng {key} ở {seen[key]} và {baseline_id}: chỉ nạp mỗi đợt một lần.")
            seen[key] = baseline_id
            record["_path"] = str(path.parent)
            record["label"] = (f"{record['method']} ({float(budget):g} s)" if record["method"] in BUDGETED and budget is not None
                               else record["method"])
            records.append(record)
    return records


def paper_reference() -> dict | None:
    return load_json(BENCH_DIR / "paper_reference.json")


# ------------------------------------------------------------------------------ mục 1

def summary_ci_rows(c_rows: list[dict], core: list[dict]) -> list[list]:
    """Dòng tóm tắt kèm khoảng tin cậy (thêm vào bảng tóm tắt của report.py)."""
    decided = [r for r in core if r["task_status"] in ("PASS", "FAIL")]
    return [
        ["Task success (CI Wilson 95%)", S.fmt_rate(sum(r["task_status"] == "PASS" for r in decided), len(decided)),
         "Cùng mẫu số với dòng Task success"],
        ["SR nhóm C (CI t 95%)", _ci([r["sr"] for r in c_rows]), "mean ± std [CI] (n)"],
        ["NPS nhóm C (CI t 95%)", _ci([r["nps"] for r in c_rows]), "Chỉ lượt đo được test"],
        ["CS nhóm C (CI t 95%)", _ci([r["cs"] for r in c_rows]), ""],
    ]


# ------------------------------------------------------------------------------ nhóm S

def section_s(all_full: list[dict], titles: dict, cases_doc: dict) -> list[str]:
    s_rows = [r for r in all_full if r["group"] == "S"]
    if not s_rows:
        return []
    lines = ["## 3c. Nhóm S - lấy dữ liệu từ database qua SQL Agent và adapter", ""]
    table = []
    for case_id in sorted({r["scenario_id"] for r in s_rows}):
        g = [r for r in s_rows if r["scenario_id"] == case_id and r["task_status"] != "INVALID_FIXTURE"]
        decided = [r for r in g if r["task_status"] in ("PASS", "FAIL")]
        imported = [r for r in g if any(c["check"] == "imported_dataset_matches" for c in r["checks"])]
        imported_ok = sum(1 for r in imported for c in r["checks"] if c["check"] == "imported_dataset_matches" and c["passed"])
        trained = any(r["sr"] is not None for r in g)
        table.append([
            case_id, titles.get(case_id, ""), S.fmt_rate(sum(r["task_status"] == "PASS" for r in decided), len(decided)),
            S.fmt_rate(imported_ok, len(imported)) if imported else "—",
            _ci([r["sr"] for r in g]) if trained else "—", _ci([r["nps"] for r in g]) if trained else "—",
            f"{sum(r['sql_queries'] for r in g)} / {sum(r['sql_rejected'] for r in g)} / {sum(r['sql_write_attempts'] for r in g)}",
            sum(r["unwanted_proposals"] or 0 for r in g),
        ])
    lines += _table(["Ca", "Nội dung", "Task success [CI]", "Dataset nhập đúng (dòng, cột, tên)", "SR", "NPS",
                     "Truy vấn / bị từ chối / câu ghi", "Đề nghị trái ý"], table)
    # So sánh có cặp theo khối lặp: cùng nhiệm vụ ML, khác nguồn dữ liệu (database ngoài vs dataset đã upload).
    by_case = {c["id"]: c for c in cases_doc["cases"]}
    table = []
    for case_id in sorted({r["scenario_id"] for r in s_rows}):
        other = (by_case.get(case_id) or {}).get("compare_with")
        if not other:
            continue
        mine = {r["repeat"]: r for r in s_rows if r["scenario_id"] == case_id and r["task_status"] != "INVALID_FIXTURE"}
        base = {r["repeat"]: r for r in all_full if r["scenario_id"] == other and r["task_status"] != "INVALID_FIXTURE"}
        common = sorted(mine.keys() & base.keys())
        for key, label in (("sr", "SR"), ("nps", "NPS"), ("e2e_wall_seconds", "End-to-end (s)"), ("total_tokens", "Token")):
            pairs = [(base[k][key], mine[k][key]) for k in common]
            result = S.paired_comparison(pairs)
            table.append([f"{case_id} vs {other}", label, result["n_pairs"], _fmt(result["mean_a"]), _fmt(result["mean_b"]),
                          _fmt_diff(result)])
    if table:
        lines += ["Cùng nhiệm vụ ML, khác nguồn dữ liệu: ca S nhập từ database rồi train; ca so sánh dùng dataset đã upload. "
                  "Ghép cặp theo lần lặp (cùng khối lịch chạy), KHÔNG chung seed LLM/HPO.", ""]
        lines += _table(["Cặp", "Chỉ số", "Số cặp", "Ca upload (A)", "Ca SQL (B)", "Hiệu B − A [CI bootstrap 95%]"], table)
    lines += ["`Truy vấn` đếm mọi lần agent chạy thử SQL; `câu ghi` là câu INSERT/UPDATE/DELETE/DDL agent gửi (lớp chỉ đọc "
              "của adapter phải chặn - ca S07 kiểm thêm bảng nguồn không đổi). Dataset nhập trong ca được bộ chạy xoá sau khi "
              "ghi nhận (job và model không bị xoá), để danh sách dataset của tài khoản không lớn dần.", ""]
    return lines


def _fmt(value, digits=3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _fmt_diff(result: dict) -> str:
    if result["mean_diff"] is None:
        return "—"
    ci = (f" [{result['diff_ci_low']:.3f}, {result['diff_ci_high']:.3f}]" if result["diff_ci_low"] is not None else "")
    p = result["wilcoxon"]["p_value"]
    return f"{result['mean_diff']:+.3f}{ci}; Wilcoxon p={'—' if p is None else f'{p:.3f}'}"


# ------------------------------------------------------------------------------ baseline

def _agent_values(rows: list[dict], dataset: str) -> list[dict]:
    """Mọi lượt train hợp lệ của dataset (có SR), KỂ CẢ lượt không tạo được job - để mẫu số không bỏ thất bại."""
    return [r for r in rows if r.get("dataset") == dataset and r["sr"] is not None and r["task_status"] != "INVALID_FIXTURE"]


def section_baselines(all_full: list[dict], baselines: list[dict]) -> list[str]:
    lines = ["## 12. So sánh với baseline ngoài agent (cùng split, cùng metric)", ""]
    if not baselines:
        return lines + ["Chưa có kết quả baseline. Chạy `bench.py baselines --mode full --id <id>` (offline) và "
                        "`bench.py engine-baseline --id <id>` (engine HAutoML), rồi `report --baselines <id>`.", ""]
    datasets = sorted({b["dataset"] for b in baselines} | {r["dataset"] for r in all_full if r.get("dataset") and r["sr"] is not None})
    for dataset in datasets:
        agent = _agent_values(all_full, dataset)
        problem = (agent[0]["problem_type"] if agent else None) or _baseline_problem(baselines, dataset)
        if problem not in PRIMARY:
            continue
        metric, direction = PRIMARY[problem]
        secondary = SECONDARY[problem]
        lines += [f"### {dataset} ({problem}; chỉ số chính {metric} {direction})", ""]
        table = []
        if agent:
            measured = [r for r in agent if r.get(metric) is not None]
            table.append(["**HAutoML agent (full)**", "Agent LLM + engine", f"{len(measured)}/{len(agent)}",
                          _ci([r[metric] for r in measured])] + [_ci([r.get(k) for r in measured]) for k in secondary]
                         + ["—", _ci([r.get("engine_training_seconds") for r in agent], 1)])
        labels = sorted({b["label"] for b in baselines if b["dataset"] == dataset},
                        key=lambda l: (METHOD_ORDER.index(l.split(" ")[0]) if l.split(" ")[0] in METHOD_ORDER else 99, l))
        for label in labels:
            group = [b for b in baselines if b["dataset"] == dataset and b["label"] == label]
            method = group[0]["method"]
            ok = [b for b in group if b.get("status") == "ok"]
            values = [(b.get("metrics") or {}) for b in ok]
            status = "" if len(ok) == len(group) else f" ({', '.join(sorted({b.get('status') for b in group if b.get('status') != 'ok'}))})"
            table.append([label, METHOD_KIND.get(method, ""), f"{len(ok)}/{len(group)}{status}",
                          _ci([v.get(metric) for v in values])] + [_ci([v.get(k) for v in values]) for k in secondary]
                         + [_ci([v.get("roc_auc") for v in values]), _ci([b.get("fit_seconds") for b in ok], 1)])
        lines += _table(["Phương pháp", "Loại", "Đo được / lượt", metric, *secondary, "ROC-AUC", "Thời gian fit/train (s)"], table)
    lines += [
        "Đọc bảng: agent tính trên mọi ca train của dataset (cả ca có ràng buộc) mà bộ chấm đo được test; lượt agent hỏng không "
        "có metric nên **cột `Đo được / lượt` phải đọc cùng SR** - baseline luôn được chạy với đúng nhiệm vụ, agent thì phải tự "
        "hiểu yêu cầu. Lặp của agent (lần chạy) và seed của baseline không ghép cặp được, nên chỉ so mô tả bằng khoảng tin cậy; "
        "không có kiểm định giữa agent và baseline. API của HAutoML chỉ trả nhãn nên ROC-AUC chỉ có ở baseline. Thời gian của agent "
        "ở đây là thời gian huấn luyện của engine (pipeline backend), không gồm suy luận LLM; engine chạy song song nhiều model "
        "trên worker, baseline chạy n_jobs=1 - thời gian chỉ để tham khảo.", ""]
    return lines


def _baseline_problem(baselines: list[dict], dataset: str) -> str | None:
    """Loại bài toán của dataset: khai báo tường minh (config của engine) trước, rồi tên dataset, cuối cùng mới đoán."""
    group = [b for b in baselines if b["dataset"] == dataset]
    for b in group:
        if (b.get("config") or {}).get("problem_type") in PRIMARY:
            return b["config"]["problem_type"]
    if dataset in ("electricity", "weather") or any(b["method"] in ("naive_last_day", "naive_last_week", "lag_gbr", "lag_ridge")
                                                    for b in group):
        return "time_series"
    for b in group:
        if "f1_macro" in (b.get("metrics") or {}):
            return "classification"
        if b.get("metrics"):
            return "regression"
    return None


# --------------------------------------------------------------------------- cấp agent

def section_agents(all_full: list[dict]) -> list[str]:
    lines = ["## 13. Đánh giá theo từng agent và luồng phối hợp", ""]
    table = []
    agents = [a for a in AGENT_ORDER if any(a in (r.get("llm_calls_by_agent") or {}) or a in (r.get("subagent_runs") or {})
                                            for r in all_full)]
    for agent in agents:
        delegated = [r["delegations_by_agent"][agent] for r in all_full if agent in (r.get("delegations_by_agent") or {})]
        runs = [r["subagent_runs"][agent] for r in all_full if agent in (r.get("subagent_runs") or {})]
        tools = [r["tool_by_agent"][agent] for r in all_full if agent in (r.get("tool_by_agent") or {})]
        cases_used = sum(1 for r in all_full if agent in (r.get("llm_calls_by_agent") or {}))
        table.append([agent, cases_used, _ratio(delegated) if delegated else "—", _ratio(runs) if runs else "—",
                      _ratio(tools) if tools else "—",
                      _ci([(r.get("llm_calls_by_agent") or {}).get(agent) for r in all_full if agent in (r.get("llm_calls_by_agent") or {})], 1),
                      _ci([(r.get("agent_seconds_by_agent") or {}).get(agent) for r in all_full if agent in (r.get("agent_seconds_by_agent") or {})], 1)])
    lines += _table(["Agent", "Số lượt có tham gia", "Được Manager giao việc thành công", "Lần chạy kết thúc ok",
                     "Tool nghiệp vụ thành công", "Gọi LLM / lượt", "Thời gian / lượt (s)"], table)
    reasons: dict[str, int] = {}
    for r in all_full:
        for name, count in (r.get("rejection_reasons") or {}).items():
            reasons[name] = reasons.get(name, 0) + count
    if reasons:
        lines += _table(["Lý do người dùng mô phỏng từ chối thẻ", "Số thẻ"], [[k, v] for k, v in sorted(reasons.items())])
    lines += ["`Được giao việc thành công`: lời gọi `ask_*` của Manager trả ok. `Lần chạy kết thúc ok`: sự kiện agent_done ok "
              "(Prompt Agent tính cả khi R hợp lệ). Thời gian theo agent lồng nhau (Manager bao các sub-agent), không cộng lại. "
              "Chất lượng riêng của từng sub-agent không đo được trực tiếp ngoài các tiêu chí của ca (vd config đúng 7 trường cho "
              "Model Agent, dataset nhập đúng cho SQL Agent); không dựng điểm chất lượng cho từng agent.", ""]

    totals: dict[str, dict[str, int]] = {}
    for r in all_full:
        for kind, counts in (r.get("proposals") or {}).items():
            slot = totals.setdefault(kind, {"proposed": 0, "confirmed": 0, "rejected": 0, "failed": 0})
            for key in slot:
                slot[key] += counts.get(key, 0)
    if totals:
        lines += _table(["Loại thẻ xác nhận", "Agent đề nghị", "Người dùng mô phỏng xác nhận", "Bị từ chối (trái ý)", "Xác nhận nhưng thực thi lỗi"],
                        [[k, v["proposed"], v["confirmed"], v["rejected"], v["failed"]] for k, v in sorted(totals.items())])
    measured = [r for r in all_full if r.get("continuation_turns") is not None]
    propagation = [r["imported_dataset_used"] for r in all_full if r.get("imported_dataset_used") is not None]
    lines += _table(["Chỉ số luồng phối hợp", "Kết quả", "Cách đo"], [
        ["Lượt có đề nghị trái ý người dùng", S.fmt_rate(sum(1 for r in measured if r.get("unwanted_proposals")), len(measured)),
         "Đề nghị train/bật model khi người dùng không yêu cầu (kể cả đã bị từ chối)"],
        ["Lượt cần nhắn 'tiếp tục'", S.fmt_rate(sum(1 for r in measured if r["continuation_turns"]), len(measured)),
         "Agent dừng chờ thẻ bật model rồi mới predict được"],
        ["Thẻ còn treo cuối lượt", sum(r.get("pending_actions_left") or 0 for r in all_full), "Đề nghị không ai xử lý (nên là 0)"],
        ["Dataset SQL nhập được dùng đúng cho job", S.fmt_rate(sum(propagation), len(propagation)) if propagation else "—",
         "Kết quả trung gian truyền SQL Agent → Model/Operation Agent"],
        ["Sub-agent hỏng rồi chạy lại thành công", S.fmt_rate(sum(r["agent_recovered"] for r in all_full), sum(r["agent_failures"] for r in all_full)),
         "agent_done ok=false, sau đó cùng agent ok"],
    ])

    # Bốn chiều tách riêng, không gộp điểm.
    train = [r for r in all_full if r["sr"] is not None]
    decided = [r for r in all_full if r["task_status"] in ("PASS", "FAIL")]
    configs = [r for r in all_full if r["first_config_valid"] is not None]
    lines += ["Bốn chiều đánh giá tách riêng (không gộp thành một điểm):", ""]
    lines += _table(["Chiều", "Chỉ số", "Kết quả"], [
        ["Đúng chức năng", "Config hợp lệ ngay lần đầu", S.fmt_rate(sum(bool(r["first_config_valid"]) for r in configs), len(configs))],
        ["Đúng chức năng", "Trường config đúng ở lần đầu", _ci([r["config_field_accuracy"] for r in all_full])],
        ["Đúng chức năng", "Tool bắt buộc được gọi đúng tham số",
         S.fmt_rate(sum(r["required_tools_hit"] for r in all_full), sum(r["required_tools_total"] for r in all_full))],
        ["Độ tin cậy luồng", "Task success", S.fmt_rate(sum(r["task_status"] == "PASS" for r in decided), len(decided))],
        ["Độ tin cậy luồng", "Workflow train → bật → predict trọn vẹn",
         S.fmt_rate(sum(bool(r["workflow_pass"]) for r in train), len(train))],
        ["Độ tin cậy luồng", "Lượt chat lỗi (exception)", sum(r["turn_errors"] for r in all_full)],
        ["Chất lượng ML", "NPS (C, T, S)", _ci([r["nps"] for r in train])],
        ["Hiệu quả", "Token / lượt (lượt đủ usage)", _ci([r["total_tokens"] for r in all_full if r["token_status"] == "complete"], 0)],
        ["Hiệu quả", "Thời gian agent / lượt (s)", _ci([r["agent_seconds"] for r in all_full], 1)],
    ])
    return lines


# ------------------------------------------------------------------------------ tài nguyên

def section_resources(all_full: list[dict], baselines: list[dict]) -> list[str]:
    lines = ["## 14. Tài nguyên", ""]
    train = [r for r in all_full if r["main_job"]]
    rows = [
        ["CPU tiến trình agent / lượt (s)", _ci([r.get("harness_cpu_seconds") for r in all_full], 2),
         "Đo thật: user+sys của tiến trình chạy ChatSession (agent + bộ chạy), gồm lúc chờ job"],
        ["RAM đỉnh tiến trình agent (MB)", _fmt(max([r.get("harness_peak_rss_mb") or 0 for r in all_full] or [0]), 1),
         "ru_maxrss, đỉnh của cả tiến trình qua mọi lượt (không tách được theo lượt)"],
        ["Thời gian huấn luyện của engine / job (s)", _ci([r.get("engine_training_seconds") for r in train], 1),
         "Bước train trong pipeline backend (độ phân giải 1 s)"],
        ["Thời gian cả pipeline backend / job (s)", _ci([r.get("engine_pipeline_seconds") for r in train], 1), "Đọc dữ liệu → lưu model"],
        ["Số cấu hình HPO engine đã đánh giá / job", _ci([r.get("engine_candidates") for r in train], 1),
         "Tổng trial (tham số khác nhau) của mọi model"],
        ["Model lỗi trong job", sum(r.get("engine_models_failed") or 0 for r in train), "Model bị huỷ do hết max_time hoặc lỗi"],
        ["Nguồn điểm backend", ", ".join(f"{k}: {v}" for k, v in sorted(_count(r.get("engine_score_source") for r in train).items())),
         "cv = điểm CV trên chính dữ liệu chọn model (≤10k dòng); holdout = tập giữ lại"],
    ]
    lines += _table(["Chỉ số", "Kết quả", "Ghi chú"], rows)
    if baselines:
        table = []
        for label in sorted({b["label"] for b in baselines}):
            group = [b for b in baselines if b["label"] == label and b.get("status") == "ok"]
            if group:
                table.append([label, len(group), _ci([b.get("fit_seconds") for b in group], 2),
                              _ci([b.get("cpu_seconds") for b in group], 2), _ci([b.get("peak_rss_mb") for b in group], 0)])
        lines += _table(["Baseline", "Lượt", "Fit (s)", "CPU (s)", "RAM đỉnh (MB)"], table)
    lines += ["Chưa đo: CPU/RAM của worker huấn luyện (backend không ghi), GPU (engine không dùng GPU), thời gian fit từng trial "
              "(backend bỏ khi lưu pipeline). Chi phí LLM ở mục 5 là ước tính từ token × bảng giá, không phải hoá đơn.", ""]
    return lines


def _count(values) -> dict:
    counts: dict = {}
    for v in values:
        counts[str(v)] = counts.get(str(v), 0) + 1
    return counts


# ---------------------------------------------------------------------------- bài báo

_PAPER_CASES = {
    "crab": {"constraint_free": ["C09"], "constraint_aware": ["C10"]},
    "weather": {"constraint_free": ["T03"], "constraint_aware": ["T04"]},
    "electricity": {"constraint_free": ["T01", "T05"], "constraint_aware": ["T02"]},
}


def section_paper(all_full: list[dict], paper: dict | None) -> list[str]:
    lines = ["## 15. Đối chiếu với AutoML-Agent (ICML 2025)", ""]
    if not paper:
        return lines + ["Thiếu benchmark/paper_reference.json.", ""]
    lines += [f"Nguồn: {paper['source']}. {paper['extracted']}", ""]
    table = []
    for dataset, settings in _PAPER_CASES.items():
        ref = paper["datasets"][dataset]
        for setting, case_ids in settings.items():
            theirs = (ref.get(setting) or {}).get("AutoML-Agent") or {}
            mine = [r for r in all_full if r["scenario_id"] in case_ids and r["task_status"] != "INVALID_FIXTURE"]
            table.append([dataset, setting.replace("_", "-"), "AutoML-Agent (bài báo)",
                          _paper_cell(theirs.get("sr")), _paper_cell(theirs.get("nps")), _paper_cell(theirs.get("cs")), "5"])
            if mine:
                table.append(["", "", f"HAutoML ({', '.join(case_ids)})", _ci([r["sr"] for r in mine]),
                              _ci([r["nps_paper"] for r in mine]), _ci([r["cs_paper"] for r in mine]), str(len(mine))])
        for name, values in (ref.get("constraint_free") or {}).items():
            if name != "AutoML-Agent" and "nps" in values:
                table.append([dataset, "constraint-free", f"{name} (bài báo)", "—", _paper_cell(values["nps"]), "—", "5"])
    lines += _table(["Dataset", "Thiết lập", "Hệ thống", "SR", "NPS (RMSLE)", "CS", "n"], table)
    train = [r for r in all_full if r["sr"] is not None]
    cost = paper["cost_per_run"]
    lines += _table(["Chi phí / lượt", "AutoML-Agent (bài báo, không gồm train)", "HAutoML (ca train, agent_seconds không gồm chờ job)"], [
        ["Thời gian (s)", f"{cost['constraint_free']['seconds']} (CF) / {cost['constraint_aware']['seconds']} (CA)",
         _ci([r["agent_seconds"] for r in train], 1)],
        ["Tiền (USD)", f"{cost['constraint_free']['usd']} (CF) / {cost['constraint_aware']['usd']} (CA)",
         _ci([r["llm_cost_usd"] for r in train if r["cost_status"] == "estimated"], 4)],
        ["Token", "—", _ci([r["total_tokens"] for r in train if r["token_status"] == "complete"], 0)],
    ])
    lines += ["Khác biệt protocol, phải nêu khi đặt hai cột cạnh nhau:", ""]
    lines += [f"- {item}" for item in paper["protocol_differences"]]
    lines += ["- NPS của HAutoML ở bảng này theo đúng cách chấm của bài (hồi quy: 1/(1+RMSLE)); NPS ở mục 3 theo protocol v4 "
              "(hồi quy: 1/(1+MAE)) để so với các đợt trước. Ràng buộc của hai bên khác nhau (bài: RMSLE/thời gian; HAutoML: MAE/RMSE).", ""]
    return lines


def _paper_cell(value) -> str:
    if not value:
        return "—"
    return f"{value[0]:.3f} ± {value[1]:.3f}"


# ---------------------------------------------------------------------------- ablation

def ablation_tests(full_map: dict, other_map: dict, variant: str) -> list[list]:
    """
    Kiểm định cặp full vs biến thể trên giao (ca, lần lặp): McNemar chính xác cho PASS/FAIL, Wilcoxon cho CS.
    Cặp ghép theo lịch chạy xen kẽ đã khoá, không chung seed LLM/HPO.
    """
    common = sorted(full_map.keys() & other_map.keys())
    decided = [k for k in common if full_map[k]["task_status"] in ("PASS", "FAIL") and other_map[k]["task_status"] in ("PASS", "FAIL")]
    full_only = sum(1 for k in decided if full_map[k]["task_status"] == "PASS" and other_map[k]["task_status"] == "FAIL")
    variant_only = sum(1 for k in decided if full_map[k]["task_status"] == "FAIL" and other_map[k]["task_status"] == "PASS")
    p = S.mcnemar_exact(full_only, variant_only)
    cs = S.paired_comparison([(full_map[k]["cs"], other_map[k]["cs"]) for k in common])
    tokens = S.paired_comparison([(full_map[k]["total_tokens"], other_map[k]["total_tokens"]) for k in common
                                  if full_map[k]["token_status"] == other_map[k]["token_status"] == "complete"])
    return [variant, len(decided), f"{full_only} / {variant_only}", "—" if p is None else f"{p:.3f}",
            cs["n_pairs"], _fmt_diff(cs), tokens["n_pairs"], _fmt_diff(tokens)]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
