r"""189_high_beta_basket.py — 高 beta 山寨篮子凸性研究（用户方向：涨跌放大篮子的 α）。

问题：大饼涨山寨普涨、跌普跌——是否存在一篮子山寨在 BTC 涨时涨更多、跌时跌更多，
且这种放大是"对称 beta"（杠杆替代，无 α）还是"凸性"（涨时 beta > 跌时 beta，真 α）？

设计：
1. 月度滚动：每山寨对 BTC 24h 收益回归（60d 窗口）→ beta
2. 高 beta top20% 篮子 vs 低 beta bottom20% vs BTC（月度再平衡，12 次/年）
3. 收益分解：α（超额）、beta 对称性、凸性（涨市 beta vs 跌市 beta 分别回归）
4. 对冲组合：多高 beta 篮子 + 空 BTC（beta 中性）→ 纯凸性/α 暴露
5. 成本：月度再平衡（54bps round-trip），换手可控

输出：reports/high_beta_basket.md
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

REPORT = PROJECT_ROOT / "reports" / "high_beta_basket.md"
START = "2022-01-01"
END = "2026-06-30"
BETA_WIN = 60        # beta 估计窗口（天）
REBAL = 30           # 月度再平衡
COST = 0.0054
MIN_N = 30


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    # 日线面板
    closes = {}
    for sym, ctx in ctxs.items():
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        s = pd.Series(close, index=pd.to_datetime(axis, unit="ms", utc=True).tz_localize(None).normalize())
        closes[sym] = s[~s.index.duplicated(keep="last")].sort_index()
    panel = pd.DataFrame(closes).dropna(how="all").loc[START:END]
    # BTC 单独加载（universe 是山寨池，不含 BTC）
    p_btc = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    bdf = pd.read_parquet(p_btc, columns=["open_time", "close"])
    bts = pd.to_numeric(bdf["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    bcl = pd.to_numeric(bdf["close"], errors="coerce").to_numpy(dtype=float)
    btc_s = pd.Series(bcl, index=pd.to_datetime(bts, unit="ms", utc=True).tz_localize(None).normalize())
    btc = btc_s[~btc_s.index.duplicated(keep="last")].sort_index().loc[START:END]
    alts = [c for c in panel.columns if c != "BTCUSDT"]
    rets = panel.pct_change()
    btc_ret = btc.pct_change()
    # 注意：不整体 dropna（新上市币早期 NaN 会删光面板行）；每币单独 dropna

    # 月度滚动 beta
    dates = rets.index
    monthly_idx = list(range(BETA_WIN, len(dates), REBAL))
    results = {"hi_alpha": [], "lo_alpha": [], "hi_beta_up": [], "hi_beta_dn": [],
               "lo_beta_up": [], "lo_beta_dn": [], "month": []}
    hi_nets, lo_nets = [], []
    for mi in monthly_idx:
        t0 = dates[mi - BETA_WIN]
        t1 = dates[mi - 1]
        w = rets.loc[t0:t1]
        br = btc_ret.loc[t0:t1]
        betas = {}
        for a in alts:
            if a not in w.columns or w[a].dropna().count() < BETA_WIN * 0.5:
                continue
            x = w[a].dropna()
            y = br.reindex(x.index)
            valid = pd.concat([x, y], axis=1).dropna()
            if len(valid) < 20:
                continue
            b = np.polyfit(valid.iloc[:, 1].to_numpy(), valid.iloc[:, 0].to_numpy(), 1)[0]
            if np.isfinite(b):
                betas[a] = b
        if len(betas) < 10:
            continue
        ranked = sorted(betas.items(), key=lambda kv: kv[1])
        n_sel = max(3, len(ranked) // 5)
        hi = [s for s, _ in ranked[-n_sel:]]
        lo = [s for s, _ in ranked[:n_sel]]
        # 下月收益
        f0 = dates[mi]
        f1 = dates[min(mi + REBAL - 1, len(dates) - 1)]
        fr = rets.loc[f0:f1]
        if len(fr) == 0:
            continue
        hi_nets.append(fr[hi].mean(axis=1).mean() - COST)
        lo_nets.append(fr[lo].mean(axis=1).mean() - COST)
        # 涨跌市 beta（下月内）
        br_f = btc_ret.loc[f0:f1]
        for name, basket in [("hi", hi), ("lo", lo)]:
            bret = fr[basket].mean(axis=1)
            up = br_f > 0
            dn = br_f <= 0
            if up.sum() >= 5 and dn.sum() >= 5:
                bu = np.polyfit(br_f[up].to_numpy(), bret[up].to_numpy(), 1)[0]
                bd = np.polyfit(br_f[dn].to_numpy(), bret[dn].to_numpy(), 1)[0]
                results[f"{name}_beta_up"].append(bu)
                results[f"{name}_beta_dn"].append(bd)
        results["month"].append(str(f0.date()))

    lines = ["# 高 beta 山寨篮子凸性研究（189）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 方法：60d 滚动 beta，月度再平衡，top/bottom 20% 篮子；成本 {COST * 1e4:.0f}bps/月\n",
             f"- 样本：{len(monthly_idx)} 个月度期，可用 {len(hi_nets)} 期\n",
             "| 篮子 | 月均净收益 | 年化 | 涨市 beta | 跌市 beta | 凸性(涨−跌) |",
             "|---|---:|---:|---:|---:|---|"]
    hi_n, lo_n = np.array(hi_nets), np.array(lo_nets)
    for label, arr, bu, bd in [
        ("高 beta top20%", hi_n, results["hi_beta_up"], results["hi_beta_dn"]),
        ("低 beta bottom20%", lo_n, results["lo_beta_up"], results["lo_beta_dn"]),
    ]:
        if len(arr) == 0:
            continue
        ann = arr.mean() * 12 * 100
        bu_a, bd_a = np.mean(bu), np.mean(bd)
        lines.append(f"| {label} | {arr.mean() * 100:+.2f}% | {ann:+.1f}% "
                     f"| {bu_a:+.2f} | {bd_a:+.2f} | {bu_a - bd_a:+.2f} |")
        print(f"[189] {label}: 月均 {arr.mean() * 100:+.2f}% 年化 {ann:+.1f}% "
              f"涨市beta {bu_a:+.2f} 跌市beta {bd_a:+.2f} 凸性 {bu_a - bd_a:+.2f}")

    # 对冲组合：多高 beta + 空 BTC（近似 beta 中性）
    if len(hi_nets) > 5:
        # 简化：BTC 月收益
        btc_month = []
        for mi in monthly_idx[1:]:
            f0 = dates[mi]
            f1 = dates[min(mi + REBAL - 1, len(dates) - 1)]
            r = btc.loc[f1] / btc.loc[f0] - 1
            btc_month.append(r)
        bm = np.array(btc_month[:len(hi_nets)])
        hedge = hi_n - bm * 1.0  # 1:1 对冲（未按 beta 缩放，近似）
        lines.append(f"\n- 对冲组合（多高 beta + 空 BTC 1:1）：月均 {hedge.mean() * 100:+.2f}% "
                     f"年化 {hedge.mean() * 12 * 100:+.1f}%（beta 中性后的 α/凸性暴露）")

    lines.extend(["\n## 解读\n",
                  "- 高 beta 篮子涨市 beta > 跌市 beta（凸性 > 0）→ 真 α（免费杠杆）；≈ 对称 → 杠杆替代。",
                  "- 对冲组合年化显著正 → 纯凸性/α 可剥离（s019 候选）；≈0 → 无独立 α（仅增强工具）。",
                  "- 注意：月度再平衡换手可控；篮子大小 ≥3 币分散。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
