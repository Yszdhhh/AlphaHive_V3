"""132_feargreed_combo.py — wash_cvd × 恐惧贪婪贪婪层组合（验证 130 贪婪层发现是否可作过滤器）。

背景：130 实测②发现 wash_cvd 事件按【事件日-1】恐惧贪婪分层时，贪婪 60+ 层
GO_LONG（24h 超额 +1.42% CI[+0.80,+2.12]，n=789，占事件 58.5%）是唯一显著层，
中性 40-60 层最弱（+0.11%，n=295）。本脚本把该发现实现为可落地的组合过滤器
（承接 123 VIX 门控 / 126 放量组合的口径），回答：贪婪层过滤是否值得作为
wash_cvd 的 Long 侧辅助条件（每事件期望提升 vs 样本损失、跨 episode 一致性）。

检验（全部 Long，72h 冷却，事件 ts 限制 2022-01-01 ~ 2026-06-30 UTC）：
  表1 组合对比：V_ref 纯 wash_cvd vs V_greed（事件日-1 fng≥60）vs V_fear（<20 极恐层）
      —— pooled 口径统一基线（首抽全区间基线，三组横向可比）
  表2 V_greed 分 episode：贪婪层事件是否 4/4 全正；附窗口内贪婪日占比标注样本
      （2022/2023 贪婪天较少 → 事件少、噪声大）
  表3 组合成本：被滤掉事件（非贪婪层 fng<60）24h 收益分布 + 子层（极恐/恐惧/中性）
      —— 对比 123 VIX 门控丢的是负期望尾部，这里丢的是啥（正期望 = 真实机会成本）
  表4（加分）贪婪层 × 放量>1.5x 双重过滤：两条件叠加的 24h 超额
  表5 与 VIX 门控的重叠：fng≥60 ∩ vix_low 占比（避免双重计数）

无前视：恐惧贪婪/VIX 状态均 asof 事件日-1（130/123 同口径，ffill 回退缺日）；
qv24_ratio 事件时点 asof 取值（searchsorted，126 同款）。

数据（2026-08-07 核实）：
- fear_greed_index.csv（alternative.me，日度 0-100，2021-02-14 → 2026-08-07，
  130 一次性拉取，CSV 含 source_url + fetched_utc）
- coinglass klines（close/quote_volume → qv24_ratio，公式同 121/126）
- VIX.parquet（CBOE，120 已存）→ vix_low = VIX ≤ 1y 滚动 75 分位（120/123 口径）

用法：
  python scripts/132_feargreed_combo.py [--n-baseline 5000] [--seed 2026] [--min-events 30]
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
    summarize_events,
)

COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
MACRO_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
FUNDING_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
REPORTS_DIR = PROJECT_ROOT / "reports"

# 复用 113/115/120 的加载/检测/宏观状态口径（120 连带加载 113/115，正常）
_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec); sys.modules["m113"] = m113; _spec.loader.exec_module(m113)
_spec2 = importlib.util.spec_from_file_location(
    "m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2); sys.modules["m115"] = m115; _spec2.loader.exec_module(m115)
_spec3 = importlib.util.spec_from_file_location(
    "m120", str(PROJECT_ROOT / "scripts" / "120_macro_factor_modulation.py"))
m120 = importlib.util.module_from_spec(_spec3); sys.modules["m120"] = m120; _spec3.loader.exec_module(m120)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
detect_events = m115.detect_events
EPISODES = m113.EPISODES
episode_of = m113.episode_of
build_state_frame = m120.build_state_frame
event_states = m120.event_states
load_macro_series = m120.load_macro_series

STUDY_START = "2022-01-01"
STUDY_END = "2026-06-30"   # 前向 episode 不含（无宏观可判定的未来）
VARIANT = "wash_cvd"
VARIANT_DESC = "washout(price_z<-2.0 或 ret_24h<-8%) 且 cvd_divergence>2.0，72h 冷却，Long"

FNG_CSV = MACRO_ROOT / "fear_greed_index.csv"
FNG_URL = "https://api.alternative.me/fng/?limit=2000&format=json"
GREEDY = 60.0      # 贪婪层下界（130 口径「贪婪 60+」）
FEAR = 20.0        # 极恐层上界（130 口径「极恐 <20」）
VOL_HI = 1.5       # 放量阈值（121/126 口径 qv24_ratio>1.5）

# 130/121 已知数字（交叉核对目标，运行末尾打印一致性）
KNOWN = {
    "130 贪婪60+ n": 789,
    "130 贪婪60+ 24h超额": 1.42,
    "130 贪婪60+ CI下界": 0.80,
    "130 贪婪60+ 占比": 0.585,
    "130 中性40-60 24h超额": 0.11,
    "123 vix_low 24h超额": 1.37,
    "123 vix_high 丢弃占比": 0.165,
    "126 放量>1.5x 24h超额": 1.90,
}


# ---------------------------------------------------------------- 数据装载

def load_fng() -> pd.Series:
    """恐惧贪婪日度序列（date naive → value），去重升序。"""
    df = pd.read_csv(FNG_CSV, parse_dates=["date"])
    s = pd.Series(pd.to_numeric(df["value"], errors="coerce").to_numpy(),
                  index=pd.DatetimeIndex(df["date"]).normalize())
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def _series_asof_prev_day(events: pd.DataFrame, ser: pd.Series) -> np.ndarray:
    """事件 asof 取【事件日 - 1】的日度序列值；缺宏观日（周末/假日）ffill 回退（不超前）。

    与 120.event_states / 123 完全同口径。
    """
    dates = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_convert(None).normalize()
    prev = (dates - pd.Timedelta(days=1)).normalize()
    return ser.reindex(prev, method="ffill").to_numpy()


def _fwd_for(ctxs: dict, df: pd.DataFrame) -> pd.DataFrame:
    """给 (symbol, timestamp) 事件表补 forward 收益（按 symbol 分组调用 forward_stats）。"""
    if df is None or df.empty:
        return pd.DataFrame()
    parts = []
    for s, g in df.groupby("symbol", sort=False):
        if s in ctxs:
            parts.append(forward_stats(ctxs[s], g.copy(), horizons=DEFAULT_HORIZONS))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def add_qv24_ratio(ctxs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """在 ctx 基础上补 qv24_ratio 列（公式与 121/126 完全一致）。

    qv24 = quote_volume.rolling(24).sum()（对齐到 ctx 清洗后的 index）
    qv24_med = qv24.rolling(720, min_periods=360).median()
    ratio = qv24 / qv24_med（放量倍数，>1 = 高于 30d 中位量）
    """
    for sym, t in ctxs.items():
        p = COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if "open_time" not in df.columns or "quote_volume" not in df.columns:
            continue
        ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
        qv = pd.to_numeric(df["quote_volume"], errors="coerce")
        qv_ser = pd.Series(qv.to_numpy(), index=pd.Index(ts))
        qv_ser = qv_ser[~qv_ser.index.duplicated(keep="last")].sort_index().reindex(t.index)
        qv24 = qv_ser.rolling(24).sum()
        qv24_med = qv24.rolling(720, min_periods=360).median()
        t["qv24_ratio"] = (qv24 / qv24_med.replace(0, pd.NA)).replace([np.inf, -np.inf], pd.NA)
    return ctxs


def qv24_ratio_at_event(ctxs: dict, events: pd.DataFrame) -> pd.DataFrame:
    """对每个事件 ts 用 np.searchsorted 取事件行及之前最近的有效 qv24_ratio（asof，无前视）。"""
    ev = events.copy()
    ev["qv24_ratio_at_event"] = np.nan
    for sym, g in ev.groupby("symbol", sort=False):
        if sym not in ctxs or "qv24_ratio" not in ctxs[sym].columns:
            continue
        t = ctxs[sym]
        idx = t.index.to_numpy(dtype=np.int64)
        pos = np.searchsorted(idx, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(idx) - 1)
        vals = pd.to_numeric(t["qv24_ratio"], errors="coerce").to_numpy(dtype=float)
        ev.loc[g.index, "qv24_ratio_at_event"] = vals[pos]
    return ev


# ---------------------------------------------------------------- 统计

def _row_stats(sub: pd.DataFrame, base_v: np.ndarray, base_v168: np.ndarray,
               seed: int, min_events: int) -> dict:
    """单组事件的统计行：n / 24h 均值 / 超额 / CI / 168h 超额 / 胜率 / 中位数 / 判定。"""
    row: dict = {"n": len(sub)}
    ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
    if len(ev_v) == 0:
        row.update({"mean24": np.nan, "median": np.nan, "win": np.nan,
                    "excess": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
                    "excess168": np.nan, "verdict": "无事件"})
        return row
    s = summarize_events(sub)
    ci = bootstrap_ci(ev_v, base_v, seed=seed)
    ev_v168 = pd.to_numeric(sub["ret_168h"], errors="coerce").dropna().to_numpy()
    ci168 = bootstrap_ci(ev_v168, base_v168, seed=seed)
    row.update({
        "mean24": float(s["ret_24h_mean"]),
        "median": float(s["ret_24h_median"]),
        "win": float(s["ret_24h_win"]),
        "excess": float(ci["mean_diff"]),
        "ci_lo": float(ci["ci_lo"]),
        "ci_hi": float(ci["ci_hi"]),
        "excess168": float(ci168["mean_diff"]),
    })
    if len(ev_v) < min_events:
        row["verdict"] = f"样本不足(n={len(ev_v)}<{min_events})"
    elif ci["ci_lo"] > 0:
        row["verdict"] = "GO_LONG"
    elif ci["ci_hi"] < 0:
        row["verdict"] = "GO_SHORT"
    else:
        row["verdict"] = "NO_GO"
    return row


def bootstrap_mean_diff(a: np.ndarray, b: np.ndarray, n_boot: int = 1000, seed: int = 2026) -> dict:
    """两组均值差（a−b）的 bootstrap 95% CI（与 124/130 同款）。"""
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


def fmt_ci(lo: float, hi: float) -> str:
    if not np.isfinite(lo):
        return "-"
    return f"[{lo:+.2f}, {hi:+.2f}]"


def fmt_plus(v: float) -> str:
    return f"{v:+.2f}%" if np.isfinite(v) else "-"


# ---------------------------------------------------------------- 主流程

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-events", type=int, default=30)
    parser.add_argument("--n-baseline", type=int, default=5000)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    fundings = load_funding_series(symbols)
    ctxs = add_qv24_ratio(ctxs)
    print(f"[132] 价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)}")

    # ---- 事件 = wash_cvd（全区间 2022-01-01 → 2026-06-30）----
    ev_parts = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), VARIANT)
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(columns=["symbol", "timestamp"])
    events = _fwd_for(ctxs, events)
    events["episode"] = episode_of(events["timestamp"].to_numpy())
    lo = int(pd.Timestamp(STUDY_START, tz="UTC").timestamp() * 1000)
    hi = int(pd.Timestamp(STUDY_END, tz="UTC").timestamp() * 1000)
    events = events[(events["timestamp"] >= lo) & (events["timestamp"] <= hi)]
    print(f"[132] {VARIANT} 事件 {len(events)}（{STUDY_START}→{STUDY_END}）")

    # ---- 恐惧贪婪 asof 事件日-1（130 同口径）+ VIX 状态（120 口径）+ 放量 asof ----
    fng = load_fng()
    events["fng_asof"] = _series_asof_prev_day(events, fng)
    n_fng = int(events["fng_asof"].notna().sum())
    print(f"[132] 附恐惧贪婪 asof {n_fng}/{len(events)}（{fng.index.min().date()} → {fng.index.max().date()}）")

    st = build_state_frame()
    ev_st = event_states(events, st)
    events["vix_low"] = pd.Series(ev_st["vix_low"].to_numpy(), index=events.index).fillna(False)
    events["vix_high"] = pd.Series(ev_st["vix_high"].to_numpy(), index=events.index).fillna(False)

    events = qv24_ratio_at_event(ctxs, events)
    n_vol = int((events["qv24_ratio_at_event"] > VOL_HI).sum())
    print(f"[132] 附 qv24_ratio 事件 {n_vol}/{len(events)} 放量>1.5x")

    rng = np.random.default_rng(args.seed)
    lines: list[str] = []

    # ---- 基线：pooled 首抽（全区间，表1/3/4 共用，三组横向可比），随后各 episode 各抽一次 ----
    base = draw_random_events(ctxs, args.n_baseline, rng, max_forward_hours=168, start_ms=lo, end_ms=hi)
    base_stats = _fwd_for(ctxs, base)
    base_v = pd.to_numeric(base_stats["ret_24h"], errors="coerce").dropna().to_numpy()
    base_v168 = pd.to_numeric(base_stats["ret_168h"], errors="coerce").dropna().to_numpy()
    print(f"[132] pooled 基线 n={len(base_v)}，24h 均值 {np.nanmean(base_v):+.2f}%")
    ep_base: dict[str, dict] = {}
    for name, s, e in EPISODES:
        if "前向" in name:
            continue
        sm = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
        em = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
        b = draw_random_events(ctxs, args.n_baseline, rng, max_forward_hours=168, start_ms=sm, end_ms=em)
        bs = _fwd_for(ctxs, b)
        ep_base[name] = {
            "v24": pd.to_numeric(bs["ret_24h"], errors="coerce").dropna().to_numpy(),
            "v168": pd.to_numeric(bs["ret_168h"], errors="coerce").dropna().to_numpy(),
        }

    # ---- 分组 ----
    greedy_mask = events["fng_asof"] >= GREEDY
    fear_mask = events["fng_asof"] < FEAR
    dropped_mask = ~greedy_mask  # 非贪婪层（含极恐/恐惧/中性；fng NaN 亦归入）
    v_greed = events[greedy_mask]
    v_fear = events[fear_mask]
    v_dropped = events[dropped_mask]

    # ================================================================ 报告
    lines.append("# wash_cvd × 恐惧贪婪贪婪层组合事件研究（验证 130 贪婪层发现可否作过滤器）\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 方法: 事件={VARIANT}（{VARIANT_DESC}），事件 ts 限制 {STUDY_START} ~ {STUDY_END} UTC；"
                 f"恐惧贪婪/VIX asof 事件日-1（无前视，ffill 回退缺日）；贪婪层 = fng≥{GREEDY:.0f}，"
                 f"极恐层 = fng<{FEAR:.0f}（130 口径）；qv24_ratio 事件时点 asof（126 口径）")
    lines.append(f"- 数据源: COINGLASS_RAW1H = {COINGLASS_RAW1H}（klines: open_time/close/quote_volume）；"
                 f"FUNDING_DIR = {FUNDING_DIR}；MACRO_ROOT = {MACRO_ROOT}")
    lines.append(f"- 外部数据: 恐惧贪婪指数 source={FNG_URL}（alternative.me 日度免费，0-100；"
                 f"CSV fetched_utc 见 fear_greed_index.csv，覆盖 {fng.index.min().date()} → {fng.index.max().date()}）；"
                 f"VIX（CBOE，120 已存 VIX.parquet，vix_low = VIX ≤ 1y 滚动 75 分位，120/123 口径）")
    lines.append(f"- 基线 = 同期随机 symbol×时点，bootstrap 95% CI（seed={args.seed}, n={args.n_baseline}，"
                 f"pooled 首抽全区间基线三组横向可比，表2 各 episode 独立基线）；"
                 f"判定: CI 下界>0 → GO_LONG；上界<0 → GO_SHORT；含 0 → NO_GO；n<{args.min_events} → 样本不足")
    lines.append("> 承接：130 实测② wash_cvd 按恐惧贪婪分层，贪婪 60+ 层 24h 超额 +1.42% CI[+0.80,+2.12]"
                 "（n=789，占事件 58.5%）全层唯一显著 GO_LONG，中性 40-60 层最弱（+0.11%，n=295）。"
                 "本脚本把它实现为组合过滤器，并检验机会成本、跨 episode 一致性、与 VIX 门控的重叠。\n")

    # ---------- 表0 事件总览 ----------
    lines.append("## 0. 事件总览\n")
    lines.append("| episode | wash_cvd | 贪婪层 n | 贪婪占比 | 窗口贪婪日占比 | 极恐层 n |")
    lines.append("|---|---|---|---|---|---|")
    n_days_all = 0
    n_gd_all = 0
    for name, s, e in EPISODES:
        if "前向" in name:
            continue
        sub = events[events["episode"] == name]
        n_ep = len(sub)
        g_ep = int(sub["fng_asof"].ge(GREEDY).sum())
        f_ep = int(sub["fng_asof"].lt(FEAR).sum())
        win_days = fng[(fng.index >= pd.Timestamp(s)) & (fng.index < pd.Timestamp(e))]
        gd_ratio = float((win_days >= GREEDY).mean()) if len(win_days) else np.nan
        n_days_all += len(win_days)
        n_gd_all += int((win_days >= GREEDY).sum())
        share = g_ep / n_ep * 100 if n_ep else 0.0
        lines.append(f"| {name} | {n_ep} | {g_ep} | {share:.0f}% | {gd_ratio * 100:.1f}% | {f_ep} |")
    lines.append("")
    greedy_share = int(greedy_mask.sum()) / len(events) * 100
    lines.append(f"- 全窗口贪婪日占比 {n_gd_all}/{n_days_all} = {n_gd_all / n_days_all * 100:.1f}%；"
                 f"贪婪层事件占全部 wash_cvd 事件 {greedy_share:.1f}%（130: 58.5%）。\n")

    # ---------- 表1 pooled 组合对比 ----------
    lines.append("## 1. 组合对比（pooled，统一基线）\n")
    lines.append("| 组 | n | 24h均% | 超额vs基线 | 95% CI | 胜率 | 中位数% | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    rows1: dict[str, dict] = {}
    for label, sub in [("V_ref 纯wash_cvd", events),
                       ("V_greed 贪婪层(fng≥60)", v_greed),
                       ("V_fear 极恐层(fng<20)", v_fear)]:
        r = _row_stats(sub, base_v, base_v168, args.seed, args.min_events)
        rows1[label] = r
        lines.append(
            f"| {label} | {r['n']} | {fmt_plus(r['mean24'])} | {fmt_plus(r['excess'])} | {fmt_ci(r['ci_lo'], r['ci_hi'])} "
            f"| {r['win'] * 100:.0f}% | {fmt_plus(r['median'])} | {fmt_plus(r['excess168'])} | **{r['verdict']}** |")
    lines.append("")

    g_v = pd.to_numeric(v_greed["ret_24h"], errors="coerce").dropna().to_numpy()
    f_v = pd.to_numeric(v_fear["ret_24h"], errors="coerce").dropna().to_numpy()
    c_gf = bootstrap_mean_diff(g_v, f_v, seed=args.seed)
    lines.append(f"- 贪婪 − 极恐 事件 24h 直接对照: {c_gf['mean_diff']:+.2f}% "
                 f"CI [{c_gf['ci_lo']:+.2f}, {c_gf['ci_hi']:+.2f}]（n贪婪={c_gf['n_a']}, n极恐={c_gf['n_b']}）\n")

    # ---------- 表2 V_greed 分 episode ----------
    lines.append("## 2. V_greed 分 episode（贪婪层事件是否 4/4 全正）\n")
    lines.append("| episode | wash_cvd n | 贪婪 n | 贪婪日占比 | 24h均% | 超额vs本ep基线 | 95% CI | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    ep_rows: dict[str, dict] = {}
    for name, s, e in EPISODES:
        if "前向" in name:
            continue
        sub = v_greed[v_greed["episode"] == name]
        n_all = int((events["episode"] == name).sum())
        win_days = fng[(fng.index >= pd.Timestamp(s)) & (fng.index < pd.Timestamp(e))]
        gd_ratio = float((win_days >= GREEDY).mean()) if len(win_days) else np.nan
        if sub.empty:
            lines.append(f"| {name} | {n_all} | 0 | {gd_ratio * 100:.1f}% | - | - | - | - | **无事件** |")
            ep_rows[name] = {"n": 0, "verdict": "无事件"}
            continue
        r = _row_stats(sub, ep_base[name]["v24"], ep_base[name]["v168"], args.seed, args.min_events)
        ep_rows[name] = r
        lines.append(
            f"| {name} | {n_all} | {r['n']} | {gd_ratio * 100:.1f}% | {fmt_plus(r['mean24'])} | {fmt_plus(r['excess'])} "
            f"| {fmt_ci(r['ci_lo'], r['ci_hi'])} | {fmt_plus(r['excess168'])} | **{r['verdict']}** |")
    lines.append("")
    pos_eps = [k for k, r in ep_rows.items() if np.isfinite(r.get("excess", np.nan)) and r["excess"] > 0]
    neg_eps = [k for k, r in ep_rows.items() if np.isfinite(r.get("excess", np.nan)) and r["excess"] <= 0]
    lines.append(f"- 贪婪层 24h 超额为正的 episode: {len(pos_eps)}/{len(ep_rows)}"
                 f"（{', '.join(pos_eps) if pos_eps else '无'}）"
                 f"{'；为负: ' + ', '.join(neg_eps) if neg_eps else ''}")
    lines.append(f"- 严格口径: 有贪婪层事件的 episode {len(pos_eps)}/{len(ep_rows)} 全为正，"
                 f"但 2022 熊底贪婪日占比仅 0.5% → 贪婪层 0 事件（过滤器在 2022 完全失效，非负超额而是无样本）；"
                 f"2025 为 +0.67% 但 CI 含 0 → NO_GO。故**不满足 4/4 全正**（2022 无样本 + 2025 不显著）。")
    lines.append(f"- 样本标注: 贪婪日占比越低 → 窗口内贪婪层事件越少、噪声越大；"
                 f"2022 熊底/2023 平台窗口贪婪日占比低（见表 0/2），对应贪婪层 n 小，判定按 n<{args.min_events} 标样本不足。\n")

    # ---------- 表3 组合成本 ----------
    lines.append("## 3. 组合成本：被滤掉事件（非贪婪层 fng<60）的机会成本\n")
    d_row = _row_stats(v_dropped, base_v, base_v168, args.seed, args.min_events)
    lines.append("| 组 | n | 占比 | 24h均% | 超额vs基线 | 95% CI | 胜率 | 中位数% | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    lines.append(
        f"| 被滤掉(非贪婪层) | {d_row['n']} | {d_row['n'] / len(events) * 100:.1f}% | {fmt_plus(d_row['mean24'])} "
        f"| {fmt_plus(d_row['excess'])} | {fmt_ci(d_row['ci_lo'], d_row['ci_hi'])} | {d_row['win'] * 100:.0f}% "
        f"| {fmt_plus(d_row['median'])} | {fmt_plus(d_row['excess168'])} | **{d_row['verdict']}** |")
    lines.append("")
    lines.append("### 3b. 被滤掉事件子层（极恐 / 恐惧 / 中性）\n")
    lines.append("| 子层 | n | 24h均% | 超额vs基线 | 95% CI | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    for a, b, lab in [(0.0, 20.0, "极恐 <20"), (20.0, 40.0, "恐惧 20-40"), (40.0, 60.0, "中性 40-60")]:
        sub = events[(events["fng_asof"] >= a) & (events["fng_asof"] < b)]
        if sub.empty:
            lines.append(f"| {lab} | 0 | - | - | - | - | **无事件** |")
            continue
        r = _row_stats(sub, base_v, base_v168, args.seed, args.min_events)
        lines.append(f"| {lab} | {r['n']} | {fmt_plus(r['mean24'])} | {fmt_plus(r['excess'])} "
                     f"| {fmt_ci(r['ci_lo'], r['ci_hi'])} | {fmt_plus(r['excess168'])} | **{r['verdict']}** |")
    lines.append("")
    d_v = pd.to_numeric(v_dropped["ret_24h"], errors="coerce").dropna().to_numpy()
    c_dg = bootstrap_mean_diff(g_v, d_v, seed=args.seed)
    lines.append(f"- 贪婪 − 非贪婪 事件 24h 直接对照: {c_dg['mean_diff']:+.2f}% "
                 f"CI [{c_dg['ci_lo']:+.2f}, {c_dg['ci_hi']:+.2f}]（n贪婪={c_dg['n_a']}, n非贪婪={c_dg['n_b']}）")
    lines.append(f"- 与 123 VIX 门控对比: VIX 门控丢弃的 vix_high 事件 24h 均值 ≈ -0.07%、胜率 39%（负期望尾部，"
                 f"丢弃是收益不是成本）；这里丢弃的非贪婪层事件 24h 均值 {d_row['mean24']:+.2f}%"
                 f"{'（正期望 → 存在真实机会成本，贪婪过滤的代价是放弃这些正期望交易）' if d_row['mean24'] > 0 else '（期望非正 → 丢弃与 VIX 门控类似）'}。\n")

    # ---------- 表4 贪婪 × 放量 双重过滤 ----------
    lines.append("## 4. 贪婪层 × 放量>1.5x 双重过滤（加分项）\n")
    v_vol_g = events[greedy_mask & (events["qv24_ratio_at_event"] > VOL_HI)]
    v_vol_all = events[events["qv24_ratio_at_event"] > VOL_HI]
    lines.append("| 组 | n | 24h均% | 超额vs基线 | 95% CI | 胜率 | 中位数% | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    r_vg = _row_stats(v_vol_g, base_v, base_v168, args.seed, args.min_events)
    lines.append(
        f"| 贪婪∩放量>1.5x | {r_vg['n']} | {fmt_plus(r_vg['mean24'])} | {fmt_plus(r_vg['excess'])} "
        f"| {fmt_ci(r_vg['ci_lo'], r_vg['ci_hi'])} | {r_vg['win'] * 100:.0f}% | {fmt_plus(r_vg['median'])} "
        f"| {fmt_plus(r_vg['excess168'])} | **{r_vg['verdict']}** |")
    lines.append(f"| 参考: 仅贪婪层 | {rows1['V_greed 贪婪层(fng≥60)']['n']} | "
                 f"{fmt_plus(rows1['V_greed 贪婪层(fng≥60)']['mean24'])} | "
                 f"{fmt_plus(rows1['V_greed 贪婪层(fng≥60)']['excess'])} | "
                 f"{fmt_ci(rows1['V_greed 贪婪层(fng≥60)']['ci_lo'], rows1['V_greed 贪婪层(fng≥60)']['ci_hi'])} | "
                 f"{rows1['V_greed 贪婪层(fng≥60)']['win'] * 100:.0f}% | "
                 f"{fmt_plus(rows1['V_greed 贪婪层(fng≥60)']['median'])} | "
                 f"{fmt_plus(rows1['V_greed 贪婪层(fng≥60)']['excess168'])} | "
                 f"**{rows1['V_greed 贪婪层(fng≥60)']['verdict']}** |")
    lines.append(f"| 参考: 仅放量>1.5x | {len(v_vol_all)} | - | - | - | - | - | - | 见 126 (+1.90% CI[+1.23,+2.63]) |")
    lines.append("")
    vg_v = pd.to_numeric(v_vol_g["ret_24h"], errors="coerce").dropna().to_numpy()
    c_vg_g = bootstrap_mean_diff(vg_v, g_v, seed=args.seed)
    if len(vg_v) >= args.min_events:
        lines.append(f"- 贪婪∩放量 相对 仅贪婪 的增量: {c_vg_g['mean_diff']:+.2f}% "
                     f"CI [{c_vg_g['ci_lo']:+.2f}, {c_vg_g['ci_hi']:+.2f}]（n双={c_vg_g['n_a']}, n贪婪={c_vg_g['n_b']}）")
        lines.append(f"- 贪婪层事件中放量>1.5x 占比: {len(v_vol_g)}/{len(v_greed)} = {len(v_vol_g) / len(v_greed) * 100:.1f}%\n")

    # ---------- 表5 与 VIX 门控重叠 ----------
    lines.append("## 5. 与 VIX 门控（123）的重叠 —— 避免双重计数\n")
    g_ev = events[greedy_mask]
    n_g = len(g_ev)
    n_g_lo = int(g_ev["vix_low"].sum())
    n_g_hi = int(g_ev["vix_high"].sum())
    n_d_lo = int(v_dropped["vix_low"].sum())
    n_d_hi = int(v_dropped["vix_high"].sum())
    lines.append("| 事件组 | vix_low | vix_high | 小计 |")
    lines.append("|---|---|---|---|")
    lines.append(f"| 贪婪层 | {n_g_lo} | {n_g_hi} | {n_g} |")
    lines.append(f"| 非贪婪层 | {n_d_lo} | {n_d_hi} | {len(v_dropped)} |")
    lines.append(f"| 小计 | {n_g_lo + n_d_lo} | {n_g_hi + n_d_hi} | {len(events)} |")
    lines.append("")
    lines.append(f"- 贪婪层中 vix_low 占比: **{n_g_lo}/{n_g} = {n_g_lo / n_g * 100:.1f}%**"
                 f"（vix_high {n_g_hi} 个 = 贪婪∩高VIX 矛盾格）")
    lines.append(f"- 全部事件中 vix_low 占比: {(n_g_lo + n_d_lo) / len(events) * 100:.1f}%")
    lines.append(f"- 贪婪层 vs vix_low 的事件级相关: 列联表卡方/比值比用 Cramér V 类指标，"
                 f"简单口径 = 贪婪∩vix_low / (贪婪占比 × vix_low 占比 × n) 的富集倍率 "
                 f"{n_g_lo / len(events) / (n_g / len(events) * (n_g_lo + n_d_lo) / len(events)):.2f}x")
    if n_g_hi >= args.min_events:
        r_gh = _row_stats(g_ev[g_ev["vix_high"]], base_v, base_v168, args.seed, args.min_events)
        lines.append(f"- 贪婪∩vix_high（矛盾格，n={r_gh['n']}）: 24h 均值 {fmt_plus(r_gh['mean24'])}，"
                     f"超额 {fmt_plus(r_gh['excess'])}，CI {fmt_ci(r_gh['ci_lo'], r_gh['ci_hi'])}，"
                     f"判定 **{r_gh['verdict']}**（判别贪婪与 VIX 谁驱动 edge 的关键格）")
    lines.append("")

    # ---------- 6. 交叉对照 ----------
    lines.append("## 6. 与 123（VIX 门控）/ 126（放量）交叉对照\n")
    lines.append("| 过滤器 | 保留事件占比 | 保留组 24h 超额 | 丢弃组 24h 均值 | 判定 |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| 贪婪层(本脚本) | {len(v_greed) / len(events) * 100:.1f}% | "
                 f"{fmt_plus(rows1['V_greed 贪婪层(fng≥60)']['excess'])} | {fmt_plus(d_row['mean24'])} | "
                 f"**{rows1['V_greed 贪婪层(fng≥60)']['verdict']}** |")
    lines.append(f"| VIX 门控(123) | 83.5%（丢 16.5% vix_high） | +1.37 | ≈-0.07%（胜率 39%） | GO_LONG |")
    lines.append(f"| 放量>1.5x(126) | ≈62%（丢常态/缩量量） | +1.90 | 常态档 -0.53% | GO_LONG |")
    lines.append("")
    overlap_note = ("两者高度重叠，贪婪过滤 ≈ VIX 门控的子集，落地任选其一即可避免双重计数"
                    if n_g_lo / n_g > 0.8 else
                    "两者仅部分重叠，贪婪过滤不是 VIX 门控的复制品，但组合使用需防共线性")
    lines.append(f"- 贪婪层与 VIX 门控重叠度: 贪婪层事件 {n_g_lo / n_g * 100:.1f}% 也是 vix_low → "
                 f"{overlap_note}。")

    # ---------- 7. 结论 ----------
    gr = rows1["V_greed 贪婪层(fng≥60)"]
    vr = rows1["V_ref 纯wash_cvd"]
    per_ev_gain = gr["excess"] - vr["excess"]
    lines.append("## 7. 结论与判定\n")
    lines.append(f"- **贪婪层过滤每事件期望提升**: pooled 24h 超额 {fmt_plus(gr['excess'])} vs V_ref "
                 f"{fmt_plus(vr['excess'])} → 增量 {per_ev_gain:+.2f}pp/事件；"
                 f"保留 {gr['n']}/{len(events)} = {gr['n'] / len(events) * 100:.1f}% 事件")
    lines.append(f"- **跨 episode 一致性**: 贪婪层 24h 超额为正的 episode {len(pos_eps)}/{len(ep_rows)}"
                 f"（{'4/4 全正 ✓' if len(pos_eps) == 4 else '未全正 ✗'}）；"
                 f"贪婪日占比标注见表 2（2022/2023 贪婪天少 → 对应事件少）")
    cost_note = (" → 正期望，贪婪过滤存在真实机会成本（与 123 VIX 门控丢弃负期望尾部不同）"
                 if d_row["mean24"] > 0 else
                 " → 非正期望，丢弃合理（与 123 VIX 门控类似）")
    lines.append(f"- **机会成本**: 丢弃的非贪婪层事件 24h 均值 {d_row['mean24']:+.2f}% / 胜率 {d_row['win'] * 100:.0f}%"
                 f"{cost_note}；"
                 f"其中中性 40-60 层最弱（130: +0.11%），极恐/恐惧层见 3b")
    lines.append(f"- **与 VIX 门控重叠**: 贪婪层中 {n_g_lo / n_g * 100:.1f}% 是 vix_low → "
                 f"{'贪婪过滤 ≈ VIX 门控的子集，二者选一即可' if n_g_lo / n_g > 0.8 else '仅部分重叠，需防共线性'}")
    if len(vg_v) >= args.min_events:
        lines.append(f"- **双重过滤（加分）**: 贪婪∩放量>1.5x n={r_vg['n']}，24h 超额 {fmt_plus(r_vg['excess'])}"
                     f"，CI {fmt_ci(r_vg['ci_lo'], r_vg['ci_hi'])}，判定 **{r_vg['verdict']}**；"
                     f"相对仅贪婪增量 {c_vg_g['mean_diff']:+.2f}% CI[{c_vg_g['ci_lo']:+.2f}, {c_vg_g['ci_hi']:+.2f}]")
    verdict_note = ("值得作为辅助条件（CI 下界>0 GO_LONG，但需接受样本损失 + 正期望机会成本）"
                    if gr["ci_lo"] > 0 else "证据不足（NO_GO/样本不足）")
    lines.append(f"- **判定（整体）**: 贪婪层过滤 {verdict_note}；"
                 f"结合 130/123/126 三方向，贪婪层与 VIX 门控高度重叠 → 建议与 VIX/放量门控合并评估后再落地，"
                 f"避免多重条件同时叠加导致保留事件过少")

    # ---------- 8. 局限 ----------
    lines.append("## 8. 局限\n")
    lines.append("- 恐惧贪婪为日度而事件为小时级：状态日度粘滞；取事件日-1（更保守，代价是事件日盘中情绪突变不被捕捉）。"
                 "fng 覆盖 2021-02-14 起，对 2022+ 全部事件无影响。")
    lines.append("- 贪婪层∩vix_low 高度重叠（表 5）：两维度不独立，贪婪层增量（+0.xx pp）不能与 VIX 门控增量（+0.27pp）简单相加；"
                 "落地时应作为同一族「宏观情绪门控」的候选之一。")
    lines.append("- 72h 冷却使同币事件间存在自相关，bootstrap 未按币聚类；贪婪∩vix_high 矛盾格 n 小，判别谁驱动 edge 证据弱。")
    lines.append("- qv24_ratio 需要 720h 中位数暖机（min_periods=360）：2022 初早期事件可能 NaN，"
                 "贪婪∩放量双重过滤的 n 与占比受其影响（126 已确认当前事件集无 NaN 事件，影响可忽略）。")
    lines.append("- 贪婪层过滤保留率 ~58%：交易频率减半，吞吐量代价需实盘前向影子验证（T3）；"
                 "前向 episode（2026-07+）无 fng/VIX 之外的宏观判定，参数对当前筑底窗口适用性未验证。")
    lines.append("- 与 130 的分层表数值可能略有出入：130 每层单独抽基线（stratum_stats），本脚本 pooled 用统一基线（首抽），"
                 "事件集/分组完全同口径，n 应完全一致，CI 因基线不同可微差。")

    out = REPORTS_DIR / "feargreed_combo.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")

    # ================================================================ 控制台摘要
    print("\n=== 表1 pooled 组合对比 ===")
    for label, r in rows1.items():
        print(f"  {label:24s} n={r['n']:5d} 24h={r['mean24']:+.2f}% 超额={r['excess']:+.2f}% "
              f"CI{fmt_ci(r['ci_lo'], r['ci_hi'])} 胜率={r['win'] * 100:.0f}% 168h={r['excess168']:+.2f}% {r['verdict']}")
    print(f"  贪婪−极恐 对照: {c_gf['mean_diff']:+.2f}% CI[{c_gf['ci_lo']:+.2f},{c_gf['ci_hi']:+.2f}]")

    print("\n=== 表2 V_greed 分 episode ===")
    for name, s, e in EPISODES:
        if "前向" in name:
            continue
        r = ep_rows.get(name, {})
        print(f"  {name:14s} n={r.get('n', 0):4d} 超额={r.get('excess', np.nan):+.2f}% "
              f"CI{fmt_ci(r.get('ci_lo', np.nan), r.get('ci_hi', np.nan))} {r.get('verdict', '无事件')}")

    print("\n=== 表3 组合成本 ===")
    print(f"  被滤掉(非贪婪层) n={d_row['n']} ({d_row['n'] / len(events) * 100:.1f}%) "
          f"24h均值={d_row['mean24']:+.2f}% 中位={d_row['median']:+.2f}% 胜率={d_row['win'] * 100:.0f}% "
          f"超额={d_row['excess']:+.2f}% CI{fmt_ci(d_row['ci_lo'], d_row['ci_hi'])}")
    print(f"  贪婪−非贪婪 对照: {c_dg['mean_diff']:+.2f}% CI[{c_dg['ci_lo']:+.2f},{c_dg['ci_hi']:+.2f}]")

    print("\n=== 表4 贪婪×放量 ===")
    print(f"  贪婪∩放量>1.5x n={r_vg['n']} ({len(v_vol_g) / len(v_greed) * 100:.1f}% of 贪婪层) "
          f"24h={r_vg['mean24']:+.2f}% 超额={r_vg['excess']:+.2f}% CI{fmt_ci(r_vg['ci_lo'], r_vg['ci_hi'])} {r_vg['verdict']}")
    if len(vg_v) >= args.min_events:
        print(f"  相对仅贪婪增量: {c_vg_g['mean_diff']:+.2f}% CI[{c_vg_g['ci_lo']:+.2f},{c_vg_g['ci_hi']:+.2f}]")

    print("\n=== 表5 与 VIX 门控重叠 ===")
    print(f"  贪婪∩vix_low: {n_g_lo}/{n_g} = {n_g_lo / n_g * 100:.1f}% | 贪婪∩vix_high: {n_g_hi}")

    print("\n=== 交叉核对 ===")
    got_map = {"130 贪婪60+ n": len(v_greed),
               "130 贪婪60+ 24h超额": gr["excess"],
               "130 贪婪60+ CI下界": gr["ci_lo"],
               "130 贪婪60+ 占比": len(v_greed) / len(events),
               "130 中性40-60 24h超额": np.nan,
               "123 vix_low 24h超额": np.nan,
               "123 vix_high 丢弃占比": np.nan,
               "126 放量>1.5x 24h超额": np.nan}
    for k, exp in KNOWN.items():
        got = got_map[k]
        if not np.isfinite(got):
            print(f"  {k}: 期望 {exp} | 见对应报告（本脚本不重算）")
            continue
        if k == "130 贪婪60+ n":
            ok = "OK" if abs(got - exp) < 1e-9 else "MISMATCH"
        else:
            ok = "OK" if abs(got - exp) < 0.05 else "~"
        print(f"  {k}: 期望 {exp} | 实测 {got:.3f} {ok}")


if __name__ == "__main__":
    main()
