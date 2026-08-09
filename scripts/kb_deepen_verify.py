"""方向深化验证（2026-08-09）：知识库方向 1（缠论底分型缩量）× 方向 2（ahr999 顶层开关）。

三级漏斗纪律：历史 development 只参考，不冻结不激活。
  A. 底分型缩量（4h，同月基线）：缠论 3K 底分型 + vol<0.6*MA20 → fwd24/72 超额
  B. ahr999 分桶 wash_cvd：ahr999=(P/MA200)*(P/10^(5.84log10(age)-17.01))（原文第十五章），
     wash_cvd 事件按抄底(<0.45)/定投(0.45-1.2)/起飞(1.2-5)/狂热(>5) 分桶 → 超额差异
  C. 正交性：wash_cvd 事件后 24h 内出现 4h 底分型缩量（洗盘结束确认）vs 无 → 是否增强
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location("m115", PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py")
m115 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m115)

load_universe_symbols = m115.load_universe_symbols
load_price_ctx = m115.load_price_ctx
detect_events = m115.detect_events
WASH_CVD = "wash_cvd"

BTCDAY_EPOCH = pd.Timestamp("2009-01-03", tz="UTC")
DAY_MS = 86_400_000


def ahr999_series(btc_daily: pd.DataFrame) -> pd.Series:
    """ahr999 = (P/MA200)*(P/10^(5.84*log10(age)-17.01))，age=距 2009-01-03 天数。"""
    ts = btc_daily["ts"].to_numpy()
    close = btc_daily["close"].to_numpy()
    ma200 = pd.Series(close).rolling(200, min_periods=100).mean().to_numpy()
    age_days = (ts - int(BTCDAY_EPOCH.value // 1_000_000) * 1000) / DAY_MS  # 注意: value 是 ns
    age_days = (pd.to_datetime(ts, unit="ms", utc=True) - BTCDAY_EPOCH).days.astype(float)
    growth = 10.0 ** (5.84 * np.log10(np.maximum(age_days, 1.0)) - 17.01)
    idx = pd.DatetimeIndex(pd.to_datetime(ts, unit="ms", utc=True)).normalize()
    return pd.Series((close / ma200) * (close / growth), index=idx)


def monthly_base(sym_fwd: list[tuple[str, pd.DataFrame]]) -> dict[str, float]:
    """同月基线：每月全体 bar fwd24 均值（跨 symbol 合并）。"""
    out: dict[str, list[float]] = {}
    for _, df in sym_fwd:
        m = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.strftime("%Y-%m")
        for mm, v in zip(m, df["fwd_24h"]):
            if np.isfinite(v):
                out.setdefault(mm, []).append(v)
    return {k: float(np.mean(v)) for k, v in out.items()}


def main() -> None:
    symbols = load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    print(f"universe {len(ctxs)} symbols loaded")

    # ---- B. ahr999 序列（BTC 日线，coinglass klines）----
    btc_path = None
    import glob
    for p in glob.glob(str(Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h\klines\BTCUSDT.parquet"))):
        btc_path = Path(p)
    if btc_path is None:
        print("BTCUSDT klines not found"); return
    b = pd.read_parquet(btc_path)
    btc = pd.DataFrame({
        "ts": pd.to_numeric(b["open_time"], errors="coerce"),
        "close": pd.to_numeric(b["close"], errors="coerce"),
    }).dropna().sort_values("ts")
    btc["day"] = (btc["ts"] // DAY_MS).astype("int64")
    btc_daily = btc.groupby("day").agg(ts=("ts", "first"), close=("close", "last")).reset_index()
    ahr = ahr999_series(btc_daily)
    print(f"ahr999: n={len(ahr)} range=[{ahr.min():.3f},{ahr.max():.3f}] "
          f"<0.45 占比 {(ahr < 0.45).mean():.1%} | 0.45-1.2 {(ahr.between(0.45, 1.2)).mean():.1%}")

    # ---- 事件（wash_cvd）+ 分型缩量（4h）----
    fwd_buckets: dict[str, list[float]] = {k: [] for k in ["<0.45 抄底", "0.45-1.2 定投", "1.2-5 起飞", ">5 狂热"]}
    bucket_events: dict[str, int] = {k: 0 for k in fwd_buckets}
    fx24: list[float] = []; fx72: list[float] = []; fx_month: list[str] = []
    fx_events = 0
    ortho_yes: list[float] = []; ortho_no: list[float] = []
    sym_fwd: list[tuple[str, pd.DataFrame]] = []

    for sym, ctx in ctxs.items():
        if ctx is None or len(ctx) < 500:
            continue
        # 4h 重采样做分型（直接读原始 klines 拿 OHLCV）
        raw = pd.read_parquet(Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h\klines") / f"{sym}.parquet")
        raw = pd.DataFrame({
            "ts": pd.to_numeric(raw["open_time"], errors="coerce"),
            "close": pd.to_numeric(raw["close"], errors="coerce"),
            "low": pd.to_numeric(raw["low"], errors="coerce"),
            "high": pd.to_numeric(raw["high"], errors="coerce"),
            "volume": pd.to_numeric(raw["volume"], errors="coerce"),
        }).dropna().sort_values("ts")
        raw4 = raw.set_axis(pd.to_datetime(raw["ts"], unit="ms", utc=True))
        c4 = raw4["close"].resample("4h").last().dropna()
        l4 = raw4["low"].resample("4h").min().dropna()
        h4 = raw4["high"].resample("4h").max().dropna()
        v4 = raw4["volume"].resample("4h").sum().dropna()
        # 事件坐标：ctx 是 1h index
        ev = detect_events(sym, ctx, None, WASH_CVD)
        if len(ev) == 0:
            continue
        c = ctx["close"].to_numpy()
        f24 = np.full(len(c), np.nan); f24[:-24] = c[24:] / c[:-24] - 1.0
        f72 = np.full(len(c), np.nan); f72[:-72] = c[72:] / c[:-72] - 1.0
        fwd = pd.DataFrame({"ts": ctx.index, "fwd_24h": f24, "fwd_72h": f72})
        sym_fwd.append((sym, fwd))

        for _, row in ev.iterrows():
            t = pd.Timestamp(int(row["timestamp"]), unit="ms", tz="UTC")
            t_int = int(t.value // 1_000_000)
            a = ahr.asof(t)
            if np.isfinite(a):
                bk = "<0.45 抄底" if a < 0.45 else ("0.45-1.2 定投" if a < 1.2 else ("1.2-5 起飞" if a < 5 else ">5 狂热"))
                i = ctx.index.get_indexer([t_int], method="ffill")[0]
                if i >= 0 and np.isfinite(f24[i]):
                    fwd_buckets[bk].append(float(f24[i]))
                    bucket_events[bk] += 1
            # C. 正交性：事件后 24h 内 4h 底分型缩量
            win = c4[(c4.index >= t) & (c4.index <= t + pd.Timedelta(hours=24))]
            if len(win) < 3:
                ortho_no.append(float(ctx["fwd_24h"].iloc[i])) if i >= 0 else None
                continue
            lw = l4.reindex(win.index); vw = v4.reindex(win.index)
            ma20_full = pd.Series(v4.to_numpy(), index=v4.index).rolling(20, min_periods=10).mean()
            ma20v = ma20_full.reindex(win.index)
            found = False
            for j in range(1, len(win) - 1):
                if (lw.iloc[j] < lw.iloc[j - 1] and lw.iloc[j] < lw.iloc[j + 1]
                        and vw.iloc[j] < 0.6 * ma20v.iloc[j]):
                    found = True; break
            i = ctx.index.get_indexer([t_int], method="ffill")[0]
            if i >= 0 and np.isfinite(f24[i]):
                (ortho_yes if found else ortho_no).append(float(f24[i]))

        # ---- A. 分型缩量 4h 独立事件 ----
        n = len(c4)
        c = c4.to_numpy(); l = l4.to_numpy(); v = v4.to_numpy(); ts4 = c4.index
        vol_ma = pd.Series(v).rolling(20, min_periods=10).mean().to_numpy()
        for j in range(1, n - 1):
            if l[j] < l[j - 1] and l[j] < l[j + 1] and v[j] < 0.6 * vol_ma[j]:
                t4 = ts4[j]
                pos = ctx.index.get_indexer([int(t4.value // 1_000_000)], method="ffill")
                if pos[0] >= 0 and pos[0] < len(ctx):
                    f24v, f72v = f24[pos[0]], f72[pos[0]]
                    if np.isfinite(f24v) and np.isfinite(f72v):
                        fx24.append(float(f24v)); fx72.append(float(f72v))
                        fx_month.append(t4.strftime("%Y-%m"))
                        fx_events += 1
        if (list(ctxs.keys()).index(sym) + 1) % 15 == 0:
            print(f"  {list(ctxs.keys()).index(sym)+1}/{len(ctxs)}", flush=True)

    # ---- 汇总 ----
    base = monthly_base(sym_fwd)
    def rep(label: str, vals: list[float], months: list[str] | None = None) -> None:
        x = np.array(vals)
        if len(x) < 10:
            print(f"  {label}: n={len(x)} 样本不足"); return
        ex = 0.0
        if months is not None:
            ex = float(np.mean([v - base.get(m, 0.0) for v, m in zip(x, months)]))
        print(f"  {label}: n={len(x)} mean={x.mean():+.3%} med={np.median(x):+.3%} 超额vs同月={ex:+.3%}")

    print(f"\n=== A. 底分型缩量 4h 独立事件（n={fx_events}）===")
    rep("fwd_24h", fx24, fx_month)
    rep("fwd_72h", fx72, fx_month)

    print(f"\n=== B. wash_cvd × ahr999 分桶（fwd24h）===")
    for k in fwd_buckets:
        rep(k, fwd_buckets[k])

    print(f"\n=== C. wash_cvd 事件后 24h 内 4h 底分型缩量（正交性）===")
    rep("有分型确认", ortho_yes)
    rep("无分型确认", ortho_no)


if __name__ == "__main__":
    main()
