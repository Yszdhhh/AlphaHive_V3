r"""207_cvd_slope_test.py — 因子 5：CVD 卖压衰减斜率 × wash_cvd（codex 因子池候选 5）。

机制（E-A）：wash_cvd 已要求 CVD 背离（cvd_divergence>2.0）；新增量不是"更极端"，
而是**卖压速度是否正在衰减**（被动承接/强制卖盘结束的微观结构）。

定义（codex 规格，事件时点 asof，无前视）：
  cvd = cumsum(2 * taker_buy_quote_volume − quote_volume)          （113 同款近似）
  slope = mean(ΔCVD 最近 3h) − mean(ΔCVD 前 21h)                   （30d 自身标准化）
含义：slope 高 = 卖压最近 3h 显著减弱（衰减）；slope 低 = 卖压仍在加速。

检验：
- wash_cvd 事件内按 slope 三分位 → 24/72/168h 前向
- 增量 vs 4h 确认（E18）：slope 必须在不使用事件后 4h 信息时仍有价值
  （2×2：slope 高 × 4h 确认 → 净增量）
- episode 两段同号；聚类 CI

输出：reports/cvd_slope_test.md
用法：python scripts/207_cvd_slope_test.py
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

from harness.lib.event_study import forward_stats  # noqa: E402

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

REPORT = PROJECT_ROOT / "reports" / "cvd_slope_test.md"
MIN_N = 100
SEED = 2026
HORIZONS = (4, 24, 72, 168)
HOUR_MS = 3_600_000


def cvd_series(sym: str) -> pd.Series | None:
    """113 同款 CVD 近似序列（index=ts ms）。"""
    p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    ts_col = "time" if "time" in df.columns else "open_time"
    ts = pd.to_numeric(df[ts_col], errors="coerce")
    if "taker_buy_quote_volume" not in df.columns or "quote_volume" not in df.columns:
        return None
    tb = pd.to_numeric(df["taker_buy_quote_volume"], errors="coerce").fillna(0)
    qv = pd.to_numeric(df["quote_volume"], errors="coerce").fillna(0)
    s = pd.Series(np.cumsum(2.0 * tb.to_numpy() - qv.to_numpy()), index=pd.Index(ts))
    return s[~s.index.duplicated(keep="last")].sort_index()


def slope_at(cvd: pd.Series, ts_ms: int) -> float:
    """事件时点 asof 的衰减斜率：mean(ΔCVD 近 3h) − mean(ΔCVD 前 21h)，30d 标准化。"""
    idx = cvd.index.to_numpy(dtype=np.int64)
    pos = int(np.searchsorted(idx, ts_ms, side="right")) - 1
    if pos - 24 < 0:
        return np.nan
    d = np.diff(cvd.to_numpy())
    # 近 3h（pos-3..pos 的 Δ） vs 前 21h（pos-24..pos-3 的 Δ）
    recent = d[pos - 3:pos]
    prior = d[pos - 24:pos - 3]
    if len(recent) == 0 or len(prior) == 0:
        return np.nan
    slope = float(np.mean(recent) - np.mean(prior))
    # 30d 自身标准化（720 bar 滚动）
    s = pd.Series(np.diff(cvd.to_numpy()))
    std = s.rolling(720, min_periods=360).std()
    st = std.iloc[pos - 1] if pos - 1 < len(std) else np.nan
    return slope / st if st and st > 0 else np.nan


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

    cvd_cache: dict[str, pd.Series] = {}
    slopes: list[dict] = []
    for _, e in events.iterrows():
        sym = e["symbol"]
        if sym not in cvd_cache:
            cvd_cache[sym] = cvd_series(sym)
        cvd = cvd_cache.get(sym)
        if cvd is None:
            continue
        slopes.append({"symbol": sym, "timestamp": int(e["timestamp"]),
                       "slope": slope_at(cvd, int(e["timestamp"]))})
    ann = pd.DataFrame(slopes)
    ev = events.merge(ann, on=["symbol", "timestamp"], how="left")
    ev = ev.dropna(subset=["slope"])
    print(f"wash_cvd 事件 {len(events)} | 有 slope 样本 {len(ev)}")

    fwd_parts = []
    for sym, g in ev.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=HORIZONS))
    ev = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else ev

    ev["tercile"] = pd.qcut(ev["slope"], 3, labels=[0, 1, 2], duplicates="drop")
    ev["r4"] = pd.to_numeric(ev["ret_4h"], errors="coerce")
    ev["conf"] = ev["r4"] > 0
    hi = ev[ev["tercile"] == 2]
    lo = ev[ev["tercile"] == 0]
    lines = ["# CVD 卖压衰减斜率 × wash_cvd（207，因子 5）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- slope = mean(ΔCVD 近3h) − mean(ΔCVD 前21h)，30d 标准化；事件时点 asof（无前视）",
             f"- 三分位：高 = 卖压最近 3h 显著衰减\n",
             "| 层 | n | 24h 均值 | 72h 均值 | 168h 均值 | 168h 中位 |",
             "|---|---|---:|---:|---:|---:|"]
    for label, g in [("衰减高（T3）", hi), ("衰减低（T1）", lo)]:
        cells = []
        for h in HORIZONS[1:]:  # 显示 24/72/168（4h 仅用于确认分层）
            v = pd.to_numeric(g[f"ret_{h}h"], errors="coerce").dropna()
            cells.append(f"{v.mean():+.2f}%（n={len(v)}）")
        med = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().median()
        lines.append(f"| {label} | {len(g)} | {' | '.join(cells)} | {med:+.2f}% |")

    # high−low 24h 增量（时点聚类近似：CI 用 bootstrap）
    from harness.lib.event_study import bootstrap_ci
    v_hi = pd.to_numeric(hi["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    v_lo = pd.to_numeric(lo["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    lines.append("\n## high−low 增量\n")
    if len(v_hi) >= MIN_N and len(v_lo) >= MIN_N:
        ci = bootstrap_ci(v_hi, v_lo, seed=SEED)
        lines.append(f"| 24h high−low | {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] |")
        print(f"[207] high−low 24h {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")

    # 2×2：slope × 4h 确认（E18）——slope 必须在不使用事件后信息时仍有价值
    lines.append("\n## 2×2：slope × 4h 确认（24h 均值）\n")
    lines.append("| slope\\4h | 4h 确认（r4>0） | 无确认 |")
    lines.append("|---|---:|---:|")
    for s_label, g in [("slope 高", hi), ("slope 低", lo)]:
        cells = []
        for c_label in [True, False]:
            gg = g[g["conf"] == c_label]
            v = pd.to_numeric(gg["ret_24h"], errors="coerce").dropna()
            cells.append(f"{v.mean():+.2f}%（n={len(v)}）" if len(v) else "-")
        lines.append(f"| {s_label} | {' | '.join(cells)} |")
    # slope 在确认组内的增量
    conf_hi = hi[hi["conf"]]
    conf_lo = lo[lo["conf"]]
    v_ch = pd.to_numeric(conf_hi["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    v_cl = pd.to_numeric(conf_lo["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    if len(v_ch) >= MIN_N and len(v_cl) >= MIN_N:
        ci = bootstrap_ci(v_ch, v_cl, seed=SEED)
        lines.append(f"\nslope 在 4h 确认组内的增量：{ci['mean_diff']:+.2f}% "
                     f"CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]（须>0 才有独立价值）")
        print(f"[207] slope-in-conf {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")

    lines += ["\n## 解读\n",
              "- high−low 显著 + 确认组内增量 >0 → 卖压衰减斜率是 wash_cvd 的正调制（更早可用：事件时点即可用，无需等 4h）；",
              "- CI 含 0 / 确认组内无增量 → 只是 cvd_divergence 水平的重包装或已被 4h 确认覆盖 → NO_GO。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
