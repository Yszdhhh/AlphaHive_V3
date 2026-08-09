"""120_macro_factor_modulation.py — 宏观环境对 A 线因子（wash_cvd）的调制检验。

问题：119 证明宏观【单变量】不预测次日大盘收益。但 wash_cvd 是【币种级】信号，
其 edge 是否随宏观环境变化（risk_on/off、美元强弱、利率方向、VIX 高低、黄金趋势）？
→ 回答"宏观数据跟我们的因子组合是否有关联"，找 wash_cvd 的"环境开关"。

方法（无前视）：
- 事件 = 115 的 wash_cvd（washout 且 cvd_divergence>2.0，72h 冷却，Long）
- 每个事件 asof 取【事件日 - 1】的宏观状态（macro 日线收盘状态，避免用事件日尚未
  发布的当日宏观值 → 严格无前视；宏观状态日度粘滞，t-1 vs t 差异可忽略）
- 按 regime 分列 24h/168h 超额（bootstrap 95% CI），对照全样本随机基线
- 另附：每 episode 宏观状态签名（牛熊前置环境的描述性对照，诚实：4 年 2 周期，
  统计性不足，只能看方向性）

输出 reports/macro_factor_modulation.md
用法：
  python scripts/120_macro_factor_modulation.py [--seed 2026]
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

from harness.lib.event_study import DEFAULT_HORIZONS, bootstrap_ci, draw_random_events, forward_stats

MACRO_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
REPORTS_DIR = PROJECT_ROOT / "reports"

# 复用 113/115（同一检测/加载口径）
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

STUDY_START = "2022-01-01"
STUDY_END = "2026-06-30"   # 前向 episode 不含（无宏观可判定的未来）
HOUR_MS = 3_600_000


def load_macro_series(key: str) -> pd.Series:
    df = pd.read_parquet(MACRO_ROOT / f"{key}.parquet")
    idx = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
    return pd.Series(pd.to_numeric(df["close"], errors="coerce").to_numpy(), index=idx)


def build_state_frame() -> pd.DataFrame:
    """每日宏观状态布尔帧（index=date）。全部只用当日收盘信息。"""
    sp = load_macro_series("SP500")
    dollar = load_macro_series("DOLLAR")
    vix = load_macro_series("VIX")
    gold = load_macro_series("GOLD")
    tr = pd.read_parquet(MACRO_ROOT / "TREASURY.parquet")
    tr_idx = pd.DatetimeIndex(tr.index).tz_localize(None).normalize()
    us10 = pd.Series(pd.to_numeric(tr["us_10y"], errors="coerce").to_numpy(), index=tr_idx)
    spread = pd.Series(pd.to_numeric(tr["us_10y_2y_spread"], errors="coerce").to_numpy(), index=tr_idx)
    ff = load_macro_series("FEDFUNDS")

    idx = sp.index.union(dollar.index).union(vix.index).union(us10.index)
    st = pd.DataFrame(index=pd.DatetimeIndex(idx).sort_values())
    st["risk_on"] = (sp > sp.rolling(50, min_periods=30).mean()).reindex(st.index, method="ffill").astype(bool)
    st["dollar_weak"] = (dollar < dollar.rolling(50, min_periods=30).mean()).reindex(st.index, method="ffill").astype(bool)
    st["d10y_down"] = (us10.diff() < 0).reindex(st.index, method="ffill").astype(bool)
    st["vix_high"] = (vix > vix.rolling(365, min_periods=120).quantile(0.75)).reindex(st.index, method="ffill").astype(bool)
    st["gold_up"] = (gold.diff(5) > 0).reindex(st.index, method="ffill").astype(bool)
    st["spread_steep"] = (spread > 0).reindex(st.index, method="ffill").astype(bool)
    st["fed_lo"] = (ff < ff.rolling(365, min_periods=120).median()).reindex(st.index, method="ffill").astype(bool)
    # 互补列（显式，避免在 regimes 字典里写 ~ 逻辑）
    st["risk_off"] = ~st["risk_on"]
    st["dollar_strong"] = ~st["dollar_weak"]
    st["d10y_up"] = ~st["d10y_down"]
    st["vix_low"] = ~st["vix_high"]
    st["gold_down"] = ~st["gold_up"]
    st["spread_invert"] = ~st["spread_steep"]
    st["fed_high"] = ~st["fed_lo"]
    st["liq_expand"] = st["dollar_weak"] & st["d10y_down"]
    st["liq_tight"] = st["dollar_strong"] & st["d10y_up"]
    return st


def event_states(events: pd.DataFrame, st: pd.DataFrame) -> pd.DataFrame:
    """每个事件 asof 取事件日 - 1 的宏观状态（严格无前视）。"""
    dates = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_convert(None).normalize()
    prev = (dates - pd.Timedelta(days=1)).normalize()
    st_prev = st.reindex(prev)  # exact date match; 缺宏观日（周末/假日）→ NaN
    # 缺日回退：取 <= prev 的最近宏观日（不超前）
    for c in st_prev.columns:
        st_prev[c] = st[c].reindex(prev, method="ffill").to_numpy()
    return st_prev


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-events", type=int, default=30)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    fundings = load_funding_series(symbols)
    print(f"[120] 价格上下文 {len(ctxs)} | funding {len(fundings)}")

    # wash_cvd 事件（同 115 口径）
    ev_parts = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(columns=["symbol", "timestamp"])
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    events["episode"] = episode_of(events["timestamp"].to_numpy())
    # 只保留研究区间（不含前向 episode）
    lo = int(pd.Timestamp(STUDY_START, tz="UTC").timestamp() * 1000)
    hi = int(pd.Timestamp(STUDY_END, tz="UTC").timestamp() * 1000)
    events = events[(events["timestamp"] >= lo) & (events["timestamp"] <= hi)]
    print(f"[120] wash_cvd 事件 {len(events)}（2022-01→2026-06）")

    st = build_state_frame()
    ev_st = event_states(events, st)
    for c in ev_st.columns:
        events[c] = ev_st[c].to_numpy()

    # 全样本随机基线（同期）
    rng = np.random.default_rng(args.seed)
    base = draw_random_events(ctxs, 5000, rng, max_forward_hours=168, start_ms=lo, end_ms=hi)
    base_parts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            base_parts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_stats = pd.concat(base_parts, ignore_index=True) if base_parts else pd.DataFrame()
    base_v = pd.to_numeric(base_stats["ret_24h"], errors="coerce").dropna().to_numpy()
    base_v168 = pd.to_numeric(base_stats["ret_168h"], errors="coerce").dropna().to_numpy()
    pooled_v = pd.to_numeric(events["ret_24h"], errors="coerce").dropna().to_numpy()

    lines: list[str] = []
    lines.append("# 宏观环境对 wash_cvd 的调制检验\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 事件 = wash_cvd（washout 且 cvd_div>2.0，72h 冷却，Long），{len(events)} 个，区间 {STUDY_START}→{STUDY_END}")
    lines.append("- 宏观状态 asof 事件日-1（无前视）；状态日度粘滞，t-1 vs t 差异可忽略")
    lines.append(f"- 基线 = 同期随机 symbol×时点（bootstrap 95% CI, seed={args.seed}）")
    lines.append(f"- 参考: 全事件 pooled 24h={np.nanmean(pooled_v):+.2f}%\n")

    lines.append("## 1. wash_cvd 事件按宏观 regime 分列（24h 超额）\n")
    lines.append("| regime | 定义(事件日-1) | n | 24h均% | 超额vs基线 | 95% CI | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    regimes = {
        "risk_on": "SP500 > 50dMA",
        "risk_off": "SP500 < 50dMA",
        "dollar_weak": "美元指数 < 50dMA",
        "dollar_strong": "美元指数 > 50dMA",
        "d10y_down": "10Y日变 < 0",
        "d10y_up": "10Y日变 > 0",
        "vix_low": "VIX < 1y 75分位",
        "vix_high": "VIX > 1y 75分位",
        "gold_down": "黄金5d < 0",
        "gold_up": "黄金5d > 0",
        "spread_invert": "10Y-2Y < 0",
        "spread_steep": "10Y-2Y > 0",
        "liq_expand": "美元弱 且 10Y下行",
        "liq_tight": "美元强 且 10Y上行",
    }
    regime_rows = []
    for key, desc in regimes.items():
        mask_ev = events[key].fillna(False)
        sub = events[mask_ev]
        ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        ev_v168 = pd.to_numeric(sub["ret_168h"], errors="coerce").dropna().to_numpy()
        if len(ev_v) < args.min_events:
            lines.append(f"| {key} | {desc} | {len(sub)} | - | - | - | - | 样本不足 |")
            regime_rows.append({"regime": key, "n": len(sub), "excess": np.nan, "ci_lo": np.nan, "ci_hi": np.nan})
            continue
        ci = bootstrap_ci(ev_v, base_v, seed=args.seed)
        ci168 = bootstrap_ci(ev_v168, base_v168, seed=args.seed)
        if ci["ci_lo"] > 0:
            verdict = "GO_LONG"
        elif ci["ci_hi"] < 0:
            verdict = "GO_SHORT"
        else:
            verdict = "NO_GO"
        lines.append(f"| {key} | {desc} | {len(sub)} | {np.nanmean(ev_v):+.2f} | {ci['mean_diff']:+.2f} | "
                     f"[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {ci168['mean_diff']:+.2f} | **{verdict}** |")
        regime_rows.append({"regime": key, "n": len(sub), "excess": ci["mean_diff"], "ci_lo": ci["ci_lo"], "ci_hi": ci["ci_hi"]})

    # regime 内相对差异（同 regime 的 wash_cvd 两半对照）
    lines.append("\n## 2. 同 regime 内两分半对照（edge 是否环境敏感）\n")
    lines.append("| 维度 | 半A | 半A超额 | 半B | 半B超额 | 差(A−B) |")
    lines.append("|---|---|---|---|---|---|")
    pairs = [
        ("risk_on", "risk_off"), ("dollar_weak", "dollar_strong"),
        ("d10y_down", "d10y_up"), ("vix_low", "vix_high"),
        ("gold_down", "gold_up"), ("spread_invert", "spread_steep"),
        ("liq_expand", "liq_tight"),
    ]
    for a, b in pairs:
        va = pd.to_numeric(events[events[a].fillna(False)]["ret_24h"], errors="coerce").dropna().to_numpy()
        vb = pd.to_numeric(events[events[b].fillna(False)]["ret_24h"], errors="coerce").dropna().to_numpy()
        if len(va) < 10 or len(vb) < 10:
            continue
        ex_a = np.nanmean(va) - np.nanmean(base_v)
        ex_b = np.nanmean(vb) - np.nanmean(base_v)
        lines.append(f"| {a}/{b} | {a} n={len(va)} | {ex_a:+.2f} | {b} n={len(vb)} | {ex_b:+.2f} | {ex_a - ex_b:+.2f} |")

    # 3) 去混淆：GO episode 内部按 VIX/risk 分列（排除"2022 episode"整体效应）
    lines.append("\n## 3. 去混淆：GO episode 内部分 VIX / risk（排除 2022 整体效应）\n")
    lines.append("| episode | 组 | n | 24h均% | 超额vs同期基线 | 95% CI |")
    lines.append("|---|---|---|---|---|---|")
    for ep_name, s, e in [("2023平台蓄力", "2023-02-01", "2024-05-31"),
                          ("2024崩→恢复", "2024-06-01", "2025-01-31"),
                          ("2025顶→熊", "2025-02-01", "2026-06-30")]:
        sub = events[events["episode"] == ep_name]
        if sub.empty:
            continue
        elo = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
        ehi = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
        base_ep = draw_random_events(ctxs, 3000, rng, max_forward_hours=168, start_ms=elo, end_ms=ehi)
        base_ep_stats = []
        if not base_ep.empty:
            for bs, bg in base_ep.groupby("symbol", sort=False):
                if bs in ctxs:
                    base_ep_stats.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
        bep = pd.concat(base_ep_stats, ignore_index=True) if base_ep_stats else pd.DataFrame()
        bep_v = pd.to_numeric(bep["ret_24h"], errors="coerce").dropna().to_numpy() if not bep.empty else np.array([])
        for grp, mask in [("vix_low", sub["vix_low"].fillna(False)), ("vix_high", sub["vix_high"].fillna(False)),
                          ("risk_on", sub["risk_on"].fillna(False)), ("risk_off", sub["risk_off"].fillna(False))]:
            g = sub[mask]
            gv = pd.to_numeric(g["ret_24h"], errors="coerce").dropna().to_numpy()
            if len(gv) < 15 or len(bep_v) == 0:
                continue
            ci = bootstrap_ci(gv, bep_v, seed=args.seed)
            lines.append(f"| {ep_name} | {grp} | {len(g)} | {np.nanmean(gv):+.2f} | {ci['mean_diff']:+.2f} | "
                         f"[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] |")

    # 4) 牛熊前置环境：每 episode 宏观状态签名（描述性）
    lines.append("\n## 4. 每 episode 宏观状态签名（牛熊前置环境，描述性）\n")
    lines.append("| episode | 区间 | risk_on占比 | 美元弱占比 | 10Y下行占比 | VIX高位占比 | 黄金涨占比 | 利差陡占比 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    st_full = build_state_frame()
    for name, s, e in EPISODES:
        if "前向" in name:
            continue
        sub = st_full[(st_full.index >= s) & (st_full.index < e)]
        if sub.empty:
            continue
        lines.append(f"| {name} | {s}→{e} | {sub['risk_on'].mean() * 100:.0f}% | {sub['dollar_weak'].mean() * 100:.0f}% | "
                     f"{sub['d10y_down'].mean() * 100:.0f}% | {sub['vix_high'].mean() * 100:.0f}% | "
                     f"{sub['gold_up'].mean() * 100:.0f}% | {sub['spread_steep'].mean() * 100:.0f}% |")

    lines.append("\n## 5. 解读要点")
    lines.append("- 若某 regime 下 wash_cvd 超额明显收缩/反号且 n 足够 → 找到环境开关，可做成门控。")
    lines.append("- 若各 regime 超额都稳定正 → 宏观环境对 wash_cvd 关联弱，edge 是币种级内生的。")
    lines.append("- 去混淆表：若 VIX/risk 调制在 2023/2024/2025 内部也成立 → 调制真实；若只在 2022 明显 → 是 episode 假象。")
    lines.append("- episode 签名表是 4 年 2 周期的描述性对照，不能当统计证据；只看方向性。")

    out = REPORTS_DIR / "macro_factor_modulation.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")
    for l in lines:
        if l.startswith("|") and ("GO_" in l or "差(" in l):
            print(l)


if __name__ == "__main__":
    main()
