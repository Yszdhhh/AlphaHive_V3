"""103_data_inventory.py — 盘点 coinglass_db 历史数据（P0 地基）。

目标：确认回测区间（各维度公共交集）、各特征可覆盖符号集、数据断点、单位坑，
并用 universe/delisted_pairs.json 标注退市币防幸存者偏差。

输出：
- reports/data_inventory_report.md   人类可读聚合报告
- reports/data_inventory_detail.csv  symbol × dimension 粒度明细

只读操作，不写任何数据库/快照。符合宪法（无订单路径）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DB_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db")
RAW1H = DB_ROOT / "raw_1h"
MACRO_DIR = DB_ROOT / "macro"
REPORTS_DIR = PROJECT_ROOT / "reports"

# 维度 -> 时间列候选（coinglass 各维度列名已实测）
DIMENSIONS = {
    "klines": ["open_time", "timestamp", "time"],
    "oi_ohlc": ["time", "timestamp"],
    "funding_ohlc": ["time", "timestamp"],
    "liquidation": ["time", "timestamp"],
    "ls_top_trader": ["time", "timestamp"],
    "ls_global": ["time", "timestamp"],
    "net_position": ["time", "timestamp"],
    "cvd": ["time", "timestamp"],
    "taker_buysell": ["time", "timestamp"],
}
MACRO_TIME_COLS = ["timestamp", "time", "date", "datetime"]
MS_EPOCH_THRESHOLD = 5e10  # > 这个值视为 ms 时间戳（2026 ≈ 1.78e12 ms；秒 ≈ 1.78e9）

MULTIPLIER_PREFIXES = ("1000000", "10000", "1000")
QUOTE_SUFFIXES = ("USDT", "USD_PERP", "USD", "BUSD")


def iso(ms: int) -> str:
    return pd.to_datetime(int(ms), unit="ms", utc=True).strftime("%Y-%m-%d")


def base_asset(symbol: str) -> str:
    s = symbol
    for p in MULTIPLIER_PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
            break
    for suffix in QUOTE_SUFFIXES:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    return s


def load_delisted_bases() -> set[str]:
    p = DB_ROOT / "universe" / "delisted_pairs.json"
    if not p.exists():
        return set()
    doc = json.loads(p.read_text(encoding="utf-8"))
    bases: set[str] = set()
    for exch, items in doc.get("data", {}).items():
        for item in items:
            bases.add(str(item.get("base_asset", "")))
    return {b for b in bases if b}


def pick_time_col(names: list[str], cands: list[str]) -> str | None:
    return next((c for c in cands if c in names), None)


def scan_series(ms_series: pd.Series) -> dict:
    """给定原始时间戳序列，返回标准化统计。"""
    v = pd.to_numeric(ms_series, errors="coerce").dropna()
    v = v.sort_values().drop_duplicates()
    if v.empty:
        return {"n": 0}
    if float(v.max()) < MS_EPOCH_THRESHOLD:
        v = v * 1000  # 秒 -> 毫秒
    diff = v.diff().dropna()
    return {
        "n": int(len(v)),
        "min_ms": int(v.min()),
        "max_ms": int(v.max()),
        "max_gap_hours": float(diff.max()) / 3600_000 if not diff.empty else 0.0,
        "gap_bars_gt2h": int((diff > 2 * 3600_000).sum()) if not diff.empty else 0,
    }


def scan_dimension(dim: str, time_cands: list[str], delisted: set[str]) -> list[dict]:
    dim_dir = RAW1H / dim
    rows: list[dict] = []
    files = sorted(dim_dir.glob("*.parquet"))
    for f in files:
        sym = f.stem
        try:
            schema = pq.read_schema(f)
            tc = pick_time_col(schema.names, time_cands)
            if tc is None:
                rows.append({"dim": dim, "symbol": sym, "error": "NO_TIME_COL", "cols": ",".join(schema.names)})
                continue
            t = pq.read_table(f, columns=[tc]).to_pandas()[tc]
            st = scan_series(t)
            rows.append({
                "dim": dim,
                "symbol": sym,
                "base": base_asset(sym),
                "is_delisted": base_asset(sym) in delisted,
                "time_col": tc,
                "n": st.get("n", 0),
                "min_date": iso(st["min_ms"]) if "min_ms" in st else None,
                "max_date": iso(st["max_ms"]) if "max_ms" in st else None,
                "max_gap_hours": st.get("max_gap_hours", 0.0),
                "gap_bars_gt2h": st.get("gap_bars_gt2h", 0),
            })
        except Exception as exc:  # noqa: BLE001 — 盘点必须吞错，逐文件报告
            rows.append({"dim": dim, "symbol": sym, "error": f"{type(exc).__name__}: {exc}"})
    return rows


def dt_to_ms(series: pd.Series) -> pd.Series:
    """任意 datetime64 序列 -> epoch ms int 序列（按列/索引实际 unit）。"""
    s = pd.Series(series)
    if not pd.api.types.is_datetime64_any_dtype(s.dtype):
        return s
    unit = getattr(s.dt, "unit", "ns")
    i64 = s.astype("int64")
    if unit == "ns":
        return i64 // 1_000_000
    if unit == "us":
        return i64 // 1_000
    if unit == "s":
        return i64 * 1_000
    return i64  # ms


def scan_macro() -> list[dict]:
    rows: list[dict] = []
    for f in sorted(MACRO_DIR.glob("*.parquet")):
        sym = f.stem
        try:
            df = pq.read_table(f).to_pandas()
            tc = pick_time_col(list(df.columns), MACRO_TIME_COLS)
            if tc is None and isinstance(df.index, pd.DatetimeIndex):
                v = dt_to_ms(pd.Series(df.index))
            elif tc is not None:
                v = dt_to_ms(df[tc])
            else:
                rows.append({"dim": "macro", "symbol": sym, "error": "NO_TIME"})
                continue
            v = v.astype("float64")
            if v.dropna().max() < MS_EPOCH_THRESHOLD:
                v = v * 1000  # 秒 -> 毫秒
            st = scan_series(v)
            rows.append({
                "dim": "macro", "symbol": sym, "base": sym, "is_delisted": False,
                "time_col": tc or "index", "n": st.get("n", 0),
                "min_date": iso(st["min_ms"]) if "min_ms" in st else None,
                "max_date": iso(st["max_ms"]) if "max_ms" in st else None,
                "max_gap_hours": st.get("max_gap_hours", 0.0),
                "gap_bars_gt2h": st.get("gap_bars_gt2h", 0),
            })
        except Exception as exc:  # noqa: BLE001
            rows.append({"dim": "macro", "symbol": sym, "error": f"{type(exc).__name__}: {exc}"})
    return rows


def sample_columns(dim: str) -> dict:
    """采样 2 个文件读全列，确认列结构 + 关键列量级（单位坑探测）。"""
    dim_dir = RAW1H / dim
    files = sorted(dim_dir.glob("*.parquet"))
    if not files:
        return {"dim": dim, "files": 0}
    sample = [files[0]]
    if len(files) > 1:
        sample.append(files[len(files) // 2])
    out = {"dim": dim, "files": len(files), "samples": []}
    for f in sample:
        try:
            df = pq.read_table(f).to_pandas()
            numeric = {c: float(df[c].median()) for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c not in ("time", "timestamp", "open_time")}
            out["samples"].append({"symbol": f.stem, "cols": list(df.columns), "median": numeric})
        except Exception as exc:  # noqa: BLE001
            out["samples"].append({"symbol": f.stem, "error": str(exc)})
    return out


def build_report(rows: list[dict], samples: list[dict], delisted: set[str]) -> str:
    df = pd.DataFrame(rows)
    df["min_dt"] = pd.to_datetime(df["min_date"], errors="coerce")
    df["max_dt"] = pd.to_datetime(df["max_date"], errors="coerce")
    lines: list[str] = []
    lines.append("# coinglass_db 数据盘点报告\n")
    lines.append(f"- 生成时间: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 数据根: `{DB_ROOT}`")
    lines.append(f"- 退市 base_asset 数（delisted_pairs.json）: {len(delisted)}\n")

    lines.append("## 各维度覆盖总览\n")
    lines.append("| 维度 | 文件数 | 数据行中位数 | 最早 | 最晚 | 断点>2h符号数 |")
    lines.append("|---|---|---|---|---|---|")
    for dim, g in df.groupby("dim"):
        ok = g.dropna(subset=["min_date"])
        if ok.empty:
            lines.append(f"| {dim} | {len(g)} | - | - | - | - |")
            continue
        lines.append(
            f"| {dim} | {len(g)} | {int(ok['n'].median())} | {ok['min_date'].min()} | {ok['max_date'].max()} "
            f"| {(g['gap_bars_gt2h'] > 0).sum()} |"
        )

    lines.append("\n## 回测窗口参考\n")
    lines.append("> 交集列 = 所有 symbol 同时可用的【严格公共窗】（被个别上市晚/退市早的币压缩）。")
    lines.append("> 事件研究实际用每个 symbol 自身可用窗口，主覆盖区间才代表真实回测窗。\n")
    lines.append("| 维度 | 严格公共交集 | 主覆盖（中位数 symbol） | 符号数 |")
    lines.append("|---|---|---|---|")
    for dim, g in df.groupby("dim"):
        ok = g.dropna(subset=["min_date"])
        if ok.empty:
            continue
        start = ok["min_dt"].max()
        end = ok["max_dt"].min()
        med_start = ok["min_dt"].median()
        med_end = ok["max_dt"].median()
        common = f"{start:%Y-%m-%d} → {end:%Y-%m-%d}" if end > start else "∅"
        lines.append(f"| {dim} | {common} | {med_start:%Y-%m-%d} → {med_end:%Y-%m-%d} | {len(ok)} |")

    lines.append("\n## 最大断点 TOP 12\n")
    lines.append("| 维度 | 符号 | 最大gap(h) | >2h断点数 | 区间 |")
    lines.append("|---|---|---|---|---|")
    top = df.nlargest(12, "max_gap_hours").dropna(subset=["max_gap_hours"])
    for _, r in top.iterrows():
        lines.append(f"| {r['dim']} | {r['symbol']} | {r['max_gap_hours']:.1f} | {int(r['gap_bars_gt2h'])} | {r['min_date']} → {r['max_date']} |")

    lines.append("\n## 退市币（coinglass 有历史数据但已下架）\n")
    dl = df[df["is_delisted"] == True]  # noqa: E712
    if not dl.empty:
        dl_syms = sorted(set(dl["symbol"]))
        lines.append(f"- {len(dl_syms)} 个符号在 delisted_pairs.json 中：{', '.join(dl_syms)}")
    else:
        lines.append("- 无")

    lines.append("\n## 单位/列结构采样\n")
    for s in samples:
        lines.append(f"\n### {s['dim']}（{s['files']} 文件）")
        for sm in s["samples"]:
            lines.append(f"- `{sm['symbol']}` cols={sm.get('cols', 'ERR')}")
            if "median" in sm:
                lines.append(f"  - 数值列中位数: {sm['median']}")
            else:
                lines.append(f"  - ERROR: {sm.get('error')}")

    return "\n".join(lines)


def main() -> None:
    delisted = load_delisted_bases()
    all_rows: list[dict] = []
    for dim, tc in DIMENSIONS.items():
        all_rows.extend(scan_dimension(dim, tc, delisted))
    all_rows.extend(scan_macro())

    samples = [sample_columns(d) for d in DIMENSIONS]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    detail_path = REPORTS_DIR / "data_inventory_detail.csv"
    report_path = REPORTS_DIR / "data_inventory_report.md"
    pd.DataFrame(all_rows).to_csv(detail_path, index=False)
    report_path.write_text(build_report(all_rows, samples, delisted), encoding="utf-8")
    print(f"wrote {report_path}")
    print(f"wrote {detail_path}")

    # 控制台摘要
    df = pd.DataFrame(all_rows)
    print("\n=== 维度覆盖 ===")
    for dim, g in df.groupby("dim"):
        ok = g.dropna(subset=["min_date"])
        if ok.empty:
            print(f"  {dim:16s} ERR {g['error'].iloc[0] if 'error' in g.columns else 'empty'}")
            continue
        print(f"  {dim:16s} n={len(ok):4d}  span={ok['min_date'].min()} -> {ok['max_date'].max()}  gap2h_symbols={(g['gap_bars_gt2h'] > 0).sum()}")


if __name__ == "__main__":
    main()
