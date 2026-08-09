r"""144_chain_assets_washout.py — 全市场交叉验证：washout 事件在链上传统资产上是否成立。

背景：wash_cvd 的唯一验证 edge 在加密山寨（washout=price_z<-2 或 ret_24h<-8%，砸坑后
反弹）。用户要求把方法论迁移到链上传统资产（Pyth 喂价的永续/合成资产：美股、指数、
黄金白银、外汇）。本脚本做**纯 washout 形态**事件研究（Pyth 无 taker/CVD 维度，
诚实标注：无"卖压枯竭"确认，只测价格形态层）。

数据（Pyth Benchmarks TradingView shim，免费，缓存到 data/pyth_raw/）：
- METAL.XAU/USD 黄金 / METAL.XAG/USD 白银 / FX.GBP/USD 英镑：24/7 连续，与加密同构
- EQUITY.US.SPY/USD / EQUITY.US.QQQ/USD / EQUITY.US.NVDA/USD：仅美盘时段（隔夜无数据）
  → ret_24h = 24 根美盘小时 ≈ 跨 3 个交易日，跳空结构直接可见，报告如实标注。

方法（复用 event_study.py 框架，但基线改为单资产时间随机点，因为无横截面）：
- 事件：price_z<-2 或 ret_24h<-8%（720h rolling z，同 115 口径），72h 冷却
- 基线：同资产同区间随机时间点前向收益，bootstrap 95% CI（seed=2026，n=3000）
- 判定：CI 下界>0→GO_LONG / 上界<0→GO_SHORT / 含0→NO_GO / n<30→样本不足
- 对照：加密 wash_cvd pooled 24h +1.31% CI[+0.66,+1.63]（115）

输出：reports/chain_assets_washout.md
用法：python scripts/144_chain_assets_washout.py [--n-baseline 3000] [--seed 2026]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import bootstrap_ci  # noqa: E402

DATA_DIR = PROJECT_ROOT / "data" / "pyth_raw"
REPORT = PROJECT_ROOT / "reports" / "chain_assets_washout.md"
PYTH_URL = "https://benchmarks.pyth.network/v1/shims/tradingview/history"
START_TS = int(pd.Timestamp("2022-06-01", tz="UTC").timestamp())
HOUR_MS = 3_600_000
COOLDOWN_H = 72
WASH_Z = -2.0
WASH_RET = -8.0

ASSETS = {
    "METAL.XAU/USD": ("黄金 XAU", "24/7"),
    "METAL.XAG/USD": ("白银 XAG", "24/7"),
    "FX.GBP/USD": ("英镑 GBP", "24/7"),
    "EQUITY.US.SPY/USD": ("标普 SPY", "美盘"),
    "EQUITY.US.QQQ/USD": ("纳指 QQQ", "美盘"),
    "EQUITY.US.NVDA/USD": ("英伟达 NVDA", "美盘"),
    "EQUITY.US.TSLA/USD": ("特斯拉 TSLA", "美盘"),
    "EQUITY.US.MSTR/USD": ("微策略 MSTR", "美盘"),
    "EQUITY.US.COIN/USD": ("Coinbase COIN", "美盘"),
    "EQUITY.US.AMD/USD": ("AMD", "美盘"),
    "EQUITY.US.MU/USD": ("美光 MU", "美盘"),
    "EQUITY.US.STX/USD": ("希捷 STX", "美盘"),
    "EQUITY.US.WDC/USD": ("西部数据 WDC", "美盘"),
    "EQUITY.US.AVGO/USD": ("博通 AVGO", "美盘"),
    "EQUITY.US.TSM/USD": ("台积电 TSM", "美盘"),
    "EQUITY.US.ASML/USD": ("ASML", "美盘"),
}

# 加密对照（115 wash_cvd pooled）
CRYPTO_REF = ("+1.31%", "[+0.66, +1.63]", 1348)


def fetch_symbol(sym: str) -> pd.DataFrame:
    """Pyth 全历史（2022-01-01 起），60 天分段拉取防单次条数上限，合并去重。"""
    cache = DATA_DIR / f"{sym.replace('/', '_')}.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        last = int(df["t"].max())
        if last >= int(pd.Timestamp.now(tz="UTC").timestamp()) - 3 * 86400:
            return df
        start = last + 3600
    else:
        df = pd.DataFrame()
        start = START_TS
    chunks = []
    while start < int(pd.Timestamp.now(tz="UTC").timestamp()):
        end = min(start + 90 * 86400, int(pd.Timestamp.now(tz="UTC").timestamp()))
        url = (f"{PYTH_URL}?symbol={sym}&resolution=60&from={start}&to={end}")
        ok = False
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.loads(r.read())
                ok = True
                break
            except Exception as exc:
                print(f"  [fetch] {sym} {start}→{end} attempt{attempt + 1}: {exc}")
                time.sleep(30)  # 免费档限流窗口约 30-60s
        if not ok:
            start = end
            continue
        if not d.get("t"):
            start = end
            continue
        chunk = pd.DataFrame({"t": d["t"], "o": d["o"], "h": d["h"],
                              "l": d["l"], "c": d["c"], "v": d.get("v", [])})
        chunks.append(chunk)
        start = end
        if len(chunks) > 40:
            break
        time.sleep(1.5)
    if chunks:
        new = pd.concat(chunks, ignore_index=True).drop_duplicates(subset="t").sort_values("t")
        df = pd.concat([df, new], ignore_index=True).drop_duplicates(subset="t").sort_values("t")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache)
    return df


def detect_washout(ts: np.ndarray, close: np.ndarray) -> list[int]:
    """washout：price_z<-2 或 ret_24h<-8%（720h rolling z），72h 冷却。"""
    s = pd.Series(close)
    z = (s - s.rolling(720, min_periods=360).mean()) / s.rolling(720, min_periods=360).std().replace(0, np.nan)
    ret24 = s.pct_change(24) * 100.0
    fired = np.isfinite(z.to_numpy()) & np.isfinite(ret24.to_numpy()) & \
        ((z.to_numpy() < WASH_Z) | (ret24.to_numpy() < WASH_RET))
    events: list[int] = []
    last = -10**18
    # ⚠️ Pyth TradingView shim 的 t 是【秒】单位（非毫秒）：冷却按秒算
    cooldown_s = COOLDOWN_H * 3600
    for i in np.flatnonzero(fired):
        t = int(ts[i])
        if t - last >= cooldown_s:
            events.append(t)
            last = t
    return events


def forward_rets(ts: np.ndarray, close: np.ndarray, ev_ts: np.ndarray,
                 horizons: list[int]) -> pd.DataFrame:
    """每事件前向收益（按 bar 数），返回 DataFrame[ev_ts, ret_24h, ret_72h, ret_168h]。"""
    rows = []
    for t in ev_ts:
        pos = int(np.searchsorted(ts, t, side="right")) - 1
        if pos < 0 or pos + max(horizons) >= len(close):
            continue
        r = {"ev_ts": t}
        for h in horizons:
            r[f"ret_{h}h"] = (close[pos + h] / close[pos] - 1) * 100.0
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-baseline", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    lines = ["# 全市场交叉验证：washout 事件在链上传统资产（Pyth）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             "- 事件：washout（price_z<-2 或 ret_24h<-8%，720h rolling z，72h 冷却）——115 口径的价格形态层",
             "- 数据：Pyth Benchmarks（免费，2022-01 起，缓存 data/pyth_raw/）",
             "- 基线：单资产同区间随机时间点（bootstrap 95% CI，seed=2026）",
             "- 对照：加密 wash_cvd pooled 24h 超额 +1.31% CI[+0.66,+1.63]（n=1348，115）",
             f"- ⚠️ 无 CVD 维度（Pyth 无 taker 流）→ 只测价格形态，未含'卖压枯竭'确认\n",
             "| 资产 | 交易制 | 事件 n | 24h均值 | 24h超额 | 95% CI | 72h超额 | 168h超额 | 胜率 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    rng = np.random.default_rng(args.seed)

    for sym, (name, mode) in ASSETS.items():
        df = fetch_symbol(sym)
        if df.empty or len(df) < 800:
            lines.append(f"| {name} | {mode} | 数据不足 | - | - | - | - | - | - | - |")
            continue
        ts = df["t"].to_numpy(dtype=np.int64)
        close = df["c"].to_numpy(dtype=float)
        ev = detect_washout(ts, close)
        fwd = forward_rets(ts, close, np.array(ev, dtype=np.int64), [24, 72, 168])
        n = len(fwd)
        if n == 0:
            lines.append(f"| {name} | {mode} | 0 | - | - | - | - | - | - | 无事件 |")
            continue
        # 基线：同资产随机时间点（事件数×50 个，区间同事件跨度；单事件时用全区间）
        lo, hi = int(fwd["ev_ts"].min()), int(fwd["ev_ts"].max())
        if hi <= lo:
            lo, hi = int(ts.min()), int(ts.max())
        base_ev = np.sort(rng.integers(lo, hi + 1, size=max(args.n_baseline, n * 50), dtype=np.int64))
        base = forward_rets(ts, close, base_ev, [24, 72, 168])
        ci = bootstrap_ci(fwd["ret_24h"].to_numpy(), base["ret_24h"].to_numpy(),
                          n_boot=1000, alpha=0.05, seed=args.seed)
        win = float((fwd["ret_24h"] > 0).mean() * 100)
        verdict = ("样本不足" if n < 30 else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {name} | {mode} | {n} | {fwd['ret_24h'].mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {fwd['ret_72h'].mean():+.2f}% "
                     f"| {fwd['ret_168h'].mean():+.2f}% | {win:.0f}% | **{verdict}** |")
        print(f"[144] {name}: n={n} ex24={ci['mean_diff']:+.2f}% {verdict}")

    lines.extend(["\n## 解读要点\n",
                   "- 判定语义与加密一致：超额 vs 同资产随机基线；CI 跨零 = 无统计证据（不宣称证伪）。",
                   "- 美股/指数只有美盘小时数据：'24h' = 24 根美盘 bar ≈ 跨 3 个交易日；隔夜跳空含在 bar 间隙中，"
                   "事件检测用连续 bar 序列（跳空表现为 bar 间大 gap）。",
                   "- 黄金/白银/英镑为 24/7 连续市场，结构与加密最接近，结果可直接与 wash_cvd 对照。",
                   "- 无 CVD 维度：若某资产 washout 有正超额，下一步接 taker/CVD 数据（如加密平台永续）验证'卖压枯竭'层。",
                   "- 多重检验：6 资产 × 1 事件类型 = 6 次检验，属探索性；任一 GO 需独立样本复核才升级。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
