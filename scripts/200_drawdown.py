r"""200_drawdown.py — 账户回撤可视化与统计（U5：回撤可视化缺失补位）。

从 paper_equity_{A,B,C,D}.csv 计算：
- 最大回撤 / 当前回撤 / 回撤时长 / 恢复期 / 水下曲线（underwater）
- 输出 reports/dashboard/drawdown.png（水下曲线堆叠图）+ reports/drawdown_stats.md

也可作为模块被 174_dashboard.py 复用（把回撤面板并入每日看板）。

用法：python scripts/200_drawdown.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

REPORTS = PROJECT_ROOT / "reports"
OUT_PNG = REPORTS / "dashboard" / "drawdown.png"
OUT_MD = REPORTS / "drawdown_stats.md"
ACCOUNTS = {"A": "统计口径", "B": "风控口径", "C": "4h确认", "D": "新币×确认"}


def drawdown_series(equity: pd.Series) -> pd.Series:
    """水下曲线：equity / running_max - 1（%）"""
    peak = equity.cummax()
    return (equity / peak - 1.0) * 100.0


def drawdown_stats(equity: pd.Series) -> dict:
    dd = drawdown_series(equity)
    max_dd = dd.min()
    cur_dd = dd.iloc[-1] if len(dd) else np.nan
    # 当前回撤段起点（从峰值回落开始）
    start = None
    for i in range(len(dd) - 1, -1, -1):
        if dd.iloc[i] == 0:
            start = dd.index[i]
            break
    cur_dur = None
    if start is not None and len(dd) and dd.iloc[-1] < 0:
        cur_dur = int(dd.index[-1] - start)
    # 最大回撤段：找到最大回撤谷底，回溯起点
    trough = dd.idxmin()
    if pd.isna(trough):
        return {"max_dd_pct": np.nan, "current_dd_pct": np.nan,
                "current_dd_steps": None, "max_dd_trough": None, "max_dd_recovered": None}
    seg = dd.loc[:trough]
    peak_idx = seg.idxmax()
    after = dd.loc[trough:]
    recover_idx = after[after >= 0].index.min() if (after >= 0).any() else None
    ret = {
        "max_dd_pct": float(max_dd),
        "current_dd_pct": float(cur_dd),
        "current_dd_steps": cur_dur,
        "max_dd_trough": int(trough),
        "max_dd_duration_steps": int(trough - peak_idx),
        "max_dd_recovered": int(recover_idx) if recover_idx is not None else None,
        "max_dd_recovery_steps": int(recover_idx - trough) if recover_idx is not None else None,
    }
    return ret


def load_equity(acct: str) -> pd.Series | None:
    p = REPORTS / f"paper_equity_{acct}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    if df.empty or "equity" not in df.columns:
        return None
    eq = pd.to_numeric(df["equity"], errors="coerce").dropna().reset_index(drop=True)
    return eq


def main() -> int:
    fig, axes = plt.subplots(len(ACCOUNTS), 1, figsize=(12, 2.2 * len(ACCOUNTS)), dpi=110,
                             sharex=True)
    if len(ACCOUNTS) == 1:
        axes = [axes]
    lines = ["# 纸面账户回撤统计（200）\n", f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n",
             "| 账户 | 最大回撤 | 回撤谷底(步) | 回撤时长(步) | 恢复步 | 恢复耗时(步) | 当前回撤 | 当前回撤步数 |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for ax, (acct, name) in zip(axes, ACCOUNTS.items()):
        eq = load_equity(acct)
        if eq is None or len(eq) < 2:
            lines.append(f"| {acct} {name} | - | - | - | - | - | - | - |")
            ax.set_title(f"账户 {acct}（{name}）：无数据")
            ax.axis("off")
            continue
        dd = drawdown_series(eq)
        st = drawdown_stats(eq)
        ax.fill_between(dd.index, dd.to_numpy(), 0, color="#c5604a", alpha=0.55, linewidth=0)
        ax.plot(dd.index, dd.to_numpy(), color="#c5604a", linewidth=0.9)
        ax.axhline(0, color="#8a8678", linewidth=0.6)
        ax.set_title(f"账户 {acct}（{name}）水下曲线 · 最大回撤 {st['max_dd_pct']:.1f}% · "
                     f"当前 {st['current_dd_pct']:.1f}%", fontsize=9)
        ax.grid(alpha=0.25)
        lines.append(f"| {acct} {name} | {st['max_dd_pct']:.1f}% | {st['max_dd_trough']} | "
                     f"{st['max_dd_duration_steps']} | {st['max_dd_recovered'] if st['max_dd_recovered'] is not None else '-'} | "
                     f"{st['max_dd_recovery_steps'] if st['max_dd_recovered'] is not None else '-'} | "
                     f"{st['current_dd_pct']:.1f}% | {st['current_dd_steps'] or '-'} |")
        print(f"[200] 账户 {acct}: 最大回撤 {st['max_dd_pct']:.1f}%（步 {st['max_dd_trough']}）"
              f"当前 {st['current_dd_pct']:.1f}%")
    fig.tight_layout()
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG)
    plt.close(fig)
    lines.append("\n- 口径：equity/历史峰值−1；恢复 = 水下回到 0。A/B/C 事件流短（≤5 笔），回撤数字随积累变化。")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PNG} + {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
