r"""220 — 多源 klines/funding 覆盖缺口报告（基建）。

对比：coinglass raw_1h · binance raw_1h · binance history/klines · funding history
输出：reports/coverage_gap_220.md + reports/coverage_gap_220.csv
用法：python scripts/220_coverage_gap_report.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.data_registry import paths  # noqa: E402

CG = Path(str(paths.coinglass.raw_1h)) / "klines"
BN_RAW = Path(str(paths.binance_free.raw_1h)) / "klines"
DB = Path(str(paths.binance_free.raw_1h)).parent
BN_HIST = DB / "history" / "klines"
BN_FUND = DB / "history" / "funding"
OUT_MD = PROJECT_ROOT / "reports" / "coverage_gap_220.md"
OUT_CSV = PROJECT_ROOT / "reports" / "coverage_gap_220.csv"


def file_span(path: Path, ts_col: str) -> dict:
    if not path.exists():
        return {"exists": False, "n": 0, "min": None, "max": None}
    try:
        df = pd.read_parquet(path, columns=[ts_col])
        t = pd.to_numeric(df[ts_col], errors="coerce").dropna()
        if t.empty:
            return {"exists": True, "n": 0, "min": None, "max": None}
        return {
            "exists": True,
            "n": int(len(t)),
            "min": int(t.min()),
            "max": int(t.max()),
        }
    except Exception as e:  # noqa: BLE001
        return {"exists": True, "n": 0, "min": None, "max": None, "err": str(e)[:80]}


def fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "-"
    return pd.Timestamp(ms, unit="ms", tz="UTC").strftime("%Y-%m-%d")


def main() -> int:
    syms = set()
    for d in (CG, BN_RAW, BN_HIST):
        if d.exists():
            syms |= {p.stem for p in d.glob("*.parquet")}
    syms = sorted(syms)

    rows = []
    for sym in syms:
        cg = file_span(CG / f"{sym}.parquet", "open_time")
        br = file_span(BN_RAW / f"{sym}.parquet", "open_time")
        bh = file_span(BN_HIST / f"{sym}.parquet", "open_time")
        # funding 用 fundingTime
        ff = file_span(BN_FUND / f"{sym}.parquet", "fundingTime")
        # gap after cg end if bn starts later
        gap_days = None
        if cg.get("max") and br.get("min"):
            gap_days = (br["min"] - cg["max"]) / 86_400_000
        rows.append(
            {
                "symbol": sym,
                "cg_n": cg.get("n", 0),
                "cg_min": fmt_ms(cg.get("min")),
                "cg_max": fmt_ms(cg.get("max")),
                "bn_raw_n": br.get("n", 0),
                "bn_raw_min": fmt_ms(br.get("min")),
                "bn_raw_max": fmt_ms(br.get("max")),
                "bn_hist_n": bh.get("n", 0),
                "bn_hist_min": fmt_ms(bh.get("min")),
                "bn_hist_max": fmt_ms(bh.get("max")),
                "fund_n": ff.get("n", 0),
                "fund_min": fmt_ms(ff.get("min")),
                "fund_max": fmt_ms(ff.get("max")),
                "cg_to_raw_gap_days": round(gap_days, 2) if gap_days is not None else None,
                "hist_covers_cg_end": bool(
                    bh.get("max") and cg.get("max") and bh["max"] >= cg["max"]
                ),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)

    n_hist = int((df["bn_hist_n"] > 0).sum())
    n_raw = int((df["bn_raw_n"] > 0).sum())
    n_cg = int((df["cg_n"] > 0).sum())
    # 需要回补：无 hist 或 hist max 早于 raw max（未并入最新）
    need = df[(df["bn_hist_n"] == 0) | (df["bn_raw_n"] < 500)]
    short_raw = df[df["bn_raw_n"] > 0].nsmallest(8, "bn_raw_n")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = f"""# 220 多源覆盖缺口报告

- date: {now}
- symbols scanned: {len(df)}
- coinglass klines: {n_cg}
- binance raw_1h klines: {n_raw}
- binance history/klines: {n_hist}
- funding history: {int((df['fund_n']>0).sum())}

## 结论（给基建）

| 项 | 值 |
|---|---|
| history 已覆盖币 | {n_hist} |
| raw 仍短（n&lt;500 或无 hist） | {len(need)} |
| CSV | `{OUT_CSV}` |

### raw 最短样本

```
{short_raw[['symbol','bn_raw_n','bn_raw_min','bn_raw_max','bn_hist_n','bn_hist_min']].to_string(index=False) if len(short_raw) else 'n/a'}
```

### 建议

1. 跑 `python scripts/218_backfill_binance_klines.py` 直到 history 与 raw 拉长
2. coinglass 仅作 2026-07 前对照；**新研究默认 binance history/raw**
3. funding 用 `python scripts/110_backfill_history.py` 增量刷新

## 全表

见 CSV（按 symbol）。
"""
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)
    print(f"wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
