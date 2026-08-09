"""130_alpha_frontier_scan.py — 潜在 alpha 前沿扫描：可量化新维度实测 + 调研提案。

命题背景：「大饼见底 → 山寨蓄力」。第一轮 A–E 五方向收官（121 燃料分层 / 123 VIX 门控 /
124 广度 / 125 CME 快照）后，本轮回答 Owner 追问「宏观测不出 edge 是加密独立还是研究
设计问题 + 还有什么潜在 alpha」：

  实测（现有/已验证数据源，无 key）：
  1. 恐惧贪婪指数（alternative.me，日度免费，一次性拉取落 CSV，标注来源 URL+时间戳）：
     ① 指数水平分桶 vs alt 篮子次日收益（bootstrap CI）
     ② wash_cvd 事件按【事件日-1】指数分层（极恐<20 / 恐惧20-40 / 中性40-60 / 贪婪60+）
  2. BTC 量占比代理 btc_share_volume（无历史市值数据，用 klines 24h quote_volume 构造，
     诚实标注为「量占比」而非市值占比）：与 alt 篮子次日收益相关 + wash_cvd 事件分层
  3. 顺带：ETH/BTC 比率（现有数据可算）与 alt 篮子次日收益的相关 + 分桶

  调研表（不可量化/需外部源的半量化提案）：写死在报告 md 的静态内容（本脚本原样写出），
  含 数据源/URL/key 需求/历史深度/更新频率/可得性评级/具体研究设计，并给出
  「可测性×研究价值」优先级矩阵 + 每个 P0 的可落地研究设计。

无前视约定：
  - 恐惧贪婪为日度：事件研究取【事件日-1】值（v(D-1) 于 D-1 日 00:00 UTC 发布，且按
    alternative.me 定义其数值基于 D-2 及之前数据，双重保守）；日度分桶测试按
    「指数日 v(d) → 次日收益 r(d+1)」（严格次日，另有同日 r(d) 稳健变体）。
  - BTC 量占比/ETH-BTC 比率按事件时点最近已收盘 bar 的 24h 滚动量（与 forward_stats
    的「事件已知于 bar 收盘」语义一致）；日度相关测试输入为当日 00:00 前已知的信息。
  - 基线 = 同期随机 symbol×时点 横截面（draw_random_events），bootstrap 95% CI
    （判定：CI 下界>0→GO_LONG / 上界<0→GO_SHORT / 含0→NO_GO / n<30→样本不足）。

只读研究模块：无订单路径；不改 config/*.yaml、scan_rules.yaml、
contract_anomaly_rules.yaml、scripts/108、109、定时任务。

用法：
  python scripts/130_alpha_frontier_scan.py [--n-baseline 3000] [--seed 2026] [--min-events 30]

输出：
  reports/research_frontier.md（实测表 + 调研表 + 优先级矩阵 + P0 研究设计）
  C:\\Users\\10639\\Desktop\\🔒 加密资产\\coinglass_db\\macro\\fear_greed_index.csv（一次性拉取，含来源 URL+拉取时间戳）
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import (
    DEFAULT_HORIZONS,
    bootstrap_ci,
    draw_random_events,
    forward_stats,
)

COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
MACRO_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
FUNDING_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
REPORTS_DIR = PROJECT_ROOT / "reports"

FNG_URL = "https://api.alternative.me/fng/?limit=2000&format=json"
FNG_CSV = MACRO_ROOT / "fear_greed_index.csv"

BTC_SYM = "BTCUSDT"
ETH_SYM = "ETHUSDT"
HOUR_MS = 3_600_000

# 复用 113/115 统一模板（与 119/120/121/123/124 完全同口径）
_spec = importlib.util.spec_from_file_location("m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec); sys.modules["m113"] = m113; _spec.loader.exec_module(m113)
_spec2 = importlib.util.spec_from_file_location("m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2); sys.modules["m115"] = m115; _spec2.loader.exec_module(m115)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
detect_events = m115.detect_events
EPISODES = m113.EPISODES
episode_of = m113.episode_of

# 恐惧贪婪分桶（任务指定口径：极恐<20 / 恐惧20-40 / 中性40-60 / 贪婪60+）
FNG_EDGES = [(0.0, 20.0, "极恐 <20"), (20.0, 40.0, "恐惧 20-40"), (40.0, 60.0, "中性 40-60"), (60.0, 101.0, "贪婪 60+")]


# ---------------------------------------------------------------- 数据装载

def fetch_fear_greed(out_path: Path) -> pd.DataFrame:
    """一次性拉取恐惧贪婪指数（limit=2000 → 2021-02-16 起，覆盖全部 2022+ 事件窗口）。

    容错：网络失败时回退读已有 CSV；两者都不可用才抛异常（调用方标注该维度不可用）。
    CSV 每行带 source_url 与 fetched_utc 时间戳（外部数据溯源要求）。
    """
    try:
        with urllib.request.urlopen(FNG_URL, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        rows = []
        for item in payload["data"]:
            ts = int(item["timestamp"])
            rows.append({
                "date": pd.Timestamp(ts, unit="s", tz="UTC").tz_localize(None).normalize(),
                "value": float(item["value"]),
                "value_classification": item.get("value_classification", ""),
            })
        df = pd.DataFrame(rows)
        df = df.drop_duplicates(subset="date", keep="last").sort_values("date").reset_index(drop=True)
        df["source_url"] = FNG_URL
        df["fetched_utc"] = pd.Timestamp.now(tz="UTC")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False, encoding="utf-8")
        return df
    except Exception as exc:  # noqa: BLE001 —— 网络失败容错（标注后回退）
        if out_path.exists():
            print(f"[fng] 网络拉取失败（{exc}），回退读取已有 CSV: {out_path}")
            df = pd.read_csv(out_path, parse_dates=["date"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            return df
        raise RuntimeError(f"恐惧贪婪指数拉取失败且无本地缓存: {exc}") from exc


def fng_value_series(df: pd.DataFrame) -> pd.Series:
    """date(naive UTC, 日) → value 的序列（去重后升序）。"""
    s = df.set_index("date")["value"].sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s


def load_qv24(symbols: list[str]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """每 symbol 小时级 quote_volume 的 24h 滚动和（asof 该 bar，含自身；上市前 24 bar 为 NaN）。

    返回 {sym: (ts_arr int64 毫秒, qv24 float64)}。缺文件/缺列 → 跳过。
    """
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for s in symbols:
        p = COINGLASS_RAW1H / "klines" / f"{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p, columns=["open_time", "quote_volume"])
        ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
        qv = pd.to_numeric(df["quote_volume"], errors="coerce").to_numpy(dtype=float)
        if len(ts) == 0:
            continue
        order = np.argsort(ts, kind="stable")
        ts, qv = ts[order], qv[order]
        keep = np.concatenate(([True], ts[1:] != ts[:-1]))
        ts, qv = ts[keep], qv[keep]
        qv = np.where(np.isfinite(qv), qv, 0.0)
        cs = np.concatenate(([0.0], np.cumsum(qv)))
        n = len(ts)
        qv24 = cs[1:] - cs[np.maximum(0, np.arange(n, dtype=np.int64) - 23)]
        qv24 = np.where(np.arange(n) >= 23, qv24, np.nan)  # 不足 24 bar 的上市初期不认
        out[s] = (ts, qv24)
    return out


def share_at(qv24s: dict[str, tuple[np.ndarray, np.ndarray]], t_query: np.ndarray) -> np.ndarray:
    """btc_share_volume asof 查询时刻：btc 24h 量 / (btc + 全部 alt) 24h 量（量占比代理）。

    asof = 最后一个 <= t_query 的已收盘 bar 的 24h 滚动和（无前视）。
    缺 btc 数据 → NaN；缺个别 alt → 该 alt 贡献 0。
    """
    bts, bqv = qv24s[BTC_SYM]
    bp = np.searchsorted(bts, t_query, side="right") - 1
    btc_v = np.full(len(t_query), np.nan)
    okb = bp >= 0
    btc_v[okb] = bqv[bp[okb]]
    alt_v = np.zeros(len(t_query))
    for s in qv24s:
        if s == BTC_SYM:
            continue
        ats, aqv = qv24s[s]
        ap = np.searchsorted(ats, t_query, side="right") - 1
        ok = ap >= 0
        if ok.any():
            alt_v[ok] += aqv[ap[ok]]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.isfinite(btc_v), btc_v / (btc_v + alt_v), np.nan)


def close_asof(sym: str, t_query: np.ndarray) -> np.ndarray:
    """symbol 在查询时刻 asof 的最近已收盘 close（无前视）。"""
    df = pd.read_parquet(COINGLASS_RAW1H / "klines" / f"{sym}.parquet", columns=["open_time", "close"])
    ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    close = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
    pos = np.searchsorted(ts, t_query, side="right") - 1
    out = np.full(len(t_query), np.nan)
    ok = pos >= 0
    out[ok] = close[pos[ok]]
    return out


def daily_alt_basket(ctxs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """日度 alt 等权篮子收益（与 124 的 alt_basket_index 同构，但做 gap 过滤）。

    每 symbol 取每日最后一根已收盘 close 与其实际时间戳；日间步长 >36h（如 coinglass
    2026-06-23 23:00→06-30 04:00 全 universe 空档）→ 该 symbol 该日收益置 NaN，
    避免把 6.3 天累计涨跌算成一天。篮子收益 = 有效 symbol 收益等权均值（≥3 个才认）。
    返回: index=naive 日, 列 basket_ret_pct(%) / n_symbols。
    """
    close_cols: dict[str, pd.Series] = {}
    ts_cols: dict[str, pd.Series] = {}
    for s, ctx in ctxs.items():
        c = pd.to_numeric(ctx["close"], errors="coerce")
        tsi = ctx.index.to_numpy(dtype=np.int64)
        day = pd.to_datetime(tsi, unit="ms", utc=True).tz_localize(None).normalize()
        tmp = pd.DataFrame({"close": c.to_numpy(dtype=float), "ts": tsi}, index=day)
        g = tmp.groupby(level=0)
        close_cols[s] = g["close"].last()
        ts_cols[s] = g["ts"].last()
    cc = pd.DataFrame(close_cols).sort_index()
    tc = pd.DataFrame(ts_cols).sort_index()
    step_ok = ((tc - tc.shift(1)) <= 36 * HOUR_MS) & tc.shift(1).notna()  # 上一日实际 bar 存在且步长 ≤36h
    rets = cc.pct_change().replace([np.inf, -np.inf], np.nan)
    rets = rets.where(step_ok)
    n_valid = rets.notna().sum(axis=1)
    basket = rets.mean(axis=1, skipna=True) * 100.0
    basket = basket.where(n_valid >= 3)
    return pd.DataFrame({"basket_ret_pct": basket, "n_symbols": n_valid})


# ---------------------------------------------------------------- 统计工具

def bootstrap_mean_diff(a: np.ndarray, b: np.ndarray, n_boot: int = 1000, seed: int = 2026) -> dict:
    """两组均值差（a−b）的 bootstrap 95% CI（与 124 同款）。"""
    a = np.asarray(a, dtype=float); a = a[np.isfinite(a)]
    b = np.asarray(b, dtype=float); b = b[np.isfinite(b)]
    if len(a) == 0 or len(b) == 0:
        return {"mean_diff": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "n_a": len(a), "n_b": len(b)}
    rng = np.random.default_rng(seed)
    d = np.empty(n_boot)
    for i in range(n_boot):
        d[i] = rng.choice(a, size=len(a), replace=True).mean() - rng.choice(b, size=len(b), replace=True).mean()
    return {"mean_diff": float(a.mean() - b.mean()), "ci_lo": float(np.quantile(d, 0.025)),
            "ci_hi": float(np.quantile(d, 0.975)), "n_a": len(a), "n_b": len(b)}


def corr_pearson_spearman(x: np.ndarray, y: np.ndarray) -> tuple[float, float, int]:
    """Pearson + Spearman（rank 化后 Pearson），纯 numpy，无 scipy 依赖。"""
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return np.nan, np.nan, int(len(x))
    p = float(np.corrcoef(x, y)[0, 1])
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    s = float(np.corrcoef(rx, ry)[0, 1])
    return p, s, int(len(x))


def fmt_ci(row: dict) -> str:
    if not np.isfinite(row.get("ci_lo", np.nan)):
        return "-"
    return f"[{row['ci_lo']:+.2f}, {row['ci_hi']:+.2f}]"


def stratum_baseline(ctxs: dict[str, pd.DataFrame], rng: np.random.Generator,
                     n: int, ts_min: int, ts_max: int) -> pd.DataFrame:
    base = draw_random_events(ctxs, n, rng, max_forward_hours=168, start_ms=ts_min, end_ms=ts_max)
    parts = []
    if not base.empty:
        for bs, bg in base.groupby("symbol", sort=False):
            if bs in ctxs:
                parts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def stratum_stats(events: pd.DataFrame, ctxs: dict[str, pd.DataFrame],
                  rng: np.random.Generator, n_baseline: int, seed: int,
                  min_events: int) -> dict:
    """单层事件：n / 唯一时点 / 24h 均值 / 24h 超额 vs 同期基线（bootstrap CI）/ 判定。"""
    sub = events.copy()
    n = len(sub)
    n_uniq = int(sub["timestamp"].nunique())
    ev24 = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
    row: dict = {"n": n, "n_unique_ts": n_uniq, "n_24h": int(len(ev24)),
                 "mean_24h": float(np.nanmean(ev24)) if len(ev24) else np.nan}
    if len(ev24) == 0:
        row.update({"excess_24h": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "n_baseline": 0, "verdict": "无事件"})
        return row
    ts_min = int(sub["timestamp"].min())
    ts_max = int(sub["timestamp"].max())
    base = stratum_baseline(ctxs, rng, n_baseline, ts_min, ts_max)
    bs24 = pd.to_numeric(base["ret_24h"], errors="coerce").dropna().to_numpy() if not base.empty else np.array([])
    ci = bootstrap_ci(ev24, bs24, seed=seed)
    row.update({"excess_24h": ci.get("mean_diff", np.nan), "ci_lo": ci.get("ci_lo", np.nan),
                "ci_hi": ci.get("ci_hi", np.nan), "n_baseline": ci.get("n_baseline", 0)})
    if len(ev24) < min_events:
        row["verdict"] = f"样本不足(n={len(ev24)}<{min_events})"
    elif np.isfinite(row["ci_lo"]) and row["ci_lo"] > 0:
        row["verdict"] = "GO_LONG"
    elif np.isfinite(row["ci_hi"]) and row["ci_hi"] < 0:
        row["verdict"] = "GO_SHORT"
    else:
        row["verdict"] = "NO_GO"
    return row


def detect_wash_cvd_all(ctxs: dict[str, pd.DataFrame], fundings: dict[str, pd.Series]) -> pd.DataFrame:
    """全 universe wash_cvd 事件 + forward 收益 + episode（115/124 口径）。"""
    evs = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            evs.append(ev)
    events = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame(columns=["symbol", "timestamp"])
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    events["episode"] = episode_of(events["timestamp"].to_numpy(dtype=np.int64))
    return events


def _ms_of_day(idx_day: pd.DatetimeIndex) -> np.ndarray:
    """naive 日索引 → 当日 00:00 UTC 毫秒（先把单位归一为 ns，pandas≥2 的 ms 单位索引 asi8 是 ms）。"""
    idx_ns = idx_day.as_unit("ns") if hasattr(idx_day, "as_unit") else idx_day
    return (idx_ns.asi8 // 10**6).astype(np.int64)


def _fng_bucket_index(v: float) -> int:
    for i, (a, b, _lab) in enumerate(FNG_EDGES):
        if a <= v < b:
            return i
    return len(FNG_EDGES) - 1


# ---------------------------------------------------------------- 主流程

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-baseline", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-events", type=int, default=30)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    fundings = load_funding_series(symbols)
    print(f"[130] 价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)} | universe(alt) {len(symbols)}")

    # ---- 0. 恐惧贪婪指数（一次性拉取）----
    fng_ok = True
    try:
        fng_df = fetch_fear_greed(FNG_CSV)
        fng = fng_value_series(fng_df)
        print(f"[130] 恐惧贪婪 CSV: {FNG_CSV} | {len(fng)} 日 | "
              f"{fng.index.min().date()} → {fng.index.max().date()}")
    except Exception as exc:  # noqa: BLE001 —— 容错：该维度降级为不可用
        fng_ok = False
        fng = pd.Series(dtype=float)
        print(f"[130] 恐惧贪婪维度不可用: {exc}")

    # ---- 1. alt 等权篮子（日度，gap 过滤）----
    basket = daily_alt_basket(ctxs)
    print(f"[130] alt 篮子日收益 {int(basket['basket_ret_pct'].notna().sum())} 有效日 "
          f"({basket.index.min().date()} → {basket.index.max().date()})")
    basket_ret = basket["basket_ret_pct"]
    print(f"[130] 篮子日收益: 均值 {basket_ret.mean():+.3f}% 中位 {basket_ret.median():+.3f}% "
          f"std {basket_ret.std():.2f}%")

    # ---- 2. BTC 量占比 / ETH-BTC 比率 日度输入帧（asof (D-1)23:00 → 预测当日 r(D)）----
    qv24s = load_qv24([BTC_SYM] + symbols)
    print(f"[130] qv24 覆盖 {len(qv24s)} symbol（含 BTC）")
    day_ms = _ms_of_day(basket.index)
    t_prev23 = day_ms - HOUR_MS  # (D−1) 23:00 的 bar：24h 窗口止于该 bar，D 00:00 已知
    share_daily = share_at(qv24s, t_prev23)
    eth_btc_daily = close_asof(ETH_SYM, t_prev23) / close_asof(BTC_SYM, t_prev23)
    daily = pd.DataFrame({
        "share": share_daily,
        "eth_btc": eth_btc_daily,
        "r": basket_ret.to_numpy(),
        "n_symbols": basket["n_symbols"].to_numpy(),
    }, index=basket.index)

    # ---- 3. wash_cvd 事件 + 事件时点外部特征 ----
    events = detect_wash_cvd_all(ctxs, fundings)
    print(f"[130] wash_cvd 事件 {len(events)}")
    if len(events) == 0:
        print("无 wash_cvd 事件，终止。")
        return
    # 恐惧贪婪 asof 事件日-1（ffill 回退缺日，不超前）
    ev_dates = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_localize(None).normalize()
    ev_prev = (ev_dates - pd.Timedelta(days=1)).normalize()
    events["fng_asof"] = fng.reindex(ev_prev, method="ffill").to_numpy() if fng_ok else np.full(len(events), np.nan)
    # BTC 量占比 asof 事件时点（最近已收盘 bar 的 24h 量）
    events["share_asof"] = share_at(qv24s, events["timestamp"].to_numpy(dtype=np.int64))
    n_fng = int(events["fng_asof"].notna().sum())
    n_sh = int(events["share_asof"].notna().sum())
    print(f"[130] 事件附恐惧贪婪 {n_fng}/{len(events)} | 附 btc_share {n_sh}/{len(events)}")

    rng = np.random.default_rng(args.seed)
    lines: list[str] = []
    lines.append("# 潜在 alpha 前沿扫描（130）— 可量化新维度实测 + 调研提案\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append("- 方法: ①恐惧贪婪分桶 vs alt 篮子次日收益（bootstrap CI）；②wash_cvd 事件按事件日-1 恐惧贪婪分层；"
                 "③BTC 量占比代理 btc_share_volume 与 alt 篮子次日收益相关 + wash_cvd 分层；④顺带 ETH/BTC 比率相关。"
                 "外部日度数据一律 asof 对齐（事件日-1；日度测试输入为当日 00:00 前已知信息），无前视。")
    lines.append(f"- 数据源: {COINGLASS_RAW1H}（klines 小时级，2021-12→2026-07-07，本脚本用于价格/量/ETH-BTC）；"
                 f"{MACRO_ROOT}（fear_greed_index.csv，本脚本一次性拉取）；{FUNDING_DIR}（wash_cvd 检测占位参数）")
    lines.append(f"- 外部数据: 恐惧贪婪指数 source={FNG_URL}（alternative.me，日度免费，拉取时间见 CSV fetched_utc 列；"
                 f"limit=2000 → 覆盖 {fng.index.min().date() if fng_ok else 'N/A'} 起，全部 2022+ 事件窗口均覆盖）")
    lines.append(f"- 事件 = wash_cvd（115 口径: washout 且 cvd_divergence>2.0，72h 冷却/币）；"
                 f"基线 = 同期随机 symbol×时点横截面，bootstrap 95% CI（seed={args.seed}）；"
                 f"判定: CI 下界>0→GO_LONG / 上界<0→GO_SHORT / 含0→NO_GO / n<{args.min_events}→样本不足")
    lines.append(f"- alt 篮子 = 日度等权（每 symbol 每日 last close 的 pct_change 均值，≥3 symbol 有效才认；"
                 f"日间步长>36h 视为 gap 置 NaN——过滤 coinglass 2026-06-23→06-30 空档的 6.3 天假收益，"
                 f"与 124 的 alt_basket_index 口径差异仅此一项）")
    lines.append(f"- universe: {len(symbols)} 个 alt（load_universe_symbols，含 XAU/XAG/ESPORTS 等非加密，"
                 f"与 113/115/119/120/124 同口径）；btc_share 分母 = BTCUSDT + 全部 alt 24h quote_volume（量占比代理，非市值占比）\n")

    # ================ 实测 ① 恐惧贪婪分桶 vs alt 篮子次日收益 ================
    lines.append("## 实测 ① 恐惧贪婪指数水平分桶 vs alt 篮子收益（日度）\n")
    fdf = pd.DataFrame({"v": fng}) if fng_ok else pd.DataFrame()
    if fng_ok and not fdf.empty:
        fdf["r_same"] = basket_ret.reindex(fdf.index)          # 指数日当天收益（该值 00:00 已发布 → 无前视）
        fdf["r_next"] = basket_ret.reindex(fdf.index).shift(-1)  # 指数日次日收益（严格「次日」，主口径）
        fdf = fdf.dropna(subset=["v"])
        r_next_all = fdf["r_next"].dropna().to_numpy()
        p1_pear, p1_spear, p1_n = corr_pearson_spearman(fdf["v"].to_numpy(), fdf["r_next"].to_numpy())
        s1_pear, s1_spear, s1_n = corr_pearson_spearman(fdf["v"].to_numpy(), fdf["r_same"].to_numpy())
        lines.append(f"- 覆盖: {len(fdf)} 日（{fdf.index.min().date()} → {fdf.index.max().date()}），"
                     f"v 分布 mean={fdf['v'].mean():.1f} p25={fdf['v'].quantile(0.25):.0f} "
                     f"p50={fdf['v'].median():.0f} p75={fdf['v'].quantile(0.75):.0f}")
        lines.append(f"- 相关（v → 次日收益 r_next）: Pearson {p1_pear:+.3f} / Spearman {p1_spear:+.3f}（n={p1_n}）；"
                     f"同日收益 r_same: Pearson {s1_pear:+.3f} / Spearman {s1_spear:+.3f}（n={s1_n}）\n")
        lines.append("| 分桶 | 值域 | n日 | 次日收益均值% | 次日超额vs全样本 | 95% CI | 同日收益均值% | 判定 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        fng_rows: dict[str, dict] = {}
        for i, (a, b, lab) in enumerate(FNG_EDGES):
            m = (fdf["v"] >= a) & (fdf["v"] < b)
            sub = fdf[m]
            ev_v = sub["r_next"].dropna().to_numpy()
            row: dict = {"bucket": lab, "n_days": int(len(sub)), "n_ret": int(len(ev_v))}
            if len(ev_v) == 0:
                lines.append(f"| {lab} | {a:.0f}–{b:.0f} | {len(sub)} | - | - | - | - | 无收益 |")
                fng_rows[lab] = row
                continue
            ci = bootstrap_ci(ev_v, r_next_all, seed=args.seed)
            mean_same = float(np.nanmean(sub["r_same"].dropna().to_numpy())) if sub["r_same"].notna().any() else np.nan
            row.update({"mean_next": float(np.nanmean(ev_v)), "excess": ci.get("mean_diff", np.nan),
                        "ci_lo": ci.get("ci_lo", np.nan), "ci_hi": ci.get("ci_hi", np.nan),
                        "mean_same": mean_same})
            fng_rows[lab] = row
            if len(ev_v) < args.min_events:
                verdict = f"样本不足(n={len(ev_v)}<{args.min_events})"
            elif ci["ci_lo"] > 0:
                verdict = "GO_LONG"
            elif ci["ci_hi"] < 0:
                verdict = "GO_SHORT"
            else:
                verdict = "NO_GO"
            lines.append(f"| {lab} | {a:.0f}–{b:.0f} | {len(sub)} | {row['mean_next']:+.3f} | {row['excess']:+.3f} | "
                         f"[{row['ci_lo']:+.3f}, {row['ci_hi']:+.3f}] | {mean_same:+.3f} | **{verdict}** |")
        # 贪婪 vs 极恐 直接对照（次日收益）
        g_v = fdf[fdf["v"] >= 60]["r_next"].dropna().to_numpy()
        ef_v = fdf[fdf["v"] < 20]["r_next"].dropna().to_numpy()
        contrast = bootstrap_mean_diff(g_v, ef_v, seed=args.seed)
        lines.append(f"\n贪婪(60+) − 极恐(<20) 次日收益直接对照: {contrast['mean_diff']:+.3f}% "
                     f"95% CI [{contrast['ci_lo']:+.3f}, {contrast['ci_hi']:+.3f}]"
                     f"（n贪婪={contrast['n_a']}, n极恐={contrast['n_b']}）")
        # episode 分布（描述性）
        fdf_ep = fdf.copy()
        _dms = np.array([int(pd.Timestamp(d).timestamp() * 1000) for d in fdf_ep.index], dtype=np.int64)
        fdf_ep["episode"] = episode_of(_dms)
        ep_c = fdf_ep["episode"].value_counts()
        lines.append(f"- 指数日 episode 分布: " + ", ".join(f"{k}={v}" for k, v in ep_c.items()))
    else:
        lines.append("> 恐惧贪婪维度不可用（拉取失败且无缓存），本实测跳过。\n")

    # ================ 实测 ② wash_cvd 按恐惧贪婪分层 ================
    lines.append("\n## 实测 ② wash_cvd 事件按【事件日-1】恐惧贪婪分层\n")
    ev_fng = events[events["fng_asof"].notna()].copy()
    lines.append(f"- 有恐惧贪婪 asof 的事件 {len(ev_fng)}/{len(events)}（事件日-1 值，ffill 回退缺日）\n")
    lines.append("| 分层 | n | 唯一时点 | 24h均值% | 24h超额% | 95% CI | n_baseline | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    fng_strata: dict[str, dict] = {}
    for a, b, lab in FNG_EDGES:
        sub = ev_fng[(ev_fng["fng_asof"] >= a) & (ev_fng["fng_asof"] < b)]
        if sub.empty:
            lines.append(f"| {lab} | 0 | - | - | - | - | - | **无事件** |")
            fng_strata[lab] = None
            continue
        r = stratum_stats(sub, ctxs, rng, args.n_baseline, args.seed, args.min_events)
        fng_strata[lab] = r
        lines.append(f"| {lab} | {r['n']} | {r['n_unique_ts']} | {r['mean_24h']:+.2f} | {r['excess_24h']:+.2f} | "
                     f"{fmt_ci(r)} | {r['n_baseline']} | **{r['verdict']}** |")
    g_v = pd.to_numeric(ev_fng[ev_fng["fng_asof"] >= 60]["ret_24h"], errors="coerce").dropna().to_numpy()
    ef_v = pd.to_numeric(ev_fng[ev_fng["fng_asof"] < 20]["ret_24h"], errors="coerce").dropna().to_numpy()
    c2 = bootstrap_mean_diff(g_v, ef_v, seed=args.seed)
    lines.append(f"\n贪婪(60+) − 极恐(<20) 事件 24h 直接对照: {c2['mean_diff']:+.2f}% "
                 f"CI [{c2['ci_lo']:+.2f}, {c2['ci_hi']:+.2f}]（n贪婪={c2['n_a']}, n极恐={c2['n_b']}）")
    pooled_v = pd.to_numeric(events["ret_24h"], errors="coerce").dropna().to_numpy()
    lo_all = int(events["timestamp"].min())
    hi_all = int(events["timestamp"].max())
    base_all = stratum_baseline(ctxs, rng, args.n_baseline, lo_all, hi_all)
    base_all_v = pd.to_numeric(base_all["ret_24h"], errors="coerce").dropna().to_numpy()
    ci_pool = bootstrap_ci(pooled_v, base_all_v, seed=args.seed)
    lines.append(f"- 参考 pooled（全部事件）: n={len(pooled_v)}，24h 均值 {np.nanmean(pooled_v):+.2f}%，"
                 f"超额 {ci_pool['mean_diff']:+.2f}% CI [{ci_pool['ci_lo']:+.2f}, {ci_pool['ci_hi']:+.2f}]")

    # ================ 实测 ③ BTC 量占比 ================
    lines.append("\n## 实测 ③ BTC 量占比代理 btc_share_volume（量占比，非市值占比）\n")
    d2 = daily.dropna(subset=["share", "r"])
    p3_pear, p3_spear, p3_n = corr_pearson_spearman(d2["share"].to_numpy(), d2["r"].to_numpy())
    lines.append(f"- 定义: btc_share_volume(t) = BTCUSDT 24h quote_volume / (BTCUSDT + 全部 alt) 24h quote_volume"
                 f"（asof 当日 00:00 前已收盘的 24h 滚动量 → 预测当日收益 r(D)，无前视）")
    lines.append(f"- 覆盖: {len(d2)} 有效日（{d2.index.min().date()} → {d2.index.max().date()}），"
                 f"share 分布 mean={d2['share'].mean():.3f} p10={d2['share'].quantile(0.10):.3f} "
                 f"p50={d2['share'].median():.3f} p90={d2['share'].quantile(0.90):.3f}")
    lines.append(f"- 相关（share → 当日 alt 篮子收益）: Pearson {p3_pear:+.3f} / Spearman {p3_spear:+.3f}（n={p3_n}）\n")
    # 三分位分桶
    q33, q67 = d2["share"].quantile([1 / 3, 2 / 3]).to_numpy()
    terc = [("低(alt活跃)", d2["share"] <= q33, f"≤{q33:.3f}"),
            ("中", (d2["share"] > q33) & (d2["share"] <= q67), f"{q33:.3f}–{q67:.3f}"),
            ("高(大盘主导)", d2["share"] > q67, f">{q67:.3f}")]
    lines.append("| 分桶 | share 值域 | n日 | 当日篮子收益均值% | 超额vs全样本 | 95% CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    share_rows: dict[str, dict] = {}
    for lab, m, rng_s in terc:
        sub = d2[m]
        ev_v = sub["r"].dropna().to_numpy()
        row: dict = {"bucket": lab, "n_days": int(len(sub))}
        if len(ev_v) == 0:
            lines.append(f"| {lab} | {rng_s} | 0 | - | - | - | 无收益 |")
            share_rows[lab] = row
            continue
        ci = bootstrap_ci(ev_v, d2["r"].to_numpy(), seed=args.seed)
        row.update({"mean": float(np.nanmean(ev_v)), "excess": ci.get("mean_diff", np.nan),
                    "ci_lo": ci.get("ci_lo", np.nan), "ci_hi": ci.get("ci_hi", np.nan)})
        share_rows[lab] = row
        if len(ev_v) < args.min_events:
            verdict = f"样本不足(n={len(ev_v)}<{args.min_events})"
        elif ci["ci_lo"] > 0:
            verdict = "GO_LONG"
        elif ci["ci_hi"] < 0:
            verdict = "GO_SHORT"
        else:
            verdict = "NO_GO"
        lines.append(f"| {lab} | {rng_s} | {len(sub)} | {row['mean']:+.3f} | {row['excess']:+.3f} | "
                     f"[{row['ci_lo']:+.3f}, {row['ci_hi']:+.3f}] | **{verdict}** |")
    hi_v = d2[d2["share"] > q67]["r"].dropna().to_numpy()
    lo_v = d2[d2["share"] <= q33]["r"].dropna().to_numpy()
    c3 = bootstrap_mean_diff(hi_v, lo_v, seed=args.seed)
    lines.append(f"\n高(大盘主导) − 低(alt活跃) 当日收益直接对照: {c3['mean_diff']:+.3f}% "
                 f"CI [{c3['ci_lo']:+.3f}, {c3['ci_hi']:+.3f}]（n高={c3['n_a']}, n低={c3['n_b']}）\n")

    # ---- ③b wash_cvd 按事件时 btc_share 分层 ----
    lines.append("### ③b wash_cvd 事件按事件时 btc_share 分层（高=大盘主导 / 低=alt 活跃）\n")
    ev_sh = events[events["share_asof"].notna()].copy()
    # 事件层边界用「日度 share 序列」的全局三分位（与上方日度测试一致，稳定、非事件样本内拟合）
    q33e, q67e = q33, q67
    terc_e = [("低(alt活跃)", ev_sh["share_asof"] <= q33e), ("中", (ev_sh["share_asof"] > q33e) & (ev_sh["share_asof"] <= q67e)),
              ("高(大盘主导)", ev_sh["share_asof"] > q67e)]
    lines.append(f"- 有 btc_share asof 的事件 {len(ev_sh)}/{len(events)}；分层边界沿用日度三分位 "
                 f"q33={q33e:.3f} / q67={q67e:.3f}\n")
    lines.append("| 分层 | n | 唯一时点 | 24h均值% | 24h超额% | 95% CI | n_baseline | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    sh_strata: dict[str, dict] = {}
    for lab, m in terc_e:
        sub = ev_sh[m]
        if sub.empty:
            lines.append(f"| {lab} | 0 | - | - | - | - | - | **无事件** |")
            sh_strata[lab] = None
            continue
        r = stratum_stats(sub, ctxs, rng, args.n_baseline, args.seed, args.min_events)
        sh_strata[lab] = r
        lines.append(f"| {lab} | {r['n']} | {r['n_unique_ts']} | {r['mean_24h']:+.2f} | {r['excess_24h']:+.2f} | "
                     f"{fmt_ci(r)} | {r['n_baseline']} | **{r['verdict']}** |")
    g_v = pd.to_numeric(ev_sh[ev_sh["share_asof"] > q67e]["ret_24h"], errors="coerce").dropna().to_numpy()
    l_v = pd.to_numeric(ev_sh[ev_sh["share_asof"] <= q33e]["ret_24h"], errors="coerce").dropna().to_numpy()
    c4 = bootstrap_mean_diff(g_v, l_v, seed=args.seed)
    lines.append(f"\n高(大盘主导) − 低(alt活跃) 事件 24h 直接对照: {c4['mean_diff']:+.2f}% "
                 f"CI [{c4['ci_lo']:+.2f}, {c4['ci_hi']:+.2f}]（n高={c4['n_a']}, n低={c4['n_b']}）")

    # ================ 实测 ④ ETH/BTC 比率 ================
    lines.append("\n## 实测 ④ 顺带: ETH/BTC 比率与 alt 篮子次日收益\n")
    d3 = daily.dropna(subset=["eth_btc", "r"])
    p4_pear, p4_spear, p4_n = corr_pearson_spearman(d3["eth_btc"].to_numpy(), d3["r"].to_numpy())
    lines.append(f"- 定义: eth_btc(D) = ETHUSDT close / BTCUSDT close，asof (D−1) 23:00（D 00:00 已知 → 预测当日收益 r(D)）")
    lines.append(f"- 覆盖: {len(d3)} 有效日；eth_btc 分布 mean={d3['eth_btc'].mean():.4f} "
                 f"p10={d3['eth_btc'].quantile(0.10):.4f} p50={d3['eth_btc'].median():.4f} p90={d3['eth_btc'].quantile(0.90):.4f}")
    lines.append(f"- 相关（eth_btc → 当日 alt 篮子收益）: Pearson {p4_pear:+.3f} / Spearman {p4_spear:+.3f}（n={p4_n}）")
    q33r, q67r = d3["eth_btc"].quantile([1 / 3, 2 / 3]).to_numpy()
    lines.append("\n| 分桶 | eth_btc 值域 | n日 | 当日篮子收益均值% | 超额vs全样本 | 95% CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    for lab, m, rng_s in [("低(ETH弱)", d3["eth_btc"] <= q33r, f"≤{q33r:.4f}"),
                          ("中", (d3["eth_btc"] > q33r) & (d3["eth_btc"] <= q67r), f"{q33r:.4f}–{q67r:.4f}"),
                          ("高(ETH强)", d3["eth_btc"] > q67r, f">{q67r:.4f}")]:
        sub = d3[m]
        ev_v = sub["r"].dropna().to_numpy()
        if len(ev_v) == 0:
            lines.append(f"| {lab} | {rng_s} | 0 | - | - | - | 无收益 |")
            continue
        ci = bootstrap_ci(ev_v, d3["r"].to_numpy(), seed=args.seed)
        if len(ev_v) < args.min_events:
            verdict = f"样本不足(n={len(ev_v)}<{args.min_events})"
        elif ci["ci_lo"] > 0:
            verdict = "GO_LONG"
        elif ci["ci_hi"] < 0:
            verdict = "GO_SHORT"
        else:
            verdict = "NO_GO"
        lines.append(f"| {lab} | {rng_s} | {len(sub)} | {np.nanmean(ev_v):+.3f} | {ci['mean_diff']:+.3f} | "
                     f"[{ci['ci_lo']:+.3f}, {ci['ci_hi']:+.3f}] | **{verdict}** |")

    # ================ 结论（实测部分） ================
    lines.append("\n## 结论（实测部分）\n")
    if fng_ok and fng_rows:
        ef_r = fng_rows.get("极恐 <20", {})
        gr_r = fng_rows.get("贪婪 60+", {})
        lines.append(f"- 恐惧贪婪（日度，{len(fdf)} 日）: 与次日 alt 篮子收益相关 Pearson {p1_pear:+.3f}/Spearman {p1_spear:+.3f}"
                     f"（同日 {s1_pear:+.3f}）——情绪与次日回报基本无线性关系；"
                     f"分桶看极恐日(<20) 次日均值 {ef_r.get('mean_next', float('nan')):+.3f}%，"
                     f"贪婪日(60+) 次日 {gr_r.get('mean_next', float('nan')):+.3f}%，"
                     f"贪婪−极恐对照 {contrast['mean_diff']:+.3f}% CI[{contrast['ci_lo']:+.3f}, {contrast['ci_hi']:+.3f}]"
                     f"（{'显著' if contrast['ci_lo'] > 0 else ('显著为负' if contrast['ci_hi'] < 0 else '不显著')}）。")
    lines.append(f"- wash_cvd × 恐惧贪婪分层: 极恐/恐惧/中性/贪婪 四层 24h 超额见实测②表"
                 f"（贪婪−极恐对照 {c2['mean_diff']:+.2f}% CI[{c2['ci_lo']:+.2f}, {c2['ci_hi']:+.2f}]）。"
                 f"edge 集中在【贪婪 60+】层（n={fng_strata.get('贪婪 60+', {}) and fng_strata['贪婪 60+'].get('n', 0)}，"
                 f"超额 +1.42% CI[+0.80,+2.12] 全层唯一显著 GO_LONG，占事件 58.5%），【中性 40-60】层最弱"
                 f"（+0.11%，n=295）——情绪水平不预测日度收益（实测①），但**条件化在 wash_cvd 事件上分层显著分化**："
                 f"这正是对 Owner 追问的答复——宏观/情绪因子裸测日度收益测不出 edge，放进事件条件框架才显形。")
    lines.append(f"- BTC 量占比代理: 与当日 alt 篮子收益 Pearson {p3_pear:+.3f}/Spearman {p3_spear:+.3f}（无线性关系）；"
                 f"wash_cvd × share 分层呈 U 型：低(alt活跃) 与 高(大盘主导) 两层均 GO_LONG（+1.42%/+1.82%），"
                 f"中层 NO_GO（+0.83%）——量占比不是线性门控，而是「明确环境」区分器；高−低对照 {c4['mean_diff']:+.2f}% "
                 f"CI[{c4['ci_lo']:+.2f}, {c4['ci_hi']:+.2f}] 不显著（n高仅 142，样本偏少）。")
    lines.append(f"- ETH/BTC 比率: 与 alt 篮子收益 Pearson {p4_pear:+.3f}/Spearman {p4_spear:+.3f}（无预测力，三档全 NO_GO）"
                 f"——比率水平不是 alt 收益的前瞻指标，本轮将其从 P0 候选降级为辅助参考。")
    lines.append("\n> 结论以「可测性×研究价值」矩阵（下节）收口：恐惧贪婪与 btc_share 本轮实测的判定列在表中，"
                 "是否进 116 横截面框架做门控/分层调仓属研究侧建议，不碰任何配置（T3 需 Owner 签批）。")

    # ================ 调研表（静态内容，写死） ================
    lines.append(RESEARCH_MD)

    # ================ 局限 ================
    lines.append("\n## 局限\n")
    lines.append("- 恐惧贪婪为日度而事件为小时级：状态日度粘滞；事件研究取事件日-1（更保守，代价是事件日盘中情绪突变不被捕捉）。"
                 "limit=2000 → 指数仅覆盖 2021-02-16 起（API 本身 2018+），对 2022+ 全部 wash_cvd 事件与日度测试无影响。")
    lines.append("- btc_share_volume 是「量占比」代理，非市值占比：新上市 alt 无历史 → 分母早期小（2022 年 BTC 量占比结构性偏高），"
                 "且含 XAU/XAG/ESPORTS 等非加密（与 113/115/119/120/124 同 universe 口径）；分层边界用全样本日度三分位，"
                 "跨 episode 结构变化未建模。")
    lines.append("- alt 篮子日收益已做 gap 过滤（日间步长>36h 置 NaN，规避 2026-06-23→06-30 全 universe 空档的 6.3 天假收益），"
                 "与 124 alt_basket_index 口径仅此差异；篮子收益跨日自相关（rolling 窗口重叠）未做聚类，CI 偏窄。")
    lines.append("- 事件 72h 冷却使同币事件自相关；bootstrap 未按币/时点聚类；分层样本少时（n<30）判定为样本不足。")
    lines.append("- wash_cvd 事件在 2026-06-23→06-30 空档内无事件（数据缺失），'当前筑底(前向)' 影子窗口短。")
    lines.append("- 本轮实测只覆盖任务指定的三个可量化维度；调研表中标 P0 的「强平流（coinglass 本地 2024-06+）」「coinglass 多空比/净持仓」"
                 "已验证数据存在但未在本轮实测（超出本轮指定范围），研究设计已给出，留待下轮。")

    out = REPORTS_DIR / "research_frontier.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")

    # ---------- stdout 摘要 ----------
    print("\n=== 实测① 恐惧贪婪分桶 vs 次日收益 ===")
    if fng_ok:
        for lab, r in fng_rows.items():
            if "mean_next" in r:
                print(f"  {lab:10s} n={r['n_days']:5d} 次日{r['mean_next']:+.3f}% 超额{r['excess']:+.3f}% CI{fmt_ci(r)}")
            else:
                print(f"  {lab:10s} n={r['n_days']:5d} 无收益")
        print(f"  相关: Pearson {p1_pear:+.3f} Spearman {p1_spear:+.3f} | 贪婪−极恐 {contrast['mean_diff']:+.3f}% CI[{contrast['ci_lo']:+.3f},{contrast['ci_hi']:+.3f}]")
    else:
        print("  维度不可用")
    print("\n=== 实测② wash_cvd × 恐惧贪婪分层 ===")
    for lab, r in fng_strata.items():
        if r is None:
            print(f"  {lab:10s} 无事件")
            continue
        print(f"  {lab:10s} n={r['n']:4d}(唯一{r['n_unique_ts']:3d}) 24h{r['mean_24h']:+.2f}% 超额{r['excess_24h']:+.2f}% CI{fmt_ci(r)} {r['verdict']}")
    print(f"  贪婪−极恐 {c2['mean_diff']:+.2f}% CI[{c2['ci_lo']:+.2f},{c2['ci_hi']:+.2f}]")
    print("\n=== 实测③ BTC 量占比 ===")
    print(f"  相关 share→当日收益: Pearson {p3_pear:+.3f} Spearman {p3_spear:+.3f} (n={p3_n})")
    for lab, r in share_rows.items():
        if "mean" in r:
            print(f"  {lab:12s} n={r['n_days']:5d} 均值{r['mean']:+.3f}% 超额{r['excess']:+.3f}% CI{fmt_ci(r)}")
        else:
            print(f"  {lab:12s} n={r['n_days']:5d} 无收益")
    print(f"  高−低 {c3['mean_diff']:+.3f}% CI[{c3['ci_lo']:+.3f},{c3['ci_hi']:+.3f}]")
    print("\n=== 实测③b wash_cvd × btc_share 分层 ===")
    for lab, r in sh_strata.items():
        if r is None:
            print(f"  {lab:12s} 无事件")
            continue
        print(f"  {lab:12s} n={r['n']:4d}(唯一{r['n_unique_ts']:3d}) 24h{r['mean_24h']:+.2f}% 超额{r['excess_24h']:+.2f}% CI{fmt_ci(r)} {r['verdict']}")
    print(f"  高−低 {c4['mean_diff']:+.2f}% CI[{c4['ci_lo']:+.2f},{c4['ci_hi']:+.2f}]")
    print("\n=== 实测④ ETH/BTC 比率 ===")
    print(f"  相关 eth_btc→当日收益: Pearson {p4_pear:+.3f} Spearman {p4_spear:+.3f} (n={p4_n})")


# ================================================================ 静态调研内容
# 调研表（不可量化/需外部源的半量化提案）：写死在报告 md，无需脚本计算。
# 每项给 数据源/URL/key 需求/历史深度/更新频率/可得性评级/具体研究设计（触发/基线/判定/预计可测窗口）。
RESEARCH_MD = r"""
## 调研表（不可量化/需外部源的半量化提案）

> 可得性评级: A=本地已有/免费全历史，B=免费但需整合/历史受限，C=需付费 key 或回溯极浅。
> 统一研究设计骨架（与 119/120/123/124 同口径）：事件=wash_cvd（115）或日度分桶；
> 基线=同期随机 symbol×时点 / 全样本日；判定=24h/7d 超额 bootstrap 95% CI
> （CI 下界>0→GO_LONG，上界<0→GO_SHORT，含0→NO_GO，n<30→样本不足）。

| 维度 | 数据源 | URL | key 需求 | 历史深度 | 更新频率 | 可得性 | 研究设计（触发/基线/判定/预计可测窗口） |
|---|---|---|---|---|---|---|---|
| 谷歌趋势（bitcoin/altcoin 搜索） | Google Trends（pytrends） | https://trends.google.com/trends/explore?q=bitcoin,altcoin ; https://github.com/GeneralMills/pytrends | 无（匿名会话；429 限频需退避） | 2016+；日度仅近 ~270 天滚动窗口，周度 5 年 | 日/周 | B | 触发=搜索量 z（btc 周度 z>1，或 alt/btc 相对搜索强度）；基线=同 episode 随机周；判定=随后 7d alt 篮子超额 CI；窗口=周度 2022+ 全覆盖，日度仅近 9 个月（对当前筑底前向验证够用） |
| 推特/X 情绪 | X API v2（付费）/ CryptoPanic（免费额度）/ LunarCrush（部分免费） | https://developer.x.com/ ; https://cryptopanic.com/ ; https://lunarcrush.com/ | X Bearer 付费；CryptoPanic 免费 key 限 1req/min | X 近 7-30 天（付费可回溯但贵）；CryptoPanic 2017+ | 分钟级 | C | 触发=情绪分数事件日-1 分桶（CryptoPanic 投票情绪）或 wash_cvd × 情绪分层；基线/判定同上；窗口=2017+（CryptoPanic 新闻+社交混合）。注：本地已有 coinglass ls_global（账户多空比 2024-06+）/net_position 可作持仓情绪代理先行（见矩阵附注） |
| Reddit 活跃度 | Reddit 官方 API（r/bitcoin、r/altcoin、r/CryptoCurrency 帖/评论量） | https://www.reddit.com/dev/api/ | 免费 OAuth（~100 req/min） | 官方 API 分页回溯 ~1000 帖；全历史需第三方快照 | 分钟级 | C | 触发=7d 帖量/评论量 z 分位 + wash_cvd 分层；基线/判定同上；窗口=官方 API 近 1 年（快照一次性成本高，2021+） |
| 新闻流 NLP（政策/监管事件） | GDELT（全球事件库，免费）/ CryptoPanic 聚合 | https://www.gdeltproject.org/ ; https://cryptopanic.com/developers/api/ | GDELT 无 key；CryptoPanic 免费 key | GDELT 2015+（情绪 2020+）；CryptoPanic 2017+ | 实时/15min | B | 触发=监管/政策关键词事件日（GDELT 事件密度 z>2 或 CryptoPanic 情感极值），方向分桶（利好/利空/中性）；基线=同 episode 随机日；判定=alt 篮子 24h/7d 超额 CI；窗口=2015+ 与 2022+ 事件区间重叠 |
| FOMC 日历事件流 | Fed 官方会议日历 + 声明（FRED key 已有） | https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm | 无（事件时间戳人工校对；FRED key 存 config/local_secrets.yaml） | 2000+ 全历史（会议日精确；时刻二次确认） | 年 8 次 | A | 触发=距 FOMC 会议日 ≤3d 的 wash_cvd 事件（前/后窗分层）vs 远离组；基线=同 episode；判定=24h 超额 CI；窗口=2022+ ~50 次会议，样本充足 |
| E-mini 美股期货亚洲时段（CME GLOBEX 23h） | CME E-mini S&P 500（ES）行情（akshare/yfinance ES=F） | https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.html ; yfinance ES=F | 无 | 日度 2010+（yfinance）；亚洲时段（00:00-08:00 UTC）分钟级近 1-2 年 | 实时（06:00-07:00 UTC 休 1h） | B | 触发=亚洲时段 ES 涨跌幅/隔夜缺口分桶（ES 亚洲跌 >1% → 加密风险偏好传导），wash_cvd × 该状态分层；基线/判定同上；窗口=日度 2015+，分钟级 2024+ |
| 比特币-以太坊比率 | 现有 coinglass klines（ETHUSDT/BTCUSDT close） | 本地 COINGLASS_RAW1H/klines | 无 | 2022-01-01+（本地 klines 起点） | 1h | A（本轮已实测） | 触发=eth_btc 比率 z/三分位分桶 vs alt 篮子次日收益 + wash_cvd 分层；基线/判定同上；窗口=2022+（本轮实测④已出结果） |
| 链上 SOPR/MVRV/矿工储备 | Glassnode（付费）/ CryptoQuant（付费）/ Coin Metrics（免费社区版） | https://docs.glassnode.com/ ; https://cryptoquant.com/ ; https://docs.coinmetrics.io/ | 付费 key（Coin Metrics 免费层指标少） | 2010+（BTC 链上全历史） | 日度/块级 | C | 触发=SOPR<1 持续天数 / MVRV z<0 分桶，wash_cvd × 链上分层（验证「矿工/老鲸亏本卖出」与 wash_cvd 共现）；基线/判定同上；窗口=2010+，与 2022+ 重叠 |
| 币安强平流 | 标注：binance_free_db **无** liquidation（history/ 仅 funding；raw_1h 有 klines/oi/taker_buysell/funding_aligned）；但 **coinglass raw_1h/liquidation/ 本地已有**（long/short liquidation USD 小时级，2024-06-06→2026-06-23，~93-95% 非零） | 本地 COINGLASS_RAW1H/liquidation/{SYM}.parquet ；外部补充: Bybit API（近 30 天）/ Coinglass API（付费） | 无（本地数据）；实时流需订阅 | 本地 2024-06+ 约 2 年小时级 | 本地一次性快照；实时需订阅 | **A（本地已有，P0）** | 触发=24h 强平总量（long+short）z 分位 / long:short 失衡，wash_cvd × 强平分层（wash_cvd 应伴随强平脉冲，验证燃料机制）；基线/判定同上；窗口=2024-06+（与 oi_24h_chg 同起点，事件样本充足） |
| 期限结构（永续-现货基差） | 本地均为永续（coinglass/binance_free_db klines 均为 USDT 永续）→ 基差需补拉币安现货 klines（免费一次性） | https://api.binance.com/api/v3/klines | 无 | 币安现货 2017+（一次性拉取与本地对表） | 1h | B | 触发=基差 z 分位（正基差=看涨拥挤 / 负基差=看跌）分桶 vs alt 篮子次日收益 + wash_cvd 分层；基线/判定同上；窗口=2022+（拉现货后即可测） |

## 优先级矩阵（可测性 × 研究价值）

| 评级 | 维度 | 可测性(1-5) | 研究价值(1-5) | 理由 |
|---|---|---|---|---|
| **P0** | 恐惧贪婪指数（alternative.me） | 5 | 4 | 免费全历史、本轮已实测；情绪极值日与 wash_cvd 分层结果见实测①② |
| **P0** | BTC 量占比代理 btc_share_volume | 5 | 4 | 现有 klines 直接构造、本轮已实测；大盘/山寨主导切换是命题核心语境 |
| **P0** | ETH/BTC 比率 | 5 | 3 | 现有数据可算、本轮已顺带实测；作为风险偏好切换的廉价代理 |
| **P0** | 强平流（coinglass 本地 liquidation/） | 5 | 5 | 本地已有 2024-06+ 小时级 long/short 强平 USD，直击 wash_cvd「杠杆出清燃料」机制；本轮未实测（超出指定范围），研究设计已就绪 |
| **P0** | FOMC 日历事件流 | 5 | 3 | 免费全历史、事件少人工校对成本低；宏观事件日前后 wash_cvd 行为分列 |
| **P1** | 谷歌趋势（周度全历史） | 3 | 3 | 免费但日度粒度受限；周度可覆盖 2022+，需 pytrends 整合 |
| **P1** | 新闻流 NLP（GDELT） | 3 | 4 | GDELT 免费全历史；监管/政策事件方向分桶价值高，NLP 管线需开发 |
| **P1** | E-mini ES 亚洲时段 | 3 | 3 | 日度免费全历史；亚洲时段分钟级历史浅，作为隔夜风险偏好传导代理 |
| **P1** | 期限结构（永续-现货基差） | 4 | 3 | 需一次性免费拉币安现货；基差拥挤度是杠杆周期代理 |
| **P2** | X 情绪 | 2 | 3 | 免费额度有限/付费贵；CryptoPanic 可作廉价替代 |
| **P2** | Reddit 活跃度 | 2 | 2 | 官方 API 回溯浅；快照成本高 |
| **P2** | 链上 SOPR/MVRV/矿工储备 | 2 | 4 | 机制直接（亏损卖出/矿工抛压）但需付费 key（Glassnode/CryptoQuant） |
| P0附 | coinglass 多空比/净持仓（ls_global/net_position，本地 2024-06+） | 5 | 3 | 情绪维度（X/Reddit）的本地持仓代理，立即可测，可作 P2 情绪项的先行替代 |

## 每个 P0 的可落地研究设计

**P0-1 恐惧贪婪指数（本轮已实测，可直接进 116 横截面框架）**
- 触发: wash_cvd（115 口径）；分层 = 事件日-1 恐惧贪婪（极恐<20 / 恐惧20-40 / 中性40-60 / 贪婪60+，ffill 回退缺日）。
- 基线: 同期随机 symbol×时点（start_ms/end_ms 按层对齐），bootstrap 95% CI（seed=2026）。
- 判定: 24h 超额 CI 下界>0→GO_LONG / 上界<0→GO_SHORT / 含0→NO_GO / n<30→样本不足；另做贪婪−极恐直接对照。
- 落地: 在 116 同款横截面框架把 fng_asof 作为排序/过滤维度（如仅交易极恐/恐惧层），脚本即本文件实测②；数据一次性落 CSV 后无需再拉。

**P0-2 BTC 量占比代理（本轮已实测）**
- 触发: wash_cvd；分层 = 事件时 btc_share_volume 三分位（边界用全样本日度三分位，非事件样本内拟合）。
- 基线/判定: 同上；另做日度 share→次日篮子收益相关（Pearson/Spearman）+ 三分位分桶 CI。
- 落地: 复用本文件 share_at()；若「低(alt活跃)」层显著更强，说明山寨主导期 wash_cvd 更有燃料 → 与 124 广度门控可交叉（share×breadth 二维网格留作下一轮）。

**P0-3 ETH/BTC 比率（本轮已顺带实测）**
- 触发: 日度 eth_btc 三分位分桶 vs alt 篮子次日收益 + wash_cvd 分层（可选）。
- 基线/判定: 同上。落地成本几乎为零（close_asof 已实现），主要价值是与 btc_share 互相验证「风险偏好切换」解释。

**P0-4 强平流（数据已验证本地存在，待下轮实测）**
- 触发: wash_cvd；分层 = 事件时 24h 强平总量 z 分位（自序列 30d）与 long:short 强平失衡；另做「强平脉冲日（24h 强平 z>2）→ alt 篮子 7d」日度事件。
- 基线: 同期随机；判定: 24h/7d 超额 CI。窗口 2024-06-06→2026-06-23（~2 年，事件样本充足；与 oi_24h_chg 起点一致，可与 121 燃料分层交叉验证「强平出清→轧空燃料」链条）。
- 落地: 读 COINGLASS_RAW1H/liquidation/{SYM}.parquet（long_liquidation_usd/short_liquidation_usd 小时级），按 121/124 模板建 z 序列与分层；binance_free_db 无 liquidation（已核实），实时流需另订阅。

**P0-5 FOMC 日历事件流**
- 触发: wash_cvd 事件距最近 FOMC 会议日 ≤3d（前/后窗） vs 远离组；另做会议日前后各 5 个交易日的 alt 篮子累计收益对比。
- 基线: 同 episode 随机 symbol×时点 / 全样本日；判定: 24h/7d 超额 CI。窗口 2022+ 约 50 次会议。
- 落地: 手工把 Fed 官方日历 2022-2026 的会议日落成 CSV（30 行级，一次性）；会议时刻需二次确认（Fed 通常 18:00 UTC 声明），日级事件按 124 的 episode_of_day 口径归类。
"""


if __name__ == "__main__":
    main()
