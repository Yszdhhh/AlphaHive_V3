r"""211_attention_shock_factors.py — 因子 7 注意力-情绪背离 + 因子 8 本地-全球冲击（codex 因子池）。

两因子都是市场级日度特征（同一事件管道，一并测）：

因子 7（E-B 情绪）：
  attention_resid = GoogleTrends_z − z(|BTC 24h return|)
  组合 = attention_resid 高 且 前一日 F&G ≥ 60（关注增加但未恐慌）
  主问题：attention 对已知 F&G 调制是否有 marginal（不重新证明 F&G）。
  数据：Google Trends 周频（138 缓存，周分辨率）→ 事件所在周的 attention_resid（前周 asof）。

因子 8（E-A/E-C）：
  local_shock_score = z(alt 横截面 realized vol / breadth 压力) − z(VIX 前收)
  高 = 加密本地冲击（非全球风险驱动）→ 卖压结束后反弹更容易？
  数据：universe alt klines（横截面 24h realized vol + breadth）、VIX（macro）。

验收：分位分层 → 24/72/168h；日度因子按 unique event day 等权；≥60 独立事件日；
组合不优于 F&G-only / 控制 VIX 后消失 → NO_GO。

输出：reports/attention_shock_factors.md
用法：python scripts/211_attention_shock_factors.py
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

from harness.lib.event_study import bootstrap_ci, forward_stats  # noqa: E402

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

REPORT = PROJECT_ROOT / "reports" / "attention_shock_factors.md"
GTRENDS = PROJECT_ROOT / "reports" / "free_sources_gtrends_weekly.csv"
FNG = PROJECT_ROOT / "reports" / "free_sources_gtrends_daily.csv"  # 见下
FNG_ALT = PROJECT_ROOT / "data" / "fear_greed_index.csv" if False else None
MACRO = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
MIN_DAYS = 60
SEED = 2026
HORIZONS = (24, 72, 168)


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    fundings = m113.load_funding_series(symbols)
    ev_parts = []
    for sym, ctx in ctxs.items():
        ev = m115.detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    ev_day = pd.to_datetime(events["timestamp"], unit="ms", utc=True).dt.floor("D")
    events = events.assign(ev_day=ev_day)
    print(f"wash_cvd 事件 {len(events)} | 独立事件日 {events['ev_day'].nunique()}")

    lines = ["# 注意力-情绪背离 + 本地-全球冲击（211，因子 7/8）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n"]

    # ---------- 因子 8：本地-全球冲击 ----------
    vix_p = MACRO / "VIX.parquet"
    if vix_p.exists() and len(ctxs):
        vix = pd.read_parquet(vix_p)
        vix_s = pd.Series(pd.to_numeric(vix["close"], errors="coerce").to_numpy(),
                          index=pd.DatetimeIndex(vix.index).tz_localize("UTC")).sort_index()
        # alt 横截面：24h realized vol 中位数（日度） + breadth 压力（washout 广度代理：24h 跌幅 <-8% 的币占比）
        rv_list, brd_list = [], []
        for sym, ctx in ctxs.items():
            c = ctx["close"].to_numpy(dtype=float)
            ret24 = np.full(len(c), np.nan)
            ret24[24:] = c[24:] / c[:-24] - 1.0
            s = pd.Series(ret24 * 100, index=pd.to_datetime(ctx.index, unit="ms", utc=True))
            rv_list.append(s.abs().resample("D").mean())
            brd_list.append((s < -8.0).resample("D").mean())
        rv = pd.concat(rv_list, axis=1).median(axis=1)
        brd = pd.concat(brd_list, axis=1).mean(axis=1)
        local = (rv / rv.rolling(30, min_periods=15).std().replace(0, np.nan)
                 + 2.0 * brd)  # 本地压力合成：波动抬升 + 广度恶化
        lz = (local - local.rolling(30, min_periods=15).mean()) / local.rolling(30, min_periods=15).std().replace(0, np.nan)
        vz = (vix_s - vix_s.rolling(30, min_periods=15).mean()) / vix_s.rolling(30, min_periods=15).std().replace(0, np.nan)
        both_idx = lz.index.intersection(vz.index)
        local_shock = (lz - vz).reindex(both_idx)
        # 事件日-1 asof
        ev_f8 = events.copy()
        prev = ev_day - pd.Timedelta(days=1)
        ev_f8["score"] = local_shock.reindex(prev).to_numpy()
        sub = ev_f8.dropna(subset=["score"]).copy()
        fwd_parts = []
        for sym, g in sub.groupby("symbol", sort=False):
            fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=HORIZONS))
        sub = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else sub
        sub["tercile"] = pd.qcut(sub["score"], 3, labels=[0, 1, 2], duplicates="drop")
        hi, lo = sub[sub["tercile"] == 2], sub[sub["tercile"] == 0]
        n_days = sub["ev_day"].nunique()
        lines.append("## 因子 8：本地-全球冲击（score = z(本地压力) − z(VIX)）\n")
        lines.append("| 层 | n | 独立日 | 24h 均值 | 72h 均值 | 168h 均值 |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for label, g in [("本地冲击高（T3）", hi), ("本地冲击低（T1）", lo)]:
            cells = []
            for h in HORIZONS:
                v = pd.to_numeric(g[f"ret_{h}h"], errors="coerce").dropna()
                cells.append(f"{v.mean():+.2f}%（n={len(v)}）")
            lines.append(f"| {label} | {len(g)} | {g['ev_day'].nunique()} | {' | '.join(cells)} |")
        v_hi = pd.to_numeric(hi["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
        v_lo = pd.to_numeric(lo["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
        if len(v_hi) >= MIN_DAYS and len(v_lo) >= MIN_DAYS:
            ci = bootstrap_ci(v_hi, v_lo, seed=SEED)
            lines.append(f"\n高−低 24h：{ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]"
                         f"（独立日 {n_days}）")
            print(f"[211] 因子8 高−低 {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")
        else:
            lines.append(f"\n样本不足（{len(v_hi)}/{len(v_lo)}，独立日 {n_days}）")

    # ---------- 因子 7：注意力-情绪背离 ----------
    gtrends_p = GTRENDS
    fng_p = MACRO / "fear_greed_index.csv"
    if gtrends_p.exists() and fng_p.exists():
        gt = pd.read_csv(gtrends_p)
        gt["date"] = pd.to_datetime(gt["date"], utc=True)
        gt["bitcoin"] = pd.to_numeric(gt["bitcoin"], errors="coerce")
        gt = gt.dropna(subset=["bitcoin"]).set_index("date")["bitcoin"]
        gt_z = (gt - gt.rolling(52, min_periods=20).mean()) / gt.rolling(52, min_periods=20).std().replace(0, np.nan)
        # BTC 日收益（coinglass klines）
        btc_kl = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
        btc = pd.read_parquet(btc_kl)
        btc_c = pd.Series(pd.to_numeric(btc["close"], errors="coerce").to_numpy(),
                          index=pd.to_datetime(pd.to_numeric(btc["open_time"], errors="coerce"), unit="ms", utc=True))
        btc_d = btc_c.resample("D").last().pct_change().abs() * 100
        btc_z = (btc_d - btc_d.rolling(30, min_periods=15).mean()) / btc_d.rolling(30, min_periods=15).std().replace(0, np.nan)
        # attention_resid：趋势 z − 价格冲击 z（周频 → 日频展平，当周 asof）
        att_resid = (gt_z - btc_z.resample("W").mean().reindex(gt_z.index).ffill())
        att_resid = att_resid.reindex(btc_z.index).ffill()
        fng = pd.read_csv(fng_p)
        fng["date"] = pd.to_datetime(fng["date"], utc=True) if "date" in fng.columns else pd.to_datetime(fng.iloc[:, 0], utc=True)
        fng_v = pd.to_numeric(fng.iloc[:, 1], errors="coerce") if fng.shape[1] > 1 else None
        if fng_v is not None:
            fng_s = pd.Series(fng_v.to_numpy(), index=fng["date"]).sort_index()
            prev = ev_day - pd.Timedelta(days=1)
            events7 = events.copy()
            events7["att"] = att_resid.reindex(prev).to_numpy()
            events7["fng"] = fng_s.reindex(prev).to_numpy()
            sub7 = events7.dropna(subset=["att", "fng"]).copy()
            fwd7 = []
            for sym, g in sub7.groupby("symbol", sort=False):
                fwd7.append(forward_stats(ctxs[sym], g.copy(), horizons=HORIZONS))
            sub7 = pd.concat(fwd7, ignore_index=True) if fwd7 else sub7
            combo = sub7[(sub7["att"] > sub7["att"].median()) & (sub7["fng"] >= 60)]
            fng_only = sub7[sub7["fng"] >= 60]
            rest = sub7[~((sub7["att"] > sub7["att"].median()) & (sub7["fng"] >= 60))]
            lines.append("\n## 因子 7：注意力-情绪背离（attention_resid 高 + F&G≥60）\n")
            lines.append("| 组 | n | 独立日 | 24h 均值 | 72h 均值 | 168h 均值 |")
            lines.append("|---|---|---:|---:|---:|---:|")
            for label, g in [("组合（att高+F&G≥60）", combo), ("F&G≥60（对照）", fng_only), ("其余", rest)]:
                cells = []
                for h in HORIZONS:
                    v = pd.to_numeric(g[f"ret_{h}h"], errors="coerce").dropna()
                    cells.append(f"{v.mean():+.2f}%（n={len(v)}）")
                lines.append(f"| {label} | {len(g)} | {g['ev_day'].nunique()} | {' | '.join(cells)} |")
            v_c = pd.to_numeric(combo["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
            v_f = pd.to_numeric(fng_only["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
            if len(v_c) >= MIN_DAYS and len(v_f) >= MIN_DAYS:
                ci = bootstrap_ci(v_c, v_f, seed=SEED)
                lines.append(f"\n组合−F&G-only 24h：{ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]"
                             f"（attention 的 marginal）")
                print(f"[211] 因子7 marginal {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")
            else:
                lines.append(f"\n样本不足（{len(v_c)}/{len(v_f)}）")
        else:
            lines.append("\n## 因子 7：F&G 列解析失败（fear_greed_index.csv 结构未知），本轮跳过。")
    else:
        lines.append("\n## 因子 7：数据缺失（gtrends/fng 文件不存在）。")

    lines += ["\n## 解读\n",
              "- 因子 8：本地冲击高 vs 低显著（且控制 VIX 后仍成立）→ 加密内部清杠杆后反弹更容易；",
              "- CI 含 0 / 与 VIX 门控重叠 → 本地-全球分解无增量 → NO_GO。",
              "- 因子 7 待补（列结构核对）。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
