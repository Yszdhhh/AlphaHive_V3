"""AHR999 三版参数对比方案（2026-08-09）。

对比对象：
  A 原版（九神 2018）：a=5.84, b=-17.01（2011-2018 拟合，固定）
  B 文章版：a=5.64, b 重拟合（用户助手方案：固定斜率 + 数据拟合截距）
  C OLS 版：a,b 完全数据驱动（用户助手推荐）

方法学修正（用户助手方案的缺陷）：
  B/C 若用全数据（含事件窗口 2022-2026）拟合再评估事件 = 前视偏差。
  → 主口径 walk-forward：用 2017-08 → 2022-01（事件窗前）数据拟合 B/C 参数，
    再用拟合参数评估 2022-01 后 wash_cvd 事件（无前视）。
  → 附全数据拟合参数对照（展示参数漂移，不用于事件评估）。

有效性检验：
  1. 参数表（a/b/R²/斜率 95% CI）
  2. AHR 三版分布（<0.45 占比、当前值）
  3. BTC 未来收益分桶（全历史 2017-08+，AHR<0.45 后 30/90/180d BTC 收益）
  4. wash_cvd 事件 × 三版 AHR 分桶（fwd24h，asof 无前视）
  5. 定投区（0.45-1.2）时间占比 vs 后续收益稳定性
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

GENESIS = pd.Timestamp("2009-01-03", tz="UTC")
DAY_MS = 86_400_000
WALK_END = pd.Timestamp("2022-01-01", tz="UTC")  # 事件窗口前
CSV = PROJECT_ROOT / "data" / "btc_daily_tmp" / "btc_daily_raw.csv"


def load_btc_daily() -> pd.DataFrame:
    df = pd.read_csv(CSV)
    # Binance vision 部分月度文件 open_time 是微秒（17 位）——统一转 ms
    ot = df["open_time"].to_numpy(dtype=float)
    df["open_time"] = np.where(ot > 1e14, ot / 1000.0, ot)
    df["date"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    # binance_free 补尾 2026-08（本地无网络依赖）
    bf = pd.read_parquet(Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h\klines\BTCUSDT.parquet"),
                         columns=["open_time", "close"])
    bf["date"] = pd.to_datetime(bf["open_time"], unit="ms", utc=True).dt.normalize()
    tail = bf.groupby("date")["close"].last().reset_index()
    tail = tail[tail["date"] > df["date"].max()]
    df = pd.concat([df[["date", "close"]], tail[["date", "close"]]]).sort_values("date").reset_index(drop=True)
    df = df[df["close"] > 0]
    df["t"] = (df["date"] - GENESIS).dt.days.astype(float)
    df["logt"] = np.log10(df["t"])
    df["logp"] = np.log10(df["close"])
    return df


def fit_params(d: pd.DataFrame, a_fixed: float | None = None) -> tuple[float, float, float]:
    """返回 (a, b, R²)。a_fixed 给定则只拟合 b；否则 OLS。"""
    lt, lp = d["logt"].to_numpy(), d["logp"].to_numpy()
    if a_fixed is not None:
        b = float(lp.mean() - a_fixed * lt.mean())
        resid = lp - (a_fixed * lt + b)
        ss_res = float(np.sum(resid ** 2)); ss_tot = float(np.sum((lp - lp.mean()) ** 2))
        return a_fixed, b, 1.0 - ss_res / ss_tot
    a, b = np.polyfit(lt, lp, 1)
    pred = a * lt + b
    resid = lp - pred
    ss_res = float(np.sum(resid ** 2)); ss_tot = float(np.sum((lp - lp.mean()) ** 2))
    return float(a), float(b), 1.0 - ss_res / ss_tot


def slope_ci(d: pd.DataFrame) -> tuple[float, float]:
    lt, lp = d["logt"].to_numpy(), d["logp"].to_numpy()
    n = len(lt)
    a, b = np.polyfit(lt, lp, 1)
    resid = lp - (a * lt + b)
    se = float(np.sqrt(np.sum(resid ** 2) / (n - 2) / np.sum((lt - lt.mean()) ** 2)))
    return a - 1.96 * se, a + 1.96 * se


def ahr_series(d: pd.DataFrame, a: float, b: float) -> pd.Series:
    ev = 10.0 ** (a * d["logt"] + b)
    ma200 = d["close"].rolling(200, min_periods=100).mean()
    return pd.Series(((d["close"] / ma200) * (d["close"] / ev)).to_numpy(), index=d["date"])


def main() -> None:
    d = load_btc_daily()
    print(f"BTC 日线: {len(d)} 天, {d['date'].min().date()} -> {d['date'].max().date()}")

    walk = d[d["date"] < WALK_END]
    full = d
    print(f"\n拟合窗 walk-forward: {walk['date'].min().date()} -> {walk['date'].max().date()} ({len(walk)} 天)")
    print(f"拟合窗 全数据:      {full['date'].min().date()} -> {full['date'].max().date()} ({len(full)} 天)")

    # 参数
    aA, bA, r2A = 5.84, -17.01, np.nan
    aBw, bBw, r2Bw = fit_params(walk, a_fixed=5.64)
    aCf, bCf, r2Cf = fit_params(full)
    aCw, bCw, r2Cw = fit_params(walk)
    aBf, bBf, r2Bf = fit_params(full, a_fixed=5.64)
    lo, hi = slope_ci(walk)
    print("\n=== 1. 参数表 ===")
    print(f"  A 原版 2018:      a=5.84      b=-17.01       (2011-2018 拟合)")
    print(f"  B 文章版 walk:    a=5.64      b={bBw:+.4f}   R²={r2Bw:.4f}  (斜率固定)")
    print(f"  B 文章版 全数据:  a=5.64      b={bBf:+.4f}   R²={r2Bf:.4f}")
    print(f"  C OLS walk:       a={aCw:.4f} b={bCw:+.4f}   R²={r2Cw:.4f}  斜率95%CI[{lo:.3f},{hi:.3f}]")
    print(f"  C OLS 全数据:     a={aCf:.4f} b={bCf:+.4f}   R²={r2Cf:.4f}")

    # AHR 三版（walk-forward 参数，asof 评估）
    ahrA = ahr_series(d, aA, bA)
    ahrB = ahr_series(d, aBw, bBw)
    ahrC = ahr_series(d, aCw, bCw)
    print("\n=== 2. AHR 分布（2017-08 起，含 MA200 预热后）===")
    for name, s in [("A", ahrA), ("B", ahrB), ("C", ahrC)]:
        valid = s.dropna()
        print(f"  {name}: <0.45 占比 {100*(valid<0.45).mean():.1f}% | 0.45-1.2 {100*valid.between(0.45,1.2).mean():.1f}% "
              f"| 1.2-5 {100*valid.between(1.2,5).mean():.1f}% | 当前值 {s.iloc[-1]:.3f}")

    # 3. BTC 未来收益分桶（全历史 asof）
    print("\n=== 3. BTC 未来收益 × AHR 分桶（30/90/180d，asof 无前视）===")
    c = d.set_index("date")["close"]
    for name, s in [("A", ahrA), ("B", ahrB), ("C", ahrC)]:
        rows = []
        for lo_, hi_, lab in [(0, 0.45, "<0.45"), (0.45, 1.2, "0.45-1.2"), (1.2, 5, "1.2-5")]:
            idx = s[(s >= lo_) & (s < hi_)].index
            out = {}
            for nd in (30, 90, 180):
                f = (c.shift(-nd) / c - 1.0).reindex(idx)
                f = f.dropna()
                out[f"f{nd}d"] = f.mean() if len(f) else np.nan
            out["n"] = len(idx)
            rows.append((lab, out))
        print(f"  {name}: " + " | ".join(f"{lab} f30={r['f30d']:+.2%} f90={r['f90d']:+.2%} f180={r['f180d']:+.2%} n={r['n']}"
                                          for lab, r in rows))

    # 4. wash_cvd × AHR 分桶
    print("\n=== 4. wash_cvd 事件 × AHR 分桶（fwd24h，2022-01 起事件）===")
    symbols = load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    buckets = {name: {"<0.45": [], "0.45-1.2": [], "1.2-5": [], "NA": []} for name in "ABC"}
    n_ev = 0
    for sym, ctx in ctxs.items():
        if ctx is None or len(ctx) < 500:
            continue
        ev = detect_events(sym, ctx, None, "wash_cvd")
        if len(ev) == 0:
            continue
        c_ = ctx["close"].to_numpy()
        f24 = np.full(len(c_), np.nan); f24[:-24] = c_[24:] / c_[:-24] - 1.0
        for _, row in ev.iterrows():
            t = pd.Timestamp(int(row["timestamp"]), unit="ms", tz="UTC")
            t_int = int(t.value // 1_000_000)
            i = ctx.index.get_indexer([t_int], method="ffill")[0]
            if i < 0 or not np.isfinite(f24[i]):
                continue
            n_ev += 1
            for name, s in [("A", ahrA), ("B", ahrB), ("C", ahrC)]:
                a = s.asof(t)
                if not np.isfinite(a):
                    buckets[name]["NA"].append(float(f24[i]))
                elif a < 0.45:
                    buckets[name]["<0.45"].append(float(f24[i]))
                elif a < 1.2:
                    buckets[name]["0.45-1.2"].append(float(f24[i]))
                else:
                    buckets[name]["1.2-5"].append(float(f24[i]))
    for name in "ABC":
        parts = []
        for lab in ["<0.45", "0.45-1.2", "1.2-5"]:
            x = np.array(buckets[name][lab])
            parts.append(f"{lab} n={len(x)} mean={x.mean():+.3%}" if len(x) >= 10 else f"{lab} n={len(x)}")
        print(f"  {name}: " + " | ".join(parts))

    # 5. 定投区稳定性（0.45-1.2 期间月均收益波动）
    print("\n=== 5. 定投区（0.45-1.2）内 BTC 月收益稳定性 ===")
    d2 = d.set_index("date")
    mret = (d2["close"].resample("ME").last().pct_change()).dropna()
    for name, s in [("A", ahrA), ("B", ahrB), ("C", ahrC)]:
        in_zone = s.reindex(mret.index, method="ffill").between(0.45, 1.2)
        zm = mret[in_zone]
        print(f"  {name}: 定投区月收益 mean={zm.mean():+.3%} std={zm.std():.3%} 月数={len(zm)} "
              f"| 全区 std={mret.std():.3%}")


if __name__ == "__main__":
    main()
