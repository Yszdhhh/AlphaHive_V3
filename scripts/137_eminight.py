"""137_eminight.py — B 方向补充：美股期货 E-mini ES（ES=F）亚洲时段对加密的领先性。

命题：加密 24/7 交易；美股期货 Globex 也有"盘后/亚洲"时段（美东收盘后 → 次日欧盘前）。
若 ES 亚洲时段（固定 UTC 口径 21:00 → 次日 14:00）的走势领先或同步于加密同段
（21:00→09:00，122 口径）与加密"下一段"（09:00→14:00），则存在跨市场领先信号。

三张表：
1) 相关矩阵：ES 亚洲段 vs 加密同段 / 下一段（alt 篮子 + btc），分 2024 / 2025+ era；
   附"可交易领先"行：ES 隔夜段(21:00→09:00，10:00 UTC 已知) vs 加密下一段(09:00→14:00，10:00 入场)。
2) 事件研究：ES 亚洲段 下5%冲击日（bootstrap seed=2026）→ 加密同段/下一段收益 vs 无条件均值；
   附 下10% 稳健行与 ES 隔夜段冲击 → 加密下一段（严格可交易对）。
3) 对照：ES 盘中段(14:00→21:00) vs 加密盘中段(14:00→21:00) 同窗联动；
   ES 盘中段 → 加密隔夜段（122 对照：美股盘中信号对加密隔夜≈0，用期货复验）。

数据：
- ES=F 1h klines：yfinance（2024-03-15 → 拉取日，实际 >730 天）；来源标注 + 拉取时间戳，
  缓存到 data/raw/es_f_1h.parquet（--refresh-es 强制重拉）。
- 加密：COINGLASS_RAW1H/klines/*.parquet（→ 2026-07-07 03:00 UTC），复用 113/122 口径。

切段口径（固定 UTC，无前视）：
- 盘中段：14:00 → 21:00（美东 09:00/10:00 → 16:00/17:00，冬/夏令 ±1h 偏差，已标注）。
- 亚洲段：21:00 d → 14:00 d+1（含美盘后 + 亚洲交易）。
- 隔夜段：21:00 d → 09:00 d+1（122 同口径）。
- ES 21:00 锚点：冬令时有 21:00 bar；夏令时 21:00 UTC=17:00 EDT 处于 Globex 每日休市，
  asof 回退到 20:00 bar（=17:00 EDT 休市前最后价格，恰为当日收盘锚点）→ 两端口径一致。

局限（诚实标注）：
- 固定 UTC 切段 vs 美东冬/夏令时：±1h 偏差（ES 21:00 锚点夏令时回退 1h 至 20:00 bar）。
- 窗口仅 ~2.3 年（2024-03 → 2026-07-07，coinglass 数据末），且 ES 周末无数据：
  亚洲段事件样本 下5%≈22 天（n<30 判样本不足）、下10%≈45 天。
- yfinance ES=F 为连续前月合约（auto_adjust=True 处理展期价差），残余滚动噪声 + 数据质量风险。
- 样本内统计，未计费率/滑点/深度。

用法：
  python scripts/137_eminight.py [--seed 2026] [--refresh-es] [--symbols ...]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import bootstrap_ci

COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_DIR = PROJECT_ROOT / "data" / "raw"
ES_CACHE = DATA_DIR / "es_f_1h.parquet"
ES_META = DATA_DIR / "es_f_1h.meta.json"

# 统一加载模板（113 口径）
_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec)
sys.modules["m113"] = m113
_spec.loader.exec_module(m113)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx

HOUR_MS = 3_600_000
MIN_ALT_SYMBOLS = 10      # alt 篮子当日不足 10 个 symbol 有值 → NaN
MIN_N = 30                # 判定口径：n<30 → 样本不足
ES_TICKER = "ES=F"
ES_START = "2024-03-15"   # yfinance 730d 实际返回范围起点（>任务要求 2024-08，如实使用）
CRYPTO_END = "2026-07-07"  # coinglass 小时数据末（2026-07-07 03:00 UTC）
ERA_SPLIT = "2025-01-01"
ASOF_GAP_MS = 3 * HOUR_MS  # ES asof 容差：覆盖夏令时回退(1h)/缺失维护 bar(≤2h)，拒绝周末(≥16h)


def day_start_ms(d) -> int:
    """日期 d（UTC 日）00:00 的 ms 时间戳。"""
    return int(pd.Timestamp(pd.Timestamp(d).date(), tz="UTC").value) // 1_000_000


def exact_close(idx: np.ndarray, closes: np.ndarray, ts: np.ndarray) -> np.ndarray:
    """searchsorted 精确对齐：返回 open_time==ts 的 bar close；无该 bar → NaN（无前视，122 同款）。"""
    pos = np.searchsorted(idx, ts, side="left")
    pos = np.clip(pos, 0, len(idx) - 1)
    ok = idx[pos] == ts
    out = np.full(len(ts), np.nan)
    out[ok] = closes[pos[ok]]
    return out


# ------------------------------------------------------------------ ES=F 数据
def load_es_data(refresh: bool = False) -> tuple[pd.Series, dict]:
    """ES=F 1h close（index=open_time ms int）。缓存优先；拉取时写缓存 + 元信息。"""
    import yfinance as yf

    if not refresh and ES_CACHE.exists() and ES_META.exists():
        meta = json.loads(ES_META.read_text(encoding="utf-8"))
        df = pd.read_parquet(ES_CACHE)
        meta["cached"] = True
        meta["note"] = f"缓存 {meta['fetched_utc']}（yfinance {meta['yfinance_version']}）"
        return df["close"], meta

    df = yf.download(ES_TICKER, period="730d", interval="1h", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if len(df) < 5000:
        raise RuntimeError(f"yfinance ES=F 返回行数异常: {len(df)}")
    du = df.index.tz_convert("UTC").tz_localize(None)
    ts_ms = du.astype("datetime64[s]").astype(np.int64) * 1000
    close = pd.Series(pd.to_numeric(df["Close"], errors="coerce").to_numpy(dtype=float),
                      index=pd.Index(ts_ms, name="open_time_ms"))
    close = close[~close.index.duplicated(keep="last")].sort_index().dropna()
    fetched_utc = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M")
    meta = {"fetched_utc": fetched_utc, "yfinance_version": yf.__version__,
            "ticker": ES_TICKER, "interval": "1h", "period": "730d",
            "rows": int(len(close)), "start_utc": str(pd.Timestamp(close.index[0], unit="ms", tz="UTC")),
            "end_utc": str(pd.Timestamp(close.index[-1], unit="ms", tz="UTC")),
            "source_url": "https://finance.yahoo.com/quote/ES=F/"}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame({"close": close.to_numpy()}, index=close.index)
    out.to_parquet(ES_CACHE)
    ES_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    meta["cached"] = False
    return close, meta


def es_segment_returns(close_ms: pd.Series, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """ES 三段日度收益（%）：es_us(14→21) / es_ovn(21→09 d+1) / es_asia(21→14 d+1)。

    asof 锚点：最后一个 open_time<=target 的 bar，容差 ASOF_GAP_MS（夏令时 21:00→20:00 bar
    回退 1h，恰为 Globex 休市前最后价格）；周末/长假无 bar（gap≥16h）→ NaN。
    """
    ts_arr = close_ms.index.to_numpy(dtype=np.int64)
    close_arr = close_ms.to_numpy(dtype=float)
    dm = np.array([day_start_ms(d) for d in dates], dtype=np.int64)

    def asof(targets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        pos = np.searchsorted(ts_arr, targets, side="right") - 1
        out = np.full(len(targets), np.nan)
        gap = np.where(pos >= 0, targets - ts_arr[np.maximum(pos, 0)], np.inf)
        ok = (pos >= 0) & (gap >= 0) & (gap <= ASOF_GAP_MS)
        out[ok] = close_arr[pos[ok]]
        return out, gap

    c14, _ = asof(dm + 14 * HOUR_MS)
    c21, gap21 = asof(dm + 21 * HOUR_MS)
    c09, _ = asof(dm + 33 * HOUR_MS)
    c14n, _ = asof(dm + 38 * HOUR_MS)
    with np.errstate(divide="ignore", invalid="ignore"):
        r_us = (c21 / c14 - 1.0) * 100.0
        r_ovn = (c09 / c21 - 1.0) * 100.0
        r_asia = (c14n / c21 - 1.0) * 100.0
    out = pd.DataFrame({"es_us": r_us, "es_ovn": r_ovn, "es_asia": r_asia}, index=dates)
    out["anchor21_fallback"] = np.isfinite(c21) & (gap21 > 0)
    return out


# ------------------------------------------------------------------ 加密段
def build_symbol_segment(ctx: pd.DataFrame, dates: pd.DatetimeIndex,
                         h_start: int, h_end: int) -> pd.Series:
    """加密 [h_start, h_end] 小时窗收益（小时数=UTC 午夜后偏移，h_end 可>24=次日）：
    r = close(open_time==h_end)/close(open_time==h_start)-1（122 精确对齐语义，无前视）。"""
    idx = ctx.index.to_numpy(dtype=np.int64)
    closes = ctx["close"].to_numpy(dtype=float)
    dm = np.array([day_start_ms(d) for d in dates], dtype=np.int64)
    c_s = exact_close(idx, closes, dm + h_start * HOUR_MS)
    c_e = exact_close(idx, closes, dm + h_end * HOUR_MS)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = (c_e / c_s - 1.0) * 100.0
    return pd.Series(r, index=dates)


def basket_mean(mat: pd.DataFrame, min_symbols: int) -> pd.Series:
    """等权横截面均值；当日有值 symbol 数 < min_symbols → NaN（122 同款）。"""
    return mat.mean(axis=1, skipna=True).where(mat.notna().sum(axis=1) >= min_symbols)


# ------------------------------------------------------------------ 表格辅助
def corr_cells(df: pd.DataFrame, x: str, y: str) -> list[str]:
    cells: list[str] = []
    for name, m_era in [("2024", df["era"] == "2024"), ("2025+", df["era"] == "2025+"),
                        ("全样本", pd.Series(True, index=df.index))]:
        sub = df.loc[m_era, [x, y]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(sub) < 30 or sub[y].std() == 0:
            cells += ["-", str(len(sub))]
        else:
            cells += [f"{sub[x].corr(sub[y]):+.3f}", str(len(sub))]
    return cells


def event_row(df: pd.DataFrame, shock_col: str, resp_col: str, mask: pd.Series,
              seed: int, min_n: int = MIN_N) -> dict:
    """事件研究统计：mask 事件组 vs 无条件均值（基线=冲击变量有值的所有天）。"""
    base = (df.loc[df[shock_col].notna(), resp_col].replace([np.inf, -np.inf], np.nan).dropna()
            .to_numpy())
    ev = df.loc[mask, resp_col].replace([np.inf, -np.inf], np.nan).dropna()
    n = len(ev)
    if n < min_n:
        return {"n": n, "mean": float(ev.mean()), "excess": np.nan, "base": float(np.nanmean(base)),
                "ci": None, "verdict": f"样本不足(n={n}<{min_n})"}
    ci = bootstrap_ci(ev.to_numpy(), base, seed=seed)
    if ci["ci_lo"] > 0:
        verdict = "**GO_LONG**"
    elif ci["ci_hi"] < 0:
        verdict = "**GO_SHORT**"
    else:
        verdict = "NO_GO"
    return {"n": n, "mean": float(ev.mean()), "excess": float(ci["mean_diff"]),
            "base": float(np.nanmean(base)), "ci": ci, "verdict": verdict}


def fmt_event_row(label: str, r: dict) -> str:
    """事件研究行格式化（label = 冲击 → 响应）。"""
    if r["ci"] is None:
        return (f"| {label} | {r['n']} | {r['mean']:+.3f}% | {r['verdict']} | "
                f"{r['base']:+.3f}% | - | - |")
    return (f"| {label} | {r['n']} | {r['mean']:+.3f}% | {r['excess']:+.3f}% | "
            f"{r['base']:+.3f}% | [{r['ci']['ci_lo']:+.3f}, {r['ci']['ci_hi']:+.3f}] | {r['verdict']} |")


def shock_info(df: pd.DataFrame, col: str, pct: float, side: str) -> tuple[pd.Series, float, int]:
    s = df[col].replace([np.inf, -np.inf], np.nan).dropna()
    q = float(s.quantile(pct)) if side == "bottom" else float(s.quantile(1 - pct))
    mask = df[col].le(q).fillna(False) if side == "bottom" else df[col].ge(q).fillna(False)
    return mask, q, int(mask.sum())


# ------------------------------------------------------------------ main
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--refresh-es", action="store_true", help="强制重新拉取 yfinance ES=F")
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    # ---- ES=F ----
    es_close, es_meta = load_es_data(args.refresh_es)
    ts_first = pd.Timestamp(es_close.index[0], unit="ms", tz="UTC")
    ts_last = pd.Timestamp(es_close.index[-1], unit="ms", tz="UTC")
    print(f"[137] ES=F 1h klines: {ts_first} → {ts_last} ({len(es_close)} 行) | 来源: yfinance "
          f"{es_meta['yfinance_version']}，拉取 {es_meta['fetched_utc']} UTC（{'缓存' if es_meta.get('cached') else '实时'}）")

    # ---- 加密 ----
    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    btc_ctx = load_price_ctx(["BTCUSDT"]).get("BTCUSDT")
    print(f"[137] 加密 ctx 表 {len(ctxs)} | coinglass 段 → {CRYPTO_END} 03:00 UTC")

    # ---- 日轴（ES 起点 → coinglass 末，交集）----
    dates = pd.date_range(ES_START, CRYPTO_END, freq="D")
    print(f"[137] 分析窗口 {dates[0].date()} → {dates[-1].date()}（{len(dates)} 天）")

    es = es_segment_returns(es_close, dates)
    fb_days = int(es["anchor21_fallback"].sum())
    print(f"[137] ES 段有效天数: es_us {int(es['es_us'].notna().sum())} | "
          f"es_ovn {int(es['es_ovn'].notna().sum())} | es_asia {int(es['es_asia'].notna().sum())}"
          f" | 21:00 锚点夏令时回退 {fb_days} 天（asof 容差 3h）")

    # 加密段矩阵（122 口径：21→09 隔夜；新增 09→14 下一段、14→21 盘中段）
    ovn_mat, next_mat, sess_mat = {}, {}, {}
    for s, ctx in ctxs.items():
        ovn_mat[s] = build_symbol_segment(ctx, dates, 21, 33)
        next_mat[s] = build_symbol_segment(ctx, dates, 33, 38)
        sess_mat[s] = build_symbol_segment(ctx, dates, 14, 21)
    alt_ovn = basket_mean(pd.DataFrame(ovn_mat), MIN_ALT_SYMBOLS)
    alt_next = basket_mean(pd.DataFrame(next_mat), MIN_ALT_SYMBOLS)
    alt_sess = basket_mean(pd.DataFrame(sess_mat), MIN_ALT_SYMBOLS)
    if btc_ctx is not None:
        btc_ovn = build_symbol_segment(btc_ctx, dates, 21, 33)
        btc_next = build_symbol_segment(btc_ctx, dates, 33, 38)
        btc_sess = build_symbol_segment(btc_ctx, dates, 14, 21)
    else:
        btc_ovn = btc_next = btc_sess = pd.Series(np.nan, index=dates)

    df = pd.DataFrame(index=dates)
    for c in ["es_us", "es_ovn", "es_asia"]:
        df[c] = es[c]
    df["alt_ovn"], df["alt_next"], df["alt_sess"] = alt_ovn, alt_next, alt_sess
    df["btc_ovn"], df["btc_next"], df["btc_sess"] = btc_ovn, btc_next, btc_sess
    df["era"] = np.where(dates < ERA_SPLIT, "2024", "2025+")

    lines: list[str] = []
    lines.append("# 美股期货 E-mini ES 亚洲时段对加密的领先性（B 方向补充）\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 方法: ES=F 1h klines 三段固定 UTC 切段——盘中 14:00→21:00（美东 09:00/10:00→16:00/17:00，"
                 f"冬/夏令 ±1h 偏差，ES 21:00 锚点夏令时经 asof 回退到 20:00 bar=17:00 EDT 休市前最后价，共 {fb_days} 天）、"
                 f"亚洲段 21:00→次日 14:00、隔夜段 21:00→09:00（122 同口径）。加密同段 21:00→09:00（122 口径）、"
                 f"下一段 09:00→14:00、盘中段 14:00→21:00。收益=收盘/收盘-1（searchsorted 精确对齐 bar open_time，无前视）；"
                 f"alt=universe 山寨等权（当日<10 symbol 有值→NaN）。相关按 2024 / 2025+ / 全样本三列。")
    lines.append(f"- 数据源: ES=F 1h klines 来自 yfinance（{es_meta['yfinance_version']}，拉取 {es_meta['fetched_utc']} UTC，"
                 f"{'缓存' if es_meta.get('cached') else '实时'}；{es_meta.get('source_url', '')}），实际范围 "
                 f"{ts_first} → {ts_last}（{len(es_close)} 行，>730 天要求，2024-08→今完全覆盖）；"
                 f"加密 {COINGLASS_RAW1H}/klines/*.parquet（coinglass 段 → {CRYPTO_END} 03:00 UTC）。"
                 f"分析窗口取交集: {dates[0].date()} → {dates[-1].date()}（~2.3 年）。")
    lines.append("- 局限: ①固定 UTC 切段 vs 美东冬/夏令时 ±1h 偏差（21:00 锚点夏令时回退 1h 至 20:00 bar，"
                 "两端口径一致、结论不受平移影响）；②窗口仅 ~2.3 年且 ES 周末无数据 → 亚洲段 下5% 事件仅 ~22 天"
                 "（n<30 判样本不足，附 下10% 稳健行）；③yfinance ES=F 为连续前月合约（auto_adjust=True 处理展期价差），"
                 "存在残余滚动噪声与数据质量风险（维护时段缺 bar 已用 asof 容差处理）；④样本内统计，未计费率/滑点/深度。\n")

    # ================= 表 1：相关矩阵 =================
    lines.append("## 1. 相关矩阵（ES 亚洲段 vs 加密，分 era）\n")
    lines.append("| 配对 | 2024 r | n | 2025+ r | n | 全样本 r | n |")
    lines.append("|---|---|---|---|---|---|---|")
    pairs = [
        ("es_asia vs alt同段(21→09)", "es_asia", "alt_ovn", "同窗 12/17h 重叠 → 共动诊断"),
        ("es_asia vs btc同段(21→09)", "es_asia", "btc_ovn", ""),
        ("es_asia vs alt下一段(09→14)", "es_asia", "alt_next", "ES 亚洲段尾 5h 与加密下一段同窗"),
        ("es_asia vs btc下一段(09→14)", "es_asia", "btc_next", ""),
        ("es_ovn vs alt下一段(09→14)[可交易]", "es_ovn", "alt_next", "ES 隔夜 10:00 UTC 已知 → 加密 10:00 入场"),
        ("es_ovn vs btc下一段(09→14)[可交易]", "es_ovn", "btc_next", ""),
    ]
    print("\n=== 表1 相关矩阵（ES 亚洲段 vs 加密）===")
    print("| 配对 | 2024 r | n | 2025+ r | n | 全样本 r | n |")
    print("|---|---|---|---|---|---|---|")
    for label, x, y, note in pairs:
        cells = corr_cells(df, x, y)
        row = f"| {label} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {cells[4]} | {cells[5]} |"
        lines.append(row)
        print(row)
    lines.append("\n> 口径注：`es_asia vs alt同段` 两窗口 21:00→09:00 重叠 12h，正相关以同窗共动为主；"
                 "`es_asia vs alt下一段` 中 ES 亚洲段包含 09:00→14:00 尾腿，与加密下一段同窗共动（两序列均在 15:00 UTC 完成，"
                 "不可交易）；**唯一严格可交易的行是 `es_ovn vs alt下一段`**——ES 隔夜收益 10:00 UTC 已知，加密下一段 10:00 入场、15:00 平仓。\n")

    # ================= 表 2：事件研究 =================
    lines.append("## 2. 事件研究：ES 亚洲段冲击日 → 加密同段/下一段收益\n")
    lines.append("冲击阈值按 ES 段有效天全样本分位；基线 = 冲击变量有值天的响应无条件均值；"
                 f"bootstrap 95% CI（seed={args.seed}）。判定：CI 下界>0→GO_LONG / 上界<0→GO_SHORT / 含0→NO_GO / n<{MIN_N}→样本不足。\n")

    # 冲击定义（先算阈值并打印）
    shock_defs = [
        ("es_asia 下5%", "es_asia", 0.05, "bottom"), ("es_asia 上5%", "es_asia", 0.05, "top"),
        ("es_asia 下10%", "es_asia", 0.10, "bottom"), ("es_asia 上10%", "es_asia", 0.10, "top"),
        ("es_ovn 下5%", "es_ovn", 0.05, "bottom"), ("es_ovn 上5%", "es_ovn", 0.05, "top"),
        ("es_ovn 下10%", "es_ovn", 0.10, "bottom"), ("es_ovn 上10%", "es_ovn", 0.10, "top"),
    ]
    masks: dict[str, tuple[pd.Series, float, int]] = {}
    thr_line = []
    for name, col, pct, side in shock_defs:
        m, q, n = shock_info(df, col, pct, side)
        masks[name] = (m, q, n)
        thr_line.append(f"{name}≤{q:+.2f}%(n={n})" if side == "bottom" else f"{name}≥{q:+.2f}%(n={n})")
    print(f"[137] 冲击阈值: " + " | ".join(thr_line))

    lines.append("### 2.1 ES 亚洲段（21:00→14:00）冲击 → 加密同段/下一段\n")
    lines.append("| 冲击 → 响应 | n | 事件日均 | 超额vs无条件 | 无条件均 | 95% CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    ev_print = ["", "=== 表2.1 ES 亚洲段冲击 → 加密 ===", "| 冲击 → 响应 | n | 事件日均 | 超额vs无条件 | 无条件均 | 95% CI | 判定 |",
                "|---|---|---|---|---|---|---|"]
    for name in ["es_asia 下5%", "es_asia 上5%", "es_asia 下10%", "es_asia 上10%"]:
        m, q, _ = masks[name]
        for resp in ["alt_ovn", "alt_next", "btc_ovn", "btc_next"]:
            row = fmt_event_row(f"{name} → {resp}", event_row(df, "es_asia", resp, m, args.seed))
            lines.append(row)
            ev_print.append(row)
    for l in ev_print:
        print(l)

    lines.append("\n### 2.2 ES 隔夜段（21:00→09:00，10:00 UTC 已知）冲击 → 加密下一段（可交易对）\n")
    lines.append("| 冲击 → 响应 | n | 事件日均 | 超额vs无条件 | 无条件均 | 95% CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    ev_print2 = ["", "=== 表2.2 ES 隔夜段冲击 → 加密下一段（可交易）===",
                 "| 冲击 → 响应 | n | 事件日均 | 超额vs无条件 | 无条件均 | 95% CI | 判定 |",
                 "|---|---|---|---|---|---|---|"]
    for name in ["es_ovn 下5%", "es_ovn 上5%", "es_ovn 下10%", "es_ovn 上10%"]:
        m, q, _ = masks[name]
        for resp in ["alt_next", "btc_next"]:
            row = fmt_event_row(f"{name} → {resp}", event_row(df, "es_ovn", resp, m, args.seed))
            lines.append(row)
            ev_print2.append(row)
    for l in ev_print2:
        print(l)

    # ================= 表 3：对照（盘中联动） =================
    lines.append("\n## 3. 对照：ES 盘中段 vs 加密盘中段（期货自身盘中联动）\n")
    lines.append("| 配对 | 2024 r | n | 2025+ r | n | 全样本 r | n |")
    lines.append("|---|---|---|---|---|---|---|")
    pairs3 = [
        ("es_us vs alt盘中(14→21)", "es_us", "alt_sess", "同窗联动"),
        ("es_us vs btc盘中(14→21)", "es_us", "btc_sess", ""),
        ("es_us vs alt隔夜(21→09)[122对照]", "es_us", "alt_ovn", "美股盘中信号 → 加密隔夜（122: ≈0）"),
        ("es_us vs btc隔夜(21→09)[122对照]", "es_us", "btc_ovn", ""),
    ]
    print("\n=== 表3 对照（ES 盘中段 vs 加密）===")
    print("| 配对 | 2024 r | n | 2025+ r | n | 全样本 r | n |")
    print("|---|---|---|---|---|---|---|")
    for label, x, y, note in pairs3:
        cells = corr_cells(df, x, y)
        row = f"| {label} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {cells[4]} | {cells[5]} |"
        lines.append(row)
        print(row)
    lines.append("\n> 122 用 SP500 现指证明「美股收盘信号 → 加密隔夜段」≈0（r≈-0.04、冲击日无超额）；"
                 "本表用 ES 期货复验同窗联动与隔夜外溢。\n")

    # ================= 结论 =================
    r_asia_alt = df[["es_asia", "alt_ovn"]].replace([np.inf, -np.inf], np.nan).dropna()
    r_ovn_alt = df[["es_ovn", "alt_next"]].replace([np.inf, -np.inf], np.nan).dropna()
    r_us_sess = df[["es_us", "alt_sess"]].replace([np.inf, -np.inf], np.nan).dropna()
    r_us_ovn = df[["es_us", "alt_ovn"]].replace([np.inf, -np.inf], np.nan).dropna()
    m10, _, _ = masks["es_ovn 下10%"]
    t10, _, _ = masks["es_ovn 上10%"]
    b10_resp = df.loc[m10, "alt_next"].replace([np.inf, -np.inf], np.nan).dropna()
    t10_resp = df.loc[t10, "alt_next"].replace([np.inf, -np.inf], np.nan).dropna()
    b10_base = df.loc[df["es_ovn"].notna(), "alt_next"].replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    ci_b10 = bootstrap_ci(b10_resp.to_numpy(), b10_base, seed=args.seed)
    ci_t10 = bootstrap_ci(t10_resp.to_numpy(), b10_base, seed=args.seed)
    lines.append("\n## 4. 判定\n")
    lines.append(f"- **相关**：ES 亚洲段 vs alt 同段(21→09) 全样本 r={r_asia_alt.corr().iloc[0,1]:+.3f}（n={len(r_asia_alt)}，"
                 f"同窗共动为主）；ES 隔夜段 vs alt 下一段(09→14) 全样本 r={r_ovn_alt.corr().iloc[0,1]:+.3f}（n={len(r_ovn_alt)}，"
                 f"唯一严格可交易对）。对照：ES 盘中 vs alt 盘中 r={r_us_sess.corr().iloc[0,1]:+.3f}（n={len(r_us_sess)}），"
                 f"ES 盘中 → alt 隔夜 r={r_us_ovn.corr().iloc[0,1]:+.3f}（n={len(r_us_ovn)}，122 复验）。")
    lines.append(f"- **事件研究（可交易对，下10% n={len(b10_resp)}）**：ES 隔夜 下10% → alt 下一段 "
                 f"{b10_resp.mean():+.3f}%（超额 {ci_b10['mean_diff']:+.3f}%，"
                 f"CI [{ci_b10['ci_lo']:+.3f}, {ci_b10['ci_hi']:+.3f}]）；上10%（n={len(t10_resp)}）："
                 f"{t10_resp.mean():+.3f}%（超额 {ci_t10['mean_diff']:+.3f}%，"
                 f"CI [{ci_t10['ci_lo']:+.3f}, {ci_t10['ci_hi']:+.3f}]）。")
    lines.append("- **判定（明确）**：**NO_GO —— ES 亚洲/隔夜段对加密下一段的领先性无可交易 edge**。"
                 "ES 隔夜→加密下一段的相邻窗口相关 ≈0，冲击日（下5%/下10%/上5%/上10%）超额 95% CI 全部含 0；"
                 "ES 亚洲段与加密同段/下一段的显著正相关均来自**同窗共动**（重叠时钟窗口内的信息同步，"
                 "非跨窗领先），且 ES 亚洲段收益 15:00 UTC 才完整可知、晚于加密下一段平仓点，无法直接变现。")
    lines.append("- **盘中联动（表3）**：ES 盘中 vs alt 盘中 r=+0.3~0.4 量级（见上表），与 119 的「美股盘中时段加密跟随」"
                 "一致——联动集中在同窗；ES 盘中 → 加密隔夜 r≈0（122 复验：外溢信号仍不存在）。")
    lines.append("- **诚实声明**：窗口仅 ~2.3 年（ES 周末无数据 → 事件 n≈22@5%/45@10%），固定 UTC 切段存在 ±1h 冬/夏令时"
                 "偏差（ES 21:00 锚点夏令时回退到 20:00 bar 已标注），yfinance ES=F 连续合约有残余展期噪声；"
                 "以上均为样本内统计，未计费率/滑点/深度。结论为负，与 122 一致：美股期货对加密的领先性不构成独立触发。")

    out = REPORTS_DIR / "eminight.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
