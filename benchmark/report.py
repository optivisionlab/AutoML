"""
Gộp mọi lượt chạy thành báo cáo: report.md (đọc), results.csv và results.jsonl (dữ liệu thô).

Tỷ lệ luôn ghi kèm tử số/mẫu số; lượt chưa chấm xong (PENDING*) không bị tính
là đạt hay trượt mà được báo riêng.
"""

# Standard libraries
import csv
import json
import statistics
from datetime import datetime
from pathlib import Path

# Local modules
from benchmark import report_sections as sections
from benchmark.analyze import analyze_run
from benchmark.common import load_json
from benchmark.variants_doc import VARIANT_DOCS


GROUP_TITLES = {
    "A": "Tra cứu và hiểu dữ liệu",
    "B": "Chọn và kiểm tra cấu hình",
    "C": "Pipeline end-to-end",
    "D": "Vận hành và xử lý tình huống",
    "E": "Chèn lỗi (error recovery)",
    "F": "Hiểu yêu cầu qua hội thoại",
    "T": "Dự báo chuỗi thời gian (time series)",
    "S": "Database ngoài qua SQL Agent (adapter)",
}
# Nhóm thêm sau v4: tóm tắt và các chỉ số tổng tính trên A–F để so được với các đợt trước.
_ADDED_GROUPS = {"T", "S"}
_LIST_FIELDS = ("checks", "llm_latencies", "tool_latencies")
_CSV_SKIP = _LIST_FIELDS


# --------------------------------------------------------------------- định dạng

def _num(value, digits=3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _rate(hit: int, total: int) -> str:
    return f"{hit}/{total} ({hit / total:.1%})" if total else "—"


def _mean_std(values: list, digits=3) -> str:
    values = [v for v in values if v is not None]
    if not values:
        return "—"
    if len(values) == 1:
        return f"{values[0]:.{digits}f} (n=1)"
    return f"{statistics.mean(values):.{digits}f} ± {statistics.stdev(values):.{digits}f} (n={len(values)})"


def _mean(values: list, digits=1) -> str:
    values = [v for v in values if v is not None]
    return f"{statistics.mean(values):.{digits}f}" if values else "—"


def _pct(values: list[float], q: float) -> str:
    if not values:
        return "—"
    ordered = sorted(values)
    return f"{ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]:.2f}"


def _table(header: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return lines + [""]


# ---------------------------------------------------------------------- tổng hợp

def _status_counts(rows: list[dict]) -> dict:
    counts = {s: 0 for s in ("PASS", "FAIL", "PENDING_REVIEW", "PENDING", "INVALID_FIXTURE")}
    for r in rows:
        counts[r["task_status"]] = counts.get(r["task_status"], 0) + 1
    return counts


def _success_rate(rows: list[dict]) -> str:
    c = _status_counts(rows)
    return _rate(c["PASS"], c["PASS"] + c["FAIL"])


def _tool_accuracy(rows: list[dict]) -> dict:
    all_calls = sum(r["tool_calls_all"] for r in rows)
    invalid = sum(r["tool_schema_invalid"] for r in rows)
    business = sum(r["tool_calls"] for r in rows)
    excluded = sum(r["tool_injected_failures"] + r["tool_expected_failures"] for r in rows)
    ok = sum(r["tool_successes"] for r in rows)
    return {
        "schema": _rate(all_calls - invalid, all_calls),
        "execution": _rate(ok, business - excluded),
        "selection": _rate(sum(r["required_tools_hit"] for r in rows), sum(r["required_tools_total"] for r in rows)),
        "forbidden": sum(r["forbidden_tool_violations"] for r in rows),
    }


def _c_rows(rows):
    return [r for r in rows if r["group"] == "C"]


def _t_rows(rows):
    return [r for r in rows if r["group"] == "T"]


def _core_rows(rows):
    return [r for r in rows if r["group"] not in _ADDED_GROUPS]


def _tokens(rows):
    """Token chỉ tính trên lượt đủ usage: lượt thiếu usage có tổng token thấp hơn thực tế."""
    return [r["total_tokens"] for r in rows if r["token_status"] == "complete"]


def constraint_rate(rows):
    eligible = [r for r in rows if r.get("has_constraints") and r["task_status"] != "INVALID_FIXTURE"]
    passed = sum(r["all_constraints_pass"] is True and r["workflow_pass"] is True for r in eligible)
    missing = sum(r["all_constraints_pass"] is None for r in eligible)
    return (f"{_rate(passed, len(eligible))}; chưa đo: {missing}" if eligible else "không có ngưỡng")


def build_rows(runs_root: Path, cases_doc: dict, pricing: dict | None) -> list[dict]:
    from benchmark.protocol import read_lock
    locked = read_lock(runs_root) if (runs_root / "protocol.json").exists() else None
    planned = {tuple(x) for x in locked["payload"]["plan"]} if locked else None
    by_id = {c["id"]: c for c in cases_doc["cases"]}
    rows = []
    for run_file in sorted(runs_root.glob("*/*/run.json")):
        if ".aborted-" in run_file.parent.name or ".invalid-" in run_file.parent.name:
            continue
        run = load_json(run_file)
        if (run_file.parent.name != f"{run['case_id']}_r{int(run['repeat']):02d}"
                or run_file.parent.parent.name != run["variant"]):
            # Bản sao kiểu A01_r01.bak sẽ bị đếm hai lần và che mất lượt còn thiếu.
            raise ValueError(f"Thư mục lượt chạy không đúng tên theo run.json (bản sao?): {run_file.parent}")
        if locked and (run.get("protocol_id") != locked["protocol_id"] or
                       (run["variant"], run["case_id"], run["repeat"]) not in planned):
            raise ValueError(f"Run không thuộc protocol/plan: {run_file}")
        case = by_id.get(run["case_id"])
        if case:
            rows.append(analyze_run(run_file.parent, case, pricing))
    return rows


def write_data(rows: list[dict], out: Path) -> None:
    with (out / "results.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    columns = [k for k in rows[0] if k not in _CSV_SKIP] if rows else []
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for r in rows:
            writer.writerow([
                json.dumps(r[k], ensure_ascii=False) if isinstance(r[k], (dict, list)) else ("" if r[k] is None else r[k])
                for k in columns
            ])


# ------------------------------------------------------------------------ báo cáo

def render(rows: list[dict], cases_doc: dict, pricing: dict | None, baselines: list[dict] | None = None) -> str:
    full = [r for r in rows if r["variant"] == "full"]
    titles = {c["id"]: c.get("title", "") for c in cases_doc["cases"]}
    lines = ["# Báo cáo benchmark hệ thống agent HAutoML", ""]

    # ---- 0. Thông tin lượt chạy
    phases = sorted({r["phase"] or "?" for r in rows})
    lines += _table(["Mục", "Giá trị"], [
        ["Thời điểm tạo", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Phiên bản kịch bản", cases_doc["version"]],
        ["Commit", ", ".join(sorted({str(r["commit"]) for r in rows}))],
        ["Provider / model", ", ".join(sorted({f"{r['provider']} / {r['model']}" for r in rows}))],
        ["Giai đoạn", ", ".join(phases)],
        ["Số lượt chạy", f"{len(rows)} ({len(full)} lượt bản đầy đủ)"],
        ["Biến thể", ", ".join(sorted({r["variant"] for r in rows}))],
        ["Bảng giá", f"{pricing.get('provider')} / {pricing.get('model')} ({pricing.get('price_date')})" if pricing else "chưa có pricing.json — chi phí tiền để trống"],
    ])
    if "pilot" in phases:
        lines += ["> **Có dữ liệu chạy thử (pilot).** Không dùng làm kết quả chính thức; không chấm test ở giai đoạn này.", ""]
    pending = [r for r in rows if r["task_status"].startswith("PENDING") or r["measurement_status"] != "complete"]
    if pending:
        lines += [f"> **{len(pending)} lượt chưa chấm xong** (cần review hoặc thiếu phép đo). Task success chỉ tính lượt có kết luận; tỷ lệ đạt ràng buộc vẫn giữ mọi ca hợp lệ trong mẫu số. Xem mục 10.", ""]

    if not full:
        lines += ["Chưa có lượt chạy của bản đầy đủ (`full`).", ""]
        return "\n".join(lines)

    # ---- 1. Tóm tắt
    # Tóm tắt và mục 6–7 tính trên các nhóm A–F (33 ca của v4) để so được với đợt trước; nhóm T báo riêng.
    all_full = full
    t_rows = _t_rows(all_full)
    full = _core_rows(all_full)
    acc = _tool_accuracy(full)
    c_rows = _c_rows(full)
    jobs = [r for r in full if r["main_job"] and r["job_success"] is not None]
    episodes = sum(r["error_episodes"] for r in full)
    e_rows = [r for r in full if r["group"] == "E"]
    e_counts = _status_counts(e_rows)
    lines += ["## 1. Tóm tắt (bản đầy đủ" + (", nhóm A–F; nhóm T, S ở cuối bảng và mục 3b, 3c)" if t_rows else ")"), ""]
    summary = [
        ["Task success rate", _success_rate(full), "PASS / (PASS + FAIL), nhóm A–F" if t_rows else "PASS / (PASS + FAIL), mọi nhóm"],
        ["SR nhóm C", _mean_std([r["sr"] for r in c_rows]), "Thang điều chỉnh từ AutoML-Agent cho HAutoML"],
        ["NPS nhóm C", _mean_std([r["nps"] for r in c_rows]), "Trên test độc lập"],
        ["CS nhóm C", _mean_std([r["cs"] for r in c_rows]), "0.5·SR + 0.5·NPS"],
        ["Đạt mọi ràng buộc", constraint_rate(c_rows), "Mọi ca có ngưỡng hợp lệ, kể cả train thất bại; cần workflow đạt"],
        ["Job train thành công", _rate(sum(1 for r in jobs if r["job_success"]), len(jobs)), "Trên các lượt có tạo job"],
        ["Số lần gọi LLM / ca", _mean([r["llm_calls"] for r in full]), "Số bước suy luận"],
        ["Số tool call / ca", _mean([r["tool_calls"] for r in full]), "Không tính ask_* của Manager"],
        ["Token / ca", _mean(_tokens(full), 0), f"Chỉ lượt đủ usage: {len(_tokens(full))}/{len(full)}"],
        ["Chi phí / ca (USD)", _mean([r["llm_cost_usd"] for r in full if r["cost_status"] in ("estimated", "billed")], 4),
         f"Chỉ ca đủ dữ liệu: {sum(r['cost_status'] in ('estimated', 'billed') for r in full)}/{len(full)}"],
        ["Thời gian agent / ca (s)", _mean([r["agent_seconds"] for r in full]), "Không gồm chờ train"],
        ["Tool call đúng schema", acc["schema"], "Tên tool + tham số hợp lệ"],
        ["Tool call thực thi thành công", acc["execution"], "Không tính lỗi do benchmark chèn và lỗi đúng như ca mong đợi"],
        ["Chọn đúng tool/endpoint", acc["selection"], "Tool bắt buộc của ca được gọi đúng tham số"],
        ["Tham số config đúng (lần đầu)", _mean_std([r["config_field_accuracy"] for r in full]), "Tỷ lệ trường đúng ở submit_config đầu tiên (B/C)"],
        ["Tự phục hồi sau lỗi tool/sub-agent", _rate(sum(r["error_recovered"] for r in full), episodes), "Lỗi không mong đợi (tự nhiên + chèn), sau đó gọi lại thành công"],
        ["Hoàn thành dù bị chèn lỗi", _rate(e_counts["PASS"], e_counts["PASS"] + e_counts["FAIL"]), "Nhóm E"],
    ]
    if t_rows:
        t_train = [r for r in t_rows if r["sr"] is not None or r["main_job"]]
        summary += [
            ["Task success nhóm T", _success_rate(t_rows), "Time series, báo riêng (không có ở v4-02)"],
            ["SR nhóm T", _mean_std([r["sr"] for r in t_train]), "Cùng thang SR với nhóm C"],
            ["NPS nhóm T", _mean_std([r["nps"] for r in t_train]), "1/(1+RMSLE) trên 96 bước test, như AutoML-Agent"],
            ["CS nhóm T", _mean_std([r["cs"] for r in t_train]), "0.5·SR + 0.5·NPS"],
            ["Đạt mọi ràng buộc nhóm T", constraint_rate(t_train), "Ngưỡng rmse kiểm trên test"],
        ]
    s_rows = [r for r in all_full if r["group"] == "S"]
    if s_rows:
        summary += [["Task success nhóm S", _success_rate(s_rows), "SQL Agent + adapter database (v5), báo riêng"]]
    summary += sections.summary_ci_rows(c_rows, full)
    lines += _table(["Chỉ số", "Kết quả", "Ghi chú"], summary)

    # ---- 2. Task success rate theo nhóm
    lines += ["## 2. Task success rate theo nhóm", ""]
    table = []
    for group, title in GROUP_TITLES.items():
        g = [r for r in all_full if r["group"] == group]
        if g:
            c = _status_counts(g)
            table.append([f"{group} - {title}", len(g), c["PASS"], c["FAIL"], c["PENDING_REVIEW"] + c["PENDING"], c["INVALID_FIXTURE"], _success_rate(g)])
    lines += _table(["Nhóm", "Lượt", "PASS", "FAIL", "Chờ chấm", "Fixture lỗi", "Tỷ lệ"], table)
    table = []
    for case_id in sorted({r["scenario_id"] for r in all_full}):
        g = [r for r in all_full if r["scenario_id"] == case_id]
        reasons = sorted({r["failure_reason"] for r in g if r["task_status"] == "FAIL" and r["failure_reason"]})
        table.append([case_id, titles.get(case_id, ""), _success_rate(g), "; ".join(reasons)[:160] or ""])
    lines += _table(["Ca", "Nội dung", "PASS/(PASS+FAIL)", "Lý do trượt"], table)

    # ---- 3. Nhóm C
    if c_rows:
        lines += ["## 3. Nhóm C - SR, NPS, CS (AutoML-Agent)", ""]
        table = []
        for case_id in sorted({r["scenario_id"] for r in c_rows}):
            g = [r for r in c_rows if r["scenario_id"] == case_id and r["task_status"] != "INVALID_FIXTURE"]
            metric = "f1_macro" if any(r["f1_macro"] is not None for r in g) else "mae"
            table.append([
                case_id, titles.get(case_id, ""), _mean_std([r["sr"] for r in g]), _mean_std([r["nps"] for r in g]),
                _mean_std([r["cs"] for r in g]), f"{metric}: {_mean_std([r[metric] for r in g])}",
                constraint_rate(g),
                _rate(sum(1 for r in g if r["workflow_pass"]), len(g)),
            ])
        lines += _table(["Ca", "Nội dung", "SR", "NPS", "CS", "Metric test", "Đạt ràng buộc", "Workflow hoàn tất"], table)
        bounded_ids = {c["id"] for c in cases_doc["cases"] if c.get("constraints")}
        free = [r for r in c_rows if r["scenario_id"] not in bounded_ids]
        bound = [r for r in c_rows if r["scenario_id"] in bounded_ids]
        lines += _table(["Nhóm ca", "SR", "CS"], [
            ["Không ràng buộc", _mean_std([r["sr"] for r in free]), _mean_std([r["cs"] for r in free])],
            ["Có ràng buộc", _mean_std([r["sr"] for r in bound]), _mean_std([r["cs"] for r in bound])],
        ])
        lines += ["Hai nhóm dùng thang SR khác nhau nên không gộp khi so sánh. NPS hồi quy = 1/(1+MAE), phụ thuộc đơn vị của từng dataset.", ""]

    # ---- 3b. Nhóm T
    if t_rows:
        lines += ["## 3b. Nhóm T - dự báo chuỗi thời gian (SR, NPS theo RMSLE, CS)", ""]
        table = []
        for case_id in sorted({r["scenario_id"] for r in t_rows}):
            g = [r for r in t_rows if r["scenario_id"] == case_id and r["task_status"] != "INVALID_FIXTURE"]
            if not any(r["main_job"] or r["sr"] is not None for r in g):
                # Ca không train (T06): không có SR/NPS - task success ở mục 2.
                table.append([case_id, titles.get(case_id, "")] + ["—"] * 9)
                continue
            measured = [r for r in g if r["rmse"] is not None and r["naive_last_week_rmse"] is not None]
            naive_nps = [1 / (1 + r["naive_last_week_rmsle"]) for r in g if r["naive_last_week_rmsle"] is not None]
            table.append([
                case_id, titles.get(case_id, ""), _mean_std([r["sr"] for r in g]), _mean_std([r["nps"] for r in g]),
                _mean_std(naive_nps), _mean_std([r["cs"] for r in g]), _mean_std([r["rmse"] for r in g]),
                _mean_std([r["naive_last_week_rmse"] for r in g]),
                _rate(sum(1 for r in measured if r["rmse"] < r["naive_last_week_rmse"]), len(measured)),
                constraint_rate(g), _rate(sum(1 for r in g if r["workflow_pass"]), len(g)),
            ])
        lines += _table(["Ca", "Nội dung", "SR", "NPS", "NPS naive (tuần trước)", "CS", "RMSE test",
                         "RMSE naive (tuần trước)", "Thắng naive tuần trước", "Đạt ràng buộc", "Workflow hoàn tất"], table)
        lines += ["Dự báo 96 bước (giờ) liền sau phần train, chấm ngoài agent trên phần test không tải lên. NPS = 1/(1+RMSLE) như AutoML-Agent; "
                  "với chuỗi dương biến thiên nhỏ so với mức trung bình, NPS sát 1 ngay cả với dự báo ngây thơ, nên đọc NPS cùng cột NPS naive "
                  "và tỷ lệ thắng baseline lặp lại tuần trước (168 giờ cuối của train). RMSE theo đơn vị của từng chuỗi (kWh, ppm), không so giữa "
                  "hai dataset; baseline lặp lại ngày trước có trong results.csv. T06 là ca từ chối đúng (dataset không có cột thời gian), "
                  "không có SR/NPS; task success của nó ở mục 2.", ""]

    # ---- 3c. Nhóm S
    lines += sections.section_s(all_full, titles, cases_doc)

    # ---- 4. Số bước
    lines += ["## 4. Số vòng lặp / bước để hoàn thành", ""]
    table = []
    agents = sorted({a for r in full for a in r["llm_calls_by_agent"]})
    for group, title in GROUP_TITLES.items():
        g = [r for r in all_full if r["group"] == group]
        if g:
            table.append([group, _mean([r["chat_turns"] for r in g]), _mean([r["llm_calls"] for r in g]),
                          _mean([r["tool_calls"] for r in g]), _mean([r["delegations"] for r in g]),
                          sum(r["step_limit_hits"] for r in g), sum(r["turn_budget_exceeded"] for r in g)])
    lines += _table(["Nhóm", "Lượt chat", "Gọi LLM", "Tool call", "Uỷ thác (ask_*)", "Chạm trần bước", "Vượt trần token"], table)
    lines += _table(["Agent", "Gọi LLM trung bình / ca"], [
        [a, _mean([r["llm_calls_by_agent"].get(a, 0) for r in full])] for a in agents
    ])

    # ---- 5. Chi phí và độ trễ
    lines += ["## 5. Chi phí và độ trễ", ""]
    table = []
    for group in GROUP_TITLES:
        g = [r for r in all_full if r["group"] == group]
        if g:
            llm = [s for r in g for s in r["llm_latencies"]]
            tool = [s for r in g for s in r["tool_latencies"]]
            table.append([group, f"{_mean(_tokens(g), 0)} ({len(_tokens(g))}/{len(g)})", _mean([r["llm_cost_usd"] for r in g], 4),
                          _mean([r["agent_seconds"] for r in g]), f"{_pct(llm, .5)} / {_pct(llm, .95)}",
                          f"{_pct(tool, .5)} / {_pct(tool, .95)}", _mean([r["job_wait_seconds"] for r in g]),
                          _mean([r["e2e_wall_seconds"] for r in g])])
    lines += _table(["Nhóm", "Token / ca (lượt đủ usage)", "USD / ca", "Agent (s)", "LLM p50/p95 (s)", "Tool p50/p95 (s)", "Chờ job (s)", "End-to-end (s)"], table)
    lines += _table(["Agent", "Thời gian trung bình / ca (s)"], [
        [a, _mean([r["agent_seconds_by_agent"].get(a, 0) for r in full])]
        for a in sorted({a for r in full for a in r["agent_seconds_by_agent"]})
    ])
    statuses = sorted({r["cost_status"] for r in full})
    lines += [f"Trạng thái chi phí: {', '.join(statuses)}. `incomplete` = có token suy luận tính riêng hoặc thiếu usage; `unavailable` = chưa có bảng giá. Chỉ là chi phí LLM, không gồm CPU/GPU huấn luyện.", ""]

    # ---- 6. Tool/API call accuracy
    lines += ["## 6. Tool/API call accuracy", ""]
    lines += _table(["Chỉ số", "Kết quả", "Cách đo"], [
        ["Đúng schema", acc["schema"], "Lời gọi không bị từ chối vì sai tên tool, sai tham số hoặc JSON hỏng"],
        ["Thực thi thành công", acc["execution"], "tool_call ok=true; không tính lỗi do benchmark chèn và lỗi mà ca chờ đợi (vd B03 bị chặn config)"],
        ["Chọn đúng tool + đúng tham số", acc["selection"], "Tool bắt buộc của từng ca (vd get_job_info với đúng job_id)"],
        ["Gọi tool bị cấm", acc["forbidden"], "Vd start_training trong ca chỉ tra cứu"],
        ["Config hợp lệ ngay lần đầu", _rate(sum(1 for r in full if r["first_config_valid"]), sum(1 for r in full if r["first_config_valid"] is not None)), "Ca B/C có đầu vào hợp lệ; không submit lần nào tính là không đạt"],
        ["Trường config đúng ở lần đầu", _mean_std([r["config_field_accuracy"] for r in full]), "7 trường của config tool nhận (trường được phép bỏ trống tính theo giá trị hệ thống điền)"],
    ])
    per_tool: dict[str, list[int]] = {}
    for r in full:
        for name, (ok, total) in r["tool_by_name"].items():
            agg = per_tool.setdefault(name, [0, 0])
            agg[0] += ok
            agg[1] += total
    lines += _table(["Tool", "Thành công / tổng"], [[n, _rate(*v)] for n, v in sorted(per_tool.items())])
    lines += ["Mỗi tool gắn cố định với một endpoint trong `api_client.py`, nên chọn đúng tool đồng nghĩa gọi đúng endpoint.", ""]

    # ---- 7. Error recovery
    lines += ["## 7. Khả năng tự phục hồi (error recovery)", ""]
    agent_failures = sum(r["agent_failures"] for r in full)
    natural = [r for r in full if r["group"] != "E"]
    rejections = [r for r in full if r["first_config_rejected"]]
    lines += _table(["Loại lỗi", "Phục hồi", "Cách đo"], [
        ["Tool/sub-agent trả lỗi tự nhiên (nhóm A–D)", _rate(sum(r["error_recovered"] for r in natural), sum(r["error_episodes"] for r in natural)), "Sau lỗi, cùng tool (kể cả ask_*) được gọi lại thành công trong ca"],
        ["Lỗi do benchmark chèn (nhóm E)", _rate(sum(r["error_recovered"] for r in e_rows), sum(r["error_episodes"] for r in e_rows)), "Như trên, trên các ca chèn lỗi"],
        ["Sub-agent hỏng", _rate(sum(r["agent_recovered"] for r in full), agent_failures), "Sau agent_done ok=false, cùng agent chạy lại thành công"],
        ["Config bị validate_config chặn", _rate(sum(1 for r in rejections if r["config_self_corrected"]), len(rejections)), "Ca có đầu vào hợp lệ: config đầu bị chặn, sau đó có config hợp lệ"],
        ["Lượt chat lỗi (exception)", f"{sum(r['turn_errors'] for r in full)} lượt", "Không phục hồi trong lượt đó"],
    ])
    if e_rows:
        lines += _table(["Ca E", "Lỗi chèn", "Hoàn thành"], [
            [cid, titles.get(cid, ""), _success_rate([r for r in e_rows if r["scenario_id"] == cid])]
            for cid in sorted({r["scenario_id"] for r in e_rows})
        ])

    # ---- 8. Ablation
    others = sorted({r["variant"] for r in rows} - {"full"})
    lines += ["## 8. Ablation: đóng góp của từng thành phần", ""]
    if not others:
        lines += ["Chưa chạy biến thể ablation (`python benchmark/bench.py run --ablation`).", ""]
    else:
        table = []
        # Từ all_full (không chỉ A–F): S05 nằm trong plan ablation của v5.
        full_map = {(r["scenario_id"], r["repeat"]): r for r in all_full if r["task_status"] != "INVALID_FIXTURE"}
        for variant in others:
            other_map = {(r["scenario_id"], r["repeat"]): r for r in rows
                         if r["variant"] == variant and r["task_status"] != "INVALID_FIXTURE"}
            common = sorted(full_map.keys() & other_map.keys())
            # CS chỉ so trên cặp cả hai bên cùng đo được, để một lượt thiếu phép đo không làm bên kia trông tốt hơn.
            c_keys = [k for k in common if full_map[k]["group"] == "C"]
            cs_pairs = [(full_map[k]["cs"], other_map[k]["cs"]) for k in c_keys
                        if full_map[k]["cs"] is not None and other_map[k]["cs"] is not None]
            for side, (label, lookup) in enumerate(((f"full (vs {variant})", full_map), (variant, other_map))):
                v_rows = [lookup[k] for k in common]
                acc_v = _tool_accuracy(v_rows)
                guard = [r for r in v_rows if r["scenario_id"] in ("B03", "B04", "B05", "B06")]
                table.append([
                    label, len(v_rows), _success_rate(v_rows), _mean_std([r["sr"] for r in _c_rows(v_rows)]),
                    f"{_mean_std([pair[side] for pair in cs_pairs])}; {len(cs_pairs)}/{len(c_keys)} cặp",
                    _success_rate(guard), f"{_mean(_tokens(v_rows), 0)} ({len(_tokens(v_rows))}/{len(v_rows)})",
                    _mean([r["agent_seconds"] for r in v_rows]), acc_v["schema"],
                ])
        lines += _table(["Biến thể", "Lượt", "Task success", "SR nhóm C", "CS nhóm C (cặp cùng đo được)", "Chặn config sai (B03–B06)", "Token / ca", "Agent (s)", "Tool đúng schema"], table)
        lines += _table(["Biến thể", "Kiểm định cặp: lượt có kết luận", "Chỉ full đạt / chỉ biến thể đạt", "McNemar p",
                         "Cặp CS", "CS biến thể − full", "Cặp token", "Token biến thể − full"],
                        [sections.ablation_tests(full_map, {(r["scenario_id"], r["repeat"]): r for r in rows
                                                            if r["variant"] == v and r["task_status"] != "INVALID_FIXTURE"}, v)
                         for v in others])
        lines += _table(["Biến thể", "Thay đổi"], [[v, VARIANT_DOCS.get(v, "")] for v in ["full"] + others])
        lines += ["Mỗi cặp full/biến thể chỉ dùng giao của (mã ca, lần lặp), loại cặp có INVALID_FIXTURE. Không trộn full 5 lần với biến thể 3 lần. "
                  "Cặp ghép theo lịch chạy xen kẽ đã khoá, không chung seed LLM/HPO; với vài chục cặp, p > 0.05 nghĩa là chưa đủ bằng chứng, "
                  "không phải \"không khác nhau\". Không gỡ SQL Agent trong ablation: nhóm S không làm được nếu thiếu nó (thành phần bắt buộc, "
                  "không phải tuỳ chọn); hệ thống không có critic agent riêng.", ""]

    # ---- 9. Ổn định và độ nhạy prompt
    lines += ["## 9. Độ ổn định và độ nhạy prompt", ""]
    table = []
    for case_id in sorted({r["scenario_id"] for r in all_full}):
        g = [r for r in all_full if r["scenario_id"] == case_id]
        table.append([case_id, len(g), _mean_std([r["cs"] for r in g]), _mean_std(_tokens(g), 0),
                      _mean_std([r["agent_seconds"] for r in g], 1)])
    lines += _table(["Ca", "Số lần", "CS", "Token", "Agent (s)"], table)
    c01 = [r for r in full if r["scenario_id"] == "C01"]
    c04 = [r for r in full if r["scenario_id"] == "C04"]
    if c01 and c04:
        lines += ["Độ nhạy cách diễn đạt (C01 so với C04, cùng yêu cầu kỹ thuật):", ""]
        def values(rows, key):
            return _tokens(rows) if key == "total_tokens" else [r[key] for r in rows]
        lines += _table(["Chỉ số", "C01", "C04"], [
            [k, _mean_std(values(c01, k)), _mean_std(values(c04, k))]
            for k in ("sr", "f1_macro", "cs", "total_tokens", "agent_seconds")
        ])

    # ---- 10. Cần xem lại
    lines += ["## 10. Lượt cần chấm thủ công hoặc còn thiếu phép đo", ""]
    if pending:
        lines += _table(["Lượt", "Trạng thái", "Cần kiểm"], [
            [f"{r['variant']}/{r['scenario_id']} r{r['repeat']}", r["task_status"], (r["failure_reason"] or "")[:200]]
            for r in pending
        ])
        lines += ['Chấm thủ công: tạo `review.json` với `{"verdict": "PASS", "note": "Bằng chứng đã đối chiếu..."}` (hoặc verdict `FAIL`) rồi chạy lại `report`. Review không thay thế phép đo tự động còn thiếu.', ""]
    else:
        lines += ["Không có.", ""]

    # ---- 12-15. Baseline, cấp agent, tài nguyên, bài báo
    lines += sections.section_baselines(all_full, baselines or [])
    lines += sections.section_agents(all_full)
    lines += sections.section_resources(all_full, baselines or [])
    lines += sections.section_paper(all_full, sections.paper_reference())

    # ---- 16. Giới hạn
    lines += [
        "## 16. Giới hạn khi đọc báo cáo", "",
        "- Quy mô nhỏ (4 dataset tabular); kết quả là kiểm chứng chức năng và độ ổn định, không phải khẳng định hiệu quả tổng quát.",
        "- Test set cố định (seed 42): các lần lặp chỉ đo biến thiên do LLM và HPO.",
        ("- Baseline ngoài hệ thống: xem mục 12; FLAML/AutoGluon chỉ có khi đã cài (không tự cài)." if baselines else
         "- Chưa nạp kết quả baseline ngoài hệ thống (mục 12)."),
        "- Từ v5, train/bật/tắt model chỉ chạy khi người dùng bấm Xác nhận: benchmark đóng vai người dùng theo chính sách cố định "
        "của từng ca (consent.py). Người dùng thật có thể bấm khác; lượt 'tiếp tục' sau khi bật model là một tin nhắn cố định.",
        "- Nhóm S dùng hai server test (PostgreSQL 16, MySQL 8.4) chứa phần train của các dataset benchmark; chưa đo MongoDB, "
        "SQLite/DuckDB qua kết nối đã lưu, hay database lớn/nhiều bảng.",
        "- `single-agent` khác bản đầy đủ ở nhiều điểm cùng lúc (một vòng LLM, không có Prompt Agent nên không có R và kiểm định ngưỡng; trần bước 36 do benchmark chọn): đây là so sánh hai cấu hình hệ thống, không chỉ riêng việc chia agent.",
        "- Tự phục hồi tự nhiên phụ thuộc lỗi phát sinh thật; số tập lỗi nhỏ thì tỷ lệ không ổn định - xem mẫu số.",
    ]
    if t_rows:
        lines += [
            "- Nhóm T: HAutoML dự báo MỘT chuỗi (đơn biến) bằng mô hình bảng với đặc trưng trễ, đệ quy từng bước; "
            "AutoML-Agent dự báo đa biến (21/321 chiều) bằng mô hình sâu. Cùng nguồn dữ liệu và độ dài dự báo 96, "
            "không phải tái lập bảng kết quả của bài. Mỗi dataset một cửa sổ test cố định.",
        ]
    lines += [""]
    return "\n".join(lines)


def write_report(runs_root: Path, out: Path, cases_doc: dict, pricing: dict | None,
                 baseline_ids: list[str] | None = None) -> Path:
    rows = build_rows(runs_root, cases_doc, pricing)
    baselines = sections.load_baselines(baseline_ids)
    out.mkdir(parents=True, exist_ok=True)
    write_data(rows, out)
    if baselines:
        sections.write_json(out / "baselines.json", [{k: v for k, v in b.items() if k != "traceback"} for b in baselines])
    path = out / "report.md"
    text = render(rows, cases_doc, pricing, baselines)
    if (runs_root / "protocol.json").exists():
        from benchmark.protocol import read_lock, source_hashes
        locked = read_lock(runs_root)
        note = f"\nProtocol: `{locked['protocol_id']}`. Đã ghi {len(rows)}/{len(locked['payload']['plan'])} lượt theo plan.\n"
        if len(rows) < len(locked["payload"]["plan"]):
            note += "**Báo cáo chưa đủ lượt; không dùng như kết quả benchmark hoàn chỉnh.**\n"
        archived = [p.name for p in runs_root.glob("*/*") if p.is_dir()]
        retried = sum(".invalid-" in name for name in archived)
        aborted = sum(".aborted-" in name for name in archived)
        note += f"Lượt lưu trữ (không tính vào kết quả): {retried} `.invalid-*` đã chạy lại vì fixture lỗi, {aborted} `.aborted-*` bị ngắt giữa chừng.\n"
        locked_hashes, current = locked["payload"]["source_hashes"], source_hashes()
        changed = sorted(k for k in set(locked_hashes) | set(current) if locked_hashes.get(k) != current.get(k))
        if changed:
            note += (f"**Code đã đổi sau khi khóa ({len(changed)} file, vd {', '.join(changed[:5])}): báo cáo này chấm "
                     "bằng code hiện tại, không phải code đã khóa.**\n")
        text = text.replace("# Báo cáo benchmark hệ thống agent HAutoML\n", "# Báo cáo benchmark hệ thống agent HAutoML\n" + note, 1)
    path.write_text(text, encoding="utf-8")
    return path
