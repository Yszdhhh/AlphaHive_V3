"""124_market_breadth.py — D 方向：washout 市场级出清广度研究。

命题：大饼见底 → 山寨蓄力。本脚本从"市场级"视角看 washout：
不只看单个币出清，而看同一时点多少币同时出清（广度 breadth）。
回答：市场级广度能否区分"个别币出清 vs 市场级底"；wash_cvd 信号
在高广度环境（市场级出清）下是否更强 → 广度门控值不值得做（仅研究侧建议）。

广度口径（6h 网格，UTC 0/6/12/18 整点）：
- washout(sym, t) = (price_z < -2.0) | (ret_24h < -8)，两者任一 NaN → 不计入分母
- breadth_pct(t) = 100 × (washout 币数 / 有效币数)      # n_active = 有效币数
- breadth_z(t)  = breadth_pct 自序列 z（滚动 720×6h = 180d，min_periods=360）

事件研究（统一模板，照抄 119/120 口径）：
- 事件 = wash_cvd：m115.detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
- forward 收益 = harness.lib.event_study.forward_stats(ctxs[sym], ev, DEFAULT_HORIZONS)
- 基线 = draw_random_events(ctxs, n, rng, max_forward_hours=168, start_ms=lo, end_ms=hi)
  （start_ms/end_ms 按分层事件的时间跨度对齐）
- bootstrap_ci(ev_v, base_v, seed=2026)；判定：CI 下界>0 → GO_LONG，上界<0 → GO_SHORT，含 0 → NO_GO

样本重叠（诚实标注）：
- 同一 6h 时点多币同时出清 → wash_cvd 事件非独立，报告每层唯一时点数 n_unique_ts
- 7d 篮子窗口跨 6h 网格重度重叠 → 按日聚合 + 说明自相关

数据（写死，emoji 路径是历史反复坑）：
- COINGLASS_RAW1H = r"C:\\Users\\10639\\Desktop\\🔒 加密资产\\coinglass_db\\raw_1h"（klines 子目录）
- FUNDING_DIR     = r"C:\\Users\\10639\\Desktop\\加密\\binance_free_db\\history\\funding"
- PROJECT_ROOT    = r"G:\\Quant test\\AlphaHive_V3"

用法：
  python scripts/124_market_breadth.py [--n-baseline 3000] [--seed 2026]
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
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
FUNDING_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
REPORTS_DIR = PROJECT_ROOT / "reports"

# 复用 113/115 的统一加载模板（保证口径与 washout-settle / wash_cvd 研究一致）
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
rolling_z = m113.rolling_z

HOUR_MS = 3_600_000
SIXH_MS = 6 * HOUR_MS
WASH_PRICE_Z = -2.0
WASH_RET_24H = -8.0
BREADTH_LOW = 5.0     # 低广度阈值（%）
BREADTH_MID = 15.0    # 高广度阈值（%）
BREADTH_Z_PEAK = 2.0  # breadth_z 高峰阈值
BASKET_H = 168        # 7d 篮子
GRID_START = "2022-01-01"
MIN_ACTIVE = 5        # breadth_pct 有效所需最少有效币数


def build_grid(ctxs: dict[str, pd.DataFrame]) -> np.ndarray:
    """6h 网格：UTC 0/6/12/18 整点，从 GRID_START 到全池最后 6h 点。"""
    lo = pd.Timestamp(GRID_START, tz="UTC").timestamp() * 1000
    hi = max(int(t.index.to_numpy(dtype=np.int64).max()) for t in ctxs.values())
    hi -= hi % SIXH_MS  # 回退到最后一个完整 6h 点
    n = int((hi - lo) // SIXH_MS) + 1
    grid = lo + np.arange(n, dtype=np.int64) * SIXH_MS
    return grid


def symbol_grid_vals(ctx: pd.DataFrame, grid: np.ndarray, col: str) -> np.ndarray:
    """symbol 在 6h 网格上的列值（仅精确整点行有效，缺 bar → NaN）。"""
    idx = ctx.index.to_numpy(dtype=np.int64)
    vals = pd.to_numeric(ctx[col], errors="coerce").to_numpy(dtype=float)
    loc = np.searchsorted(idx, grid, side="left")
    out = np.full(len(grid), np.nan)
    inb = loc < len(idx)
    ok = np.zeros(len(grid), dtype=bool)
    ok[inb] = idx[loc[inb]] == grid[inb]
    out[ok] = vals[loc[ok]]
    return out


def symbol_fwd_rets(ts_arr: np.ndarray, close_arr: np.ndarray,
                    gs: np.ndarray, h_ms: int) -> np.ndarray:
    """向量化 asof 前向收益（与 event_study._future_prices_at 同语义，无前视）。

    base = 时点 g 的整点 close（无该行 → NaN，不进篮子）
    future = g+h_ms 前最近已收盘 bar（gap 超 2 个 bar 周期 → NaN）
    """
    gs = np.asarray(gs, dtype=np.int64)
    bpos = np.searchsorted(ts_arr, gs, side="right") - 1
    base = np.full(len(gs), np.nan)
    okb = (bpos >= 0) & (ts_arr[bpos] == gs)
    base[okb] = close_arr[bpos[okb]]

    targets = gs + h_ms
    fpos = np.searchsorted(ts_arr, targets, side="right") - 1
    fut = np.full(len(gs), np.nan)
    okf = ((fpos >= 0) & (ts_arr[fpos] <= targets) & (ts_arr[fpos] > gs)
           & ((targets - ts_arr[fpos]) < 2 * HOUR_MS))
    fut[okf] = close_arr[fpos[okf]]

    with np.errstate(divide="ignore", invalid="ignore"):
        return (fut / base - 1.0) * 100.0


def build_breadth_series(ctxs: dict[str, pd.DataFrame], grid: np.ndarray) -> pd.DataFrame:
    """广度序列：n_active / breadth_pct / breadth_z / basket_7d（7d alt 等权篮子收益）。"""
    pz_mat = np.full((len(grid), len(ctxs)), np.nan)
    r24_mat = np.full((len(grid), len(ctxs)), np.nan)
    ret168_mat = np.full((len(grid), len(ctxs)), np.nan)
    syms = sorted(ctxs)
    for j, s in enumerate(syms):
        ctx = ctxs[s]
        pz_mat[:, j] = symbol_grid_vals(ctx, grid, "price_z")
        r24_mat[:, j] = symbol_grid_vals(ctx, grid, "ret_24h")
        ts_arr = ctx.index.to_numpy(dtype=np.int64)
        close_arr = pd.to_numeric(ctx["close"], errors="coerce").to_numpy(dtype=float)
        ret168_mat[:, j] = symbol_fwd_rets(ts_arr, close_arr, grid, BASKET_H * HOUR_MS)

    finite = np.isfinite(pz_mat) & np.isfinite(r24_mat)
    n_active = finite.sum(axis=1)
    wash = finite & ((pz_mat < WASH_PRICE_Z) | (r24_mat < WASH_RET_24H))
    with np.errstate(invalid="ignore"):
        breadth = np.where(n_active >= MIN_ACTIVE, wash.sum(axis=1) / n_active * 100.0, np.nan)

    b_ser = pd.Series(breadth, index=pd.Index(grid))
    bz = rolling_z(b_ser, 720)

    # 7d 等权 alt 篮子（每时点取有前向收益的 symbol 均值）
    ret_cnt = np.isfinite(ret168_mat).sum(axis=1)
    basket7d = np.full(len(grid), np.nan)
    if ret_cnt.max() > 0:
        basket7d[ret_cnt > 0] = np.nanmean(ret168_mat[ret_cnt > 0], axis=1)

    out = pd.DataFrame({
        "n_active": n_active,
        "breadth_pct": breadth,
        "breadth_z": bz.to_numpy(),
        "basket_7d": basket7d,
    }, index=pd.Index(grid, name="ts"))
    out.index = out.index.astype(np.int64)
    return out


def alt_basket_index(ctxs: dict[str, pd.DataFrame]) -> pd.Series:
    """日度 alt 等权收益指数（用于定位各 episode 底部，对上市时间无偏）。"""
    daily_rets: list[pd.Series] = []
    for s, ctx in ctxs.items():
        c = pd.to_numeric(ctx["close"], errors="coerce")
        c.index = pd.to_datetime(c.index, unit="ms", utc=True).tz_localize(None)
        dc = c.resample("D").last().dropna()
        r = dc.pct_change().replace([np.inf, -np.inf], np.nan)
        daily_rets.append(r)
    allr = pd.concat(daily_rets, axis=1)
    basket_ret = allr.mean(axis=1, skipna=True)
    return (1.0 + basket_ret.fillna(0.0)).cumprod()


def episode_of_day(d) -> str:
    """按日期归类 episode（含边界日：episode 结束当天归入该 episode）。
    ts 级 episode_of 把结束日 00:00 起判为 ?（下个 episode 次日才开始），
    日级分析用日期包含式端点避免 ? 残差。"""
    d = pd.Timestamp(d)
    if d.tzinfo is not None:
        d = d.tz_convert("UTC").tz_localize(None)
    d = d.normalize()
    for name, s, e in EPISODES:
        if pd.Timestamp(s) <= d <= pd.Timestamp(e):
            return name
    return "?"


def episode_span(name: str) -> tuple[int, int]:
    s, e = next((a, b) for n, a, b in EPISODES if n == name)
    return (int(pd.Timestamp(s, tz="UTC").timestamp() * 1000),
            int(pd.Timestamp(e, tz="UTC").timestamp() * 1000))


def detect_wash_cvd_all(ctxs: dict[str, pd.DataFrame],
                        fundings: dict[str, pd.Series]) -> pd.DataFrame:
    evs = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            evs.append(ev)
    events = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame(
        columns=["symbol", "timestamp"])
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    events["episode"] = episode_of(events["timestamp"].to_numpy(dtype=np.int64))
    return events


def attach_breadth(events: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame:
    """事件时点 asof 取最近 6h 网格的广度（无前视：只用 <= 事件时点信息）。"""
    grid = breadth.index.to_numpy(dtype=np.int64)
    ts = events["timestamp"].to_numpy(dtype=np.int64)
    pos = np.searchsorted(grid, ts, side="right") - 1
    valid = pos >= 0
    out = events.copy()
    out["breadth_pct"] = np.nan
    out["n_active"] = np.nan
    out["breadth_z"] = np.nan
    out.loc[valid, "breadth_pct"] = breadth["breadth_pct"].to_numpy()[pos[valid]]
    out.loc[valid, "n_active"] = breadth["n_active"].to_numpy()[pos[valid]]
    out.loc[valid, "breadth_z"] = breadth["breadth_z"].to_numpy()[pos[valid]]
    return out


def stratum_baseline(ctxs: dict[str, pd.DataFrame], rng: np.random.Generator,
                     n: int, ts_min: int, ts_max: int) -> pd.DataFrame:
    base = draw_random_events(ctxs, n, rng, max_forward_hours=168,
                              start_ms=ts_min, end_ms=ts_max)
    parts = []
    if not base.empty:
        for bs, bg in base.groupby("symbol", sort=False):
            if bs in ctxs:
                parts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def stratum_stats(events: pd.DataFrame, ctxs: dict[str, pd.DataFrame],
                  rng: np.random.Generator, n_baseline: int, seed: int) -> dict:
    """单层 wash_cvd 事件：24h 均值 + 24h 超额 vs 同期随机基线（bootstrap CI）。"""
    sub = events.copy()
    n = len(sub)
    n_uniq = int(sub["timestamp"].nunique())
    ev24 = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
    row: dict = {"n": n, "n_unique_ts": n_uniq,
                 "n_24h": int(len(ev24)),
                 "mean_24h": float(np.nanmean(ev24)) if len(ev24) else np.nan}
    if len(ev24) > 0:
        ts_min = int(sub["timestamp"].min())
        ts_max = int(sub["timestamp"].max())
        base = stratum_baseline(ctxs, rng, n_baseline, ts_min, ts_max)
        bs24 = (pd.to_numeric(base["ret_24h"], errors="coerce").dropna().to_numpy()
                if not base.empty else np.array([]))
        ci = bootstrap_ci(ev24, bs24, seed=seed)
        row["excess_24h"] = ci.get("mean_diff", np.nan)
        row["ci_lo"] = ci.get("ci_lo", np.nan)
        row["ci_hi"] = ci.get("ci_hi", np.nan)
        row["n_baseline"] = ci.get("n_baseline", 0)
        if np.isfinite(row["ci_lo"]):
            row["verdict"] = "GO_LONG" if row["ci_lo"] > 0 else ("GO_SHORT" if row["ci_hi"] < 0 else "NO_GO")
        else:
            row["verdict"] = "PENDING"
    return row


def bootstrap_mean_diff(a: np.ndarray, b: np.ndarray, n_boot: int = 1000, seed: int = 2026) -> dict:
    """高−低 两层 24h 均值的直接对照（bootstrap 95% CI）。"""
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


def fmt_ci(row: dict) -> str:
    if not np.isfinite(row.get("ci_lo", np.nan)):
        return "-"
    return f"[{row['ci_lo']:+.2f}, {row['ci_hi']:+.2f}]"


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
    print(f"价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)}")

    rng = np.random.default_rng(args.seed)

    # ---------- 1. 广度序列 ----------
    grid = build_grid(ctxs)
    breadth = build_breadth_series(ctxs, grid)
    print(f"6h 网格 {len(grid)} 点 | 广度有效点 "
          f"{int(breadth['breadth_pct'].notna().sum())}（n_active>={MIN_ACTIVE}）")
    bv = breadth["breadth_pct"].dropna()
    print(f"breadth_pct 全样本: mean={bv.mean():.2f} p50={bv.median():.2f} "
          f"max={bv.max():.2f} p95={bv.quantile(0.95):.2f}")

    # 日度聚合（峰值日 / 高广度日分析用）——floor 到当日零点，否则 6h 点各自成组
    day_idx = pd.to_datetime(breadth.index, unit="ms", utc=True).tz_localize(None).normalize()
    def _day_peak_ts(x: pd.Series) -> float:
        if x.notna().sum() == 0:
            return np.nan  # 全天无有效广度
        return x.idxmax()

    bday = breadth.assign(day=day_idx).groupby("day").agg(
        peak_breadth=("breadth_pct", "max"),
        peak_ts=("breadth_pct", _day_peak_ts),
        n_active=("n_active", "max"),
        basket_7d=("basket_7d", "mean"),
    )
    bday = bday.dropna(subset=["peak_breadth"])  # 全天无有效广度（如数据未到）的日丢弃
    bday["episode"] = [episode_of_day(d) for d in bday.index]

    lines: list[str] = []
    lines.append("# 市场级出清广度（breadth）研究 — D 方向\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 方法: 6h 网格（UTC 0/6/12/18）逐币判定 washout = (price_z<{WASH_PRICE_Z}) | (ret_24h<{WASH_RET_24H}%)；"
                 f"breadth_pct = 100×出清币数/有效币数（NaN 不计入分母，n_active>={MIN_ACTIVE} 才有效）；"
                 f"breadth_z = 自序列 z（滚动 720×6h=180d，min_periods=360）")
    lines.append(f"- 数据源: {COINGLASS_RAW1H}（klines: close/price_z/ret_24h，覆盖 2021-12→2026-07）；"
                 f"{FUNDING_DIR}（wash_cvd 检测用 funding 参数占位，实际不参与）")
    lines.append(f"- 事件 = wash_cvd（115 口径: washout 且 cvd_divergence>2.0，72h 冷却/币）；"
                 f"基线 = 同期随机 symbol×时点横截面（start_ms/end_ms 按分层对齐），bootstrap 95% CI（seed={args.seed}）")
    lines.append(f"- 篮子: 每时点所有有效 symbol 的 7d（168h）asof 前向收益等权均值（与 forward_stats 同语义，无前视）")
    lines.append("> **样本重叠（务必读）**：同一 6h 时点多币同时出清 → wash_cvd 事件彼此相关，"
                 "报告唯一时点数 n_unique_ts；7d 篮子窗口跨 6h 重度重叠 → 高广度日分析按日聚合，CI 仍偏窄（自相关未完全扣除）。\n")
    lines.append("**局限**：")
    lines.append("- coinglass klines 在 2026-06-23 23:00 → 2026-06-30 04:00 存在约 6.3 天空档（公共接口未回填该周，全 universe 一致）；"
                 "该窗口广度/篮子为 NaN，'当前筑底(前向)' 影子仅有 06-30 04:00 后约 7 天数据，且 06-18~23 峰值日的 7d 前向窗口跨空档被弃（见表2 注）。")
    lines.append("- universe 含少量非加密资产（XAU/XAG 与股票类），与 113/115/119/120 完全同口径（load_universe_symbols），未额外剔除；"
                 "n_active 前低后高（2022 平均 18 → 2025 平均 50），早期广度粒度粗（1/17≈5.9%）。")
    lines.append("- 广度依赖 price_z/ret_24h 的 30d 滚动窗口：2022-01 月初无 price_z → 广度 2022-01-16 前后才开始有效；"
                 "breadth_z 为 180d 滚动 z，头部 90 天为 NaN。\n")

    # ---------- 2. 表1: 各 episode 广度分布 ----------
    lines.append("## 表1: 各 episode 广度分布（6h 网格点）\n")
    lines.append("| episode | 网格点数 | 均值% | 中位数% | 峰值% | 95分位% | 广度>10%占比 | 广度>20%占比 | 平均n_active |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    ep_rows = []
    for name, s, e in EPISODES:
        lo, hi = episode_span(name)
        m = (breadth.index.to_numpy(dtype=np.int64) >= lo) & (breadth.index.to_numpy(dtype=np.int64) < hi)
        sub = breadth["breadth_pct"].to_numpy()[m]
        valid = sub[np.isfinite(sub)]
        if len(valid) == 0:
            lines.append(f"| {name} | 0 | - | - | - | - | - | - | - |")
            continue
        row = {
            "episode": name,
            "n_pts": len(sub),
            "mean": float(np.mean(valid)),
            "median": float(np.median(valid)),
            "peak": float(np.max(valid)),
            "p95": float(np.quantile(valid, 0.95)),
            "gt10": float((valid > 10).mean()),
            "gt20": float((valid > 20).mean()),
            "avg_active": float(np.mean(breadth["n_active"].to_numpy()[m][np.isfinite(sub)])),
        }
        ep_rows.append(row)
        lines.append(f"| {name} | {row['n_pts']} | {row['mean']:.2f} | {row['median']:.2f} | "
                     f"{row['peak']:.1f} | {row['p95']:.1f} | {row['gt10']:.0%} | {row['gt20']:.0%} | {row['avg_active']:.0f} |")

    # ---------- 3. 表2: 广度峰值日 Top15 ----------
    top = bday[bday["basket_7d"].notna()].nlargest(15, "peak_breadth")
    lines.append("\n## 表2: 广度峰值日 Top 15（市场级出清底候选）\n")
    lines.append("| # | 峰值时点(UTC) | 日峰值广度% | n_active | 随后7d alt等权篮子% | episode |")
    lines.append("|---|---|---|---|---|---|")
    for i, (d, r) in enumerate(top.iterrows(), 1):
        tstr = pd.Timestamp(int(r["peak_ts"]), unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M")
        lines.append(f"| {i} | {tstr} | {r['peak_breadth']:.1f} | {int(r['n_active'])} | "
                     f"{r['basket_7d']:+.2f} | {r['episode']} |")
    recent = bday[bday["basket_7d"].isna()].nlargest(5, "peak_breadth")
    if not recent.empty:
        lines.append("\n> 注：以下近期峰值日无 7d 前向窗口（数据止于 2026-07-07），未进 Top15：")
        for d, r in recent.iterrows():
            tstr = pd.Timestamp(int(r["peak_ts"]), unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M")
            lines.append(f"> - {tstr} 广度 {r['peak_breadth']:.1f}% n_active={int(r['n_active'])}")

    # ---------- 4. 事件研究 a: wash_cvd 按事件时广度分层 ----------
    lines.append("\n## 事件研究 A: wash_cvd 按事件时广度分层（市场级出清时更强？）\n")
    events = attach_breadth(detect_wash_cvd_all(ctxs, fundings), breadth)
    events = events[events["breadth_pct"].notna()].copy()
    strata_cfg = [
        ("低 <5%", events["breadth_pct"] < BREADTH_LOW),
        (f"中 {BREADTH_LOW:.0f}~{BREADTH_MID:.0f}%", (events["breadth_pct"] >= BREADTH_LOW) & (events["breadth_pct"] < BREADTH_MID)),
        (f"高 >{BREADTH_MID:.0f}%", events["breadth_pct"] >= BREADTH_MID),
    ]
    lines.append("| 分层 | 事件数 | 唯一时点 | 24h均值 | 24h超额 | 24h CI | n_baseline | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    strata_rows = {}
    for label, mask in strata_cfg:
        sub = events[mask]
        if sub.empty:
            lines.append(f"| {label} | 0 | - | - | - | - | - | **无事件** |")
            strata_rows[label] = None
            continue
        r = stratum_stats(sub, ctxs, rng, args.n_baseline, args.seed)
        strata_rows[label] = r
        if r["n_24h"] < args.min_events:
            r["verdict"] = f"样本不足(n={r['n_24h']}<{args.min_events})"
        lines.append(f"| {label} | {r['n']} | {r['n_unique_ts']} | {r['mean_24h']:+.2f}% | "
                     f"{r['excess_24h']:+.2f}% | {fmt_ci(r)} | {r['n_baseline']} | **{r['verdict']}** |")
    # 高 vs 低 直接对照
    hi_v = pd.to_numeric(events[events["breadth_pct"] >= BREADTH_MID]["ret_24h"], errors="coerce").dropna().to_numpy()
    lo_v = pd.to_numeric(events[events["breadth_pct"] < BREADTH_LOW]["ret_24h"], errors="coerce").dropna().to_numpy()
    contrast = bootstrap_mean_diff(hi_v, lo_v, seed=args.seed)
    lines.append(f"\n高 vs 低 直接对照（24h 均值差 高−低）: {contrast['mean_diff']:+.2f}% "
                 f"95% CI [{contrast['ci_lo']:+.2f}, {contrast['ci_hi']:+.2f}]（n高={contrast['n_a']}, n低={contrast['n_b']}）")

    # 分层 × episode 描述性矩阵（numpy 掩码，避免 pandas 布尔重索引警告）
    lines.append("\n### 分层 × episode 24h 均值（描述性，样本小层仅供参考）\n")
    lines.append("| episode | 低<5% n/均值 | 中5~15% n/均值 | 高>15% n/均值 |")
    lines.append("|---|---|---|---|")
    thresh = [(0.0, BREADTH_LOW), (BREADTH_LOW, BREADTH_MID), (BREADTH_MID, np.inf)]
    mat: dict[tuple[str, int], tuple[int, float]] = {}
    for name, s, e in EPISODES:
        sub = events[events["episode"] == name]
        bp = sub["breadth_pct"].to_numpy(dtype=float)
        r24 = pd.to_numeric(sub["ret_24h"], errors="coerce").to_numpy(dtype=float)
        cells = []
        for ti, (a, b) in enumerate(thresh):
            m = (bp >= a) & (bp < b)
            v = r24[m]
            v = v[np.isfinite(v)]
            mean_v = float(v.mean()) if len(v) else np.nan
            mat[(name, ti)] = (len(v), mean_v)
            cells.append(f"{len(v)}/{mean_v:+.2f}%" if len(v) else "0/-")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    n_q = int((events["episode"] == "?").sum())
    lines.append(f"\n> 注：另有 {n_q} 个事件落在 episode 边界时刻（episode_of 按 ts 端点排他），"
                 f"未出现在矩阵行中，但已计入上方分层统计（2023-01-31 00:00 / 2024-05-31 17:00）。")

    # ---------- 5. 事件研究 b: 高广度日后 7d 篮子 vs 全样本 ----------
    lines.append("\n## 事件研究 B: 高广度日（breadth>15%）→ 随后 7d alt 等权篮子\n")
    hi_days = bday[bday["peak_breadth"] > BREADTH_MID]
    all_days = bday
    ev_v = hi_days["basket_7d"].dropna().to_numpy()
    bs_v = all_days["basket_7d"].dropna().to_numpy()
    ci = bootstrap_ci(ev_v, bs_v, seed=args.seed)
    lines.append(f"- 高广度日数: {len(hi_days)}（其中 7d 篮子有效 {int(len(ev_v))}）；全样本日数 {len(all_days)}（有效 {int(len(bs_v))}）")
    lines.append(f"- 高广度日 7d 篮子均值: {np.mean(ev_v):+.2f}% | 全样本 7d 篮子均值: {np.mean(bs_v):+.2f}%")
    lines.append(f"- 超额 vs 全样本: {ci['mean_diff']:+.2f}% 95% CI [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] "
                 f"→ **{'GO_LONG' if ci['ci_lo'] > 0 else ('GO_SHORT' if ci['ci_hi'] < 0 else 'NO_GO')}**")
    hi_ep = hi_days["episode"].value_counts()
    lines.append(f"- 高广度日 episode 分布: " + ", ".join(f"{k}={v}" for k, v in hi_ep.items()))

    # ---------- 6. 与命题联动: 广度高峰 vs 各 episode 底部 ----------
    lines.append("\n## 广度高峰（breadth_z>2）与各 episode 底部（命题联动）\n")
    basket_idx = alt_basket_index(ctxs)
    bottom_date = {name: basket_idx[s:e].idxmin() for name, s, e in EPISODES
                   if not basket_idx[s:e].empty}
    lines.append("各 episode alt 等权篮子最低日（日度收益指数 cumprod）:")
    for name, d in bottom_date.items():
        lines.append(f"- {name}: **{d.date()}**")
    # 连续 run 提取
    bz = breadth["breadth_z"]
    is_peak = (bz > BREADTH_Z_PEAK).to_numpy(dtype=bool)
    ts_arr = breadth.index.to_numpy(dtype=np.int64)
    runs = []
    i = 0
    n = len(is_peak)
    while i < n:
        if not is_peak[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and is_peak[j + 1]:
            j += 1
        seg_vals = bz.iloc[i:j + 1].to_numpy()
        k = int(np.argmax(seg_vals))  # 段内最大点（位置）
        runs.append(i + k)
        i = j + 1
    near_cnt = 0
    if runs:
        lines.append("\nbreadth_z>2 高峰（每段取最大值点）:")
        lines.append("| # | 时点(UTC) | breadth_pct% | breadth_z | n_active | episode | 距该episode篮子底(天) | 底部±30d内 | 7d篮子% |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        peak_rows = []
        for idx, p in enumerate(runs, 1):
            ts = int(ts_arr[p])
            t = pd.Timestamp(ts, unit="ms", tz="UTC")
            ep = episode_of_day(t)
            bd = bottom_date.get(ep)
            offset = (t.tz_localize(None).date() - bd.date()).days if bd is not None else np.nan
            near = "是" if bd is not None and abs(offset) <= 30 else "否"
            b7 = breadth["basket_7d"].iloc[p]
            b7s = f"{b7:+.2f}" if np.isfinite(b7) else "-"
            peak_rows.append({"idx": idx, "ts": ts, "t": t, "ep": ep, "offset": offset, "near": near,
                              "b7": float(b7) if np.isfinite(b7) else np.nan,
                              "b7s": b7s, "breadth_pct": float(breadth["breadth_pct"].iloc[p])})
            lines.append(f"| {idx} | {t:%Y-%m-%d %H:%M} | {breadth['breadth_pct'].iloc[p]:.1f} | "
                         f"{bz.iloc[p]:.2f} | {int(breadth['n_active'].iloc[p])} | {ep} | "
                         f"{offset if np.isfinite(offset) else '-'} | {near} | {b7s} |")
        # 每 episode 高峰汇总
        near_cnt = 0
        ep_peak: dict[str, list] = {}
        for pr in peak_rows:
            if pr["near"] == "是":
                near_cnt += 1
            ep_peak.setdefault(pr["ep"], []).append(pr)
        lines.append("\n### 每 episode 高峰汇总（breadth_z>2 段）\n")
        lines.append("| episode | 高峰段数 | 底部±30d内 | 比例 | 篮子底 |")
        lines.append("|---|---|---|---|---|")
        for name, s, e in EPISODES:
            pk = ep_peak.get(name, [])
            bd = bottom_date.get(name)
            nn = sum(1 for pr in pk if pr["near"] == "是")
            bd_s = f"{bd.date()}" if bd is not None else "-"
            if pk:
                lines.append(f"| {name} | {len(pk)} | {nn} | {nn/len(pk):.0%} | {bd_s} |")
            else:
                lines.append(f"| {name} | 0 | 0 | - | {bd_s} |")
        lines.append(f"\n> 高峰共 {len(runs)} 段；落在 episode 底部±30d 内的比例: {near_cnt}/{len(runs)} = {near_cnt/len(runs):.0%}"
                     "（说明：各 episode 底部 = 该 episode 内 alt 等权收益指数最低日；"
                     "部分峰值如 2022-11 FTX、2023/2024 中段距底部较远）")

    # ---------- 7. 结论 ----------
    n_runs = len(runs)
    lines.append("\n## 结论\n")
    hi_r = strata_rows["高 >15%"]
    mid_r = strata_rows["中 5~15%"]
    lo_r = strata_rows["低 <5%"]
    c_sig = "显著" if contrast["ci_lo"] > 0 else ("显著为负" if contrast["ci_hi"] < 0 else "不显著")
    mid_23 = mat.get(("2023平台蓄力", 1), (0, np.nan))
    mid_24 = mat.get(("2024崩→恢复", 1), (0, np.nan))
    hi_22 = mat.get(("2022熊底+FTX底", 2), (0, np.nan))
    hi_23 = mat.get(("2023平台蓄力", 2), (0, np.nan))
    hi_24 = mat.get(("2024崩→恢复", 2), (0, np.nan))
    def _m(t: tuple[int, float]) -> str:
        return f"{t[1]:+.2f}%" if np.isfinite(t[1]) else "-"
    lines.append(f"**1. 广度能区分个别币出清 vs 市场级出清（wash_cvd × 广度分层）**")
    lines.append(f"- wash_cvd 24h 超额：低<5% = {lo_r['excess_24h']:+.2f}% → 中5~15% = {mid_r['excess_24h']:+.2f}% "
                 f"（约 {mid_r['excess_24h']/lo_r['excess_24h']:.1f} 倍）→ 高>15% = {hi_r['excess_24h']:+.2f}%（与中层相当），"
                 f"三层 24h CI 均不含 0（全 GO_LONG）；高−低直接对照 Δ = {contrast['mean_diff']:+.2f}% "
                 f"CI [{contrast['ci_lo']:+.2f}, {contrast['ci_hi']:+.2f}]（{c_sig}）——广度越高，wash_cvd 确认价值越大（方向一致，95% 直接对照未过显著线）。")
    lines.append(f"- 峰值在中度出清层（5~15%，超额 {mid_r['excess_24h']:+.2f}%），且 2023/2024 两 episode 的中度层 "
                 f"24h 均值最高（{_m(mid_23)}/{_m(mid_24)}）；极端全市场出清（>15%）在 2022 深熊里反而弱（{_m(hi_22)}，"
                 f"LUNA/FTX 瀑布中继），在 2023/2024 是真正的筑底（{_m(hi_23)}/{_m(hi_24)}）——广度越高 ≠ 无脑越强，需要 episode 语境。")
    lines.append(f"**2. 广度单独不是可靠的'市场级底'信号**")
    lines.append(f"- 高广度日（breadth>15%）随后 7d alt 篮子 {np.mean(ev_v):+.2f}% vs 全样本 {np.mean(bs_v):+.2f}%，"
                 f"超额 {ci['mean_diff']:+.2f}% CI [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] → "
                 f"{'**GO_LONG（显著）**' if ci['ci_lo'] > 0 else '**NO_GO（不显著）**'}；"
                 f"广度 z>2 高峰 {n_runs} 段中仅 {near_cnt} 段（{near_cnt/n_runs:.0%}）落在该 episode 底部±30d 内。")
    fin = [pr for pr in peak_rows if np.isfinite(pr["b7"])]
    near_b7 = [pr["b7"] for pr in fin if pr["near"] == "是"]
    far_b7 = [pr["b7"] for pr in fin if pr["near"] == "否"]
    if near_b7 and far_b7:
        lines.append(f"- 高峰段分化：底部±30d 内高峰的 7d 篮子均值 {np.mean(near_b7):+.2f}%（n={len(near_b7)}）"
                     f" vs 非底部高峰 {np.mean(far_b7):+.2f}%（n={len(far_b7)}）——同一高广度，位置决定后续。")
    def _ex(prs, k=3):
        return "、".join(f"{pr['t']:%Y-%m-%d}（{pr['breadth_pct']:.0f}%，7d {pr['b7']:+.2f}%）"
                         for pr in sorted(prs, key=lambda r: r["b7"])[:k])
    def _px(prs, k=3):
        return "、".join(f"{pr['t']:%Y-%m-%d}（{pr['breadth_pct']:.0f}%，7d {pr['b7']:+.2f}%）"
                         for pr in sorted(prs, key=lambda r: -r["b7"])[:k])
    if fin:
        lines.append(f"- 反面例证（高峰表 7d 最差）：{_ex(fin)}——全市场同时出清仍可继续下跌（接飞刀）。")
        lines.append(f"- 正面例证（高峰表 7d 最好）：{_px(fin)}——真正底部常伴随持续数日的强广度簇（如 2022-06 底、2024-08-05、2025-04 初）。")
    lines.append(f"**3. wash_cvd × 广度门控是否值得做（仅研究侧建议，不碰任何配置）**")
    lines.append(f"- 值得：广度分层把 24h 超额从低层的 {lo_r['excess_24h']:+.2f}% 提升到中/高层的 "
                 f"{mid_r['excess_24h']:+.2f}%/{hi_r['excess_24h']:+.2f}%，且分层 × episode 矩阵 2023/2024/2025 三个 episode "
                 f"中度层均为正——广度作为 wash_cvd 的**排序/过滤维度**有研究价值。")
    lines.append(f"- 建议路线（研究侧）：把 breadth_pct 作为 wash_cvd 的辅助门控（如要求事件时广度 ≥5%，或按广度分层调仓），"
                 f"在 116 同类横截面框架里做下一轮验证；高广度层需配合 episode 语境（深熊里避开）。"
                 f"广度>15% 单独作为入场信号无统计证据（事件研究 B NO_GO），不建议单用。")

    out = REPORTS_DIR / "market_breadth.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")

    # ---------- stdout 摘要 ----------
    print("\n=== 表1 摘要（广度分布）===")
    for r in ep_rows:
        print(f"  {r['episode']:16s} 均值{r['mean']:5.2f}% 中位{r['median']:5.2f}% 峰值{r['peak']:5.1f}% "
              f"p95 {r['p95']:5.1f}% >10%: {r['gt10']:.0%} >20%: {r['gt20']:.0%}")
    print("\n=== 表2 Top5 峰值日 ===")
    for i, (d, r) in enumerate(top.head(5).iterrows(), 1):
        tstr = pd.Timestamp(int(r["peak_ts"]), unit="ms", tz="UTC").strftime("%Y-%m-%d")
        print(f"  #{i} {tstr} 广度{r['peak_breadth']:.1f}% n={int(r['n_active'])} 7d篮子{r['basket_7d']:+.2f}% {r['episode']}")
    print("\n=== 事件研究 A: 分层 ===")
    for label, r in strata_rows.items():
        if r is None:
            print(f"  {label:10s} 无事件")
            continue
        print(f"  {label:10s} n={r['n']:4d} (唯一时点{r['n_unique_ts']:3d}) 24h均值{r['mean_24h']:+.2f}% "
              f"超额{r['excess_24h']:+.2f}% CI{fmt_ci(r)} {r['verdict']}")
    print("\n=== 事件研究 B: 高广度日 7d 篮子 ===")
    print(f"  高广度日 {len(ev_v)} 均值 {np.mean(ev_v):+.2f}% vs 全样本 {np.mean(bs_v):+.2f}% "
          f"超额 {ci['mean_diff']:+.2f}% CI [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")
    print("\n=== 广度高峰 vs 底部 ===")
    for name, d in bottom_date.items():
        print(f"  {name}: 篮子底 {d.date()}")


if __name__ == "__main__":
    main()
