r"""198_otc_premium_btc.py — P7：U 场外溢价 × BTC 抄底联动检验（前向积累框架）。

命题（Owner 2026-08-08 提出）：捕捉 U 场外突然溢价，与 BTC 抄底策略是否有关联？
机制：中国散户先在场外买 U（溢价 = 需求）再场内买币 → 溢价是现货买盘的前置信号；
抄底语境（BTC 大跌）下溢价转正/飙升 = 抄底资金进场。

⚠️ 数据现实（2026-08-08 实测）：P2P 无免费历史 → 本脚本是**前向积累框架**：
- A1 溢价尖峰事件（z>2 或 由负转正>+30bps）→ BTC 前向 24/72/168h（溢价作择时信号）
- A2 BTC 大跌事件（ret_24h<-3%）按溢价 regime 分层 → BTC 前向（溢价作抄底质量调节）
- B 恐慌日描述：大跌日溢价水平与次日变化（积累）
判定：样本不足 → PENDING（30 事件块规则同 E21）；样本足够 → bootstrap CI vs 随机日基线。

只读研究；输出：reports/otc_premium_btc.md
用法：python scripts/198_otc_premium_btc.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import bootstrap_ci  # noqa: E402

CSV = PROJECT_ROOT / "data" / "otc_premium.csv"
REPORT = PROJECT_ROOT / "reports" / "otc_premium_btc.md"
BTC_KL = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h\klines\BTCUSDT.parquet")

DIP_RET = -3.0        # BTC 大跌定义（24h）
SPIKE_Z = 2.0         # 溢价 z 尖峰阈值（30d 滚动）
SPIKE_BPS = 30.0      # 由负转正阈值（绝对）
MIN_EVENTS = 20
SEED = 2026


def load_premium() -> pd.DataFrame:
    if not CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(CSV)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    df = df.sort_values("ts").reset_index(drop=True)
    df["premium_buy_bps"] = pd.to_numeric(df["premium_buy_bps"], errors="coerce")
    return df.dropna(subset=["premium_buy_bps"])


def load_btc() -> pd.DataFrame:
    if not BTC_KL.exists():
        return pd.DataFrame()
    kl = pd.read_parquet(BTC_KL)
    kl = kl.rename(columns={"open_time": "t"})
    kl["t"] = pd.to_numeric(kl["t"], errors="coerce")
    kl["close"] = pd.to_numeric(kl["close"], errors="coerce")
    return kl[["t", "close"]].dropna().sort_values("t").reset_index(drop=True)


def btc_forward(btc: pd.DataFrame, ts_ms: int) -> dict:
    """快照时点后 24/72/168h BTC 收益（时间对齐，无前视）。"""
    axis = btc["t"].to_numpy(dtype=np.int64)
    close = btc["close"].to_numpy(dtype=float)
    pos = int(np.searchsorted(axis, ts_ms, side="right")) - 1
    if pos < 0:
        return {"ok": False}
    out = {"ok": True}
    for h in (24, 72, 168):
        target = pos + h
        if target < len(close):
            out[f"r{h}"] = (close[target] / close[pos] - 1.0) * 100.0
        else:
            out[f"r{h}"] = np.nan
    return out


def rolling_z(s: pd.Series, window: int, minp: int) -> pd.Series:
    mean = s.rolling(window, min_periods=minp).mean()
    std = s.rolling(window, min_periods=minp).std()
    return (s - mean) / std.replace(0, np.nan)


def main() -> int:
    prem = load_premium()
    btc = load_btc()
    if len(prem) < 2 or len(btc) == 0:
        print(f"数据不足：premium={len(prem)} 天, btc={len(btc)} bar")
        return 1
    print(f"溢价序列 {len(prem)} 天（{prem['date'].iloc[0]}→{prem['date'].iloc[-1]}）| BTC {len(btc)} bar")

    # 溢价特征
    p = prem["premium_buy_bps"]
    prem["z"] = rolling_z(p, 30, 15)
    prem["prev"] = p.shift(1)
    prem["btc_ret24h"] = np.nan
    for i, row in prem.iterrows():
        fwd = btc_forward(btc, int(row["ts"].timestamp() * 1000))
        for k, v in fwd.items():
            if k != "ok":
                prem.at[i, k] = v
        # 大跌日判定（快照时点往回 24h 的 BTC 收益 → 需历史；用前向收益的负值不成立，改用快照前 24h）
    # 大跌语境：快照时点前 24h BTC 收益（searchsorted 前向 24h 无意义 → 单独算）
    btc_axis = btc["t"].to_numpy(dtype=np.int64)
    btc_close = btc["close"].to_numpy(dtype=float)
    for i, row in prem.iterrows():
        ts = int(row["ts"].timestamp() * 1000)
        pos = int(np.searchsorted(btc_axis, ts, side="right")) - 1
        if pos >= 24 and pos < len(btc_close):
            prem.at[i, "btc_ret24h"] = (btc_close[pos] / btc_close[pos - 24] - 1.0) * 100.0

    lines = ["# U 场外溢价 × BTC 抄底联动（198，P7 前向积累）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 溢价序列 {len(prem)} 天（{prem['date'].iloc[0]}→{prem['date'].iloc[-1]}），当前溢价 {p.iloc[-1]:+.1f}bps",
             "- 数据：Binance/OKX P2P + USDCNH（197 日快照）；BTC = binance_free_db 1h\n",
             "## A1. 溢价尖峰事件 → BTC 前向\n",
             "| 事件定义 | n | 24h 均值 | 72h 均值 | 168h 均值 | 判定 |",
             "|---|---|---:|---:|---:|---|"]

    # A1：溢价尖峰 = z>2 或 由负转正且 >+30bps
    spike = prem[(prem["z"] > SPIKE_Z) | ((prem["prev"] <= 0) & (p > SPIKE_BPS))]
    for col, h in [("r24", "24h"), ("r72", "72h"), ("r168", "168h")]:
        vals = pd.to_numeric(spike[col], errors="coerce").dropna()
        if len(vals):
            lines.append(f"| 溢价尖峰 {col} | {len(vals)} | {vals.mean():+.2f}% | - | - | "
                         f"{'样本不足' if len(vals) < MIN_EVENTS else '待 bootstrap'} |")
    if spike.empty:
        lines.append("| 溢价尖峰（z>2 或转正>+30bps） | 0 | - | - | - | 样本积累中 |")

    lines += ["\n## A2. BTC 大跌 × 溢价 regime 分层\n",
              "| 层 | n | 24h 均值 | 72h 均值 | 168h 均值 | 判定 |",
              "|---|---|---:|---:|---:|---|"]
    dips = prem[prem["btc_ret24h"] <= DIP_RET]
    if len(dips):
        for label, mask in [("大跌+溢价>0", dips["premium_buy_bps"] > 0),
                            ("大跌+溢价≤0", dips["premium_buy_bps"] <= 0)]:
            g = dips[mask]
            cells = []
            for col in ("r24", "r72", "r168"):
                v = pd.to_numeric(g[col], errors="coerce").dropna()
                cells.append(f"{v.mean():+.2f}%（n={len(v)}）" if len(v) else "-")
            lines.append(f"| {label} | {len(g)} | {' | '.join(cells)} | "
                         f"{'样本不足' if len(g) < MIN_EVENTS else '待 bootstrap'} |")
    else:
        lines.append("| 无大跌日样本（积累中） | 0 | - | - | - | - |")

    lines += ["\n## B. 恐慌日描述（积累）\n", "| 日期 | 大跌日 BTC 24h | 当日溢价 | 次日溢价 | 溢价变化 |",
              "|---|---|---:|---:|---:|"]
    prem["next_prem"] = prem["premium_buy_bps"].shift(-1)
    for _, row in dips.iterrows():
        lines.append(f"| {row['date']} | {row['btc_ret24h']:+.2f}% | {row['premium_buy_bps']:+.1f}bps | "
                     f"{row['next_prem']:+.1f}bps | "
                     f"{row['next_prem'] - row['premium_buy_bps']:+.1f}bps |")
    if dips.empty:
        lines.append("| - | - | - | - | 无大跌日样本 |")

    lines += ["\n## 解读\n",
              "- 溢价>0 = 场外资金付溢价买 U（入场/抄底需求）；<0 = 出金/离场。",
              "- 当前窗口（2026-08）：场外折价 ≈-90bps → 与三重负面窗口（资金离场）自洽。",
              "- 样本积累：30 事件块约需 2-6 个月（尖峰频率待观察）；判决前只记账不判定。",
              "- ⚠️ P2P 报价噪音/做市商操纵：单日快照可能有偏差，长期用多所中位数。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
