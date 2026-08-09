"""131_liquidation_cross.py — wash_cvd × 强平流（coinglass 真 liquidation）交叉事件研究。

命题（机制）：wash_cvd 是唯一已验证的 edge（115 pooled 24h 超额 +1.31% CI[+0.66,+1.63]）。
本脚本用 coinglass **真实逐小时强平数据**（liquidation parquet，2024-06-06 → 2026-06-23，
66/66 universe 全覆盖，time 列与 klines open_time 精确对齐）检验强平流是否调制 wash_cvd，
以及"空头强平级联 = 轧空燃料"在真数据下是否可交易（补 105 用衍生特征近似不可得的空白）：

- 表1 wash_cvd × liq_24h（24h 总强平 USD，对每 symbol 自身 30d 中位数归一）档位：低/中/高
- 表2 wash_cvd × liq_short_z（24h 空头强平累计的自序列 30d z-score）档位：>1 / [-1,1] / <-1
      —— 核心：空头强平激增是否预示后续轧空
- 表3 独立事件研究：强平级联（liq_short_z>2 且 ret_24h<+5%，72h 冷却，Long）自身
      24h/168h 超额——验证"空头强平级联=轧空"（对照 105 liq_cascade_short NO_GO）

数据：COINGLASS_RAW1H = C:\\Users\\10639\\Desktop\\🔒 加密资产\\coinglass_db\\raw_1h
  - liquidation/{symbol}.parquet：time(ms Int64) / long_liquidation_usd / short_liquidation_usd
  - klines/{symbol}.parquet：close / quote_volume / taker_buy_quote_volume（CVD，经 113 清洗）
事件：m115.detect_events(...,"wash_cvd")（washout(price_z<-2 或 ret_24h<-8%) 且 cvd_div>2.0，
72h 冷却，Long）；强平特征在事件时点 asof 取值（np.searchsorted side='right'-1，无前视）。
窗口：liquidation 只覆盖 2024-06+ → 只测 2024崩→恢复 / 2025顶→熊 两个 episode + pooled
（lo=2024-06-01 hi=2026-06-23 UTC）。基线：draw_random_events + bootstrap_ci(seed=2026)。
判定：CI 下界>0→GO_LONG / 上界<0→GO_SHORT / 含0→NO_GO / n<30→样本不足。

用法：
  python scripts/131_liquidation_cross.py [--n-baseline 3000] [--seed 2026]
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

# ---------- 共享加载模板（113/115 口径，禁止改配置） ----------
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

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
detect_events = m115.detect_events
EPISODES = m113.EPISODES
episode_of = m113.episode_of

COINGLASS_RAW1H = m113.COINGLASS_RAW1H
LIQ_DIR = COINGLASS_RAW1H / "liquidation"

# ---------- 研究窗口与参数 ----------
# liquidation 覆盖 2024-06-06 14:00 → 2026-06-23 03:00 UTC（小时网格与 klines 对齐）
LO_MS = int(pd.Timestamp("2024-06-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-23", tz="UTC").timestamp() * 1000)
HOUR_MS = 3_600_000
N_BASELINE = 3000
SEED = 2026
MIN_EVENTS = 30
COOLDOWN_H = 72.0
CASCADE_Z = 2.0      # 表3：liq_short_z > 2
CASCADE_RET = 5.0    # 表3：ret_24h < +5%（24h 未大涨，未跑飞，同 105 price_filter）
LIQ_RATIO_LO = 0.5   # 表1档位：liq_24h / 30d中位数 ≤0.5 → 低
LIQ_RATIO_HI = 1.5   # 表1档位：>1.5 → 高；之间 → 中

# 只测 liquidation 覆盖区间内的两个 episode
EPISODES_LIQ = ["2024崩→恢复", "2025顶→熊"]

# 105 已知数字（event_study_summary.csv，2024-06-01~2026-05-27，衍生特征近似，48h 冷却）
KNOWN_105 = {
    "n": 4848,
    "mean24": 0.465,      # +0.47%
    "ci_lo": -0.0116,     # [-0.01, +0.54] 含 0 → NO_GO
    "ci_hi": 0.5366,
    "verdict": "NO_GO",
}


# ---------- 强平特征 ----------
def add_liq_features(ctxs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """在 ctx 基础上补强平特征（全部对齐到 ctx index，asof 口径，无前视）：

    liq_24h        : 24h 总强平 USD = rolling(24).sum(long+short)
    liq_long_share : 24h long 强平占比 = rolling(24).sum(long) / liq_24h
    liq_short_z    : 24h 空头强平累计的自序列 30d(720h) z-score（m113.rolling_z 复用）
    liq_long_z     : 24h 多头强平累计的自序列 30d(720h) z-score
    liq_med_720    : liq_24h 自身 30d(720h) rolling 中位数（表1 归一基准，min_periods=360）
    """
    zwin = 720
    for sym, t in ctxs.items():
        p = LIQ_DIR / f"{sym}.parquet"
        if not p.exists():
            for col in ["liq_24h", "liq_long_share", "liq_short_z", "liq_long_z", "liq_med_720"]:
                t[col] = np.nan
            continue
        df = pd.read_parquet(p)
        if "time" not in df.columns or "long_liquidation_usd" not in df.columns \
                or "short_liquidation_usd" not in df.columns:
            continue
        ts = pd.to_numeric(df["time"], errors="coerce").to_numpy(dtype=np.int64)
        liq_long = pd.to_numeric(df["long_liquidation_usd"], errors="coerce").to_numpy(dtype=float)
        liq_short = pd.to_numeric(df["short_liquidation_usd"], errors="coerce").to_numpy(dtype=float)
        lon = pd.Series(liq_long, index=pd.Index(ts))
        sho = pd.Series(liq_short, index=pd.Index(ts))
        lon = lon[~lon.index.duplicated(keep="last")].sort_index().reindex(t.index)
        sho = sho[~sho.index.duplicated(keep="last")].sort_index().reindex(t.index)
        long24 = lon.rolling(24).sum()
        short24 = sho.rolling(24).sum()
        liq24 = long24 + short24
        t["liq_24h"] = liq24.replace([np.inf, -np.inf], pd.NA)
        denom = liq24.replace(0, pd.NA)
        t["liq_long_share"] = (long24 / denom).replace([np.inf, -np.inf], pd.NA)
        t["liq_short_z"] = m113.rolling_z(short24, zwin)
        t["liq_long_z"] = m113.rolling_z(long24, zwin)
        t["liq_med_720"] = liq24.rolling(zwin, min_periods=360).median()
    return ctxs


def attach_liq_asof(ctxs: dict[str, pd.DataFrame], events: pd.DataFrame) -> pd.DataFrame:
    """对每个事件 ts 用 np.searchsorted 取事件行及之前最近的有效强平特征（asof，无前视）。"""
    ev = events.copy()
    cols = ["liq_24h", "liq_long_share", "liq_short_z", "liq_long_z", "liq_med_720"]
    for c in cols:
        ev[f"{c}_at_event"] = np.nan
    for sym, g in ev.groupby("symbol", sort=False):
        if sym not in ctxs:
            continue
        t = ctxs[sym]
        idx = t.index.to_numpy(dtype=np.int64)
        pos = np.searchsorted(idx, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(idx) - 1)
        for c in cols:
            if c not in t.columns:
                continue
            vals = pd.to_numeric(t[c], errors="coerce").to_numpy(dtype=float)
            ev.loc[g.index, f"{c}_at_event"] = vals[pos]
    return ev


def detect_liq_cascade_events(sym: str, ctx: pd.DataFrame, cooldown_h: float) -> pd.DataFrame:
    """表3：空头强平级联事件 = liq_short_z>2 且 ret_24h<+5%（Long，72h 冷却，无前视）。

    对照 105 liq_cascade_short（liq_short_z>=2，price_filter ret_24h<=5%，48h 冷却）；
    这里用 coinglass 真 liquidation 数据 + 72h 冷却（与 wash_cvd 同口径）。
    """
    axis = ctx.index.to_numpy()
    lsz = pd.to_numeric(ctx["liq_short_z"], errors="coerce").to_numpy(dtype=float)
    ret24 = pd.to_numeric(ctx["ret_24h"], errors="coerce").to_numpy(dtype=float)
    fired = np.isfinite(lsz) & np.isfinite(ret24) & (lsz > CASCADE_Z) & (ret24 < CASCADE_RET)

    cooldown_ms = int(cooldown_h * HOUR_MS)
    events: list[int] = []
    last: int | None = None
    for i in np.flatnonzero(fired):
        ts = int(axis[i])
        if last is None or (ts - last) >= cooldown_ms:
            events.append(ts)
            last = ts
    if not events:
        return pd.DataFrame(columns=["symbol", "timestamp"])
    return pd.DataFrame({
        "symbol": sym,
        "timestamp": np.array(events, dtype=np.int64),
    })


# ---------- 事件研究工具（126 同款） ----------
def build_baseline(ctxs: dict[str, pd.DataFrame], rng: np.random.Generator,
                   start_ms: int, end_ms: int, n: int) -> pd.DataFrame:
    base = draw_random_events(ctxs, n, rng, max_forward_hours=168,
                              start_ms=start_ms, end_ms=end_ms)
    if base.empty:
        return pd.DataFrame()
    parts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            parts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def excess(ev_rets: np.ndarray, base_rets: np.ndarray, seed: int) -> dict:
    return bootstrap_ci(np.asarray(ev_rets, dtype=float),
                        np.asarray(base_rets, dtype=float),
                        n_boot=1000, alpha=0.05, seed=seed)


def verdict_for(n: int, ci: dict, min_events: int) -> str:
    if n < min_events:
        return "样本不足"
    if not np.isfinite(ci.get("ci_lo", np.nan)) or not np.isfinite(ci.get("ci_hi", np.nan)):
        return "无基线"
    if ci["ci_lo"] > 0:
        return "GO_LONG"
    if ci["ci_hi"] < 0:
        return "GO_SHORT"
    return "NO_GO"


def stats_row(ev: pd.DataFrame, base: pd.DataFrame, label: str,
              min_events: int, seed: int) -> dict:
    n = len(ev)
    r: dict = {"label": label, "n": n}
    ev24 = pd.to_numeric(ev["ret_24h"], errors="coerce").dropna().to_numpy()
    ev168 = pd.to_numeric(ev["ret_168h"], errors="coerce").dropna().to_numpy()
    if len(ev24) == 0 or base.empty:
        r.update(mean24=np.nan, ex24=np.nan, ci_lo=np.nan, ci_hi=np.nan,
                 ex168=np.nan, win=np.nan,
                 verdict="无事件" if n == 0 else "无基线")
        return r
    ci24 = excess(ev24, pd.to_numeric(base["ret_24h"], errors="coerce").dropna().to_numpy(), seed)
    ci168 = excess(ev168, pd.to_numeric(base["ret_168h"], errors="coerce").dropna().to_numpy(), seed) \
        if len(ev168) else {"mean_diff": np.nan}
    r.update(
        mean24=float(np.nanmean(ev24)),
        ex24=ci24["mean_diff"], ci_lo=ci24["ci_lo"], ci_hi=ci24["ci_hi"],
        ex168=ci168.get("mean_diff", np.nan),
        win=float((ev24 > 0).mean()),
        verdict=verdict_for(len(ev24), ci24, min_events),
    )
    return r


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


def liq_level_group(ratio: float) -> str:
    if pd.isna(ratio):
        return "NaN(暖机不足)"
    if ratio <= LIQ_RATIO_LO:
        return "低 ≤0.5x"
    if ratio > LIQ_RATIO_HI:
        return "高 >1.5x"
    return "中 0.5~1.5x"


def short_z_group(z: float) -> str:
    if pd.isna(z):
        return "NaN(暖机不足)"
    if z > 1.0:
        return "激增 >1"
    if z < -1.0:
        return "萎缩 <-1"
    return "常态 [-1,1]"


# ---------- 报告辅助 ----------
def table_header(extra_cols: str = "") -> str:
    return f"| 组 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 24h胜率 | 判定 {extra_cols}|"


def table_sep(extra: int = 0) -> str:
    return "|" + "---|" * (7 + extra)


def row_line(r: dict, group_label: str | None = None) -> str:
    label = r["label"] if group_label is None else group_label
    return (f"| {label} | {r['n']} | {fmt(r.get('mean24'))} "
            f"| {fmt(r.get('ex24'), plus=True)} | {fmt_ci(r)} "
            f"| {fmt(r.get('ex168'), plus=True)} | {fmt_win(r.get('win'))} "
            f"| **{r['verdict']}** |")


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

    rng = np.random.default_rng(args.seed)

    # ---------- wash_cvd 事件（lo..hi 窗口） ----------
    evs = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            evs.append(ev)
    wc_events = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame(
        columns=["symbol", "timestamp"])
    wc_events = wc_events[(wc_events["timestamp"] >= LO_MS) & (wc_events["timestamp"] <= HI_MS)]
    wc_events = wc_events.reset_index(drop=True)
    fwd_parts = []
    for sym, g in wc_events.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=DEFAULT_HORIZONS))
    wc_events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else wc_events
    wc_events = attach_liq_asof(ctxs, wc_events)
    wc_events["episode"] = episode_of(wc_events["timestamp"].to_numpy())
    print(f"wash_cvd 事件（{pd.Timestamp(LO_MS, unit='ms', tz='UTC'):%Y-%m-%d}~"
          f"{pd.Timestamp(HI_MS, unit='ms', tz='UTC'):%Y-%m-%d}）: {len(wc_events)}")
    for name, _, _ in EPISODES:
        n_ep = int((wc_events["episode"] == name).sum())
        if n_ep:
            print(f"  {name:16s} n={n_ep}")

    # ---------- 强平级联事件（表3，独立检测） ----------
    cevs = []
    for sym, ctx in ctxs.items():
        ev = detect_liq_cascade_events(sym, ctx, COOLDOWN_H)
        if not ev.empty:
            cevs.append(ev)
    cas_events = pd.concat(cevs, ignore_index=True) if cevs else pd.DataFrame(
        columns=["symbol", "timestamp"])
    cas_events = cas_events[(cas_events["timestamp"] >= LO_MS) & (cas_events["timestamp"] <= HI_MS)]
    cas_events = cas_events.reset_index(drop=True)
    fwd_parts = []
    for sym, g in cas_events.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=DEFAULT_HORIZONS))
    cas_events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else cas_events
    cas_events = attach_liq_asof(ctxs, cas_events)
    cas_events["episode"] = episode_of(cas_events["timestamp"].to_numpy())
    print(f"强平级联事件（liq_short_z>{CASCADE_Z} 且 ret_24h<+{CASCADE_RET}%，"
          f"{COOLDOWN_H:.0f}h 冷却）: {len(cas_events)}")
    for name, _, _ in EPISODES:
        n_ep = int((cas_events["episode"] == name).sum())
        if n_ep:
            print(f"  {name:16s} n={n_ep}")

    # ---------- 基线：pooled 首抽，随后各 episode（只测 2024/2025 两档） ----------
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

    def window_base(ep: str, pooled_base: pd.DataFrame) -> pd.DataFrame:
        return pooled_base if ep == "pooled" else base_by_ep.get(ep, pd.DataFrame())

    # ---------- 表1/表2 分档统计 ----------
    wc_events["liq_level"] = (wc_events["liq_24h_at_event"]
                              / wc_events["liq_med_720_at_event"].replace(0, pd.NA)).apply(liq_level_group)
    wc_events["short_z_grp"] = wc_events["liq_short_z_at_event"].apply(short_z_group)

    def strat_rows(events: pd.DataFrame, grp_col: str, groups: list[str],
                   base_pooled: pd.DataFrame) -> dict[str, list[dict]]:
        rows: dict[str, list[dict]] = {}
        for gname in groups:
            gsub = events[events[grp_col] == gname]
            rows[gname] = []
            for ep in ["pooled"] + EPISODES_LIQ:
                sub = gsub if ep == "pooled" else gsub[gsub["episode"] == ep]
                if len(sub) == 0:
                    rows[gname].append({"label": f"{ep}:{gname}", "n": 0, "mean24": np.nan,
                                        "ex24": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
                                        "ex168": np.nan, "win": np.nan, "verdict": "无事件"})
                    continue
                r = stats_row(sub, window_base(ep, base_pooled), f"{ep}:{gname}",
                              args.min_events, args.seed)
                rows[gname].append(r)
        return rows

    t1_groups = ["低 ≤0.5x", "中 0.5~1.5x", "高 >1.5x", "NaN(暖机不足)"]
    t2_groups = ["激增 >1", "常态 [-1,1]", "萎缩 <-1", "NaN(暖机不足)"]
    t1 = strat_rows(wc_events, "liq_level", t1_groups, base_pooled)
    t2 = strat_rows(wc_events, "short_z_grp", t2_groups, base_pooled)

    # 直接对比（pooled 事件集直比，bootstrap_ci 差异）
    def direct_contrast(events: pd.DataFrame, a_mask: pd.Series, b_mask: pd.Series,
                        name_a: str, name_b: str) -> dict:
        ra = pd.to_numeric(events.loc[a_mask, "ret_24h"], errors="coerce").dropna().to_numpy()
        rb = pd.to_numeric(events.loc[b_mask, "ret_24h"], errors="coerce").dropna().to_numpy()
        return {"a": name_a, "b": name_b, "n_a": len(ra), "n_b": len(rb),
                **excess(ra, rb, args.seed)}

    t1_hi_lo = direct_contrast(wc_events, wc_events["liq_level"] == "高 >1.5x",
                               wc_events["liq_level"] == "低 ≤0.5x", "高 >1.5x", "低 ≤0.5x")
    t1_hi_mid = direct_contrast(wc_events, wc_events["liq_level"] == "高 >1.5x",
                                wc_events["liq_level"] == "中 0.5~1.5x", "高 >1.5x", "中 0.5~1.5x")
    t2_surge_mid = direct_contrast(wc_events, wc_events["short_z_grp"] == "激增 >1",
                                   wc_events["short_z_grp"] == "常态 [-1,1]",
                                   "激增 >1", "常态 [-1,1]")
    t2_surge_shrink = direct_contrast(wc_events, wc_events["short_z_grp"] == "激增 >1",
                                      wc_events["short_z_grp"] == "萎缩 <-1",
                                      "激增 >1", "萎缩 <-1")

    # ---------- 表3 强平级联统计 ----------
    t3 = {"pooled": stats_row(cas_events, base_pooled, "pooled", args.min_events, args.seed)}
    for name, s, e in EPISODES:
        if name not in EPISODES_LIQ:
            continue
        sub = cas_events[cas_events["episode"] == name]
        t3[name] = stats_row(sub, base_by_ep[name], name, args.min_events, args.seed)

    # ---------- 报告 ----------
    lines: list[str] = []
    lines.append("# wash_cvd × 强平流（coinglass 真 liquidation）交叉事件研究\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 方法: wash_cvd 事件（m115.detect_events，washout(price_z<-2 或 ret_24h<-8%) "
                 f"且 cvd_divergence>2.0，72h 冷却，Long），事件 ts 限制 {LO_MS}~{HI_MS} ms "
                 f"（2024-06-01 ~ 2026-06-23 UTC，liquidation 覆盖区间）；强平特征=逐 symbol 读 "
                 f"liquidation parquet → 对齐 ctx index（时间轴与 klines open_time 精确对齐）→ "
                 f"24h 累计（rolling(24).sum()）→ 30d(720h) 自序列 z-score（m113.rolling_z，"
                 f"min_periods=360）与 30d 中位数（表1 归一基准），事件时点 asof 取值"
                 f"（np.searchsorted side='right'-1，无前视）；基线=draw_random_events + "
                 f"bootstrap_ci(seed={args.seed}, n={args.n_baseline})，pooled 首抽、episode 各抽"
                 f"一次并分档共用同一基线（横向可比）。")
    lines.append(f"- 数据源: COINGLASS_RAW1H = {COINGLASS_RAW1H}"
                 f"（liquidation/{'{symbol}'}.parquet: time/long_liquidation_usd/"
                 f"short_liquidation_usd，2024-06-06 14:00 ~ 2026-06-23 03:00 UTC，"
                 f"66/66 universe 全覆盖，小时网格与 klines 对齐；klines: close/quote_volume/"
                 f"taker_buy_quote_volume → CVD）；FUNDING_DIR = {m113.FUNDING_DIR}；"
                 f"PROJECT_ROOT = {PROJECT_ROOT}")
    lines.append(f"- 判定: CI 下界>0 → GO_LONG；上界<0 → GO_SHORT；含 0 → NO_GO；"
                 f"n<{args.min_events} → 样本不足不判；24h 胜率 = P(ret_24h>0)")
    lines.append("- 窗口限制: liquidation 只覆盖 2024-06+ → 只测 2024崩→恢复 / 2025顶→熊 "
                 "两个 episode + pooled；coinglass klines 2026-06-23 23:00 → 06-30 04:00 "
                 "约 6.3 天全 universe 空档（liquidation 到 06-23 衔接），事件尾部 forward "
                 "收益可能 NaN，轻微减少样本，不影响结论。\n")

    # 0. 特征覆盖
    lines.append("## 0. 特征覆盖\n")
    liq_cov = {sym: int(t["liq_24h"].notna().sum()) for sym, t in ctxs.items()
               if "liq_24h" in t.columns}
    n_sym_liq = sum(v > 0 for v in liq_cov.values())
    first_valid = min((t.index[t["liq_short_z"].notna()].min() for t in ctxs.values()
                       if "liq_short_z" in t.columns and t["liq_short_z"].notna().any()),
                      default=None)
    lines.append(f"- {n_sym_liq}/{len(ctxs)} symbol 有强平数据；liq_short_z 最早有效时点 ≈ "
                 f"{pd.Timestamp(first_valid, unit='ms', tz='UTC'):%Y-%m-%d %H:%M} UTC"
                 f"（24h 累计 + 720h z-score 暖机后）")
    wc_liq_finite = int(wc_events["liq_24h_at_event"].notna().sum())
    lines.append(f"- wash_cvd 事件 {len(wc_events)} 中，事件时 liq_24h 有效 "
                 f"{wc_liq_finite}（{wc_liq_finite / max(len(wc_events), 1):.1%}），"
                 f"NaN 为 2024-06 暖机期事件")
    lines.append("")

    # 1. 表1
    lines.append("## 1. 表1 wash_cvd × liq_24h 档位（vs 同期随机基线）\n")
    lines.append("分档：事件时 liq_24h（24h 总强平 USD）对该 symbol 自身 30d(720h) 中位数归一："
                 f"低 ≤{LIQ_RATIO_LO}x / 中 {LIQ_RATIO_LO}~{LIQ_RATIO_HI}x / 高 >{LIQ_RATIO_HI}x。"
                 "问：强平总量是否调制 wash_cvd edge？\n")
    lines.append(table_header())
    lines.append(table_sep())
    for gname in t1_groups:
        rows = t1[gname]
        for r in rows:
            if r["n"] == 0 and gname == "NaN(暖机不足)":
                continue
            lines.append(row_line(r))
    lines.append("")
    lines.append("直接对比（wash_cvd 事件集直比，bootstrap 95% CI，seed="
                 f"{args.seed}）\n")
    lines.append("| 对比 | n1 vs n2 | 24h均值差 | 95% CI |")
    lines.append("|---|---|---|---|")
    for dc in [t1_hi_lo, t1_hi_mid]:
        lines.append(f"| {dc['a']} − {dc['b']} | {dc['n_a']} vs {dc['n_b']} "
                     f"| {fmt(dc['mean_diff'], plus=True)} "
                     f"| [{fmt(dc['ci_lo'], plus=True)}, {fmt(dc['ci_hi'], plus=True)}] |")
    lines.append("")

    # 2. 表2
    lines.append("## 2. 表2 wash_cvd × liq_short_z 档位（vs 同期随机基线）\n")
    lines.append("分档：事件时 liq_short_z（24h 空头强平累计的 30d z-score）：激增 >1 / "
                 "常态 [-1,1] / 萎缩 <-1。**核心问题：空头强平激增是否预示后续轧空（更高 24h 超额）？**\n")
    lines.append(table_header())
    lines.append(table_sep())
    for gname in t2_groups:
        rows = t2[gname]
        for r in rows:
            if r["n"] == 0 and gname == "NaN(暖机不足)":
                continue
            lines.append(row_line(r))
    lines.append("")
    lines.append("直接对比（wash_cvd 事件集直比，bootstrap 95% CI，seed="
                 f"{args.seed}）\n")
    lines.append("| 对比 | n1 vs n2 | 24h均值差 | 95% CI |")
    lines.append("|---|---|---|---|")
    for dc in [t2_surge_mid, t2_surge_shrink]:
        lines.append(f"| {dc['a']} − {dc['b']} | {dc['n_a']} vs {dc['n_b']} "
                     f"| {fmt(dc['mean_diff'], plus=True)} "
                     f"| [{fmt(dc['ci_lo'], plus=True)}, {fmt(dc['ci_hi'], plus=True)}] |")
    lines.append("")

    # 3. 表3
    lines.append("## 3. 表3 强平级联事件研究（coinglass 真 liquidation）\n")
    lines.append(f"事件：liq_short_z > {CASCADE_Z} 且 ret_24h < +{CASCADE_RET}%（24h 未大涨），"
                 f"{COOLDOWN_H:.0f}h 冷却，Long 方向。对照 105 liq_cascade_short："
                 f"liq_short_z>=2 且 ret_24h<=5%，48h 冷却，n={KNOWN_105['n']}，"
                 f"24h 均值 {KNOWN_105['mean24']:+.2f}%，CI "
                 f"[{KNOWN_105['ci_lo']:+.2f}, {KNOWN_105['ci_hi']:+.2f}] 含 0 → **NO_GO**"
                 f"（105 用 coinglass API 衍生特征近似，此处为逐小时真数据）。\n")
    lines.append(table_header())
    lines.append(table_sep())
    for ep in ["pooled"] + EPISODES_LIQ:
        lines.append(row_line(t3[ep]))
    lines.append("")
    lines.append("与 105 对照\n")
    lines.append("| 项 | 105（衍生特征近似，48h冷却） | 131（真 liquidation，72h冷却） |")
    lines.append("|---|---|---|")
    p = t3["pooled"]
    lines.append(f"| 事件数 | {KNOWN_105['n']} | {p['n']} |")
    lines.append(f"| 24h均值 | {KNOWN_105['mean24']:+.2f}% | {fmt(p.get('mean24'))} |")
    lines.append(f"| 24h CI | [{KNOWN_105['ci_lo']:+.2f}, {KNOWN_105['ci_hi']:+.2f}] "
                 f"| {fmt_ci(p)} |")
    lines.append(f"| 判定 | **{KNOWN_105['verdict']}** | **{p['verdict']}** |")
    lines.append("")

    # 4. 判定
    lines.append("## 4. 判定\n")
    # 表1
    hi_p = t1["高 >1.5x"][0]
    mid_p = t1["中 0.5~1.5x"][0]
    lo_p = t1["低 ≤0.5x"][0]
    hi_pos = (np.isfinite(hi_p.get("ex24", np.nan)) and hi_p["ex24"] > 0
              and hi_p["verdict"] == "GO_LONG")
    t1_mod = (np.isfinite(hi_p.get("ex24", np.nan)) and np.isfinite(lo_p.get("ex24", np.nan))
              and t1_hi_lo["ci_lo"] > 0 and hi_p["ex24"] > lo_p["ex24"])
    lines.append(f"- **表1（强平总量调制）**：高档 pooled n={hi_p['n']}，24h 超额 "
                 f"{fmt(hi_p.get('ex24'), plus=True)}（CI {fmt_ci(hi_p)}）；中档 n={mid_p['n']}，"
                 f"{fmt(mid_p.get('ex24'), plus=True)}；低档 n={lo_p['n']}，"
                 f"{fmt(lo_p.get('ex24'), plus=True)}。直接对比 高−低 {fmt(t1_hi_lo['mean_diff'], plus=True)}"
                 f"（CI [{fmt(t1_hi_lo['ci_lo'], plus=True)}, {fmt(t1_hi_lo['ci_hi'], plus=True)}]），"
                 f"高−中 {fmt(t1_hi_mid['mean_diff'], plus=True)}"
                 f"（CI [{fmt(t1_hi_mid['ci_lo'], plus=True)}, {fmt(t1_hi_mid['ci_hi'], plus=True)}]）→ "
                 f"{'强平总量显著调制 wash_cvd（高档更强）' if t1_mod else '强平总量对 wash_cvd 的调制不显著'}。")
    # 表2
    sg_p = t2["激增 >1"][0]
    mid_p2 = t2["常态 [-1,1]"][0]
    shr_p = t2["萎缩 <-1"][0]
    t2_mod = (np.isfinite(sg_p.get("ex24", np.nan)) and np.isfinite(mid_p2.get("ex24", np.nan))
              and t2_surge_mid["ci_lo"] > 0 and sg_p["ex24"] > mid_p2["ex24"])
    lines.append(f"- **表2（空头强平激增 → 轧空？）**：激增 >1 档 pooled n={sg_p['n']}，24h 超额 "
                 f"{fmt(sg_p.get('ex24'), plus=True)}（CI {fmt_ci(sg_p)}）；常态 n={mid_p2['n']}，"
                 f"{fmt(mid_p2.get('ex24'), plus=True)}；萎缩 n={shr_p['n']}，"
                 f"{fmt(shr_p.get('ex24'), plus=True)}。直接对比 激增−常态 "
                 f"{fmt(t2_surge_mid['mean_diff'], plus=True)}"
                 f"（CI [{fmt(t2_surge_mid['ci_lo'], plus=True)}, {fmt(t2_surge_mid['ci_hi'], plus=True)}]），"
                 f"激增−萎缩 {fmt(t2_surge_shrink['mean_diff'], plus=True)}"
                 f"（CI [{fmt(t2_surge_shrink['ci_lo'], plus=True)}, "
                 f"{fmt(t2_surge_shrink['ci_hi'], plus=True)}]）→ "
                 f"{'空头强平激增档显著强于常态档（轧空燃料确认）' if t2_mod else '空头强平激增对 wash_cvd 的调制不显著'}。")
    # 表3
    p3 = t3["pooled"]
    t3_ok = p3["verdict"] == "GO_LONG" and p3["n"] >= args.min_events
    lines.append(f"- **表3（强平级联自身可交易？）**：pooled n={p3['n']}，24h 均值 "
                 f"{fmt(p3.get('mean24'))}，超额 {fmt(p3.get('ex24'), plus=True)}"
                 f"（CI {fmt_ci(p3)}），168h 超额 {fmt(p3.get('ex168'), plus=True)}，"
                 f"胜率 {fmt_win(p3.get('win'))}，判定 **{p3['verdict']}**。"
                 f"对照 105 衍生特征近似 NO_GO（CI [-0.01, +0.54]）→ "
                 f"{'真数据下空头强平级联可交易（GO_LONG），与 105 衍生特征结论相反' if t3_ok else '真数据下空头强平级联仍不可交易/样本不足（与 105 一致或证据不足）'}。")
    lines.append("")

    # 5. 局限
    lines.append("## 5. 局限\n")
    lines.append(f"- liquidation 只覆盖 2024-06-06 → 2026-06-23：只测 2024崩→恢复 / 2025顶→熊 "
                 f"两个 episode + pooled，2022/2023 磨底/蓄力期的强平流不可测（wash_cvd 全历史 "
                 f"edge 不受影响，但强平调制是否跨周期成立未验证）。")
    lines.append("- 强平特征需 24h 累计 + 720h z-score/中位数暖机（min_periods=360）：2024-06 "
                 f"暖机期事件归入 NaN(暖机不足) 档（数量见上表），不参与调制判定。")
    lines.append("- 表3 对照 105 含口径差异：冷却 72h vs 48h、真数据 vs 衍生特征近似、事件窗口 "
                 f"2024-06~2026-06-23 vs 2024-06~2026-05-27；方向性结论以 131 事件集为准，"
                 f"跨口径对比仅供参考。")
    lines.append("- coinglass klines 2026-06-23 23:00 → 06-30 04:00 约 6.3 天全 universe 空档："
                 "事件 ts 上限 2026-06-23，尾部事件 forward 收益可能 NaN（forward_stats 自动置 "
                 "NaN），轻微减少样本，不影响结论。")
    lines.append("- 表1/表2 档位基线为同期随机基线（非条件化），档间直接对比（高−低 / 激增−常态）"
                 "才是调制量的净估计；分 episode 基线为独立抽样，数值在抽样误差内可比。")
    lines.append("- liq_long_share / liq_long_z 已构建但未用于本报告主表（多头强平侧留作后续"
                 "下跌/空头侧研究）；表2/表3 聚焦空头强平（轧空燃料）。")
    lines.append("- 未做参数敏感性（2.0/5.0 阈值、档位边界 0.5/1.5）、未做样本外前向验证"
                 "（当前筑底窗口只有影子数据）；四维联合筛选（如与 126 放量、124 breadth 门控）"
                 "是后续工作。")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "liquidation_cross.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")

    # ---------- 控制台三表摘要 ----------
    print("\n=== 表1 wash_cvd × liq_24h 档位（低/中/高） ===")
    print("组 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 24h胜率 | 判定")
    for gname in t1_groups:
        for r in t1[gname]:
            if r["n"] == 0 and gname == "NaN(暖机不足)":
                continue
            print(row_line(r))
    print(f"直接对比 高−低: {fmt(t1_hi_lo['mean_diff'], plus=True)} "
          f"CI[{fmt(t1_hi_lo['ci_lo'], plus=True)}, {fmt(t1_hi_lo['ci_hi'], plus=True)}] | "
          f"高−中: {fmt(t1_hi_mid['mean_diff'], plus=True)} "
          f"CI[{fmt(t1_hi_mid['ci_lo'], plus=True)}, {fmt(t1_hi_mid['ci_hi'], plus=True)}]")

    print("\n=== 表2 wash_cvd × liq_short_z 档位（激增/常态/萎缩） ===")
    print("组 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 24h胜率 | 判定")
    for gname in t2_groups:
        for r in t2[gname]:
            if r["n"] == 0 and gname == "NaN(暖机不足)":
                continue
            print(row_line(r))
    print(f"直接对比 激增−常态: {fmt(t2_surge_mid['mean_diff'], plus=True)} "
          f"CI[{fmt(t2_surge_mid['ci_lo'], plus=True)}, {fmt(t2_surge_mid['ci_hi'], plus=True)}] | "
          f"激增−萎缩: {fmt(t2_surge_shrink['mean_diff'], plus=True)} "
          f"CI[{fmt(t2_surge_shrink['ci_lo'], plus=True)}, {fmt(t2_surge_shrink['ci_hi'], plus=True)}]")

    print("\n=== 表3 强平级联事件研究 ===")
    print("组 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 24h胜率 | 判定")
    for ep in ["pooled"] + EPISODES_LIQ:
        print(row_line(t3[ep]))
    print(f"105 对照: n={KNOWN_105['n']} 24h均值={KNOWN_105['mean24']:+.2f}% "
          f"CI=[{KNOWN_105['ci_lo']:+.2f}, {KNOWN_105['ci_hi']:+.2f}] → {KNOWN_105['verdict']}")


if __name__ == "__main__":
    main()
