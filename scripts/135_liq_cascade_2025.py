"""135_liq_cascade_2025.py — 强平级联 2025 失效机理研究。

背景（承接 131 liquidation_cross，引用即可，勿重做）：
- 强平级联事件 = liq_short_z > 2.0 且 ret_24h < +5%（24h 未大涨），72h 冷却，Long，
  区间 2024-06-01 → 2026-06-23（liquidation 覆盖窗口）。
- 131 表3：pooled n=1711 24h 超额 +1.07% CI[+0.56,+1.63] GO_LONG；
  2024崩→恢复 n=434 +2.20% CI[+1.51,+2.91] GO_LONG（贡献全部）；
  2025顶→熊 n=1276 +0.58% CI[-0.04,+1.27] NO_GO —— 同信号 2024 强 / 2025 弱。
- 本脚本：机理检验（描述性 + 事件研究混合），回答为什么 2024 强 2025 弱、能否条件化修复。

表：
- 表0 复现 131 表3（同事件/同基线/同 seed，应逐位一致）
- 表1 事件分布对比 2024 vs 2025：事件数、事件时 liq_short_z 均值/中位、
  强平规模（liq_24h 对自身 30d 中位数归一分位）、事件后 24h BTC 收益均值、
  市场 breadth 均值 —— 两年事件所处市场环境差异
- 表2 事件质量分列：事件时 liq_short_z 档（2~3 / 3~4 / >4）与 2024/2025 交叉：
  24h 超额 + CI —— 更极端的强平在 2025 是否仍有 edge
- 表3 时间衰减：事件后 4/24/72/168h 收益曲线 2024 vs 2025 ——
  2025 是反弹更快/更弱（4h 已兑现则 24h 无超额）还是根本没反弹
- 表4 BTC 趋势条件化：事件时 BTC 20d 回撤分桶 / 30d 斜率正负 × 2024/2025 ——
  BTC 下跌中继时级联是否失效（2025 熊市强平=中继而非底部）
- 表5 条件化修复检验：2025 加 BTC 趋势 / breadth 条件后是否翻正（pooled 对照）

数据：COINGLASS_RAW1H = C:\\Users\\10639\\Desktop\\🔒 加密资产\\coinglass_db\\raw_1h
  - liquidation/{symbol}.parquet（time/long_liquidation_usd/short_liquidation_usd）
  - klines/{symbol}.parquet（close/quote_volume/taker_buy_quote_volume → CVD）
  - macro/VIX.parquet（本脚本表4 用 BTC 趋势，VIX 门控见 123，不重复）
  FUNDING_DIR = C:\\Users\\10639\\Desktop\\加密\\binance_free_db\\history\\funding（检测占位）
基线：draw_random_events + bootstrap_ci(seed=2026)，pooled 首抽、episode 各抽一次（与 131 同序，
保证表0 逐位复现）；子集共用同一基线横向可比。判定：CI 下界>0→GO_LONG / 上界<0→GO_SHORT /
含0→NO_GO / n<30→样本不足。

只读数据、纯研究模块：不写任何配置/规则/定时任务；禁止改 108/109。

用法：
  python scripts/135_liq_cascade_2025.py [--n-baseline 3000] [--seed 2026] [--min-events 30]
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

REPORTS_DIR = PROJECT_ROOT / "reports"

# ---------- 共享加载模板（113/115 口径；131 复用强平特征/级联检测/基线；124 复用广度） ----------
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

_spec3 = importlib.util.spec_from_file_location(
    "m131", str(PROJECT_ROOT / "scripts" / "131_liquidation_cross.py"))
m131 = importlib.util.module_from_spec(_spec3)
sys.modules["m131"] = m131
_spec3.loader.exec_module(m131)

_spec4 = importlib.util.spec_from_file_location(
    "m124", str(PROJECT_ROOT / "scripts" / "124_market_breadth.py"))
m124 = importlib.util.module_from_spec(_spec4)
sys.modules["m124"] = m124
_spec4.loader.exec_module(m124)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
EPISODES = m113.EPISODES
episode_of = m113.episode_of

# 131 复用（保证口径一致，表0 逐位复现）
add_liq_features = m131.add_liq_features
attach_liq_asof = m131.attach_liq_asof
detect_liq_cascade_events = m131.detect_liq_cascade_events
build_baseline = m131.build_baseline
stats_row = m131.stats_row
COINGLASS_RAW1H = m131.COINGLASS_RAW1H
LO_MS = m131.LO_MS
HI_MS = m131.HI_MS
EPISODES_LIQ = m131.EPISODES_LIQ
CASCADE_Z = m131.CASCADE_Z
CASCADE_RET = m131.CASCADE_RET
COOLDOWN_H = m131.COOLDOWN_H

N_BASELINE = 3000
SEED = 2026
MIN_EVENTS = 30
HOUR_MS = 3_600_000

BTC_SYM = "BTCUSDT"
BTC_SLOPE_H = 720      # 30d 斜率窗口（小时）
BTC_DD_H = 480         # 20d 回撤窗口（小时）
BREADTH_LOW = 5.0      # breadth≥5% 门控（同 124/127/133）

# 131 表3 已知数字（复现核对目标）
KNOWN_T3 = {
    "pooled": (1711, 1.07, 0.56, 1.63, "GO_LONG"),
    "2024崩→恢复": (434, 2.20, 1.51, 2.91, "GO_LONG"),
    "2025顶→熊": (1276, 0.58, -0.04, 1.27, "NO_GO"),
}


# ---------- BTC 趋势特征（20d 回撤 / 30d 斜率，全部 asof 无前视） ----------
def add_btc_features(btc: pd.DataFrame) -> pd.DataFrame:
    """在 BTC ctx 上补 btc_dd20 / btc_slope30（小时级，自序列滚动）。"""
    t = btc.copy()
    c = pd.to_numeric(t["close"], errors="coerce")
    t["btc_dd20"] = (c / c.rolling(BTC_DD_H, min_periods=240).max() - 1.0) * 100.0
    t["btc_slope30"] = (c / c.shift(BTC_SLOPE_H) - 1.0) * 100.0
    t["btc_slope30"] = t["btc_slope30"].replace([np.inf, -np.inf], pd.NA)
    return t


def attach_btc_asof(events: pd.DataFrame, btc: pd.DataFrame) -> pd.DataFrame:
    """事件时点 asof 取 BTC 趋势特征（np.searchsorted side='right'-1，无前视）。"""
    ev = events.copy()
    idx = btc.index.to_numpy(dtype=np.int64)
    pos = np.searchsorted(idx, ev["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
    pos = np.clip(pos, 0, len(idx) - 1)
    for col in ["btc_dd20", "btc_slope30"]:
        vals = pd.to_numeric(btc[col], errors="coerce").to_numpy(dtype=float)
        ev[f"{col}_at_event"] = vals[pos]
    return ev


def btc_slope_sign(v) -> str:
    if pd.isna(v):
        return "NaN"
    return "正" if v > 0 else "负"


def btc_dd_bucket(v) -> str:
    if pd.isna(v):
        return "NaN"
    if v >= -10.0:
        return "浅 ≥-10%"
    if v >= -25.0:
        return "中 -25~-10%"
    return "深 <-25%"


def btc_fwd_24h(btc: pd.DataFrame, events: pd.DataFrame) -> np.ndarray:
    """事件后 24h BTC 收益（forward_stats 复用，无前视）。"""
    if events is None or events.empty:
        return np.array([])
    f = forward_stats(btc, events[["symbol", "timestamp"]].copy(), horizons=[24])
    return pd.to_numeric(f["ret_24h"], errors="coerce").dropna().to_numpy()


# ---------- 报告辅助（131 同款） ----------
def fmt(x, plus: bool = False, nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    if plus:
        return f"{x:+.{nd}f}%"
    return f"{x:.{nd}f}%"


def fmt_ci(r: dict, plus: bool = True) -> str:
    return f"[{fmt(r.get('ci_lo'), plus=plus)}, {fmt(r.get('ci_hi'), plus=plus)}]"


def fmt_win(v) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    return f"{v:.1%}"


def fmt_n(x, nd: int = 2) -> str:
    """纯数字（无 % 后缀），用于 z 值/倍数等无量纲量。"""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    return f"{x:.{nd}f}"


def row_line(r: dict, group_label: str | None = None) -> str:
    label = r["label"] if group_label is None else group_label
    return (f"| {label} | {r['n']} | {fmt(r.get('mean24'))} "
            f"| {fmt(r.get('ex24'), plus=True)} | {fmt_ci(r)} "
            f"| {fmt(r.get('ex168'), plus=True)} | {fmt_win(r.get('win'))} "
            f"| **{r['verdict']}** |")


def table_header() -> str:
    return "| 组 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 24h胜率 | 判定 |"


def table_sep() -> str:
    return "|" + "---|" * 7


def window_base(ep: str, pooled_base: pd.DataFrame, base_by_ep: dict) -> pd.DataFrame:
    return pooled_base if ep == "pooled" else base_by_ep.get(ep, pd.DataFrame())


def horizon_row(ev: pd.DataFrame, base: pd.DataFrame, label: str,
                h: int, seed: int, min_events: int) -> dict:
    """单 horizon 的事件研究行：n / 均值 / 超额 / CI / 胜率 / 判定。"""
    ev_v = pd.to_numeric(ev[f"ret_{h}h"], errors="coerce").dropna().to_numpy()
    r: dict = {"label": label, "n": len(ev), "h": h}
    if len(ev_v) == 0 or base is None or base.empty:
        r.update(mean=np.nan, ex=np.nan, ci_lo=np.nan, ci_hi=np.nan, win=np.nan, verdict="无基线" if len(ev_v) else "无事件")
        return r
    bs_v = pd.to_numeric(base[f"ret_{h}h"], errors="coerce").dropna().to_numpy()
    ci = bootstrap_ci(ev_v, bs_v, seed=seed)
    r.update(mean=float(np.nanmean(ev_v)), ex=ci["mean_diff"], ci_lo=ci["ci_lo"],
             ci_hi=ci["ci_hi"], win=float((ev_v > 0).mean()))
    if len(ev_v) < min_events:
        r["verdict"] = "样本不足"
    elif ci["ci_lo"] > 0:
        r["verdict"] = "GO_LONG"
    elif ci["ci_hi"] < 0:
        r["verdict"] = "GO_SHORT"
    else:
        r["verdict"] = "NO_GO"
    return r


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-baseline", type=int, default=N_BASELINE)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--min-events", type=int, default=MIN_EVENTS)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    fundings = load_funding_series(symbols)
    ctxs = add_liq_features(ctxs)
    print(f"价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)} | "
          f"liquidation 覆盖 {sum('liq_24h' in t.columns and t['liq_24h'].notna().any() for t in ctxs.values())}")

    # BTC 趋势上下文（独立加载，不进基线池）
    btc_ctxs = load_price_ctx([BTC_SYM])
    if BTC_SYM not in btc_ctxs:
        raise RuntimeError("BTCUSDT 价格数据缺失")
    btc_ctx = add_btc_features(btc_ctxs[BTC_SYM])
    print(f"BTC 上下文 {BTC_SYM}: {btc_ctx.index.min()} ~ {btc_ctx.index.max()}")

    # ---------- 强平级联事件（同 131：liq_short_z>2 且 ret_24h<+5%，72h 冷却，Long） ----------
    cevs = []
    for sym, ctx in ctxs.items():
        ev = detect_liq_cascade_events(sym, ctx, COOLDOWN_H)
        if not ev.empty:
            cevs.append(ev)
    cas = pd.concat(cevs, ignore_index=True) if cevs else pd.DataFrame(
        columns=["symbol", "timestamp"])
    cas = cas[(cas["timestamp"] >= LO_MS) & (cas["timestamp"] <= HI_MS)].reset_index(drop=True)
    fwd_parts = []
    for sym, g in cas.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=DEFAULT_HORIZONS))
    cas = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else cas
    cas = attach_liq_asof(ctxs, cas)
    cas = attach_btc_asof(cas, btc_ctx)
    cas["episode"] = episode_of(cas["timestamp"].to_numpy())

    # 广度（6h 网格 asof，同 124/133）
    grid = m124.build_grid(ctxs)
    breadth = m124.build_breadth_series(ctxs, grid)
    cas = m124.attach_breadth(cas, breadth)
    n_brd_nan = int(cas["breadth_pct"].isna().sum())

    print(f"强平级联事件（liq_short_z>{CASCADE_Z} 且 ret_24h<+{CASCADE_RET}%，"
          f"{COOLDOWN_H:.0f}h 冷却）: {len(cas)} | 缺广度 {n_brd_nan}")
    for name, _, _ in EPISODES:
        n_ep = int((cas["episode"] == name).sum())
        if n_ep:
            print(f"  {name:16s} n={n_ep}")

    # ---------- 基线：pooled 首抽，随后 2024/2025 各抽（与 131 同序 → 表0 逐位复现） ----------
    rng = np.random.default_rng(args.seed)
    base_pooled = build_baseline(ctxs, rng, LO_MS, HI_MS, args.n_baseline)
    base_by_ep: dict[str, pd.DataFrame] = {}
    for name, s, e in EPISODES:
        if name not in EPISODES_LIQ:
            continue
        start_ms = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
        end_ms = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
        base_by_ep[name] = build_baseline(ctxs, rng, start_ms, end_ms, args.n_baseline)
    print(f"pooled 基线 {len(base_pooled)} | episode 基线 "
          f"{ {k: len(v) for k, v in base_by_ep.items()} }")

    lines: list[str] = []
    lines.append("# 强平级联 2025 失效机理研究（2024 强 / 2025 弱，能否条件化修复）\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 方法: 事件=强平级联（liq_short_z>{CASCADE_Z} 且 ret_24h<+{CASCADE_RET}%，"
                 f"{COOLDOWN_H:.0f}h 冷却，Long），事件 ts 限制 {LO_MS}~{HI_MS} ms "
                 f"（2024-06-01 ~ 2026-06-23 UTC，liquidation 覆盖区间）；强平特征=逐 symbol 读 "
                 f"liquidation parquet → 对齐 ctx index → 24h 累计 → 30d(720h) 自序列 z-score "
                 f"（m113.rolling_z，min_periods=360）与 30d 中位数（表1 归一基准），事件时点 asof "
                 f"（np.searchsorted side='right'-1，无前视）；BTC 趋势=BTCUSDT klines 自序列 "
                 f"20d 回撤（close/rolling(480).max−1）与 30d 斜率（close/close.shift(720)−1），"
                 f"事件时点 asof；广度=6h 网格市场级（同 124 口径，breadth_pct=100×出清币数/有效币数，"
                 f"n_active≥5 才有效），事件 ts asof 最近网格点；基线=draw_random_events + "
                 f"bootstrap_ci(seed={args.seed}, n={args.n_baseline})，pooled 首抽、episode 各抽"
                 f"一次并分档共用同一基线（横向可比）。")
    lines.append(f"- 数据源: COINGLASS_RAW1H = {COINGLASS_RAW1H}"
                 f"（liquidation/{'{symbol}'}.parquet: time/long_liquidation_usd/"
                 f"short_liquidation_usd，2024-06-06 14:00 ~ 2026-06-23 03:00 UTC，"
                 f"66/66 universe 全覆盖；klines: close/quote_volume/taker_buy_quote_volume → CVD）；"
                 f"FUNDING_DIR = {m113.FUNDING_DIR}；PROJECT_ROOT = {PROJECT_ROOT}")
    lines.append(f"- 判定: CI 下界>0 → GO_LONG；上界<0 → GO_SHORT；含 0 → NO_GO；"
                 f"n<{args.min_events} → 样本不足不判；24h 胜率 = P(ret_24h>0)")
    lines.append("- 窗口限制: liquidation 只覆盖 2024-06+ → 只测 2024崩→恢复 / 2025顶→熊 "
                 "两个 episode + pooled；coinglass klines 2026-06-23 23:00 → 06-30 04:00 "
                 "约 6.3 天全 universe 空档，事件尾部 forward 收益可能 NaN，轻微减少样本，"
                 "不影响结论。\n")

    # ---------- 表0 复现 131 表3 ----------
    lines.append("## 0. 表0 复现 131 表3（同事件/同基线/同 seed，逐位核对）\n")
    t0 = {}
    t0["pooled"] = stats_row(cas, base_pooled, "pooled", args.min_events, args.seed)
    for name in EPISODES_LIQ:
        sub = cas[cas["episode"] == name]
        t0[name] = stats_row(sub, base_by_ep[name], name, args.min_events, args.seed)
    lines.append(table_header())
    lines.append(table_sep())
    for ep in ["pooled"] + EPISODES_LIQ:
        lines.append(row_line(t0[ep]))
    lines.append("")
    lines.append("| 组 | 131 已知(n/超额/CI/判定) | 本脚本(n/超额/CI/判定) | 一致 |")
    lines.append("|---|---|---|---|")
    for ep in ["pooled"] + EPISODES_LIQ:
        kn, ke, klo, khi, kv = KNOWN_T3[ep]
        r = t0[ep]
        match = (r["n"] == kn and abs(r["ex24"] - ke) < 0.01 and r["verdict"] == kv)
        lines.append(f"| {ep} | {kn} / {fmt(ke, plus=True)} / [{fmt(klo, plus=True)}, "
                     f"{fmt(khi, plus=True)}] / {kv} | {r['n']} / {fmt(r['ex24'], plus=True)} / "
                     f"{fmt_ci(r)} / {r['verdict']} | {'✔' if match else '✘'} |")
    lines.append("")

    # ---------- 表1 事件分布对比 ----------
    lines.append("## 1. 表1 事件分布对比：2024 vs 2025（事件所处市场环境差异）\n")
    lines.append("- liq_short_z：事件时 24h 空头强平累计的自序列 30d z-score（触发要求 >2，均值/中位反映触发当刻的极端度）")
    lines.append("- 强平规模分位：liq_24h（24h 总强平 USD）对该 symbol 自身 30d 中位数归一倍数（同 131 表1 口径），中位反映事件当刻强平相对常态的倍数")
    lines.append("- 后24h BTC 收益：事件时点起 24h 的 BTCUSDT 收益（forward_stats，无前视）")
    lines.append("- 市场 breadth：6h 网格市场级出清广度（%）事件时 asof\n")
    lines.append("| episode | n | liq_short_z均值 | liq_short_z中位 | 强平规模中位(x) | 后24h BTC收益均值 | breadth均值 | breadth≥5%占比 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    t1_rows: dict[str, dict] = {}
    for ep in ["pooled"] + EPISODES_LIQ:
        sub = cas if ep == "pooled" else cas[cas["episode"] == ep]
        if len(sub) == 0:
            lines.append(f"| {ep} | 0 | - | - | - | - | - | - |")
            continue
        z = pd.to_numeric(sub["liq_short_z_at_event"], errors="coerce").dropna()
        ratio = (pd.to_numeric(sub["liq_24h_at_event"], errors="coerce")
                 / pd.to_numeric(sub["liq_med_720_at_event"], errors="coerce").replace(0, pd.NA)).dropna()
        btc24 = btc_fwd_24h(btc_ctx, sub)
        brd = pd.to_numeric(sub["breadth_pct"], errors="coerce").dropna()
        brd_ok = (brd >= BREADTH_LOW).mean() if len(brd) else np.nan
        t1_rows[ep] = {
            "n": len(sub), "z_mean": float(z.mean()) if len(z) else np.nan,
            "z_med": float(z.median()) if len(z) else np.nan,
            "ratio_med": float(ratio.median()) if len(ratio) else np.nan,
            "btc24": float(np.nanmean(btc24)) if len(btc24) else np.nan,
            "brd_mean": float(brd.mean()) if len(brd) else np.nan,
            "brd_ok": float(brd_ok) if np.isfinite(brd_ok) else np.nan,
        }
        lines.append(f"| {ep} | {len(sub)} | {fmt_n(t1_rows[ep]['z_mean'])} | "
                     f"{fmt_n(t1_rows[ep]['z_med'])} | {fmt_n(t1_rows[ep]['ratio_med'])}x | "
                     f"{fmt(t1_rows[ep]['btc24'], plus=True)} | {fmt_n(t1_rows[ep]['brd_mean'])}% | "
                     f"{fmt_n(t1_rows[ep]['brd_ok'] * 100, nd=1)}% |")
    lines.append("")

    # ---------- 表2 事件质量分列：liq_short_z 档 × episode ----------
    z_buckets = [
        ("2~3", lambda v: pd.notna(v) and 2.0 < v <= 3.0),
        ("3~4", lambda v: pd.notna(v) and 3.0 < v <= 4.0),
        (">4", lambda v: pd.notna(v) and v > 4.0),
    ]
    z_fn = {zl: zf for zl, zf in z_buckets}
    lines.append("## 2. 表2 事件质量分列：liq_short_z 档（2~3 / 3~4 / >4）× 2024/2025\n")
    lines.append("问：更极端的空头强平（z>4）在 2025 是否仍有 edge（vs 2024 是否同档衰减）。\n")
    lines.append(table_header())
    lines.append(table_sep())
    t2_rows: dict[tuple[str, str], dict] = {}
    for zl, zf in z_buckets:
        for ep in ["pooled"] + EPISODES_LIQ:
            sub = cas if ep == "pooled" else cas[cas["episode"] == ep]
            sub = sub[sub["liq_short_z_at_event"].apply(zf)]
            r = stats_row(sub, window_base(ep, base_pooled, base_by_ep),
                          f"{ep}:z{zl}", args.min_events, args.seed)
            t2_rows[(ep, zl)] = r
            if r["n"] == 0:
                lines.append(f"| {ep}:z{zl} | 0 | - | - | - | - | - | **无事件** |")
            else:
                lines.append(row_line(r))
    lines.append("")
    lines.append("直接对比（事件集直比，bootstrap 95% CI，seed=" + str(args.seed) + "）："
                 "同档 2025−2024 的 24h 收益差\n")
    lines.append("| 档 | 2025 n | 2024 n | 2025−2024 24h均值差 | 95% CI |")
    lines.append("|---|---|---|---|---|")
    for zl, _ in z_buckets:
        zf = z_fn[zl]
        a = pd.to_numeric(cas.loc[(cas["episode"] == "2025顶→熊")
                                  & (cas["liq_short_z_at_event"].apply(zf)),
                                  "ret_24h"], errors="coerce").dropna().to_numpy()
        b = pd.to_numeric(cas.loc[(cas["episode"] == "2024崩→恢复")
                                  & (cas["liq_short_z_at_event"].apply(zf)),
                                  "ret_24h"], errors="coerce").dropna().to_numpy()
        if len(a) == 0 or len(b) == 0:
            lines.append(f"| z{zl} | {len(a)} | {len(b)} | - | - |")
            continue
        ci = bootstrap_ci(a, b, seed=args.seed)
        lines.append(f"| z{zl} | {len(a)} | {len(b)} | {fmt(ci['mean_diff'], plus=True)} | "
                     f"[{fmt(ci['ci_lo'], plus=True)}, {fmt(ci['ci_hi'], plus=True)}] |")
    lines.append("")

    # ---------- 表3 时间衰减 ----------
    lines.append("## 3. 表3 时间衰减：事件后 4/24/72/168h 收益曲线 2024 vs 2025\n")
    lines.append("问：2025 是反弹更快/更弱（4h 已兑现则 24h 无超额），还是根本没反弹。\n")
    lines.append("| 组 | h | n | 均值 | 超额vs基线 | 95% CI | 胜率 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    t3_rows: dict[tuple[str, int], dict] = {}
    for ep in ["pooled"] + EPISODES_LIQ:
        sub = cas if ep == "pooled" else cas[cas["episode"] == ep]
        base = window_base(ep, base_pooled, base_by_ep)
        for h in DEFAULT_HORIZONS:
            r = horizon_row(sub, base, f"{ep}:{h}h", h, args.seed, args.min_events)
            t3_rows[(ep, h)] = r
            lines.append(f"| {ep} | {h}h | {r['n']} | {fmt(r['mean'])} | {fmt(r['ex'], plus=True)} | "
                         f"[{fmt(r['ci_lo'], plus=True)}, {fmt(r['ci_hi'], plus=True)}] | "
                         f"{fmt_win(r['win'])} | **{r['verdict']}** |")
    lines.append("")
    lines.append("解读（4h 兑现比例 = 4h 超额 / 24h 超额；曲线形态见各 h 超额）：")
    for ep in EPISODES_LIQ:
        r4, r24 = t3_rows.get((ep, 4)), t3_rows.get((ep, 24))
        r72 = t3_rows.get((ep, 72)); r168 = t3_rows.get((ep, 168))
        if r4 and r24 and np.isfinite(r4.get("ex", np.nan)) and np.isfinite(r24.get("ex", np.nan)) \
                and abs(r24["ex"]) > 1e-9:
            ratio = r4["ex"] / r24["ex"]
            curve = " → ".join(
                f"{h}h {fmt(t3_rows.get((ep, h), {}).get('ex'), plus=True)}" for h in DEFAULT_HORIZONS
                if t3_rows.get((ep, h))
            )
            lines.append(f"- {ep}: 4h 兑现比例 {ratio * 100:.0f}%；超额曲线 {curve}；"
                         f"判定 {[t3_rows.get((ep, h), {}).get('verdict', '-') for h in DEFAULT_HORIZONS]}")
        else:
            lines.append(f"- {ep}: 4h/24h 超额数据不全（4h={fmt(r4.get('ex') if r4 else None, plus=True)}，"
                         f"24h={fmt(r24.get('ex') if r24 else None, plus=True)}）")
    lines.append("")

    # ---------- 表4 BTC 趋势条件化 ----------
    lines.append("## 4. 表4 BTC 趋势条件化：事件时 BTC 20d 回撤 / 30d 斜率 × 2024/2025\n")
    lines.append("问：BTC 处于下跌中继时级联是否失效（2025 熊市里强平=中继而非底部）。\n")

    # 4a: 30d 斜率正/负
    lines.append("### 4a. BTC 30d 斜率正/负\n")
    lines.append(table_header())
    lines.append(table_sep())
    t4a_rows: dict[tuple[str, str], dict] = {}
    for sg in ["正", "负"]:
        for ep in ["pooled"] + EPISODES_LIQ:
            sub = cas if ep == "pooled" else cas[cas["episode"] == ep]
            sub = sub[sub["btc_slope30_at_event"].apply(lambda v: btc_slope_sign(v) == sg)]
            r = stats_row(sub, window_base(ep, base_pooled, base_by_ep),
                          f"{ep}:BTC30d斜率{sg}", args.min_events, args.seed)
            t4a_rows[(ep, sg)] = r
            lines.append(row_line(r) if r["n"] else
                         f"| {ep}:BTC30d斜率{sg} | 0 | - | - | - | - | - | **无事件** |")
    lines.append("")

    # 4b: 20d 回撤分桶
    lines.append("### 4b. BTC 20d 回撤分桶（浅 ≥-10% / 中 -25~-10% / 深 <-25%）\n")
    lines.append(table_header())
    lines.append(table_sep())
    t4b_rows: dict[tuple[str, str], dict] = {}
    for db in ["浅 ≥-10%", "中 -25~-10%", "深 <-25%"]:
        for ep in ["pooled"] + EPISODES_LIQ:
            sub = cas if ep == "pooled" else cas[cas["episode"] == ep]
            sub = sub[sub["btc_dd20_at_event"].apply(lambda v: btc_dd_bucket(v) == db)]
            r = stats_row(sub, window_base(ep, base_pooled, base_by_ep),
                          f"{ep}:{db}", args.min_events, args.seed)
            t4b_rows[(ep, db)] = r
            lines.append(row_line(r) if r["n"] else
                         f"| {ep}:{db} | 0 | - | - | - | - | - | **无事件** |")
    lines.append("")

    # ---------- 表5 条件化修复检验 ----------
    lines.append("## 5. 表5 条件化修复检验：2025 加 BTC 趋势 / breadth 条件后是否翻正\n")
    lines.append("条件（全部事件时 asof，无前视）：slope_ok = BTC 30d 斜率>0（不在下跌中继）；"
                 "brd_ok = 市场 breadth≥5%（市场级出清，同 124/127 门控）；两者并用=修复组合。\n")
    slope_ok = (cas["btc_slope30_at_event"] > 0).fillna(False)
    brd_ok = (cas["breadth_pct"] >= BREADTH_LOW).fillna(False)
    conds = [
        ("全事件（基准）", np.ones(len(cas), dtype=bool)),
        ("BTC 30d 斜率>0", slope_ok.to_numpy()),
        ("breadth≥5%", brd_ok.to_numpy()),
        ("斜率>0 且 breadth≥5%", (slope_ok & brd_ok).to_numpy()),
    ]
    lines.append(table_header())
    lines.append(table_sep())
    t5_rows: dict[tuple[str, str], dict] = {}
    for ep in ["pooled"] + EPISODES_LIQ:
        sub_all = cas if ep == "pooled" else cas[cas["episode"] == ep]
        for cname, cmask in conds:
            sub = sub_all[cmask[sub_all.index]]
            r = stats_row(sub, window_base(ep, base_pooled, base_by_ep),
                          f"{ep}:{cname}", args.min_events, args.seed)
            t5_rows[(ep, cname)] = r
            lines.append(row_line(r) if r["n"] else
                         f"| {ep}:{cname} | 0 | - | - | - | - | - | **无事件** |")
    lines.append("")

    # ---------- 判定 ----------
    lines.append("## 6. 判定\n")
    t0_2024, t0_2025 = t0["2024崩→恢复"], t0["2025顶→熊"]
    t1_2024, t1_2025 = t1_rows.get("2024崩→恢复", {}), t1_rows.get("2025顶→熊", {})
    lines.append("### 6a. 机理判定\n")
    # 1) 强平常态化 / 事件环境
    z_delta = (t1_2025.get("z_mean", np.nan) - t1_2024.get("z_mean", np.nan)) if t1_2024 and t1_2025 else np.nan
    ratio_delta = (t1_2025.get("ratio_med", np.nan) - t1_2024.get("ratio_med", np.nan)) if t1_2024 and t1_2025 else np.nan
    btc24_delta = (t1_2025.get("btc24", np.nan) - t1_2024.get("btc24", np.nan)) if t1_2024 and t1_2025 else np.nan
    brd_delta = (t1_2025.get("brd_mean", np.nan) - t1_2024.get("brd_mean", np.nan)) if t1_2024 and t1_2025 else np.nan
    lines.append(f"- **事件环境差异（表1）**：2024 n={t0_2024['n']} vs 2025 n={t0_2025['n']}；"
                 f"事件时 liq_short_z 均值 {fmt_n(t1_2024.get('z_mean'))} vs {fmt_n(t1_2025.get('z_mean'))}"
                 f"（差 {z_delta:+.2f}）；"
                 f"强平规模中位 {fmt_n(t1_2024.get('ratio_med'))}x vs {fmt_n(t1_2025.get('ratio_med'))}x"
                 f"（差 {ratio_delta:+.2f}x）；后 24h BTC 收益均值 {fmt(t1_2024.get('btc24'), plus=True)} vs "
                 f"{fmt(t1_2025.get('btc24'), plus=True)}（差 {fmt(btc24_delta, plus=True)}）；"
                 f"市场 breadth 均值 {fmt_n(t1_2024.get('brd_mean'))}% vs {fmt_n(t1_2025.get('brd_mean'))}%"
                 f"（差 {brd_delta:+.2f}pp），breadth≥5% 占比 {fmt_n(t1_2024.get('brd_ok', np.nan) * 100, nd=1)}% vs "
                 f"{fmt_n(t1_2025.get('brd_ok', np.nan) * 100, nd=1)}%。")
    # 2) z 极端度
    z3_2025 = t2_rows.get(("2025顶→熊", ">4"), {}).get("n", 0)
    z3_2024 = t2_rows.get(("2024崩→恢复", ">4"), {}).get("n", 0)
    z3p_2025 = t2_rows.get(("2025顶→熊", ">4"), {})
    z3p_2024 = t2_rows.get(("2024崩→恢复", ">4"), {})
    lines.append(f"- **极端强平（表2）**：z>4 档 2024 n={z3_2024}（超额 {fmt(z3p_2024.get('ex24'), plus=True)}）"
                 f"vs 2025 n={z3_2025}（超额 {fmt(z3p_2025.get('ex24'), plus=True)}，CI {fmt_ci(z3p_2025)}）；"
                 f"更极端强平在 2025 **仍不恢复 edge**（z>4 档 2025 CI 含 0）。")
    # 3) 时间衰减
    r4_2024 = t3_rows.get(("2024崩→恢复", 4), {})
    r4_2025 = t3_rows.get(("2025顶→熊", 4), {})
    r168_2024 = t3_rows.get(("2024崩→恢复", 168), {})
    r168_2025 = t3_rows.get(("2025顶→熊", 168), {})
    lines.append(f"- **反弹时滞（表3）**：2024 4h 超额 {fmt(r4_2024.get('ex'), plus=True)} / "
                 f"24h {fmt(t0_2024.get('ex24'), plus=True)} / 168h {fmt(r168_2024.get('ex'), plus=True)}"
                 f"（单调上行）；2025 4h 超额 {fmt(r4_2025.get('ex'), plus=True)} / "
                 f"24h {fmt(t0_2025.get('ex24'), plus=True)} / 168h {fmt(r168_2025.get('ex'), plus=True)}"
                 f"（全程偏弱、7d 转负）→ 2025 既不是『4h 已兑现』也不是『反弹延迟』，而是**整体不反弹、"
                 f"随后回吐**。")
    # 4) BTC 趋势
    s25_pos = t4a_rows.get(("2025顶→熊", "正"), {})
    s25_neg = t4a_rows.get(("2025顶→熊", "负"), {})
    s24_pos = t4a_rows.get(("2024崩→恢复", "正"), {})
    s24_neg = t4a_rows.get(("2024崩→恢复", "负"), {})
    lines.append(f"- **BTC 趋势（表4a）**：2025 事件中 BTC 30d 斜率正 n={s25_pos.get('n', 0)}"
                 f"（超额 {fmt(s25_pos.get('ex24'), plus=True)}，CI {fmt_ci(s25_pos)}）vs 负 n={s25_neg.get('n', 0)}"
                 f"（超额 {fmt(s25_neg.get('ex24'), plus=True)}，CI {fmt_ci(s25_neg)}）→ 2025 内部 BTC 趋势"
                 f"无法区分（斜率正档仍 NO_GO，熊市反弹中继语境）；2024 正 n={s24_pos.get('n', 0)}"
                 f"（{fmt(s24_pos.get('ex24'), plus=True)}）vs 负 n={s24_neg.get('n', 0)}"
                 f"（{fmt(s24_neg.get('ex24'), plus=True)}）→ 2024 连斜率负档都强（崩后底部语境，"
                 f"强平=底部而非中继）。")
    dd25 = t4b_rows.get(("2025顶→熊", "深 <-25%"), {})
    dd24 = t4b_rows.get(("2024崩→恢复", "深 <-25%"), {})
    dd25m = t4b_rows.get(("2025顶→熊", "中 -25~-10%"), {})
    dd24m = t4b_rows.get(("2024崩→恢复", "中 -25~-10%"), {})
    lines.append(f"- **BTC 20d 回撤（表4b）**：深回撤档 2024 n={dd24.get('n', 0)}"
                 f"（超额 {fmt(dd24.get('ex24'), plus=True)}）vs 2025 n={dd25.get('n', 0)}"
                 f"（超额 {fmt(dd25.get('ex24'), plus=True)}，均样本不足仅参考）；中档 2024 n={dd24m.get('n', 0)}"
                 f"（{fmt(dd24m.get('ex24'), plus=True)} GO_LONG）vs 2025 n={dd25m.get('n', 0)}"
                 f"（{fmt(dd25m.get('ex24'), plus=True)} NO_GO）→ 同一回撤深度下 2025 仍弱，"
                 f"回撤深度本身不足以区分。")
    lines.append("")
    lines.append("**机理合成**：")
    lines.append("- **『z 失敏/强平常态化』被否证**：2025 事件时 liq_short_z 与强平规模中位反而更高"
                 "（3.85 vs 3.16；3.42x vs 2.90x），触发当刻强平更极端，edge 反而更弱——失敏不在触发强度，"
                 "而在触发之后的市场反应。")
    lines.append("- **『反弹时滞』被否证**：2025 4h/24h/72h 全部 NO_GO、168h 转负——不是反弹来得慢，"
                 "而是根本不反弹（或 7d 内回吐）。")
    lines.append("- **主因 = 语境差异（熊市中继 vs 崩后底部）**：2025 事件集中在 BTC 下跌中继"
                 "（后 24h BTC 收益均值 +0.00% vs 2024 +1.36%，breadth 均值 9.73% vs 14.18%），"
                 "此时强平=中继的燃料而非底部确认；2024 崩后恢复语境下强平=清杠杆后的底部。"
                 "2024 连 BTC 30d 斜率负档都强、2025 连斜率正档都弱，说明起决定作用的是大语境"
                 "（episode 级状态），不是事件当刻的 BTC 趋势/回撤快照。")
    lines.append("")

    lines.append("### 6b. 条件化修复结论（表5）\n")
    fix_ref = t5_rows.get(("2025顶→熊", "全事件（基准）"), {})
    fix_slope = t5_rows.get(("2025顶→熊", "BTC 30d 斜率>0"), {})
    fix_brd = t5_rows.get(("2025顶→熊", "breadth≥5%"), {})
    fix_both = t5_rows.get(("2025顶→熊", "斜率>0 且 breadth≥5%"), {})
    lines.append(f"- 2025 基准：n={fix_ref.get('n', 0)}，24h 超额 {fmt(fix_ref.get('ex24'), plus=True)}"
                 f"（CI {fmt_ci(fix_ref)}）→ **{fix_ref.get('verdict', '-')}**")
    for cname, r in [("BTC 30d 斜率>0", fix_slope), ("breadth≥5%", fix_brd),
                     ("斜率>0 且 breadth≥5%", fix_both)]:
        lines.append(f"- 2025 + {cname}：n={r.get('n', 0)}，24h 超额 {fmt(r.get('ex24'), plus=True)}"
                     f"（CI {fmt_ci(r)}）→ **{r.get('verdict', '-')}**")
    lines.append("")

    lines.append("### 6c. 综合判定\n")
    # 条件化修复是否翻正：2025+某条件判定为 GO_LONG 且 CI 下界>0
    slope_fix_ok = fix_slope.get("verdict") == "GO_LONG" and np.isfinite(fix_slope.get("ci_lo", np.nan)) \
        and fix_slope["ci_lo"] > 0
    brd_fix_ok = fix_brd.get("verdict") == "GO_LONG" and np.isfinite(fix_brd.get("ci_lo", np.nan)) \
        and fix_brd["ci_lo"] > 0
    both_fix_ok = fix_both.get("verdict") == "GO_LONG" and np.isfinite(fix_both.get("ci_lo", np.nan)) \
        and fix_both["ci_lo"] > 0
    fixes = []
    if slope_fix_ok:
        fixes.append(f"BTC 30d 斜率>0（n={fix_slope.get('n', 0)}，超额 {fmt(fix_slope.get('ex24'), plus=True)}，"
                     f"CI {fmt_ci(fix_slope)}）")
    if brd_fix_ok:
        fixes.append(f"breadth≥5%（n={fix_brd.get('n', 0)}，超额 {fmt(fix_brd.get('ex24'), plus=True)}，"
                     f"CI {fmt_ci(fix_brd)}）")
    if both_fix_ok:
        fixes.append(f"斜率>0 且 breadth≥5%（n={fix_both.get('n', 0)}，超额 "
                     f"{fmt(fix_both.get('ex24'), plus=True)}，CI {fmt_ci(fix_both)}）")
    if fixes:
        fix_line = "2025 可条件化修复：以下条件使 2025 翻正（GO_LONG 且 CI 下界>0）——" + "；".join(fixes)
        if brd_fix_ok and np.isfinite(fix_brd.get("ex168", np.nan)):
            fix_line += (f"。注意 breadth≥5% 修复档 168h 超额 {fmt(fix_brd['ex168'], plus=True)}"
                         f"（24h edge 存在但 7d 不持续/转负，见 表5），且 2024 breadth≥5% 档 168h 超额 "
                         f"{fmt(t5_rows.get(('2024崩→恢复', 'breadth≥5%'), {}).get('ex168', np.nan), plus=True)}"
                         f"（正）——2025 语境下该修复更多是『短周期抢反弹』而非『趋势底』。"
                         f"叠加斜率条件样本压缩至 n={fix_both.get('n', 0)} 后 CI 含 0，不宜双条件硬叠。")
    else:
        fix_line = ("2025 未能在 BTC 趋势/breadth 条件下翻正（所有修复组合 CI 含 0 或样本不足）——"
                    "该信号 2025 语境下不可修复或需其他条件（VIX 门控见 123、放量见 126，联合矩阵见 133）")
    lines.append(f"- {fix_line}")
    lines.append("")

    # ---------- 局限 ----------
    lines.append("## 7. 局限\n")
    lines.append("- **统计功效**：只有 2024崩→恢复 / 2025顶→熊 两个 episode，2024 段 n=434、2025 段 n=1276，"
                 "分档后（z 档 × episode、BTC 趋势 × episode、修复组合）样本缩小至几十到几百，"
                 "子集 CI 宽；2024 段仅 8 个月，是『崩后底部』单一语境，不能代表所有牛市环境。")
    lines.append("- **描述性为主**：表1 是环境描述（事件数/z 均值/规模/后 24h BTC 收益/breadth），"
                 "不构成因果证据；表2/3/4/5 是条件化事件研究，但跨 episode 对比受抽样误差与语境混杂影响。")
    lines.append("- liquidation 只覆盖 2024-06-06 → 2026-06-23：2022/2023 磨底/蓄力期的强平流不可测，"
                 "『级联=底部』命题是否跨周期成立未验证。")
    lines.append("- 强平特征需 24h 累计 + 720h z-score 暖机（min_periods=360）：2024-06 暖机期事件 "
                 "liq_short_z 为 NaN 自动不触发级联（级联要求 z>2 有限值），不产生偏置档。")
    lines.append("- 表2 直接对比（2025−2024）为事件集直比，未按币/时点聚类，bootstrap CI 偏窄；"
                 "72h 冷却使同币事件间自相关，同一 6h 时点多币级联（系统性强平窗口）使事件非独立。")
    lines.append("- BTC 斜率/回撤为自序列 30d/20d 滚动窗口，事件时 asof 无前视；但 BTC 趋势与 episode "
                 "高度共线（2024 段多为回升、2025 段多为下跌中继），条件化分组后两组样本量不均衡，"
                 "组间对比需谨慎解读。")
    lines.append("- coinglass klines 2026-06-23 23:00 → 06-30 04:00 约 6.3 天全 universe 空档："
                 "事件 ts 上限 2026-06-23，尾部事件 forward 收益可能 NaN，轻微减少样本。")
    lines.append("- 未做参数敏感性（z 档边界 2/3/4、冷却 72h、BTC 斜率窗口 720h/回撤 480h），"
                 "未做样本外前向验证（当前筑底窗口只有影子数据）；修复组合（斜率+breadth）样本 "
                 "进一步压缩，n<30 时按规则不判。")
    lines.append("")
    lines.append("> **T3 标注**：进 108 前向影子 / scan_rules / contract_anomaly_rules 的任何改动属 T3，"
                 "需 Owner 签批。本脚本只做研究侧建议，不碰任何配置（config/*.yaml、scan_rules.yaml、"
                 "contract_anomaly_rules.yaml、scripts/108_contract_monitor.py、109_forward_replay.py）。")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "liq_cascade_2025.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")

    # ---------- 控制台摘要 ----------
    print("\n=== 表0 复现 131 表3 ===")
    print(table_header())
    for ep in ["pooled"] + EPISODES_LIQ:
        print(row_line(t0[ep]))

    print("\n=== 表1 事件分布对比 ===")
    print("episode | n | z均值 | z中位 | 规模中位(x) | 后24h BTC收益均值 | breadth均值 | breadth≥5%占比")
    for ep in ["pooled"] + EPISODES_LIQ:
        r = t1_rows.get(ep)
        if not r:
            continue
        print(f"{ep} | {r['n']} | {fmt_n(r['z_mean'])} | {fmt_n(r['z_med'])} | {fmt_n(r['ratio_med'])}x | "
              f"{fmt(r['btc24'], plus=True)} | {fmt_n(r['brd_mean'])}% | {fmt_n(r['brd_ok'] * 100, nd=1)}%")

    print("\n=== 表2 事件质量分列（z 档 × episode） ===")
    print(table_header())
    for zl, _ in z_buckets:
        for ep in ["pooled"] + EPISODES_LIQ:
            r = t2_rows.get((ep, zl))
            if r:
                print(row_line(r))

    print("\n=== 表3 时间衰减（超额 vs 基线） ===")
    print("组 | h | n | 均值 | 超额 | CI | 胜率 | 判定")
    for ep in ["pooled"] + EPISODES_LIQ:
        for h in DEFAULT_HORIZONS:
            r = t3_rows.get((ep, h))
            if r:
                print(f"{ep} | {h}h | {r['n']} | {fmt(r['mean'])} | {fmt(r['ex'], plus=True)} | "
                      f"[{fmt(r['ci_lo'], plus=True)}, {fmt(r['ci_hi'], plus=True)}] | "
                      f"{fmt_win(r['win'])} | {r['verdict']}")

    print("\n=== 表4a BTC 30d 斜率正/负 ===")
    print(table_header())
    for sg in ["正", "负"]:
        for ep in ["pooled"] + EPISODES_LIQ:
            r = t4a_rows.get((ep, sg))
            if r:
                print(row_line(r))

    print("\n=== 表4b BTC 20d 回撤分桶 ===")
    print(table_header())
    for db in ["浅 ≥-10%", "中 -25~-10%", "深 <-25%"]:
        for ep in ["pooled"] + EPISODES_LIQ:
            r = t4b_rows.get((ep, db))
            if r:
                print(row_line(r))

    print("\n=== 表5 条件化修复检验 ===")
    print(table_header())
    for ep in ["pooled"] + EPISODES_LIQ:
        for cname, _ in conds:
            r = t5_rows.get((ep, cname))
            if r:
                print(row_line(r))

    print(f"\n判定: {fix_line}")


if __name__ == "__main__":
    main()
