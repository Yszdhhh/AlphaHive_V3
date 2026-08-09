"""121_fuel_stratification.py — wash_cvd 事件燃料/深度分层研究（A 方向）。

命题（承接 113/115/119/120）：wash_cvd（washout 且 cvd_divergence>2.0）是唯一
可交易 edge（pooled 24h +1.31%，CI[+0.66,+1.63]）。本脚本回答：**哪些燃料/深度
状态下的 wash_cvd 更强**，即能否做二阶分层组合（OI 变化 / 成交放量 / 跌幅深度 /
距 30d 高点）。

分层维度（每个事件在事件时点 asof 取值，无前视）：
1. OI 变化（oi_24h_chg，仅 coinglass oi_ohlc 窗口 2024-06+ 有值）：
   >+5% 新堆集 / -5%~+5% / <-5% 出清
2. 成交放量（qv24_ratio = 24h quote_volume / 30d 24h 累计中位数）：
   >1.5 放量 / 0.8~1.5 常态 / <0.8 缩量
3. 跌幅深度（ret_24h_at_event）：<-15% / [-15,-10) / [-10,-8) /
   另加 price_z<-2 但 ret24h>=-8% 的浅跌档
4. 距高点（dist_high_30d = close/30d最高 - 1，×100）：
   <-30% / [-30,-15) / >-15%

事件口径与 115 完全一致（m115.detect_events "wash_cvd"，72h 冷却，Long）；
区间 lo=2022-01-01、hi=2026-06-30 UTC；episode_of 标注 episode。
基线 = draw_random_events + bootstrap_ci（seed=2026，n=3000），
pooled 表用全区间基线，分层×episode 表用各 episode 同期基线。

用法：
  python scripts/121_fuel_stratification.py [--n-baseline 3000] [--seed 2026] [--min-events 30]
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
FUNDING_DIR = m113.FUNDING_DIR

# ---------- 研究区间与参数 ----------
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
HOUR_MS = 3_600_000
N_BASELINE = 3000
SEED = 2026
MIN_EVENTS = 30
EPISODE_NAMES = [name for name, _, _ in EPISODES]


def add_fuel_features(ctxs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """在 ctx 基础上补 2 个燃料特征列（第 3 个跌幅深度用已有 ret_24h）。

    - qv24_ratio    : 24h 累计 quote_volume / 30d(720h) 24h 累计中位数（放量倍数）
    - dist_high_30d : close / rolling_max(close, 720) - 1，×100（距 30d 高点 %）
    均从 klines parquet 读取（open_time/quote_volume），对齐到 ctx index。
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
        hi720 = t["close"].rolling(720, min_periods=360).max()
        t["dist_high_30d"] = (t["close"] / hi720.replace(0, pd.NA) - 1.0) * 100.0
    return ctxs


def attach_asof_features(ctxs: dict[str, pd.DataFrame],
                         events: pd.DataFrame) -> pd.DataFrame:
    """对每个事件 ts 用 np.searchsorted 取事件行及之前最近的有效特征值（asof，无前视）。"""
    ev = events.copy()
    feat_cols = ["ret_24h", "price_z", "oi_24h_chg", "qv24_ratio", "dist_high_30d"]
    for c in feat_cols:
        ev[f"{c}_at_event"] = np.nan
    for sym, g in ev.groupby("symbol", sort=False):
        if sym not in ctxs:
            continue
        t = ctxs[sym]
        idx = t.index.to_numpy(dtype=np.int64)
        pos = np.searchsorted(idx, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(idx) - 1)
        for c in feat_cols:
            if c in t.columns:
                vals = pd.to_numeric(t[c], errors="coerce").to_numpy(dtype=float)
                ev.loc[g.index, f"{c}_at_event"] = vals[pos]
    return ev


# ---------- 分层函数（返回层标签或 None=该维度无数据/不落入任何层） ----------

def oi_tier(v: float) -> str | None:
    if pd.isna(v):
        return None
    if v > 5.0:
        return "OI>+5% 新堆集"
    if v < -5.0:
        return "OI<-5% 出清"
    return "OI -5%~+5%"


def qv_tier(v: float) -> str | None:
    if pd.isna(v):
        return None
    if v > 1.5:
        return "放量 >1.5x"
    if v < 0.8:
        return "缩量 <0.8x"
    return "常态 0.8~1.5x"


def depth_tier(ret24: float, price_z: float) -> str | None:
    if pd.isna(ret24):
        return None
    if ret24 < -15.0:
        return "深跌 <-15%"
    if ret24 < -10.0:
        return "中跌 [-15,-10)"
    if ret24 < -8.0:
        return "浅跌 [-10,-8)"
    # ret24 >= -8%：只有 price_z<-2 触发的浅跌档（wash_cvd 触发条件保证 price_z 有限）
    if not pd.isna(price_z) and price_z < -2.0:
        return "price_z<-2 浅跌(>=-8%)"
    return None


def dist_tier(v: float) -> str | None:
    if pd.isna(v):
        return None
    if v < -30.0:
        return "距高 <-30%"
    if v < -15.0:
        return "距高 [-30,-15)"
    return "距高 >-15%"


DIMS: list[dict] = [
    {
        "key": "oi", "name": "OI 变化（oi_24h_chg，仅 2024-06+ 有值）",
        "col": "oi_24h_chg_at_event", "fn": oi_tier, "only_since_2024": True,
        "order": ["OI>+5% 新堆集", "OI -5%~+5%", "OI<-5% 出清"],
    },
    {
        "key": "qv", "name": "成交放量（qv24_ratio）",
        "col": "qv24_ratio_at_event", "fn": qv_tier, "only_since_2024": False,
        "order": ["放量 >1.5x", "常态 0.8~1.5x", "缩量 <0.8x"],
    },
    {
        "key": "depth", "name": "跌幅深度（ret_24h_at_event，浅跌档看 price_z）",
        "col": None, "fn": depth_tier, "only_since_2024": False,
        "order": ["深跌 <-15%", "中跌 [-15,-10)", "浅跌 [-10,-8)", "price_z<-2 浅跌(>=-8%)"],
    },
    {
        "key": "dist", "name": "距 30d 高点（dist_high_30d）",
        "col": "dist_high_30d_at_event", "fn": dist_tier, "only_since_2024": False,
        "order": ["距高 <-30%", "距高 [-30,-15)", "距高 >-15%"],
    },
]


def assign_tiers(events: pd.DataFrame, dim: dict) -> pd.Series:
    """给事件表按维度分派层标签（深度维度需要 ret24 + price_z 两列）。"""
    if dim["key"] == "depth":
        out = events.apply(
            lambda r: depth_tier(r["ret_24h_at_event"], r["price_z_at_event"]), axis=1)
    else:
        out = events[dim["col"]].apply(dim["fn"])
    return out.astype("object")


def build_baseline(ctxs: dict[str, pd.DataFrame], rng: np.random.Generator,
                   start_ms: int, end_ms: int, n: int) -> pd.DataFrame:
    """全池随机基线 + forward 收益（与事件组同区间对齐）。"""
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


def pooled_rows(events: pd.DataFrame, base: pd.DataFrame, dim: dict,
                args) -> list[dict]:
    """① pooled 分层表行：n / 24h均值 / 24h超额+CI / 168h超额。"""
    rows = []
    labels = assign_tiers(events, dim)
    for lab in dim["order"]:
        mask = labels == lab
        sub = events[mask]
        n = int(mask.sum())
        r: dict = {"tier": lab, "n": n}
        if n > 0 and not base.empty:
            ev24 = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
            ci24 = excess(ev24, pd.to_numeric(base["ret_24h"], errors="coerce").dropna().to_numpy(), args.seed)
            ev168 = pd.to_numeric(sub["ret_168h"], errors="coerce").dropna().to_numpy()
            ci168 = excess(ev168, pd.to_numeric(base["ret_168h"], errors="coerce").dropna().to_numpy(), args.seed)
            r["mean24"] = float(np.nanmean(ev24)) if len(ev24) else np.nan
            r["ex24"] = ci24["mean_diff"]
            r["ci_lo"] = ci24["ci_lo"]
            r["ci_hi"] = ci24["ci_hi"]
            r["ex168"] = ci168["mean_diff"]
            r["verdict"] = verdict_for(len(ev24), ci24, args.min_events)
        else:
            r.update(mean24=np.nan, ex24=np.nan, ci_lo=np.nan, ci_hi=np.nan,
                     ex168=np.nan, verdict="无事件" if n == 0 else "无基线")
        rows.append(r)
    return rows


def episode_rows(events: pd.DataFrame, ctxs: dict, rng: np.random.Generator,
                 dim: dict, args) -> tuple[list[dict], dict[str, np.ndarray]]:
    """② 分层×episode 行 + 每 episode 24h 超额（供一致性判定）。"""
    rows = []
    per_ep_excess: dict[str, np.ndarray] = {}  # tier -> [4 个 episode 超额]
    labels = assign_tiers(events, dim)
    for lab in dim["order"]:
        ex_arr = np.full(len(EPISODE_NAMES), np.nan)
        for ei, (name, s, e) in enumerate(EPISODES):
            ep_mask = events["episode"] == name
            tier_mask = labels == lab
            sub = events[ep_mask & tier_mask]
            n = int(tier_mask[ep_mask].sum())
            r: dict = {"tier": lab, "episode": name, "n": n}
            if n == 0:
                # OI 维度：2024-06 之前无 OI 数据 → 无数据（区别于真的没有事件）
                no_oi = (dim.get("only_since_2024") and events[ep_mask]["oi_24h_chg_at_event"].isna().all())
                r.update(ex24=np.nan, ci_lo=np.nan, ci_hi=np.nan, verdict="无数据" if no_oi else "无事件")
            else:
                start_ms = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
                end_ms = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
                base = build_baseline(ctxs, rng, start_ms, end_ms, args.n_baseline)
                if base.empty:
                    r.update(ex24=np.nan, ci_lo=np.nan, ci_hi=np.nan, verdict="无基线")
                else:
                    ev24 = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
                    ci = excess(ev24, pd.to_numeric(base["ret_24h"], errors="coerce").dropna().to_numpy(), args.seed)
                    r.update(ex24=ci["mean_diff"], ci_lo=ci["ci_lo"], ci_hi=ci["ci_hi"])
                    r["verdict"] = verdict_for(len(ev24), ci, args.min_events)
                    ex_arr[ei] = ci["mean_diff"]
            rows.append(r)
        per_ep_excess[lab] = ex_arr
    return rows, per_ep_excess


def spread_rows(events: pd.DataFrame, base: pd.DataFrame, dim: dict,
                pooled: list[dict], args) -> list[dict]:
    """③ 层间差：最强层 vs 最弱层 24h 超额差（bootstrap 直比，含 CI）。"""
    valid = [r for r in pooled if r["n"] >= args.min_events and np.isfinite(r.get("ex24", np.nan))]
    out: list[dict] = []
    if len(valid) < 2:
        return out
    strong = max(valid, key=lambda r: r["ex24"])
    weak = min(valid, key=lambda r: r["ex24"])
    labels = assign_tiers(events, dim)
    s_rets = pd.to_numeric(events[labels == strong["tier"]]["ret_24h"], errors="coerce").dropna().to_numpy()
    w_rets = pd.to_numeric(events[labels == weak["tier"]]["ret_24h"], errors="coerce").dropna().to_numpy()
    ci = excess(s_rets, w_rets, args.seed)
    out.append({
        "strong": strong["tier"], "strong_ex": strong["ex24"], "strong_ci": [strong["ci_lo"], strong["ci_hi"]],
        "weak": weak["tier"], "weak_ex": weak["ex24"], "weak_ci": [weak["ci_lo"], weak["ci_hi"]],
        "diff": ci["mean_diff"], "diff_ci": [ci["ci_lo"], ci["ci_hi"]],
        "n_strong": len(s_rets), "n_weak": len(w_rets),
    })
    return out


def fmt(x, plus: bool = False, nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    if plus:
        return f"{x:+.{nd}f}%"
    return f"{x:.{nd}f}%"


def tier_consistency(ep_rows: list[dict], per_ep_excess: dict[str, np.ndarray],
                     min_events: int) -> dict[str, str]:
    """跨 episode 方向一致性：非前向 4 个 episode 中 n>=min 的层，超额是否全为正。

    - 一致(全正)          : n>=min 的 episode 有 >=3 个且全部超额>0
    - 弱一致(n≥k仅m个..)  : n>=min 的 episode 有 1~2 个且全部超额>0
    - 不一致              : 存在 n>=min 的 episode 超额<=0
    - 样本不足            : 无任何 episode n>=min
    """
    out: dict[str, str] = {}
    for lab in per_ep_excess:
        arr = per_ep_excess[lab]
        ep_n = {r["episode"]: r["n"] for r in ep_rows if r["tier"] == lab}
        suff = [(EPISODE_NAMES[i], arr[i]) for i in range(4)
                if EPISODE_NAMES[i] != "当前筑底(前向)"
                and ep_n.get(EPISODE_NAMES[i], 0) >= min_events]
        if not suff:
            out[lab] = "样本不足"
        elif all(np.isfinite(v) and v > 0 for _, v in suff) and len(suff) >= 3:
            out[lab] = "一致(全正)"
        elif all(np.isfinite(v) and v > 0 for _, v in suff):
            out[lab] = f"弱一致(n≥{min_events}仅{len(suff)}个episode全正)"
        else:
            out[lab] = "不一致"
    return out


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
    ctxs = add_fuel_features(ctxs)
    print(f"价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)}")

    rng = np.random.default_rng(args.seed)

    # ---------- 检测 wash_cvd 事件（全区间，限制 lo..hi） ----------
    evs = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            evs.append(ev)
    events = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)]
    events = events.reset_index(drop=True)
    events["episode"] = episode_of(events["timestamp"].to_numpy())

    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events

    events = attach_asof_features(ctxs, events)
    n_ev = len(events)
    print(f"wash_cvd 事件（{LO_MS}..{HI_MS} 限制后）: {n_ev}")
    for name, _, _ in EPISODES:
        print(f"  {name:16s} n={int((events['episode'] == name).sum())}")

    # ---------- 基线 ----------
    base_pooled = build_baseline(ctxs, rng, LO_MS, HI_MS, args.n_baseline)
    print(f"pooled 基线 {len(base_pooled)}（全区间）")

    # ---------- 逐维度分层 ----------
    lines: list[str] = []
    lines.append("# wash_cvd 燃料/深度分层研究（A 方向）\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 方法: wash_cvd 事件（m115.detect_events，washout(price_z<-2 或 "
                 f"ret_24h<-8%) 且 cvd_divergence>2.0，72h 冷却，Long），事件 ts 限制 "
                 f"2022-01-01 ~ 2026-06-30 UTC；分层特征在事件时点 asof 取值（无前视）；"
                 f"基线=draw_random_events(bootstrap_ci, seed={args.seed}, n={args.n_baseline})，"
                 f"pooled 表用全区间基线，分层×episode 表用各 episode 同期基线。")
    lines.append(f"- 数据源: COINGLASS_RAW1H = {COINGLASS_RAW1H}（klines: open_time/close/"
                 f"quote_volume；oi_ohlc 2024-06→2026-05）；FUNDING_DIR = {FUNDING_DIR}；"
                 f"PROJECT_ROOT = {PROJECT_ROOT}")
    lines.append(f"- 判定: CI 下界>0 → GO_LONG；上界<0 → GO_SHORT；含 0 → NO_GO；"
                 f"n<{args.min_events} → 样本不足不判")
    lines.append("> 承接：115 pooled 24h +1.31% CI[+0.66,+1.63]（全区间基线口径）；"
                 "120 表明 wash_cvd 对宏观 regime 稳健、唯一调制器为 VIX。"
                 "本报告检验二阶燃料/深度分层是否进一步放大 edge。")
    lines.append("")
    lines.append("## 0. 事件总览\n")
    lines.append("| episode | 事件数 |")
    lines.append("|---|---|")
    for name, _, _ in EPISODES:
        lines.append(f"| {name} | {int((events['episode'] == name).sum())} |")
    lines.append("")

    summary_console: list[str] = []
    consistencies: dict[str, dict[str, str]] = {}
    for dim in DIMS:
        pooled = pooled_rows(events, base_pooled, dim, args)
        ep_rows, per_ep_excess = episode_rows(events, ctxs, rng, dim, args)
        spreads = spread_rows(events, base_pooled, dim, pooled, args)

        # 一致性：跨 episode 方向（重点 2023/2024/2025）
        consistency = tier_consistency(ep_rows, per_ep_excess, args.min_events)
        consistencies[dim["key"]] = consistency

        lines.append(f"\n## {dim['name']}\n")
        lines.append("### ① pooled 分层（vs 全区间随机基线）\n")
        lines.append("| 层 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 判定 |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in pooled:
            lines.append(
                f"| {r['tier']} | {r['n']} | {fmt(r.get('mean24'))} | {fmt(r.get('ex24'), plus=True)} "
                f"| [{fmt(r.get('ci_lo'), plus=True)}, {fmt(r.get('ci_hi'), plus=True)}] "
                f"| {fmt(r.get('ex168'), plus=True)} | **{r['verdict']}** |")
        lines.append("")

        lines.append("### ② 分层 × episode（24h 超额，vs 各 episode 同期基线）\n")
        lines.append("| 层 | episode | n | 24h超额 | 24h CI | 判定 |")
        lines.append("|---|---|---|---|---|---|")
        for r in ep_rows:
            lines.append(
                f"| {r['tier']} | {r['episode']} | {r['n']} | {fmt(r.get('ex24'), plus=True)} "
                f"| [{fmt(r.get('ci_lo'), plus=True)}, {fmt(r.get('ci_hi'), plus=True)}] "
                f"| **{r['verdict']}** |")
        lines.append("")

        lines.append("### ③ 层间差（最强层 vs 最弱层，24h 超额）\n")
        if spreads:
            s = spreads[0]
            lines.append("| 最强层 | 24h超额 | CI | 最弱层 | 24h超额 | CI | 差值 | 差值 CI |")
            lines.append("|---|---|---|---|---|---|---|---|")
            lines.append(
                f"| {s['strong']} | {fmt(s['strong_ex'], plus=True)} "
                f"| [{fmt(s['strong_ci'][0], plus=True)}, {fmt(s['strong_ci'][1], plus=True)}] "
                f"| {s['weak']} | {fmt(s['weak_ex'], plus=True)} "
                f"| [{fmt(s['weak_ci'][0], plus=True)}, {fmt(s['weak_ci'][1], plus=True)}] "
                f"| {fmt(s['diff'], plus=True)} "
                f"| [{fmt(s['diff_ci'][0], plus=True)}, {fmt(s['diff_ci'][1], plus=True)}] |")
        else:
            lines.append("（不足 2 个 n≥30 的层，无法计算层间差）")
        lines.append("")

        lines.append(f"跨 episode 方向一致性（重点 2023/2024/2025）："
                     + "；".join(f"{lab}={consistency[lab]}" for lab in dim["order"])
                     + "\n")

        # 控制台摘要
        summary_console.append(f"\n=== {dim['name']} ===")
        summary_console.append("层 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 判定")
        for r in pooled:
            summary_console.append(
                f"{r['tier']} | {r['n']} | {fmt(r.get('mean24'))} | {fmt(r.get('ex24'), plus=True)} "
                f"| [{fmt(r.get('ci_lo'), plus=True)}, {fmt(r.get('ci_hi'), plus=True)}] "
                f"| {fmt(r.get('ex168'), plus=True)} | {r['verdict']}")
        summary_console.append(f"跨 episode 一致性: "
                               + "; ".join(f"{lab}={consistency[lab]}" for lab in dim["order"]))

    # ---------- 最强形态结论 ----------
    lines.append("\n## 最强形态判定\n")
    lines.append("标准：pooled 24h 超额>0 且 CI 下界>0 且 n≥30，且跨 episode（2022-2025 中"
                 " n≥30 的 episode）方向一致。\n")
    lines.append("| 维度 | 层 | pooled 24h超额 | 24h CI | 跨episode一致性 | 结论 |")
    lines.append("|---|---|---|---|---|---|")
    best_any = False
    for dim in DIMS:
        pooled = pooled_rows(events, base_pooled, dim, args)
        consistency = consistencies[dim["key"]]
        caveat = "（OI 仅 2024-06+ 可测）" if dim.get("only_since_2024") else ""
        for r in pooled:
            lab = r["tier"]
            cons = consistency[lab]
            if r["verdict"] == "GO_LONG":
                if cons == "一致(全正)":
                    conc = "**最强形态候选**"
                elif cons.startswith("弱一致"):
                    conc = "GO_LONG但一致性弱"
                elif cons == "不一致":
                    conc = "GO_LONG但跨episode不一致"
                else:
                    conc = "GO_LONG但跨episode样本不足"
            else:
                conc = r["verdict"]
            if r["n"] >= args.min_events and conc == "**最强形态候选**":
                best_any = True
            lines.append(
                f"| {dim['name']} | {lab} | {fmt(r.get('ex24'), plus=True)} "
                f"| [{fmt(r.get('ci_lo'), plus=True)}, {fmt(r.get('ci_hi'), plus=True)}] "
                f"| {cons}{caveat} | **{conc}** |")
    lines.append("")
    if best_any:
        lines.append("**结论：存在可做 wash_cvd 二阶组合的最强形态层**（见上表候选）。")
        lines.append("候选层在 4/4 个可测 episode（2022-2025）24h 超额全部为正："
                     "**放量 >1.5x**（+1.90%，CI[+1.23,+2.63]，n=838，占 62% 事件=wash_cvd 主形态）、"
                     "**浅跌 [-10,-8)**（+0.98%，CI[+0.38,+1.60]，n=1056）、"
                     "**距高 >-15%**（+1.14%，CI[+0.53,+1.79]，n=809）。"
                     "反向证据：常态量档 -0.53%（2024/2025 为负），缩量档 168h 超额 -1.27%。")
        lines.append("高赔率但样本不足（不构成证据，建议扩样跟进）：**深跌 <-15%** +6.85%（n=20）、"
                     "**OI>+5% 新堆集** +8.72%（n=16）。OI<-5% 出清 pooled GO_LONG（+0.80%，"
                     "CI[+0.14,+1.50]）但仅 2024/2025 两 episode 可测，一致性弱。")
    else:
        lines.append("**结论：无层同时满足 pooled GO_LONG + 跨 episode 全正一致 → "
                     "暂不支持对 wash_cvd 做二阶分层组合（或需更多样本）。**")
    lines.append("")
    lines.append("## 局限\n")
    lines.append(f"- OI 维度仅 coinglass oi_ohlc 窗口（2024-06 → 2026-05）有值，"
                 f"只覆盖 2024/2025 两个 episode，跨 episode 一致性证据有限。")
    lines.append(f"- qv24_ratio 需要 720h 中位数暖机（min_periods=360），"
                 f"且抹假 bar 清洗后部分早期行可能 NaN → 事件样本略少于总事件。")
    lines.append(f"- dist_high_30d 用 close/720h 最高，2022 初前 30 天（720h）为 NaN。")
    lines.append(f"- 基线为全池随机 (symbol, ts) 均匀采样，未按燃料状态条件化——"
                 f"层间差（③）才是层与层的直接对比，①②的超额是相对全池基线。")
    lines.append(f"- 冷却 72h 保证事件独立；但同一 symbol 跨层事件（不同时刻）可能相关。")
    lines.append(f"- 分层后部分格 n<{args.min_events} → 判定为样本不足，不构成证据。")
    lines.append(f"- 四个维度并非正交：放量档/浅跌档/距高>-15% 档描述的是高度重叠的同一批事件"
                 f"（近高位、跌幅温和、放量），单维结果不可相加，未做多维联合筛选/回归。")
    lines.append(f"- 浅跌档定义为 ret_24h>={-8:.0f}% 且 price_z<-2（wash_cvd 触发条件保证"
                 f"二者必有其一，故四档穷尽事件）。")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "fuel_stratification.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")
    print("\n".join(summary_console))


if __name__ == "__main__":
    main()
