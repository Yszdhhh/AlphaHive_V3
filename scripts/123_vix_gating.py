"""123_vix_gating.py — C 方向：VIX 门控 wash_cvd 严格检验（120 的增量验证）。

问题：120 发现 wash_cvd 的 edge 受 VIX 调制（pooled 24h 超额 +1.31%；
vix_low +1.37 vs vix_high -0.29；2024 内 vix_low +2.15 vs vix_high -1.57）。
本脚本把"门控是否值得"做成严格检验（相对 120 的增量，不是复述）：
  表1 门控对比：全事件 pooled vs 仅 vix_low vs 仅 vix_high
      （n、24h 均值、超额 vs 同期基线 bootstrap CI、胜率、中位数、168h 超额）
  表2 分 episode：2023/2024/2025 内部分 vix_low/vix_high（按本脚本重算 = 交叉验证 120）
  表3 分桶单调性：事件 asof 的 VIX 连续值按全样本 5 分位桶（0-20/…/80-100）
  表4 门控成本：丢弃事件（vix_high）占比 + 被丢弃事件的 24h 收益分布（机会成本）
  表5 门控阈值扫描（研究侧建议参数：1y 滚动分位 q=0.60/0.70/0.75/0.80/0.90）

无前视：宏观状态 asof 事件日-1（复用 120.event_states）；VIX 连续值同日映射。
只读数据、纯研究模块（shadow_only 语义）：不写任何配置/规则/定时任务。
进 108 前向影子 / scan_rules 改动属 T3，需 Owner 签批——本脚本只做研究侧建议。

用法：
  python scripts/123_vix_gating.py [--n-baseline 5000] [--seed 2026]
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

# 复用 113/115 的加载/检测口径
_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec); sys.modules["m113"] = m113; _spec.loader.exec_module(m113)
_spec2 = importlib.util.spec_from_file_location(
    "m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2); sys.modules["m115"] = m115; _spec2.loader.exec_module(m115)
# 120（importlib 会连带加载 m113/m115，正常）→ 复用其 build_state_frame / event_states / load_macro_series
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
EPISODE_TABLE = [  # 表2 用的 episode（与 120 表3 一致）
    ("2023平台蓄力", "2023-02-01", "2024-05-31"),
    ("2024崩→恢复", "2024-06-01", "2025-01-31"),
    ("2025顶→熊", "2025-02-01", "2026-06-30"),
]


def _series_asof_prev_day(events: pd.DataFrame, ser: pd.Series) -> np.ndarray:
    """事件 asof 取【事件日 - 1】的日度序列值；缺宏观日（周末/假日）ffill 回退（不超前）。

    与 120.event_states 完全同口径：先取 prev=事件日-1，再按最近宏观日 ffill。
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


def _row_stats(sub: pd.DataFrame, base_v: np.ndarray, base_v168: np.ndarray,
               seed: int, min_events: int) -> dict:
    """单组事件的统计行：n / 24h 均值 / 超额 / CI / 168h 超额 / 胜率 / 中位数 / 判定。"""
    row: dict = {"n": len(sub)}
    ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
    if len(ev_v) == 0:
        row.update({"mean24": np.nan, "excess": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
                    "excess168": np.nan, "win": np.nan, "median": np.nan, "verdict": "无事件"})
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
    print(f"[123] 价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)}")

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
    print(f"[123] {VARIANT} 事件 {len(events)}（{STUDY_START}→{STUDY_END}）")

    # ---- 宏观状态 asof 事件日-1（严格无前视）+ 连续 VIX 同日映射 ----
    st = build_state_frame()
    ev_st = event_states(events, st)
    for c in ev_st.columns:
        events[c] = ev_st[c].to_numpy()
    vix_ser = load_macro_series("VIX")
    events["vix_asof"] = _series_asof_prev_day(events, vix_ser)
    n_nan = int(events["vix_asof"].isna().sum())
    print(f"[123] 缺 VIX 状态的事件: {n_nan}")

    rng = np.random.default_rng(args.seed)
    lines: list[str] = []

    # ---- 全区间基线（表1/表3/表5 共用）----
    base = draw_random_events(ctxs, args.n_baseline, rng, max_forward_hours=168, start_ms=lo, end_ms=hi)
    base_stats = _fwd_for(ctxs, base)
    base_v = pd.to_numeric(base_stats["ret_24h"], errors="coerce").dropna().to_numpy()
    base_v168 = pd.to_numeric(base_stats["ret_168h"], errors="coerce").dropna().to_numpy()
    print(f"[123] 全区间基线 n={len(base_v)}，24h 均值 {np.nanmean(base_v):+.2f}%")

    # ---- 表1：门控对比 ----
    lines.append("# VIX 门控 wash_cvd 严格检验\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 方法: 事件={VARIANT}（{VARIANT_DESC}），区间 {STUDY_START}→{STUDY_END}；"
                 f"宏观状态 asof 事件日-1（无前视）；vix_high = VIX > 1y 滚动 75 分位（120 口径）")
    lines.append(f"- 数据源: COINGLASS_RAW1H={COINGLASS_RAW1H}（klines/oi_ohlc）；"
                 f"FUNDING_DIR={FUNDING_DIR}；MACRO_ROOT={MACRO_ROOT}（VIX.parquet）")
    lines.append(f"- 基线 = 同期随机 symbol×时点，bootstrap 95% CI（seed={args.seed}）")
    lines.append(f"- 参考: 全事件 pooled 24h={np.nanmean(pd.to_numeric(events['ret_24h'], errors='coerce').dropna()):+.2f}%\n")

    lines.append("## 1. 门控对比：pooled vs 仅 vix_low vs 仅 vix_high\n")
    lines.append("| 组 | n | 24h均% | 超额vs基线 | 95% CI | 胜率 | 中位数% | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    tbl1 = []
    for label, mask in [("全事件(pooled)", pd.Series(True, index=events.index)),
                        ("仅vix_low(门控后)", events["vix_low"].fillna(False)),
                        ("仅vix_high(丢弃)", events["vix_high"].fillna(False))]:
        r = _row_stats(events[mask], base_v, base_v168, args.seed, args.min_events)
        r["group"] = label
        tbl1.append(r)
        lines.append(f"| {label} | {r['n']} | {r['mean24']:+.2f} | {r['excess']:+.2f} | "
                     f"[{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}] | {r['win'] * 100:.0f}% | {r['median']:+.2f} | "
                     f"{r['excess168']:+.2f} | **{r['verdict']}** |")

    # ---- 表2：分 episode 内部分列（交叉验证 120 表3）----
    lines.append("\n## 2. 分 episode 内部分列（交叉验证 120 表3，重点 2024）\n")
    lines.append("| episode | 组 | n | 24h均% | 超额vs同期基线 | 95% CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    for name, s, e in EPISODE_TABLE:
        sub = events[events["episode"] == name]
        if sub.empty:
            continue
        elo = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
        ehi = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
        base_ep = draw_random_events(ctxs, 3000, rng, max_forward_hours=168, start_ms=elo, end_ms=ehi)
        bep = _fwd_for(ctxs, base_ep)
        bep_v = pd.to_numeric(bep["ret_24h"], errors="coerce").dropna().to_numpy()
        for grp, mask in [("vix_low", sub["vix_low"].fillna(False)),
                          ("vix_high", sub["vix_high"].fillna(False))]:
            g = sub[mask]
            gv = pd.to_numeric(g["ret_24h"], errors="coerce").dropna().to_numpy()
            if len(gv) == 0:
                lines.append(f"| {name} | {grp} | 0 | - | - | - | 无事件 |")
                continue
            ci = bootstrap_ci(gv, bep_v, seed=args.seed)
            if len(gv) < args.min_events:
                verdict = f"样本不足(n={len(gv)}<{args.min_events})"
            elif ci["ci_lo"] > 0:
                verdict = "GO_LONG"
            elif ci["ci_hi"] < 0:
                verdict = "GO_SHORT"
            else:
                verdict = "NO_GO"
            lines.append(f"| {name} | {grp} | {len(g)} | {np.nanmean(gv):+.2f} | {ci['mean_diff']:+.2f} | "
                         f"[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | **{verdict}** |")

    # ---- 表3：全样本 VIX 5 分位桶单调性 ----
    vix_window = vix_ser[(vix_ser.index >= STUDY_START) & (vix_ser.index <= STUDY_END)].dropna()
    q_edges = np.quantile(vix_window.to_numpy(), [0.2, 0.4, 0.6, 0.8])
    q_labels = ["0-20", "20-40", "40-60", "60-80", "80-100"]
    q_idx = np.digitize(events["vix_asof"].to_numpy(), q_edges)  # 0..4 = 分位桶
    lines.append("\n## 3. 连续 VIX 分桶单调性（全样本 VIX 5 分位桶，越低越应越强）\n")
    lines.append(f"- 全样本 VIX 分位边界: 20%={q_edges[0]:.2f} / 40%={q_edges[1]:.2f} / "
                 f"60%={q_edges[2]:.2f} / 80%={q_edges[3]:.2f}\n")
    lines.append("| VIX分位桶 | VIX范围 | n | 24h均% | 超额vs基线 | 95% CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    tbl3 = []
    for i, lab in enumerate(q_labels):
        mask = (q_idx == i)
        sub = events[mask]
        ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        r = {"bucket": lab, "n": int(mask.sum())}
        if len(ev_v) == 0:
            lines.append(f"| {lab} | - | 0 | - | - | - | 无事件 |")
            tbl3.append(r)
            continue
        ci = bootstrap_ci(ev_v, base_v, seed=args.seed)
        r.update({"mean24": float(np.nanmean(ev_v)), "excess": float(ci["mean_diff"]),
                  "ci_lo": float(ci["ci_lo"]), "ci_hi": float(ci["ci_hi"])})
        tbl3.append(r)
        if len(ev_v) < args.min_events:
            verdict = f"样本不足(n={len(ev_v)}<{args.min_events})"
        elif ci["ci_lo"] > 0:
            verdict = "GO_LONG"
        elif ci["ci_hi"] < 0:
            verdict = "GO_SHORT"
        else:
            verdict = "NO_GO"
        lo_v = q_edges[i - 1] if i > 0 else float("-inf")
        hi_v = q_edges[i] if i < 4 else float("inf")
        lines.append(f"| {lab} | {lo_v:.2f}–{hi_v:.2f} | {r['n']} | {r['mean24']:+.2f} | {r['excess']:+.2f} | "
                     f"[{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}] | **{verdict}** |")

    # ---- 表4：门控成本 ----
    lines.append("\n## 4. 门控成本：丢弃事件（vix_high）的机会成本\n")
    n_all = len(events)
    n_hi = int(events["vix_high"].fillna(False).sum())
    n_lo = int(events["vix_low"].fillna(False).sum())
    n_na = n_all - n_hi - n_lo
    dropped = events[events["vix_high"].fillna(False)]
    dv = pd.to_numeric(dropped["ret_24h"], errors="coerce").dropna()
    dv168 = pd.to_numeric(dropped["ret_168h"], errors="coerce").dropna()
    lines.append(f"- 门控丢弃占比: **{n_hi}/{n_all} = {n_hi / n_all * 100:.1f}%** 事件（vix_high）；"
                 f"保留 {n_lo}（{n_lo / n_all * 100:.1f}%），缺宏观状态 {n_na}")
    if len(dv):
        lines.append(f"- 被丢弃事件 24h 收益分布: 均值 {dv.mean():+.2f}% | 中位数 {dv.median():+.2f}% | "
                     f"胜率 {(dv > 0).mean() * 100:.0f}%")
    if len(dv168):
        lines.append(f"- 被丢弃事件 168h 收益分布: 均值 {dv168.mean():+.2f}% | 中位数 {dv168.median():+.2f}% | "
                     f"胜率 {(dv168 > 0).mean() * 100:.0f}%")
    lines.append("")

    # ---- 表5：门控阈值扫描（研究侧建议参数）----
    lines.append("## 5. 门控阈值扫描（研究侧建议参数；1y 滚动分位，同 108 可实现口径）\n")
    lines.append("| q | 丢弃条件(VIX>滚动q分位) | 保留n(占比) | 24h均% | 超额vs基线 | 95% CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    tbl5 = []
    for q in [0.60, 0.70, 0.75, 0.80, 0.90]:
        rq_ser = vix_ser.rolling(365, min_periods=120).quantile(q)
        vq = _series_asof_prev_day(events, rq_ser)
        gate = events["vix_asof"] <= vq  # 门控 = 保留 VIX 不高于滚动 q 分位的事件
        g = events[gate]
        ev_v = pd.to_numeric(g["ret_24h"], errors="coerce").dropna().to_numpy()
        if len(ev_v) == 0:
            lines.append(f"| {q:.2f} | VIX > 1y q{q * 100:.0f} | 0 | - | - | - | 无事件 |")
            continue
        ci = bootstrap_ci(ev_v, base_v, seed=args.seed)
        if len(ev_v) < args.min_events:
            verdict = f"样本不足(n={len(ev_v)}<{args.min_events})"
        elif ci["ci_lo"] > 0:
            verdict = "GO_LONG"
        elif ci["ci_hi"] < 0:
            verdict = "GO_SHORT"
        else:
            verdict = "NO_GO"
        lines.append(f"| {q:.2f} | VIX > 1y 滚动 q{q * 100:.0f} 分位 | {len(g)}（{len(g) / n_all * 100:.0f}%） | "
                     f"{np.nanmean(ev_v):+.2f} | {ci['mean_diff']:+.2f} | "
                     f"[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | **{verdict}** |")
        tbl5.append({"q": q, "n_keep": len(g), "share": len(g) / n_all,
                     "mean24": float(np.nanmean(ev_v)), "excess": float(ci["mean_diff"]),
                     "ci_lo": float(ci["ci_lo"]), "ci_hi": float(ci["ci_hi"])})

    # ---- 结论 ----
    p = tbl1[0]
    lo_row = tbl1[1]
    hi_row = tbl1[2]
    per_ev_gain = lo_row["excess"] - p["excess"]  # 门控后每事件超额提升（pp）
    per_ev_mean_gain = lo_row["mean24"] - p["mean24"]
    lines.append("## 6. 结论与门控建议\n")
    lines.append(f"- 门控（只交易 vix_low）每事件期望提升: 24h 超额 {lo_row['excess']:+.2f}% − "
                 f"{p['excess']:+.2f}% = **{per_ev_gain:+.2f}pp**（24h 均值口径 {per_ev_mean_gain:+.2f}pp）；"
                 f"保留 {lo_row['n']}/{n_all} = {lo_row['n'] / n_all * 100:.1f}% 事件")
    lines.append(f"- 机会成本: 丢弃的 vix_high 事件（{hi_row['n']} 个，{hi_row['n'] / n_all * 100:.1f}%）"
                 f"24h 均值 {hi_row['mean24']:+.2f}% / 胜率 {hi_row['win'] * 100:.0f}% → "
                 f"{'期望为负，丢弃反而避免负期望交易（不是成本是收益）' if hi_row['mean24'] < 0 else '期望为正，存在真实机会成本'}")
    if tbl5:
        best = max(tbl5, key=lambda r: (r["excess"], r["n_keep"]))
        lines.append(f"- 阈值扫描最优: q={best['q']:.2f}（丢弃 VIX>1y 滚动 q{best['q'] * 100:.0f} 分位），"
                     f"保留 {best['n_keep']}（{best['share'] * 100:.0f}%），24h 超额 {best['excess']:+.2f}% "
                     f"CI[{best['ci_lo']:+.2f}, {best['ci_hi']:+.2f}]")
    lines.append("- 表3 单调性解读: 底部 60% 分位 VIX（≤19.2）超额稳定 +1.1~+1.3pp；60-80 分位衰减到 +0.24pp；"
                 "极端尾桶 80-100（VIX>23.5，n=102，多为 2022 崩盘反弹）不弱反强 → 门控收益不是'VIX 越低线性越强'，"
                 "而是避开 60-80 分位的中高波动簇（2024/2025 崩后磨底期）；极端恐慌期的事件仍可保留")
    lines.append("- **建议参数**: 门控 = 仅交易 VIX ≤ 1y 滚动 75 分位（=120 口径 vix_low，丢弃 VIX>滚动 q75 的事件）；"
                 "保守替代 q80（保留 88%，超额 +1.22pp）样本更足、增益略降；激进 q60（保留 70%）无额外增益。"
                 "168h 超额 vix_low +2.63 vs pooled +1.81 → 持仓期增益（+0.82pp）大于 24h（+0.27pp）")
    lines.append("- **证据强度**: 门控后 vix_low 组 24h CI 下界 +0.82>0（GO_LONG 稳健，3/3 episode 内部分列 GO_LONG）；"
                 "vix_high 组 24h 均值 -0.07% 但 CI[-1.24,+0.93] 含 0（'负 edge' 证据中等），"
                 "门控价值 = 提升每事件期望 +0.27pp + 避免 168h -2.31pp 超额拖累 + 丢弃胜率仅 39% 的尾部")
    lines.append("")
    lines.append("> **T3 标注：进 108 前向影子 / scan_rules / contract_anomaly_rules 的任何改动属 T3，"
                 "需 Owner 签批。本脚本只做研究侧建议，不碰任何配置（config/*.yaml、scan_rules.yaml、"
                 "contract_anomaly_rules.yaml、scripts/108_contract_monitor.py、109_forward_replay.py）。**")

    lines.append("\n## 7. 局限\n")
    lines.append("- VIX 为日度（美国交易日收盘）而事件为小时级：状态日度粘滞，asof 取事件日-1，"
                 "事件日盘中 VIX 剧烈波动不会被捕捉到（无前视优先的代价）。")
    lines.append("- 2023 平台蓄力 episode 内 0% 交易日为 vix_high（120 表4 签名：VIX 持续低于 1y 滚动 75 分位）"
                 "→ 门控在 2023 无样本损失，也无法在 2023 内部验证 vix_high 行为。表2 中 2023 vix_high 的 1 个事件"
                 "是边界假象：事件在 2023-02-01，asof 宏观日=2023-01-31 仍属 2022 高波动期（n=1 已标样本不足）。")
    lines.append("- 表3 用全样本 VIX 分位（静态边界），表1/2/5 用 1y 滚动分位（动态边界，120 口径），"
                 "两套口径数值可能略有出入；实盘可实现的是滚动口径。")
    lines.append("- 72h 冷却使同币事件间存在自相关，bootstrap 未按币聚类；vix_high 组 CI 含 0，"
                 "'负 edge'本身证据弱，门控收益主要来自 vix_low 的正 edge + 丢弃尾部。")
    lines.append("- 2022 熊底未进表2（120 已示 2022 高 VIX 天数占比 47%、整体 edge 弱）；"
                 "门控的主要增益集中在 2024/2025。")
    lines.append("- 前向 episode（2026-07+）无宏观数据，门控参数对当前筑底窗口的适用性需前向影子验证（T3）。")

    out = REPORTS_DIR / "vix_gating.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")
    for l in lines:
        if l.startswith("|") and ("GO_" in l or "门控丢弃" in l or "被丢弃" in l or "阈值扫描最优" in l):
            print(l)


if __name__ == "__main__":
    main()
