"""
Chia 4 bộ dữ liệu thật thành train/test cố định (seed 42) cho benchmark.

Không sinh dữ liệu: Glass và Online Shoppers có sẵn trong repo; Crab Age (Kaggle)
và Concrete Compressive Strength (UCI, qua OpenML) tải về benchmark_artifacts/raw/
kèm source_metadata.json ghi nguồn, phiên bản, ngày tải.

Chỉ cần Python chuẩn. Ghi ra benchmark_artifacts/datasets/ + manifest.json.
"""

# Standard libraries
import csv
import hashlib
import json
import math
import random
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path

# Local modules
from benchmark.common import ARTIFACTS, REPO


RAW_DIR = ARTIFACTS / "raw"
OUT_DIR = ARTIFACTS / "datasets"
SEED = 42
SPLIT_VERSION = "feature-group-v1"
DOWNLOADED = ("crab_age.csv", "concrete.csv")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shown(path: Path) -> str:
    """Đường dẫn ghi vào manifest: tương đối với repo khi nằm trong repo."""
    return str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def numeric(value, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise SystemExit(f"{field}: giá trị không phải số: {value!r}")
    if not math.isfinite(number):
        raise SystemExit(f"{field}: không chấp nhận NaN hoặc infinity.")
    return number


def check_sources() -> dict:
    """Mỗi file tải về phải có nguồn, phiên bản và ngày tải thật."""
    metadata = json.loads((RAW_DIR / "source_metadata.json").read_text(encoding="utf-8")) \
        if (RAW_DIR / "source_metadata.json").is_file() else {}
    problems = []
    for name in DOWNLOADED:
        source = metadata.get(name) or {}
        if not (RAW_DIR / name).is_file():
            problems.append(f"thiếu file {RAW_DIR / name}")
            continue
        if any(not isinstance(source.get(k), str) or not source[k].strip() for k in ("source_url", "version", "downloaded_at")):
            problems.append(f"{name}: source_metadata.json cần source_url, version, downloaded_at")
            continue
        try:
            date.fromisoformat(source["downloaded_at"])
        except ValueError:
            problems.append(f"{name}: downloaded_at phải có dạng YYYY-MM-DD")
    if problems:
        raise SystemExit("Chưa đủ dữ liệu gốc:\n  - " + "\n  - ".join(problems))
    return metadata


def load_raw(name: str, required: list[str], categories: dict, metadata: dict) -> tuple[list[dict], dict]:
    path = RAW_DIR / name
    rows, dropped, total = [], 0, 0
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        missing = [c for c in required if c not in header]
        if missing:
            raise SystemExit(f"{name}: thiếu cột {missing}; header thực tế: {header}")
        if len(header) != len(set(header)):
            raise SystemExit(f"{name}: header có cột trùng.")
        for row in reader:
            total += 1
            if None in row:
                raise SystemExit(f"{name}: dòng {reader.line_num} có thừa ô.")
            for column, allowed in categories.items():
                label = (row.get(column) or "").strip().lower()
                if label and label not in allowed:
                    raise SystemExit(f"{name}: {column}={row[column]!r} không hợp lệ ở dòng {reader.line_num}.")
            if any(not (row.get(c) or "").strip() for c in required):
                dropped += 1
                continue
            rows.append(row)
    if not rows:
        raise SystemExit(f"{name}: không còn dòng dữ liệu hợp lệ.")
    provenance = {**metadata[name], "raw_file": shown(path), "raw_sha256": sha256(path),
                  "rows_read": total, "rows_kept": len(rows), "rows_dropped_missing_required": dropped}
    return rows, provenance


def export(name: str, rows: list[dict], target: str, stratify: bool = False) -> dict:
    """Keep every observation; identical feature vectors stay in the same split.

    Labels are never part of the grouping key, so conflicting targets cannot
    put the same input in both train and test. Stratification is approximate.
    """
    if not rows:
        raise SystemExit(f"{name}: dữ liệu rỗng.")
    rng = random.Random(SEED)
    features = [c for c in rows[0] if c != target]
    by_features = defaultdict(list)
    for row in rows:
        key = tuple(numeric(row[c], f"{name}.{c}") for c in features)
        numeric(row[target], f"{name}.{target}")
        by_features[key].append(row)
    strata = defaultdict(list)
    for key, members in sorted(by_features.items()):
        labels = tuple(sorted({numeric(r[target], target) for r in members}))
        strata[labels if stratify else ()].append(members)
    train, test = [], []
    for label in sorted(strata):
        groups = strata[label][:]
        rng.shuffle(groups)
        desired = 0.2 * sum(map(len, groups))
        chosen, heldout = [], 0
        for group in groups[:-1]:
            if not chosen or abs(heldout + len(group) - desired) < abs(heldout - desired):
                chosen.append(group)
                heldout += len(group)
            else:
                train.extend(group)
        train.extend(groups[-1])
        for group in chosen:
            test.extend(group)
    if not train or not test:
        raise SystemExit(f"{name}: quá ít nhóm feature để chia train/test.")
    if stratify and {float(r[target]) for r in train} != {float(r[target]) for r in test}:
        raise SystemExit(f"{name}: thiếu lớp trong train/test sau chia nhóm; cần protocol khác.")
    rng.shuffle(train)
    rng.shuffle(test)
    for split, data in (("train", train), ("test", test)):
        with (OUT_DIR / f"{name}_{split}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(data)
    return {"target": target, "n_train": len(train), "n_test": len(test),
            "features": features, "n_feature_groups": len(by_features),
            "n_duplicate_feature_rows": len(rows) - len(by_features),
            "n_conflicting_target_groups": sum(len({float(r[target]) for r in g}) > 1 for g in by_features.values()),
            "train_test_feature_overlap": 0}


def main() -> None:
    if list((ARTIFACTS / "runs").glob("*/*/protocol.json")):
        raise SystemExit("Đã có protocol khóa. Không ghi lại dữ liệu của các đợt đang lưu; dùng workspace riêng cho bộ dữ liệu mới.")
    metadata = check_sources()

    crab_cols = ["Length", "Diameter", "Height", "Weight", "Shucked Weight", "Viscera Weight", "Shell Weight"]
    crab_src, crab_source = load_raw("crab_age.csv", ["Sex"] + crab_cols + ["Age"], {"Sex": {"f", "i", "m"}}, metadata)
    crab = []
    for r in crab_src:
        row = {c.replace(" ", "_"): numeric(r[c], f"crab.{c}") for c in crab_cols}
        sex = r["Sex"].strip().upper()
        row.update({"Sex_F": int(sex == "F"), "Sex_I": int(sex == "I"), "Sex_M": int(sex == "M")})
        row["Age"] = numeric(r["Age"], "crab.Age")
        crab.append(row)

    concrete_cols = ["cement", "blast_furnace_slag", "fly_ash", "water", "superplasticizer",
                     "coarse_aggregate", "fine_aggregate", "age"]
    concrete_src, concrete_source = load_raw("concrete.csv", concrete_cols + ["strength"], {}, metadata)
    concrete = [{c: numeric(r[c], f"concrete.{c}") for c in concrete_cols + ["strength"]} for r in concrete_src]

    glass_path = REPO / "docs/data_automl/user/glass.csv"
    shop_path = REPO / "docs/data_automl/user/online_shoppers_intention.csv"
    shop_cols = ["Administrative", "Administrative_Duration", "Informational", "Informational_Duration",
                 "ProductRelated", "ProductRelated_Duration", "BounceRates", "ExitRates", "PageValues", "SpecialDay"]
    shop = []
    for row in read_csv(shop_path):
        label = row["Revenue"].strip().lower()
        if label not in {"true", "false"}:
            raise SystemExit(f"Shopping: Revenue không hợp lệ: {label!r}")
        shop.append({**{c: row[c] for c in shop_cols}, "Revenue": int(label == "true")})

    if (OUT_DIR / "manifest.json").is_file():
        archive = ARTIFACTS / "datasets_archive" / sha256(OUT_DIR / "manifest.json")[:16]
        if not archive.exists():
            shutil.copytree(OUT_DIR, archive)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "split_seed": SEED,
        "split_version": SPLIT_VERSION,
        "split_policy": "group_by_all_selected_features_keep_rows_approximate_stratification",
        "sources": {
            "glass": {"raw_file": shown(glass_path), "raw_sha256": sha256(glass_path), "origin": "repository"},
            "shopping": {"raw_file": shown(shop_path), "raw_sha256": sha256(shop_path), "origin": "repository"},
            "crab": crab_source, "concrete": concrete_source,
        },
        "glass": export("glass", read_csv(glass_path), "Type", stratify=True),
        "shopping": export("shopping", shop, "Revenue", stratify=True),
        "crab": export("crab", crab, "Age"),
        "concrete": export("concrete", concrete, "strength"),
    }
    manifest["sha256"] = {f"{name}_{split}.csv": sha256(OUT_DIR / f"{name}_{split}.csv")
                          for name in ("glass", "shopping", "crab", "concrete") for split in ("train", "test")}
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for name in ("glass", "shopping", "crab", "concrete"):
        print(f"  {name}: {manifest[name]['n_train']} train / {manifest[name]['n_test']} test, target {manifest[name]['target']}")
    print(f"Đã ghi {OUT_DIR}. Chỉ upload các file *_train.csv.")
