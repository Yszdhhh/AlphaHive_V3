r"""141_oi_quadrant_cross.py — wash_cvd × OI×价格四象限交叉研究

背景：botv2_demo_deps 因子引擎侦察发现 OI×价格 2×2 象限维度
（Q1_NEW_LONGS / Q2_NEW_SHORTS / Q3_SHORT_COVER / Q4_LONG_LIQ）是 V3 未测的
持仓结构维度。Q3（OI↓价↑=空头回补）/ Q4（OI↓价↓=多头强平）= "杠杆被清洗"的
直接结构证据——wash_cvd（washout 出清 + 卖压枯竭）事件后若落在此二象限，
是空头/杠杆被清洗的微观确认，可能富集轧空燃料。

口径（与 131/134 完全一致，禁止改配置）：
- 事件 = detect_events(variant="wash_cvd")（115 权威定义，72h 冷却）
- 窗口 = 2024-06-01 → 2026-06-23（coinglass OI 覆盖区间）
- 基线 = 同窗口随机 symbol 横截面（bootstrap CI vs 基线）
- 象限阈值 = botv2 factor_graph_config 定义：OI 4h 变化 ±0.2%、价格 4h 变化 ±0.15%
- 象限取事件时点 asof（side="right"-1，无前视）

输出：reports/oi_quadrant_cross.md
用法：python scripts/141_oi_quadrant_cross.py [--n-baseline 3000] [--seed 2026]
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
HOUR_MS = 3_600_000

# ---------- 研究窗口与参数 ----------
# coinglass OI 覆盖 2024-06+（不可回填）；对齐 131 的 liq 窗口
LO_MS = int(pd.Timestamp("2024-06-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-23", tz="UTC").timestamp() * 1000)
N_BASELINE = 3000
SEED = 2026
MIN_EVENTS = 30

# botv2 factor_graph_config 象限阈值
OI_TH = 0.2     # OI 4h 变化 % 阈值
RET_TH = 0.15   # 价格 4h 变化 % 阈值

EPISODES_OI = ["2024崩→恢复", "2025顶→熊"]


def quadrant_of(oi_chg: float, ret_4h: float) -> str:
    """OI×价格 2×2 象限（botv2 定义）。NaN 输入 → NaN。"""
    if pd.isna(oi_chg) or pd.isna(ret_4h):
        return "NaN(无OI)"
    up_oi = oi_chg >= OI_TH
    dn_oi = oi_chg <= -OI_TH
    up_px = ret_4h >= RET_TH
    dn_px = ret_4h <= -RET_TH
    if up_oi and up_px:
        return "Q1_NEW_LONGS"
    if up_oi and dn_px:
        return "Q2_NEW_SHORTS"
    if dn_oi and up_px:
        return "Q3_SHORT_COVER"
    if dn_oi and dn_px:
        return "Q4_LONG_LIQ"
    return "Q0_FLAT"


def add_oi_quadrant_features(ctxs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """在 ctx 基础上补 OI 4h 变化与四象限（全部对齐 ctx index，asof 口径，无前视）。"""
    for sym, t in ctxs.items():
        t["oi_4h_chg"] = np.nan
        t["ret_4h"] = t["close"].pct_change(4).replace([np.inf, -np.inf], pd.NA) * 100.0
        t["quadrant"] = "NaN(无OI)"
        p = COINGLASS_RAW1H / "oi_ohlc" / f"{sym}.parquet"
        if not p.exists():
            continue
        oi = pd.read_parquet(p)
        if "time" not in oi.columns or "close" not in oi.columns:
            continue
        oi_ts = pd.to_numeric(oi["time"], errors="coerce").to_numpy(dtype=np.int64)
        oi_c = pd.to_numeric(oi["close"], errors="coerce").to_numpy(dtype=float)
        oi_ser = pd.Series(oi_c, index=pd.Index(oi_ts))
        oi_ser = oi_ser[~oi_ser.index.duplicated(keep="last")].sort_index().reindex(t.index)
        t["oi_4h_chg"] = (oi_ser.pct_change(4) * 100.0).replace([np.inf, -np.inf], pd.NA)
        t["quadrant"] = t.apply(
            lambda r: quadrant_of(r["oi_4h_chg"], r["ret_4h"]), axis=1)
    return ctxs


def attach_quadrant_asof(ctxs: dict[str, pd.DataFrame], events: pd.DataFrame) -> pd.DataFrame:
    """对每个事件 ts 取 asof 象限/oi_4h_chg/ret_4h（无前视）。"""
    ev = events.copy()
    cols = ["quadrant", "oi_4h_chg", "ret_4h"]
    for c in cols:
        ev[f"{c}_at_event"] = pd.Series(index=ev.index, dtype=object)
    for sym, g in ev.groupby("symbol", sort=False):
        if sym not in ctxs:
            continue
        t = ctxs[sym]
        idx = t.index.to_numpy(dtype=np.int64)
        pos = np.searchsorted(idx, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(idx) - 1)
        for c in cols:
            if c == "quadrant":
                vals = t[c].to_numpy(dtype=object)
            else:
                vals = pd.to_numeric(t[c], errors="coerce").to_numpy(dtype=float)
            ev.loc[g.index, f"{c}_at_event"] = vals[pos]
    return ev


# ---------- 事件研究工具（131 同款，禁止改口径） ----------
from harness.lib.event_study import bootstrap_ci, draw_random_events, forward_stats, DEFAULT_HORIZONS  # noqa: E402


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


def table_header(extra_cols: str = "") -> str:
    return f"| 组 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 24h胜率 | 判定 {extra_cols}|"


def table_sep(extra: int = 0) -> str:
    return "|---|---|---|---|---|---|---" + "---|" * extra


def row_line(r: dict) -> str:
    return (f"| {r['label']} | {r['n']} | {fmt(r.get('mean24'))} | {fmt(r.get('ex24'), plus=True)} "
            f"| {fmt_ci(r)} | {fmt(r.get('ex168'), plus=True)} | {fmt_win(r.get('win'))} | {r.get('verdict')} |")


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
    ctxs = add_oi_quadrant_features(ctxs)
    n_oi = sum("oi_4h_chg" in t.columns and t["oi_4h_chg"].notna().any() for t in ctxs.values())
    print(f"价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)} | OI 覆盖 {n_oi} symbols")

    rng = np.random.default_rng(args.seed)

    # ---------- wash_cvd 事件 ----------
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
    wc_events = attach_quadrant_asof(ctxs, wc_events)
    wc_events["episode"] = episode_of(wc_events["timestamp"].to_numpy())
    print(f"wash_cvd 事件（OI 窗口内）: {len(wc_events)}")
    for name, _, _ in EPISODES:
        n_ep = int((wc_events["episode"] == name).sum())
        if n_ep:
            print(f"  {name:16s} n={n_ep}")
    print("象限分布:")
    print(wc_events["quadrant_at_event"].value_counts().to_string())

    # ---------- 基线 ----------
    base_pooled = build_baseline(ctxs, rng, LO_MS, HI_MS, args.n_baseline)
    base_by_ep: dict[str, pd.DataFrame] = {}
    for name, s, e in EPISODES:
        if name not in EPISODES_OI:
            continue
        start_ms = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
        end_ms = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
        base_by_ep[name] = build_baseline(ctxs, rng, start_ms, end_ms, args.n_baseline)
    print(f"pooled 基线 {len(base_pooled)} | episode 基线 { {k: len(v) for k, v in base_by_ep.items()} }")

    def window_base(ep: str) -> pd.DataFrame:
        return base_pooled if ep == "pooled" else base_by_ep.get(ep, pd.DataFrame())

    # ---------- 表1：象限分层 ----------
    t1_groups = ["Q1_NEW_LONGS", "Q2_NEW_SHORTS", "Q3_SHORT_COVER", "Q4_LONG_LIQ",
                 "Q0_FLAT", "NaN(无OI)"]

    def strat_rows(events: pd.DataFrame, grp_col: str, groups: list[str]) -> list[dict]:
        rows: list[dict] = []
        for gname in groups:
            gsub = events[events[grp_col] == gname]
            for ep in ["pooled"] + EPISODES_OI:
                sub = gsub if ep == "pooled" else gsub[gsub["episode"] == ep]
                if len(sub) == 0:
                    rows.append({"label": f"{ep}:{gname}", "n": 0, "mean24": np.nan,
                                 "ex24": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
                                 "ex168": np.nan, "win": np.nan, "verdict": "无事件"})
                    continue
                rows.append(stats_row(sub, window_base(ep), f"{ep}:{gname}",
                                      args.min_events, args.seed))
        return rows

    t1 = strat_rows(wc_events, "quadrant_at_event", t1_groups)

    # 表2：清洗组 vs 堆集组 vs 其余（直接对照）
    wash_grp = wc_events["quadrant_at_event"].isin(["Q3_SHORT_COVER", "Q4_LONG_LIQ"])
    stack_grp = wc_events["quadrant_at_event"].isin(["Q1_NEW_LONGS", "Q2_NEW_SHORTS"])
    rest_grp = ~wash_grp & ~stack_grp
    wash_ev = wc_events[wash_grp]
    stack_ev = wc_events[stack_grp]
    rest_ev = wc_events[rest_grp]
    t2 = [
        stats_row(wash_ev, base_pooled, "清洗组 Q3∪Q4", args.min_events, args.seed),
        stats_row(stack_ev, base_pooled, "堆集组 Q1∪Q2", args.min_events, args.seed),
        stats_row(rest_ev, base_pooled, "其余 Q0∪NaN", args.min_events, args.seed),
    ]

    def direct_contrast(events: pd.DataFrame, a_mask: pd.Series, b_mask: pd.Series,
                        name_a: str, name_b: str) -> dict:
        ra = pd.to_numeric(events.loc[a_mask, "ret_24h"], errors="coerce").dropna().to_numpy()
        rb = pd.to_numeric(events.loc[b_mask, "ret_24h"], errors="coerce").dropna().to_numpy()
        return {"a": name_a, "b": name_b, "n_a": len(ra), "n_b": len(rb),
                **excess(ra, rb, args.seed)}

    d_wash_stack = direct_contrast(wc_events, wash_grp, stack_grp, "清洗组", "堆集组")
    d_wash_rest = direct_contrast(wc_events, wash_grp, rest_grp, "清洗组", "其余")
    d_q3_q4 = direct_contrast(wc_events,
                              wc_events["quadrant_at_event"] == "Q3_SHORT_COVER",
                              wc_events["quadrant_at_event"] == "Q4_LONG_LIQ",
                              "Q3", "Q4")

    # 表3：清洗组 × 空头强平激增（与 131 的 liq_short_z 交叉，借 add_liq_features）
    _spec3 = importlib.util.spec_from_file_location(
        "m131", str(PROJECT_ROOT / "scripts" / "131_liquidation_cross.py"))
    m131 = importlib.util.module_from_spec(_spec3)
    sys.modules["m131"] = m131
    _spec3.loader.exec_module(m131)
    ctxs = m131.add_liq_features(ctxs)
    wc_events = m131.attach_liq_asof(ctxs, wc_events)
    liq_surge = pd.to_numeric(wc_events["liq_short_z_at_event"], errors="coerce") > 1.0
    t3 = [
        stats_row(wc_events[wash_grp & liq_surge], base_pooled, "清洗组×空头强平激增",
                  args.min_events, args.seed),
        stats_row(wc_events[wash_grp & ~liq_surge & wc_events["liq_short_z_at_event"].notna()],
                  base_pooled, "清洗组×无激增", args.min_events, args.seed),
        stats_row(wc_events[stack_grp & liq_surge], base_pooled, "堆集组×空头强平激增",
                  args.min_events, args.seed),
    ]
    d_ws = direct_contrast(wc_events, wash_grp & liq_surge,
                           wash_grp & ~liq_surge & wc_events["liq_short_z_at_event"].notna(),
                           "清洗×激增", "清洗×无激增")

    # ---------- 报告 ----------
    lines: list[str] = []
    lines.append("# wash_cvd × OI×价格四象限交叉研究\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 事件: wash_cvd（115 定义，72h 冷却）；窗口 {pd.Timestamp(LO_MS, unit='ms', tz='UTC'):%Y-%m-%d} ~ {pd.Timestamp(HI_MS, unit='ms', tz='UTC'):%Y-%m-%d}")
    lines.append(f"- 基线: 随机 symbol 横截面（n_baseline={args.n_baseline}，seed={args.seed}）")
    lines.append(f"- 象限阈值（botv2 定义）: OI 4h 变化 ±{OI_TH}%、价格 4h 变化 ±{RET_TH}%")
    lines.append(f"- 事件总数: {len(wc_events)}；象限分布: {wc_events['quadrant_at_event'].value_counts().to_dict()}\n")

    lines.append("## 表1 象限分层（wash_cvd 事件按事件时点象限）\n")
    lines.append(table_header())
    lines.append(table_sep())
    for r in t1:
        lines.append(row_line(r))
    lines.append("")

    lines.append("## 表2 清洗组 vs 堆集组 vs 其余\n")
    lines.append(table_header())
    lines.append(table_sep())
    for r in t2:
        lines.append(row_line(r))
    lines.append("")
    lines.append(f"直接对照（24h 超额差，bootstrap CI）:\n")
    for d in (d_wash_stack, d_wash_rest, d_q3_q4):
        lines.append(f"- {d['a']} vs {d['b']}（n={d['n_a']} vs {d['n_b']}）: "
                     f"{d['mean_diff']:+.2f}% CI[{d['ci_lo']:+.2f}, {d['ci_hi']:+.2f}]")
    lines.append("")

    lines.append("## 表3 清洗组 × 空头强平激增（liq_short_z>1，131 口径）\n")
    lines.append(table_header())
    lines.append(table_sep())
    for r in t3:
        lines.append(row_line(r))
    lines.append("")
    lines.append(f"- 清洗×激增 vs 清洗×无激增: "
                 f"{d_ws['mean_diff']:+.2f}% CI[{d_ws['ci_lo']:+.2f}, {d_ws['ci_hi']:+.2f}]"
                 f"（n={d_ws['n_a']} vs {d_ws['n_b']}）\n")

    lines.append("## 解读要点\n")
    lines.append("- 若清洗组显著强于堆集组：OI×价格结构确认 wash_cvd 的'空头清洗'微观机制，"
                 "可作下一层筛选候选。")
    lines.append("- 若清洗组不强：四象限与 wash_cvd 重叠度高，无增量，该维度收进 GRAVEYARD 认知。")
    lines.append("- 表3 检验清洗×强平激增是否超可加（与 134 四条件体系对照）。\n")

    out = PROJECT_ROOT / "reports" / "oi_quadrant_cross.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[141] wrote {out}")

    # 控制台汇总
    print("\n表2 汇总：")
    for r in t2:
        print(f"  {r['label']:16s} n={r['n']:5d}  ex24={fmt(r.get('ex24'), plus=True)}  "
              f"CI={fmt_ci(r)}  {r['verdict']}")


if __name__ == "__main__":
    main()
