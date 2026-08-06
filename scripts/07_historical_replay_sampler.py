"""Search historical scan times for enough candidate supply before materializing runs."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.turnover import turnover_24h_effective

RAW_1H = Path(r"C:\Users\10639\Desktop\加密\coinglass_db\raw_1h")
REPORTS_DIR = PROJECT_ROOT / "reports"


@dataclass
class SymbolData:
    symbol: str
    df: pd.DataFrame
    rank: int
    history_tier: str
    eligible_for_paper: str


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_kline(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    cols = [
        "open_time", "timestamp", "open", "high", "low", "close", "volume",
        "quote_volume", "volume_usd", "turnover_usd",
    ]
    out = df[[c for c in cols if c in df.columns]].copy()
    if "open_time" in out.columns:
        out = out.rename(columns={"open_time": "timestamp"})
    out["timestamp"] = pd.to_numeric(out["timestamp"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    turnover = pd.to_numeric(out["turnover_usd"], errors="coerce") if "turnover_usd" in out.columns else None
    if turnover is None or not turnover.notna().any():
        quote_volume = pd.to_numeric(out["quote_volume"], errors="coerce") if "quote_volume" in out.columns else None
        volume_usd = pd.to_numeric(out["volume_usd"], errors="coerce") if "volume_usd" in out.columns else None
        if quote_volume is not None and volume_usd is not None:
            turnover = quote_volume.fillna(volume_usd)
        elif quote_volume is not None:
            turnover = quote_volume
        elif volume_usd is not None:
            turnover = volume_usd
        else:
            turnover = pd.Series(pd.NA, index=out.index, dtype="Float64")
    out["turnover_usd"] = turnover
    out["symbol"] = symbol
    return out.sort_values("timestamp").reset_index(drop=True)


def load_symbol_data() -> tuple[list[SymbolData], pd.DataFrame]:
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = json.load(f)["symbols"]
    symbols = []
    for item in universe:
        path = RAW_1H / "klines" / f"{item['symbol']}.parquet"
        if not path.exists():
            continue
        df = normalize_kline(pd.read_parquet(path), item["symbol"])
        if len(df) >= 25:
            symbols.append(SymbolData(item["symbol"], df, item["rank"], item["history_tier"], item["eligible_for_paper"]))
    btc_path = RAW_1H / "klines" / "BTCUSDT.parquet"
    btc = normalize_kline(pd.read_parquet(btc_path), "BTCUSDT")
    return symbols, btc


def window_before(df: pd.DataFrame, scan_ms: int, lookback_hours: int) -> pd.DataFrame:
    return df[df["timestamp"] < scan_ms].tail(lookback_hours).copy()


def btc_return_24h(btc: pd.DataFrame, scan_ms: int, lookback_hours: int) -> float:
    w = window_before(btc, scan_ms, lookback_hours)
    if len(w) < 25:
        return 0.0
    return (float(w["close"].iloc[-1]) / float(w["close"].iloc[-25]) - 1.0) * 100.0


def candidates_at(scan_ts: pd.Timestamp, symbols: list[SymbolData], btc: pd.DataFrame, rules: dict) -> list[dict]:
    scan_ms = int(scan_ts.value / 1e6)
    lookback_hours = int(rules["quantile"]["lookback_days"]) * 24
    min_turnover = float(rules.get("baseline_pool", {}).get("min_effective_turnover_usd", 10_000_000))
    min_valid = int(rules.get("baseline_pool", {}).get("min_valid_turnover_bars_24h", 18))
    btc_ret = btc_return_24h(btc, scan_ms, lookback_hours)
    out = []
    for item in symbols:
        w = window_before(item.df, scan_ms, lookback_hours)
        if len(w) < 25:
            continue
        turnover = turnover_24h_effective(w, min_valid_bars=min_valid)
        if turnover.turnover_24h_usd_effective is None or turnover.turnover_24h_usd_effective < min_turnover:
            continue
        close = pd.to_numeric(w["close"], errors="coerce")
        if close.iloc[-25] == 0 or pd.isna(close.iloc[-25]) or pd.isna(close.iloc[-1]):
            continue
        ret_24h = (float(close.iloc[-1]) / float(close.iloc[-25]) - 1.0) * 100.0
        vol_24h = close.pct_change().rolling(24).std().dropna()
        if vol_24h.empty:
            continue
        latest_vol = float(vol_24h.iloc[-1])
        vol_quantile = float((vol_24h <= latest_vol).mean())
        excess = ret_24h - btc_ret
        triggers = []
        if vol_quantile >= float(rules["triggers"]["vol_quantile_high"]):
            triggers.append("vol_quantile_high")
        if abs(ret_24h) >= float(rules["large_move"]["large_move_threshold_abs_pct_24h"]):
            triggers.append("large_move_abs")
        if abs(excess) >= float(rules["large_move"]["large_move_threshold_excess_pct_24h"]):
            triggers.append("large_move_excess")
        if triggers:
            out.append({
                "symbol": item.symbol,
                "rank": item.rank,
                "turnover_24h_usd_effective": turnover.turnover_24h_usd_effective,
                "turnover_confidence": turnover.confidence,
                "trigger_reason": "|".join(triggers),
                "vol_quantile": vol_quantile,
                "abs_move_pct_24h": ret_24h,
                "excess_move_pct_24h": excess,
            })
    return sorted(out, key=lambda r: abs(r["excess_move_pct_24h"]), reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--freq_hours", type=int, default=6)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    rules = load_yaml(PROJECT_ROOT / "config" / "scan_rules.yaml")
    symbols, btc = load_symbol_data()
    times = pd.date_range(pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.end, tz="UTC"), freq=f"{args.freq_hours}h")
    rows = []
    details = {}
    for ts in times:
        cands = candidates_at(ts, symbols, btc, rules)
        unique = len({c["symbol"] for c in cands})
        rows.append({
            "scan_time_utc": ts.isoformat(),
            "candidate_count": len(cands),
            "candidate_unique": unique,
            "symbols": ",".join([c["symbol"] for c in cands[:20]]),
        })
        details[ts.isoformat()] = cands[:50]
    result = pd.DataFrame(rows).sort_values(["candidate_unique", "candidate_count"], ascending=False)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = REPORTS_DIR / "historical_replay_sampler.csv"
    out_json = REPORTS_DIR / "historical_replay_sampler_details.json"
    result.to_csv(out_csv, index=False)
    out_json.write_text(json.dumps(details, indent=2), encoding="utf-8")
    print(f"wrote {out_csv}")
    print(f"wrote {out_json}")
    print(result.head(args.top).to_string(index=False))


if __name__ == "__main__":
    main()
