"""
Baseline "engine HAutoML gọi thẳng" (oracle config, không LLM).

Gửi đúng config đáp án của ca agent tương ứng (C01/C02/C03/C09 cho dữ liệu bảng, T01/T03 cho time series)
tới API train của backend bằng code, chờ job xong, kích hoạt, chấm trên test giống hệt bộ chấm agent,
rồi TẮT model để trả tài khoản về trạng thái cũ. Không có Prompt/Data/Model/Operation Agent, không token.

Đọc cùng kết quả agent để tách hai nguồn:
- Chất lượng: agent chọn đúng config thì khác biệt với baseline này chỉ còn do biến thiên của engine
  (estimator không cố định random_state - xem báo cáo khảo sát backend). Agent kém hơn rõ rệt là dấu hiệu
  chọn sai config hoặc thất bại ở các bước khác.
- Chi phí điều phối: thời gian end-to-end của ca agent trừ thời gian huấn luyện của engine.

Dùng backend thật (tốn tài nguyên worker), KHÔNG dùng LLM. Chạy sau đợt official của agent, hoặc bằng tài
khoản riêng: job tạo ra làm danh sách job của tài khoản dài thêm (ảnh hưởng list_my_jobs của agent).

    python benchmark/bench.py engine-baseline --id <mã đợt> --repeats 5
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from agent import tools
from agent.api_client import HAutoMLClient

from benchmark import jobinfo, metrics as M
from benchmark.auth import install_reauthentication
from benchmark.common import ARTIFACTS, REPO, substitute
from benchmark.protocol import file_hash
from benchmark.runner import assert_idle

METHOD = "hautoml_engine"


def oracle_tasks(cases_doc: dict) -> dict[str, dict]:
    """dataset -> task của ca train KHÔNG ràng buộc đầu tiên dùng dataset đã upload (không phải dataset nhập từ SQL)."""
    tasks: dict[str, dict] = {}
    for case in cases_doc["cases"]:
        task = case.get("task") or {}
        if case.get("flow") != "train" or case.get("constraints") or "IMPORTED_ID" in task.get("dataset_id", ""):
            continue
        tasks.setdefault(task["dataset"], {**task, "case_id": case["id"]})
    return tasks


def _wait(api, job_id: str, limit: float, poll: float = 5.0) -> dict:
    deadline = time.monotonic() + limit
    while True:
        info = tools.get_job_info(api, job_id)
        job = info.get("job") if info.get("ok") else None
        if job and job.get("status") in tools.JOB_FINISHED:
            return job
        if time.monotonic() >= deadline:
            return job or {"status": None, "error": info.get("error")}
        time.sleep(poll)


def _predict_test(api, job_id: str, task: dict, test_path: Path) -> tuple[list, list, float]:
    from benchmark.scoring import _read_test

    time_column = task.get("time_column") if task["problem_type"] == "time_series" else None
    x, y_true = _read_test(test_path, task["target"], time_column, task.get("column_case"))
    y_pred, started = [], time.monotonic()
    for start in range(0, len(x), tools.MAX_PREDICT_ROWS):
        batch = x[start:start + tools.MAX_PREDICT_ROWS]
        result = tools.predict(api, job_id, batch)
        if not result.get("ok"):
            raise RuntimeError(f"predict lỗi: {result.get('error')}")
        predictions = result.get("predictions") or []
        if len(predictions) != len(batch):
            raise RuntimeError("số dự đoán không khớp số mẫu")
        y_pred.extend(float(item["predict"]) for item in predictions)
    return y_true, y_pred, time.monotonic() - started


def run_one(api, task: dict, dataset_id: str, test_path: Path, max_wait: float) -> dict:
    started = time.monotonic()
    created = tools.start_training(
        api, dataset_id=dataset_id, target=task["target"], list_feature=task["features"],
        metric_sort=task["metric"], problem_type=task["problem_type"],
        search_algorithm=task["search_algorithm"], max_time=task["max_time"],
    )
    if not created.get("ok") or not created.get("job_id"):
        return {"status": "error", "error": f"không tạo được job: {created.get('error')}"}
    job_id = created["job_id"]
    job = _wait(api, job_id, max_wait)
    train_wall = time.monotonic() - started
    record = {"job_id": job_id, "job_status": job.get("status"), "best_model": job.get("best_model"),
              "backend_best_score": job.get("best_score"), "train_wall_seconds": train_wall,
              "pipeline": jobinfo.fetch_summary(api, job_id)}
    if job.get("status") != tools.JOB_SUCCESS:
        return {**record, "status": "error" if job.get("status") is not None else "timeout",
                "error": f"job kết thúc với status {job.get('status')}"}
    activation = tools.activate_model(api, job_id, True)
    if not activation.get("ok"):
        return {**record, "status": "error", "error": f"không kích hoạt được: {activation.get('error')}"}
    try:
        y_true, y_pred, predict_seconds = _predict_test(api, job_id, task, test_path)
    except Exception as error:  # noqa: BLE001 - vẫn phải tắt model và ghi lại việc tắt có được không
        record["deactivated"] = bool(tools.activate_model(api, job_id, False).get("ok"))
        return {**record, "status": "error", "error": f"predict lỗi: {type(error).__name__}: {error}"}
    # Trả tài khoản về trạng thái cũ: model baseline không được để bật.
    record["deactivated"] = bool(tools.activate_model(api, job_id, False).get("ok"))
    try:
        metrics = M.compute(task["problem_type"], y_true, y_pred)
    except Exception as error:  # noqa: BLE001 - giữ job_id/deactivated để còn thử tắt lại về sau
        return {**record, "status": "error", "error": f"tính metric lỗi: {type(error).__name__}: {error}"}
    return {**record, "status": "ok", "metrics": metrics, "fit_seconds": train_wall, "predict_seconds": predict_seconds,
            "y_true": y_true, "y_pred": y_pred}


def _restore_if_left_on(api, path: Path) -> None:
    """Lượt trước chấm xong nhưng KHÔNG tắt lại được model: thử tắt lại mỗi lần chạy cho tới khi được."""
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("deactivated") is not False or not record.get("job_id"):
        return
    record["deactivated"] = bool(tools.activate_model(api, record["job_id"], False).get("ok"))
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"    tắt lại model job {record['job_id']}: {'được' if record['deactivated'] else 'CHƯA được - chạy lại sau'}")


def run(cfg: dict, cases_doc: dict, baseline_id: str, datasets: list[str] | None, repeats: int) -> Path:
    import csv

    tasks = oracle_tasks(cases_doc)
    chosen = datasets or sorted(tasks)
    unknown = sorted(set(chosen) - set(tasks))
    if unknown:
        raise ValueError(f"Không có ca train không ràng buộc cho dataset: {unknown}")
    root = ARTIFACTS / "baselines" / baseline_id
    root.mkdir(parents=True, exist_ok=True)
    max_wait = float(cfg.get("max_wait_seconds", 600))
    with HAutoMLClient() as api:
        login = tools.ensure_login(api)
        if not login.get("ok"):
            raise SystemExit(f"Không đăng nhập được: {login.get('error')}")
        install_reauthentication(api)
        # Mọi lượt cũ của đợt (không chỉ các lượt lần này chọn) còn để model bật: thử tắt lại trước.
        for path in sorted((root / METHOD).glob("*/metrics.json")):
            _restore_if_left_on(api, path)
        for dataset in chosen:
            task = tasks[dataset]
            dataset_id = substitute(task["dataset_id"], cfg["placeholders"])
            test_path = REPO / cfg["test_sets"][dataset]
            for repeat in range(1, repeats + 1):
                out = root / METHOD / f"{dataset}_s{repeat:02d}"
                if (out / "metrics.json").exists():
                    print(f"  = {METHOD}/{dataset} lần {repeat}: đã có, bỏ qua")
                    continue
                print(f"  ▶ {METHOD}/{dataset} lần {repeat} (config của {task['case_id']})")
                # Còn job chạy (vd job trước quá hạn chờ) thì dừng cả đợt: không ghi lỗi hạ tầng thành kết quả.
                assert_idle(api)
                try:
                    result = run_one(api, task, dataset_id, test_path, max_wait + float(task["max_time"]))
                except Exception as error:  # noqa: BLE001 - một lượt lỗi được ghi lại
                    result = {"status": "error", "error": f"{type(error).__name__}: {error}"}
                out.mkdir(parents=True, exist_ok=True)
                y_true, y_pred = result.pop("y_true", None), result.pop("y_pred", None)
                if y_true is not None:
                    with (out / "predictions.csv").open("w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(["row", "y_true", "y_pred"])
                        writer.writerows((i, a, p) for i, (a, p) in enumerate(zip(y_true, y_pred)))
                record = {"method": METHOD, "dataset": dataset, "seed": repeat, "baseline_id": baseline_id,
                          "time_budget_seconds": task["max_time"], "oracle_case": task["case_id"],
                          "config": {k: task[k] for k in ("target", "features", "metric", "problem_type",
                                                          "search_algorithm", "max_time")},
                          "test_sha256": file_hash(test_path), "finished_at": datetime.now(timezone.utc).isoformat(),
                          **result}
                (out / "metrics.json").write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str),
                                                  encoding="utf-8")
                print(f"    {record['status']} {record.get('error') or ''}")
                if record.get("deactivated") is False:
                    print(f"    CẢNH BÁO: chưa tắt lại được model job {record.get('job_id')}; chạy lại lệnh để thử tắt.")
    # Tổng kết: không để model baseline nào còn bật mà không ai biết.
    left_on = [json.loads(p.read_text(encoding="utf-8")).get("job_id") for p in (root / METHOD).glob("*/metrics.json")
               if json.loads(p.read_text(encoding="utf-8")).get("deactivated") is False]
    if left_on:
        raise SystemExit(f"Model baseline còn bật (chưa tắt lại được): {left_on}. Chạy lại `engine-baseline` cùng --id để thử tắt.")
    return root
