r"""223 — K 线还原：导出 CSV + 蜡烛图，方便可视化 / 策略对照。

依赖：pandas + matplotlib（已有）。
用法：
  python scripts/223_kline_view.py --symbol BTCUSDT --start 2026-01-01 --end 2026-08-01
  python scripts/223_kline_view.py --symbol ARBUSDT --days 90
  python scripts/223_kline_view.py --symbol ETHUSDT --days 30 --no-plot

产出（默认 reports/kline_views/）：
  {symbol}_{start}_{end}.csv
  {symbol}_{start}_{end}.png
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.klines_store import load_klines, resolve_path, to_datetime_index  # noqa: E402

OUT = PROJECT_ROOT / "reports" / "kline_views"


def plot_candles(df: pd.DataFrame, title: str, out_png: Path) -> None:
    """简易蜡烛图（不引入 plotly）。"""
    x = to_datetime_index(df)
    if len(x) == 0:
        raise ValueError("empty")
    # 过多 bar 时降采样到 ~800 根，否则图糊
    if len(x) > 900:
        step = int(np.ceil(len(x) / 800))
        x = x.iloc[::step]
    o, h, l, c = x["open"], x["high"], x["low"], x["close"]
    dates = mdates.date2num(x.index.to_pydatetime())
    fig, (ax, axv) = plt.subplots(
        2, 1, figsize=(14, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    width = 0.6 * (dates[1] - dates[0]) if len(dates) > 1 else 0.02
    up = c >= o
    for i in range(len(x)):
        color = "#26a69a" if up.iloc[i] else "#ef5350"
        ax.plot([dates[i], dates[i]], [l.iloc[i], h.iloc[i]], color=color, linewidth=0.8)
        bot = min(o.iloc[i], c.iloc[i])
        height = abs(c.iloc[i] - o.iloc[i]) or (h.iloc[i] - l.iloc[i]) * 0.001
        ax.add_patch(
            plt.Rectangle(
                (dates[i] - width / 2, bot),
                width,
                height,
                facecolor=color,
                edgecolor=color,
                alpha=0.9,
            )
        )
    ax.set_title(title)
    ax.set_ylabel("price")
    ax.grid(True, alpha=0.25)
    ax.xaxis_date()
    if "volume" in x.columns:
        colors = np.where(up, "#26a69a", "#ef5350")
        axv.bar(dates, x["volume"].to_numpy(), width=width, color=colors, alpha=0.7)
        axv.set_ylabel("vol")
    axv.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--days", type=int, default=0, help="若未给 start，用最近 N 天")
    ap.add_argument("--source", default="auto", choices=["auto", "binance_history", "binance_raw", "coinglass"])
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--out-dir", default=str(OUT))
    args = ap.parse_args()

    end = args.end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if args.start:
        start = args.start
    elif args.days > 0:
        start = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")
    else:
        start = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")

    src_path = resolve_path(args.symbol, args.source)  # type: ignore[arg-type]
    df = load_klines(args.symbol, source=args.source, start=start, end=end)  # type: ignore[arg-type]
    if len(df) == 0:
        print(f"no bars {args.symbol} {start}..{end} from {src_path}")
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.symbol}_{start}_{end}".replace(":", "")
    csv_path = out_dir / f"{tag}.csv"
    exp = df.copy()
    exp["datetime_utc"] = pd.to_datetime(exp["open_time"], unit="ms", utc=True)
    exp.to_csv(csv_path, index=False)
    print(f"source: {src_path}")
    print(f"bars: {len(df)}  {start} → {end}")
    print(f"csv: {csv_path}")

    if not args.no_plot:
        png = out_dir / f"{tag}.png"
        plot_candles(df, f"{args.symbol} 1h  {start} → {end}", png)
        print(f"png: {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
