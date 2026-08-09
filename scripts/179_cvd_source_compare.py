r"""179_cvd_source_compare.py — B1：真 CVD（coinglass cvd 目录）vs 近似 CVD（klines taker）对比。

背景：wash_cvd 信号用近似 CVD = cumsum(2*taker_buy_qv − qv)（klines，USD 量纲）。
coinglass 有真 cvd 目录（cum_vol_delta，币量纲）但 scout 标记从未使用。
对比窗口受限：真 cvd 仅覆盖 2025-09-20 → 2026-05-28（约 8 个月，120 币）。

检验：
1. 两序列相关性（标准化后，同 symbol 同窗口）
2. wash_cvd 事件重叠率：近似 CVD 检出 vs 真 CVD 检出（同事件定义）
3. 事件 168h 超额一致性（窗口内，2025 弱化期，方向参考）

输出：reports/cvd_source_compare.md
用法：python scripts/179_cvd_source_compare.py
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

REPORT = PROJECT_ROOT / "reports" / "cvd_source_compare.md"
CVD_DIR = m113.COINGLASS_RAW1H / "cvd"
LO_MS = int(pd.Timestamp("2025-09-20", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-05-28", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 20
SEED = 2026


def build_both_cvd(sym: str) -> pd.DataFrame | None:
    """同轴对齐：近似 CVD z 与真 CVD z（各自标准化后，量纲无关）。"""
    cvd_p = CVD_DIR / f"{sym}.parquet"
    kl_p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
    if not cvd_p.exists() or not kl_p.exists():
        return None
    cd = pd.read_parquet(cvd_p)
    if not {"time", "cum_vol_delta"}.issubset(cd.columns):
        return None
    kd = pd.read_parquet(kl_p)
    if not {"open_time", "quote_volume", "taker_buy_quote_volume"}.issubset(kd.columns):
        return None
    # 真 CVD
    cts = pd.to_numeric(cd["time"], errors="coerce").to_numpy(dtype=np.int64)
    ccvd = pd.to_numeric(cd["cum_vol_delta"], errors="coerce").to_numpy(dtype=float)
    real = pd.Series(ccvd, index=pd.Index(cts))
    real = real[~real.index.duplicated(keep="last")].sort_index()
    # 近似 CVD（klines，USD）
    kts = pd.to_numeric(kd["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    qv = pd.to_numeric(kd["quote_volume"], errors="coerce").to_numpy(dtype=float)
    tb = pd.to_numeric(kd["taker_buy_quote_volume"], errors="coerce").to_numpy(dtype=float)
    flow = pd.Series(2 * tb - qv, index=pd.Index(kts))
    flow = flow[~flow.index.duplicated(keep="last")].sort_index()
    approx = flow.cumsum()
    # 对齐共同轴
    common = real.index.intersection(approx.index)
    if len(common) < 500:
        return None
    out = pd.DataFrame({"real": real.reindex(common), "approx": approx.reindex(common)}).dropna()
    if len(out) < 500:
        return None
    # 标准化（z，滚动 720h）→ 可比
    out["real_z"] = (out["real"] - out["real"].rolling(720, min_periods=360).mean()) / \
        out["real"].rolling(720, min_periods=360).std().replace(0, np.nan)
    out["approx_z"] = (out["approx"] - out["approx"].rolling(720, min_periods=360).mean()) / \
        out["approx"].rolling(720, min_periods=360).std().replace(0, np.nan)
    return out


def main() -> int:
    symbols = m113.load_universe_symbols()
    rows = []
    ev_real_all: list[pd.DataFrame] = []
    ev_approx_all: list[pd.DataFrame] = []
    ctxs = m113.load_price_ctx(symbols)
    for sym in symbols:
        df = build_both_cvd(sym)
        if df is None or sym not in ctxs:
            continue
        corr = df[["real_z", "approx_z"]].corr().iloc[0, 1]
        rows.append({"symbol": sym, "n": len(df), "corr_z": corr})
        # 事件检测（cvd_divergence 用各自 z）
        axis = df.index.to_numpy(dtype=np.int64)
        close = ctxs[sym]["close"].reindex(pd.Index(axis)).to_numpy(dtype=float)
        s = pd.Series(close)
        pz = (s - s.rolling(720, min_periods=360).mean()) / s.rolling(720, min_periods=360).std().replace(0, np.nan)
        ret24 = s.pct_change(24) * 100.0
        for name, cvd_z_col in [("real", "real_z"), ("approx", "approx_z")]:
            div = pz.to_numpy() - df[cvd_z_col].to_numpy()
            fired = np.isfinite(pz.to_numpy()) & np.isfinite(div) & \
                ((pz.to_numpy() < -2.0) | (ret24.to_numpy() < -8.0)) & (div > 2.0)
            events = []
            last = -10**18
            for i in np.flatnonzero(fired):
                t = int(axis[i])
                if t - last >= 72 * 3_600_000:
                    events.append(t)
                    last = t
            ev_df = pd.DataFrame({"symbol": sym, "timestamp": events})
            if name == "real":
                ev_real_all.append(ev_df)
            else:
                ev_approx_all.append(ev_df)
    corr_df = pd.DataFrame(rows)
    print(f"可比 symbol {len(corr_df)} | z 相关中位 {corr_df['corr_z'].median():.3f}")

    def fwd(ev_list):
        ev = pd.concat(ev_list, ignore_index=True)
        ev = ev[(ev["timestamp"] >= LO_MS) & (ev["timestamp"] <= HI_MS)].copy()
        parts = []
        for sym, g in ev.groupby("symbol", sort=False):
            if sym in ctxs:
                parts.append(forward_stats(ctxs[sym], g.copy(), DEFAULT_HORIZONS))
        return pd.concat(parts, ignore_index=True) if parts else ev

    ev_real = fwd(ev_real_all)
    ev_approx = fwd(ev_approx_all)
    # 事件重叠：同 symbol ±4h 内
    real_set = set(zip(ev_real["symbol"], ev_real["timestamp"] // (8 * 3_600_000)))
    approx_set = set(zip(ev_approx["symbol"], ev_approx["timestamp"] // (8 * 3_600_000)))
    overlap = len(real_set & approx_set)
    print(f"事件：真 CVD {len(real_set)} | 近似 {len(approx_set)} | 重叠 {overlap} "
          f"({100 * overlap / max(len(real_set), 1):.0f}% 真侧)")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, 2000, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# 真 CVD vs 近似 CVD 对比（179，B1）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 窗口：2025-09-20 → 2026-05-28（真 cvd 目录覆盖，约 8 个月）",
             f"- 可比 symbol：{len(corr_df)}；z 序列相关中位 {corr_df['corr_z'].median():.3f}",
             f"- ⚠️ 窗口处于 2025 弱化期，超额仅作方向参考；重点是事件一致性\n",
             "| CVD 源 | 事件 n（8h 桶唯一） | 168h 均值 | 超额 | CI |",
             "|---|---:|---:|---:|---|"]

    for label, ev in [("真 CVD", ev_real), ("近似 CVD", ev_approx)]:
        r = pd.to_numeric(ev["ret_168h"], errors="coerce").dropna().to_numpy()
        if len(r) >= MIN_EVENTS:
            ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
            lines.append(f"| {label} | {len(real_set) if label == '真 CVD' else len(approx_set)} "
                         f"| {r.mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                         f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] |")
        else:
            lines.append(f"| {label} | {len(real_set) if label == '真 CVD' else len(approx_set)} | 样本不足 | - | - |")
    lines.append(f"\n- 事件重叠率：{100 * overlap / max(len(real_set), 1):.0f}%（真 CVD 侧，8h 桶容忍）\n")
    lines.extend(["## 解读\n",
                  "- z 相关 > 0.8 且事件重叠 > 70% → 近似 CVD 与真 CVD 信号等价（wash_cvd 稳健于 CVD 构造）。",
                  "- 相关低/重叠低 → 近似 CVD 有系统性偏差（taker 近似漏单），信号需用真 CVD 复核。",
                  "- 注意量纲差异（币 vs USD）已用 z 标准化消除；窗口限制是真 CVD 数据覆盖所致。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
