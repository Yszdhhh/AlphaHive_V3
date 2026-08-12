r"""218 — 币安 USDT-M 1h klines 历史回补 + 并入 raw_1h。

问题：
- coinglass klines 停更于 2026-07-07（长历史）
- binance_free raw_1h/klines 仅约 2026-05-31 起（前向）
→ 研究/前向中间不断档，且 raw 过短无法单源回测

动作：
1. fapi /fapi/v1/klines 分页拉全历史 → history/klines/{SYM}.parquet
2. 与现有 raw_1h/klines 合并去重 → 写回 raw_1h（前向链直接变长）
3. 报告 reports/backfill_klines_218.md

用法：
  python scripts/218_backfill_binance_klines.py
  python scripts/218_backfill_binance_klines.py --symbols BTCUSDT,ETHUSDT
  python scripts/218_backfill_binance_klines.py --no-merge-raw   # 只写 history
  python scripts/218_backfill_binance_klines.py --max-symbols 20
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.data_registry import paths  # noqa: E402

# 与 data_paths 一致：无 emoji 的 binance_free
DB = Path(str(paths.binance_free.raw_1h)).parent  # .../binance_free_db
RAW_KL = Path(str(paths.binance_free.raw_1h)) / "klines"
HIST_KL = DB / "history" / "klines"
REPORT = PROJECT_ROOT / "reports" / "backfill_klines_218.md"

FAPI = "https://fapi.binance.com/fapi/v1/klines"
# 备用（部分网络）
FAPI_ALT = "https://www.binance.com/fapi/v1/klines"
START_MS = 1_577_836_800_000  # 2020-01-01
PAGE = 1000
SLEEP = 0.22
UA = {"User-Agent": "AlphaHive-V3/218-backfill"}

COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades",
    "taker_buy_vol", "taker_buy_quote_vol", "turnover_usd",
]


def load_symbols() -> list[str]:
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        uni = [x["symbol"] for x in json.load(f)["symbols"]]
    extra = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    if RAW_KL.exists():
        extra += [p.stem for p in RAW_KL.glob("*.parquet")]
    # 去重保序
    seen, out = set(), []
    for s in uni + extra:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _http_json(url: str) -> list:
    last: Exception | None = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 + attempt * 2)
    raise RuntimeError(str(last))


def fetch_klines(symbol: str, start_ms: int = START_MS) -> pd.DataFrame:
    """分页拉 1h klines，返回与 raw_1h 同构列。"""
    frames: list[pd.DataFrame] = []
    cur = start_ms
    base = FAPI
    for _ in range(500):
        url = f"{base}?symbol={symbol}&interval=1h&startTime={cur}&limit={PAGE}"
        try:
            batch = _http_json(url)
        except RuntimeError:
            if base == FAPI:
                base = FAPI_ALT
                continue
            raise
        if not batch:
            break
        rows = []
        for k in batch:
            rows.append(
                {
                    "open_time": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "close_time": int(k[6]),
                    "quote_volume": float(k[7]),
                    "trades": int(k[8]),
                    "taker_buy_vol": float(k[9]),
                    "taker_buy_quote_vol": float(k[10]),
                    "turnover_usd": float(k[7]),  # USDT-M quote ≈ usd
                }
            )
        frames.append(pd.DataFrame(rows))
        last_t = int(batch[-1][0])
        if len(batch) < PAGE:
            break
        cur = last_t + 3_600_000
        time.sleep(SLEEP)
    if not frames:
        return pd.DataFrame(columns=COLS)
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["open_time"], keep="last").sort_values("open_time")
    return df.reset_index(drop=True)


def merge_frames(a: pd.DataFrame | None, b: pd.DataFrame) -> pd.DataFrame:
    parts = [x for x in (a, b) if x is not None and len(x)]
    if not parts:
        return pd.DataFrame(columns=COLS)
    df = pd.concat(parts, ignore_index=True)
    df = df.drop_duplicates(subset=["open_time"], keep="last").sort_values("open_time")
    return df.reset_index(drop=True)


def load_existing(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:  # noqa: BLE001
        return None


def span(df: pd.DataFrame) -> str:
    if df is None or len(df) == 0:
        return "empty"
    t0 = int(df["open_time"].min())
    t1 = int(df["open_time"].max())
    return (
        f"{pd.Timestamp(t0, unit='ms', tz='UTC'):%Y-%m-%d} → "
        f"{pd.Timestamp(t1, unit='ms', tz='UTC'):%Y-%m-%d} n={len(df)}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=None, help="逗号分隔；默认 universe∪raw∪基准")
    ap.add_argument("--max-symbols", type=int, default=0, help="最多处理 N 个（0=全部）")
    ap.add_argument("--no-merge-raw", action="store_true", help="只写 history/klines")
    ap.add_argument("--from-ms", type=int, default=START_MS)
    args = ap.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_symbols()
    if args.max_symbols and args.max_symbols > 0:
        symbols = symbols[: args.max_symbols]

    HIST_KL.mkdir(parents=True, exist_ok=True)
    RAW_KL.mkdir(parents=True, exist_ok=True)

    rows = []
    t_all = time.time()
    for i, sym in enumerate(symbols, 1):
        t0 = time.time()
        try:
            # 增量：若 history 已有，从倒数第 48h 前再拉（防缺口）
            old_h = load_existing(HIST_KL / f"{sym}.parquet")
            start = args.from_ms
            if old_h is not None and len(old_h) and "open_time" in old_h.columns:
                start = max(args.from_ms, int(old_h["open_time"].max()) - 48 * 3_600_000)
            new = fetch_klines(sym, start_ms=start)
            hist = merge_frames(old_h, new)
            if len(hist) == 0:
                rows.append({"symbol": sym, "ok": False, "error": "no data", "n": 0})
                print(f"[{i}/{len(symbols)}] {sym}: no data")
                continue
            hist_path = HIST_KL / f"{sym}.parquet"
            hist.to_parquet(hist_path, index=False)
            n_raw = 0
            if not args.no_merge_raw:
                # 单份存储：history 为 canonical；raw 用硬链接（省双份盘）
                import os

                raw_path = RAW_KL / f"{sym}.parquet"
                try:
                    if raw_path.exists():
                        try:
                            if os.path.samefile(hist_path, raw_path):
                                n_raw = len(hist)
                            else:
                                raw_path.unlink()
                                os.link(hist_path, raw_path)
                                n_raw = len(hist)
                        except OSError:
                            raw_path.unlink(missing_ok=True)
                            os.link(hist_path, raw_path)
                            n_raw = len(hist)
                    else:
                        os.link(hist_path, raw_path)
                        n_raw = len(hist)
                except OSError:
                    # 硬链接失败则退回拷贝一份
                    for c in COLS:
                        if c not in hist.columns:
                            hist[c] = pd.NA
                    hist[COLS].to_parquet(raw_path, index=False)
                    n_raw = len(hist)
            rows.append(
                {
                    "symbol": sym,
                    "ok": True,
                    "n_hist": len(hist),
                    "n_raw": n_raw,
                    "span": span(hist),
                    "sec": round(time.time() - t0, 1),
                    "error": "",
                }
            )
            print(f"[{i}/{len(symbols)}] {sym}: hist {span(hist)} ({time.time()-t0:.1f}s)")
        except Exception as e:  # noqa: BLE001
            rows.append({"symbol": sym, "ok": False, "error": str(e)[:120], "n": 0})
            print(f"[{i}/{len(symbols)}] {sym}: FAIL {e}")
        time.sleep(0.05)

    df = pd.DataFrame(rows)
    ok = df[df.get("ok", False) == True] if "ok" in df.columns else df  # noqa: E712
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = f"""# 218 Binance 1h klines 历史回补

- date: {now}
- history: `{HIST_KL}`
- raw_1h merge: {not args.no_merge_raw} → `{RAW_KL}`
- symbols: {len(symbols)} · ok: {int(ok['ok'].sum()) if len(df) and 'ok' in df.columns else 0}
- elapsed: {time.time()-t_all:.0f}s

## 摘要

```
{df.to_string(index=False) if len(df) else 'empty'}
```

## 用法

```bash
python scripts/218_backfill_binance_klines.py
python scripts/220_coverage_gap_report.py
```

## 说明

- 公开 fapi，无 key；OI 历史仍无法公开回补（见 110 注释）
- coinglass 仍作对照冷库；**主研究/前向应逐步切 binance history/raw**
"""
    REPORT.write_text(md, encoding="utf-8")
    print(md)
    print(f"wrote {REPORT}")
    return 0 if (len(df) == 0 or df["ok"].any()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
