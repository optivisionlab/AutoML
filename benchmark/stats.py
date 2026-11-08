"""
Thống kê mô tả và so sánh cho báo cáo benchmark, viết bằng Python thuần (không cần scipy).

Nguyên tắc:
- Luôn báo n. Khoảng tin cậy 95% cho trung bình dùng phân phối t (n nhỏ); cho tỷ lệ dùng Wilson.
- So sánh CÓ CẶP chỉ khi hai bên chạy cùng ca trong cùng khối lặp (ablation chạy xen kẽ theo lịch đã khoá).
  Cặp này KHÔNG chung seed LLM/HPO - đây là ghép theo lịch chạy, nêu rõ trong báo cáo.
- Kiểm định: Wilcoxon signed-rank hai phía, p chính xác (liệt kê phân phối) khi n ≤ 25, xấp xỉ chuẩn khi
  lớn hơn; cặp có hiệu = 0 bị loại như thông lệ (Wilcoxon 1945). Kèm khoảng bootstrap của hiệu trung bình.
- Không tự kết luận "tốt hơn có ý nghĩa thống kê": hàm chỉ trả số; báo cáo nêu ngưỡng và cỡ mẫu.
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Sequence

# t_{0.975, df} cho df = 1..30 (bảng chuẩn); df > 30 dùng nội suy về 1.96.
_T975 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
         2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
         2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def t_critical(df: int) -> float:
    if df < 1:
        raise ValueError("df phải >= 1")
    if df <= 30:
        return _T975[df - 1]
    # Khai triển Cornish-Fisher hai số hạng quanh z = 1.96: sai số < 0.0005 với df > 30.
    z = 1.959964
    return z + (z ** 3 + z) / (4 * df) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * df ** 2)


def clean(values: Sequence) -> list[float]:
    return [float(v) for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]


def describe(values: Sequence) -> dict:
    """mean, std mẫu, n, khoảng tin cậy 95% (t) của trung bình. Không có giá trị thì mọi trường None (n = 0)."""
    data = clean(values)
    n = len(data)
    result = {"n": n, "mean": None, "std": None, "ci_low": None, "ci_high": None, "min": None, "max": None}
    if not n:
        return result
    mean = statistics.fmean(data)
    result.update({"mean": mean, "min": min(data), "max": max(data)})
    if n >= 2:
        std = statistics.stdev(data)
        half = t_critical(n - 1) * std / math.sqrt(n)
        result.update({"std": std, "ci_low": mean - half, "ci_high": mean + half})
    return result


def wilson(successes: int, total: int, z: float = 1.959964) -> tuple[float | None, float | None]:
    """Khoảng Wilson 95% cho tỷ lệ - đúng cả khi tỷ lệ là 0 hay 1, khác khoảng Wald."""
    if total <= 0:
        return None, None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def bootstrap_mean_ci(values: Sequence, iterations: int = 5000, seed: int = 0) -> tuple[float | None, float | None]:
    """Khoảng bootstrap phân vị 95% của trung bình (seed cố định để báo cáo tái lập được)."""
    data = clean(values)
    if len(data) < 2:
        return None, None
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(data, k=len(data))) for _ in range(iterations))
    return means[int(0.025 * (iterations - 1))], means[int(0.975 * (iterations - 1))]


def _wilcoxon_exact_p(ranks: list[float], w_plus: float) -> float:
    """p hai phía chính xác: liệt kê phân phối của W+ theo hạng (hạng nửa được nhân đôi để thành số nguyên)."""
    doubled = [int(round(2 * r)) for r in ranks]
    total = sum(doubled)
    counts = {0: 1}
    for r in doubled:
        nxt = dict(counts)
        for s, c in counts.items():
            nxt[s + r] = nxt.get(s + r, 0) + c
        counts = nxt
    observed = int(round(2 * w_plus))
    mirrored = total - observed
    low, high = min(observed, mirrored), max(observed, mirrored)
    tail = sum(c for s, c in counts.items() if s <= low) + sum(c for s, c in counts.items() if s >= high)
    return min(1.0, tail / 2 ** len(doubled))


def wilcoxon_signed_rank(differences: Sequence) -> dict:
    """
    Wilcoxon signed-rank cho hiệu theo cặp (b - a). Trả n_used (sau khi bỏ hiệu 0), W+, W-, p hai phía và
    phương pháp ("exact" khi n_used <= 25). n_used < 1 thì p = None.
    """
    diffs = [d for d in clean(differences) if d != 0]
    n = len(diffs)
    if not n:
        return {"n_used": 0, "w_plus": None, "w_minus": None, "p_value": None, "method": None}
    ordered = sorted(range(n), key=lambda i: abs(diffs[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(diffs[ordered[j + 1]]) == abs(diffs[ordered[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[ordered[k]] = (i + j) / 2 + 1
        i = j + 1
    w_plus = sum(r for r, d in zip(ranks, diffs) if d > 0)
    w_minus = sum(r for r, d in zip(ranks, diffs) if d < 0)
    if n <= 25:
        p, method = _wilcoxon_exact_p(ranks, w_plus), "exact"
    else:
        mean = n * (n + 1) / 4
        ties = {}
        for r in ranks:
            ties[r] = ties.get(r, 0) + 1
        variance = n * (n + 1) * (2 * n + 1) / 24 - sum(t ** 3 - t for t in ties.values()) / 48
        z = (abs(w_plus - mean) - 0.5) / math.sqrt(variance) if variance > 0 else 0.0
        p, method = min(1.0, math.erfc(z / math.sqrt(2))), "normal"
    return {"n_used": n, "w_plus": w_plus, "w_minus": w_minus, "p_value": p, "method": method}


def paired_comparison(pairs: Sequence[tuple], seed: int = 0) -> dict:
    """
    pairs: (a, b) cùng ca, cùng khối lặp. Bỏ cặp thiếu một bên. Trả hiệu trung bình (b - a), khoảng
    bootstrap 95%, số cặp b tốt hơn / kém hơn / bằng, và Wilcoxon. Hướng "tốt hơn" do người gọi diễn giải.
    """
    usable = [(float(a), float(b)) for a, b in pairs if a is not None and b is not None]
    diffs = [b - a for a, b in usable]
    low, high = bootstrap_mean_ci(diffs, seed=seed)
    return {
        "n_pairs": len(usable),
        "mean_a": statistics.fmean(a for a, _ in usable) if usable else None,
        "mean_b": statistics.fmean(b for _, b in usable) if usable else None,
        "mean_diff": statistics.fmean(diffs) if diffs else None,
        "diff_ci_low": low, "diff_ci_high": high,
        "b_higher": sum(d > 0 for d in diffs), "b_lower": sum(d < 0 for d in diffs), "ties": sum(d == 0 for d in diffs),
        "wilcoxon": wilcoxon_signed_rank(diffs),
    }


def mcnemar_exact(a_only: int, b_only: int) -> float | None:
    """
    McNemar chính xác (nhị thức) cho kết quả nhị phân theo cặp: a_only = cặp chỉ A đạt, b_only = chỉ B đạt.
    p hai phía; không có cặp lệch thì None (không có bằng chứng theo hướng nào).
    """
    n = a_only + b_only
    if n == 0:
        return None
    k = min(a_only, b_only)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def fmt_ci(summary: dict, digits: int = 3) -> str:
    """'0.812 ± 0.040 [0.763, 0.861] (n=5)'; thiếu dữ liệu thì '—'."""
    if not summary or summary.get("mean") is None:
        return "—"
    if summary["n"] == 1:
        return f"{summary['mean']:.{digits}f} (n=1)"
    return (f"{summary['mean']:.{digits}f} ± {summary['std']:.{digits}f} "
            f"[{summary['ci_low']:.{digits}f}, {summary['ci_high']:.{digits}f}] (n={summary['n']})")


def fmt_rate(successes: int, total: int) -> str:
    """'7/10 (70.0%) [39.7%, 89.2%]' - tỷ lệ kèm khoảng Wilson."""
    if not total:
        return "—"
    low, high = wilson(successes, total)
    return f"{successes}/{total} ({successes / total:.1%}) [{low:.1%}, {high:.1%}]"
