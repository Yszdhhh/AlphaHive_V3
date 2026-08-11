"""109_forward_replay.py — 前向影子候选收益复核（Phase 4 闭环）。

对 108_contract_monitor 产出的候选，用 binance_free_db 价格回填
forward 4h/24h/72h/168h 收益，与【同一时点】随机 symbol 横截面基线对比
（bootstrap CI），给 cvd_bear 真实前向判决。

关键设计（避免前视与不可比）：
- 事件收益复用 event_study.forward_stats（close@ts+h / close@ts - 1，时间对齐 asof）。
- 基线是横截面而非全历史：前向候选都集中在最新 bar，基线若全区间采样会
  大量落在历史早期，与候选不可比。因此基线 = 与候选相同时点、随机其他 symbols。

诚实边界：
- 候选样本不足时 CI 必然宽 → verdict 标注 PENDING（待积累）。
- 持有期若候选太近没有足够前向数据 → 该 horizon 标 NOT_ENOUGH_DATA。

用法：
  python scripts/109_forward_replay.py [--n-baseline 300] [--seed 0]

输出：
  reports/forward_replay_returns.csv   每候选 × 每 horizon 一行（积累用）
  reports/forward_replay_report.md     汇总 + bootstrap CI + verdict
"""
from __future__ import annotations

import argparse
import json
import sys
import yaml
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import bootstrap_ci, forward_stats

BINANCE_ROOT = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h")
CANDIDATES_PATH = PROJECT_ROOT / "reports" / "contract_monitor_candidates.csv"
OUT_CSV = PROJECT_ROOT / "reports" / "forward_replay_returns.csv"
OUT_MD = PROJECT_ROOT / "reports" / "forward_replay_report.md"
HORIZONS = [4, 24, 72, 168]
BASE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def load_universe_symbols() -> list[str]:
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = json.load(f)["symbols"]
    return [item["symbol"] for item in universe if item["symbol"] not in BASE_SYMBOLS]


def load_price_tables(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """symbol -> DataFrame(index=ts ms, close)。只取有 close 的表。"""
    tables: dict[str, pd.DataFrame] = {}
    for s in symbols:
        p = BINANCE_ROOT / "klines" / f"{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if "open_time" not in df.columns or "close" not in df.columns:
            continue
        close = pd.to_numeric(df["close"], errors="coerce")
        ts = pd.to_numeric(df["open_time"], errors="coerce")
        t = pd.DataFrame({"close": close.to_numpy(dtype=float)}, index=pd.Index(ts.to_numpy(dtype=np.int64), name="timestamp"))
        t = t[~t.index.duplicated(keep="last")].sort_index()
        t = t.replace([np.inf, -np.inf], np.nan).dropna(subset=["close"])
        tables[s] = t
    return tables


def _event_frame(symbols: list[str], ts_values: np.ndarray) -> pd.DataFrame:
    """构造 events DataFrame（每行一个 (symbol, ts)）。"""
    return pd.DataFrame({"symbol": symbols, "timestamp": ts_values})


def forward_for_events(tables: dict[str, pd.DataFrame], events: pd.DataFrame) -> pd.DataFrame:
    """逐 symbol 调 forward_stats，收集各 horizon 收益。无数据 → NaN。"""
    parts = []
    for sym, g in events.groupby("symbol", sort=False):
        table = tables.get(sym)
        if table is None:
            continue
        ft = forward_stats(table, g, horizons=HORIZONS)
        ft["symbol"] = sym
        parts.append(ft)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["timestamp", "symbol"] + [f"ret_{h}h" for h in HORIZONS]
    )


def summarize(rets: np.ndarray, label: str, h: int) -> dict:
    r = rets[np.isfinite(rets)]
    return {
        "horizon_h": h,
        "group": label,
        "n": int(len(r)),
        "mean_pct": float(np.mean(r)) if len(r) else np.nan,
        "median_pct": float(np.median(r)) if len(r) else np.nan,
        "winrate": float((r > 0).mean()) if len(r) else np.nan,
    }


def decay_monitor(cand_fwd: pd.DataFrame, base_ret: np.ndarray,
                  block: int = 30, seed: int = 0, cusum_k: float = 0.5, cusum_h: float = 4.5) -> list[str]:
    """事件计数窗口衰减监测（EDGE_LEDGER 配套，gemini 行业实践调研落地）。

    - 判决单位 = 事件计数窗口（非日历窗口），按时间序每 block 个事件一块
    - 判定对象 = 24h 净超额收益（相对基线横截面）
    - CUSUM 简化版：z_i = ex_i / σ_ex，S^- = max(0, S^- + (-z_i - k))，S^- > h 触发预警
    - 块级 CI 上限 < 0 → 衰退预警；CI 跨零 = 证据不足（不触发衰退）
    """
    out: list[str] = ["\n## Decay 监测（事件计数窗口）\n"]

    def _fmt(x, plus: bool = False, nd: int = 2) -> str:
        if x is None or (isinstance(x, float) and not np.isfinite(x)):
            return "-"
        return f"{x:+.{nd}f}%" if plus else f"{x:.{nd}f}%"

    if cand_fwd is None or len(cand_fwd) == 0:
        out.append("- 无候选。")
        return out
    df = cand_fwd.copy()
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df = df.sort_values("timestamp").reset_index(drop=True)
    base = pd.to_numeric(pd.Series(base_ret), errors="coerce").dropna().to_numpy()
    ex_all = pd.to_numeric(df["ret_24h"], errors="coerce").to_numpy(dtype=float) - (
        np.nanmean(base) if len(base) else np.nan)
    df["ex24"] = ex_all
    n_all = int(np.isfinite(ex_all).sum())
    sigma = np.nanstd(ex_all) if n_all > 1 else np.nan

    out.append(f"- 判决单位: 每 {block} 事件一块（非重叠，按时间序）；n 总={n_all}")
    out.append(f"- CUSUM(向下, k={cusum_k}, h={cusum_h})：z_i = 事件超额/σ，S⁻ 超阈值触发预警\n")
    out.append("| 块 | 时间范围 (北京时间) | n | 24h均值% | 超额% | CI | 判定 |")
    out.append("|---|---|---|---|---|---|---|")

    s_minus = 0.0
    rows: list[dict] = []
    for i in range(0, len(df), block):
        sub = df.iloc[i:i + block]
        t0 = pd.Timestamp(int(sub["timestamp"].iloc[0]), unit="ms", tz="Asia/Shanghai").strftime("%m-%d %H:%M")
        t1 = pd.Timestamp(int(sub["timestamp"].iloc[-1]), unit="ms", tz="Asia/Shanghai").strftime("%m-%d %H:%M")
        ev = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        if len(ev) == 0 or len(base) == 0:
            rows.append({"label": f"{i // block + 1}", "t": f"{t0}~{t1}", "n": len(ev),
                         "mean": np.nan, "ex": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "verdict": "无基线"})
            continue
        ci = bootstrap_ci(ev, base, n_boot=1000, alpha=0.05, seed=seed)
        if len(ev) < block:
            verdict = "样本不足"
        elif ci["ci_lo"] > 0:
            verdict = "GO_LONG"
        elif ci["ci_hi"] < 0:
            verdict = "GO_SHORT"
        else:
            verdict = "NO_GO"
        rows.append({"label": f"{i // block + 1}", "t": f"{t0}~{t1}", "n": len(ev),
                     "mean": float(np.nanmean(ev)), "ex": ci["mean_diff"],
                     "ci_lo": ci["ci_lo"], "ci_hi": ci["ci_hi"], "verdict": verdict})
        # CUSUM 更新
        if np.isfinite(sigma) and sigma > 0:
            for x in ev:
                z = (x - np.nanmean(ev)) / sigma
                s_minus = max(0.0, s_minus + (-z - cusum_k))
    for r in rows:
        out.append(f"| {r['label']} | {r['t']} | {r['n']} | {_fmt(r['mean'])} | {_fmt(r['ex'], plus=True)} "
                   f"| {_fmt(r['ci_lo'], plus=True)} ~ {_fmt(r['ci_hi'], plus=True)} | {r['verdict']} |")

    # 累积判决 + 预警
    last = rows[-1] if rows else None
    out.append("")
    if n_all < block:
        out.append(f"**累积**: n={n_all} < {block} → 样本不足，观察中（不判衰退）")
    else:
        ci_all = bootstrap_ci(ex_all[np.isfinite(ex_all)], base, n_boot=1000, alpha=0.05, seed=seed) if len(base) else {"mean_diff": np.nan, "ci_lo": np.nan, "ci_hi": np.nan}
        out.append(f"**累积**: n={n_all}，24h 超额 {_fmt(ci_all.get('mean_diff'), plus=True)} "
                   f"CI[{_fmt(ci_all.get('ci_lo'), plus=True)}, {_fmt(ci_all.get('ci_hi'), plus=True)}]")
    if np.isfinite(s_minus):
        flag = " ⚠️ **CUSUM 向下预警触发**" if s_minus > cusum_h else ""
        out.append(f"**CUSUM S⁻** = {s_minus:.2f}（阈值 {cusum_h}）{flag}")
    if last and np.isfinite(last.get("ci_hi")) and last["ci_hi"] < 0:
        out.append(f"**⚠️ 衰退预警（块级）**: 最近块 {last['label']} 超额 CI 上限 {_fmt(last['ci_hi'], plus=True)} < 0 → 进入 watch")
    elif last and np.isfinite(last.get("ci_lo")) and last["ci_lo"] > 0:
        out.append(f"**健康**: 最近块 {last['label']} 超额 CI 下限 {_fmt(last['ci_lo'], plus=True)} > 0")
    elif last and np.isfinite(last.get("ci_lo")):
        out.append(f"**证据不足（非衰退）**: 最近块 {last['label']} CI 跨零，继续积累")
    return out


def apply_score_gate(df: pd.DataFrame) -> pd.DataFrame:
    """冻结门控（2026-08-09）：status!=FROZEN 或 ts<forward_start → score_vol=NA。

    0 是有效低分，NA 是"不适用/不可用"，绝不混用；异常 → 全 NA 但流程继续。
    """
    try:
        with (PROJECT_ROOT / "config" / "factor_funnel.yaml").open("r", encoding="utf-8") as f:
            spec = yaml.safe_load(f).get("forward_scores", {}).get("score_vol")
        if spec is None or spec.get("status") != "FROZEN":
            df["score_vol"] = np.nan
            return df
        fs = spec.get("forward_start")
        if not fs:
            df["score_vol"] = np.nan
            return df
        fs_ms = int(pd.Timestamp(fs).timestamp() * 1000)
        ts = pd.to_numeric(df["timestamp_ms"], errors="coerce")
        df.loc[ts < fs_ms, "score_vol"] = np.nan
    except Exception:  # noqa: BLE001
        df["score_vol"] = np.nan
    return df


def score_vol_report(cand_fwd: pd.DataFrame, seed: int = 0) -> list[str]:
    """连续分数前向验证段（2026-08-09）：描述性，显式不参与 verdict。

    只对非 NA 分数分桶（high−low uplift）；n<30 或分值无变化 → 明确标注不展示。
    方向化：Long→ret，Short→−ret（只用于本报告，不覆盖 CSV 收益）。
    """
    out = ["\n## 连续分数前向验证（描述性，不参与 verdict）\n"]
    sv = pd.to_numeric(cand_fwd["score_vol"], errors="coerce")
    n_valid = int(sv.notna().sum())
    n_unique = int(sv.dropna().nunique())
    if n_unique < 2 or n_valid < 30:
        out.append(f"- 有效分数样本不足（n={n_valid}，唯一值 {n_unique}）"
                   f"→ **INSUFFICIENT_VARIATION / NOT_ENOUGH_DATA**\n")
        return out
    out.append(f"- 有效分数样本 n={int(sv.notna().sum())}（覆盖率 {sv.notna().mean():.0%}）")
    dirv = cand_fwd["direction"].fillna("Long")
    ret = pd.to_numeric(cand_fwd["ret_24h"], errors="coerce")
    directed = np.where(dirv.astype(str).str.upper().str.startswith("SHORT"), -ret, ret)
    valid = pd.DataFrame({"score": sv, "y": directed}).dropna()
    try:
        valid["bucket"] = pd.qcut(valid["score"], 5, labels=False, duplicates="drop")
    except ValueError:
        valid["bucket"] = 0
    out.append("| 桶 | n | 方向化 24h 均值% | 中位% | 胜率% |")
    out.append("|---|---|---:|---:|---:|")
    rows = []
    for b, g in valid.groupby("bucket"):
        rows.append({"bucket": int(b), "n": len(g), "mean": float(g["y"].mean()),
                     "median": float(g["y"].median()), "win": float((g["y"] > 0).mean())})
    bdf = pd.DataFrame(rows).sort_values("bucket")
    for _, r in bdf.iterrows():
        out.append(f"| {int(r['bucket']) + 1} | {int(r['n'])} | {r['mean']:+.2f} | {r['median']:+.2f} | "
                   f"{100 * r['win']:.0f} |")
    if len(bdf) >= 2:
        out.append(f"\n最高−最低桶 uplift = {bdf.iloc[-1]['mean'] - bdf.iloc[0]['mean']:+.2f}%"
                   f"（样本小，不作显著性叙事）")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-baseline", type=int, default=300, help="每候选时点的基线采样数")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--all", action="store_true",
                        help="用积累 csv（forward_replay_returns.csv）全部候选做验证（前向影子到期验证用）")
    args = parser.parse_args()

    if args.all:
        if not OUT_CSV.exists():
            print(f"[109] --all 需要 {OUT_CSV.name} 积累文件，先跑默认模式积累。")
            return
        cand = pd.read_csv(OUT_CSV)
        cand = cand[pd.to_numeric(cand["timestamp_ms"], errors="coerce").notna()].copy()
        cand["timestamp_ms"] = pd.to_numeric(cand["timestamp_ms"], errors="coerce")
        source_label = f"{OUT_CSV.name}（全量 {len(cand)} 行）"
    else:
        if not CANDIDATES_PATH.exists():
            print(f"[109] 无 {CANDIDATES_PATH}，先跑 108_contract_monitor.py")
            return
        cand = pd.read_csv(CANDIDATES_PATH)
        source_label = f"{CANDIDATES_PATH.name}（n={len(cand)}）"
    if cand.empty:
        print("[109] 无候选。")
        return

    universe = load_universe_symbols()

    # 数据闭环：108 每天覆盖 candidates csv，旧候选不在今日源里。
    # 默认模式下把积累 csv 中收益缺失的旧行纳入回填，否则其 forward 收益永远 NaN。
    old = None
    backfill_events = pd.DataFrame()
    if not args.all and OUT_CSV.exists():
        old = pd.read_csv(OUT_CSV)
        miss = old[old["ret_4h"].isna()].copy()
        ms = pd.to_numeric(miss["timestamp_ms"], errors="coerce")
        miss = miss[ms.notna()]
        if not miss.empty:
            backfill_events = _event_frame(
                miss["symbol"].tolist(),
                pd.to_numeric(miss["timestamp_ms"], errors="coerce").to_numpy(dtype=np.int64),
            )
            print(f"[109] 回填旧候选 {len(backfill_events)} 行（收益缺失）")

    # 事件集 = 候选 + 回填
    ev_ts = pd.to_numeric(cand["timestamp_ms"], errors="coerce").to_numpy(dtype=np.int64)
    ev_syms = cand["symbol"].tolist()
    cand_events = _event_frame(ev_syms, ev_ts)
    all_events = pd.concat([cand_events, backfill_events], ignore_index=True) if not backfill_events.empty else cand_events
    all_events = all_events.dropna(subset=["timestamp"])
    all_syms = sorted(set(all_events["symbol"]))
    tables = load_price_tables(universe + all_syms)
    print(f"[109] 价格表加载: {len(tables)} symbols（universe {len(universe)}）")

    fwd_all = forward_for_events(tables, all_events)
    if fwd_all.empty:
        print("[109] 候选在 binance_free_db 无价格数据。")
        return

    # 收益回填：把本次算出的收益写进旧积累行（数据闭环关键）
    if not backfill_events.empty:
        fill = old.merge(fwd_all, left_on=["symbol", "timestamp_ms"], right_on=["symbol", "timestamp"],
                         how="left", suffixes=("", "_new"))
        for h in HORIZONS:
            c, cn = f"ret_{h}h", f"ret_{h}h_new"
            if cn in fill.columns:
                fill[c] = fill[c].fillna(fill[cn])
                fill = fill.drop(columns=[cn])
        old = fill

    # verdict 事件：默认=今日候选；--all=积累全量（验证模式）
    if args.all:
        verdict_events = _event_frame(
            cand["symbol"].tolist(), pd.to_numeric(cand["timestamp_ms"], errors="coerce").to_numpy(dtype=np.int64))
    else:
        verdict_events = cand_events
    verdict_events = verdict_events.dropna(subset=["timestamp"])
    cand_fwd = fwd_all.merge(
        verdict_events.assign(_v=True)[["symbol", "timestamp", "_v"]],
        on=["symbol", "timestamp"], how="inner").drop(columns=["_v"])
    # 连续打分标注（2026-08-09）：把候选的 score_vol 附到事件行（无列则 NA）
    if "score_vol" in cand.columns:
        cand_fwd = cand_fwd.merge(
            cand[["symbol", "timestamp_ms", "score_vol"]].rename(columns={"timestamp_ms": "timestamp"}),
            on=["symbol", "timestamp"], how="left")
        cand_fwd["score_vol"] = pd.to_numeric(cand_fwd["score_vol"], errors="coerce")
    else:
        cand_fwd["score_vol"] = np.nan
    if cand_fwd.empty:
        print("[109] 候选在 binance_free_db 无价格数据。")
        return

    if args.all:
        # 验证模式：只读积累，不重写（收益已由历史默认运行回填）
        print(f"[109] --all 验证模式：{OUT_CSV.name} 全量 {len(cand)} 候选")
        merged = None
    else:
        # 追加/覆盖 returns 积累 csv（重跑会覆盖同日行，天然幂等）
        accum = cand.merge(
            cand_fwd,
            left_on=["symbol", "timestamp_ms"],
            right_on=["symbol", "timestamp"],
            how="left",
        )
        if old is not None:
            merged = pd.concat([old, accum], ignore_index=True)
        elif OUT_CSV.exists():
            merged = pd.concat([pd.read_csv(OUT_CSV), accum], ignore_index=True)
        else:
            merged = accum
        merged = merged.drop_duplicates(subset=["symbol", "timestamp_ms"], keep="last")
        # 冻结门控（2026-08-09）：未冻结或 < forward_start 的分数清 NA（109 绝不回算历史分）
        if "score_vol" in merged.columns:
            merged = apply_score_gate(merged)
        merged.to_csv(OUT_CSV, index=False)
        print(f"[109] 收益累计写入 {OUT_CSV}（累计 {len(merged)} 行）")

    # 基线：同一时点随机 symbols 横截面（去重候选时点）
    rng = np.random.default_rng(args.seed)
    unique_ts = np.unique(ev_ts)
    base_events = []
    for ts in unique_ts:
        n = max(args.n_baseline, 1)
        syms = rng.choice(sorted(universe), size=n, replace=True)
        base_events.append(_event_frame(syms.tolist(), np.full(n, ts)))
    base_fwd = forward_for_events(tables, pd.concat(base_events, ignore_index=True))

    # 汇总 + bootstrap
    lines: list[str] = []
    lines.append("# AlphaHive V3 前向影子收益复核\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='Asia/Shanghai'):%Y-%m-%d %H:%M 北京时间}")
    lines.append(f"- 候选源: {source_label}，trigger={cand['trigger'].dropna().unique().tolist()}）")
    lines.append(f"- 基线: 候选时点 {len(unique_ts)} 个，每时点随机 {args.n_baseline} 个 universe symbol 横截面")
    lines.append(f"- 样本不足时 verdict=PENDING（CI 宽，待积累）\n")

    verdicts = []
    for h in HORIZONS:
        col = f"ret_{h}h"
        e = pd.to_numeric(cand_fwd[col], errors="coerce").to_numpy(dtype=float)
        b = pd.to_numeric(base_fwd[col], errors="coerce").to_numpy(dtype=float)
        n_e = int(np.isfinite(e).sum())
        if n_e == 0:
            lines.append(f"\n## {h}h — NOT_ENOUGH_DATA（候选尚无 {h}h 前向数据）\n")
            verdicts.append(f"{h}h:PENDING")
            continue
        b = b[np.isfinite(b)]
        boot = bootstrap_ci(e, b, seed=args.seed)
        es = summarize(e, "candidate", h)
        bs = summarize(b, "baseline", h)
        # verdict：均值差 CI 下限 > 0 且基线充分 → GO；样本太少 → PENDING
        if n_e < 10 or len(b) < 100:
            verdict = "PENDING"
        elif boot["ci_lo"] > 0:
            verdict = "GO"
        elif boot["ci_hi"] < 0:
            verdict = "NO_GO"
        else:
            verdict = "INCONCLUSIVE"
        verdicts.append(f"{h}h:{verdict}")
        lines.append(f"\n## {h}h — {verdict}\n")
        lines.append("| 组 | n | 均值% | 中位数% | 胜率% |")
        lines.append("|---|---|---|---|---|")
        for s in (es, bs):
            lines.append(f"| {s['group']} | {s['n']} | {s['mean_pct']:.2f} | {s['median_pct']:.2f} | {s['winrate']*100:.0f} |")
        lines.append(f"\n超额（事件−基线）均值 = {boot['mean_diff']:+.2f}%  "
                     f"bootstrap 95% CI [{boot['ci_lo']:+.2f}, {boot['ci_hi']:+.2f}]")
        if n_e < 10 or len(b) < 100:
            lines.append(f"\n> ⚠️ 样本不足（事件 n={n_e}，基线 n={len(b)}）→ PENDING，继续积累前向影子。")

    lines.append(f"\n## Verdict 汇总\n\n{' | '.join(verdicts)}\n")

    # 连续分数前向验证段（2026-08-09，描述性不参与 verdict）
    lines.extend(score_vol_report(cand_fwd, seed=args.seed))

    # Decay 监测（EDGE_LEDGER 配套；--all 全量时才有统计意义，默认模式也输出观察段）
    lines.extend(decay_monitor(cand_fwd, base_fwd["ret_24h"].to_numpy() if not base_fwd.empty else np.array([]),
                               seed=args.seed))
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[109] wrote {OUT_MD}")
    print(f"[109] verdict: {' | '.join(verdicts)}")

    # 控制台明细
    print("\n候选 forward 收益：")
    show = cand_fwd[["symbol", "timestamp"] + [f"ret_{h}h" for h in HORIZONS]].copy()
    show["timestamp"] = pd.to_datetime(show["timestamp"], unit="ms", utc=True)
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()
