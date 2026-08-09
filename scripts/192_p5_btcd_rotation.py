r"""192_p5_btcd_rotation.py — P5：BTC 主导率（BTC.D）断裂 → 山寨轮动。

2025 弱化 H2：山寨 beta 回流失效（BTC.D 上升）。假设：BTC.D（成交额占比代理）的
结构变化（见顶回落 / 持续上升）调制山寨篮子相对收益——BTC.D 回落期山寨轮动走强。

BTC.D 代理 = BTC 24h 成交额 / 全 pool 24h 成交额（klines quote_volume，非市值，诚实标注）。
事件：BTC.D 的 30d 滚动 z-score 断裂（>+1 高位 / <-1 低位）。
观察：山寨等权篮子（去 BTC）未来 7 天超额 vs BTC。
输出：reports/p5_btcd_rotation.md
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

from harness.lib.event_study import bootstrap_ci  # noqa: E402

REPORT = PROJECT_ROOT / "reports" / "p5_btcd_rotation.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 20
SEED = 2026
COOLDOWN = 10  # 天


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    # BTC.D 代理：日度成交额占比
    btc_qv = {}
    pool_qv = {}
    for sym, ctx in ctxs.items():
        p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
        if not p.exists():
            continue
        kdf = pd.read_parquet(p, columns=["open_time", "quote_volume"])
        kts = pd.to_numeric(kdf["open_time"], errors="coerce").to_numpy(dtype=np.int64)
        kqv = pd.to_numeric(kdf["quote_volume"], errors="coerce").to_numpy(dtype=float)
        day = pd.to_datetime(kts, unit="ms", utc=True).tz_localize(None).normalize()
        s = pd.Series(kqv, index=day)
        s = s[~s.index.duplicated(keep="last")].sort_index()
        daily = s.groupby(s.index).sum()
        pool_qv[sym] = daily
    p_btc = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    kdf = pd.read_parquet(p_btc, columns=["open_time", "quote_volume"])
    kts = pd.to_numeric(kdf["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    kqv = pd.to_numeric(kdf["quote_volume"], errors="coerce").to_numpy(dtype=float)
    day = pd.to_datetime(kts, unit="ms", utc=True).tz_localize(None).normalize()
    s = pd.Series(kqv, index=day)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    btc_daily = s.groupby(s.index).sum()
    pool_total = pd.concat(pool_qv.values(), axis=1).sum(axis=1)
    btcd = btc_daily / pool_total.replace(0, np.nan)
    btcd = btcd.dropna()
    z30 = (btcd - btcd.rolling(30).mean()) / btcd.rolling(30).std().replace(0, np.nan)
    print(f"BTC.D 代理（成交额占比）{len(btcd)} 天 | 中位 {btcd.median():.2%} | 近期 {btcd.iloc[-1]:.2%}")

    # 事件：z30 高位（>1）vs 低位（<-1），10 天冷却
    def events_for(mask: np.ndarray) -> list[int]:
        ev = []
        last = None
        for i, m in enumerate(mask):
            if m and (last is None or i - last >= COOLDOWN):
                ev.append(i)
                last = i
        return ev

    hi_idx = events_for((z30 > 1.0).to_numpy())
    lo_idx = events_for((z30 < -1.0).to_numpy())

    # 山寨篮子（去 BTC）7 天收益 - 用价格 close
    closes_daily = {}
    for sym, ctx in ctxs.items():
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        s = pd.Series(close, index=pd.to_datetime(axis, unit="ms", utc=True).tz_localize(None).normalize())
        s = s[~s.index.duplicated(keep="last")].sort_index()
        closes_daily[sym] = s.groupby(s.index).last()
    btc_close = closes_daily.get("BTCUSDT")

    def basket_excess(ev_idx: list[int]) -> np.ndarray:
        out = []
        for i in ev_idx:
            t0 = btcd.index[i]
            rs = []
            for sym, daily in closes_daily.items():
                if sym == "BTCUSDT":
                    continue
                i0 = daily.index.searchsorted(t0)
                i1 = daily.index.searchsorted(t0 + pd.Timedelta(days=7))
                if i1 >= len(daily) or i1 <= i0 or i0 < 0:
                    continue
                r = daily.iloc[i1] / daily.iloc[i0] - 1
                if np.isfinite(r):
                    rs.append(r)
            if len(rs) >= 10:
                out.append(np.mean(rs))
        return np.array(out)

    def btc_excess(ev_idx: list[int]) -> np.ndarray:
        out = []
        if btc_close is None:
            return np.array([])
        for i in ev_idx:
            t0 = btcd.index[i]
            i0 = btc_close.index.searchsorted(t0)
            i1 = btc_close.index.searchsorted(t0 + pd.Timedelta(days=7))
            if i1 >= len(btc_close) or i1 <= i0 or i0 < 0:
                continue
            r = btc_close.iloc[i1] / btc_close.iloc[i0] - 1
            if np.isfinite(r):
                out.append(r)
        return np.array(out)

    hi_b = np.array(basket_excess(hi_idx))
    lo_b = np.array(basket_excess(lo_idx))
    print(f"BTC.D 高位事件 {len(hi_idx)}（篮子 {len(hi_b)}）| 低位事件 {len(lo_idx)}（篮子 {len(lo_b)}）")

    lines = ["# P5：BTC.D 断裂 → 山寨轮动（192）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             "- BTC.D 代理 = BTC 成交额/全 pool 成交额（非市值，诚实标注）",
             f"- 事件：30d z>+1（高位）/ z<-1（低位），{COOLDOWN} 天冷却",
             "- 观察：山寨等权篮子（去 BTC）未来 7 天收益\n",
             "| 事件 | n | 山寨篮子 7d 均值 | 篮子中位 | 判定参考 |",
             "|---|---|---:|---:|---|"]
    for label, b, n_ev in [("BTC.D 高位（主导率飙升后）", hi_b, len(hi_idx)),
                           ("BTC.D 低位（主导率回落）", lo_b, len(lo_idx))]:
        if len(b) < MIN_EVENTS:
            lines.append(f"| {label} | {n_ev} | - | - | 样本不足 |")
            continue
        lines.append(f"| {label} | {n_ev} | {b.mean() * 100:+.2f}% | {np.median(b) * 100:+.2f}% | |")
        print(f"[192] {label}: n={n_ev} 篮子7d {b.mean() * 100:+.2f}% 中位 {np.median(b) * 100:+.2f}%")

    # BTC.D 高位 vs 低位直接对照（山寨篮子）
    if len(hi_b) >= MIN_EVENTS and len(lo_b) >= MIN_EVENTS:
        ci = bootstrap_ci(hi_b, lo_b, n_boot=1000, alpha=0.05, seed=SEED)
        lines.append(f"\n直接对照（低位 − 高位）：{ci['mean_diff'] * 100:+.2f}% "
                     f"CI[{ci['ci_lo'] * 100:+.2f}, {ci['ci_hi'] * 100:+.2f}]"
                     f"（{'显著' if ci['ci_lo'] > 0 else '不显著'}）")
        print(f"[192] 低位−高位: {ci['mean_diff'] * 100:+.2f}%")

    lines.extend(["\n## 解读\n",
                  "- BTC.D 低位后山寨篮子显著强于高位 → 主导率断裂调制轮动（s020 候选）。",
                  "- 无差异 → BTC.D 不调制山寨相对收益（2025 弱化另有原因）。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
