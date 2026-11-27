"""
Dữ liệu 6 dataset mới (adult, madelon, student, digits, gaming, wilt): chia train/test cố định
`feature-group-v1` (seed 42), giữ nguyên giá trị gốc (đọc dạng chuỗi), ghi vào
benchmark_artifacts/datasets/extra/ + manifest_extra.json (kèm 2 ngưỡng ràng buộc tính từ phần train).

    python benchmark/bench.py prepare-extra
    python benchmark/bench.py prepare-extra --rebuild   # ghi lại split khi manifest đã có (cùng file gốc)

File chia giữ đúng thứ tự cột của file gốc (wilt có target `class` ở cột đầu - ca G09 dựa vào đó);
manifest ghi `columns` (header đầy đủ), `features` (mọi cột trừ target, theo thứ tự gốc) và `target`.
"""

# Standard libraries
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

# Third-party
import pandas as pd

# Local modules
from benchmark.common import ARTIFACTS, load_json


RAW_DIR = ARTIFACTS / "raw"
EXTRA_DIR = ARTIFACTS / "datasets" / "extra"
MANIFEST = EXTRA_DIR / "manifest_extra.json"
SPLIT_VERSION = "feature-group-v1"
SEED = 42

SPECS: dict[str, dict] = {
    "adult": {"raw": "adult.csv", "target": "income", "problem_type": "classification"},
    "madelon": {"raw": "Madelon.csv", "target": "decision", "problem_type": "classification"},
    "student": {"raw": "Student_performance_data _.csv", "target": "GradeClass", "problem_type": "classification"},
    "digits": {"raw": "digits.csv", "target": "target", "problem_type": "classification"},
    "gaming": {"raw": "online_gaming_behavior_dataset.csv", "target": "EngagementLevel", "problem_type": "classification"},
    "wilt": {"raw": "wilt.csv", "target": "class", "problem_type": "classification"},
}
THRESHOLD_DATASETS = {"adult_f1_macro": ("adult", "f1_macro"), "wilt_f1_macro": ("wilt", "f1_macro")}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _features(df: pd.DataFrame, target: str) -> list[str]:
    return [c for c in df.columns if c != target]


def split_frame(df: pd.DataFrame, target: str, seed: int = 42, test_ratio: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gom dòng theo tuple toàn bộ feature (nhãn không tham gia khoá) nên không nhóm nào nằm ở cả hai phần;
    phân tầng xấp xỉ theo nhãn đa số của nhóm; mỗi lớp có ở cả train và test khi có ≥ 2 nhóm."""
    features = _features(df, target)
    groups: dict[tuple, list[int]] = defaultdict(list)
    for pos, key in enumerate(df[features].itertuples(index=False, name=None)):
        groups[key].append(pos)
    labels = df[target].tolist()
    strata: dict[str, list[list[int]]] = defaultdict(list)
    for key in sorted(groups):
        members = groups[key]
        majority = sorted(Counter(labels[p] for p in members).most_common(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        strata[majority].append(members)
    rng = random.Random(seed)
    train_pos, test_pos = [], []
    for label in sorted(strata):
        pool = strata[label][:]
        rng.shuffle(pool)
        desired = test_ratio * sum(map(len, pool))
        held = 0
        chosen = []
        for group in pool[:-1]:  # nhóm cuối luôn ở lại train để lớp còn mặt ở train
            if not chosen or abs(held + len(group) - desired) < abs(held - desired):
                chosen.append(group)
                held += len(group)
            else:
                train_pos.extend(group)
        train_pos.extend(pool[-1])
        for group in chosen:
            test_pos.extend(group)
    rng.shuffle(train_pos)
    rng.shuffle(test_pos)
    return df.iloc[train_pos].reset_index(drop=True), df.iloc[test_pos].reset_index(drop=True)


def _cv_score(train: pd.DataFrame, target: str, metric: str) -> float:
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import FunctionTransformer, OneHotEncoder

    features = _features(train, target)
    numeric = [c for c in features if pd.to_numeric(train[c], errors="coerce").notna().all()]
    text = [c for c in features if c not in numeric]
    to_float = FunctionTransformer(lambda x: x.astype(float), feature_names_out="one-to-one")
    pre = ColumnTransformer([("num", to_float, numeric),
                             ("cat", OneHotEncoder(handle_unknown="ignore"), text)])
    model = Pipeline([("pre", pre), ("rf", RandomForestClassifier(random_state=42))])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, train[features], train[target], cv=cv, scoring=metric, n_jobs=-1)
    return float(scores.mean())


def cv_threshold(train: pd.DataFrame, target: str, metric: str) -> float:
    """floor((điểm CV RF - 0.05) / 0.05) * 0.05, chỉ từ phần train."""
    score = _cv_score(train, target, metric)
    return round(math.floor((score - 0.05) / 0.05 + 1e-9) * 0.05, 2)


def _read_raw(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / SPECS[name]["raw"], dtype=str, keep_default_na=False)


def _write(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    df[columns].to_csv(path, index=False, lineterminator="\n", encoding="utf-8")


def build() -> tuple[dict, dict[str, tuple[pd.DataFrame, pd.DataFrame, list[str]]]]:
    manifest = {"split_version": SPLIT_VERSION, "seed": SEED, "datasets": {}, "sha256": {}, "thresholds": {}}
    frames = {}
    for name, spec in SPECS.items():
        raw_path = RAW_DIR / spec["raw"]
        df = _read_raw(name)
        target = spec["target"]
        if target not in df.columns:
            raise SystemExit(f"{spec['raw']}: thiếu cột target {target!r}; header: {list(df.columns)}")
        features = _features(df, target)
        train, test = split_frame(df, target, SEED)
        train_keys = set(train[features].itertuples(index=False, name=None))
        test_keys = set(test[features].itertuples(index=False, name=None))
        if train_keys & test_keys:
            raise SystemExit(f"{name}: nhóm feature giao nhau giữa train và test.")
        classes = sorted(df[target].unique())
        if set(train[target]) != set(classes) or set(test[target]) != set(classes):
            raise SystemExit(f"{name}: thiếu lớp ở train hoặc test sau khi chia nhóm.")
        by_key = df.groupby(features, sort=False)[target].nunique()
        manifest["datasets"][name] = {
            "raw_file": spec["raw"], "raw_sha256": sha256(raw_path), "target": target,
            "problem_type": spec["problem_type"], "columns": list(df.columns), "features": features,
            "n_train": len(train), "n_test": len(test), "classes": classes,
            "train_test_feature_overlap": 0,
            "n_duplicate_feature_rows": int(len(df) - len(train_keys | test_keys)),
            "n_conflicting_target_groups": int((by_key > 1).sum()),
        }
        frames[name] = (train, test, list(df.columns))  # thứ tự cột gốc, target ở đâu giữ đó
    return manifest, frames


def predict_rows(key: str, n: int = 1) -> list[dict]:
    """n dòng đầu file test của dataset `key` (mặc định 1 dòng như ca bảng cũ glass/shopping/concrete/crab), bỏ cột
    target (ở bất kỳ vị trí nào); giá trị cùng kiểu như bộ chấm đọc (số -> float, chữ giữ chữ)."""
    from benchmark.scoring import _read_test

    x, _ = _read_test(EXTRA_DIR / f"{key}_test.csv", SPECS[key]["target"], problem_type=SPECS[key]["problem_type"])
    return x[:n]


def _locked_v6() -> list[Path]:
    """Protocol đã khoá có dùng bộ ca v6 (tức dùng dữ liệu này): không được ghi lại split."""
    return [p for p in (ARTIFACTS / "runs").glob("*/*/protocol.json") if "hautoml-bench-v6" in p.read_text(encoding="utf-8")]


def main(rebuild: bool = False) -> dict:
    missing = [s["raw"] for s in SPECS.values() if not (RAW_DIR / s["raw"]).is_file()]
    if missing:
        raise SystemExit(f"Thiếu file gốc trong {RAW_DIR}: {missing}. Chép file gốc vào đó, hoặc chép nguyên "
                         f"{EXTRA_DIR} từ máy đã dựng (không cần prepare-extra).")
    existing = load_json(MANIFEST)
    if existing:
        for name, spec in SPECS.items():
            if existing.get("datasets", {}).get(name, {}).get("raw_sha256") != sha256(RAW_DIR / spec["raw"]):
                raise SystemExit(f"{MANIFEST} đã có nhưng hash file gốc của {name} khác; xoá thủ công nếu thật sự muốn dựng lại.")
        if not rebuild:
            print(f"đã có {MANIFEST}; giữ nguyên (dùng --rebuild để ghi lại split từ cùng file gốc).")
            return existing
        locked = _locked_v6()
        if locked:
            raise SystemExit(f"Đã có protocol v6 khoá dữ liệu này ({locked[0]}); không ghi lại split.")
        print("--rebuild: ghi lại split và manifest từ cùng file gốc (hash file gốc khớp manifest cũ).")
    manifest, frames = build()
    EXTRA_DIR.mkdir(parents=True, exist_ok=True)
    for name, (train, test, columns) in frames.items():
        _write(train, EXTRA_DIR / f"{name}_train.csv", columns)
        _write(test, EXTRA_DIR / f"{name}_test.csv", columns)
        for split in ("train", "test"):
            manifest["sha256"][f"{name}_{split}.csv"] = sha256(EXTRA_DIR / f"{name}_{split}.csv")
    for key, (name, metric) in THRESHOLD_DATASETS.items():
        manifest["thresholds"][key] = cv_threshold(frames[name][0], SPECS[name]["target"], metric)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, meta in manifest["datasets"].items():
        print(f"{name}: train {meta['n_train']}, test {meta['n_test']}, target {meta['target']}")
    print(f"thresholds: {manifest['thresholds']}")
    print(f"Đã ghi {MANIFEST}. Chỉ tải lên các file *_train.csv; KHÔNG tải *_test.csv.")
    return manifest
