r"""190_p1_negative_convexity.py — P1：负凸性交易（空高 beta 山寨 + 多 BTC）。

189 发现：山寨相对 BTC 是负凸性（跌市 beta 1.46 > 涨市 1.38），高 beta 篮子无 α。
本脚本反向做多凸性：月度滚动 beta → 做空高 beta 篮子 + 做多 BTC（按篮子 beta 均值对冲），
检验负凸性是否可以交易（反向结构）。

成本：永续空 27bps 单边 + BTC 多 27bps = 54bps/月展期。
检验：组合月均/年化/回撤/胜率 vs 0；成本 1×/2× 敏感性。
输出：reports/p1_negative_convexity.md
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

REPORT = PROJECT_ROOT / "reports" / "p1_negative_convexity.md"
START = "2022-01-01"
END = "2026-06-30"
BETA_WIN = 60
REBAL = 30
COST = 0.0054


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    closes = {}
    for sym, ctx in ctxs.items():
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        s = pd.Series(close, index=pd.to_datetime(axis, unit="ms", utc=True).tz_localize(None).normalize())
        closes[sym] = s[~s.index.duplicated(keep="last")].sort_index()
    panel = pd.DataFrame(closes).dropna(how="all").loc[START:END]
    p_btc = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    bdf = pd.read_parquet(p_btc, columns=["open_time", "close"])
    bts = pd.to_numeric(bdf["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    bcl = pd.to_numeric(bdf["close"], errors="coerce").to_numpy(dtype=float)
    btc_s = pd.Series(bcl, index=pd.to_datetime(bts, unit="ms", utc=True).tz_localize(None).normalize())
    btc = btc_s[~btc_s.index.duplicated(keep="last")].sort_index().loc[START:END]
    alts = [c for c in panel.columns if c != "BTCUSDT"]
    rets = panel.pct_change()
    btc_ret = btc.pct_change()

    dates = rets.index
    monthly_idx = list(range(BETA_WIN, len(dates), REBAL))
    net_rets = []
    bm_rets = []
    for mi in monthly_idx:
        t0, t1 = dates[mi - BETA_WIN], dates[mi - 1]
        w = rets.loc[t0:t1]
        br = btc_ret.loc[t0:t1]
        betas = {}
        for a in alts:
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
        hi_beta = np.mean([b for _, b in ranked[-n_sel:]])
        f0 = dates[mi]
        f1 = dates[min(mi + REBAL - 1, len(dates) - 1)]
        fr = rets.loc[f0:f1]
        if len(fr) == 0:
            continue
        # 空高 beta 篮子 + 多 BTC（对冲比例 = 篮子 beta）
        basket_ret = fr[hi].mean(axis=1)
        bm = btc_ret.loc[f0:f1].reindex(fr.index)
        valid2 = pd.concat([basket_ret, bm], axis=1).dropna()
        if len(valid2) < 10:
            continue
        combo = (-valid2.iloc[:, 0] + hi_beta * valid2.iloc[:, 1]).mean() - COST
        net_rets.append(combo)
        bm_rets.append(valid2.iloc[:, 1].mean())
    net = np.array(net_rets)
    bm = np.array(bm_rets)
    lines = ["# P1：负凸性交易（空高 beta 山寨 + 多 BTC）（190）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 方法：60d 滚动 beta，月度再平衡；空 top20% 高 beta 篮子 + 多 BTC（比例=篮子 beta）",
             f"- 成本 {COST * 1e4:.0f}bps/月；有效期数 {len(net)}\n",
             "| 组合 | 月均 | 年化 | 胜率 | 最大回撤 |",
             "|---|---:|---:|---:|---|"]
    if len(net) < 6:
        lines.append("| 样本不足 | - | - | - | - |")
        print("[190] 样本不足")
    else:
        eq = np.cumprod(1 + net)
        mdd = float((eq / np.maximum.accumulate(eq) - 1).min() * 100)
        lines.append(f"| 空高beta+多BTC | {net.mean() * 100:+.2f}% | {net.mean() * 12 * 100:+.1f}% "
                     f"| {100 * (net > 0).mean():.0f}% | {mdd:.1f}% |")
        lines.append(f"| 对照 BTC 持有 | {bm.mean() * 100:+.2f}% | {bm.mean() * 12 * 100:+.1f}% | - | - |")
        # 成本敏感性
        for k in [1, 2]:
            lines.append(f"- {k}× 成本（{COST * k * 1e4:.0f}bps/月）：净 {net.mean() * 100 - COST * (k - 1) * 100:+.2f}%/月")
        print(f"[190] 空高beta+多BTC: 月均 {net.mean() * 100:+.2f}% 年化 {net.mean() * 12 * 100:+.1f}% "
              f"胜率 {100 * (net > 0).mean():.0f}% 回撤 {mdd:.1f}%")
    lines.extend(["\n## 解读\n",
                  "- 组合年化显著正 → 负凸性可交易（山寨空头+做多 BTC = 正凸性暴露）。",
                  "- ≈0/负 → 负凸性不可直接交易（融资成本/空头约束吃掉），仅作认知。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
