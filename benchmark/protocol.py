"""Offline dataset checks and immutable experiment snapshots; never store secrets."""

import csv
import hashlib
import json
import math
import os
import random
import re
import sys
from pathlib import Path

from benchmark.common import ARTIFACTS, BACKEND, BENCH_DIR, REPO, load_json

DATASETS = ("glass", "shopping", "concrete", "crab")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_data(cfg=None):
    directory = ARTIFACTS / "datasets"
    manifest = load_json(directory / "manifest.json")
    if not manifest or manifest.get("split_version") != "feature-group-v1":
        raise ValueError("Chạy prepare để tạo split feature-group-v1 trước.")
    for source in manifest["sources"].values():
        if file_hash(REPO / source["raw_file"]) != source["raw_sha256"]:
            raise ValueError(f"File gốc thay đổi: {source['raw_file']}")
    for name, expected in manifest["sha256"].items():
        if file_hash(directory / name) != expected:
            raise ValueError(f"Hash không khớp manifest: {name}")
    for name in DATASETS:
        meta = manifest[name]
        inputs = []
        for split in ("train", "test"):
            path = directory / f"{name}_{split}.csv"
            if cfg and split == "test" and (REPO / cfg["test_sets"][name]).resolve() != path.resolve():
                raise ValueError(f"test_sets.{name} không trỏ vào file đã khóa trong manifest.")
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames != meta["features"] + [meta["target"]]:
                    raise ValueError(f"Schema không khớp: {path.name}")
                rows = list(reader)
            if len(rows) != meta[f"n_{split}"] or not rows:
                raise ValueError(f"Số mẫu không khớp: {path.name}")
            numbers = [[float(r[c]) for c in reader.fieldnames] for r in rows]
            if not all(math.isfinite(v) for row in numbers for v in row):
                raise ValueError(f"NaN/Inf trong {path.name}")
            inputs.append({tuple(row[:-1]) for row in numbers})
        if inputs[0] & inputs[1]:
            raise ValueError(f"{name}: feature trùng giữa train và test.")
    return manifest


def source_hashes():
    paths = list(BENCH_DIR.glob("*.py"))
    for directory in (BACKEND / "agent", BACKEND / "src", BACKEND / "assets"):
        # Bỏ cache sinh khi chạy (__pycache__, .pytest_cache...): xoá cache không được làm hỏng lock.
        paths += [p for p in directory.rglob("*") if p.is_file()
                  and p.suffix in {".py", ".yml", ".yaml", ".md", ".txt"} and "__pycache__" not in p.parts
                  and not any(part.startswith(".") for part in p.relative_to(directory).parts)]
    paths += [BACKEND / "requirements.txt", REPO / "docker-compose.yaml"]
    return {str(p.relative_to(REPO)): file_hash(p) for p in sorted(set(paths)) if p.is_file()}


def runtime_settings():
    # Explicit allowlist: no credential, API key, token or entire environment dumps.
    names = ("AGENT_TURN_TOKEN_BUDGET", "AGENT_JOB_POLL_SECONDS", "HAUTOML_BASE_URL", "HAUTOML_API_PREFIX")
    return {"python": sys.version.split()[0], "settings": {k: os.getenv(k) for k in names}}


def provider_settings(cfg):
    """Endpoint LLM thực sự dùng (URL, endpoint, api-version), không có API key."""
    from agent.providers import resolve
    resolved = resolve(cfg.get("provider"), cfg.get("model"))
    return {k: getattr(resolved, k) for k in ("name", "kind", "model", "base_url", "endpoint", "api_version")}


def plan(cfg, cases):
    if int(cfg["repeats"]) < 1:
        raise ValueError("repeats phải >= 1")
    result = [("full", c["id"], r) for r in range(1, int(cfg["repeats"]) + 1) for c in cases["cases"]]
    ab = cfg.get("ablation", {})
    if ab.get("enabled", True):
        known = {c["id"] for c in cases["cases"]}
        if int(ab["repeats"]) < 1 or not set(ab["cases"]) <= known:
            raise ValueError("Cấu hình ablation không hợp lệ.")
        from benchmark.variants_doc import VARIANT_DOCS
        if not set(ab["variants"]) <= (set(VARIANT_DOCS) - {"full"}):
            raise ValueError("Biến thể ablation không hợp lệ.")
        result += [(v, c, r) for r in range(1, int(ab["repeats"]) + 1) for v in ab["variants"] for c in ab["cases"]]
    if len(result) != len(set(result)):
        raise ValueError("Plan có ca/biến thể trùng.")
    # Xen kẽ full và ablation trong từng khối lần lặp, thứ tự ngẫu nhiên có seed: trạng thái
    # tài khoản tích luỹ (số job, độ dài list_my_jobs) không thiên về biến thể chạy sau.
    rng = random.Random(int(cfg.get("schedule_seed", 42)))
    ordered = []
    for repeat in sorted({x[2] for x in result}):
        block = [x for x in result if x[2] == repeat]
        rng.shuffle(block)
        ordered += block
    return [list(x) for x in ordered]


def preflight(cfg, cases, case_ids=None):
    errors, warnings = [], []
    try:
        check_data(cfg)
    except (ValueError, OSError, KeyError) as exc:
        errors.append(str(exc))
    if not re.fullmatch(r"[A-Za-z0-9_-]+", str(cfg.get("experiment_id", ""))):
        errors.append("experiment_id chỉ gồm chữ, số, '_' và '-'.")
    selected = [c for c in cases["cases"] if case_ids is None or c["id"] in case_ids]
    if case_ids and set(case_ids) - {c["id"] for c in cases["cases"]}:
        errors.append("Danh sách --cases chứa mã ca không tồn tại.")
    needed = set(re.findall(r"<([A-Z_]+)>", json.dumps(selected))) - {"ROWS", "RUNNING_JOB"}
    if any("running_job" in c.get("fixtures", []) for c in selected):
        needed.add(cfg["running_job_fixture"]["dataset"])
    for key in sorted(needed):
        if not cfg.get("placeholders", {}).get(key):
            errors.append(f"Chưa điền placeholders.{key}")
    for key in ("provider", "model"):
        if not cfg.get(key):
            errors.append(f"Điền {key} rõ ràng để khóa model; không dùng mặc định thay đổi theo .env.")
    for key in ("AGENT_USER", "AGENT_PASSWORD"):
        if not os.getenv(key):
            errors.append(f"Thiếu {key} trong môi trường/.env của backend.")
    try:
        from agent.providers import resolve
        resolve(cfg.get("provider"), cfg.get("model"))
    except (RuntimeError, ValueError) as exc:
        errors.append(str(exc))
    try:
        plan(cfg, cases)
        if float(cfg.get("max_wait_seconds", 0)) <= 0:
            raise ValueError("max_wait_seconds phải > 0")
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    warnings.append("Preflight offline không chứng minh key/quota, backend/consumer đang chạy hoặc ID đã upload đúng dữ liệu.")
    return errors, warnings


def experiment_root(cfg, phase):
    name = cfg.get("experiment_id", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise ValueError("experiment_id không hợp lệ")
    return ARTIFACTS / "runs" / name / phase


def snapshot(cfg, cases, pricing, phase):
    planned_cfg = cfg if phase == "official" else {**cfg, "repeats": 1, "ablation": {"enabled": False}}
    return {"config": cfg, "cases": cases, "pricing": pricing, "phase": phase,
            "manifest": check_data(cfg), "source_hashes": source_hashes(),
            "runtime": runtime_settings(), "provider": provider_settings(cfg), "plan": plan(planned_cfg, cases)}


def freeze(root, payload):
    path = root / "protocol.json"
    if path.exists():
        locked = read_lock(root)
        if locked["protocol_id"] != digest(payload):
            raise ValueError("Protocol đã khóa khác cấu hình/code/dữ liệu hiện tại. Dùng experiment_id mới.")
        return locked
    if list(root.glob("*/*/run.json")):
        raise ValueError("Có run chưa khóa; không được nhập vào đợt mới.")
    root.mkdir(parents=True, exist_ok=True)
    locked = {"protocol_id": digest(payload), "payload": payload}
    path.write_text(json.dumps(locked, ensure_ascii=False, indent=2), encoding="utf-8")
    return locked


def read_lock(root):
    locked = load_json(root / "protocol.json")
    if not locked or digest(locked["payload"]) != locked["protocol_id"]:
        raise ValueError("Thiếu protocol.json hợp lệ; chạy lock trước.")
    return locked


def verify_current(root, cfg, cases, pricing, phase):
    locked = read_lock(root)
    if digest(snapshot(cfg, cases, pricing, phase)) != locked["protocol_id"]:
        raise ValueError("Protocol/code/dữ liệu đã thay đổi; từ chối tiếp tục hoặc chấm bằng cấu hình mới.")
    return locked


def require_complete(root, locked):
    from benchmark.analyze import analyze_run
    cases = {c["id"]: c for c in locked["payload"]["cases"]["cases"]}
    missing = []
    for variant, case, repeat in locked["payload"]["plan"]:
        folder = root / variant / f"{case}_r{repeat:02d}"
        run = load_json(folder / "run.json")
        if not run or run.get("protocol_id") != locked["protocol_id"] or run.get("halt_reason"):
            missing.append(f"{variant}/{case}_r{repeat:02d}")
        elif run.get("interrupted") and not run.get("settle_verified"):
            # Lượt bị ngắt là FAIL, nhưng phải xác nhận job của nó đã dừng (chạy lại `run`) trước khi chấm.
            missing.append(f"{variant}/{case}_r{repeat:02d} (bị ngắt, chưa xác nhận job đã dừng)")
        elif analyze_run(folder, cases[case])["task_status"] == "INVALID_FIXTURE":
            missing.append(f"{variant}/{case}_r{repeat:02d} (INVALID_FIXTURE)")
    if missing:
        raise ValueError(f"Chưa đủ lượt hợp lệ theo plan hoặc còn job chưa kết thúc ({len(missing)}): {', '.join(missing[:8])}")


def check_online(cfg):
    """Read-only backend checks. No LLM, upload, activation or training."""
    from agent import tools
    from agent.api_client import HAutoMLClient
    from benchmark.runner import assert_idle
    errors = []
    manifest = check_data(cfg)
    with HAutoMLClient() as api:
        if not tools.ensure_login(api).get("ok"):
            return ["Không đăng nhập được backend bằng tài khoản benchmark."]
        try:
            assert_idle(api)
        except RuntimeError as exc:
            errors.append(str(exc))
        for name, placeholder in (("glass", "GLASS_ID"), ("shopping", "SHOP_ID"),
                                  ("concrete", "CONCRETE_ID"), ("crab", "CRAB_ID")):
            info = tools.get_dataset_schema(api, cfg["placeholders"][placeholder])
            expected = manifest[name]
            if not info.get("ok") or info.get("total_rows") != expected["n_train"] or \
                    {c["name"] for c in info.get("columns", [])} != set(expected["features"] + [expected["target"]]):
                errors.append(f"{name}: ID không đọc được hoặc số dòng/schema không khớp file train mới.")
        missing = cfg["placeholders"]["MISSING_ID"]
        listing = tools.list_my_datasets(api)
        if not listing.get("ok") or any(d.get("_id") == missing for d in listing.get("datasets", [])):
            errors.append("MISSING_ID chưa được xác nhận không tồn tại trong tài khoản.")
        for key, activated in (("GLASS_JOB", 1), ("INACTIVE_JOB", 0)):
            result = tools.get_job_info(api, cfg["placeholders"][key])
            job = result.get("job") or {}
            expected = manifest["glass"]
            config = job.get("config") or {}
            dataset = (job.get("data") or {}).get("id") or (job.get("data") or {}).get("_id")
            if not result.get("ok") or job.get("status") != 1 or job.get("activate") != activated or \
                    dataset != cfg["placeholders"]["GLASS_ID"] or \
                    config.get("target") != expected["target"] or set(config.get("list_feature", [])) != set(expected["features"]):
                errors.append(f"{key}: fixture phải là Glass train thành công, activate={activated}, đủ feature.")
    return errors
