r"""194_pull_delisted_klines.py — 下架 universe 1h klines 拉取（fapi 优先 + vision zip 回退）。

为 wash_cvd 下架池复测（195）准备数据：全列（含 taker_buy_quote_volume → 真 CVD 近似），
vol>0 截断（去掉下架后 0 量幽灵 bar），parquet 缓存 data/delisted_raw/{SYM}.parquet。

源（侦察实测）：
- fapi /fapi/v1/klines interval=1h：SETTLING 127 全历史 + USDT_PERP_GONE 27/31 可用
- 4 个 -1121（AERGOUSDT/BDXNUSDT/BTCSTUSDT/SXPUSDT）：data.binance.vision 月 zip 回退

幂等：缓存已含 taker 列且 vol>0 截断则跳过（183 的旧缓存只有 o/c/v，会重拉）。
速率：limit=1000（weight 5），请求间 sleep 0.25s；失败重试 3 次。

用法：
  python scripts/194_pull_delisted_klines.py --symbols=ALL
  python scripts/194_pull_delisted_klines.py --symbols=ACXUSDT,OMGUSDT
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

CACHE = PROJECT_ROOT / "data" / "delisted_raw"
MASTER = PROJECT_ROOT / "data" / "delisted_master.csv"

FAPI = "https://fapi.binance.com/fapi/v1/klines"
VISION_ZIP = ("https://data.binance.vision/data/futures/um/monthly/klines/"
              "{sym}/1h/{sym}-1h-{ym}.zip")
UA = {"User-Agent": "Mozilla/5.0"}

KCOL = ["t", "o", "h", "l", "c", "v", "qv", "tbv", "tbqv"]
KIDX = [0, 1, 2, 3, 4, 5, 7, 9, 10]  # open_time,o,h,l,c,vol,quote_vol,taker_buy_vol,taker_buy_quote_vol
SLEEP = 0.25
PAGE = 1000


def _http(url: str, retries: int = 3) -> bytes:
    last: Exception | None = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.0 + retries)
    raise RuntimeError(f"GET {url} failed: {last}")


def parse_rows(raw: list[list]) -> pd.DataFrame:
    df = pd.DataFrame([{KCOL[i]: float(k[KIDX[i]]) for i in range(len(KCOL))} for k in raw])
    df["t"] = df["t"].astype("int64")
    return df


def fetch_fapi(sym: str) -> pd.DataFrame | None:
    start = 1577836800000  # 2020-01-01
    frames: list[pd.DataFrame] = []
    for _ in range(200):
        url = f"{FAPI}?symbol={sym}&interval=1h&startTime={start}&limit={PAGE}"
        try:
            data = json.loads(_http(url))
        except RuntimeError:
            return None
        if not data:
            break
        frames.append(parse_rows(data))
        start = int(data[-1][0]) + 3_600_000
        if len(data) < PAGE:
            break
        time.sleep(SLEEP)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def fetch_vision(sym: str, start_ym: str | None = None) -> pd.DataFrame:
    """vision 月 zip 回退（-1121 符号）。start_ym 默认 2020-01。"""
    if start_ym is None:
        start_ym = "2020-01"
    y, m = (int(x) for x in start_ym.split("-"))
    now = datetime.now(timezone.utc)
    frames: list[pd.DataFrame] = []
    while (y, m) <= (now.year, now.month):
        ym = f"{y:04d}-{m:02d}"
        url = VISION_ZIP.format(sym=sym, ym=ym)
        try:
            data = _http(url, retries=2)
        except RuntimeError:
            pass  # 无该月档案（上架前/数据缺）
        else:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                name = z.namelist()[0]
                with z.open(name) as fh:
                    raw = pd.read_csv(fh, header=None)
            # 部分月档 CSV 带表头行（"open_time,open,..."）→ 过滤非数值行
            raw = raw[raw.iloc[:, 0].apply(
                lambda x: isinstance(x, (int, float)) or str(x).strip().lstrip("-").isdigit())]
            rows = [list(r) for r in raw.itertuples(index=False, name=None)]
            frames.append(parse_rows(rows))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    if not frames:
        raise RuntimeError(f"vision fallback empty for {sym}")
    return pd.concat(frames, ignore_index=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["c"] > 0]
    df = df[df["v"] > 0]  # 截断下架后 0 量幽灵 bar
    df = df.drop_duplicates(subset="t", keep="last").sort_values("t").reset_index(drop=True)
    return df


def pull(sym: str, verbose: bool = True) -> bool:
    cp = CACHE / f"{sym}.parquet"
    if cp.exists():
        try:
            old = pd.read_parquet(cp)
            if "tbqv" in old.columns:
                return True  # 已含 taker 列的完整缓存
        except Exception:  # noqa: BLE001
            pass
    df = fetch_fapi(sym)
    if df is None or len(df) == 0:
        # -1121 或其它失败 → vision 回退
        df = fetch_vision(sym)
    df = clean(df)
    if len(df) < 100:
        if verbose:
            print(f"  [194] {sym}: too few bars ({len(df)}), skip")
        return False
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cp)
    span = f"{df['t'].iloc[0]}..{df['t'].iloc[-1]}"
    if verbose:
        print(f"  [194] {sym}: bars={len(df)} t0={datetime.fromtimestamp(df['t'].iloc[0] / 1000, tz=timezone.utc):%Y-%m-%d}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="ALL",
                    help="逗号分隔符号列表，或 ALL=master 的 SETTLING∪USDT_PERP_GONE")
    args = ap.parse_args()

    if args.symbols == "ALL":
        master = pd.read_csv(MASTER)
        syms = sorted(master.loc[master["category"].isin(
            ["SETTLING", "USDT_PERP_GONE"]), "symbol"].tolist())
    else:
        syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    print(f"[194] pulling {len(syms)} symbols -> {CACHE}")
    ok = fail = 0
    for s in syms:
        try:
            if pull(s):
                ok += 1
            else:
                fail += 1
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"  [194] {s} FAILED: {exc}")
    print(f"[194] done: ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
