r"""161_positioning_divergence.py — 仓位分歧层：聪明钱×散户分歧作为 wash_cvd 确认层。

交叉验证来源：gpt 方案 A + scout 未利用维度 Top1-3（ls_top_trader/ls_global/
net_position，research_frontier 标 P0"立即可测"）。

假设（E-C 信息锚）：wash_cvd 事件时点若【聪明钱（top trader）做多 + 散户（global）
做空】分歧大 → 反弹更强（聪明钱提前布局）；反向分歧 → 反弹弱。

特征（事件时点 asof，无前视）：
- div = top_position_long_percent − global_account_long_percent（聪明钱-散户多头占比差）
- np_turn = net_position_change_cum 的 30d z-score（大户净持仓拐头）

窗口：2024-06→2026-05（ls/net_position 数据覆盖，~2 年）。
事件：wash_cvd（115）；基线：同期随机横截面；168h 超额 + 中位数。
分层：div 高（>q67）/ 中 / 低（<q33）；np_turn 高/低。

输出：reports/positioning_divergence.md
用法：python scripts/161_positioning_divergence.py
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

REPORT = PROJECT_ROOT / "reports" / "positioning_divergence.md"
RAW = m113.COINGLASS_RAW1H
LO_MS = int(pd.Timestamp("2024-06-06", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-05-31", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026


def add_positioning(ctxs: dict[str, pd.DataFrame]) -> None:
    """每 ctx 补 div（聪明钱-散户多头占比差）与 np_z（净持仓 30d z）。"""
    for sym, t in ctxs.items():
        t["div"] = np.nan
        t["np_z"] = np.nan
        lp = RAW / "ls_top_trader" / f"{sym}.parquet"
        gp = RAW / "ls_global" / f"{sym}.parquet"
        np_p = RAW / "net_position" / f"{sym}.parquet"
        axis = t.index.to_numpy(dtype=np.int64)
        if lp.exists() and gp.exists():
            try:
                l = pd.read_parquet(lp)
                g = pd.read_parquet(gp)
                lts = pd.to_numeric(l["time"], errors="coerce").to_numpy(dtype=np.int64)
                lv = pd.to_numeric(l["top_position_long_percent"], errors="coerce").to_numpy(dtype=float)
                gts = pd.to_numeric(g["time"], errors="coerce").to_numpy(dtype=np.int64)
                gv = pd.to_numeric(g["global_account_long_percent"], errors="coerce").to_numpy(dtype=float)
                ls = pd.Series(lv, index=pd.Index(lts))
                ls = ls[~ls.index.duplicated(keep="last")].sort_index().reindex(axis)
                gs = pd.Series(gv, index=pd.Index(gts))
                gs = gs[~gs.index.duplicated(keep="last")].sort_index().reindex(axis)
                t["div"] = (ls - gs).to_numpy()
            except Exception:
                pass
        if np_p.exists():
            try:
                n = pd.read_parquet(np_p)
                nts = pd.to_numeric(n["time"], errors="coerce").to_numpy(dtype=np.int64)
                nv = pd.to_numeric(n["net_position_change_cum"], errors="coerce").to_numpy(dtype=float)
                ns = pd.Series(nv, index=pd.Index(nts))
                ns = ns[~ns.index.duplicated(keep="last")].sort_index().reindex(axis)
                t["np_z"] = m113.rolling_z(ns, 720).to_numpy()
            except Exception:
                pass


def attach_asof(ctxs: dict[str, pd.DataFrame], events: pd.DataFrame,
                cols: list[str]) -> pd.DataFrame:
    ev = events.copy()
    for c in cols:
        ev[f"{c}_at"] = np.nan
    for sym, g in ev.groupby("symbol", sort=False):
        if sym not in ctxs:
            continue
        t = ctxs[sym]
        idx = t.index.to_numpy(dtype=np.int64)
        pos = np.searchsorted(idx, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(idx) - 1)
        for c in cols:
            vals = pd.to_numeric(t[c], errors="coerce").to_numpy(dtype=float)
            ev.loc[g.index, f"{c}_at"] = vals[pos]
    return ev


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    add_positioning(ctxs)
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
    events = attach_asof(ctxs, events, ["div", "np_z"])
    usable = events[events["div_at"].notna()].copy()
    print(f"wash_cvd {len(events)} | 有 div {len(usable)}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# 仓位分歧层：聪明钱×散户分歧 × wash_cvd（161）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 数据：ls_top_trader/ls_global/net_position（2024-06→2026-05，~2 年窗，scout 确认未用维度）",
             "- div = top_long% − global_long%（聪明钱−散户多头占比）；np_z = 净持仓 30d z",
             "- 事件：wash_cvd（115）；基线：随机横截面；168h 超额 + 中位数\n",
             "| 层 | n | 168h 超额 | CI | 中位数 | 尾切 | 判定 |",
             "|---|---|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | 无事件 |")
            return
        r = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().to_numpy()
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        thr = np.quantile(r, 0.95)
        tail = r[r <= thr].mean()
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% "
                     f"| {tail:+.2f}% | **{verdict}** |")
        print(f"[161] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    row("wash_cvd 全（窗口锚）", usable)
    q67 = usable["div_at"].quantile(0.67)
    q33 = usable["div_at"].quantile(0.33)
    row("×聪明钱多头分歧（div>q67）", usable[usable["div_at"] > q67])
    row("×分歧中性", usable[(usable["div_at"] >= q33) & (usable["div_at"] <= q67)])
    row("×散户多头分歧（div<q33）", usable[usable["div_at"] < q33])
    nu = usable[usable["np_z_at"].notna()]
    if len(nu):
        row("×净持仓拐头（np_z>1）", nu[nu["np_z_at"] > 1])
        row("×净持仓背离（np_z<-1）", nu[nu["np_z_at"] < -1])

    lines.extend(["\n## 解读\n",
                   "- 聪明钱多头分歧层显著更强 → 信息锚成立：wash_cvd + 聪明钱确认 = 更强反弹（s012 候选）。",
                   "- 无差异 → 仓位分歧已被价格吸收，该维度不提供增量。",
                   "- 注意 2 年窗（2024-06→2026-05）与 2025 弱化语境，需独立窗口复核。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
