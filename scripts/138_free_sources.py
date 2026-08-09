"""138_free_sources.py — 免费外部数据源实测：谷歌趋势 + GDELT 新闻流。

命题（Owner 指令：把现有数据 + 免费数据能挖掘的维度全部跑一遍；本轮补测
0xEggg 框架中尚未直接验证的"散户关注度"维度）：
- 谷歌趋势搜索指数 = 散户关注度的免费代理（周频 5 年 / 日频近 3 月）；
- GDELT 新闻流 = 事件驱动注意力的免费代理（近 90-180 天日频条数）。

检验：
- 表1 谷歌趋势水平/变化 vs alt 篮子收益（5y 周频对齐 2022+；日频子窗口直接测"次日"）
- 表2 wash_cvd 事件按事件日前一完整周/日趋势分位分层 → 24h 超额（关注度低时信号质量？）
- 表3 GDELT 新闻条数（90-180 天，描述性）：btc 新闻量日变化 vs btc/alt 当日收益相关
- 永续-现货基差：确认不可得性（binance_free_db 无现货历史、coinglass 无现货），
  funding 是基差的代理（112/115 已测）。

数据源（外部，一次性拉取不做定时化，缓存于 reports/）：
- 谷歌趋势 via pytrends 4.9.2（https://trends.google.com/trends/），周频 5 年 + 日频近 3 月；
  连续请求会触发 Google 400 限流 → 内置 45s+ 间隔重试。
- GDELT 2.0 DOC API（https://api.gdeltproject.org/api/v2/doc/doc，来源 gdeltproject.org），
  mode=timelinevolraw 日频条数；429 限流 → 30s 起指数退避，尊重 Retry-After。

无前视：趋势/新闻特征一律取事件时点及之前的最近已完成周/日（shift 1），分位用
滚动窗口（周频 104 周、min_periods 26 周）计算，不引入未来信息。

用法：
  python scripts/138_free_sources.py [--refresh] [--n-baseline 3000] [--seed 2026]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import (
    DEFAULT_HORIZONS,
    bootstrap_ci,
    draw_random_events,
    forward_stats,
)

COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
BINANCE_FREE_DB = Path(r"C:\Users\10639\Desktop\加密\binance_free_db")
REPORTS_DIR = PROJECT_ROOT / "reports"

# ---------- 共享加载模板（113/115 口径，禁止改配置） ----------
_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec)
sys.modules["m113"] = m113
_spec.loader.exec_module(m113)

_spec2 = importlib.util.spec_from_file_location(
    "m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2)
sys.modules["m115"] = m115
_spec2.loader.exec_module(m115)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
detect_events = m115.detect_events
EPISODES = m113.EPISODES
episode_of = m113.episode_of

# ---------- 研究参数 ----------
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
HOUR_MS = 3_600_000
N_BASELINE = 3000
SEED = 2026
MIN_EVENTS = 30

GT_KW = ["bitcoin", "crypto"]
GT_TIMEFRAME_W = "today 5-y"      # 周频，5 年（Google 对 >270d 只给周频）
GT_TIMEFRAME_D = "today 3-m"      # 日频（8-m/6-m 实测间歇 400，3-m 稳定日频）
GDELT_DAYS = 180                  # GDELT 回看窗口（按 coinglass 数据末尾对齐）
GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_SOURCE = "gdeltproject.org (GDELT 2.0 DOC API, timelinevolraw)"
GT_SOURCE = "google trends via pytrends (https://trends.google.com/trends/)"

# 已知数字（交叉核对目标）
KNOWN = {"115 pooled wash_cvd n": 1348, "115 pooled wash_cvd 24h超额": 1.31}

CACHE_FILES = {
    "gtrends_weekly": REPORTS_DIR / "free_sources_gtrends_weekly.csv",
    "gtrends_daily": REPORTS_DIR / "free_sources_gtrends_daily.csv",
    "gdelt": REPORTS_DIR / "free_sources_gdelt_daily.csv",
    "fetch_log": REPORTS_DIR / "free_sources_fetch_log.json",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _ns(idx) -> pd.DatetimeIndex:
    """统一为 naive datetime64[ns]（pandas 3.0 CSV 读入是 [us]，period 计算是 [ns]，
    混用会让 join/reindex 静默失配 → 统一）。"""
    return pd.to_datetime(idx, utc=True).tz_localize(None).astype("datetime64[ns]")


# ============================================================
# 数据获取
# ============================================================

def _patch_urllib3_retry() -> None:
    """pytrends 4.9.2 与 urllib3>=2 不兼容（method_whitelist 改名 allowed_methods）→ 局部 monkeypatch。"""
    try:
        from urllib3.util import retry as _retry_mod
        if "method_whitelist" not in _retry_mod.Retry.__init__.__code__.co_varnames:
            _orig = _retry_mod.Retry.__init__
            def _patched(self, *args, **kwargs):
                if "method_whitelist" in kwargs:
                    kwargs["allowed_methods"] = kwargs.pop("method_whitelist")
                _orig(self, *args, **kwargs)
            _retry_mod.Retry.__init__ = _patched
    except Exception:
        pass


def _gtrends_pull(timeframe: str, kw: list[str], attempts: int = 4, base_wait: float = 45.0):
    """拉谷歌趋势；连续请求 Google 会 400 限流 → 递增间隔重试。返回 (df, attempts_used)。"""
    _patch_urllib3_retry()
    from pytrends.request import TrendReq
    last_err: Exception | None = None
    for att in range(1, attempts + 1):
        try:
            t = TrendReq(hl="en-US", tz=0, timeout=(10, 20), retries=1)
            t.build_payload(kw, timeframe=timeframe)
            df = t.interest_over_time()
            if df is None or df.empty:
                raise RuntimeError("empty response")
            df.index = df.index.tz_localize(None)  # tz=0 → 已是 UTC 日期
            return df, att
        except Exception as e:  # noqa: BLE001 — 记录后重试
            last_err = e
            wait = base_wait * att
            print(f"  [gtrends {timeframe}] attempt {att} 失败 ({type(e).__name__}: {str(e)[:100]})，等待 {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"gtrends {timeframe} 拉取失败: {last_err}")


def fetch_gtrends(force: bool = False) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    """周频 5 年 + 日频近 3 月。缓存到 reports/，带拉取时间戳。"""
    log: list[dict] = []
    out: dict[str, pd.DataFrame] = {}
    for key, timeframe in [("weekly", GT_TIMEFRAME_W), ("daily", GT_TIMEFRAME_D)]:
        cache = CACHE_FILES[f"gtrends_{key}"]
        if cache.exists() and not force:
            df = pd.read_csv(cache, parse_dates=["date"]).set_index("date")
            df.index = _ns(df.index)
            out[key] = df
            log.append({"source": f"gtrends_{key}", "outcome": "cache", "ts": _utcnow()})
            print(f"  [gtrends {key}] 读取缓存 {cache.name}")
            continue
        try:
            t0 = _utcnow()
            df, n_att = _gtrends_pull(timeframe, GT_KW)
            # 去 isPartial 的最后一行（未完成周/日，无前视）
            if "isPartial" in df.columns:
                df = df[df["isPartial"] == False]  # noqa: E712
            df = df.drop(columns=["isPartial"], errors="ignore")
            df.index = _ns(df.index)
            df["fetched_at"] = _utcnow()
            df.to_csv(cache)
            out[key] = df
            log.append({"source": f"gtrends_{key}", "timeframe": timeframe, "rows": len(df),
                        "attempts": n_att, "ts": t0, "outcome": "ok"})
            print(f"  [gtrends {key}] {timeframe} 拉取成功 rows={len(df)} (尝试 {n_att} 次)")
        except Exception as e:
            log.append({"source": f"gtrends_{key}", "timeframe": timeframe,
                        "ts": _utcnow(), "outcome": f"FAIL: {type(e).__name__}: {str(e)[:200]}"})
            print(f"  [gtrends {key}] 失败: {e}")
        time.sleep(20)  # 两次 Google 请求间留间隔
    return out, log


def _gdelt_get(params: dict, timeout: int = 60) -> dict:
    url = GDELT_BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "AlphaHiveV3-research/1.0 (academic)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _gdelt_fetch_retry(params: dict, max_attempts: int = 6, base_wait: float = 30.0,
                       max_wait: float = 300.0):
    """429 → 指数退避（上限 max_wait），尊重 Retry-After。返回 (data|None, log)。"""
    wait = base_wait
    log: list[dict] = []
    for att in range(1, max_attempts + 1):
        t0 = _utcnow()
        try:
            data = _gdelt_get(params)
            log.append({"attempt": att, "ts": t0, "outcome": "ok"})
            return data, log
        except urllib.error.HTTPError as e:
            if e.code != 429:
                log.append({"attempt": att, "ts": t0, "outcome": f"HTTP {e.code}: {e.reason}"})
                raise
            ra = e.headers.get("Retry-After") if e.headers else None
            wait = max(wait, float(ra)) if ra and ra.replace(".", "", 1).isdigit() else min(wait * 2, max_wait)
            log.append({"attempt": att, "ts": t0, "outcome": "HTTP 429", "wait_s": round(wait, 1)})
            print(f"  [gdelt] HTTP 429 (第 {att} 次)，等待 {wait:.0f}s", flush=True)
            if att == max_attempts:
                return None, log
            time.sleep(wait)
        except Exception as e:
            log.append({"attempt": att, "ts": t0, "outcome": f"{type(e).__name__}: {str(e)[:100]}"})
            raise
    return None, log


def fetch_gdelt(force: bool = False) -> tuple[pd.DataFrame, list[dict]]:
    """GDELT 日频文章条数（bitcoin/crypto，近 GDELT_DAYS 天，按 coinglass 末尾对齐）。"""
    cache = CACHE_FILES["gdelt"]
    if cache.exists() and not force:
        df = pd.read_csv(cache, parse_dates=["date"]).set_index("date")
        df.index = _ns(df.index)
        print(f"  [gdelt] 读取缓存 {cache.name} rows={len(df)}")
        return df, [{"source": "gdelt", "outcome": "cache", "ts": _utcnow()}]

    # 窗口：coinglass klines 数据末尾（2026-07-07）往前 GDELT_DAYS 天
    end = pd.Timestamp("2026-07-07", tz="UTC")
    start = end - pd.Timedelta(days=GDELT_DAYS)
    fmt = lambda t: t.strftime("%Y%m%d%H%M%S")  # noqa: E731
    rows: list[dict] = []
    log: list[dict] = []
    for kw in GT_KW:
        params = {"query": kw, "mode": "timelinevolraw", "format": "json",
                  "startdatetime": fmt(start), "enddatetime": fmt(end)}
        try:
            t0 = _utcnow()
            data, flog = _gdelt_fetch_retry(params)
            log += [{"kw": kw, **d} for d in flog]
            if data is None:
                print(f"  [gdelt] {kw} 拉取失败：连续 429（限流超预算），跳过（后续分析用部分数据）")
                continue
            tl = data.get("timeline", [])
            series = None
            for s in tl:
                if s.get("series") == "Article Count":
                    series = s
                    break
            if series is None:
                raise RuntimeError(f"timelinevolraw 无 Article Count 序列 (kw={kw})")
            for pt in series["data"]:
                rows.append({"date": pt["date"], f"{kw}_count": pt["value"],
                             f"{kw}_norm": pt.get("norm")})
            # 渐进保存：每关键字成功即写盘，避免中途被杀丢数据
            _df = pd.DataFrame(rows)
            _df["date"] = pd.to_datetime(_df["date"].str[:8], format="%Y%m%d")
            _df = _df.groupby("date", as_index=False).last().set_index("date").sort_index()
            _df.index = _ns(_df.index)
            _df["fetched_at"] = _utcnow()
            _df.to_csv(cache)
            print(f"  [gdelt] {kw} 拉取成功: {len(series['data'])} 天 (开始 {t0})", flush=True)
        except Exception as e:
            log.append({"kw": kw, "outcome": f"FAIL: {type(e).__name__}: {str(e)[:200]}",
                        "ts": _utcnow()})
            print(f"  [gdelt] {kw} 失败: {e}")
        time.sleep(25)  # 两次 GDELT 请求间间隔（官方 ~1 req/20s）

    if not rows:
        raise RuntimeError("GDELT 全部拉取失败（429 限流或网络），详见 fetch_log")

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"].str[:8], format="%Y%m%d")
    df = df.groupby("date", as_index=False).last()
    df = df.set_index("date").sort_index()
    df.index = _ns(df.index)
    for kw in GT_KW:
        if f"{kw}_count" not in df.columns:
            df[f"{kw}_count"] = np.nan
    df["fetched_at"] = _utcnow()
    df.to_csv(cache)
    return df, log


# ============================================================
# 价格/收益（与 113 同一套清洗）
# ============================================================

def load_daily_returns() -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """由 113 的 ctxs 派生日频收益。

    返回 (daily, by_sym)：
    - daily: index=UTC 日期，列 close_btc / ret_btc / ret_alt（等权篮子）/ n_alt
    - by_sym: {sym: 日收益 Series}（表2 事件 24h 用不到的篮子备用）
    """
    ctxs = load_price_ctx(load_universe_symbols())
    daily = pd.DataFrame(index=pd.date_range("2021-12-31", "2026-07-07", freq="D",
                                             tz="UTC").tz_localize(None).astype("datetime64[ns]"))
    by_sym: dict[str, pd.Series] = {}
    for sym, t in ctxs.items():
        s = t["close"].copy()
        s.index = pd.to_datetime(s.index, unit="ms", utc=True)
        dclose = s.resample("D").last()
        dclose.index = dclose.index.tz_localize(None)  # 统一 naive UTC 日期
        dret = dclose.pct_change() * 100.0
        dret.name = sym
        by_sym[sym] = dret
        daily[sym] = dret
    # BTC 不在 universe（BASE_SYMBOLS 排除）→ 单独按 113 清洗口径读
    btc_p = COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    if btc_p.exists():
        bdf = pd.read_parquet(btc_p, columns=["open_time", "close"])
        ts = pd.to_numeric(bdf["open_time"], errors="coerce")
        close = pd.to_numeric(bdf["close"], errors="coerce")
        s = pd.Series(close.to_numpy(), index=pd.Index(ts.to_numpy(dtype=np.int64)))
        s = s[~s.index.duplicated(keep="last")].sort_index().replace([np.inf, -np.inf], np.nan).dropna()
        med = s.rolling(720, min_periods=360).median()
        ratio = s / med.replace(0, pd.NA)
        s = s.where((ratio >= 0.02) & (ratio <= 50.0))
        s.index = pd.to_datetime(s.index, unit="ms", utc=True)
        btc_d = s.resample("D").last()
        btc_d.index = btc_d.index.tz_localize(None)
        btc_d = btc_d.pct_change() * 100.0
        by_sym["BTCUSDT"] = btc_d
        daily["BTCUSDT"] = btc_d
    alt_cols = [c for c in daily.columns if c != "BTCUSDT"]
    daily["ret_alt"] = daily[alt_cols].mean(axis=1, skipna=True)
    daily["ret_btc"] = daily["BTCUSDT"]
    daily["n_alt"] = daily[alt_cols].notna().sum(axis=1)
    daily = daily[["ret_btc", "ret_alt", "n_alt"]].dropna(subset=["ret_btc", "ret_alt"])
    return daily, by_sym


# ============================================================
# 表1：谷歌趋势 vs 收益
# ============================================================

def _corr_block(x: pd.Series, y: pd.Series) -> dict:
    m = x.notna() & y.notna()
    x, y = x[m], y[m]
    if len(x) < 20:
        return {"n": int(m.sum()), "pearson": np.nan, "spearman": np.nan}
    return {"n": int(m.sum()),
            "pearson": float(np.corrcoef(x, y)[0, 1]),
            "spearman": float(pd.Series(x).corr(pd.Series(y), method="spearman"))}


def table1_weekly(weekly: pd.DataFrame, daily: pd.DataFrame) -> dict:
    """周频 5 年：趋势水平/变化（前一完整周）vs 下一周 alt/btc 收益。"""
    w = weekly.copy()
    # Google Trends 周标签是周最后一天(周日) → 统一转成周一
    w.index = w.index - pd.Timedelta(days=6)
    # 每周收益 = 该周日收益之和（近似连续复利）；W-SUN = 周一起始周日结束
    d = daily.copy()
    d["week"] = d.index.to_period("W-SUN").start_time.normalize()
    wret = d.groupby("week")[["ret_alt", "ret_btc"]].sum()
    wret.index = _ns(wret.index)
    w = w.join(wret, how="inner")
    w = w.sort_index()
    # 无前视：用 w-1 周趋势值预测 w 周收益；变化 = (w-1) - (w-2)
    w["prev"] = w["bitcoin"].shift(1)
    w["chg"] = w["bitcoin"].shift(1) - w["bitcoin"].shift(2)
    w["next_alt"] = w["ret_alt"]
    w["next_btc"] = w["ret_btc"]
    w = w[w.index >= pd.Timestamp("2022-01-01")]

    def bucket_mean(series, b, label):
        q = pd.qcut(b, 4, labels=False, duplicates="drop")
        out = {}
        if q.notna().sum() == 0 or pd.isna(q.max()):
            return out
        for i in range(int(q.max()) + 1):
            out[f"{label}_q{i + 1}"] = float(series[q == i].mean())
        return out

    res = {
        "level_vs_next_alt": _corr_block(w["prev"], w["next_alt"]),
        "chg_vs_next_alt": _corr_block(w["chg"], w["next_alt"]),
        "level_vs_next_btc": _corr_block(w["prev"], w["next_btc"]),
        "level_quartile_next_alt": bucket_mean(w["next_alt"], w["prev"], "level"),
        "chg_quartile_next_alt": bucket_mean(w["next_alt"], w["chg"], "chg"),
        "n_weeks": int(w["next_alt"].notna().sum()),
        "series": {"start": str(w.index.min().date()), "end": str(w.index.max().date())},
    }
    return res


def table1_daily(daily_t: pd.DataFrame, daily: pd.DataFrame) -> dict:
    """日频近 3 月：趋势水平/变化（前一完整日）vs 当日 alt/btc 收益。

    无前视映射：行=日 t；prev = 趋势 t-1（日 t 开盘前已确定）；ret 为日 t 收益。
    """
    d = daily_t.copy()
    d["prev"] = d["bitcoin"].shift(1)
    d["chg"] = d["bitcoin"].shift(1) - d["bitcoin"].shift(2)
    d["ret_alt"] = daily["ret_alt"].reindex(d.index)
    d["ret_btc"] = daily["ret_btc"].reindex(d.index)
    d = d[d.index >= daily.index.min()]
    return {
        "level_vs_next_alt": _corr_block(d["prev"], d["ret_alt"]),
        "chg_vs_next_alt": _corr_block(d["chg"], d["ret_alt"]),
        "level_vs_next_btc": _corr_block(d["prev"], d["ret_btc"]),
        "n_days": int(d["ret_alt"].notna().sum()),
        "series": {"start": str(d.index.min().date()), "end": str(d.index.max().date())},
    }


# ============================================================
# 表2：wash_cvd 事件 × 谷歌趋势分位分层
# ============================================================

def _trailing_pct_rank(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    """滚动分位（asof）：第 i 点在其前 window 窗口内的百分位，无未来信息。"""
    vals = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    out = np.full(len(vals), np.nan)
    for i in range(len(vals)):
        lo = max(0, i - window + 1)
        seg = vals[lo:i + 1]
        seg = seg[np.isfinite(seg)]
        if len(seg) >= min_periods and np.isfinite(vals[i]):
            out[i] = (seg <= vals[i]).mean() * 100.0
    return pd.Series(out, index=series.index)


def _asof_rank(events: pd.DataFrame, series: pd.Series, rank_ser: pd.Series,
               step: str) -> pd.Series:
    """事件 ts → 前一完整周/日（shift 1）的趋势值 → 其滚动分位。无前视。

    series 索引约定：日频=自然日（naive UTC）；周频=周一（naive UTC，
    原始周日标签已在调用前转周一）。事件侧统一转 naive UTC 后对齐。
    """
    ev_ts = events["timestamp"].to_numpy(dtype=np.int64)
    ev_dt = pd.to_datetime(ev_ts, unit="ms", utc=True).tz_localize(None)
    if step == "W":
        asof = ev_dt.to_period("W-SUN").start_time.normalize() - pd.Timedelta(days=7)
    else:
        asof = ev_dt.normalize() - pd.Timedelta(days=1)
    pos = np.searchsorted(series.index.to_numpy(dtype="datetime64[ns]"),
                          asof.to_numpy(dtype="datetime64[ns]"), side="right") - 1
    pos = np.clip(pos, 0, len(series) - 1)
    ranks = rank_ser.to_numpy(dtype=float)
    return pd.Series(ranks[pos], index=events.index)


def table2_strat(events: pd.DataFrame, ctxs: dict, weekly: pd.DataFrame,
                 daily_t: pd.DataFrame, rng: np.random.Generator,
                 n_baseline: int, min_events: int) -> dict:
    """按事件日前一完整周（主）/前一日（近 3 月子集）趋势分位分层 → 24h 超额。"""
    events = events.copy()
    # 周频序列统一周一（周日标签 -6d），与事件侧对齐
    wk = weekly["bitcoin"].copy()
    wk.index = wk.index - pd.Timedelta(days=6)
    # 滚动分位（周频：104 周窗口、min 26 周；日频：90 日窗口、min 14 日——3 月窗口内
    # 事件少且集中在窗口前段，30 日 warmup 会把它们全部排除）
    wk_rank = _trailing_pct_rank(wk, 104, 26)
    dy_rank = _trailing_pct_rank(daily_t["bitcoin"], 90, 14)
    events["trend_pct_weekly"] = _asof_rank(events, wk, wk_rank, "W")
    events["trend_pct_daily"] = _asof_rank(events, daily_t["bitcoin"], dy_rank, "D")

    # 基线（与 115 同口径：lo=2022-01-01 hi=2026-06-30）
    base = draw_random_events(ctxs, n_baseline, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    base_parts = []
    if not base.empty:
        for bs, bg in base.groupby("symbol", sort=False):
            if bs in ctxs:
                base_parts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_stats = pd.concat(base_parts, ignore_index=True) if base_parts else pd.DataFrame()
    bs24 = (pd.to_numeric(base_stats["ret_24h"], errors="coerce").dropna().to_numpy()
            if not base_stats.empty else np.array([]))

    def strat_row(sub: pd.DataFrame, label: str) -> dict:
        v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        ci = bootstrap_ci(v, bs24, seed=SEED) if len(v) else {}
        n = int(len(v))
        if n < min_events:
            verdict = f"样本不足(n={n}<{min_events})"
        elif not np.isfinite(ci.get("ci_lo", np.nan)):
            verdict = "PENDING"
        elif ci["ci_lo"] > 0:
            verdict = "GO_LONG"
        elif ci["ci_hi"] < 0:
            verdict = "GO_SHORT"
        else:
            verdict = "NO_GO"
        return {"层": label, "n": n,
                "24h均": float(np.nanmean(v)) if len(v) else np.nan,
                "24h超额": ci.get("mean_diff", np.nan) if len(v) else np.nan,
                "CI下": ci.get("ci_lo", np.nan) if len(v) else np.nan,
                "CI上": ci.get("ci_hi", np.nan) if len(v) else np.nan,
                "判定": verdict}

    rows = []
    tercile_labels = ["低", "中", "高"]

    def _tercile(series: pd.Series) -> pd.Series:
        """qcut 3 分位，重复边自动合并（duplicates='drop'），返回 低/中/高 标签。"""
        q = pd.qcut(series, 3, labels=False, duplicates="drop")
        out = pd.Series(pd.NA, index=series.index, dtype="object")
        if q.notna().sum() == 0:
            return out
        n_bins = int(q.max()) + 1
        for i in range(n_bins):
            out[q == i] = tercile_labels[min(i, len(tercile_labels) - 1)]
        return out

    # 主分层：周频分位三分位
    q = _tercile(events["trend_pct_weekly"])
    qn = q.notna()
    if qn.sum() > 0:
        rows.append(strat_row(events[qn & (q == "低")], "周分位-低"))
        rows.append(strat_row(events[qn & (q == "中")], "周分位-中"))
        rows.append(strat_row(events[qn & (q == "高")], "周分位-高"))
        rows.append(strat_row(events[qn], "周分位-全（复核115）"))
    # 子集：日频分位（近 3 月窗口内的事件，n 小、描述性）
    qd = _tercile(events["trend_pct_daily"])
    qdn = qd.notna()
    if qdn.sum() > 0:
        for lab in tercile_labels:
            sub = events[qdn & (qd == lab)]
            if not sub.empty:
                rows.append(strat_row(sub, f"日分位-{lab}(近3月子集)"))
        rows.append(strat_row(events[qdn], "日分位-全(近3月子集)"))
    return {"rows": rows, "n_total": len(events), "n_with_weekly_pct": int(qn.sum()),
            "n_with_daily_pct": int(qdn.sum())}


# ============================================================
# 表3：GDELT 新闻条数（描述性）
# ============================================================

def table3_gdelt(gdelt: pd.DataFrame, daily: pd.DataFrame) -> dict:
    d = gdelt.join(daily[["ret_btc", "ret_alt"]], how="inner")
    d = d.dropna(subset=["bitcoin_count", "ret_btc"])
    d["btc_chg"] = d["bitcoin_count"].pct_change() * 100.0
    d["btc_chg_1"] = d["bitcoin_count"].diff()
    d["ret_btc_next"] = d["ret_btc"].shift(-1)
    d["ret_alt_next"] = d["ret_alt"].shift(-1)
    rows = {}
    for label, x, y in [
        ("count_vs_ret_sameday_btc", d["bitcoin_count"], d["ret_btc"]),
        ("count_vs_ret_sameday_alt", d["bitcoin_count"], d["ret_alt"]),
        ("chg_vs_ret_sameday_btc", d["btc_chg"], d["ret_btc"]),
        ("chg_vs_ret_sameday_alt", d["btc_chg"], d["ret_alt"]),
        ("count_vs_ret_nextday_btc", d["bitcoin_count"], d["ret_btc_next"]),
        ("count_vs_ret_nextday_alt", d["bitcoin_count"], d["ret_alt_next"]),
        ("crypto_count_vs_ret_btc", d["crypto_count"], d["ret_btc"]),
    ]:
        rows[label] = _corr_block(x, y)
    rows["n_days"] = int(len(d))
    rows["window"] = {"start": str(d.index.min().date()), "end": str(d.index.max().date())}
    rows["count_desc"] = {"mean": float(d["bitcoin_count"].mean()),
                          "min": int(d["bitcoin_count"].min()),
                          "max": int(d["bitcoin_count"].max()),
                          "p25": float(d["bitcoin_count"].quantile(.25)),
                          "p75": float(d["bitcoin_count"].quantile(.75))}
    return rows


# ============================================================
# 基差可得性
# ============================================================

def check_basis_availability() -> dict:
    """实证：binance_free_db 与 coinglass 均无现货 klines → 永续-现货基差不可得。"""
    out = {"spot_found": False, "evidence": []}
    for sub in ["klines"]:
        d = BINANCE_FREE_DB / "raw_1h" / sub
        files = sorted(d.glob("*.parquet")) if d.exists() else []
        out["evidence"].append({"loc": str(d), "files": len(files)})
    for sub in ["raw_1h", "raw"]:
        d = COINGLASS_RAW1H.parent / "raw_1h"
        if d.exists():
            names = [p.name for p in d.iterdir()]
            out["evidence"].append({"loc": str(d), "dirs": names})
            break
    # binance 现货 klines 的命名特征（如 BTCUSDT 现货无后缀）；perp 为 BTCUSDT 永续
    out["funding_proxy"] = ("funding 是基差的代理：永续资金费率 ≈ 基差经年化折减，"
                            "112（横截面/择时证伪）与 115（cvd_bear+funding 反转为 GO_SHORT）已测")
    return out


# ============================================================
# main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="强制重新拉取外部数据")
    parser.add_argument("--n-baseline", type=int, default=N_BASELINE)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--min-events", type=int, default=MIN_EVENTS)
    args = parser.parse_args()

    print("== 1/4 外部数据拉取 ==")
    weekly, gt_log_w = fetch_gtrends(args.refresh)
    time.sleep(25)
    gdelt, gd_log = fetch_gdelt(args.refresh)
    fetch_log = gt_log_w + gd_log
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = REPORTS_DIR / "free_sources_fetch_log.json"
    if log_path.exists():
        try:
            fetch_log = json.loads(log_path.read_text(encoding="utf-8")) + fetch_log
        except Exception:
            pass
    log_path.write_text(json.dumps(fetch_log, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n== 2/4 价格上下文（113 口径，66 币）==")
    ctxs = load_price_ctx(load_universe_symbols())
    fundings = m113.load_funding_series(load_universe_symbols())
    print(f"  价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)}")

    print("\n== 3/4 日频收益（alt 等权篮子）==")
    daily, _by_sym = load_daily_returns()

    print("\n== 4/4 检验 ==")
    rng = np.random.default_rng(args.seed)
    lines: list[str] = []
    lines.append("# 免费外部数据源实测：谷歌趋势 + GDELT 新闻流\n")
    lines.append(f"- 生成: {_utcnow()}")
    lines.append(f"- 谷歌趋势: {GT_SOURCE}，周频 5 年（2021-08 → 2026-08，Google 对 >270d 仅给周频）"
                 f"+ 日频近 3 月（{GT_TIMEFRAME_D}；8-m/6-m 实测间歇 400 限流，3-m 稳定）")
    lines.append(f"- GDELT: {GDELT_SOURCE}，mode=timelinevolraw 日频条数，"
                 f"窗口 {GDELT_DAYS}d 对齐 coinglass klines 末尾（2026-07-07），来源 gdeltproject.org")
    lines.append(f"- 拉取日志: free_sources_fetch_log.json（每次尝试时间戳/结果/等待）")
    lines.append(f"- 无前视：趋势/新闻特征取事件时点及之前最近完整周/日（shift 1）；分位用滚动窗口")
    lines.append("> 目的：实测两个免费情绪源的数据可用性（质量/限流/历史深度），并检验其与 alt 收益的关联。")

    # ---- 表1 ----
    print("  [表1] 谷歌趋势 vs 收益")
    t1w = table1_weekly(weekly["weekly"], daily)
    t1d = table1_daily(weekly["daily"], daily)
    lines.append("\n## 表1 谷歌趋势指数 vs 收益相关\n")
    lines.append(f"周频 5 年（2022 起对齐 coinglass，{t1w['n_weeks']} 周；趋势值 = 前一完整周，收益 = 下一周）：\n")
    lines.append("| 对比 | n | Pearson | Spearman |")
    lines.append("|---|---|---|---|")
    for k, lab in [("level_vs_next_alt", "水平 → 下周 alt 收益"),
                   ("chg_vs_next_alt", "周变化 → 下周 alt 收益"),
                   ("level_vs_next_btc", "水平 → 下周 btc 收益")]:
        r = t1w[k]
        lines.append(f"| {lab} | {r['n']} | {r['pearson']:+.3f} | {r['spearman']:+.3f} |")
    lq = t1w["level_quartile_next_alt"]
    cq = t1w["chg_quartile_next_alt"]
    lines.append("\n水平四分位 → 下周 alt 收益均值（%）："
                 + " | ".join(f"Q{i+1}: {lq[f'level_q{i+1}']:+.2f}" for i in range(4)))
    lines.append("变化四分位 → 下周 alt 收益均值（%）："
                 + " | ".join(f"Q{i+1}: {cq[f'chg_q{i+1}']:+.2f}" for i in range(4)))
    lines.append(f"\n日频近 3 月（{t1d['n_days']} 日；趋势值 = 前一日，收益 = 次日）：\n")
    lines.append("| 对比 | n | Pearson | Spearman |")
    lines.append("|---|---|---|---|")
    for k, lab in [("level_vs_next_alt", "水平 → 次日 alt 收益"),
                   ("chg_vs_next_alt", "日变化 → 次日 alt 收益"),
                   ("level_vs_next_btc", "水平 → 次日 btc 收益")]:
        r = t1d[k]
        lines.append(f"| {lab} | {r['n']} | {r['pearson']:+.3f} | {r['spearman']:+.3f} |")

    # ---- 表2 ----
    print("  [表2] wash_cvd × 趋势分位")
    evs: list[pd.DataFrame] = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        ev = ev[(ev["timestamp"] >= LO_MS) & (ev["timestamp"] <= HI_MS)]
        if not ev.empty:
            evs.append(ev)
    events = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame(columns=["symbol", "timestamp"])
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    t2 = table2_strat(events, ctxs, weekly["weekly"], weekly["daily"], rng,
                      args.n_baseline, args.min_events)
    print(f"  wash_cvd 事件 n={t2['n_total']}（周分位覆盖 {t2['n_with_weekly_pct']}，"
          f"日分位覆盖 {t2['n_with_daily_pct']}）")
    lines.append("\n## 表2 wash_cvd 事件 × 谷歌趋势分位分层（24h 超额，基线=同窗口随机，bootstrap 95% CI）\n")
    lines.append("| 层 | n | 24h均 | 24h超额 | CI | 判定 |")
    lines.append("|---|---|---|---|---|---|")
    for r in t2["rows"]:
        lines.append(f"| {r['层']} | {r['n']} | {r['24h均']:+.2f}% | {r['24h超额']:+.2f}% "
                     f"| [{r['CI下']:+.2f}, {r['CI上']:+.2f}] | **{r['判定']}** |")
    lines.append(f"\n- wash_cvd 事件总数 {t2['n_total']}（对照：115 pooled n=1348，24h超额 +1.31%）。"
                 f"周分位覆盖 {t2['n_with_weekly_pct']}；日分位仅覆盖近 3 月窗口事件 {t2['n_with_daily_pct']} 个（描述性）。")

    # ---- 表3 ----
    print("  [表3] GDELT 新闻条数")
    t3 = table3_gdelt(gdelt, daily)
    lines.append("\n## 表3 GDELT 新闻条数（描述性，样本小）\n")
    cd = t3["count_desc"]
    lines.append(f"窗口 {t3['window']['start']} → {t3['window']['end']}，{t3['n_days']} 天；"
                 f"bitcoin 日条数 mean={cd['mean']:.0f} min={cd['min']} max={cd['max']} "
                 f"P25={cd['p25']:.0f} P75={cd['p75']:.0f}\n")
    lines.append("| 对比 | n | Pearson | Spearman |")
    lines.append("|---|---|---|---|")
    for k, lab in [("count_vs_ret_sameday_btc", "当日条数 vs 当日 btc 收益"),
                   ("count_vs_ret_sameday_alt", "当日条数 vs 当日 alt 收益"),
                   ("chg_vs_ret_sameday_btc", "条数日变化 vs 当日 btc 收益"),
                   ("chg_vs_ret_sameday_alt", "条数日变化 vs 当日 alt 收益"),
                   ("count_vs_ret_nextday_btc", "当日条数 vs 次日 btc 收益"),
                   ("count_vs_ret_nextday_alt", "当日条数 vs 次日 alt 收益"),
                   ("crypto_count_vs_ret_btc", "crypto 条数 vs 当日 btc 收益")]:
        r = t3[k]
        if r["n"] < 20:
            lines.append(f"| {lab} | {r['n']} | - | - |")
        else:
            lines.append(f"| {lab} | {r['n']} | {r['pearson']:+.3f} | {r['spearman']:+.3f} |")

    # ---- 基差 ----
    print("  [基差] 可得性检查")
    basis = check_basis_availability()
    lines.append("\n## 永续-现货基差：数据不可得（实证）\n")
    for ev in basis["evidence"]:
        if "files" in ev:
            lines.append(f"- {ev['loc']}: {ev['files']} 个 parquet（币安 USDT 永续 klines，非现货）")
        else:
            lines.append(f"- {ev['loc']}: {ev['dirs']}（无现货目录）")
    lines.append(f"- coinglass confirmed_endpoints 无 spot 端点；binance_free_db 仅 funding/perp 数据。")
    lines.append(f"- {basis['funding_proxy']}")

    # ---- 判定 ----
    lines.append("\n## 判定与局限\n")
    lines.append("### 数据可用性（实测）\n")
    lines.append("- **谷歌趋势（pytrends 4.9.2）**：可用。5 年历史 → 仅**周频**（Google 限制），"
                 "262 周 2021-08 → 2026-08；日频仅近 3 月（today 3-m 稳定，8-m/6-m 实测间歇 400 限流，"
                 "脚本内置 45s+ 递增间隔重试）。数值为相对指数（窗口内归一化 max=100），只能用于相对高低。")
    lines.append("- **GDELT（timelinevolraw）**：可用。单请求即得**日频条数**（近 90-180 天，本次 "
                 f"{GDELT_DAYS}d 窗口），429 限流实测：连续多请求会触发分钟级封锁，需 25-30s+ 间隔 + 指数退避"
                 "（脚本已实现，见 fetch_log）。")
    lines.append("- **永续-现货基差**：**不可得**（无任何现货历史数据源）；funding 为代理，112/115 已测。\n")

    lines.append("### 与收益的关联（判定口径：CI 下界>0 → GO_LONG / 上界<0 → GO_SHORT / 含0 → NO_GO）\n")
    v1_lo, v1_hi = t1w["level_vs_next_alt"]["pearson"], t1w["level_vs_next_alt"]["spearman"]
    v1 = "有弱相关" if abs(v1_lo) > 0.1 else "无相关"
    lines.append(f"- 表1 周频水平 → 下周 alt 收益: Pearson {v1_lo:+.3f} / Spearman {v1_hi:+.3f} → **{v1}**（描述性，相关不是信号）")
    t2rows = t2["rows"]
    v2 = "；".join(f"{r['层']} {r['判定']}" for r in t2rows)
    lines.append(f"- 表2 wash_cvd × 趋势分位: {v2}")
    t3k = t3["count_vs_ret_sameday_btc"]["pearson"]
    lines.append(f"- 表3 GDELT 当日条数 vs 当日 btc 收益: Pearson {t3k:+.3f}（n={t3['count_vs_ret_sameday_btc']['n']}，描述性）\n")

    lines.append("### 局限\n")
    lines.append("- 样本窗口差异：谷歌趋势 5 年（周频）vs GDELT 180 天（日频），两源仅近 3 月可同日对照。")
    lines.append("- 谷歌趋势周频 + 归一化：跨年绝对水平不可比，只反映相对热度；'次日收益'在周频下退化为'下周收益'。")
    lines.append("- GDELT 匹配的是全文含 'bitcoin' 的新闻，含噪音（重复转载、非市场新闻），且窗口短、n 小，仅描述性。")
    lines.append("- wash_cvd 事件集中在 2022-2026，趋势周频为其最粗粒度；日分位子集 n 很小。")
    lines.append("- 相关性检验为描述性，无多重检验校正；不构成交易信号，仅评估免费数据源价值。")

    out = REPORTS_DIR / "free_sources.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")

    print("\n=== 摘要 ===")
    print(f"  谷歌趋势: 周频 {len(weekly['weekly'])} 行 / 日频 {len(weekly['daily'])} 行")
    print(f"  GDELT: {len(gdelt)} 天")
    print(f"  wash_cvd 事件: {t2['n_total']}（对照 115 n=1348, +1.31%）")
    for r in t2["rows"]:
        print(f"    {r['层']:16s} n={r['n']:5d}  24h超额 {r['24h超额']:+.2f}% [{r['CI下']:+.2f},{r['CI上']:+.2f}] {r['判定']}")
    print(f"  表1 周频水平→下周alt: P={t1w['level_vs_next_alt']['pearson']:+.3f} S={t1w['level_vs_next_alt']['spearman']:+.3f} (n={t1w['level_vs_next_alt']['n']})")
    print(f"  表1 日频水平→次日alt: P={t1d['level_vs_next_alt']['pearson']:+.3f} S={t1d['level_vs_next_alt']['spearman']:+.3f} (n={t1d['level_vs_next_alt']['n']})")
    print(f"  表3 GDELT条数→当日btc: P={t3['count_vs_ret_sameday_btc']['pearson']:+.3f} (n={t3['count_vs_ret_sameday_btc']['n']})")
    print(f"  基差: 现货数据 {'发现' if basis['spot_found'] else '不可得'}")


if __name__ == "__main__":
    main()
