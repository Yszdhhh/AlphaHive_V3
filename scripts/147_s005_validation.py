r"""147_s005_validation.py — s005-B（funding 拥挤空头做多）升级验证。

四项验证（s005 alpha_card §4 failure 清单）：
1. 独立时间窗口：2022-01→2023-12（W1）vs 2024-01→2026-06（W2），168h 超额各自 bootstrap CI
2. 尾部切除：去掉 top 5% 大赢家后均值/中位数是否仍正
3. 组合增量：B 与 wash_cvd 同 symbol 配对 168h 收益相关 + 等权组合风险收益 vs 单流
4. 成本 2× 敏感性：毛利 - 108bps 后净期望

数据/事件口径与 146 完全一致（funding 30d min-max < 0.05，72h 冷却）。
输出：reports/s005_validation.md
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

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
    "m146", str(PROJECT_ROOT / "scripts" / "146_funding_extreme_reversal.py"))
m146 = importlib.util.module_from_spec(_spec3)
sys.modules["m146"] = m146
_spec3.loader.exec_module(m146)

from harness.lib.event_study import bootstrap_ci  # noqa: E402

REPORT = PROJECT_ROOT / "reports" / "s005_validation.md"
W1_END = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)
COST_2X = 108.0 / 10000.0


def collect_b_events() -> list[dict]:
    symbols = m113.load_universe_symbols()
    fundings = m113.load_funding_series(symbols)
    ctxs = m113.load_price_ctx(symbols)
    rows: list[dict] = []
    for sym in symbols:
        if sym not in fundings or sym not in ctxs:
            continue
        fund = fundings[sym]
        fund = fund[fund.index >= m146.LO_MS]
        norm = m146.funding_norm(fund)
        _, b_ev = m146.detect_events(norm, m146.NORM_HI, m146.NORM_LO, 72)
        if not b_ev:
            continue
        ctx = ctxs[sym]
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        for t in b_ev:
            pos = int(np.searchsorted(axis, t, side="right")) - 1
            if pos < 0 or pos + 168 >= len(close):
                continue
            r168 = (close[pos + 168] / close[pos] - 1) * 100.0
            if np.isfinite(r168):
                rows.append({"symbol": sym, "t": t, "r168": r168})
    return rows


def collect_wc_events() -> list[dict]:
    symbols = m113.load_universe_symbols()
    fundings = m113.load_funding_series(symbols)
    ctxs = m113.load_price_ctx(symbols)
    rows: list[dict] = []
    for sym, ctx in ctxs.items():
        ev = m115.detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if ev.empty:
            continue
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        for t in ev["timestamp"].astype(np.int64).to_numpy():
            pos = int(np.searchsorted(axis, t, side="right")) - 1
            if pos < 0 or pos + 168 >= len(close):
                continue
            r168 = (close[pos + 168] / close[pos] - 1) * 100.0
            if np.isfinite(r168):
                rows.append({"symbol": sym, "t": int(t), "r168": r168})
    return rows


def main() -> int:
    b = collect_b_events()
    wc = collect_wc_events()
    bdf = pd.DataFrame(b)
    wdf = pd.DataFrame(wc)
    print(f"B 事件 {len(bdf)} | wash_cvd 事件 {len(wdf)}")

    lines = ["# s005-B 升级验证（147）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- B 事件 n={len(bdf)}（168h 有值）；wash_cvd 对照 n={len(wdf)}\n"]

    # 1. 独立时间窗口
    bdf["period"] = np.where(bdf["t"] < W1_END, "W1_2022-23", "W2_2024-26")
    lines.append("## 1. 独立时间窗口（168h 超额 vs 全区间随机基线）\n")
    rng = np.random.default_rng(2026)
    ctxs = m113.load_price_ctx(m113.load_universe_symbols())
    base = m146.draw_random_events if hasattr(m146, "draw_random_events") else None
    # 用 146 同款基线生成
    from harness.lib.event_study import draw_random_events, DEFAULT_HORIZONS, forward_stats  # noqa: E402
    rng2 = np.random.default_rng(2026)
    bbase = draw_random_events(ctxs, 3000, rng2, max_forward_hours=168,
                               start_ms=m146.LO_MS, end_ms=m146.HI_MS)
    bparts = []
    for bs, bg in bbase.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    bbase_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br = pd.to_numeric(bbase_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines.append("| 窗口 | n | 168h 均值 | 168h 超额 | CI | 中位数 | 判定 |")
    lines.append("|---|---|---:|---:|---:|---:|---|")
    for period, g in bdf.groupby("period", sort=False):
        r = g["r168"].to_numpy(dtype=float)
        ci = bootstrap_ci(r, br, n_boot=1000, alpha=0.05, seed=2026)
        verdict = ("样本不足" if len(r) < 30 else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {period} | {len(r)} | {r.mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% | **{verdict}** |")
        print(f"[147] {period}: n={len(r)} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    # 2. 尾部切除
    lines.append("\n## 2. 尾部切除（去 top 5% 大赢家后）\n")
    r_all = bdf["r168"].to_numpy(dtype=float)
    thr = np.quantile(r_all, 0.95)
    keep = r_all[r_all <= thr]
    lines.append(f"- 切除阈值：168h > {thr:+.2f}%（top 5%）")
    lines.append(f"- 切除后：n={len(keep)}，均值 {keep.mean():+.2f}%，中位数 {np.median(keep):+.2f}%")
    lines.append(f"- 原：n={len(r_all)}，均值 {r_all.mean():+.2f}%，中位数 {np.median(r_all):+.2f}%\n")
    print(f"[147] 尾部切除后均值 {keep.mean():+.2f}% 中位数 {np.median(keep):+.2f}%")

    # 3. 组合增量：同 symbol 配对相关 + 等权组合
    lines.append("## 3. 与 wash_cvd 的组合增量\n")
    b_sym = bdf.groupby("symbol")["r168"].mean()
    w_sym = wdf.groupby("symbol")["r168"].mean()
    common = b_sym.index.intersection(w_sym.index)
    if len(common) >= 10:
        corr = np.corrcoef(b_sym[common].to_numpy(), w_sym[common].to_numpy())[0, 1]
        lines.append(f"- 同 symbol 配对 168h 收益相关（n={len(common)} symbols）：r = {corr:+.2f}")
        # 等权组合（每 symbol 的 B/wc 均值各半）
        combo = 0.5 * b_sym[common] + 0.5 * w_sym[common]
        lines.append(f"- 等权组合：均值 {combo.mean():+.2f}% vs B 单流 {b_sym[common].mean():+.2f}% "
                     f"vs wc 单流 {w_sym[common].mean():+.2f}%")
        lines.append(f"- 组合标准差 {combo.std():.2f}% vs B {b_sym[common].std():.2f}% "
                     f"vs wc {w_sym[common].std():.2f}% → "
                     f"{'分散有效（组合 Sharpe 提升）' if combo.std() < min(b_sym[common].std(), w_sym[common].std()) else '无分散'}")
        print(f"[147] 配对相关 r={corr:+.2f} 组合均值 {combo.mean():+.2f}%")
    else:
        lines.append("- 共同 symbol < 10，跳过配对相关。")

    # 4. 成本 2× 敏感性
    lines.append("\n## 4. 成本 2× 敏感性（108bps round-trip）\n")
    gross = r_all.mean() / 100.0
    net_2x = gross - COST_2X
    lines.append(f"- 毛利 168h {gross * 100:+.2f}% - 2×成本 {COST_2X * 100:.2f}% = 净 {net_2x * 100:+.2f}%"
                 f"（{'✓ 仍正' if net_2x > 0 else '✗ 转负'}）")
    # 尾部切除后 + 2× 成本
    gross_t = keep.mean() / 100.0
    net_t = gross_t - COST_2X
    lines.append(f"- 尾部切除后：{gross_t * 100:+.2f}% - {COST_2X * 100:.2f}% = {net_t * 100:+.2f}%"
                 f"（{'✓' if net_t > 0 else '✗'}）")

    lines.extend(["\n## 裁决\n",
                  "- 独立窗口两段均显著且同向 → edge 跨 regime 稳定；仅一段显著 → regime 依赖。",
                  "- 尾部切除后均值/中位数仍正 → 不是纯运气驱动；转负 → 依赖少数大赢家，需筛选条件。",
                  "- 配对相关低 + 组合波动下降 → 与 wash_cvd 可组合；高相关 → 合并管理。",
                  "- 净期望（含 2× 成本）> 0 → 可交易；≤0 → 不可交易。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
