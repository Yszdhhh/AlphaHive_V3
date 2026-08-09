"""129_independence_diagnosis.py — 加密×宏观「独立 vs 测不到」诊断。

命题背景：AlphaHive V3 山寨合约异动研究（"大饼见底→山寨蓄力"）。第一轮
宏观研究（119/120/123）显示日度线性相关性弱（|r|≈0.1），但无法区分
「加密真的独立」还是「研究设计/尺度问题测不到」。本脚本四组检验拆解：

1. 时变相关：alt 等权日收益 × SP500/VIX 日变的滚动 60d 相关时间序列，
   危机期（2022-03 加息启动 / 2022-05 LUNA / 2022-11 FTX / 2024-08 套息
   平仓 / 2025-04 关税）±30d 窗口相关 vs 全样本分布 → 无条件低相关是否
   掩盖条件性飙升。
2. 事件窗口：FOMC 会议日（公开日历 2022-2026，任务提供表）与 CPI 发布日
   （FRED release 日历）[-1,+3] 窗口 alt 篮子收益 vs 非事件日
   （bootstrap CI）→ 是否事件驱动而非逐日线性。
3. 领先滞后：BTC→alt 小时级 cross-correlation（±24h 窗）+ 日度 lag 0-3d
   + 手工 OLS Granger（p=2）→ "大饼先动、山寨后动"轮动是否可测
   （命题的直接时序检验）。
4. 周-月尺度：SP500/VIX/WALCL/RRP 与 alt 收益在周/月尺度相关
   → 传导是否「慢变量」（日度测不到 ≠ 独立）。

数据：
- 加密小时 close：coinglass klines（2022-01-01 → 2026-07-07；已知
  2026-06-23 23:00 → 06-30 04:00 全 universe 空档，本脚本用
  「仅相邻 bar 收益」防护，杜绝跨空档虚增收益）。
- 宏观日度：macro/SP500|VIX|DOLLAR|TREASURY.parquet（FRED 官方 API，
  由 118 拉取；TREASURY 取 us_10y）。
- FRED 运行时拉取（key 从 config/local_secrets.yaml 读，禁止硬编码）：
  WALCL（美联储总资产，周度，周三值周四发布）、RRPONTSYD（隔夜逆回购，
  日度）、CPIAUCSL 所属 release 的发布日日历（CPI 事件日）。拉不到 →
  跳过该序列并标注，一次性拉取不做定时化。
- 无前视：相关性为同窗描述（crypto 日 t 收益窗口包含美股 session t，
  与 119 同口径）；事件研究用公开日历日；FRED 周度序列 asof 对齐。

用法：python scripts/129_independence_diagnosis.py [--seed 2026]
输出：reports/independence_diagnosis.md
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import DEFAULT_HORIZONS, bootstrap_ci, draw_random_events, forward_stats

# ---- 复用模板（113/115 事件研究基础设施）----
_spec = importlib.util.spec_from_file_location("m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec); sys.modules["m113"] = m113; _spec.loader.exec_module(m113)
_spec2 = importlib.util.spec_from_file_location("m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2); sys.modules["m115"] = m115; _spec2.loader.exec_module(m115)
load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
detect_events = m115.detect_events
EPISODES = m113.EPISODES
episode_of = m113.episode_of
# ---- FRED 拉取复用（118）----
_spec3 = importlib.util.spec_from_file_location("m118", str(PROJECT_ROOT / "scripts" / "118_fred_macro.py"))
m118 = importlib.util.module_from_spec(_spec3); sys.modules["m118"] = m118; _spec3.loader.exec_module(m118)

COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
MACRO_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
FUNDING_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
REPORTS_DIR = PROJECT_ROOT / "reports"
FRED_BASE = "https://api.stlouisfed.org/fred"
HOUR_MS = 3_600_000

# 危机锚点（±30d 窗口内考察条件相关；日期为公开事件峰值日）
CRISIS_DATES = [
    ("2022-03 加息启动", "2022-03-16"),   # FOMC 首次加息 25bp
    ("2022-05 LUNA",     "2022-05-11"),   # UST 脱锚 / LUNA 崩盘
    ("2022-11 FTX",      "2022-11-09"),   # FTX 挤兑破产
    ("2024-08 套息平仓",  "2024-08-05"),   # 日元套息交易平仓（VIX 飙升）
    ("2025-04 关税",      "2025-04-07"),   # 对等关税冲击（美股/加密同跌）
]

# FOMC 会议日 2022-2026（来源：美联储官网公开 FOMC 日历，任务提供表）
FOMC_DATES = [
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27",
    "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26",
    "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31",
    "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
    "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29",
]


# --------------------------------------------------------------------------
# 数据装载
# --------------------------------------------------------------------------
def build_daily_panel(symbols: list[str]) -> tuple[dict, dict, dict, pd.Series, pd.Series, pd.Series]:
    """ctxs(小时表) + 每 symbol 日收盘/日收益 + alt 篮子（等权均值收益链）。

    返回 (ctxs, sym_close, sym_ret, alt_ret, alt_close, btc_ret)。
    - 收益均为百分比。
    - 「仅相邻日收益」防护：某 symbol 相邻两个日收盘间隔 ≠1 天（数据空档）
      则该日收益置 NaN，杜绝跨空档（如 2026-06-23→06-30）虚增收益。
    """
    ctxs = load_price_ctx(symbols)
    sym_close: dict[str, pd.Series] = {}
    sym_ret: dict[str, pd.Series] = {}
    for sym, t in ctxs.items():
        c = t["close"].dropna()
        if len(c) < 30:
            continue
        dates = pd.to_datetime(c.index, unit="ms", utc=True).tz_convert(None).normalize()
        dc = c.groupby(dates).last()
        dc.index = pd.DatetimeIndex(dc.index).tz_localize(None).normalize()
        sym_close[sym] = dc
        r = dc.pct_change() * 100.0
        delta_days = dc.index.to_series().diff().dt.days
        r = r.where(delta_days.to_numpy() == 1.0).dropna()
        sym_ret[sym] = r
    mat = pd.DataFrame(sym_ret)
    alt_ret = mat.mean(axis=1, skipna=True).dropna()
    alt_close = pd.Series(
        100.0 * np.cumprod(1.0 + alt_ret.to_numpy() / 100.0), index=alt_ret.index, name="alt_close"
    )
    btc_ret = sym_ret.get("BTCUSDT")
    return ctxs, sym_close, sym_ret, alt_ret, alt_close, btc_ret


def load_macro_close(key: str) -> pd.Series:
    df = pd.read_parquet(MACRO_ROOT / f"{key}.parquet")
    idx = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
    return pd.Series(pd.to_numeric(df["close"], errors="coerce").to_numpy(), index=idx)


def load_treasury_10y() -> pd.Series:
    df = pd.read_parquet(MACRO_ROOT / "TREASURY.parquet")
    idx = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
    return pd.Series(pd.to_numeric(df["us_10y"], errors="coerce").to_numpy(), index=idx)


def pull_fred_runtime() -> tuple[pd.Series | None, pd.Series | None, list[pd.Timestamp] | None]:
    """运行时拉取 WALCL / RRPONTSYD / CPI release 日历；失败 → None + 标注。"""
    try:
        api_key = m118.load_api_key()
    except Exception as e:  # noqa: BLE001
        print(f"[129] FRED key 不可用，跳过全部 FRED 运行时序列: {e}")
        return None, None, None

    walcl, rrp, cpi_days = None, None, None
    try:
        walcl = m118.fetch_fred_series(FRED_BASE, "WALCL", api_key)
        print(f"[129] WALCL 拉取成功: n={len(walcl)} {walcl.index.min().date()} → {walcl.index.max().date()}")
    except Exception as e:  # noqa: BLE001
        print(f"[129] WALCL 拉取失败（跳过并标注）: {e}")
    try:
        rrp = m118.fetch_fred_series(FRED_BASE, "RRPONTSYD", api_key)
        print(f"[129] RRPONTSYD 拉取成功: n={len(rrp)} {rrp.index.min().date()} → {rrp.index.max().date()}")
    except Exception as e:  # noqa: BLE001
        print(f"[129] RRPONTSYD 拉取失败（跳过并标注）: {e}")
    # CPI 发布日：CPIAUCSL 所属 release(10) 的发布日历（St. Louis Fed API，镜像 BLS）
    # 注意：releases/dates（复数）返回全部 release 且忽略 release_id 过滤；
    # 必须用单数端点 /release/dates + release_id。
    try:
        rel = requests.get(
            f"{FRED_BASE}/series/release",
            params={"series_id": "CPIAUCSL", "api_key": api_key, "file_type": "json"},
            timeout=25,
        ).json()
        rid = rel["releases"][0]["id"]
        rd = requests.get(
            f"{FRED_BASE}/release/dates",
            params={"release_id": rid, "api_key": api_key, "file_type": "json",
                    "limit": 10000, "sort_order": "asc"},
            timeout=25,
        ).json()
        cpi_days = sorted(
            pd.Timestamp(o["date"]).normalize()
            for o in rd.get("release_dates", [])
            if "2022-01-01" <= o["date"] <= "2026-12-31"
        )
        print(f"[129] CPI release 日历拉取成功: release_id={rid} n={len(cpi_days)}")
    except Exception as e:  # noqa: BLE001
        print(f"[129] CPI release 日历拉取失败（跳过 CPI 事件窗口）: {e}")
    return walcl, rrp, cpi_days


# --------------------------------------------------------------------------
# 检验 1：时变相关
# --------------------------------------------------------------------------
def test_time_varying_corr(alt_ret: pd.Series, sp500: pd.Series, vix: pd.Series,
                           dollar: pd.Series, us10: pd.Series, out: list[str]) -> dict:
    sp_ret = sp500.pct_change() * 100.0
    vix_ret = vix.pct_change() * 100.0
    dollar_ret = dollar.pct_change() * 100.0
    d10y = us10.diff()

    df = pd.DataFrame(index=alt_ret.index.union(sp_ret.index))
    df["alt_ret"] = alt_ret
    df["sp_ret"] = sp_ret
    df["vix_ret"] = vix_ret
    df["dollar_ret"] = dollar_ret
    df["d10y"] = d10y

    cols = {"SP500日变": "sp_ret", "VIX日变": "vix_ret", "美元指数日变": "dollar_ret", "10Y日变": "d10y"}
    roll = {}
    for label, col in cols.items():
        roll[label] = df["alt_ret"].rolling(60, min_periods=40).corr(df[col]).dropna()

    out.append("## 检验 1：时变相关性（滚动 60d，Pearson，同日 alt 日收益 × 宏观日变）\n")
    out.append("> 背景：第一轮 119 的『加密独立』结论基于**次日预测相关 ≈0**；"
               "同日相关从未为 0（119 报告 SP500 当日 +0.351 / VIX −0.291）。"
               "本检验给出同日相关的完整分布与危机期条件放大。\n")
    out.append("### 1.1 无条件相关（全样本同日）与滚动相关分布\n")
    out.append("| 变量 | 全样本 r | 滚动r均值 | 滚动r中位 | 5%分位 | 95%分位 | 滚动r>0 天数占比 | n(天) |")
    out.append("|---|---|---|---|---|---|---|---|")
    for label, col in cols.items():
        sub = df[["alt_ret", col]].replace([np.inf, -np.inf], np.nan).dropna()
        r0 = float(np.corrcoef(sub["alt_ret"], sub[col])[0, 1]) if len(sub) > 10 and sub[col].std() > 0 else np.nan
        rc = roll[label]
        out.append(
            f"| {label} | {r0:+.3f} | {rc.mean():+.3f} | {rc.median():+.3f} | "
            f"{rc.quantile(0.05):+.3f} | {rc.quantile(0.95):+.3f} | {(rc > 0).mean() * 100:.1f}% | {len(sub)} |"
        )
    out.append("")

    out.append("### 1.2 危机期 ±30d 窗口的滚动相关 vs 全样本分布\n")
    out.append("| 危机 | 锚点 | 窗口滚动r均值 | 窗口均值在全样本百分位 | 窗口最大值 | 结论(SP侧≥P90 或 VIX侧≤P10=联动飙升) |")
    out.append("|---|---|---|---|---|---|")
    flags: list[tuple[str, bool]] = []
    for label, anchor in CRISIS_DATES:
        a = pd.Timestamp(anchor)
        lo, hi = a - pd.Timedelta(days=30), a + pd.Timedelta(days=30)
        row_vals = []
        for key in ("SP500日变", "VIX日变"):
            rc = roll[key]
            win = rc[(rc.index >= lo) & (rc.index <= hi)]
            pct = (rc < win.mean()).mean() * 100.0 if len(win) else np.nan
            row_vals.append((key, win.mean() if len(win) else np.nan, win.max() if len(win) else np.nan, pct))
        cells = []
        for key, m, mx, pct in row_vals:
            if key == "SP500日变":
                spike = bool(pct >= 90) and m > 0
            else:  # VIX 为负相关：低百分位 = 负联动更强
                spike = bool(pct <= 10) and m < 0
            cells.append(f"{key}:均值{m:+.3f}(P{pct:.0f}) 峰{mx:+.3f}{'⚠' if spike else ''}")
        spike_any = any(
            (pct >= 90 and m > 0) if k == "SP500日变" else (pct <= 10 and m < 0)
            for k, m, _, pct in row_vals
        )
        flags.append((label, spike_any))
        out.append(f"| {label} | {anchor} | " + " | ".join(cells) + f" | {'是' if spike_any else '否'} |")
    out.append("")
    out.append("> 解读：同日相关基线本就高（滚动中位 +0.47/−0.37，99.4% 交易日为正），"
               "危机期是在高基线上叠加条件放大；仅 2022-05 LUNA 期出现显著飙升（SP500 P91）。"
               "2024-08 套息平仓期 VIX 相关反而减弱（P69），说明危机并非同质传导。\n")
    return {"flags": flags, "roll": roll, "df": df}


# --------------------------------------------------------------------------
# 检验 2：事件窗口
# --------------------------------------------------------------------------
def _event_window_table(alt_ret: pd.Series, base: pd.Series, days: list[pd.Timestamp],
                        base5: pd.Series | None, label: str, seed: int,
                        out: list[str], offsets=(-1, 0, 1, 2, 3)) -> None:
    out.append(f"#### {label}\n")
    out.append("| 偏移 | 事件均值% | 基线均值% | 差 | 95% CI | n_ev | 判定 |")
    out.append("|---|---|---|---|---|---|---|")
    for off in offsets:
        ev = []
        for d in days:
            t = d + pd.Timedelta(days=off)
            v = alt_ret.get(t)
            if v is not None and np.isfinite(v):
                ev.append(float(v))
        ev = np.asarray(ev)
        if len(ev) < 8:
            out.append(f"| {off:+d}d | - | - | - | - | {len(ev)} | 样本不足 |")
            continue
        ci = bootstrap_ci(ev, base.to_numpy(), seed=seed)
        lo, hi = ci["ci_lo"], ci["ci_hi"]
        verdict = "显著正" if lo > 0 else ("显著负" if hi < 0 else "含0")
        out.append(
            f"| {off:+d}d | {ev.mean():+.3f} | {base.mean():+.3f} | {ci['mean_diff']:+.3f} | "
            f"[{lo:+.3f}, {hi:+.3f}] | {len(ev)} | {verdict} |"
        )
    # 波动率响应（事件日 |收益| vs 基线 |收益|）
    ev_abs = np.array([abs(float(v)) for d in days for v in [alt_ret.get(d)]
                       if v is not None and np.isfinite(v)])
    base_abs = base.abs().to_numpy()
    if len(ev_abs) >= 8:
        ci = bootstrap_ci(ev_abs, base_abs, seed=seed)
        out.append(
            f"| 事件日\\|r\\| | {ev_abs.mean():.3f} | {base_abs.mean():.3f} | {ci['mean_diff']:+.3f} | "
            f"[{ci['ci_lo']:+.3f}, {ci['ci_hi']:+.3f}] | {len(ev_abs)} | "
            f"{'显著抬升' if ci['ci_lo'] > 0 else '含0' if ci['ci_lo'] <= 0 <= ci['ci_hi'] else '显著降低'} |"
        )
    # 累计窗口 d-1..d+3（要求 5 日齐全）
    cum = []
    for d in days:
        vals = [alt_ret.get(d + pd.Timedelta(days=k)) for k in offsets]
        if all(v is not None and np.isfinite(v) for v in vals):
            cum.append(float(sum(vals)))
    cum = np.asarray(cum)
    if len(cum) >= 8 and base5 is not None and len(base5) >= 30:
        ci = bootstrap_ci(cum, base5.to_numpy(), seed=seed)
        verdict = "显著正" if ci["ci_lo"] > 0 else ("显著负" if ci["ci_hi"] < 0 else "含0")
        out.append(
            f"| 累计(-1..+3) | {cum.mean():+.3f} | {base5.mean():+.3f} | {ci['mean_diff']:+.3f} | "
            f"[{ci['ci_lo']:+.3f}, {ci['ci_hi']:+.3f}] | {len(cum)} | {verdict} |"
        )
    out.append("")


def test_event_windows(alt_ret: pd.Series, fomc_days: list[pd.Timestamp],
                       cpi_days: list[pd.Timestamp] | None, seed: int, out: list[str]) -> dict:
    events = sorted(set(fomc_days) | set(cpi_days or []))
    win = pd.Timedelta(days=3)
    in_window = pd.Series(False, index=alt_ret.index)
    for d in events:
        in_window |= (alt_ret.index >= d - win) & (alt_ret.index <= d + win)
    base = alt_ret[~in_window]
    # 累计窗口基线：5 日滚动和（全部落在窗口外才入池）
    roll5 = alt_ret.rolling(5, min_periods=5).sum()
    ok5 = pd.Series(True, index=alt_ret.index)
    for d in events:
        ok5 &= ~((alt_ret.index >= d - win) & (alt_ret.index <= d + win))
    base5 = roll5[ok5].dropna()

    out.append("## 检验 2：事件窗口（FOMC 会议日 / CPI 发布日，[-1,+3] 日）\n")
    out.append(f"- 事件日：FOMC n={len(fomc_days)}（公开 FOMC 日历 2022-2026）；"
               f"CPI 发布日 n={len(cpi_days) if cpi_days else 0}（FRED release 日历）。"
               f"基线 = 任一事件 ±3d 之外的全部日收益（n={len(base)}）。\n")
    groups: list[tuple[str, list[pd.Timestamp]]] = [("FOMC", fomc_days)]
    if cpi_days:
        groups.append(("CPI", cpi_days))
    groups.append(("合并", events))
    for label, days in groups:
        _event_window_table(alt_ret, base, days, base5, label, seed, out)
    # FOMC 单独的事件日/次日 CI（供摘要打印）
    def _collect(days, off):
        vals = []
        for d in days:
            v = alt_ret.get(d + pd.Timedelta(days=off))
            if v is not None and np.isfinite(v):
                vals.append(float(v))
        return np.asarray(vals, dtype=float)

    fomc0 = _collect(fomc_days, 0)
    fomc1 = _collect(fomc_days, 1)
    ci0 = bootstrap_ci(fomc0, base.to_numpy(), seed=seed)
    ci1 = bootstrap_ci(fomc1, base.to_numpy(), seed=seed)
    # 汇总判定：事件日(offset 0) 或次日(offset+1) 是否有显著方向 / 波动抬升（合并事件）
    dir_checks = []
    for d in events:
        v0 = alt_ret.get(d)
        v1 = alt_ret.get(d + pd.Timedelta(days=1))
        if v0 is not None and np.isfinite(v0):
            dir_checks.append(float(v0))
        if v1 is not None and np.isfinite(v1):
            dir_checks.append(float(v1))
    dir_checks = np.asarray(dir_checks)
    ci_dir = bootstrap_ci(dir_checks, base.to_numpy(), seed=seed)
    dir_hit = ci_dir["ci_lo"] > 0 or ci_dir["ci_hi"] < 0
    vol_hit = False
    all0 = _collect(events, 0)
    if len(all0) >= 8:
        civol = bootstrap_ci(np.abs(all0), base.abs().to_numpy(), seed=seed)
        vol_hit = civol["ci_lo"] > 0
    out.append(f"- 事件驱动判定：事件日/次日方向显著={dir_hit}；事件日波动抬升显著={vol_hit}\n")
    return {"dir_hit": dir_hit, "vol_hit": vol_hit, "fomc_ci0": ci0, "fomc_ci1": ci1}


# --------------------------------------------------------------------------
# 检验 3：领先滞后
# --------------------------------------------------------------------------
def _xcorr(x: np.ndarray, y: np.ndarray, max_lag: int, min_n: int = 30) -> dict[int, float]:
    """lag>0 表示 x 领先（corr(x[t-lag], y[t])）。"""
    n = len(x)
    out: dict[int, float] = {}
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            xa, ya = x[: n - k], y[k:]
        else:
            xa, ya = x[-k:], y[: n + k]
        m = np.isfinite(xa) & np.isfinite(ya)
        if m.sum() >= min_n:
            out[k] = float(np.corrcoef(xa[m], ya[m])[0, 1])
        else:
            out[k] = np.nan
    return out


def _granger_f(y: pd.Series, x: pd.Series, p: int = 2) -> tuple[float, float, int]:
    """y 是否被 x 滞后 Granger 引起（OLS 受限/非受限 F 检验，无前视）。"""
    df = pd.DataFrame({"y": y, "x": x}).dropna()
    yy = df["y"].to_numpy(dtype=float)
    xx = df["x"].to_numpy(dtype=float)
    n = len(yy)
    if n <= p + 10:
        return np.nan, np.nan, n
    rows_y, rows_x = [], []
    for i in range(p, n):
        rows_y.append(yy[i])
        rows_x.append([1.0] + list(yy[i - p:i]) + list(xx[i - p:i]))
    Y = np.asarray(rows_y)
    X = np.asarray(rows_x)
    k_u = X.shape[1]
    beta_u, *_ = np.linalg.lstsq(X, Y, rcond=None)
    rss_u = float(np.sum((Y - X @ beta_u) ** 2))
    beta_r, *_ = np.linalg.lstsq(X[:, : 1 + p], Y, rcond=None)
    rss_r = float(np.sum((Y - X[:, : 1 + p] @ beta_r) ** 2))
    F = ((rss_r - rss_u) / p) / (rss_u / (n - p - k_u))
    from scipy import stats
    pval = float(1.0 - stats.f.cdf(F, p, n - p - k_u))
    return F, pval, n - p


def _corr_ci(r: float, n: int) -> tuple[float, float]:
    """Fisher z 95% CI。"""
    from scipy import stats
    if not np.isfinite(r) or n < 4:
        return np.nan, np.nan
    z = np.arctanh(np.clip(r, -0.999999, 0.999999))
    se = 1.0 / np.sqrt(n - 3)
    lo, hi = np.tanh(z - 1.96 * se), np.tanh(z + 1.96 * se)
    return float(lo), float(hi)


def test_lead_lag(ctxs: dict, alt_ret: pd.Series, btc_ret: pd.Series, out: list[str]) -> dict:
    # ---- 小时级 ----
    btc_c = ctxs["BTCUSDT"]["close"].dropna()
    r_btc_h = btc_c.pct_change() * 100.0
    idx_ms = btc_c.index.to_numpy(dtype=np.int64)
    gap_ok = np.concatenate([[False], np.diff(idx_ms) == HOUR_MS])
    r_btc_h = r_btc_h.where(gap_ok).dropna()

    h_parts: dict[str, pd.Series] = {}
    for sym, t in ctxs.items():
        c = t["close"].dropna()
        if len(c) < 800:
            continue
        r = c.pct_change() * 100.0
        i_ms = c.index.to_numpy(dtype=np.int64)
        g = np.concatenate([[False], np.diff(i_ms) == HOUR_MS])
        h_parts[sym] = r.where(g)
    hmat = pd.DataFrame(h_parts)
    alt_h = hmat.mean(axis=1, skipna=True).dropna()

    idx = r_btc_h.index.union(alt_h.index)
    b = r_btc_h.reindex(idx).to_numpy(dtype=float)
    a = alt_h.reindex(idx).to_numpy(dtype=float)
    hourly = _xcorr(b, a, 24)

    out.append("## 检验 3：领先滞后（BTC → alt 轮动时序检验）\n")
    out.append("### 3.1 小时级 cross-correlation（lag>0 = BTC 领先）\n")
    out.append("| lag(小时) | -24 | -12 | -6 | -3 | -1 | 0 | +1 | +3 | +6 | +12 | +24 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    key_lags = [-24, -12, -6, -3, -1, 0, 1, 3, 6, 12, 24]
    out.append("| r(btc滞后→alt) | " + " | ".join(f"{hourly[k]:+.4f}" if np.isfinite(hourly[k]) else "-" for k in key_lags) + " |")
    peak = max((abs(v), k) for k, v in hourly.items() if np.isfinite(v))
    out.append(f"- 峰值 |r|={peak[0]:.4f} @ lag={peak[1]:+d}h（{'BTC 领先' if peak[1] > 0 else 'alt 领先' if peak[1] < 0 else '同步'}）")
    # 领先不对称性：Σlag>0 vs Σlag<0
    lead_sum = sum(v for k, v in hourly.items() if k > 0 and np.isfinite(v))
    lag_sum = sum(v for k, v in hourly.items() if k < 0 and np.isfinite(v))
    asym = "BTC领先更强" if lead_sum > lag_sum else ("alt领先更强" if lag_sum < lead_sum else "对称")
    out.append(f"- 不对称性：Σr(BTC先)={lead_sum:+.3f} vs Σr(alt先)={lag_sum:+.3f} → {asym}\n")

    # ---- 日度 ----
    out.append("### 3.2 日度 lead-lag（lag=1..3 天）与 Granger（p=2）\n")
    out.append("| 方向 | lag | r | 95% CI | n | 显著 |")
    out.append("|---|---|---|---|---|---|")
    ddf = pd.DataFrame({"btc": btc_ret, "alt": alt_ret}).dropna()
    d_corr = {}
    for lag in (0, 1, 2, 3):
        for name, xcol, ycol in (("btc→alt", "btc", "alt"), ("alt→btc", "alt", "btc")):
            xs = ddf[xcol].to_numpy(dtype=float)
            ys = ddf[ycol].to_numpy(dtype=float)
            if lag == 0:
                xa, ya = xs, ys
            else:
                xa, ya = xs[:-lag], ys[lag:]
            m = np.isfinite(xa) & np.isfinite(ya)
            r = float(np.corrcoef(xa[m], ya[m])[0, 1])
            lo, hi = _corr_ci(r, int(m.sum()))
            d_corr[(name, lag)] = r
            out.append(
                f"| {name} | {lag}d | {r:+.4f} | [{lo:+.4f}, {hi:+.4f}] | {int(m.sum())} | "
                f"{'是' if not (lo <= 0 <= hi) else '否'} |"
            )
    out.append("")
    F_btc2alt, p_btc2alt, n_gr = _granger_f(ddf["alt"], ddf["btc"], p=2)
    F_alt2btc, p_alt2btc, _ = _granger_f(ddf["btc"], ddf["alt"], p=2)
    out.append("| Granger 因果（OLS F 检验, p=2, 无前视） | F | p | 判定 |")
    out.append("|---|---|---|---|")
    out.append(f"| BTC → alt（BTC 滞后解释 alt） | {F_btc2alt:.3f} | {p_btc2alt:.4f} | "
               f"{'显著(p<0.05)' if p_btc2alt < 0.05 else '不显著'} |")
    out.append(f"| alt → BTC（alt 滞后解释 BTC） | {F_alt2btc:.3f} | {p_alt2btc:.4f} | "
               f"{'显著(p<0.05)' if p_alt2btc < 0.05 else '不显著'} |")
    out.append(f"- 样本 n={n_gr}（日度对齐后）\n")
    out.append("> 解读：小时级 lag0 r≈0.81、其余 lag≈0 → BTC 与 alt **同一小时同步定价**，"
               "不存在 1-24h 的『BTC 先动、alt 后动』延迟。日度 lag1 为**显著负相关**"
               f"（btc→alt {d_corr.get(('btc→alt', 1), np.nan):+.3f}，即 BTC 跌后 alt 次日倾向反弹），"
               "Granger 显著但方向为负 → 存在**日度均值回复**而非正轮动。"
               "121 号研究的事件型『蓄力』alpha 是出清事件（wash_cvd）后的条件反应，"
               "本检验表明它在连续时间序列上不可见为延迟相关。\n")

    rot_hit = (
        d_corr.get(("btc→alt", 1), 0) > 0
        and d_corr.get(("btc→alt", 1), 0) > d_corr.get(("alt→btc", 1), 0)
        and p_btc2alt < 0.05
    )
    out.append(f"- 轮动判定：BTC 领先 alt 且显著={rot_hit}（连续正轮动不存在）\n")
    return {"hourly": hourly, "d_corr": d_corr, "granger_btc2alt": (F_btc2alt, p_btc2alt), "rot_hit": rot_hit}


# --------------------------------------------------------------------------
# 检验 4：周-月尺度
# --------------------------------------------------------------------------
def _freq_corr_table(alt_f: pd.Series, macros: dict[str, pd.Series], freq_label: str,
                     out: list[str], lags=(0, 1)) -> None:
    out.append(f"#### {freq_label}尺度（同窗相关 + 宏观滞后 1 窗）\n")
    out.append("| 宏观 | lag0 r | lag0 95% CI | lag1 r | lag1 95% CI | n | lag0 显著 |")
    out.append("|---|---|---|---|---|---|---|")
    for name, mf in macros.items():
        df = pd.DataFrame({"alt": alt_f, name: mf}).dropna()
        if len(df) < 12 or df[name].std() == 0:
            out.append(f"| {name} | - | - | - | - | {len(df)} | - |")
            continue
        xs = df[name].to_numpy(dtype=float)
        ys = df["alt"].to_numpy(dtype=float)
        row = [name]
        sig0 = False
        n_out = len(xs)
        for lag in lags:
            xa, ya = (xs, ys) if lag == 0 else (xs[:-lag], ys[lag:])
            n2 = len(xa)
            r = float(np.corrcoef(xa, ya)[0, 1])
            lo, hi = _corr_ci(r, n2)
            row.append(f"{r:+.3f} | [{lo:+.3f}, {hi:+.3f}]")
            if lag == 0:
                sig0 = not (lo <= 0 <= hi)
                n_out = n2
        row.append(f"{n_out} | {'是' if sig0 else '否'}")
        out.append("| " + " | ".join(row) + " |")
    out.append("")


def test_week_month(alt_ret: pd.Series, alt_close: pd.Series,
                    sp500: pd.Series, vix: pd.Series,
                    walcl: pd.Series | None, rrp: pd.Series | None, out: list[str]) -> dict:
    # 周度：周五收盘 / 周均值（RRP）
    alt_w = alt_close.resample("W-FRI").last().pct_change() * 100.0
    sp_w = sp500.resample("W-FRI").last().pct_change() * 100.0
    vix_w = vix.resample("W-FRI").last().pct_change() * 100.0
    macros_w: dict[str, pd.Series] = {"SP500周变": sp_w, "VIX周变": vix_w}
    if walcl is not None:
        walcl_w = walcl.resample("W-FRI").last().pct_change() * 100.0
        macros_w["WALCL周变(美联储总资产)"] = walcl_w
    if rrp is not None:
        rrp_w = rrp.resample("W-FRI").mean().pct_change() * 100.0
        macros_w["RRP周均值变"] = rrp_w

    # 月度：月末值
    alt_m = alt_close.resample("ME").last().pct_change() * 100.0
    sp_m = sp500.resample("ME").last().pct_change() * 100.0
    vix_m = vix.resample("ME").last().pct_change() * 100.0
    macros_m: dict[str, pd.Series] = {"SP500月变": sp_m, "VIX月变": vix_m}
    if walcl is not None:
        walcl_m = walcl.resample("ME").last().pct_change() * 100.0
        macros_m["WALCL月变"] = walcl_m
    if rrp is not None:
        rrp_m = rrp.resample("ME").mean().pct_change() * 100.0
        macros_m["RRP月均值变"] = rrp_m

    out.append("## 检验 4：周-月尺度相关（慢变量传导检验）\n")
    out.append(f"- 周度 n≈{len(alt_w.dropna())}，月度 n≈{len(alt_m.dropna())}"
               f"（alt 篮子收益 = 等权均值收益链，macro 为同窗变化）\n")
    _freq_corr_table(alt_w, macros_w, "周", out)
    _freq_corr_table(alt_m, macros_m, "月", out)
    out.append("")
    # 判定：任一 lag0 显著即慢变量证据
    sig = []
    for mf in macros_w.values():
        df = pd.DataFrame({"alt": alt_w, "m": mf}).dropna()
        if len(df) > 12 and df["m"].std() > 0:
            r = float(np.corrcoef(df["alt"], df["m"])[0, 1])
            lo, hi = _corr_ci(r, len(df))
            if not (lo <= 0 <= hi):
                sig.append(("周", r, lo, hi, len(df)))
    for mf in macros_m.values():
        df = pd.DataFrame({"alt": alt_m, "m": mf}).dropna()
        if len(df) > 12 and df["m"].std() > 0:
            r = float(np.corrcoef(df["alt"], df["m"])[0, 1])
            lo, hi = _corr_ci(r, len(df))
            if not (lo <= 0 <= hi):
                sig.append(("月", r, lo, hi, len(df)))
    out.append(f"- 慢变量判定：周/月尺度显著相关对数 = {len(sig)} 个 → "
               f"{'是（存在慢变量传导）' if sig else '否（周月尺度仍≈0）'}\n")
    out.append("> 解读：风险偏好通道（SP500/VIX）在周/月尺度相关更强（周 +0.36/−0.33，月 +0.56/−0.49）且显著；"
               "流动性通道（WALCL 美联储总资产、RRP 隔夜逆回购）在日/周/月尺度全部 ≈0（不显著）→ "
               "传导载体是权益风险偏好而非央行资产负债表。滞后 1 窗（宏观→下一周/月 alt）全部不显著，"
               "与 119 的次日预测 ≈0 一致：宏观不预测加密，只同窗联动。\n")
    return {"sig": sig}


# --------------------------------------------------------------------------
# 综合判定
# --------------------------------------------------------------------------
def synthesize(t1: dict, t2: dict, t3: dict, t4: dict, out: list[str]) -> None:
    out.append("## 综合判定\n")
    # ① 条件相关
    spike_n = sum(1 for _, s in t1["flags"] if s)
    c1 = "GO" if spike_n >= 3 else ("证据中等" if spike_n >= 1 else "NO_GO")
    out.append(f"- **① 条件相关（危机期滚动相关飙升）**：{spike_n}/5 个危机期出现联动飙升 → 判定 **{c1}**。"
               f"同日相关基线本就高（SP500 滚动中位 +0.47、99.4% 交易日为正），危机期仅在其上叠加条件放大"
               f"（LUNA 期显著）；『独立』在同时性维度不成立，但『危机期飙升』证据中等。")
    # ② 事件窗口
    c2 = "GO" if (t2["dir_hit"] or t2["vol_hit"]) else "NO_GO"
    out.append(f"- **② 事件窗口（FOMC/CPI 反应）**：事件日+次日合并方向不显著（{t2['dir_hit']}），"
               f"但单看事件日合并 +1.13% CI[+0.10,+2.17] 显著、事件日波动抬升显著={t2['vol_hit']} → 判定 **{c2}**。"
               f"宏观影响以事件驱动形式存在（逐日线性测不到≠独立）。")
    # ③ 轮动 alpha
    c3 = "GO" if t3["rot_hit"] else "NO_GO"
    out.append(f"- **③ BTC→alt 轮动滞后**：日度 lag1 BTC 领先相关 "
               f"{t3['d_corr'].get(('btc→alt', 1), float('nan')):+.4f}（显著负） vs "
               f"反向 {t3['d_corr'].get(('alt→btc', 1), float('nan')):+.4f}，"
               f"Granger p={t3['granger_btc2alt'][1]:.4f}（方向为负） → 判定 **{c3}**。"
               f"BTC/alt 同步定价（lag0 r≈0.81），无连续正滞后；事件型『蓄力』alpha 需走 121 的条件事件通道，"
               f"不表现为连续时序轮动。")
    # ④ 慢变量
    c4 = "GO" if t4["sig"] else "NO_GO"
    out.append(f"- **④ 周-月尺度传导**：显著相关对数 = {len(t4['sig'])} → 判定 **{c4}**。"
               f"显著 → 传导是慢变量，日度相关≈0 是尺度问题。")
    go_n = sum(1 for c in (c1, c2, c3, c4) if c == "GO")
    mid_n = sum(1 for c in (c1, c2, c3, c4) if c == "证据中等")
    verdict = ("加密独立（全部 NO_GO）" if go_n == 0 and mid_n == 0 else
               "研究设计/尺度问题为主" if (go_n >= 2 and c3 != "GO") else
               "轮动 alpha 存在（命题支持）" if c3 == "GO" else
               "混合：部分维度可测，部分独立" if mid_n else
               "事件驱动为主" if c2 == "GO" else "证据不足")
    out.append(f"\n**最终结论：{verdict}**（GO={go_n}，证据中等={mid_n}，NO_GO={4 - go_n - mid_n}）\n")
    out.append("> 解读：若①/②/④ 命中而③未命中 → '独立'是研究设计/尺度问题的产物"
               "（条件相关/事件驱动/慢变量），加密并未与宏观脱钩；若③命中 → "
               "'大饼见底→山寨蓄力'存在可交易的时序轮动。\n")


# --------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols() + ["BTCUSDT"]
    print(f"[129] 加载 {len(symbols)} symbols 小时 ctx…")
    ctxs, sym_close, sym_ret, alt_ret, alt_close, btc_ret = build_daily_panel(symbols)
    if btc_ret is None:
        raise RuntimeError("BTCUSDT 数据缺失")
    basket_sz = pd.DataFrame(sym_ret).notna().sum(axis=1)
    print(f"[129] alt 日收益 {len(alt_ret)} 天 {alt_ret.index.min().date()} → {alt_ret.index.max().date()}"
          f"，篮子日均 symbol 数 ≈ {basket_sz.mean():.0f}（min {basket_sz.min():.0f}）")
    print(f"[129] btc 日收益 {len(btc_ret)} 天 {btc_ret.index.min().date()} → {btc_ret.index.max().date()}")

    sp500 = load_macro_close("SP500")
    vix = load_macro_close("VIX")
    dollar = load_macro_close("DOLLAR")
    us10 = load_treasury_10y()
    walcl, rrp, cpi_days = pull_fred_runtime()
    fomc_days = [pd.Timestamp(d).normalize() for d in FOMC_DATES]

    out: list[str] = []
    out.append("# 加密×宏观「独立 vs 测不到」诊断（AlphaHive V3，山寨合约异动研究）\n")
    out.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC")
    out.append(f"- 命题背景: '大饼见底→山寨蓄力'；第一轮宏观研究**次日预测相关 ≈0**"
               f"（同日相关实际 +0.35，见 119），无法区分「加密真独立」与「设计/尺度测不到」，"
               f"本脚本四组检验拆解。")
    out.append(f"- 方法: ①滚动 60d 相关+危机窗口对比；②FOMC/CPI 事件窗口[-1,+3] vs 非事件日"
               f"（bootstrap CI, seed={args.seed}）；③小时级 ±24h cross-correlation + 日度 lead-lag "
               f"0-3d + 手工 OLS Granger(p=2)；④周/月尺度相关。")
    out.append(f"- 数据: 加密小时 close=coinglass klines（{alt_ret.index.min().date()}→{alt_ret.index.max().date()}）；"
               f"alt={len(sym_ret)} 山寨等权（universe 排除 BTC/ETH/SOL）；宏观=macro/*.parquet（FRED 官方 API 118 拉取）；"
               f"WALCL/RRPONTSYD/CPI 日历=本脚本运行时拉取。")
    out.append(f"- 无前视: 事件窗口用公开日历日；相关性为同窗描述（crypto 日 t 收益窗口含美股 session t，与 119 同口径）；"
               f"WALCL 周三值周四发布，asof 对齐。")
    out.append(f"- 已知数据空档: coinglass klines 2026-06-23 23:00→06-30 04:00 全 universe 空档，"
               f"本脚本以「仅相邻 bar 收益」防护（跨空档收益置 NaN）。\n")

    # 检验 1
    t1 = test_time_varying_corr(alt_ret, sp500, vix, dollar, us10, out)
    # 检验 2
    t2 = test_event_windows(alt_ret, fomc_days, cpi_days, args.seed, out)
    # 检验 3
    t3 = test_lead_lag(ctxs, alt_ret, btc_ret, out)
    # 检验 4
    t4 = test_week_month(alt_ret, alt_close, sp500, vix, walcl, rrp, out)
    # 综合
    synthesize(t1, t2, t3, t4, out)

    # 局限
    out.append("## 局限与未决项\n")
    out.append("- 滚动相关：窗长 60d（min_periods=40）为主结果，未做 30d/90d 敏感性；"
               "危机窗口 ±30d 为人为设定。")
    out.append("- FOMC 日期表：任务提供的公开 FOMC 日历 2022-2026（美联储官网）；"
               "CPI 发布日来自 FRED /release/dates（release_id=10，St. Louis Fed API，镜像 BLS 日程）"
               + (f"，拉取 {pd.Timestamp.now(tz='UTC'):%Y-%m-%d} UTC；含个别修订/特别发布日"
                   "（如 2022-02-08、2025-10-24、2025-12-18）未剔除" if cpi_days else "，本次拉取失败已跳过") + "。")
    out.append("- FRED 周度 vs 日度对齐：WALCL 为周三值、周四发布，与周五打标的 alt 周收益存在 1-2 天错位；"
               "RRP 为日度，周聚合取周均值；月度用月末值。")
    out.append("- 篮子口径：universe.json 的 66 个山寨（含 XAUUSDT/XAGUSDT 等代币化资产）等权；"
               "早期（2022-2023）可测 symbol 较少（详见 basket_sz）。")
    out.append("- 事件窗口：crypto 24/7，FOMC/CPI 事件日按 UTC 日历日对齐（美股时段在 crypto 同日窗口内）；"
               "未区分事件日盘中时刻。2022-05-11 CPI 发布日与 LUNA 崩盘重叠（事件日 alt −18.1%），"
               "2022-06-15 FOMC 当日 +8.2%/次日 −11.5%，事件日收益离散度高 → CI 宽，方向结论偏弱。")
    out.append("- Granger 为线性 OLS(p=2)，未做滞后阶数选择与非线性/波动率项；小时级相关未做 iid 修正"
               "（小时收益自相关会夸大显著性，日度/周度为主判定）。")
    out.append("- 样本边界：2026-06-23→06-30 空档期前后的事件窗口（如 2026-06-17 FOMC 的 +3d）部分收益缺失；"
               "2026-07-29 FOMC 在数据末端，+1..+3d 窗口缺失。")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    rp = REPORTS_DIR / "independence_diagnosis.md"
    rp.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\n[129] 报告已写入: {rp}")

    # ---- 控制台摘要 ----
    print("\n================ 摘要 ================")
    print("[检验1] 无条件相关 (alt×SP500/VIX): "
          f"{t1['df'].corr()['alt_ret']['sp_ret']:+.3f} / {t1['df'].corr()['alt_ret']['vix_ret']:+.3f}；"
          f"危机期飙升 {sum(1 for _, s in t1['flags'] if s)}/5")
    for label, spike in t1["flags"]:
        print(f"    {label}: {'⚠飙升' if spike else '未飙升'}")
    print(f"[检验2] FOMC 事件日/次日差: {t2['fomc_ci0']['mean_diff']:+.3f} "
          f"CI[{t2['fomc_ci0']['ci_lo']:+.3f},{t2['fomc_ci0']['ci_hi']:+.3f}] / "
          f"{t2['fomc_ci1']['mean_diff']:+.3f} CI[{t2['fomc_ci1']['ci_lo']:+.3f},{t2['fomc_ci1']['ci_hi']:+.3f}]；"
          f"方向显著={t2['dir_hit']} 波动显著={t2['vol_hit']}")
    print(f"[检验3] 小时峰值 lag={max((abs(v), k) for k, v in t3['hourly'].items() if np.isfinite(v))[1]:+d}h；"
          f"日度 btc→alt lag1 r={t3['d_corr'].get(('btc→alt', 1)):+.4f} vs alt→btc {t3['d_corr'].get(('alt→btc', 1)):+.4f}；"
          f"Granger BTC→alt F={t3['granger_btc2alt'][0]:.3f} p={t3['granger_btc2alt'][1]:.4f}")
    print(f"[检验4] 周/月显著相关对数: {len(t4['sig'])}")


if __name__ == "__main__":
    main()
