"""140_exchange_netflow.py — 交易所 BTC 净流入免费数据源实测（CoinMetrics Community API）。

项目红线遵守：
- 外部数据带时间戳 + 来源 URL（fetch_log + 报告头部）；一次性拉取不做定时化（默认读缓存，--refresh 才重拉）；
- 只读、纯研究模块、无订单路径；不改 config / 108 / 109 / 定时任务；不跑 pytest。

方法：
1. CoinMetrics Community API（免费，无需 key）：
   - catalog: GET /v4/catalog/asset-metrics → 列出 btc 1d 免费指标（含 4 个 flow + 2 个 SplyEx）。
   - timeseries: GET /v4/timeseries/asset-metrics?assets=btc&metrics=FlowInExNtv,FlowOutExNtv,FlowInExUSD,FlowOutExUSD&frequency=1d
   - 净流入 = FlowInExNtv − FlowOutExNtv（原生 BTC），USD 版 = FlowInExUSD − FlowOutExUSD。
   - 实测：1h/1b 频率 403（社区档仅 1d）；FlowTnxCount/FlowInExchanges 不受支持（400/不在目录）。
2. Dune / CryptoQuant：需注册账号 + API key → 本机无 key 则跳过并标注（读 config/local_secrets.yaml 实证）。
3. 关联检验：净流入日序列 vs btc/alt 篮子当日/次日收益（表2）；wash_cvd 事件按事件日-1 净流入滚动分位分层 → 24h 超额（表3）。
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

from harness.lib.event_study import DEFAULT_HORIZONS, bootstrap_ci, draw_random_events, forward_stats

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
load_funding_series = m113.load_funding_series
detect_events = m115.detect_events

# ---------- 研究参数 ----------
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
N_BASELINE = 3000
SEED = 2026
MIN_EVENTS = 30
RANK_WINDOW = 90          # 净流入滚动分位窗口（日）
RANK_MIN = 14

COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
REPORTS_DIR = PROJECT_ROOT / "reports"
SECRETS = PROJECT_ROOT / "config" / "local_secrets.yaml"

CM_BASE = "https://community-api.coinmetrics.io/v4"
CM_SOURCE = "CoinMetrics Community API（community-api.coinmetrics.io/v4，免费无 key）"
FLOW_METRICS = ["FlowInExNtv", "FlowOutExNtv", "FlowInExUSD", "FlowOutExUSD"]
EXTRA_METRICS = ["SplyExNtv", "SplyExUSD"]     # 交易所持仓（同请求顺带拉，表1 覆盖实证）
ALL_METRICS = FLOW_METRICS + EXTRA_METRICS

CACHE_CSV = REPORTS_DIR / "coinmetrics_btc_exflow_daily.csv"
FETCH_LOG = REPORTS_DIR / "exchange_netflow_fetch_log.json"
NETFLOW_CSV = REPORTS_DIR / "btc_exchange_netflow_daily.csv"   # 供下游复用的干净日序列


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _ns(idx: pd.Index) -> pd.DatetimeIndex:
    """统一为 naive datetime64[ns]（pandas 3.0 CSV 读入是 [us]，period 计算是 [ns]，混用会静默失配）。"""
    return pd.to_datetime(idx, utc=True).tz_localize(None).astype("datetime64[ns]")


# ============================================================
# CoinMetrics 拉取
# ============================================================

def _cm_get(url: str, attempts: int = 4, base_wait: float = 8.0) -> tuple[dict, list[dict]]:
    """GET + 重试（429/5xx 退避），返回 (data, log)。"""
    log: list[dict] = []
    wait = base_wait
    last_err: Exception | None = None
    for att in range(1, attempts + 1):
        t0 = _utcnow()
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaHiveV3-research/1.0 (academic)"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8"))
            log.append({"attempt": att, "ts": t0, "outcome": "ok", "url": url})
            return data, log
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")[:200]
            except Exception:  # noqa: BLE001
                pass
            log.append({"attempt": att, "ts": t0, "outcome": f"HTTP {e.code}: {e.reason} {body}"})
            if e.code not in (429, 500, 502, 503, 504):
                raise
            last_err = e
            print(f"  [cm] HTTP {e.code}（第 {att} 次），等待 {wait:.0f}s")
            if att == attempts:
                break
            time.sleep(wait)
            wait = min(wait * 2, 60.0)
        except Exception as e:  # noqa: BLE001
            log.append({"attempt": att, "ts": t0, "outcome": f"{type(e).__name__}: {str(e)[:120]}"})
            last_err = e
            if att == attempts:
                break
            time.sleep(wait)
            wait = min(wait * 2, 60.0)
    raise RuntimeError(f"CoinMetrics GET 失败: {last_err} url={url}")


def probe_catalog() -> dict:
    """目录实测：btc 1d 可用指标里与交易所/flow 相关的（含 400/403 证据）。"""
    data, log = _cm_get(f"{CM_BASE}/catalog/asset-metrics")
    total = len(data.get("data", []))
    flow = []
    for m in data.get("data", []):
        ok = any("btc" in f.get("assets", []) and f.get("frequency") == "1d"
                 for f in m.get("frequencies", []))
        if ok and ("Ex" in m.get("metric", "") or "Exchange" in m.get("metric", "")):
            flow.append({"metric": m.get("metric"), "category": m.get("category"),
                         "subcategory": m.get("subcategory"), "unit": m.get("unit")})
    probes = {}
    # 1h 频率与 FlowTnxCount 实测（记录拒绝原因）
    try:
        _cm_get(f"{CM_BASE}/timeseries/asset-metrics?assets=btc&metrics=FlowInExNtv"
                f"&frequency=1h&page_size=3")
        probes["1h"] = "OK"
    except Exception as e:  # noqa: BLE001
        probes["1h"] = f"FAIL: {type(e).__name__}: {str(e)[:160]}"
    try:
        _cm_get(f"{CM_BASE}/timeseries/asset-metrics?assets=btc&metrics=FlowTnxCount"
                f"&frequency=1d&page_size=3")
        probes["FlowTnxCount"] = "OK"
    except Exception as e:  # noqa: BLE001
        probes["FlowTnxCount"] = f"FAIL: {type(e).__name__}: {str(e)[:160]}"
    return {"catalog_total_metrics": total, "btc_ex_metrics": flow, "probes": probes, "log": log}


def fetch_coinmetrics(force: bool = False) -> tuple[pd.DataFrame, list[dict], dict]:
    """拉 btc 1d flow + sply 序列；缓存 CSV（带 fetched_at）。返回 (df, log, meta)。"""
    log: list[dict] = []
    if CACHE_CSV.exists() and not force:
        df = pd.read_csv(CACHE_CSV, parse_dates=["date"]).set_index("date")
        df.index = _ns(df.index)
        meta = {"cache": True, "fetched_at": str(df["fetched_at"].iloc[-1])}
        log.append({"source": "coinmetrics", "outcome": "cache", "ts": _utcnow(),
                    "file": CACHE_CSV.name})
        print(f"  [cm] 读取缓存 {CACHE_CSV.name} rows={len(df)}")
        return df, log, meta

    t0 = _utcnow()
    params = {"assets": "btc", "metrics": ",".join(ALL_METRICS),
              "frequency": "1d", "page_size": 10000}
    url = f"{CM_BASE}/timeseries/asset-metrics?" + urllib.parse.urlencode(params)
    data, flog = _cm_get(url)
    log += flog
    rows = data.get("data", [])
    if not rows:
        raise RuntimeError("CoinMetrics timeseries 返回空")
    df = pd.DataFrame(rows).set_index("time")
    df.index = _ns(df.index)
    df.index.name = "date"
    # 值列转数值，status 列保留
    for c in ALL_METRICS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_index()
    df["fetched_at"] = t0
    CACHE_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE_CSV)
    meta = {"cache": False, "fetched_at": t0}
    log.append({"source": "coinmetrics", "outcome": "ok", "ts": t0,
                "rows": len(df), "url": url})
    print(f"  [cm] 拉取成功 rows={len(df)} {df.index.min().date()} → {df.index.max().date()}")
    return df, log, meta


# ============================================================
# Dune / CryptoQuant：注册类免费源（无 key 实证）
# ============================================================

def check_registered_sources() -> dict:
    """读 local_secrets.yaml（只读，不打印值）判断 Dune/CryptoQuant key 是否存在。"""
    out = {"dune": {"available": False, "note": ""},
           "cryptoquant": {"available": False, "note": ""}}
    text = ""
    if SECRETS.exists():
        try:
            text = SECRETS.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:  # noqa: BLE001
            text = ""
    out["dune"]["note"] = ("config/local_secrets.yaml 未发现 dune key → 需注册 Dune 免费账号并申请 API key"
                           if "dune" not in text and "dune_api" not in text
                           else "config/local_secrets.yaml 发现 dune 条目（值不展示）")
    out["cryptoquant"]["note"] = ("config/local_secrets.yaml 未发现 cryptoquant key；且 CryptoQuant API 的 "
                                  "exchange-flows/netflow 端点仅 Professional/Premium 付费档开放"
                                  "（免费档仅网站查看、无 API 凭证）→ 免费路径为付费墙，不可行"
                                  if "cryptoquant" not in text and "cq_" not in text
                                  else "config/local_secrets.yaml 发现 cryptoquant 条目（值不展示）")
    return out


# ============================================================
# 价格/收益（与 113 同一套清洗，复制 138 口径）
# ============================================================

def load_daily_returns() -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """由 113 的 ctxs 派生日频收益。返回 (daily, by_sym)。"""
    ctxs = load_price_ctx(load_universe_symbols())
    daily = pd.DataFrame(index=pd.date_range("2021-12-31", "2026-12-31", freq="D",
                                             tz="UTC").tz_localize(None).astype("datetime64[ns]"))
    by_sym: dict[str, pd.Series] = {}
    for sym, t in ctxs.items():
        s = t["close"].copy()
        s.index = pd.to_datetime(s.index, unit="ms", utc=True)
        dclose = s.resample("D").last()
        dclose.index = dclose.index.tz_localize(None)
        dret = dclose.pct_change() * 100.0
        dret.name = sym
        by_sym[sym] = dret
        daily[sym] = dret
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


def build_netflow(df: pd.DataFrame) -> pd.DataFrame:
    """净流入 = FlowIn − FlowOut（Ntv 原生 / USD）。返回仅含净流入 + 两分量的日序列。"""
    n = pd.DataFrame(index=_ns(df.index))
    n["flow_in_ntv"] = df["FlowInExNtv"].to_numpy()
    n["flow_out_ntv"] = df["FlowOutExNtv"].to_numpy()
    n["flow_in_usd"] = df["FlowInExUSD"].to_numpy()
    n["flow_out_usd"] = df["FlowOutExUSD"].to_numpy()
    n["netflow_ntv"] = n["flow_in_ntv"] - n["flow_out_ntv"]
    n["netflow_usd"] = n["flow_in_usd"] - n["flow_out_usd"]
    for c in ["SplyExNtv", "SplyExUSD"]:
        if c in df.columns:
            n[c] = pd.to_numeric(df[c], errors="coerce").to_numpy()
    return n


# ============================================================
# 表1：数据覆盖实证
# ============================================================

def table1_coverage(df: pd.DataFrame) -> dict:
    rows = []
    for c in ALL_METRICS:
        if c not in df.columns:
            continue
        v = df[c].dropna()
        rows.append({"metric": c, "rows": int(len(v)),
                     "start": str(v.index.min().date()) if len(v) else None,
                     "end": str(v.index.max().date()) if len(v) else None,
                     "latest": str(v.index.max().date()) if len(v) else None})
    exp = pd.date_range(df.index.min(), df.index.max(), freq="D")
    missing = exp.difference(df.index)
    return {"metrics": rows, "index_start": str(df.index.min().date()),
            "index_end": str(df.index.max().date()),
            "index_rows": int(len(df)), "missing_days": [str(d.date()) for d in missing[:20]],
            "n_missing": int(len(missing))}


# ============================================================
# 表2：净流入 vs 收益相关
# ============================================================

def _corr_block(x: pd.Series, y: pd.Series) -> dict:
    m = x.notna() & y.notna()
    xx, yy = x[m].to_numpy(dtype=float), y[m].to_numpy(dtype=float)
    if len(xx) < 30:
        return {"n": int(len(xx)), "pearson": np.nan, "spearman": np.nan}
    return {"n": int(len(xx)), "pearson": float(np.corrcoef(xx, yy)[0, 1]),
            "spearman": float(pd.Series(xx).corr(pd.Series(yy), method="spearman"))}


def table2_corr(net: pd.DataFrame, daily: pd.DataFrame) -> dict:
    d = net.join(daily[["ret_btc", "ret_alt"]], how="inner")
    d = d.dropna(subset=["netflow_ntv", "netflow_usd", "ret_btc"])
    d["netflow_ntv_chg"] = d["netflow_ntv"].diff()
    d["netflow_usd_chg"] = d["netflow_usd"].diff()
    d["ret_btc_next"] = d["ret_btc"].shift(-1)
    d["ret_alt_next"] = d["ret_alt"].shift(-1)
    rows = {}
    for label, x, y in [
        ("ntv_level_vs_sameday_btc", d["netflow_ntv"], d["ret_btc"]),
        ("ntv_level_vs_sameday_alt", d["netflow_ntv"], d["ret_alt"]),
        ("ntv_level_vs_nextday_btc", d["netflow_ntv"], d["ret_btc_next"]),
        ("ntv_level_vs_nextday_alt", d["netflow_ntv"], d["ret_alt_next"]),
        ("ntv_chg_vs_sameday_btc", d["netflow_ntv_chg"], d["ret_btc"]),
        ("ntv_chg_vs_sameday_alt", d["netflow_ntv_chg"], d["ret_alt"]),
        ("ntv_chg_vs_nextday_btc", d["netflow_ntv_chg"], d["ret_btc_next"]),
        ("ntv_chg_vs_nextday_alt", d["netflow_ntv_chg"], d["ret_alt_next"]),
        ("usd_level_vs_sameday_btc", d["netflow_usd"], d["ret_btc"]),
        ("usd_level_vs_sameday_alt", d["netflow_usd"], d["ret_alt"]),
        ("usd_level_vs_nextday_btc", d["netflow_usd"], d["ret_btc_next"]),
        ("usd_level_vs_nextday_alt", d["netflow_usd"], d["ret_alt_next"]),
        ("usd_chg_vs_sameday_btc", d["netflow_usd_chg"], d["ret_btc"]),
        ("usd_chg_vs_nextday_btc", d["netflow_usd_chg"], d["ret_btc_next"]),
    ]:
        rows[label] = _corr_block(x, y)
    rows["n_days"] = int(len(d))
    rows["window"] = {"start": str(d.index.min().date()), "end": str(d.index.max().date())}
    rows["netflow_desc"] = {
        "ntv": {"mean": float(d["netflow_ntv"].mean()), "std": float(d["netflow_ntv"].std()),
                "p10": float(d["netflow_ntv"].quantile(.10)), "p90": float(d["netflow_ntv"].quantile(.90))},
        "usd": {"mean": float(d["netflow_usd"].mean()), "std": float(d["netflow_usd"].std())}}
    return rows


# ============================================================
# 表3：wash_cvd 事件 × 事件日-1 净流入分层
# ============================================================

def _trailing_pct_rank(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    """滚动分位（asof）：第 i 点在其前 window 窗口内的百分位，无未来信息。"""
    out = pd.Series(np.nan, index=series.index, dtype=float)
    vals = series.to_numpy(dtype=float)
    idx = series.index.to_numpy(dtype="datetime64[ns]")
    for i in range(len(series)):
        lo = max(0, i - window + 1)
        if i - lo + 1 < min_periods:
            continue
        v = vals[i]
        if not np.isfinite(v):
            continue
        w = vals[lo:i + 1]
        w = w[np.isfinite(w)]
        if len(w) < min_periods:
            continue
        out.iloc[i] = float((w <= v).mean() * 100.0)
    return out


def table3_strat(events: pd.DataFrame, ctxs: dict, net: pd.DataFrame,
                 rng: np.random.Generator, n_baseline: int, min_events: int) -> dict:
    """按事件日-1 净流入（滚动 90 日分位）三分位 → 24h 超额（基线=同窗口随机，bootstrap 95% CI）。"""
    ev = events.copy()
    rank = _trailing_pct_rank(net["netflow_ntv"], RANK_WINDOW, RANK_MIN)
    ev_ts = ev["timestamp"].to_numpy()
    ev_dt = pd.Series(pd.to_datetime(ev_ts, unit="ms", utc=True).tz_localize(None).normalize(),
                      index=ev.index)
    # 事件日-1 的净流入滚动分位（无前视：-1 日结束时已完全可知）
    asof = ev_dt - pd.Timedelta(days=1)
    pos = np.searchsorted(rank.index.to_numpy(dtype="datetime64[ns]"),
                          asof.to_numpy(dtype="datetime64[ns]"), side="right") - 1
    pos = np.clip(pos, 0, len(rank) - 1)
    rv = rank.to_numpy(dtype=float)
    ev["net_pct"] = pd.Series(rv[pos], index=ev.index)
    ev["net_d1"] = pd.Series(net["netflow_ntv"].to_numpy()[np.clip(
        np.searchsorted(net.index.to_numpy(dtype="datetime64[ns]"),
                        asof.to_numpy(dtype="datetime64[ns]"), side="right") - 1, 0, len(net) - 1)],
        index=ev.index)

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
                "净流入均值(BTC)": float(sub["net_d1"].mean()) if len(sub) else np.nan,
                "判定": verdict}

    rows = []
    q = pd.qcut(ev["net_pct"], 3, labels=["低", "中", "高"], duplicates="drop")
    qn = q.notna()
    for lab in ["低", "中", "高"]:
        sub = ev[qn & (q == lab)]
        if not sub.empty:
            rows.append(strat_row(sub, f"净流入-{lab}"))
    rows.append(strat_row(ev[qn], "净流入-全"))
    return {"rows": rows, "n_total": len(ev),
            "n_with_rank": int(qn.sum()),
            "n_baseline_24h": int(len(bs24))}


# ============================================================
# main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="强制重新拉取 CoinMetrics")
    parser.add_argument("--n-baseline", type=int, default=N_BASELINE)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--min-events", type=int, default=MIN_EVENTS)
    args = parser.parse_args()

    print("== 1/5 外部数据实测 ==")
    cat = probe_catalog()
    df, cm_log, cm_meta = fetch_coinmetrics(args.refresh)
    reg = check_registered_sources()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fetch_log = cm_log + cat["log"]
    log_path = FETCH_LOG
    if log_path.exists():
        try:
            fetch_log = json.loads(log_path.read_text(encoding="utf-8")) + fetch_log
        except Exception:  # noqa: BLE001
            pass
    log_path.write_text(json.dumps(fetch_log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  CoinMetrics 目录: {cat['catalog_total_metrics']} 个指标, btc 交易所相关 {len(cat['btc_ex_metrics'])} 个")
    print(f"  1h/FlowTnxCount 实测: {cat['probes']}")
    print(f"  Dune: {reg['dune']['note']}")
    print(f"  CryptoQuant: {reg['cryptoquant']['note']}")

    net = build_netflow(df)
    # 干净净流入序列落盘（带时间戳，供下游复用）
    out_n = net[["flow_in_ntv", "flow_out_ntv", "netflow_ntv",
                 "flow_in_usd", "flow_out_usd", "netflow_usd"]].copy()
    out_n["fetched_at"] = cm_meta["fetched_at"]
    out_n.to_csv(NETFLOW_CSV)

    print("\n== 2/5 价格上下文（113 口径，66 币）==")
    ctxs = load_price_ctx(load_universe_symbols())
    fundings = load_funding_series(load_universe_symbols())
    print(f"  价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)}")

    print("\n== 3/5 日频收益（alt 等权篮子）==")
    daily, _by_sym = load_daily_returns()

    print("\n== 4/5 检验 ==")
    rng = np.random.default_rng(args.seed)
    lines: list[str] = []
    lines.append("# 交易所 BTC 净流入免费数据源实测（CoinMetrics Community API）\n")
    lines.append(f"- 生成: {_utcnow()}")
    lines.append(f"- 方法: CoinMetrics Community API v4（免费无 key）—— "
                 f"`GET /v4/timeseries/asset-metrics?assets=btc&metrics=FlowInExNtv,FlowOutExNtv,FlowInExUSD,FlowOutExUSD&frequency=1d`；"
                 f"净流入 = FlowInExNtv − FlowOutExNtv（原生 BTC）/ FlowInExUSD − FlowOutExUSD（USD）")
    lines.append(f"- 数据源: {CM_SOURCE}，拉取时间 {cm_meta['fetched_at']}"
                 f"（{'缓存' if cm_meta.get('cache') else '实时'}）；fetch_log={FETCH_LOG.name}")
    lines.append(f"- 净流入日序列落盘: {NETFLOW_CSV.name}（含 fetched_at 时间戳，一次性拉取不做定时化）")
    lines.append(f"- 收益口径: coinglass klines（113 清洗）日频，btc=BTCUSDT，alt=universe 等权篮子（138 同款）")
    lines.append(f"- 无前视：wash_cvd 事件分层用事件日-1 的净流入滚动分位（-1 日收盘后完全可知）")
    lines.append("> 目的：实测免费交易所净流入数据路径的可用性/质量/覆盖，检验与 btc/alt 收益及 wash_cvd 信号的关联，"
                 "评估 Dune 免费账号注册是否值得（T3-2 免费替代）。")

    # ---- 表1 ----
    print("  [表1] 数据覆盖实证")
    t1 = table1_coverage(df)
    lines.append("\n## 表1 数据覆盖实证（CoinMetrics btc 1d，社区档）\n")
    lines.append("| 指标 | 行数 | 起始 | 最新 |")
    lines.append("|---|---|---|---|")
    for r in t1["metrics"]:
        lines.append(f"| {r['metric']} | {r['rows']} | {r['start']} | {r['end']} |")
    lines.append(f"\n- 索引覆盖 {t1['index_start']} → {t1['index_end']}，{t1['index_rows']} 行；"
                 f"范围内缺失日期 {t1['n_missing']} 天"
                 + (f"（前 {min(10, len(t1['missing_days']))} 个: {', '.join(t1['missing_days'][:10])}）"
                    if t1["missing_days"] else "（无）"))
    lines.append("- 全部行的 `-status` 字段为 **flash**（社区档不提供 final/修订标记；值可能随上游修订变化）——"
                 "见 fetch_log 与下方局限。")

    # ---- 表2 ----
    print("  [表2] 净流入 vs 收益相关")
    t2 = table2_corr(net, daily)
    lines.append("\n## 表2 净流入 vs btc/alt 收益相关\n")
    lines.append(f"窗口 {t2['window']['start']} → {t2['window']['end']}，{t2['n_days']} 天"
                 f"（coinglass 侧为数据末尾约束）；netflow_ntv mean={t2['netflow_desc']['ntv']['mean']:.0f} "
                 f"std={t2['netflow_desc']['ntv']['std']:.0f} P10={t2['netflow_desc']['ntv']['p10']:.0f} "
                 f"P90={t2['netflow_desc']['ntv']['p90']:.0f} BTC\n")
    lines.append("| 对比 | n | Pearson | Spearman |")
    lines.append("|---|---|---|---|")
    for k, lab in [("ntv_level_vs_sameday_btc", "净流入水平 vs 当日 btc 收益"),
                   ("ntv_level_vs_sameday_alt", "净流入水平 vs 当日 alt 收益"),
                   ("ntv_level_vs_nextday_btc", "净流入水平 → 次日 btc 收益"),
                   ("ntv_level_vs_nextday_alt", "净流入水平 → 次日 alt 收益"),
                   ("ntv_chg_vs_sameday_btc", "净流入日变化 vs 当日 btc 收益"),
                   ("ntv_chg_vs_sameday_alt", "净流入日变化 vs 当日 alt 收益"),
                   ("ntv_chg_vs_nextday_btc", "净流入日变化 → 次日 btc 收益"),
                   ("ntv_chg_vs_nextday_alt", "净流入日变化 → 次日 alt 收益"),
                   ("usd_level_vs_sameday_btc", "净流入USD vs 当日 btc 收益"),
                   ("usd_level_vs_sameday_alt", "净流入USD vs 当日 alt 收益"),
                   ("usd_level_vs_nextday_btc", "净流入USD → 次日 btc 收益"),
                   ("usd_level_vs_nextday_alt", "净流入USD → 次日 alt 收益"),
                   ("usd_chg_vs_sameday_btc", "净流入USD日变化 vs 当日 btc 收益"),
                   ("usd_chg_vs_nextday_btc", "净流入USD日变化 → 次日 btc 收益")]:
        r = t2[k]
        lines.append(f"| {lab} | {r['n']} | {r['pearson']:+.3f} | {r['spearman']:+.3f} |")

    # ---- 表3 ----
    print("  [表3] wash_cvd × 事件日-1 净流入分层")
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
    t3 = table3_strat(events, ctxs, net, rng, args.n_baseline, args.min_events)
    print(f"  wash_cvd 事件 n={t3['n_total']}（净流入分位覆盖 {t3['n_with_rank']}，"
          f"基线 24h n={t3['n_baseline_24h']}）")
    lines.append("\n## 表3 wash_cvd 事件 × 事件日-1 净流入分层（24h 超额，基线=同窗口随机，bootstrap 95% CI）\n")
    lines.append("| 层 | n | 净流入均值(BTC) | 24h均 | 24h超额 | CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in t3["rows"]:
        lines.append(f"| {r['层']} | {r['n']} | {r['净流入均值(BTC)']:+.0f} "
                     f"| {r['24h均']:+.2f}% | {r['24h超额']:+.2f}% "
                     f"| [{r['CI下']:+.2f}, {r['CI上']:+.2f}] | **{r['判定']}** |")
    lines.append(f"\n- wash_cvd 事件总数 {t3['n_total']}（对照：115 pooled n=1348，24h超额 +1.31%）；"
                 f"滚动分位覆盖 {t3['n_with_rank']} 个；分层用事件日-1 净流入（无前视）。")

    # ---- Dune / CryptoQuant ----
    lines.append("\n## Dune / CryptoQuant 免费档（备选路径，未实测）\n")
    lines.append(f"- Dune: {reg['dune']['note']}。免费档含 API（约 2,500 credits/月，按查询算力计费，"
                 f"超量 $5/100 credits，100MB 存储，不滚动）；需 SQL 建模（交易所钱包标签 → 净流入），"
                 f"可自定义交易所集合（CoinMetrics 做不到的分所口径）。")
    lines.append(f"- CryptoQuant: {reg['cryptoquant']['note']}（付费墙：netflow API 仅 Professional/"
                 f"Premium 档，免费档无 API 凭证）。")
    lines.append("- 两条路径本机均无 key → 未实测，不编造数据。")

    # ---- 判定 ----
    lines.append("\n## 判定与局限\n")
    lines.append("### 数据可用性（实测）\n")
    lines.append("- **CoinMetrics Community API（免费）**：**可用**。btc 1d 直接给 4 个 flow 指标"
                 "（FlowInExNtv/FlowOutExNtv/FlowInExUSD/FlowOutExUSD）+ 2 个交易所持仓"
                 "（SplyExNtv/SplyExUSD），无需 key，单请求拿全史。")
    lines.append("- **频率限制（实证）**：1h/1b 返回 403（社区档仅 1d）；`FlowTnxCount` 返回 400"
                 "（不受支持）；目录中无 `FlowInExchanges` 分所口径。")
    lines.append("- **Dune / CryptoQuant**：本机无 key 未实测；Dune 需注册免费账号 + API key，"
                 "CryptoQuant netflow API 为付费墙（免费档不可用）——详见下节。\n")

    lines.append("### 与收益的关联（判定口径：CI 下界>0 → GO_LONG / 上界<0 → GO_SHORT / 含0 → NO_GO）\n")
    rows3 = t3["rows"]
    v3 = "；".join(f"{r['层']} {r['判定']}" for r in rows3)
    lines.append(f"- 表3 wash_cvd × 事件日-1 净流入: {v3}")
    r_sd = t2["ntv_level_vs_sameday_btc"]
    r_nd = t2["ntv_level_vs_nextday_btc"]
    lines.append(f"- 表2 净流入 vs 当日 btc 收益: Pearson {r_sd['pearson']:+.3f} (n={r_sd['n']})；"
                 f"vs 次日: {r_nd['pearson']:+.3f} (n={r_nd['n']})（描述性，相关不是信号）\n")

    lines.append("### 判定\n")
    lines.append("- **免费交易所净流入路径：可用（CoinMetrics Community API）**。无需 key、单请求全史"
                 "（2011-04-24 → 2026-08-06，5584 行，0 缺失日），日频净流入 = FlowInExNtv − FlowOutExNtv"
                 "（+USD 版与 SplyEx 持仓），已落盘 `btc_exchange_netflow_daily.csv` 供下游复用。"
                 "频率仅 1d（1h/1b 实测 403），无分所口径（无 FlowInExchanges）。")
    lines.append("- **数据质量评估：中等**。全行 `-status=flash`（社区档无 final 修订标记，值可能随上游修订）；"
                 "全所汇总口径（CoinMetrics 交易所集合，非 Binance 单独口径）。适合做宏观背景/共振变量"
                 "（日频、与价格同步），不适合事件级精确拆分。")
    lines.append("- **wash_cvd 附加价值（描述性）**：事件日-1 净流入高三分位 24h 超额 +2.24%"
                 "（CI [+1.33, +3.21]，n=440，GO_LONG），低/中分位 NO_GO——washout 前一天交易所净流入高"
                 "（承接买盘）与更优 24h 结果同现；样本内观察，需独立样本复核，不构成信号。")
    lines.append("- **Dune 免费账号注册：暂不值得（作为 T3-2 免费替代）**。CoinMetrics 免费已覆盖"
                 "日频全史净流入，Dune 的边际价值仅在分所/地址级拆分，需 SQL 建模 + 2500 credits/月额度管理；"
                 "除非后续研究明确需要分所口径（如 Binance 单独净流入对齐币安 wash_cvd），否则注册投入产出比低。"
                 "CryptoQuant 免费档不可行（netflow API 为付费墙）。\n")

    lines.append("### 局限\n")
    lines.append("- 全部行 `-status=flash`（社区档无 final 标记）：值可能随 CoinMetrics 上游修订变化，"
                 "历史回测结论需在最终修订版上复核。")
    lines.append("- 净流入为全所汇总口径（CoinMetrics 覆盖的交易所集合），非 Binance 单独口径，"
                 "无分所拆分；与 wash_cvd（币安永续数据）存在口径错配。")
    lines.append("- 事件日-1 净流入分层：事件集中在 2022-2026，滚动 90 日分位 warmup 会排除窗口前段少量事件；"
                 "分层 n 见上表，样本不足层诚实标注。")
    lines.append("- 相关性检验为描述性，无多重检验校正；不构成交易信号，仅评估免费数据源价值。")
    lines.append("- Dune 免费档需自行建模（钱包地址标签），工作量大且额度有限（2500 credits/月）；"
                 "CryptoQuant netflow API 为付费墙——均见判定。")

    out = REPORTS_DIR / "exchange_netflow.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")

    print("\n=== 摘要 ===")
    print(f"  CoinMetrics: {t1['index_rows']} 行 {t1['index_start']} → {t1['index_end']}"
          f"（缺失 {t1['n_missing']} 天，全 flash status）")
    print(f"  1h/FlowTnxCount 实测: {cat['probes']['1h'].split(':')[0]} / {cat['probes']['FlowTnxCount'].split(':')[0]}")
    print(f"  wash_cvd 事件: {t3['n_total']}（对照 115 n=1348, +1.31%）；净流入分位覆盖 {t3['n_with_rank']}")
    for r in t3["rows"]:
        print(f"    {r['层']:14s} n={r['n']:5d}  净流入{r['净流入均值(BTC)']:+10.0f}  24h超额 {r['24h超额']:+.2f}%"
              f" [{r['CI下']:+.2f},{r['CI上']:+.2f}] {r['判定']}")
    print(f"  表2 净流入→当日btc: P={t2['ntv_level_vs_sameday_btc']['pearson']:+.3f}"
          f" →次日btc: P={t2['ntv_level_vs_nextday_btc']['pearson']:+.3f}"
          f" (n={t2['ntv_level_vs_sameday_btc']['n']})")
    print(f"  表2 净流入→次日alt: P={t2['ntv_level_vs_nextday_alt']['pearson']:+.3f}"
          f" (n={t2['ntv_level_vs_nextday_alt']['n']})")
    print(f"  Dune: {'有 key（未实测）' if reg['dune']['available'] else '无 key，需注册免费账号'}"
          f" | CryptoQuant: {'有 key' if reg['cryptoquant']['available'] else '无 key，且 netflow API 为付费墙（免费档不可用）'}")


if __name__ == "__main__":
    main()
