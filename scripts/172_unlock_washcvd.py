r"""172_unlock_washcvd.py — B3 可预测流：代币解锁事件 × wash_cvd（Mobula 免费 API）。

假设（B3 可预测流/卖事实效应）：解锁事件（供给压力）日历可预注册——
- 解锁前 7 天（供给预期定价期）：wash_cvd 反弹弱（抛压悬顶）
- 解锁后 7 天（利空落地）：wash_cvd 反弹强（卖事实）

数据：Mobula 免费 API（demo-api.mobula.io，release_schedule：unlock_date ms + tokens_to_unlock）；
wash_cvd 事件（115）；klines（113 ctx）。
事件分层：wash_cvd 事件时点距最近解锁日天数 → 前 7 天 / 后 7 天 / 无窗口。
基线：随机横截面；168h 超额 + 中位数。

输出：reports/unlock_washcvd.md
用法：python scripts/172_unlock_washcvd.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import urllib.request
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

REPORT = PROJECT_ROOT / "reports" / "unlock_washcvd.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 20
N_BASELINE = 3000
SEED = 2026
WINDOW_DAYS = 7
MOBULA = "https://demo-api.mobula.io/api/1/metadata?asset={}"

# universe 常见币 → Mobula asset 名（人工映射，Mobula 按名查）
ASSET_MAP = {
    "SUIUSDT": "Sui", "ARBUSDT": "Arbitrum", "ENAUSDT": "Ethena",
    "ONDOUSDT": "Ondo", "PENDLEUSDT": "Pendle", "INJUSDT": "Injective",
    "TIAUSDT": "Celestia", "LINKUSDT": "Chainlink", "AAVEUSDT": "Aave",
    "UNIUSDT": "Uniswap", "RENDERUSDT": "Render", "GRASSUSDT": "Grass",
    "AVAXUSDT": "Avalanche", "DOGEUSDT": "Dogecoin", "POLUSDT": "Polygon",
    "OPUSDT": "Optimism", "ARBUSDT": "Arbitrum", "LDOUSDT": "Lido DAO",
    "CRVUSDT": "Curve DAO", "FILUSDT": "Filecoin", "ATOMUSDT": "Cosmos",
    "DOTUSDT": "Polkadot", "NEARUSDT": "NEAR Protocol", "APTUSDT": "Aptos",
}


def fetch_unlocks(asset: str) -> pd.DataFrame:
    """Mobula release_schedule → DataFrame(unlock_ms, tokens)。"""
    try:
        req = urllib.request.Request(MOBULA.format(asset), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
    except Exception:
        return pd.DataFrame()
    rs = d.get("data", {}).get("release_schedule")
    if not rs:
        return pd.DataFrame()
    return pd.DataFrame([{
        "unlock_ms": int(x["unlock_date"]),
        "tokens": float(x.get("tokens_to_unlock", 0)),
    } for x in rs if isinstance(x, dict) and x.get("unlock_date")])


def main() -> int:
    # 收集解锁日历（按 symbol）
    unlocks: dict[str, np.ndarray] = {}
    for sym, asset in ASSET_MAP.items():
        df = fetch_unlocks(asset)
        if len(df):
            unlocks[sym] = df["unlock_ms"].to_numpy(dtype=np.int64)
            print(f"[172] {sym}({asset}): {len(df)} 次解锁")
    if not unlocks:
        print("[172] 无解锁数据")
        return 0

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

    # 事件时点距最近解锁日天数
    def dist_to_unlock(sym: str, t: int) -> float | None:
        us = unlocks.get(sym)
        if us is None or len(us) == 0:
            return None
        # 事件前后的最近解锁（前 = 事件前最近，后 = 事件后最近）
        d = (us - t) / (24 * 3_600_000)
        before = d[d <= 0].max() if (d <= 0).any() else None   # 负 = 解锁在前
        after = d[d > 0].min() if (d > 0).any() else None      # 正 = 解锁在后
        return before, after

    events["unlock_before_d"] = np.nan
    events["unlock_after_d"] = np.nan
    for sym, g in events.groupby("symbol"):
        for idx, row in g.iterrows():
            r = dist_to_unlock(sym, int(row["timestamp"]))
            if r:
                events.at[idx, "unlock_before_d"] = r[0] if r[0] is not None else np.nan
                events.at[idx, "unlock_after_d"] = r[1] if r[1] is not None else np.nan
    usable = events[events["unlock_before_d"].notna() | events["unlock_after_d"].notna()].copy()
    print(f"wash_cvd {len(events)} | 有解锁上下文 {len(usable)}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# 代币解锁 × wash_cvd（172，B3 可预测流）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 解锁数据：Mobula 免费 API（{len(unlocks)} 币有 release_schedule）",
             "- 假设：解锁前 7 天（供给预期）wash_cvd 反弹弱；解锁后 7 天（利空落地）强",
             "- 基线：随机横截面；168h 超额 + 中位数\n",
             "| 组 | n | 168h 超额 | CI | 中位数 | 判定 |",
             "|---|---|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n < MIN_EVENTS:
            lines.append(f"| {label} | {n} | - | - | - | 样本不足 |")
            print(f"[172] {label}: n={n} 样本不足")
            return
        r = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().to_numpy()
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% | **{verdict}** |")
        print(f"[172] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    row("wash_cvd 全（有解锁上下文的池）", usable)
    pre = usable[usable["unlock_before_d"] >= -WINDOW_DAYS]
    post = usable[usable["unlock_after_d"] <= WINDOW_DAYS]
    row(f"解锁前 {WINDOW_DAYS} 天内", pre)
    row(f"解锁后 {WINDOW_DAYS} 天内", post)
    row("远离解锁（前>7d 且 后>7d）", usable[
        ((usable["unlock_before_d"].isna()) | (usable["unlock_before_d"] < -WINDOW_DAYS)) &
        ((usable["unlock_after_d"].isna()) | (usable["unlock_after_d"] > WINDOW_DAYS))])

    lines.extend(["\n## 解读\n",
                   "- 解锁后组显著强于远离组 → 卖事实效应成立（B3 可预测流 → s014 候选）。",
                   "- 解锁前组显著弱 → 供给预期压制（可作为负向过滤）。",
                   "- 无差异 → 解锁事件已被价格吸收（小币解锁频繁，市场已定价）。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
