r"""152_s001_weighted_score.py — s001 筛选加权 vs 等权（路线 #4，组合层）。

134 已建 16 子集联合矩阵（等权 AND 视角）。本脚本回答：**非等权加权得分是否优于等权**？
liq 单条件边际 +4.44%（131/134），vol/vix/brd 各 +1.9/+1.4/+1.6% 量级——等权得分（命中数）
把超强条件与弱条件一视同仁，可能非最优。

数据：直接复用 134 报告的 16 子集全表（n、24h 超额，来源：reports/liq_combo_matrix.md 表1，
2026-08-07 生成，与 131/133 交叉核对一致）。加权得分 W = 3×liq + 1×vol + 1×vix + 1×brd
（权重比例 ≈ 边际贡献比）。分档：W≥3 / ≥4 / ≥5 / ≥6，与等权 ≥k 档（134 表3）对比
每事件超额与总期望（n×超额，126 口径）。

输出：reports/s001_weighted_score.md
用法：python scripts/152_s001_weighted_score.py
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT = PROJECT_ROOT / "reports" / "s001_weighted_score.md"

# 134 表1 16 子集（bits: l=liq v=vol x=vix b=brd；超额 = 24h 超额 vs pooled 基线）
SUBSETS = {
    "0000": (29, -2.46), "0001": (44, -0.84), "0010": (111, +0.05),
    "0011": (132, -0.43), "0100": (53, +0.17), "0101": (49, +1.20),
    "0110": (129, +0.37), "0111": (197, +2.00), "1000": (1, +4.95),
    "1001": (1, -12.08), "1010": (0, 0.0), "1011": (1, +0.05),
    "1100": (10, +3.34), "1101": (18, +0.76), "1110": (35, +0.70),
    "1111": (57, +8.45),
}
# 等权档（134 表3：满足 ≥k 个条件的累积）
EQUAL_WEIGHT = {
    "≥0": (867, +1.03), "≥1": (838, +1.16), "≥2": (629, +1.57),
    "≥3": (308, +2.97), "≥4": (57, +8.45),
}
WEIGHTS = {"l": 3.0, "v": 1.0, "x": 1.0, "b": 1.0}


def weighted_score(bits: str) -> float:
    return sum(WEIGHTS[c] for c, flag in zip("lvxb", bits) if flag == "1")


def main() -> int:
    # 加权分层：W 阈值 → 命中的子集集合
    tiers = [("W≥3", 3.0), ("W≥4", 4.0), ("W≥5", 5.0), ("W≥6", 6.0)]
    lines = ["# s001 筛选加权得分 vs 等权（152，路线 #4）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             "- 数据：134 报告 16 子集全表（2024-06→2026-06 窗口，与 131/133 交叉核对一致）",
             "- 加权得分 W = 3×liq + 1×vol + 1×vix + 1×brd（权重 ∝ 各条件边际贡献：liq +4.44% vs 其他 +1.4~1.9%）",
             "- 对比：加权 W≥k 档 vs 等权 ≥k 档（134 表3）——每事件超额 + 总期望（n×超额）\n",
             "| 档位 | 子集 | n | 24h 超额（加权平均） | 总期望 | 说明 |",
             "|---|---|---:|---:|---:|---|"]
    for label, thr in tiers:
        n = 0
        ex_w = 0.0
        desc = []
        for bits, (sn, sex) in SUBSETS.items():
            if weighted_score(bits) >= thr:
                n += sn
                ex_w += sn * sex
                if sn > 0:
                    desc.append(f"{bits}(n={sn})")
        ex = ex_w / n if n else 0.0
        lines.append(f"| {label} | {' + '.join(desc[:5])}{'…' if len(desc) > 5 else ''} | {n} | {ex:+.2f}% | {n * ex:.0f} | |")
        print(f"[152] {label}: n={n} ex={ex:+.2f}% 总期望={n * ex:.0f}")

    lines.append("\n## 等权对照（134 表3）\n")
    lines.append("| 档位 | n | 24h 超额 | 总期望 |")
    lines.append("|---|---:|---:|---:|")
    for label, (n, ex) in EQUAL_WEIGHT.items():
        lines.append(f"| {label} | {n} | {ex:+.2f}% | {n * ex:.0f} |")

    lines.extend(["\n## 裁决\n",
                   "- 加权档总期望 > 等权同档 → 权重分配有增量（liq 应优先）。",
                   "- 加权档总期望 ≤ 等权同档 → 条件数（等权）已是近似最优，无需调权。",
                   "- 两者最优档对比：加权最优档总期望 vs 等权最优档（≥2，985）——决定 s001 默认档建议。",
                   "- 局限：基于 134 单窗口（2024-06+）子集聚合，非独立重跑；liq 子集 n 小（单条件 n=123），"
                   "加权档的极端值（1001/1011 单事件 -12%/+0.05%）影响小 n 档。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
