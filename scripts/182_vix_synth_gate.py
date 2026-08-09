r"""182_vix_synth_gate.py — VIX_SYNTH 门控复核（181 B4 发现的独立验证）。

181 发现：VIX_SYNTH 高波动环境 wash_cvd 168h +4.26% GO_LONG vs 低 -1.63% GO_SHORT。
本脚本复核（门槛 G）：
1. 独立窗口（2022-23 vs 2024-26）
2. 尾部切除
3. 阈值敏感性（中位数切 vs q33/q67）
4. 与 123 VIX q75 门控的信息重叠（VIX_SYNTH vs VIX 相关性 + 双门控 vs 单门控）

判定：VIX_SYNTH 高门控稳健 → s001 门控增强候选（E24）；与 VIX 冗余 → 合并管理。

输出：reports/vix_synth_gate.md
用法：python scripts/182_vix_synth_gate.py
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec)
sys.modules["m113"] = m113
_spec.loader.exec_module(m113)
_spec2 = importlib.util.spec_from_file_location(
    "m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2)
sys.modules["m115"] = m115
_spec2.loader.exec_module(m115)

from harness.lib.event_study import (  # noqa: E402
    DEFAULT_HORIZONS,
    bootstrap_ci,
    draw_random_events,
    forward_stats,
)

REPORT = PROJECT_ROOT / "reports" / "vix_synth_gate.md"
MACRO = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    fundings = m113.load_funding_series(symbols)
    ev_parts = []
    for sym, ctx in ctxs.items():
        ev = m115.detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)].copy()
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        if sym in ctxs:
            fwd_parts.append(forward_stats(ctxs[sym], g.copy(), DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events

    ev_day = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_localize(None).normalize()
    # VIX_SYNTH + VIX（123 对照）
    for fname, col in [("VIX_SYNTH.parquet", "vsyn"), ("VIX.parquet", "vix")]:
        p = MACRO / fname
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        s = pd.Series(pd.to_numeric(d["close"], errors="coerce").to_numpy(),
                      index=pd.to_datetime(d.index) if not isinstance(d.index, pd.DatetimeIndex) else d.index).dropna()
        events[col] = ev_day.map(s).to_numpy()
    usable = events[events["vsyn"].notna()].copy()
    # 两序列相关（共同日）
    if "vix" in usable.columns:
        common = usable[["vsyn", "vix"]].dropna()
        corr = common["vsyn"].corr(common["vix"])
    else:
        corr = np.nan
    print(f"事件 {len(events)} | 有 VIX_SYNTH {len(usable)} | vsyn-vix 相关 {corr:.2f}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# VIX_SYNTH 门控复核（182，181 发现验证）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- VIX_SYNTH × VIX 相关：{corr:.2f}（123 门控信息重叠检查）\n",
             "| 组 | n | 168h 超额 | CI | 中位数 | 尾切 | W1(22-23) | W2(24-26) | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n < MIN_EVENTS:
            lines.append(f"| {label} | {n} | - | - | - | - | - | - | 样本不足 |")
            print(f"[182] {label}: n={n} 样本不足")
            return
        r = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().to_numpy()
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        thr = np.quantile(r, 0.95)
        tail = r[r <= thr].mean()
        split = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)
        w1 = r[g["timestamp"].to_numpy() < split]
        w2 = r[g["timestamp"].to_numpy() >= split]
        w1s = f"{w1.mean():+.2f}%({len(w1)})" if len(w1) >= 10 else "n<10"
        w2s = f"{w2.mean():+.2f}%({len(w2)})" if len(w2) >= 10 else "n<10"
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% "
                     f"| {tail:+.2f}% | {w1s} | {w2s} | **{verdict}** |")
        print(f"[182] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    med = usable["vsyn"].median()
    q67, q33 = usable["vsyn"].quantile([0.67, 0.33])
    row("VIX_SYNTH 高（≥中位）", usable[usable["vsyn"] >= med])
    row("VIX_SYNTH 低（<中位）", usable[usable["vsyn"] < med])
    row("高（≥q67）", usable[usable["vsyn"] >= q67])
    row("低（<q33）", usable[usable["vsyn"] < q33])

    lines.extend(["\n## 解读\n",
                  "- 高组 CI 显著 + 独立窗口同号 + 尾切仍正 → VIX_SYNTH 高门控稳健（E24 候选）。",
                  "- vsyn-vix 相关高（>0.7）→ 与 123 VIX 门控冗余，合并管理；低相关 → 独立信息。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
