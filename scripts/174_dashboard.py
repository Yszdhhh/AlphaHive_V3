"""174_dashboard.py — 可视化看板 MVP：虚拟交易净值 + BTC 周期 + 宏观面板。

OpenBB 集成第一步：本地数据 → matplotlib 图（PNG 输出 reports/dashboard/）。
后续可把本地数据注册为 OpenBB custom provider（obb 统一调用 + charting）。

面板：
1. 四账户净值曲线（A 统计 / B 风控 / C 确认 / D 新币）
2. BTC 价格 + Mayer Multiple（周期状态，164/166 门控依据）
3. 宏观近 90 天（VIX/SP500，本地 macro parquet）

用法：python scripts/174_dashboard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

REPORTS = PROJECT_ROOT / "reports"
OUT_DIR = REPORTS / "dashboard"
MACRO = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
COINGLASS = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")


def load_equity() -> dict[str, pd.Series]:
    out = {}
    for name in ["A", "B", "C", "D"]:
        p = REPORTS / f"paper_equity_{name}.csv"
        if p.exists():
            s = pd.read_csv(p)["equity"]
            out[name] = s
    return out


def load_btc() -> tuple[pd.Series, pd.Series]:
    p = COINGLASS / "klines" / "BTCUSDT.parquet"
    df = pd.read_parquet(p, columns=["open_time", "close"])
    ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    cl = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
    s = pd.Series(cl, index=pd.to_datetime(ts, unit="ms", utc=True).tz_localize(None).normalize())
    s = s[~s.index.duplicated(keep="last")].sort_index()
    daily = s.groupby(s.index).last()
    ma200 = daily.rolling(200, min_periods=120).mean()
    mayer = daily / ma200.replace(0, np.nan)
    return daily, mayer


def load_macro() -> dict[str, pd.Series]:
    out = {}
    for name, fname in [("VIX", "VIX.parquet"), ("SP500", "SP500.parquet")]:
        p = MACRO / fname
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p)
            date_col = "date" if "date" in df.columns else df.columns[0]
            val_col = [c for c in df.columns if c not in ("date", "index")][0]
            s = pd.Series(pd.to_numeric(df[val_col], errors="coerce").to_numpy(),
                          index=pd.to_datetime(df[date_col]))
            out[name] = s.dropna()
        except Exception:
            continue
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    eq = load_equity()
    btc, mayer = load_btc()
    macro = load_macro()

    # OpenBB FRED 双源（VIX/SP500 对照本地；失败则跳过）
    fred = {}
    try:
        sys.path.insert(0, r"G:\openbb\.venv\Lib\site-packages")
        from openbb import obb
        d = obb.economy.fred_series("VIXCLS", provider="fred", start_date="2025-01-01")
        if d.results:
            fred["VIX_fred"] = pd.Series(
                [r.VIXCLS for r in d.results],
                index=pd.to_datetime([r.date for r in d.results]))
    except Exception as exc:
        print(f"[174] OpenBB FRED 跳过: {exc}")

    fig, axes = plt.subplots(4, 1, figsize=(12, 13), dpi=110)

    # 1. 净值
    ax = axes[0]
    for name, s in eq.items():
        ax.plot(range(len(s)), s.to_numpy(), label=f"账户 {name}", linewidth=1.5)
    ax.set_title("AlphaHive V3 虚拟交易净值（四账户）")
    ax.set_ylabel("equity")
    ax.legend()
    ax.grid(alpha=0.3)

    # 2. BTC + Mayer
    ax = axes[1]
    ax2 = ax.twinx()
    ax.plot(btc.index[-365:], btc.to_numpy()[-365:], color="#333", linewidth=1, label="BTC")
    ax2.plot(mayer.index[-365:], mayer.to_numpy()[-365:], color="#c44", linewidth=1, label="Mayer")
    ax2.axhline(0.8, color="#4a4", ls="--", lw=0.8, label="熊市线 0.8")
    ax2.axhline(1.5, color="#a44", ls="--", lw=0.8, label="牛市线 1.5")
    ax.set_title("BTC 价格 + Mayer Multiple（近 365 天，周期门控依据）")
    ax.legend(loc="upper left")
    ax2.legend(loc="upper right")
    ax.grid(alpha=0.3)

    # 3. 宏观（本地 + OpenBB FRED 对照）
    ax = axes[2]
    for name, s in macro.items():
        s90 = s[s.index >= (pd.Timestamp.now() - pd.Timedelta(days=90))]
        ax.plot(s90.index, s90.to_numpy(), label=f"{name}(本地)", linewidth=1.2)
    for name, s in fred.items():
        s90 = s[s.index >= (pd.Timestamp.now() - pd.Timedelta(days=90))]
        ax.plot(s90.index, s90.to_numpy(), ls="--", label=f"{name}(OpenBB)", linewidth=1.2)
    ax.set_title("宏观近 90 天（本地 + OpenBB FRED 双源）")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # 4. 幸存者偏差标注区（当前 universe 状态）
    ax = axes[3]
    ax.axis("off")
    info = [
        "AlphaHive V3 状态面板",
        f"D 账户：净盈亏 ${_d_pnl():+.0f}（{_d_n()} 笔）| 胜率 {_d_win():.0f}%",
        f"KITE carry：{_kite()}",
        f"CEX-DEX 最新价差：{_spread()}bps",
        "⚠️ 幸存者偏差：历史 universe 仅含活跃币（124/124），下架币 washout 表现未计入——历史 edge 可能高估，前向验证为准",
    ]
    ax.text(0.02, 0.95, "\n".join(info), va="top", fontsize=10, family="monospace")

    fig.tight_layout()
    out = OUT_DIR / "dashboard.png"
    fig.savefig(out)
    print(f"[174] wrote {out}")
    return 0


def _d_pnl() -> float:
    p = REPORTS / "paper_positions_D.csv"
    if not p.exists():
        return 0.0
    return float(pd.read_csv(p)["pnl_net"].sum())


def _d_n() -> int:
    p = REPORTS / "paper_positions_D.csv"
    if not p.exists():
        return 0
    return len(pd.read_csv(p))


def _d_win() -> float:
    p = REPORTS / "paper_positions_D.csv"
    if not p.exists():
        return 0.0
    df = pd.read_csv(p)
    return 100 * (df["pnl_net"] > 0).mean()


def _kite() -> str:
    p = REPORTS / "kite_carry.csv"
    if not p.exists():
        return "未启动"
    df = pd.read_csv(p)
    return f"funding {df.funding_ann_pct.iloc[-1]:+.1f}%/yr"


def _spread() -> float:
    p = REPORTS / "cex_dex_spread.csv"
    if not p.exists():
        return float("nan")
    return float(pd.read_csv(p).spread_bps.iloc[-1])


if __name__ == "__main__":
    raise SystemExit(main())
