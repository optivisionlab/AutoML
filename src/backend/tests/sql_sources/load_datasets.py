"""
Nạp các bộ dữ liệu benchmark THẬT (benchmark_artifacts/datasets) vào database `datasets` của 2 server
test (tests/sql_sources/docker-compose.yml), cấp quyền CHỈ SELECT cho hautoml_ro để thử SQL agent.

Chỉ nạp phần TRAIN: phần test là dữ liệu chấm điểm giữ kín (manifest: không tải lên, không đưa vào
LLM), nên không để agent đọc được. Trước khi nạp, đối chiếu sha256 với manifest để chắc đúng file gốc.
Database `lab` (dùng cho test tự động) không bị đụng tới. Chạy lại được nhiều lần (xoá rồi tạo lại).

    docker compose -f src/backend/tests/sql_sources/docker-compose.yml up -d --wait
    docker run --rm --network host -v "$PWD":/repo:ro -w /repo hautoml-backend-test:local \
        python -I src/backend/tests/sql_sources/load_datasets.py
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd
import psycopg2
import pymysql
from psycopg2.extras import execute_values

REPO = Path(__file__).resolve().parents[4]
DATA = REPO / "benchmark_artifacts" / "datasets"
DB = "datasets"
POSTGRES = dict(host="127.0.0.1", port=55432, user="admin", password="admin-test-password")
MYSQL = dict(host="127.0.0.1", port=53306, user="root", password="root-test-password")

# bảng -> (file train, manifest, khoá trong manifest, mô tả nguồn)
TABLES = {
    "glass_train": ("glass_train.csv", "manifest.json", "glass", "UCI Glass Identification; target Type"),
    "shopping_train": ("shopping_train.csv", "manifest.json", "shopping",
                       "UCI Online Shoppers Purchasing Intention; target Revenue"),
    "crab_train": ("crab_train.csv", "manifest.json", "crab", "Kaggle sidhus/crab-age-prediction; target Age"),
    "concrete_train": ("concrete_train.csv", "manifest.json", "concrete",
                       "UCI Concrete Compressive Strength (OpenML 44959); target strength"),
    "electricity_train": ("timeseries/electricity_MT_301_2013_hourly_train.csv", "timeseries/manifest_ts.json",
                          "electricity", "UCI ElectricityLoadDiagrams20112014, MT_301, theo giờ; target load_kwh"),
    "weather_co2_train": ("timeseries/weather_jena_co2_hourly_train.csv", "timeseries/manifest_ts.json",
                          "weather", "MPI Jena roof weather 2020, CO2 theo giờ; target co2_ppm"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(file: str, manifest: str) -> pd.DataFrame:
    path = DATA / file
    expected = json.loads((DATA / manifest).read_text())["sha256"][Path(file).name]
    actual = _sha256(path)
    if actual != expected:
        raise SystemExit(f"{file}: sha256 {actual} khác manifest {expected}")
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def _sql_type(dtype, engine: str) -> str:
    if pd.api.types.is_bool_dtype(dtype):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(dtype):
        return "BIGINT"
    if pd.api.types.is_float_dtype(dtype):
        return "DOUBLE PRECISION" if engine == "postgres" else "DOUBLE"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "TIMESTAMP" if engine == "postgres" else "DATETIME"
    return "TEXT"


def _rows(df: pd.DataFrame) -> list[tuple]:
    out = []
    for row in df.itertuples(index=False, name=None):
        out.append(tuple(None if isinstance(v, float) and math.isnan(v)
                         else v.to_pydatetime() if isinstance(v, pd.Timestamp)
                         else v.item() if hasattr(v, "item") else v for v in row))
    return out


def load_postgres(frames: dict[str, tuple[pd.DataFrame, str]]) -> None:
    admin = psycopg2.connect(dbname="lab", **POSTGRES)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB,))
        if cur.fetchone() is None:
            cur.execute(f'CREATE DATABASE "{DB}"')
    admin.close()

    conn = psycopg2.connect(dbname=DB, **POSTGRES)
    with conn, conn.cursor() as cur:
        cur.execute("SET standard_conforming_strings = on")  # server test cố ý để off
        cur.execute(f'GRANT CONNECT ON DATABASE "{DB}" TO hautoml_ro')
        cur.execute("GRANT USAGE ON SCHEMA public TO hautoml_ro")
        for table, (df, note) in frames.items():
            cols = [c.lower() for c in df.columns]  # chữ thường như thói quen PostgreSQL (giống lab.glass)
            ddl = ", ".join(f'"{c}" {_sql_type(t, "postgres")}' for c, t in zip(cols, df.dtypes))
            cur.execute(f'DROP TABLE IF EXISTS "{table}"')
            cur.execute(f'CREATE TABLE "{table}" ({ddl})')
            execute_values(cur, f'INSERT INTO "{table}" VALUES %s', _rows(df), page_size=1000)
            cur.execute(f'COMMENT ON TABLE "{table}" IS %s', (note,))
            cur.execute(f'GRANT SELECT ON "{table}" TO hautoml_ro')
    conn.close()


def load_mysql(frames: dict[str, tuple[pd.DataFrame, str]]) -> None:
    conn = pymysql.connect(charset="utf8mb4", autocommit=True, **MYSQL)
    with conn.cursor() as cur:
        # Server test cố ý bật ANSI_QUOTES / NO_BACKSLASH_ESCAPES: trả về chế độ thường cho phiên nạp.
        cur.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES'")
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB}` CHARACTER SET utf8mb4")
        cur.execute(f"USE `{DB}`")
        for table, (df, note) in frames.items():
            ddl = ", ".join(f"`{c}` {_sql_type(t, 'mysql')}" for c, t in zip(df.columns, df.dtypes))
            cur.execute(f"DROP TABLE IF EXISTS `{table}`")
            cur.execute(f"CREATE TABLE `{table}` ({ddl}) COMMENT = %s", (note,))
            marks = ", ".join(["%s"] * len(df.columns))
            cur.executemany(f"INSERT INTO `{table}` VALUES ({marks})", _rows(df))
            cur.execute(f"GRANT SELECT ON `{DB}`.`{table}` TO 'hautoml_ro'@'%'")
    conn.close()


def main() -> None:
    frames = {}
    for table, (file, manifest, key, source) in TABLES.items():
        df = _load(file, manifest)
        frames[table] = (df, f"{source}. Phần train của benchmark ({key}), {len(df)} dòng; phần test giữ kín.")
        print(f"{table:<20} {len(df):>6} dòng  {len(df.columns):>2} cột  sha256 khớp manifest")
    load_postgres(frames)
    print(f"PostgreSQL 127.0.0.1:55432/{DB}: đã nạp {len(frames)} bảng")
    load_mysql(frames)
    print(f"MySQL      127.0.0.1:53306/{DB}: đã nạp {len(frames)} bảng")


if __name__ == "__main__":
    main()
