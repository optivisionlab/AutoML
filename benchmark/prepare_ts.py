"""
Dữ liệu nhóm T (time series): hai chuỗi THẬT theo giờ, tách theo thời gian thành phần train
(tải lên HAutoML) và 96 bước cuối để chấm (KHÔNG tải lên, không đưa vào LLM).

96 bước = PRED_SEQ_LEN của AutoML-Agent (ICML 2025) cho Weather / Electricity.
Không nội suy, không bù, không sinh số liệu: cửa sổ được chọn sao cho chuỗi đủ và cách đều.

    python benchmark/bench.py prepare-ts

Nguồn (đặt sẵn trong benchmark_artifacts, thư mục git bỏ qua; URL tải trong manifest_ts.json):
- raw/electricity_uci321/{electricityloaddiagrams20112014.zip, LD2011_2014.txt}: UCI 321 (giải nén zip).
- raw/weather_mpi_jena/mpi_roof_2020{a,b}.{zip,csv}: trạm thời tiết MPI-BGC Jena năm 2020.
"""

# Standard libraries
import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

# Local modules
from benchmark.common import ARTIFACTS, REPO, load_json


TS_DIR = ARTIFACTS / "datasets" / "timeseries"
MANIFEST = TS_DIR / "manifest_ts.json"
SPLIT_VERSION = "time-holdout-v1"
HORIZON = 96
TIME_COLUMN = "date"
FMT = "%Y-%m-%d %H:%M:%S"
_ELEC_RAW = ARTIFACTS / "raw" / "electricity_uci321"
ELEC_CLIENT = "MT_301"
ELEC_WINDOW = (datetime(2013, 4, 1), datetime(2013, 9, 30, 23))
_WEATHER_DIR = ARTIFACTS / "raw" / "weather_mpi_jena"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_hourly(rows: list[tuple[datetime, float]], name: str) -> None:
    stamps = [t for t, _ in rows]
    if len(set(stamps)) != len(stamps):
        raise ValueError(f"{name}: mốc thời gian trùng")
    if not all(b - a == timedelta(hours=1) for a, b in zip(stamps, stamps[1:])):
        raise ValueError(f"{name}: mốc không cách đều 1 giờ")


def calibrate_threshold(train: list[float], windows: int = 8) -> dict:
    """
    Ngưỡng rmse cho ca có ràng buộc, CHỈ từ phần train: trung vị RMSE của baseline lặp lại tuần
    trước (168 giờ) trên `windows` cửa sổ 96 giờ liên tiếp cuối phần train (mỗi cửa sổ chỉ dùng dữ
    liệu trước nó). Đạt ngưỡng = không tệ hơn dự báo ngây thơ điển hình của chuỗi đó.
    """
    scores = []
    for k in range(windows):
        end = len(train) - HORIZON * k
        history, actual = train[:end - HORIZON], train[end - HORIZON:end]
        forecast = [history[-168 + i] for i in range(HORIZON)]
        scores.append(math.sqrt(sum((a - f) ** 2 for a, f in zip(actual, forecast)) / HORIZON))
    ordered = sorted(scores)
    median = (ordered[windows // 2 - 1] + ordered[windows // 2]) / 2 if windows % 2 == 0 else ordered[windows // 2]
    return {"rule": f"trung vị RMSE baseline lặp lại tuần trước trên {windows} cửa sổ {HORIZON} giờ cuối phần train, làm tròn 1 chữ số",
            "window_rmse": [round(v, 4) for v in scores], "rmse_threshold": round(median, 1)}


def _split(rows, name: str, target: str, decimals: int) -> tuple[dict, dict[str, str]]:
    """(meta, {tên file: nội dung}) - 96 bước cuối là test."""
    train, test = rows[:-HORIZON], rows[-HORIZON:]
    texts = {}
    files = {}
    for split, part in (("train", train), ("test", test)):
        filename = f"{name}_{split}.csv"
        texts[filename] = f"{TIME_COLUMN},{target}\n" + "".join(
            f"{t.strftime(FMT)},{v:.{decimals}f}\n" for t, v in part
        )
        files[split] = filename
    meta = {
        "time_column": TIME_COLUMN, "target": target, "frequency": "1h", "horizon": HORIZON,
        "n_train": len(train), "n_test": len(test),
        "train_range": [train[0][0].strftime(FMT), train[-1][0].strftime(FMT)],
        "test_range": [test[0][0].strftime(FMT), test[-1][0].strftime(FMT)],
        "files": files,
        "threshold_calibration": calibrate_threshold([v for _, v in train]),
    }
    return meta, texts


def electricity() -> tuple[dict, dict[str, str]]:
    """
    UCI 321 (LD2011_2014.txt), khách hàng MT_301, 2013-04-01 .. 2013-09-30: 15 phút -> giờ.

    Năm 2013 chưa từng dùng khi phát triển tính năng time series (bản thử ngày 2026-11-03 dùng
    2014-04..09 của cùng khách hàng), nên 96 giờ test là dữ liệu chưa ai nhìn. Tháng 4-9 tránh hai
    ngày đổi giờ UCI ghi chú (tháng 3: 1h-2h toàn số 0; tháng 10: một giờ cộng dồn hai giờ).
    """
    first, last = ELEC_WINDOW
    values: dict[datetime, list[float]] = {}
    with (_ELEC_RAW / "LD2011_2014.txt").open(encoding="utf-8") as f:
        header = [h.strip('"') for h in f.readline().rstrip("\n").split(";")]
        col = header.index(ELEC_CLIENT)
        for line in f:
            stamp = datetime.strptime(line[1:20], FMT)
            # Mốc UCI là CUỐI khoảng 15 phút: 00:15 .. 01:00 thuộc giờ bắt đầu 00:00.
            hour = (stamp - timedelta(minutes=15)).replace(minute=0)
            if hour < first:
                continue
            if hour > last:
                break
            values.setdefault(hour, []).append(float(line.rstrip("\n").split(";")[col].replace(",", ".")))
    hours = sorted(values)
    if not hours or hours[0] != first or hours[-1] != last or not all(len(values[h]) == 4 for h in hours):
        raise ValueError("electricity: cửa sổ thiếu mốc 15 phút")
    if not all(v > 0 for h in hours for v in values[h]):
        raise ValueError(f"electricity: {ELEC_CLIENT} có giá trị 0 trong cửa sổ (khách hàng không hoạt động)")
    # Trung bình kW trong một giờ = điện năng (kWh) của giờ đó.
    rows = [(h, sum(values[h]) / 4) for h in hours]
    _check_hourly(rows, "electricity")
    meta, texts = _split(rows, f"electricity_{ELEC_CLIENT}_2013_hourly", "load_kwh", 4)
    meta["source"] = {
        "name": f"UCI ElectricityLoadDiagrams20112014 (id 321), khách hàng {ELEC_CLIENT}",
        "url": "https://archive.ics.uci.edu/dataset/321/electricityloaddiagrams20112014",
        "download_url": "https://archive.ics.uci.edu/static/public/321/electricityloaddiagrams20112014.zip",
        "files": {
            f"benchmark_artifacts/raw/electricity_uci321/{name}": sha256(_ELEC_RAW / name)
            for name in ("electricityloaddiagrams20112014.zip", "LD2011_2014.txt")
        },
        "downloaded_at": "2026-11-06",
        "license": "CC BY 4.0",
        "processing": (
            f"Cột {ELEC_CLIENT} (kW, 15 phút; mốc là cuối khoảng). Trung bình 4 mốc thành 1 giờ = kWh của giờ "
            "(date = giờ bắt đầu). Cửa sổ 2013-04-01 00:00 .. 2013-09-30 23:00: đủ mốc, mọi giá trị > 0, tránh hai "
            "ngày đổi giờ. Không nội suy hay bù số liệu."
        ),
        "paper_dataset": "Electricity (AutoML-Agent, qua Time-Series-Library) - cùng nguồn UCI 321",
        "not_used_before": "Bản thử 2026-11-03 dùng 2014-04..09 của cùng khách hàng; cửa sổ 2013 này chưa từng dùng.",
    }
    return meta, texts


def weather() -> tuple[dict, dict[str, str]]:
    """
    MPI-BGC Jena, trạm trên mái, 2020: CO2 (ppm) 10 phút -> trung bình theo giờ.

    CO2 là cột target "OT" Time-Series-Library dùng khi dự báo một chuỗi trên Weather. Không dùng
    nhiệt độ: RMSLE của bài (log(1 + y)) không xác định khi y <= -1 (tháng 12 ở Jena < -1 độ C).
    """
    first, last = datetime(2020, 8, 9), datetime(2020, 12, 31, 23)
    values: dict[datetime, list[float]] = {}
    for part in ("2020a", "2020b"):
        with (_WEATHER_DIR / f"mpi_roof_{part}.csv").open(encoding="latin1") as f:
            header = [h.strip().strip('"') for h in f.readline().rstrip("\n").split(",")]
            col = header.index("CO2 (ppm)")
            for line in f:
                cells = line.rstrip("\n").split(",")
                stamp = datetime.strptime(cells[0].strip(), "%d.%m.%Y %H:%M:%S")
                # Mốc là CUỐI khoảng 10 phút: HH:10 .. HH+1:00 thuộc giờ bắt đầu HH:00.
                hour = (stamp - timedelta(minutes=10)).replace(minute=0)
                if first <= hour <= last:
                    values.setdefault(hour, []).append(float(cells[col]))
    hours = sorted(values)
    if not hours or hours[0] != first or hours[-1] != last or not all(len(values[h]) == 6 for h in hours):
        raise ValueError("weather: cửa sổ thiếu mốc 10 phút")
    # File gốc ghi -9999 khi thiết bị không đo: cửa sổ đã chọn không có giá trị nào như vậy.
    if not all(0 < v < 1000 for h in hours for v in values[h]):
        raise ValueError("weather: có giá trị CO2 không hợp lệ trong cửa sổ")
    rows = [(h, sum(values[h]) / 6) for h in hours]
    _check_hourly(rows, "weather")
    meta, texts = _split(rows, "weather_jena_co2_hourly", "co2_ppm", 2)
    meta["source"] = {
        "name": "Max Planck Institute for Biogeochemistry, Jena - Weather Station (mpi_roof), năm 2020",
        "url": "https://www.bgc-jena.mpg.de/wetter/weather_data.html",
        "download_urls": [f"https://www.bgc-jena.mpg.de/wetter/data/mpi_roof_{p}.zip" for p in ("2020a", "2020b")],
        "files": {
            f"benchmark_artifacts/raw/weather_mpi_jena/mpi_roof_{p}.{ext}": sha256(_WEATHER_DIR / f"mpi_roof_{p}.{ext}")
            for p in ("2020a", "2020b") for ext in ("zip", "csv")
        },
        "downloaded_at": "2026-11-06",
        "license": "CC BY 4.0 (Terms of Use trên trang nguồn)",
        "processing": (
            "Cột CO2 (ppm) - target OT của Time-Series-Library. Mốc 10 phút là cuối khoảng; trung bình 6 mốc "
            "thành 1 giờ (date = giờ bắt đầu). Cửa sổ 2020-08-09 00:00 .. 2020-12-31 23:00 là đoạn sạch dài "
            "nhất của năm: file gốc có CO2 = -9999 (không đo) ngày 2020-02-20 và 2020-08-08, một mốc trùng "
            "(2020-05-12 06:00) và một khoảng thiếu 80 phút (2020-05-29). Không nội suy hay bù số liệu."
        ),
        "paper_dataset": "Weather (AutoML-Agent, qua Time-Series-Library) - cùng trạm, cùng năm 2020; "
                         "bài dự báo đa biến 21 cột, ở đây một chuỗi CO2 (target OT)",
    }
    return meta, texts


def build() -> tuple[dict, dict[str, str]]:
    datasets, texts = {}, {}
    for name, builder in (("electricity", electricity), ("weather", weather)):
        datasets[name], part = builder()
        texts.update(part)
    manifest = {
        "split_version": SPLIT_VERSION,
        "policy": f"Tách theo thời gian: {HORIZON} bước cuối là test (không tải lên, không đưa vào LLM, "
                  "không dùng để chọn ngưỡng/prompt). Train là toàn bộ phần trước đó; không xáo trộn.",
        "datasets": datasets,
        "sha256": {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in sorted(texts.items())},
        "build_script": str(Path(__file__).resolve().relative_to(REPO)),
    }
    return manifest, texts


def main() -> None:
    try:
        manifest, texts = build()
    except FileNotFoundError as error:
        raise SystemExit(
            f"Thiếu file gốc: {error.filename}. Máy khác: chép nguyên benchmark_artifacts/datasets/timeseries/ "
            "từ máy đã dựng (không cần prepare-ts); hoặc tải file gốc theo URL trong docstring/manifest."
        ) from None
    existing = load_json(MANIFEST)
    if existing and existing.get("sha256") != manifest["sha256"]:
        # Dữ liệu đã khoá (có thể đã upload / đã chạy) không được âm thầm đổi.
        raise SystemExit(f"{MANIFEST} đã có và khác dữ liệu dựng lại; xoá thủ công nếu thật sự muốn dựng lại.")
    TS_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in texts.items():
        (TS_DIR / name).write_text(text, encoding="utf-8", newline="\n")
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, meta in manifest["datasets"].items():
        print(f"{name}: train {meta['n_train']} {meta['train_range']}, test {meta['n_test']} {meta['test_range']}")
    print(f"Đã ghi {MANIFEST}. Tải lên HAutoML đúng hai file *_train.csv; KHÔNG tải *_test.csv.")


if __name__ == "__main__":
    main()
