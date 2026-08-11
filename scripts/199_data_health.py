r"""199_data_health.py — 数据源健康监控（U1/U7：跨源一致性监控）。

背景：数据源停更靠人肉发现（coinglass klines 停 07-07、衍生停 06-23 都是事后才知）。
本脚本用 data_registry 统一路径 + 新鲜度检查，输出全部注册源的健康报告：
- 每源：存在性、最后 bar 时间、距今小时、是否过期（阈值 per 源）
- 已知停更源标 KNOWN_STALE（coinglass 衍生维度）区分"预期停更"与"意外过期"
- 新增源只需在 data_registry.health_report() 或本脚本加一行

输出：reports/data_health.md + stdout
用法：python scripts/199_data_health.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.data_registry import health_report, paths  # noqa: E402
from harness.lib.data_cleaning import clean_hourly_klines  # noqa: E402

REPORT = PROJECT_ROOT / "reports" / "data_health.md"

# 预期停更（数据源官方断供，非故障）：停更 → 不告警
KNOWN_STALE = {
    "coinglass_klines": "coinglass 公共接口 klines 停于 2026-07-07（记忆：klines 实际到 07-07）",
    "coinglass_liquidation": "coinglass 清算停于 2026-06-23，E21 前向已切 Coinalyze（196）",
}

# 周末无交易（美股/期货）：最后 bar 停在周五 + 今天非周五 → 豁免，不告警
WEEKEND_SOURCES = {"cme_bitcoin", "macro_sp500", "macro_vix"}

# 清洗质量抽样（binance_free klines）
CLEAN_CHECK_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
CLEAN_BAD_RATIO = 0.01  # hard 无效 / 未解 gap 占比上限


def _weekend_exempt(name: str, last_str: str, now: datetime) -> bool:
    if name not in WEEKEND_SOURCES or not last_str:
        return False
    last = pd.to_datetime(last_str, errors="coerce")
    if pd.isna(last):
        return False
    # 最后 bar 为 UTC 周五，且当前非周五（周六/周日/周一晨）→ 周末无数据属预期
    return last.weekday() == 4 and now.weekday() != 4


def _clean_check(now: datetime) -> tuple[list[str], int]:
    """binance_free klines 抽样跑统一清洗管线，报告 quality_flag 分布（清洗在每日链的可见性）。"""
    rows, problems = [], 0
    klines_dir = paths.binance_free.raw_1h / "klines"
    for sym in CLEAN_CHECK_SYMBOLS:
        p = klines_dir / f"{sym}.parquet"
        if not p.exists():
            rows.append(f"| {sym} | 缺失 | - | - | - | - | - | ❌ |")
            problems += 1
            continue
        d = clean_hourly_klines(pd.read_parquet(p))
        n = len(d)
        flags = d["quality_flag"]
        hard = int((flags & 8).astype(bool).sum())
        unresolved = int(d["is_unresolved_gap"].sum())
        bad = hard / max(n, 1) > CLEAN_BAD_RATIO or unresolved / max(n, 1) > CLEAN_BAD_RATIO
        if bad:
            problems += 1
        rows.append(
            f"| {sym} | {len(pd.read_parquet(p))}→{n} | {int((flags == 0).sum())} | "
            f"{int((flags & 1).astype(bool).sum())} | {int((flags & 2).astype(bool).sum())} | "
            f"{hard} | {unresolved} | {'✅' if not bad else '⚠️'} |")
    return rows, problems


def main() -> int:
    rep = health_report()
    now = datetime.now(timezone.utc)
    lines = ["# 数据源健康报告（199）\n",
             f"- 生成：{now:%Y-%m-%d %H:%M} UTC",
             f"- 来源：config/data_paths.yaml + harness/lib/data_registry.py\n",
             "| 源 | 存在 | 最后 bar | 距今(h) | 状态 |",
             "|---|---|---|---|---|"]
    problems = 0
    for name, r in rep.items():
        if not r.get("exists"):
            status = "❌ 缺失"
            problems += 1
        elif r.get("stale"):
            note = KNOWN_STALE.get(name, "")
            if _weekend_exempt(name, r.get("last") or "", now):
                status = "✅ 正常（周末无交易）"
            else:
                status = f"⚠️ 过期{'（预期停更：' + note + '）' if note else ''}"
                if not note:
                    problems += 1
        else:
            status = "✅ 正常"
        lines.append(f"| {name} | {'✓' if r.get('exists') else '✗'} | {r.get('last') or '-'} | "
                     f"{r.get('age_h') if r.get('age_h') is not None else '-'} | {status} |")

    lines.append("\n## 清洗质量（binance_free klines 抽样，data_cleaning.clean_hourly_klines）")
    lines.append("| symbol | 行数(清洗前→后) | OK | Gap_FFill | Outlier | Hard_Invalid | 未解gap | 状态 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    clean_rows, clean_problems = _clean_check(now)
    lines.extend(clean_rows)
    problems += clean_problems

    lines.append(f"\n**意外过期/异常源：{problems} 个**（预期停更与周末豁免不计）")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
