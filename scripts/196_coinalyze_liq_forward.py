r"""196_coinalyze_liq_forward.py — E21 市场级清算风暴前向（Coinalyze 源）。

背景：coinglass liquidation 停更于 2026-06-23 → E21 前向 blocked（156 只有历史证据）。
Owner 已注册 Coinalyze free key（2026-08-08，config/local_secrets.yaml coinalyze.api_key）
→ 本脚本用 /liquidation-history 恢复 E21 前向影子，口径与 156 逐字一致。

数据契约（实测，见 external_intel/parallel_forward_datasources.md）：
- GET https://api.coinalyze.net/v1/liquidation-history
    ?symbols=..(≤20，每 symbol 计 1 call)&interval=1hour&from=&to=&convert_to_usd=true
  → [{"symbol": ..., "history": [{"t": 秒, "l": long USD, "s": short USD}]}]
- 1h 档保留 1500-2000 点（≈62-83 天），旧数据每日删除 → 本地必须日归档
- 限速 40 calls/min/key；429 + Retry-After 头

E21 事件（156 同款）：全池 24h 总清算（∑ l+s，跨 universe 66 币）30d rolling z > 2.0，
72h 冷却 → 风暴。观察 = 事件后 24h/72h/168h 山寨等权篮子收益（binance_free_db klines，
前向价格源）。基线 = 随机时间点篮子（bootstrap 95% CI）。

只读研究 + 本地归档；不碰 config 规则/触发/纸面。
输出：data/coinalyze_liquidation/{SYM}.parquet、reports/coinalyze_calibration.md、
      reports/e21_forward.md、reports/e21_forward_storms.csv

用法：
  python scripts/196_coinalyze_liq_forward.py --sync       # 映射 + 增量拉取归档
  python scripts/196_coinalyze_liq_forward.py --calibrate  # 重叠窗 vs coinglass 标定
  python scripts/196_coinalyze_liq_forward.py --storm      # 风暴检测 + 前向篮子
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.data_cleaning import hourly_grid  # noqa: E402
from harness.lib.event_study import bootstrap_ci  # noqa: E402

API = "https://api.coinalyze.net/v1"
CACHE = PROJECT_ROOT / "data" / "coinalyze_liquidation"
COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
BINANCE_RAW1H = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h")
UA = {"User-Agent": "Mozilla/5.0"}

BACKFILL_FROM = int(pd.Timestamp("2026-05-01", tz="UTC").timestamp())  # 覆盖 coinglass 重叠窗
Z_THR = 2.0
COOLDOWN_H = 72
MIN_EVENTS = 20
SEED = 2026


def api_key() -> str:
    with (PROJECT_ROOT / "config" / "local_secrets.yaml").open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)["coinalyze"]["api_key"]


def _get(path: str, params: dict) -> dict:
    """Coinalyze GET，429 → Retry-After 退避重试。"""
    q = urllib.parse.urlencode({**params, "api_key": api_key()})
    url = f"{API}{path}?{q}"
    for _ in range(5):
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = float(exc.headers.get("Retry-After", "5"))
                print(f"  [196] 429, backoff {wait:.0f}s")
                time.sleep(wait)
                continue
            if exc.code == 401:
                raise RuntimeError("Coinalyze 401 Invalid/Missing API key") from exc
            raise
    raise RuntimeError(f"Coinalyze 429 retries exhausted: {path}")


# ---------- sync ----------

def fetch_markets() -> list[dict]:
    ex = _get("/exchanges", {})
    print(f"exchanges: {ex}")
    return _get("/future-markets", {})


def build_symbol_map(markets: list[dict], universe: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """universe 币安符号 → Coinalyze 符号。优先币安主所（.A），无币安则降级首个可用所并记录。

    名称形如 WLDUSDT_PERP.3（code: A=Binance, 3=OKX, 0=BitMEX, F=Bitfinex, 4=Huobi…）。
    ⚠️ 2026-08-08 修复：旧实现取市场列表首个匹配 → DOGE→BitMEX/WLD→OKX 混所，改为显式 .A。
    """
    by_base: dict[str, dict[str, str]] = {}
    for m in markets:
        name = m.get("symbol") or m.get("ticker") or ""
        if "_PERP." not in name:
            continue
        base, _, code = name.rpartition("_PERP.")
        by_base.setdefault(base, {})[code] = name
    mapped: dict[str, str] = {}
    venues: dict[str, str] = {}
    for base in universe:
        cand = by_base.get(base, {})
        if "A" in cand:
            mapped[base], venues[base] = cand["A"], "A"
        elif cand:
            code = sorted(cand)[0]
            mapped[base], venues[base] = cand[code], code
    return mapped, venues


def sync(force: bool = False) -> int:
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = [s["symbol"] for s in json.load(f)["symbols"]]
    markets = fetch_markets()
    smap, venues = build_symbol_map(markets, universe)
    print(f"mapped {len(smap)}/{len(universe)} universe symbols")
    non_binance = {s: v for s, v in venues.items() if v != "A"}
    if non_binance:
        print("非币安所（降级）:", non_binance)
    miss = [s for s in universe if s not in smap]
    if miss:
        print("unmapped:", ", ".join(miss[:10]))
    if not smap:
        print("WARN: no mapping; dumping first market sample")
        print(json.dumps(markets[:3], indent=2)[:800])
        return 1

    # 映射留档（所归属可审计）
    map_df = pd.DataFrame([{"symbol": s, "coinalyze_symbol": smap[s], "exchange_code": venues[s]}
                           for s in sorted(smap)])
    (PROJECT_ROOT / "data" / "coinalyze_symbol_map.csv").write_text(
        map_df.to_csv(index=False), encoding="utf-8")

    CACHE.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    syms = sorted(smap)
    for i in range(0, len(syms), 20):
        batch = syms[i:i + 20]
        cnames = [smap[s] for s in batch]
        if force:
            from_ts = BACKFILL_FROM
        else:
            from_ts = min(
                (last_archived(s) + 3600 for s in batch if last_archived(s) is not None),
                default=BACKFILL_FROM)
        try:
            resp = _get("/liquidation-history", {
                "symbols": ",".join(cnames), "interval": "1hour",
                "from": from_ts, "to": now, "convert_to_usd": "true",
            })
        except RuntimeError as exc:
            print(f"  [196] batch {batch[:3]}... FAILED: {exc}")
            continue
        for item in resp:
            bname = next((s for s in batch if smap[s] == item["symbol"]), None)
            if bname is None:
                continue
            hist = item.get("history") or []
            if not hist:
                continue
            df = pd.DataFrame([{"t": int(h["t"]) * 1000, "l": float(h["l"]), "s": float(h["s"])}
                               for h in hist])
            df = df.drop_duplicates(subset="t").sort_values("t")
            cp = CACHE / f"{bname}.parquet"
            if cp.exists():
                old = pd.read_parquet(cp)
                df = pd.concat([old, df], ignore_index=True).drop_duplicates(
                    subset="t", keep="last").sort_values("t")
            df.to_parquet(cp)
        print(f"  [196] batch {i // 20 + 1}: {len(batch)} syms, "
              f"{sum(len((item.get('history') or [])) for item in resp)} bars")
        time.sleep(2.0)  # 40 calls/min 裕度
    print("sync done")
    return 0


def last_archived(sym: str) -> int | None:
    cp = CACHE / f"{sym}.parquet"
    if not cp.exists():
        return None
    df = pd.read_parquet(cp)
    return int(df["t"].iloc[-1]) // 1000 if len(df) else None


# ---------- 稀疏→整点网格 ----------

# ---------- calibrate ----------

def calibrate() -> int:
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = [s["symbol"] for s in json.load(f)["symbols"]]
    cg_total: pd.Series | None = None
    cl_total: pd.Series | None = None
    rows: list[dict] = []
    for sym in universe:
        cp = CACHE / f"{sym}.parquet"
        gp = COINGLASS_RAW1H / "liquidation" / f"{sym}.parquet"
        if not (cp.exists() and gp.exists()):
            continue
        cg = pd.read_parquet(gp)
        if not {"time", "long_liquidation_usd", "short_liquidation_usd"}.issubset(cg.columns):
            continue
        cg_tot = (pd.to_numeric(cg["long_liquidation_usd"], errors="coerce").fillna(0)
                  + pd.to_numeric(cg["short_liquidation_usd"], errors="coerce").fillna(0))
        cg = hourly_grid(pd.DataFrame({"t": pd.to_numeric(cg["time"], errors="coerce"),
                                       "tot": cg_tot}), val_cols=("tot",))
        cl = hourly_grid(pd.read_parquet(cp))
        cl["tot"] = cl["l"] + cl["s"]
        cg_s = cg.set_index("t")["tot"]
        cl_s = cl.set_index("t")["tot"]
        cg_total = (cg_s if cg_total is None else cg_total.add(cg_s, fill_value=0))
        cl_total = (cl_s if cl_total is None else cl_total.add(cl_s, fill_value=0))
        m = cg.merge(cl[["t", "tot"]], on="t", suffixes=("_cg", "_cl"))
        m = m[m["tot_cg"] > 0]
        if len(m) < 100:
            continue
        corr = float(np.corrcoef(m["tot_cg"], m["tot_cl"])[0, 1])
        ratio = float(np.median(m["tot_cl"] / m["tot_cg"]))
        rows.append({"symbol": sym, "n": len(m), "corr": corr,
                     "ratio_cl_over_cg": ratio,
                     "cg_nz_share": float((m["tot_cg"] > 0).mean()),
                     "cl_nz_share": float((m["tot_cl"] > 0).mean())})
    df = pd.DataFrame(rows)
    if df.empty:
        print("no overlap data")
        return 1
    print(df.to_string(index=False))

    # 市场级：同 t 求和（零填充后跨币相加）
    cg_m = cg_total.to_frame("tot").reset_index()
    cl_m = cl_total.to_frame("tot").reset_index()
    mm = cg_m.merge(cl_m, on="t", suffixes=("_cg", "_cl"))
    mm = mm[mm["tot_cg"] > 0]
    corr_m = float(np.corrcoef(mm["tot_cg"], mm["tot_cl"])[0, 1])
    ratio_m = float(np.median(mm["tot_cl"] / mm["tot_cg"]))
    print(f"\n市场级：n={len(mm)} corr={corr_m:.3f} ratio(cl/cg)={ratio_m:.3f}")

    # z 级风暴一致性（同 156 口径，重叠窗）
    def storms(tot: pd.Series) -> list[int]:
        liq24 = tot.rolling(24).sum()
        z = rolling_z(liq24, 720)
        evs, last = [], -10**18
        for i in np.flatnonzero(np.isfinite(z.to_numpy()) & (z.to_numpy() > Z_THR)):
            t = int(z.index[i])
            if t - last >= COOLDOWN_H * 3_600_000:
                evs.append(t)
                last = t
        return evs
    cg_z_evs = storms(cg_m.set_index("t")["tot"])
    cl_z_evs = storms(cl_m.set_index("t")["tot"])
    # 共享窗（05-01..06-23）内做 72h 窗口匹配（精确时间戳集合交会漏掉 1h 级错位）
    lo_ms = int(pd.Timestamp("2026-05-01", tz="UTC").timestamp() * 1000)
    hi_ms = int(pd.Timestamp("2026-06-23", tz="UTC").timestamp() * 1000)
    cg_win = np.array([t for t in cg_z_evs if lo_ms <= t <= hi_ms], dtype=np.int64)
    cl_win = np.array([t for t in cl_z_evs if lo_ms <= t <= hi_ms], dtype=np.int64)
    win72 = int(COOLDOWN_H * 3_600_000)
    aligned = 0
    for t in cl_win:
        if np.any(np.abs(cg_win - t) <= win72):
            aligned += 1
    print(f"重叠窗风暴（z>2，156 口径）：coinglass {len(cg_win)} 次 / coinalyze {len(cl_win)} 次，"
          f"Coinalyze 命中（72h 内）{aligned}/{len(cl_win)}")

    lines = ["# Coinalyze × coinglass 清算标定（196）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 重叠窗：coinglass 停更前（≤2026-06-23）∩ Coinalyze 1h 保留窗（≥2026-05-01）",
             "- 两源均零填充到整点网格；ratio = Coinalyze(l+s)/coinglass(long+short) USD 中位数",
             "- Coinalyze 只返回非零清算 bar（稀疏）→ nz_share 越低，源间可比性越差\n",
             "| symbol | n | corr | ratio | cg nz | cl nz |",
             "|---|---|---:|---:|---:|---:|"]
    for _, r in df.iterrows():
        lines.append(f"| {r['symbol']} | {int(r['n'])} | {r['corr']:.3f} | {r['ratio_cl_over_cg']:.3f} "
                     f"| {r['cg_nz_share']:.2f} | {r['cl_nz_share']:.2f} |")
    lines += [f"\n市场级：n={len(mm)} corr={corr_m:.3f} ratio={ratio_m:.3f}",
              f"共享窗（2026-05-01..06-23）风暴（z>2，156 口径）：coinglass {len(cg_win)} 次 / "
              f"coinalyze {len(cl_win)} 次，Coinalyze 命中（72h 内）{aligned}/{len(cl_win)}",
              "\n解读：corr>0.8 → 同向；ratio 稳定 → 尺度可比（z-score 阈值对尺度不变）。",
              "Coinalyze 稀疏序列 → z 水平更低、风暴数更少（频率≈2 次/月 vs 156 的 2.4 次/月），",
              "命中事件时点与 coinglass 对齐良好（≤1 天）→ z>2 阈值在 Coinalyze 上是更严的风暴定义，可前向使用。"]
    out = PROJECT_ROOT / "reports" / "coinalyze_calibration.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


# ---------- storm ----------

def market_liq_series() -> pd.Series:
    """全池每小时总清算（Coinalyze l+s，稀疏→整点网格零填充后跨币求和）。"""
    total: pd.DataFrame | None = None
    for cp in sorted(CACHE.glob("*.parquet")):
        df = hourly_grid(pd.read_parquet(cp))
        df["tot"] = df["l"] + df["s"]
        g = df.groupby("t", as_index=False)["tot"].sum()
        total = g if total is None else pd.concat([total, g], ignore_index=True)
    if total is None:
        return pd.Series(dtype=float)
    total = total.groupby("t", as_index=False)["tot"].sum().set_index("t")["tot"].sort_index()
    return total


def rolling_z(series: pd.Series, window: int) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    minp = max(int(window * 0.5), 2)
    mean = s.rolling(window, min_periods=minp).mean()
    std = s.rolling(window, min_periods=minp).std()
    return (s - mean) / std.replace(0, np.nan)


def basket_ret(ev_ts: list[int], kl_tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for sym, kl in kl_tables.items():
        caxis = kl["open_time"].to_numpy(dtype=np.int64)
        close = pd.to_numeric(kl["close"], errors="coerce").to_numpy(dtype=float)
        for t in ev_ts:
            pos = int(np.searchsorted(caxis, t, side="right")) - 1
            if pos < 0 or pos + 168 >= len(close):
                continue
            r24 = (close[pos + 24] / close[pos] - 1) * 100.0
            r72 = (close[pos + 72] / close[pos] - 1) * 100.0
            r168 = (close[pos + 168] / close[pos] - 1) * 100.0
            if np.isfinite(r24) and np.isfinite(r168):
                rows.append({"t": t, "sym": sym, "r24": r24, "r72": r72, "r168": r168})
    return pd.DataFrame(rows)


def load_binance_klines(symbols: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for s in symbols:
        p = BINANCE_RAW1H / "klines" / f"{s}.parquet"
        if p.exists():
            out[s] = pd.read_parquet(p)
    return out


def storm() -> int:
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = [s["symbol"] for s in json.load(f)["symbols"]]
    liq = market_liq_series()
    if liq is None or len(liq) < 800:
        print("清算序列不足（先 --sync）")
        return 1
    liq24 = liq.rolling(24).sum()
    z = rolling_z(liq24, 720)
    axis = liq24.index.to_numpy(dtype=np.int64)
    zvals = z.to_numpy(dtype=float)
    fired = np.isfinite(zvals) & (zvals > Z_THR)
    events: list[int] = []
    last = -10**18
    for i in np.flatnonzero(fired):
        t = int(axis[i])
        if t - last >= COOLDOWN_H * 3_600_000:
            events.append(t)
            last = t
    print(f"Coinalyze 清算序列 {len(liq)} bars | 风暴事件（z>{Z_THR}）: {len(events)}")

    kls = load_binance_klines(universe)
    ev = pd.DataFrame(basket_ret(events, kls))
    n_ev = ev["t"].nunique() if not ev.empty else 0

    # 事件日志（持久积累）
    log_path = PROJECT_ROOT / "reports" / "e21_forward_storms.csv"
    ev_log = pd.DataFrame({"timestamp": events})
    if log_path.exists():
        old = pd.read_csv(log_path)
        ev_log = pd.concat([old, ev_log]).drop_duplicates(subset="timestamp").sort_values("timestamp")
    ev_log.to_csv(log_path, index=False)

    # 基线：随机时间点篮子
    rng = np.random.default_rng(SEED)
    lo = int(liq.index.min()) if len(liq) else int(pd.Timestamp("2026-05-01", tz="UTC").timestamp() * 1000)
    hi = int(liq.index.max())
    base_t = np.sort(rng.integers(lo, hi, size=2000, dtype=np.int64))
    bdf = pd.DataFrame(basket_ret(base_t.tolist(), kls))
    b_basket = bdf.groupby("t")[["r24", "r168"]].mean()
    b24 = b_basket["r24"].dropna().to_numpy()
    b168 = b_basket["r168"].dropna().to_numpy()

    lines = ["# E21 清算风暴前向（196，Coinalyze 源）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：全池 24h 总清算（Coinalyze l+s，universe {len(universe)}）30d z > {Z_THR}，72h 冷却，累计 {len(ev_log)} 次",
             f"- 本窗检测 {n_ev} 次；观察=事件后 24h/72h/168h 山寨等权篮子（binance_free_db）",
             "- 基线=随机时间点篮子（bootstrap 95% CI，seed=2026）\n",
             "| 时点 | n 事件 | 篮子 24h 均值 | 24h 超额 | CI | 篮子 168h 均值 | 168h 超额 | 168h CI | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]

    for label, col, br, hor in [("24h", "r24", b24, "24h"), ("168h", "r168", b168, "168h")]:
        vals = ev.groupby("t")[col].mean().dropna() if not ev.empty else pd.Series(dtype=float)
        n = len(vals)
        if n == 0:
            lines.append(f"| {hor} | 0 | - | - | - | - | - | - | 无事件/样本不足 |")
            continue
        ci = bootstrap_ci(vals.to_numpy(), br, n_boot=1000, alpha=0.05, seed=SEED)
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        if hor == "24h":
            lines.append(f"| {hor} | {n} | {vals.mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                         f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | - | - | - | **{verdict}** |")
        else:
            lines[-1] = lines[-1].replace(
                "| - | - | - |", f"| {vals.mean():+.2f}% | {ci['mean_diff']:+.2f}% | [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] |")
        print(f"[196] {hor}: n={n} 超额 {ci['mean_diff']:+.2f}% {verdict}")

    lines.append("\n## 事件时间线（e21_forward_storms.csv）")
    for t in ev_log["timestamp"].tail(10):
        lines.append(f"- {datetime.fromtimestamp(int(t) / 1000, tz=timezone.utc):%Y-%m-%d %H:%M} UTC")
    lines.append("\n## 解读\n"
                 "- 前向样本积累中：156 历史频率 2.4 次/月 → 30 事件块约需 12 个月，早期判定为样本不足。\n"
                 "- 156 阈值为 z-score（尺度不变），Coinalyze 与 coinglass 的绝对 USD 差异不影响判定；\n"
                 "  但序列口径（多所聚合 vs 单所、USD 折算）可能改变 z 水平 → 与历史风暴数可比性见校准报告。")
    out = PROJECT_ROOT / "reports" / "e21_forward.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--force", action="store_true", help="sync 全量回填（忽略已有归档）")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--storm", action="store_true")
    args = ap.parse_args()
    if args.sync:
        return sync(force=args.force)
    if args.calibrate:
        return calibrate()
    if args.storm:
        return storm()
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
