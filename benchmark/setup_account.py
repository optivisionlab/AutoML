"""
Dựng tài khoản benchmark MỚI từ đầu (chạy một lần trên máy sẽ chạy benchmark, vd server).

    python benchmark/bench.py setup-account

Làm, theo thứ tự, mỗi bước ghi tiến độ vào benchmark_artifacts/setup_state.json (đứt giữa chừng thì chạy
lại lệnh: bước đã xong được bỏ qua, KHÔNG upload trùng):

1. Đăng nhập bằng AGENT_USER / AGENT_PASSWORD (.env). Tài khoản phải TRỐNG (không dataset, job, kết nối) -
   tránh dataset trùng tên, job cũ làm list_my_jobs dài, ID nhầm. Có sẵn thì dừng và liệt kê (trừ khi
   --allow-existing).
2. Upload 6 file TRAIN đã khoá hash (4 bảng + 2 chuỗi thời gian) - không bao giờ upload *_test.csv - rồi đọc
   lại schema: số dòng và tên cột phải khớp manifest.
3. Hai job fixture trên Glass (config của C01, train bằng code, không LLM): GLASS_JOB được kích hoạt,
   INACTIVE_JOB để tắt.
4. MISSING_ID: ObjectId hợp lệ không có trong tài khoản.
5. Hai kết nối database (PostgreSQL, MySQL) tới database `datasets` của server test (tests/sql_sources),
   tài khoản chỉ đọc; kiểm /test và danh sách bảng.
6. Ghi các ID vào placeholders của bench_config.json (sao lưu file cũ trước).

Không gọi LLM. Có train 2 job nhỏ (Glass, vài chục giây) trên backend.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from agent import tools
from agent.api_client import HAutoMLClient

from benchmark.common import ARTIFACTS, CASES_PATH, CONFIG_PATH, load_json, substitute

STATE_PATH = ARTIFACTS / "setup_state.json"
# placeholder -> (file train đã khoá, tên dataset trên HAutoML)
DATASET_FILES = {
    "GLASS_ID": ("datasets/glass_train.csv", "glass_train"),
    "SHOP_ID": ("datasets/shopping_train.csv", "shopping_train"),
    "CONCRETE_ID": ("datasets/concrete_train.csv", "concrete_train"),
    "CRAB_ID": ("datasets/crab_train.csv", "crab_train"),
    "ELEC_ID": ("datasets/timeseries/electricity_MT_301_2013_hourly_train.csv", "electricity_MT_301_2013_hourly_train"),
    "WEATHER_ID": ("datasets/timeseries/weather_jena_co2_hourly_train.csv", "weather_jena_co2_hourly_train"),
}
DEFAULT_MISSING_ID = "ffffffffffffffffffffffff"


def expected_schemas() -> dict[str, tuple[int, set[str]]]:
    """placeholder -> (số dòng, tập cột) theo manifest đã khoá (kiểm hash file trước)."""
    from benchmark import protocol

    data, ts = protocol.check_data(), protocol.check_ts_data()
    out = {}
    for key, name in (("GLASS_ID", "glass"), ("SHOP_ID", "shopping"), ("CONCRETE_ID", "concrete"), ("CRAB_ID", "crab")):
        out[key] = (data[name]["n_train"], set(data[name]["features"] + [data[name]["target"]]))
    for key, name in (("ELEC_ID", "electricity"), ("WEATHER_ID", "weather")):
        meta = ts["datasets"][name]
        out[key] = (meta["n_train"], {meta["time_column"], meta["target"]})
    return out


def glass_fixture_task() -> dict:
    """Config của job fixture: đúng task C01 (Glass, 9 feature, target Type)."""
    case = next(c for c in load_json(CASES_PATH)["cases"] if c["id"] == "C01")
    return case["task"]


def _save(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def _wait_job(api, job_id: str, limit: float, poll: float = 5.0) -> dict:
    deadline = time.monotonic() + limit
    while True:
        info = tools.get_job_info(api, job_id)
        job = info.get("job") if info.get("ok") else None
        if job and job.get("status") in tools.JOB_FINISHED:
            return job
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Job fixture {job_id} chưa xong sau {limit:.0f} giây; chờ nó xong rồi chạy lại lệnh.")
        time.sleep(poll)


def _account_inventory(api) -> dict:
    datasets = api.list_datasets()
    jobs = tools.list_my_jobs(api, limit=tools.MAX_JOB_LIMIT)
    connections = api.list_database_connections()
    return {
        "datasets": [(d.get("_id"), d.get("dataName")) for d in datasets],
        "jobs": [j.get("job_id") for j in jobs.get("jobs") or []] if jobs.get("ok") else ["<không đọc được danh sách job>"],
        "connections": [(c.get("id"), c.get("name")) for c in connections],
    }


def _check_schema(api, dataset_id: str, rows: int, columns: set[str]) -> None:
    info = tools.get_dataset_schema(api, dataset_id)
    names = {c["name"] for c in info.get("columns") or []}
    if not info.get("ok") or info.get("total_rows") != rows or names != columns:
        raise RuntimeError(f"Dataset {dataset_id}: đọc lại thấy {info.get('total_rows')} dòng, cột {sorted(names)}; "
                           f"cần {rows} dòng, cột {sorted(columns)}.")


def run(cfg: dict, pg: dict, mysql: dict, password: str, allow_existing: bool = False,
        skip_connections: bool = False, max_wait: float = 900) -> dict:
    state = load_json(STATE_PATH) or {}
    with HAutoMLClient() as api:
        login = tools.ensure_login(api)
        if not login.get("ok"):
            raise SystemExit(f"Không đăng nhập được bằng AGENT_USER/AGENT_PASSWORD: {login.get('error')}")
        user_id = tools._ensure_user_id(api)
        if state and state.get("user_id") != user_id:
            raise SystemExit(f"{STATE_PATH} thuộc tài khoản khác ({state.get('user_id')}). Đổi tên/xoá file đó nếu "
                             "chủ ý dựng lại cho tài khoản này.")
        if not state:
            inventory = _account_inventory(api)
            if any(inventory.values()) and not allow_existing:
                raise SystemExit(
                    "Tài khoản benchmark KHÔNG trống - dùng tài khoản mới để tránh dataset trùng tên / job cũ:\n"
                    + json.dumps(inventory, ensure_ascii=False, indent=1)
                    + "\n(Cố ý dùng tài khoản này thì thêm --allow-existing.)"
                )
            state = {"user_id": user_id, "started_at": datetime.now().isoformat(timespec="seconds"), "placeholders": {}}
            _save(state)
        found = state["placeholders"]

        # 2. Upload 6 file train, kiểm lại schema.
        schemas = expected_schemas()
        for key, (relative, data_name) in DATASET_FILES.items():
            if found.get(key):
                print(f"  = {key}: đã có {found[key]}")
                continue
            path = ARTIFACTS / relative
            if path.name.endswith("_test.csv"):
                raise SystemExit("Không bao giờ upload file test.")
            result = api.upload_dataset_content(data_name, path.name, path.read_bytes())
            dataset_id = result.get("_id") or result.get("id")
            if not dataset_id:
                raise RuntimeError(f"Upload {path.name} không trả ID: {result}")
            _check_schema(api, dataset_id, *schemas[key])
            found[key] = dataset_id
            _save(state)
            print(f"  ▶ {key}: upload {path.name} -> {dataset_id} ({schemas[key][0]} dòng, khớp manifest)")

        # 3. Hai job fixture Glass (config của C01), train bằng code.
        task = glass_fixture_task()
        for key, active in (("GLASS_JOB", True), ("INACTIVE_JOB", False)):
            if not found.get(key):
                created = tools.start_training(
                    api, dataset_id=found["GLASS_ID"], target=task["target"], list_feature=task["features"],
                    metric_sort=task["metric"], problem_type=task["problem_type"],
                    search_algorithm=task["search_algorithm"], max_time=task["max_time"],
                )
                if not created.get("ok") or not created.get("job_id"):
                    raise RuntimeError(f"Không tạo được job fixture {key}: {created.get('error')}")
                found[key] = created["job_id"]
                _save(state)
                print(f"  ▶ {key}: job {found[key]} đang train (Glass, config C01)...")
            job = _wait_job(api, found[key], max_wait)
            if job.get("status") != tools.JOB_SUCCESS:
                raise RuntimeError(f"Job fixture {key} {found[key]} thất bại (status {job.get('status')}). Xoá khoá "
                                   f"{key} trong {STATE_PATH} rồi chạy lại.")
            if bool(job.get("activate") == 1) != active:
                result = tools.activate_model(api, found[key], active)
                if not result.get("ok"):
                    raise RuntimeError(f"Không {'bật' if active else 'tắt'} được model của {key}: {result.get('error')}")
            print(f"  = {key}: {found[key]} thành công, {'đã kích hoạt' if active else 'để tắt'}")

        # 4. MISSING_ID: ObjectId hợp lệ, không có trong tài khoản.
        if not found.get("MISSING_ID"):
            own = {d.get("_id") for d in api.list_datasets()}
            found["MISSING_ID"] = DEFAULT_MISSING_ID if DEFAULT_MISSING_ID not in own else os.urandom(12).hex()
            _save(state)

        # 5. Hai kết nối database chỉ đọc tới database `datasets` của server test.
        if not skip_connections:
            for key, spec in (("PG_CONN_ID", pg), ("MYSQL_CONN_ID", mysql)):
                if not found.get(key):
                    body = {**spec, "username": spec.get("username") or "hautoml_ro", "password": password,
                            "description": "Benchmark HAutoML v5, nhóm S: database `datasets` chỉ chứa phần TRAIN."}
                    conn = api._request("POST", "/database-connections", json=body)
                    found[key] = conn["id"]
                    _save(state)
                    print(f"  ▶ {key}: tạo kết nối {found[key]} ({spec['db_type']} {spec['host']}:{spec['port']})")
                test = api._request("POST", f"/database-connections/{found[key]}/test")
                wanted = set((cfg.get("connection_fixtures") or {}).get(key, {}).get("tables") or [])
                tables = tools.list_database_tables(api, found[key])
                names = {t.get("name") if isinstance(t, dict) else t for t in tables.get("tables") or []}
                if not test.get("connected") or not wanted <= names:
                    raise RuntimeError(f"{key}: kết nối {found[key]} test={test}, bảng {sorted(names)}; cần {sorted(wanted)}. "
                                       "Kiểm server test đã nạp load_datasets.py và đã nối vào mạng của app.")
                print(f"  = {key}: {found[key]} kết nối được, đủ {len(wanted)} bảng")

    # 6. Ghi placeholders vào bench_config.json (sao lưu bản cũ).
    if CONFIG_PATH.exists():
        backup = CONFIG_PATH.with_name(f"bench_config.before-setup-{datetime.now():%Y%m%d-%H%M%S}.json")
        shutil.copy2(CONFIG_PATH, backup)
        print(f"  Sao lưu config cũ: {backup.name}")
    cfg = dict(cfg)
    cfg["placeholders"] = {**(cfg.get("placeholders") or {}), **found}
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    state["finished_at"] = datetime.now().isoformat(timespec="seconds")
    _save(state)
    return found


def connection_specs(cfg: dict, pg_host: str, pg_port: int, mysql_host: str, mysql_port: int) -> tuple[dict, dict]:
    fixtures = cfg.get("connection_fixtures") or {}
    pg = {"name": "bench-v5-postgres-datasets", "db_type": "postgres", "host": pg_host, "port": pg_port,
          "database": (fixtures.get("PG_CONN_ID") or {}).get("database", "datasets"), "schema_name": "public"}
    mysql = {"name": "bench-v5-mysql-datasets", "db_type": "mysql", "host": mysql_host, "port": mysql_port,
             "database": (fixtures.get("MYSQL_CONN_ID") or {}).get("database", "datasets")}
    return pg, mysql


__all__ = ["run", "connection_specs", "DATASET_FILES", "STATE_PATH", "substitute"]
