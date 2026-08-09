"""105_event_study.py — 合约异动事件研究回测（Phase 2 核心验证）。

对 config/contract_anomaly_rules.yaml 的每个触发规则：
- 在 coinglass_db 历史（2024-06 → 2026-05-27）找触发时点
- forward 4h/24h/72h/168h 收益 + MFE/MAE
- 随机基线对照 + bootstrap 置信区间
- 分月/分桶报告，输出 Go/No-Go（vs 随机基线是否显著）

诚实：bootstrap 只证明「事件组显著不同于随机采样」，不代表真实 alpha
（未计手续费/滑点/幸存者偏差，那由后续前向影子验证）。

用法：
  python scripts/105_event_study.py [--feature liq_cascade_short] [--start 2024-06-01] [--end 2026-05-27]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.contract_anomaly_features import compute_symbol_features
from harness.lib.event_study import (
    DEFAULT_HORIZONS,
    bootstrap_ci,
    detect_events,
    draw_random_events,
    forward_stats,
    summarize_events,
)

RAW_1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
REPORTS_DIR = PROJECT_ROOT / "reports"
RULES_PATH = PROJECT_ROOT / "config" / "contract_anomaly_rules.yaml"
SCAN_RULES_PATH = PROJECT_ROOT / "config" / "scan_rules.yaml"

BASE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]  # 大盘基准不参与山寨事件池


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_symbols(args: argparse.Namespace) -> list[str]:
    if args.symbols:
        return [s.strip() for s in args.symbols.split(",")]
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = json.load(f)["symbols"]
    return [item["symbol"] for item in universe if item["symbol"] not in BASE_SYMBOLS]


def build_tables(symbols: list[str]) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        ft = compute_symbol_features(sym, RAW_1H)
        if len(ft) >= 720:  # 至少 30d 历史才有特征意义
            tables[sym] = ft
    return tables


def baseline_forward_stats(
    tables: dict[str, pd.DataFrame],
    base_events: pd.DataFrame,
    horizons: list[int],
) -> pd.DataFrame:
    if base_events.empty:
        return pd.DataFrame()
    parts = []
    for sym, g in base_events.groupby("symbol"):
        if sym not in tables:
            continue
        parts.append(forward_stats(tables[sym], g.copy(), horizons))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def run_trigger(
    name: str,
    rule: dict,
    tables: dict[str, pd.DataFrame],
    study: dict,
    horizons: list[int],
    rng: np.random.Generator,
    start_ms: int | None,
    end_ms: int | None,
) -> dict:
    max_fwd = int(study.get("max_forward_hours", 168))
    evs: list[pd.DataFrame] = []
    for sym, ft in tables.items():
        ev = detect_events(ft, sym, rule, max_forward_hours=max_fwd)
        if ev.empty:
            continue
        if start_ms is not None:
            ev = ev[ev["timestamp"] >= start_ms]
        if end_ms is not None:
            ev = ev[ev["timestamp"] <= end_ms]
        ev = forward_stats(ft, ev, horizons)
        evs.append(ev)
    if not evs:
        return {"name": name, "n_events": 0, "rule": rule}
    events = pd.concat(evs, ignore_index=True)
    events["trigger"] = name  # 供 106 regime 门控分 trigger 引用

    n_base = min(int(len(events)), int(study.get("baseline_max_draws", 100_000)))
    base = draw_random_events(tables, n_base, rng, max_forward_hours=max_fwd, start_ms=start_ms, end_ms=end_ms)
    base_stats = baseline_forward_stats(tables, base, horizons)

    result = {"name": name, "n_events": len(events), "rule": rule}
    result["summary"] = summarize_events(events, horizons)
    result["baseline"] = summarize_events(base_stats, horizons) if not base_stats.empty else {}
    result["per_horizon"] = {}
    for h in horizons:
        col = f"ret_{h}h"
        ev_v = pd.to_numeric(events[col], errors="coerce").dropna().to_numpy()
        bs_v = pd.to_numeric(base_stats[col], errors="coerce").dropna().to_numpy() if not base_stats.empty else np.array([])
        ci = bootstrap_ci(ev_v, bs_v, n_boot=int(study.get("bootstrap", {}).get("n_boot", 1000)))
        result["per_horizon"][str(h)] = ci

    # Go/No-Go 判定（用 24h 主 horizon，若样本不足则 72h）
    min_ev = int(study.get("bootstrap", {}).get("min_events", 30))
    main_h = "24" if "24" in result["per_horizon"] else str(horizons[0])
    ci = result["per_horizon"].get(main_h, {})
    n_ev = int(ci.get("n_event", 0))
    if n_ev < min_ev or not np.isfinite(ci.get("ci_lo", np.nan)):
        result["verdict"] = "NO_GO"
        result["verdict_reason"] = f"样本不足(n={n_ev}<{min_ev})或基线为空"
    elif ci["ci_lo"] > 0:
        result["verdict"] = "GO_LONG"
        result["verdict_reason"] = f"{main_h}h 超额收益 CI 下界 {ci['ci_lo']:.2f}% > 0"
    elif ci["ci_hi"] < 0:
        result["verdict"] = "GO_SHORT"
        result["verdict_reason"] = f"{main_h}h 超额收益 CI 上界 {ci['ci_hi']:.2f}% < 0"
    else:
        result["verdict"] = "NO_GO"
        result["verdict_reason"] = f"{main_h}h CI=[{ci['ci_lo']:.2f},{ci['ci_hi']:.2f}] 含 0"

    # 分月
    months = pd.to_datetime(events["timestamp"], unit="ms", utc=True).dt.tz_localize(None).dt.to_period("M")
    monthly = pd.DataFrame({
        "month": months.astype(str),
        "ret_24h": pd.to_numeric(events["ret_24h"], errors="coerce"),
        "ret_168h": pd.to_numeric(events["ret_168h"], errors="coerce") if "ret_168h" in events.columns else pd.NA,
    }).groupby("month", dropna=False).agg(
        n=("ret_24h", "count"), ret_24h=("ret_24h", "mean"), ret_168h=("ret_168h", "mean"),
    )
    result["monthly"] = monthly

    # 分桶（按触发特征值 4 分桶）
    fv = pd.to_numeric(events["feature_value"], errors="coerce")
    events_b = events.assign(feature_value=fv)
    try:
        buckets = pd.qcut(events_b["feature_value"], 4, duplicates="drop")
        bucketed = events_b.assign(bucket=buckets).groupby("bucket", observed=False).agg(
            n=("ret_24h", "count"), ret_24h=("ret_24h", "mean"),
            feature_lo=("feature_value", "min"), feature_hi=("feature_value", "max"),
        )
        result["bucketed"] = bucketed
    except (ValueError, TypeError):
        result["bucketed"] = pd.DataFrame()

    result["events"] = events
    return result


def render_report(results: list[dict], horizons: list[int]) -> str:
    lines: list[str] = []
    lines.append("# AlphaHive V3 合约异动事件研究报告\n")
    lines.append(f"- 生成时间: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 规则版本: {load_yaml(RULES_PATH)['contract_anomaly_rules_version']}")
    lines.append(f"- horizons: {horizons}")
    lines.append("> 超额收益 = 事件组均值 − 随机基线均值（bootstrap 1000 次，95% CI）。")
    lines.append("> GO 只表示显著优于随机采样，不等于真实 alpha；需前向影子验证。\n")

    lines.append("## 汇总判定\n")
    lines.append("| trigger | 事件数 | 24h超额均值 | CI下界 | CI上界 | 判定 |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        ci = r.get("per_horizon", {}).get("24", {})
        md = ci.get("mean_diff", np.nan)
        lines.append(
            f"| {r['name']} | {r['n_events']} | {md:.2f}% | {ci.get('ci_lo', np.nan):.2f}% | {ci.get('ci_hi', np.nan):.2f}% "
            f"| **{r['verdict']}** |"
        )

    for r in results:
        if r["n_events"] == 0:
            lines.append(f"\n## {r['name']} — 无事件\n")
            continue
        lines.append(f"\n## {r['name']}")
        lines.append(f"**判定: {r['verdict']}** — {r['verdict_reason']}\n")
        lines.append(f"事件数: {r['n_events']}  |  描述: {r['rule'].get('description','')}\n")
        lines.append("### 各 horizon\n")
        lines.append("| horizon | 事件均值 | 事件中位 | 胜率 | 基线均值 | 超额 | CI |")
        lines.append("|---|---|---|---|---|---|---|")
        for h in horizons:
            s = r["summary"]
            b = r.get("baseline", {})
            ci = r.get("per_horizon", {}).get(str(h), {})
            lines.append(
                f"| {h}h | {s.get(f'ret_{h}h_mean', np.nan):.2f}% | {s.get(f'ret_{h}h_median', np.nan):.2f}% "
                f"| {s.get(f'ret_{h}h_win', np.nan)*100:.0f}% | {b.get(f'ret_{h}h_mean', np.nan):.2f}% "
                f"| {ci.get('mean_diff', np.nan):.2f}% | [{ci.get('ci_lo', np.nan):.2f}, {ci.get('ci_hi', np.nan):.2f}] |"
            )
        lines.append(f"\nMFE 均值: {r['summary'].get('mfe_mean', np.nan):.2f}%  |  MAE 均值: {r['summary'].get('mae_mean', np.nan):.2f}%\n")
        if not r.get("monthly", pd.DataFrame()).empty:
            lines.append("### 分月\n")
            lines.append("| 月 | n | 24h均 | 168h均 |")
            lines.append("|---|---|---|---|")
            for m, row in r["monthly"].iterrows():
                lines.append(f"| {m} | {int(row['n'])} | {row['ret_24h']:.2f}% | {row['ret_168h']:.2f}% |")
        if not r.get("bucketed", pd.DataFrame()).empty:
            lines.append("\n### 分桶（按触发特征值 4 分位）\n")
            lines.append("| 桶 | n | 24h均 | 特征范围 |")
            lines.append("|---|---|---|---|")
            for b, row in r["bucketed"].iterrows():
                lines.append(f"| {b} | {int(row['n'])} | {row['ret_24h']:.2f}% | [{row['feature_lo']:.2f}, {row['feature_hi']:.2f}] |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature", default=None, help="只跑某 trigger（默认全部）")
    parser.add_argument("--symbols", default=None, help="逗号分隔的 symbol 子集")
    parser.add_argument("--start", default="2024-06-01", help="事件区间起点")
    parser.add_argument("--end", default="2026-05-27", help="事件区间终点")
    args = parser.parse_args()

    rules = load_yaml(RULES_PATH)
    study = rules["study"]
    triggers = rules["triggers"]
    horizons = DEFAULT_HORIZONS
    if args.feature:
        triggers = {args.feature: triggers[args.feature]}

    start_ms = int(pd.Timestamp(args.start, tz="UTC").timestamp() * 1000)
    end_ms = int(pd.Timestamp(args.end, tz="UTC").timestamp() * 1000)

    print("构建特征表...")
    tables = build_tables(load_symbols(args))
    print(f"  {len(tables)} symbols 特征表就绪")
    rng = np.random.default_rng(2026)

    results = []
    for name, rule in triggers.items():
        print(f"  事件研究: {name}")
        res = run_trigger(name, rule, tables, study, horizons, rng, start_ms, end_ms)
        results.append(res)

    # 汇总事件明细
    all_events = pd.concat([r["events"] for r in results if r["n_events"] > 0], ignore_index=True)
    all_events.to_csv(REPORTS_DIR / "event_study_events.csv", index=False)

    summary_rows = [{
        "trigger": r["name"], "n_events": r["n_events"], "verdict": r["verdict"],
        **{f"{h}h_mean": r["summary"].get(f"ret_{h}h_mean") for h in horizons},
        **{f"{h}h_ci_lo": r.get("per_horizon", {}).get(str(h), {}).get("ci_lo") for h in horizons},
        **{f"{h}h_ci_hi": r.get("per_horizon", {}).get(str(h), {}).get("ci_hi") for h in horizons},
    } for r in results]
    pd.DataFrame(summary_rows).to_csv(REPORTS_DIR / "event_study_summary.csv", index=False)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "event_study_report.md"
    report_path.write_text(render_report(results, horizons), encoding="utf-8")
    print(f"\nwrote {report_path}")
    print("\n=== Go/No-Go ===")
    for r in results:
        print(f"  {r['name']:24s} n={r['n_events']:5d}  {r['verdict']}")


if __name__ == "__main__":
    main()
