"""114_funding_timing_test.py — 市场级 funding 定时信号测试。

背景：112 显示 funding-reset 作为【横截面选择器】无 edge（超额≈0）。但用户的命题
"大饼见底→山寨蓄力"本质是【择时】——该不该在这个窗口做多山寨篮子，而不是选哪个币。
本脚本区分这两个问题：测**市场级 funding 深负是否预示山寨篮子绝对收益更高**。

设计：
- funding 对齐到 1h（asof，gap cap 9h），每 bar 取横截面 median funding 当"市场费率"。
- fund_reset = median_funding < -0.0002（深负窗口）。
- 每 episode 随机采样 M 个 1h 时点，计算等权山寨篮子 forward 4/24/72/168h 收益
  （篮子 = 该时点有价格的所有 universe 币均值，避免幸存者偏差用当日可得集）。
- 比较 fund_reset ON vs OFF 的篮子绝对收益（含手续费前；择时层面先看方向）。
- 另报"持有比例"：fund_reset 在每 episode 的时长占比——择时信号可交易的频度。

输出：reports/funding_timing_test.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

COINGLASS_KLINES = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h\klines")
FUNDING_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
REPORTS_DIR = PROJECT_ROOT / "reports"

BASE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
HOUR_MS = 3_600_000
FUND_GAP_MS = 9 * HOUR_MS
FUND_RESET_THRESHOLD = -0.0002
MIN_BASKET = 5  # 篮子最少币数

EPISODES = [
    ("2022熊底+FTX底", "2022-01-01", "2023-01-31"),
    ("2023平台蓄力",    "2023-02-01", "2024-05-31"),
    ("2024崩→恢复",    "2024-06-01", "2025-01-31"),
    ("2025顶→熊",      "2025-02-01", "2026-06-30"),
    ("当前筑底(前向)",  "2026-07-01", "2030-01-01"),
]


def load_universe_symbols() -> list[str]:
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = json.load(f)["symbols"]
    return [item["symbol"] for item in universe if item["symbol"] not in BASE_SYMBOLS]


def load_price_tables(symbols: list[str]) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    for s in symbols:
        p = COINGLASS_KLINES / f"{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if "open_time" not in df.columns or "close" not in df.columns:
            continue
        close = pd.to_numeric(df["close"], errors="coerce")
        ts = pd.to_numeric(df["open_time"], errors="coerce")
        t = pd.DataFrame({"close": close.to_numpy(dtype=float)},
                         index=pd.Index(ts.to_numpy(dtype=np.int64), name="timestamp"))
        t = t[~t.index.duplicated(keep="last")].sort_index()
        t = t.replace([np.inf, -np.inf], np.nan).dropna(subset=["close"])
        med = t["close"].rolling(720, min_periods=360).median()
        ratio = t["close"] / med.replace(0, pd.NA)
        t["close"] = t["close"].where((ratio >= 0.02) & (ratio <= 50.0))
        tables[s] = t
    return tables


def load_funding_series(symbols: list[str]) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for s in symbols:
        p = FUNDING_DIR / f"{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        ts = pd.to_numeric(df["fundingTime"], errors="coerce")
        rate = pd.to_numeric(df["fundingRate"], errors="coerce")
        if len(ts) == 0:
            continue
        out[s] = pd.Series(rate.to_numpy(dtype=float), index=pd.Index(ts.to_numpy(dtype=np.int64)))
    return out


def funding_on_axis(fund_series: pd.Series, axis_ts: np.ndarray) -> np.ndarray:
    idx = pd.Index(axis_ts)
    pos = np.searchsorted(fund_series.index.to_numpy(), idx.to_numpy(), side="right") - 1
    fts = fund_series.index.to_numpy()
    fval = fund_series.to_numpy()
    out = np.full(len(axis_ts), np.nan)
    valid = pos >= 0
    out[valid] = fval[pos[valid]]
    out[valid & ((idx.to_numpy() - fts[pos]) >= FUND_GAP_MS)] = np.nan
    return out


def _basket_fwd(ts: int, tables: dict[str, pd.DataFrame], h_hours: int) -> float | None:
    """等权篮子 forward h 收益（%）。该时点有价格的币取均值；<MIN_BASKET 返回 None。"""
    rets: list[float] = []
    for sym, t in tables.items():
        arr = t.index.to_numpy()
        pos = np.searchsorted(arr, ts, side="right") - 1
        if pos < 0:
            continue
        base_ts = int(arr[pos])
        if base_ts != ts:  # 要求时点恰有 bar（无前视，asof 到自身）
            continue
        base = t["close"].iloc[pos]
        target = ts + h_hours * HOUR_MS
        tpos = np.searchsorted(arr, target, side="right") - 1
        if tpos <= pos:
            continue
        fts_ = int(arr[tpos])
        if fts_ > target or (target - fts_) >= 2 * HOUR_MS:
            continue
        f = t["close"].iloc[tpos]
        if not np.isfinite(base) or base <= 0 or not np.isfinite(f):
            continue
        rets.append((f / base - 1.0) * 100.0)
    if len(rets) < MIN_BASKET:
        return None
    return float(np.mean(rets))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-sample", type=int, default=3000, help="每 episode 采样时点数")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    tables = load_price_tables(symbols)
    fundings = load_funding_series(symbols)
    print(f"价格表 {len(tables)} | funding {len(fundings)}")

    rng = np.random.default_rng(args.seed)
    horizons = [4, 24, 72, 168]

    lines: list[str] = []
    lines.append("# 市场级 funding 定时信号测试\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- fund_reset = 横截面 median funding < {FUND_RESET_THRESHOLD}")
    lines.append(f"- 篮子 = 该时点有价格的全 universe 等权（≥{MIN_BASKET} 币），手续费前")
    lines.append("- 比较 fund_reset ON vs OFF 时点的篮子 forward 收益（择时层面）")
    lines.append("> 区分于 112：112 测【选哪个币】，本脚本测【这个窗口值不值得做多篮子】。\n")

    for name, s, e in EPISODES:
        start_ms = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
        end_ms = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
        # 该 episode 内所有可能时点
        all_ts: list[int] = []
        for sym, t in tables.items():
            arr = t.index.to_numpy()
            sub = arr[(arr >= start_ms) & (arr <= end_ms)]
            if len(sub):
                all_ts.extend(sub.tolist())
        if not all_ts:
            lines.append(f"\n## {name} — 无数据\n")
            continue
        pool = np.array(sorted(set(all_ts)))
        # 市场 funding 状态：横截面 median funding（向量化矩阵）
        fund_syms = list(fundings.keys())
        fund_matrix = np.full((len(pool), len(fund_syms)), np.nan)
        for j, sym in enumerate(fund_syms):
            fund_matrix[:, j] = funding_on_axis(fundings[sym], pool)
        median_fund = np.nanmedian(fund_matrix, axis=1)
        fund_state = median_fund < FUND_RESET_THRESHOLD
        on_ts = pool[fund_state].tolist()
        off_ts = pool[~fund_state].tolist()
        coverage = 100.0 * len(on_ts) / len(pool) if len(pool) else np.nan

        # 采样比较
        n_on = max(int(args.n_sample * max(coverage, 0.02) / 100.0), 200) if on_ts else 0
        n_off = max(int(args.n_sample * max(100.0 - coverage, 0.02) / 100.0), 200) if off_ts else 0
        samp_on = rng.choice(np.array(on_ts), size=min(n_on, len(on_ts)), replace=False) if on_ts else np.array([], dtype=np.int64)
        samp_off = rng.choice(np.array(off_ts), size=min(n_off, len(off_ts)), replace=False) if off_ts else np.array([], dtype=np.int64)

        lines.append(f"\n## {name}\n")
        lines.append(f"- fund_reset 时长占比: {coverage:.1f}%  (ON 时点数 {len(on_ts)}/{len(pool)})")
        lines.append(f"- 采样: ON {len(samp_on)} 个时点, OFF {len(samp_off)} 个时点\n")
        lines.append("| horizon | ON 篮子均收益 | OFF 篮子均收益 | 差 | n(ON/OFF) |")
        lines.append("|---|---|---|---|---|")
        for h in horizons:
            on_r = [r for r in (_basket_fwd(int(ts), tables, h) for ts in samp_on) if r is not None]
            off_r = [r for r in (_basket_fwd(int(ts), tables, h) for ts in samp_off) if r is not None]
            on_m = float(np.mean(on_r)) if on_r else np.nan
            off_m = float(np.mean(off_r)) if off_r else np.nan
            lines.append(f"| {h}h | {on_m:+.2f}% | {off_m:+.2f}% | {on_m-off_m:+.2f}% | {len(on_r)}/{len(off_r)} |")

    out = REPORTS_DIR / "funding_timing_test.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
