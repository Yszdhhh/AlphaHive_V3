"""159_newlisting_monitor.py — s009 前向监测：新上市币 washout × 4h 确认 候选扫描。

前向事件流（108 不扫 washout 裸事件，本脚本补 s009 专用流）：
1. 每日拉币安 exchangeInfo（onboardDate 精确到 ms）→ 新币池 = 上线 <90 天
2. 对每个新币：binance_free_db klines → washout 检测（price_z<-2 或 ret_24h<-8%，
   720h rolling，min_periods=360 → 上市 ~15 天后才可测）
3. 4h 确认：事件后 4h 收盘反弹（r4>0）且已过去 → 候选
4. 输出 reports/newlisting_candidates.csv（幂等：143 账户 D 按 alert_id 去重）

只读、不下单；失败不阻塞（每日任务 best-effort）。
用法：python scripts/159_newlisting_monitor.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

REPORTS = PROJECT_ROOT / "reports"
OUT_CSV = REPORTS / "newlisting_candidates.csv"
BINANCE_ROOT = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h")
RAW_DIR = PROJECT_ROOT / "data" / "newlisting_raw"
EXCHANGE_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"
KLINES_URL = "https://fapi.binance.com/fapi/v1/klines"
NEW_DAYS = 90
Z_WIN = 720
Z_MIN = 360
CONFIRM_H = 4


def fetch_klines(sym: str) -> np.ndarray | None:
    """binance_free_db → 自维护缓存（data/newlisting_raw/）→ API 增量拉取。"""
    # 1) binance_free_db（universe 币）
    p = BINANCE_ROOT / "klines" / f"{sym}.parquet"
    if p.exists():
        try:
            kl = pd.read_parquet(p)
            if {"open_time", "close", "open"}.issubset(kl.columns):
                return kl.sort_values("open_time").drop_duplicates(subset="open_time")
        except Exception:
            pass
    # 2) 自维护缓存
    cp = RAW_DIR / f"{sym}.parquet"
    df = pd.DataFrame()
    if cp.exists():
        try:
            df = pd.read_parquet(cp)
        except Exception:
            df = pd.DataFrame()
    last = int(df["open_time"].max()) if len(df) else int(df["open_time"].min()) if False else 0
    start = last + 3_600_000 if last else int((pd.Timestamp.now(tz="UTC").timestamp() - NEW_DAYS * 86400) * 1000)
    if last and pd.Timestamp.now(tz="UTC").timestamp() * 1000 - last < 3_600_000:
        return df
    chunks = []
    while start < pd.Timestamp.now(tz="UTC").timestamp() * 1000:
        url = (f"{KLINES_URL}?symbol={sym}&interval=1h&startTime={start}&limit=1500")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
        except Exception as exc:
            print(f"  [159] {sym} klines failed: {exc}")
            break
        if not data:
            break
        chunk = pd.DataFrame([{
            "open_time": int(k[0]), "open": float(k[1]), "high": float(k[2]),
            "low": float(k[3]), "close": float(k[4]),
            "quote_volume": float(k[7]),
        } for k in data])
        chunks.append(chunk)
        start = int(data[-1][0]) + 3_600_000
        if len(chunks) > 4:
            break
    if chunks:
        new = pd.concat(chunks, ignore_index=True).drop_duplicates(subset="open_time").sort_values("open_time")
        df = pd.concat([df, new], ignore_index=True).drop_duplicates(subset="open_time").sort_values("open_time")
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cp)
    return df if len(df) else None


def fetch_new_pool() -> dict[str, int]:
    """onboardDate < NEW_DAYS 天前的 TRADING 合约 → {symbol: onboard_ms}。"""
    req = urllib.request.Request(EXCHANGE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read())
    now = pd.Timestamp.now(tz="UTC").timestamp() * 1000
    cutoff = now - NEW_DAYS * 24 * 3_600_000
    out: dict[str, int] = {}
    for s in d.get("symbols", []):
        od = s.get("onboardDate")
        if od and s.get("status") == "TRADING" and cutoff <= od <= now:
            out[s["symbol"]] = int(od)
    return out


def btc_daily() -> pd.Series:
    """BTC 日线（coinglass 历史 + binance_free_db 前向拼接）→ Mayer Multiple 日序列。"""
    COINGLASS_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
    closes: dict = {}
    for root in [COINGLASS_ROOT / "klines", BINANCE_ROOT / "klines"]:
        p = root / "BTCUSDT.parquet"
        if not p.exists():
            continue
        try:
            kl = pd.read_parquet(p, columns=["open_time", "close"])
        except Exception:
            continue
        ts = pd.to_numeric(kl["open_time"], errors="coerce").astype(np.int64)
        cl = pd.to_numeric(kl["close"], errors="coerce").astype(float)
        day = pd.to_datetime(ts, unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
        for d, c in zip(day, cl):
            if np.isfinite(c):
                closes[d] = c
    if not closes:
        return pd.Series(dtype=float)
    daily = pd.Series(closes).sort_index()
    ma200 = daily.rolling(200, min_periods=120).mean()
    return (daily / ma200.replace(0, np.nan)).dropna()


MEME_POOL = {"DOGEUSDT", "1000PEPEUSDT", "FARTCOINUSDT", "1000BONKUSDT", "PENGUUSDT",
             "PUMPUSDT", "WIFUSDT", "TRUMPUSDT", "VIRTUALUSDT", "WLFIUSDT",
             "SPCXUSDT", "ESPORTSUSDT"}
# 已知加密原生（非股票 ticker）：用反例集辅助分类
KNOWN_CRYPTO = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "LINK", "DOGE", "TRX",
                "LTC", "BCH", "DOT", "NEAR", "INJ", "TIA", "SUI", "ARB", "OP", "ENA",
                "AAVE", "UNI", "CRV", "FIL", "ATOM", "ETC", "HBAR", "XLM", "XMR",
                "LDO", "PENDLE", "RENDER", "GRASS", "ONDO", "WLD", "SEI", "APT", "POL"}


def pool_category(sym: str) -> str:
    """股票代币 / meme / 加密原生 分类（前向池漂移统计用）。"""
    base = sym.replace("USDT", "").replace("USDC", "")
    if base in MEME_POOL or base in ("FARTCOIN", "1000BONK", "1000PEPE", "PENGU", "PUMP",
                                     "WIF", "TRUMP", "VIRTUAL", "WLFI", "SPCX", "ESPORTS"):
        return "meme"
    if base in KNOWN_CRYPTO or not re.fullmatch(r"[A-Z]{1,5}", base):
        return "crypto"
    # 全大写短字母 = 股票代币候选（AAOI/AMAT/BRKB/CRWV 等）
    return "stock"


def main() -> int:
    try:
        pool = fetch_new_pool()
    except Exception as exc:
        print(f"[159] exchangeInfo failed: {exc}")
        return 1
    print(f"[159] 新币池（<{NEW_DAYS} 天）: {len(pool)}")

    existing = set()
    if OUT_CSV.exists():
        try:
            existing = set(pd.read_csv(OUT_CSV)["alert_id"])
        except Exception:
            existing = set()

    mayer_series = btc_daily()
    mayer_series.index = pd.to_datetime(mayer_series.index)

    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    rows = []
    for sym, onboard in sorted(pool.items()):
        kl = fetch_klines(sym)
        if kl is None:
            continue
        ts = pd.to_numeric(kl["open_time"], errors="coerce").to_numpy(dtype=np.int64)
        close = pd.to_numeric(kl["close"], errors="coerce").to_numpy(dtype=float)
        opens = pd.to_numeric(kl["open"], errors="coerce").to_numpy(dtype=float)
        if len(close) < Z_MIN:
            continue
        s = pd.Series(close)
        z = (s - s.rolling(Z_WIN, min_periods=Z_MIN).mean()) / s.rolling(Z_WIN, min_periods=Z_MIN).std().replace(0, np.nan)
        ret24 = s.pct_change(24) * 100.0
        fired = np.isfinite(z.to_numpy()) & np.isfinite(ret24.to_numpy()) & \
            ((z.to_numpy() < -2.0) | (ret24.to_numpy() < -8.0))
        last_t = -10**18
        for i in np.flatnonzero(fired):
            t = int(ts[i])
            if t - last_t < 72 * 3_600_000:
                continue
            last_t = t
            # 4h 确认已过去且反弹
            if t + (CONFIRM_H + 1) * 3_600_000 > now_ms:
                continue
            pos = int(np.searchsorted(ts, t, side="right")) - 1
            if pos < 0 or pos + CONFIRM_H + 1 >= len(close):
                continue
            r4 = (close[pos + CONFIRM_H] / close[pos] - 1) * 100.0
            if not np.isfinite(r4) or r4 <= 0:
                continue
            aid = f"nl_washout_{sym}_{t}"
            if aid in existing:
                continue
            ev_day = pd.to_datetime(t, unit="ms", utc=True).tz_localize(None).normalize()
            m = mayer_series.reindex(mayer_series.index[mayer_series.index <= ev_day]).iloc[-1] \
                if (mayer_series.index <= ev_day).any() else np.nan
            rows.append({
                "alert_id": aid, "symbol": sym, "trigger": "newlisting_washout_confirm",
                "timestamp_ms": t, "direction": "Long",
                "onboard_ms": onboard, "age_days": (t - onboard) / (24 * 3_600_000),
                "r4_confirm": round(r4, 4),
                "entry_px": round(float(opens[pos + CONFIRM_H + 1]), 8),
                "mayer": round(float(m), 4) if np.isfinite(m) else None,
                "pool": pool_category(sym),
            })
    # 回填旧候选 mayer/pool（首次写入时无此列；新候选 0 也执行）
    if OUT_CSV.exists():
        old = pd.read_csv(OUT_CSV)
        if "mayer" not in old.columns or old["mayer"].isna().any():
            m_idx = pd.to_datetime(mayer_series.index)
            def _m(ts):
                d = pd.to_datetime(int(ts), unit="ms", utc=True).tz_localize(None).normalize()
                cand = m_idx[m_idx <= d]
                if len(cand) == 0:
                    return np.nan
                return float(mayer_series.loc[cand[-1]])
            if "mayer" not in old.columns:
                old["mayer"] = np.nan
            mask = old["mayer"].isna()
            old.loc[mask, "mayer"] = old.loc[mask, "timestamp_ms"].apply(_m)
            print(f"[159] 回填 mayer {int(mask.sum())} 行")
        if "pool" not in old.columns or old["pool"].isna().any():
            old["pool"] = old["symbol"].apply(pool_category)
            print(f"[159] 回填 pool {len(old)} 行")
        old.to_csv(OUT_CSV, index=False, encoding="utf-8")
    if rows:
        new = pd.DataFrame(rows)
        if OUT_CSV.exists():
            old = pd.read_csv(OUT_CSV)
            new = pd.concat([old, new], ignore_index=True)
        new.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"[159] 新候选 {len(rows)} → {OUT_CSV}（累计 {len(new) if rows else len(existing)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
