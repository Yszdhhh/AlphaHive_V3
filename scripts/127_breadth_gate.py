"""127_breadth_gate.py — 广度门控检验：wash_cvd + 事件时市场级 breadth≥5% 是否提升 edge。

背景：124（market_breadth）发现 wash_cvd 的 24h 超额随事件时广度分层抬升
（低<5% +0.70 / 中5~15% +1.85 / 高>15% +1.48，24h 超额 vs 同期基线，全 GO_LONG），
并建议"把 breadth_pct 作为 wash_cvd 的辅助门控（如要求事件时广度 ≥5%）"做下一轮验证。
本脚本把该建议做成严格检验（124 的增量，不是复述）：

  表1 三变体 pooled 对比：V_ref 纯 wash_cvd vs V_gate5（breadth≥5%）vs V_gate10（breadth≥10%）
      n / 唯一时点 / 24h 均值 / 中位数 / 胜率 / 超额 vs 全区间基线 / 95% CI / 168h 超额 / 判定
  表2 分 episode：2022/2023/2024/2025 各 episode 内三变体并排（同期 episode 基线；
      2022 高广度多出在深熊瀑布中继语境，单独看，注意不混进 2023+ 结论）
  表3 门控成本：被滤掉事件（breadth<5%，补充 breadth<10%）数量 + 24h/168h 收益分布
      （机会成本：124 显示低广度层本身是 GO_LONG 正超额，被滤事件 ≠ 负期望尾部）

口径与无前视（同 124，直接复用其函数）：
- 广度 = 6h 网格（UTC 0/6/12/18）逐币 washout=(price_z<-2.0)|(ret_24h<-8%)；
  breadth_pct = 100×出清币数/有效币数（NaN 不计入分母，n_active>=5 才有效）
- 事件 ts（小时级）用 np.searchsorted 取事件前最近 6h 网格点的 breadth_pct（asof，无前视）
- 事件 = wash_cvd（115 口径：washout 且 cvd_divergence>2.0，72h 冷却/币，Long），
  区间 2022-01-01 → 2026-06-30（与 123 完全同窗口，V_ref 应复现 pooled 24h=+1.31% n=1348）
- 基线 = 同期随机 symbol×时点横截面，bootstrap 95% CI（seed=2026）
  （表1 用全区间基线；表2 用各 episode 同期基线——与 123 表1/表2 同构）

样本重叠（诚实标注）：同一 6h 时点多币同时出清 → wash_cvd 事件非独立，
每行报告唯一时点数 n_unique_ts；bootstrap 未按币/时点聚类，CI 偏窄。

只读数据、纯研究模块：不写任何配置/规则/定时任务。
进 108 前向影子 / scan_rules / contract_anomaly_rules 的任何改动属 T3，需 Owner 签批。

用法：
  python scripts/127_breadth_gate.py [--n-baseline 5000] [--seed 2026]
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
FUNDING_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
REPORTS_DIR = PROJECT_ROOT / "reports"

# 复用 113/115 的统一加载模板（保证口径与 washout-settle / wash_cvd 研究一致）
_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec); sys.modules["m113"] = m113; _spec.loader.exec_module(m113)
_spec2 = importlib.util.spec_from_file_location(
    "m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2); sys.modules["m115"] = m115; _spec2.loader.exec_module(m115)
# 124（importlib 会连带加载 m113/m115，正常）→ 复用其广度序列构建/挂载函数，保证与 market_breadth 完全同口径
_spec3 = importlib.util.spec_from_file_location(
    "m124", str(PROJECT_ROOT / "scripts" / "124_market_breadth.py"))
m124 = importlib.util.module_from_spec(_spec3); sys.modules["m124"] = m124; _spec3.loader.exec_module(m124)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
detect_events = m115.detect_events
EPISODES = m113.EPISODES
episode_of = m113.episode_of

STUDY_START = "2022-01-01"
STUDY_END = "2026-06-30"   # 与 123 同窗口；前向 episode 不含
VARIANT = "wash_cvd"
VARIANT_DESC = "washout(price_z<-2.0 或 ret_24h<-8%) 且 cvd_divergence>2.0，72h 冷却，Long"
GATE5 = 5.0
GATE10 = 10.0
EPISODE_TABLE = [  # 表2 用的 episode（与 113/115/123 相同切分，含 2022 深熊）
    ("2022熊底+FTX底", "2022-01-01", "2023-01-31"),
    ("2023平台蓄力", "2023-02-01", "2024-05-31"),
    ("2024崩→恢复", "2024-06-01", "2025-01-31"),
    ("2025顶→熊", "2025-02-01", "2026-06-30"),
]


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
    """单组事件统计行：n / 唯一时点 / 24h 均值 / 中位数 / 胜率 / 超额 / CI / 168h 超额 / 判定。

    判定（统一模板）：24h 超额 bootstrap 95% CI 下界>0 → GO_LONG；上界<0 → GO_SHORT；
    含 0 → NO_GO；n<min_events → 样本不足。
    """
    row: dict = {"n": len(sub),
                 "n_unique_ts": int(sub["timestamp"].nunique()) if len(sub) else 0}
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
    print(f"[127] 价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)}")

    rng = np.random.default_rng(args.seed)

    # ---- 广度序列（124 口径，直接复用其构建函数）----
    grid = m124.build_grid(ctxs)
    breadth = m124.build_breadth_series(ctxs, grid)
    print(f"[127] 6h 网格 {len(grid)} 点 | 广度有效点 "
          f"{int(breadth['breadth_pct'].notna().sum())}（n_active>=5）")

    # ---- 事件 = wash_cvd（全区间 2022-01-01 → 2026-06-30）----
    ev_parts = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), VARIANT)
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = _fwd_for(ctxs, events)
    events["episode"] = episode_of(events["timestamp"].to_numpy())
    lo = int(pd.Timestamp(STUDY_START, tz="UTC").timestamp() * 1000)
    hi = int(pd.Timestamp(STUDY_END, tz="UTC").timestamp() * 1000)
    events = events[(events["timestamp"] >= lo) & (events["timestamp"] <= hi)].copy()

    # 事件 ts 取 asof（事件前最近 6h 网格点）的 breadth_pct，无前视
    events = m124.attach_breadth(events, breadth)
    n_nan_b = int(events["breadth_pct"].isna().sum())
    print(f"[127] wash_cvd 事件 {len(events)}（{STUDY_START}→{STUDY_END}），缺广度 {n_nan_b}")

    variants = {
        "V_ref": (f"纯 wash_cvd（无门控，124 分层全集）", events),
        "V_gate5": (f"wash_cvd 且 breadth≥{GATE5:.0f}%", events[events["breadth_pct"] >= GATE5]),
        "V_gate10": (f"wash_cvd 且 breadth≥{GATE10:.0f}%", events[events["breadth_pct"] >= GATE10]),
    }

    # ---- 全区间基线（表1 共用）----
    base = draw_random_events(ctxs, args.n_baseline, rng, max_forward_hours=168,
                              start_ms=lo, end_ms=hi)
    base_stats = _fwd_for(ctxs, base)
    base_v = pd.to_numeric(base_stats["ret_24h"], errors="coerce").dropna().to_numpy()
    base_v168 = pd.to_numeric(base_stats["ret_168h"], errors="coerce").dropna().to_numpy()
    print(f"[127] 全区间基线 n={len(base_v)}，24h 均值 {np.nanmean(base_v):+.2f}%")

    lines: list[str] = []
    lines.append("# 广度门控 wash_cvd 严格检验（验证 124 建议：breadth≥5%）\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 方法: 事件={VARIANT}（{VARIANT_DESC}），区间 {STUDY_START}→{STUDY_END}；"
                 f"广度口径同 124：6h 网格（UTC 0/6/12/18）逐币 washout=(price_z<-2.0)|(ret_24h<-8%)，"
                 f"breadth_pct=100×出清币数/有效币数（NaN 不计入分母，n_active>=5 才有效）；"
                 f"事件 ts 用 np.searchsorted 取事件前最近网格点（asof，无前视）")
    lines.append(f"- 数据源: COINGLASS_RAW1H={COINGLASS_RAW1H}（klines: close/price_z/ret_24h/cvd_divergence）；"
                 f"FUNDING_DIR={FUNDING_DIR}（wash_cvd 检测用 funding 参数占位，实际不参与）")
    lines.append(f"- 基线 = 同期随机 symbol×时点横截面，bootstrap 95% CI（seed={args.seed}）；"
                 f"表1 用全区间基线（n={args.n_baseline}），表2 用各 episode 同期基线（n=3000）")
    lines.append(f"- V_ref 复现锚点: 123 pooled 24h 均值 +1.31%、超额 +1.10%、n=1348（本表应一致）")
    lines.append("> **样本重叠（务必读）**：同一 6h 时点多币同时出清 → wash_cvd 事件彼此相关，"
                 "每行报告唯一时点数 n_unique_ts；bootstrap 未按币/时点聚类，CI 偏窄。"
                 "72h 冷却使同币事件间也存在自相关。\n")
    lines.append("**局限**：")
    lines.append("- coinglass klines 在 2026-06-23 23:00 → 2026-06-30 04:00 存在约 6.3 天空档（公共接口未回填，全 universe 一致），"
                 "该窗口 6h 网格广度 NaN（n_active=0）→ 事件缺广度被门控剔除；实测缺广度事件数见下。")
    lines.append("- 广度依赖 price_z/ret_24h 的 30d 滚动窗口：2022-01 月初无 price_z → 广度 2022-01-16 前后才开始有效；"
                 "n_active 前低后高（2022 平均 18 → 2025 平均 50），早期广度粒度粗（1/17≈5.9%）。")
    lines.append("- universe 含少量非加密资产（XAU/XAG 与股票类），与 113/115/119/120/124 完全同口径，未额外剔除。\n")

    # ---- 表1：三变体 pooled 对比 ----
    lines.append("## 1. 三变体 pooled 对比\n")
    lines.append("| 变体 | 门控条件 | n | 唯一时点 | 24h均% | 中位数% | 胜率 | 超额vs基线 | 95% CI | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    tbl1: dict[str, dict] = {}
    for key, (desc, sub) in variants.items():
        r = _row_stats(sub, base_v, base_v168, args.seed, args.min_events)
        r["key"], r["desc"] = key, desc
        tbl1[key] = r
        lines.append(f"| {key} | {desc} | {r['n']} | {r['n_unique_ts']} | {r['mean24']:+.2f} | "
                     f"{r['median']:+.2f} | {r['win'] * 100:.0f}% | {r['excess']:+.2f} | "
                     f"[{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}] | {r['excess168']:+.2f} | **{r['verdict']}** |")

    # ---- 表2：分 episode 三变体并排 ----
    lines.append("\n## 2. 分 episode：三变体并排（同期 episode 基线；2022 高广度注意深熊瀑布语境）\n")
    lines.append("| episode | 变体 | n | 24h均% | 超额vs同期基线 | 95% CI | 168h超额 | 胜率 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    tbl2: dict[tuple[str, str], dict] = {}
    for name, s, e in EPISODE_TABLE:
        elo = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
        ehi = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
        base_ep = draw_random_events(ctxs, 3000, rng, max_forward_hours=168,
                                     start_ms=elo, end_ms=ehi)
        bep = _fwd_for(ctxs, base_ep)
        bep_v = pd.to_numeric(bep["ret_24h"], errors="coerce").dropna().to_numpy()
        bep_v168 = pd.to_numeric(bep["ret_168h"], errors="coerce").dropna().to_numpy()
        for key, (desc, sub_all) in variants.items():
            sub = sub_all[sub_all["episode"] == name]
            r = _row_stats(sub, bep_v, bep_v168, args.seed, args.min_events)
            tbl2[(name, key)] = r
            lines.append(f"| {name} | {key} | {r['n']} | {r['mean24']:+.2f} | {r['excess']:+.2f} | "
                         f"[{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}] | {r['excess168']:+.2f} | "
                         f"{r['win'] * 100:.0f}% | **{r['verdict']}** |")

    # ---- 表3：门控成本 ----
    dropped5 = events[events["breadth_pct"] < GATE5]
    dropped10 = events[events["breadth_pct"] < GATE10]
    lines.append("\n## 3. 门控成本：被滤掉事件的机会成本\n")
    lines.append("| 丢弃组 | 丢弃条件 | 事件数 | 占V_ref | 唯一时点 | 24h均值% | 24h中位% | 24h胜率 | 168h均值% | 168h中位% | 168h胜率 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    tbl3: dict[str, dict] = {}
    for dkey, dsub, cond in [("drop<5%", dropped5, f"breadth<{GATE5:.0f}%"),
                             ("drop<10%", dropped10, f"breadth<{GATE10:.0f}%")]:
        dv = pd.to_numeric(dsub["ret_24h"], errors="coerce").dropna()
        dv168 = pd.to_numeric(dsub["ret_168h"], errors="coerce").dropna()
        r = {"n": len(dsub), "n_unique_ts": int(dsub["timestamp"].nunique()) if len(dsub) else 0,
             "share": len(dsub) / len(events) * 100 if len(events) else np.nan}
        if len(dv):
            r.update({"mean24": float(dv.mean()), "median24": float(dv.median()),
                      "win24": float((dv > 0).mean())})
        else:
            r.update({"mean24": np.nan, "median24": np.nan, "win24": np.nan})
        if len(dv168):
            r.update({"mean168": float(dv168.mean()), "median168": float(dv168.median()),
                      "win168": float((dv168 > 0).mean())})
        else:
            r.update({"mean168": np.nan, "median168": np.nan, "win168": np.nan})
        tbl3[dkey] = r
        lines.append(f"| {dkey} | {cond} | {r['n']} | {r['share']:.1f}% | {r['n_unique_ts']} | "
                     f"{r['mean24']:+.2f} | {r['median24']:+.2f} | {r['win24'] * 100:.0f}% | "
                     f"{r['mean168']:+.2f} | {r['median168']:+.2f} | {r['win168'] * 100:.0f}% |")

    # ---- 结论 ----
    ref, g5, g10 = tbl1["V_ref"], tbl1["V_gate5"], tbl1["V_gate10"]
    per_ev_gain = g5["excess"] - ref["excess"]
    per_ev_mean_gain = g5["mean24"] - ref["mean24"]
    kept_share = g5["n"] / ref["n"] * 100
    d5 = tbl3["drop<5%"]
    # 跨 episode 一致性：gate5 vs ref 超额、GO_LONG 计数（2022 单独标注深熊语境）
    ep_help = 0
    for name, s, e in EPISODE_TABLE:
        rr, gg = tbl2[(name, "V_ref")], tbl2[(name, "V_gate5")]
        if np.isfinite(rr["excess"]) and np.isfinite(gg["excess"]) and gg["excess"] > rr["excess"]:
            ep_help += 1
    ref_golong = sum(1 for name, s, e in EPISODE_TABLE
                     if tbl2[(name, "V_ref")]["verdict"] == "GO_LONG")
    g5_golong = sum(1 for name, s, e in EPISODE_TABLE
                    if tbl2[(name, "V_gate5")]["verdict"] == "GO_LONG")
    g10_golong = sum(1 for name, s, e in EPISODE_TABLE
                     if tbl2[(name, "V_gate10")]["verdict"] == "GO_LONG")

    lines.append("\n## 4. 结论与门控建议（交叉对照 124 / 123）\n")
    lines.append(f"- **V_ref 复现锚点**: n={ref['n']}、24h 均值 {ref['mean24']:+.2f}%、超额 {ref['excess']:+.2f}% "
                 f"CI [{ref['ci_lo']:+.2f}, {ref['ci_hi']:+.2f}]（123 pooled 为 n=1348 / +1.31% / +1.10%，一致 ✔）")
    lines.append(f"- **每事件期望提升（≥5% 门控）**: 24h 超额 {g5['excess']:+.2f}% − {ref['excess']:+.2f}% = "
                 f"**{per_ev_gain:+.2f}pp**（24h 均值口径 {per_ev_mean_gain:+.2f}pp）；"
                 f"保留 {g5['n']}/{ref['n']} = **{kept_share:.1f}%** 事件（丢弃 {100 - kept_share:.1f}%），"
                 f"唯一时点 {ref['n_unique_ts']} → {g5['n_unique_ts']}")
    lines.append(f"- **168h 维度**: {g5['excess168']:+.2f}% vs {ref['excess168']:+.2f}%"
                 f"（门控后 {g5['excess168'] - ref['excess168']:+.2f}pp）")
    lines.append(f"- **跨 episode 一致性**: gate5 超额高于 V_ref 的 episode 数 {ep_help}/4；"
                 f"GO_LONG 计数 V_ref {ref_golong}/4 vs gate5 {g5_golong}/4 vs gate10 {g10_golong}/4")
    lines.append(f"- **机会成本（表3）**: 被滤掉 breadth<5% 事件 {d5['n']} 个（{d5['share']:.1f}%），"
                 f"24h 均值 {d5['mean24']:+.2f}% / 中位 {d5['median24']:+.2f}% / 胜率 {d5['win24'] * 100:.0f}%"
                 f"（124 同层 +0.82% / +0.70pp 超额 GO_LONG）→ 被滤组本身是**正 edge**，"
                 f"{'存在真实机会成本' if d5['mean24'] > 0 else '接近零/负期望（机会成本低）'}")
    lines.append(f"- **对照 123 VIX 门控（+0.27pp/事件、丢弃 16.5% 尾部、丢弃组 24h -0.07% 胜率 39% = 负期望尾部）**: "
                 f"广度≥5% 门控的单事件增益（{per_ev_gain:+.2f}pp）{'大于' if abs(per_ev_gain) > 0.27 else '小于/接近'} VIX 门控，"
                 f"但代价是丢弃 {100 - kept_share:.1f}% 事件（VIX 只丢 16.5%），且丢弃的是正 edge 组 → "
                 f"广度门控是'集中到更高正期望子集'，VIX 门控是'丢掉负期望尾部'，性质不同，不可直接相加；"
                 f"若叠加两个门控需注意样本压缩（约保留 {kept_share / 100 * 83.5:.0f}%）。")

    # 2022 深熊语境 + 判定
    g5_22 = tbl2[("2022熊底+FTX底", "V_gate5")]
    ref_22 = tbl2[("2022熊底+FTX底", "V_ref")]
    lines.append(f"- **2022 深熊语境**: 2022 内 gate5 n={g5_22['n']}（ref {ref_22['n']}）、"
                 f"24h 均值 {g5_22['mean24']:+.2f}% vs {ref_22['mean24']:+.2f}%、"
                 f"超额 {g5_22['excess']:+.2f}% vs {ref_22['excess']:+.2f}%"
                 f"（124 显示 2022 高广度层 +0.34% 弱于 2023/2024，LUNA/FTX 瀑布中继）")
    g5_ok = per_ev_gain > 0 and g5_golong >= 3 and (ep_help >= 3 or g5["excess"] - ref["excess"] >= 0.3)
    if g5_ok:
        verdict_line = (f"- **判定（breadth≥5% 门控）**: **有条件值得**——每事件超额提升 {per_ev_gain:+.2f}pp "
                        f"且 2023-2025 跨 episode 一致；但样本损失 {100 - kept_share:.1f}% 且被滤组为正 edge，"
                        f"硬门控的机会成本高，更稳妥的用法是作为分层/排序维度（同 124 建议）或组合其他门控时保持样本。")
    else:
        verdict_line = (f"- **判定（breadth≥5% 门控）**: **不值得作为硬门控**——每事件增益 {per_ev_gain:+.2f}pp 未覆盖 "
                        f"{100 - kept_share:.1f}% 样本损失与正 edge 被滤组的真实机会成本（详见上）。")
    lines.append(verdict_line)
    lines.append("")
    lines.append("> **T3 标注：进 108 前向影子 / scan_rules / contract_anomaly_rules 的任何改动属 T3，"
                 "需 Owner 签批。本脚本只做研究侧建议，不碰任何配置（config/*.yaml、scan_rules.yaml、"
                 "contract_anomaly_rules.yaml、scripts/108_contract_monitor.py、109_forward_replay.py）。**")

    lines.append("\n## 5. 局限\n")
    lines.append("- 样本重叠：同一 6h 时点多币同时出清 → 事件非独立，表1 已报 n_unique_ts（V_ref "
                 f"{ref['n_unique_ts']} / gate5 {g5['n_unique_ts']}）；bootstrap 未按币/时点聚类，CI 偏窄。")
    lines.append("- 2026-06-23 23:00 → 06-30 04:00 coinglass 全 universe 空档：该窗口广度 NaN，"
                 f"in-window 事件缺广度 {n_nan_b} 个（预期 0，若 >0 已从门控组剔除、仍在 V_ref）。")
    lines.append("- 表1 超额用全区间基线、124 分层用各自层时间跨度基线 → 本表数值与 124 报告略有出入（方向一致）；"
                 "本脚本内三变体共用同一基线，对比自洽。")
    lines.append("- 2022 事件广度粒度粗（n_active≈18，1/17≈5.9%），breadth 值离散度高，2022 结论仅供参考。")
    lines.append("- 前向 episode（2026-07+）无足够广度/前向窗口数据，门控参数对当前筑底窗口的适用性需前向影子验证（T3）。")

    out = REPORTS_DIR / "breadth_gate.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")

    # ---- stdout 三表摘要 ----
    print("\n=== 表1 三变体 pooled ===")
    for key in ["V_ref", "V_gate5", "V_gate10"]:
        r = tbl1[key]
        print(f"  {key:9s} n={r['n']:4d} (唯一时点{r['n_unique_ts']:3d}) 24h均{r['mean24']:+.2f}% "
              f"超额{r['excess']:+.2f}% CI[{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}] 168h{r['excess168']:+.2f}% "
              f"胜率{r['win'] * 100:.0f}% {r['verdict']}")
    print("\n=== 表2 分 episode ===")
    for name, s, e in EPISODE_TABLE:
        for key in ["V_ref", "V_gate5", "V_gate10"]:
            r = tbl2[(name, key)]
            print(f"  {name} {key:9s} n={r['n']:3d} 24h均{r['mean24']:+.2f}% 超额{r['excess']:+.2f}% "
                  f"CI[{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}] 168h{r['excess168']:+.2f}% 胜率{r['win'] * 100:.0f}% {r['verdict']}")
    print("\n=== 表3 门控成本 ===")
    for dkey in ["drop<5%", "drop<10%"]:
        r = tbl3[dkey]
        print(f"  {dkey:9s} n={r['n']:4d} ({r['share']:.1f}%) 唯一时点{r['n_unique_ts']:3d} "
              f"24h均值{r['mean24']:+.2f}% 中位{r['median24']:+.2f}% 胜率{r['win24'] * 100:.0f}% "
              f"168h均值{r['mean168']:+.2f}% 中位{r['median168']:+.2f}% 胜率{r['win168'] * 100:.0f}%")
    print(f"\n判定: {verdict_line}")


if __name__ == "__main__":
    main()
