"""116_relative_strength_study.py — 山寨相对大饼超额（rel_strength）横截面研究。

命题："大饼见底、山寨蓄力"——在底部窗口，哪类山寨 forward 更好？
- 强币（跑赢 BTC，rel 正）＝资金驻扎蓄力，发动候选
- 弱币（跑输 BTC，rel 深负）＝超跌未反弹，均值回归候选

设计（无前视）：
- 每 episode 随机采样 M 个 1h 时点，对每个有 bar 的币算 rel_24h = alt_ret_24h - btc_ret_24h
  （同一 24h 窗口），及其 forward 24/72/168h 收益。
- 把观测按 rel_24h 分 5 分位，比每分位 forward 均值（横截面因子检验）。
- 交互：wash_cvd 事件（115 的 GO 信号）内，按事件时点 rel_24h 分桶，看 rel 是否
  在信号内部再分层——回答"wash_cvd + 相对强弱 是否构成二阶组合"。

输出：reports/relative_strength_study.md
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

REPORTS_DIR = PROJECT_ROOT / "reports"
HOUR_MS = 3_600_000

# 复用 113 的加载/清洗/episode
_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec)
sys.modules["m113"] = m113
_spec.loader.exec_module(m113)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
episode_of = m113.episode_of
EPISODES = m113.EPISODES


def _close_arrays(tables: dict[str, pd.DataFrame]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    out = {}
    for s, t in tables.items():
        ts = t.index.to_numpy(dtype=np.int64)
        cl = t["close"].to_numpy(dtype=float)
        out[s] = (ts, cl)
    return out


def _fwd_pct(arr_ts: np.ndarray, arr_close: np.ndarray, ts: int, h_hours: int, max_gap_ms: int) -> float | None:
    pos = np.searchsorted(arr_ts, ts, side="right") - 1
    if pos < 0:
        return None
    base_ts = int(arr_ts[pos])
    if base_ts != ts:
        return None
    base = arr_close[pos]
    target = ts + h_hours * HOUR_MS
    tpos = np.searchsorted(arr_ts, target, side="right") - 1
    if tpos <= pos:
        return None
    fts_ = int(arr_tpos := arr_ts[tpos])
    if fts_ > target or (target - fts_) >= max_gap_ms:
        return None
    f = arr_close[tpos]
    if not np.isfinite(base) or base <= 0 or not np.isfinite(f):
        return None
    return (f / base - 1.0) * 100.0


def _ret_at(arr_ts: np.ndarray, arr_close: np.ndarray, ts: int, h_hours: int) -> float | None:
    pos = np.searchsorted(arr_ts, ts, side="right") - 1
    if pos < 0 or int(arr_ts[pos]) != ts:
        return None
    bpos = np.searchsorted(arr_ts, ts - h_hours * HOUR_MS, side="right") - 1
    if bpos < 0 or bpos >= pos:
        return None
    b = arr_close[bpos]
    c = arr_close[pos]
    if not np.isfinite(b) or b <= 0 or not np.isfinite(c):
        return None
    return (c / b - 1.0) * 100.0


def collect_observations(tables, arrs, btc, pool: np.ndarray, horizon_signal: int, rng,
                         n_sample: int) -> pd.DataFrame:
    """每 episode：采样时点，收集 (t, sym, rel, fwd24, fwd72) 观测。"""
    btc_ts, btc_close = arrs[btc]
    rows = []
    # 所有 symbol 在 pool 时点的 bar 存在性（asof）
    for t in rng.choice(pool, size=min(n_sample, len(pool)), replace=False):
        t = int(t)
        btc_ret = _ret_at(btc_ts, btc_close, t, horizon_signal)
        if btc_ret is None:
            continue
        for sym, (ats, acl) in arrs.items():
            if sym == btc:
                continue
            alt_ret = _ret_at(ats, acl, t, horizon_signal)
            if alt_ret is None:
                continue
            fwd24 = _fwd_pct(ats, acl, t, 24, 2 * HOUR_MS)
            fwd72 = _fwd_pct(ats, acl, t, 72, 2 * HOUR_MS)
            if fwd24 is None or fwd72 is None:
                continue
            rows.append((t, sym, alt_ret - btc_ret, fwd24, fwd72))
    return pd.DataFrame(rows, columns=["ts", "symbol", "rel", "fwd24", "fwd72"])


def bucket_report(df: pd.DataFrame, label: str) -> list[str]:
    lines = [f"### {label}\n"]
    if df.empty or len(df) < 50:
        lines.append("无足够观测。")
        return lines
    df = df.copy()
    try:
        q = pd.qcut(df["rel"], 5, labels=["Q1弱", "Q2", "Q3", "Q4", "Q5强"], duplicates="drop")
    except ValueError:
        lines.append("rel 无足够变体（全集中）。")
        return lines
    df["bucket"] = q
    lines.append("| 分位 | rel均值 | n | fwd24h均 | fwd72h均 | 24h胜率 |")
    lines.append("|---|---|---|---|---|---|")
    for b in ["Q1弱", "Q2", "Q3", "Q4", "Q5强"]:
        g = df[df["bucket"] == b]
        if g.empty:
            continue
        lines.append(f"| {b} | {g['rel'].mean():+.1f}% | {len(g)} | {g['fwd24'].mean():+.2f}% | "
                     f"{g['fwd72'].mean():+.2f}% | {(g['fwd24'] > 0).mean() * 100:.0f}% |")
    # 强-弱价差
    q1 = df[df["bucket"] == "Q1弱"]
    q5 = df[df["bucket"] == "Q5强"]
    if not q1.empty and not q5.empty:
        lines.append(f"\n强-弱价差 (Q5-Q1) fwd24: {q5['fwd24'].mean() - q1['fwd24'].mean():+.2f}%  |  fwd72: {q5['fwd72'].mean() - q1['fwd72'].mean():+.2f}%")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-sample", type=int, default=2000, help="每 episode 采样时点数")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    btc = "BTCUSDT"
    if btc not in symbols:
        symbols = symbols + [btc]
    tables = load_price_ctx(symbols)
    arrs = _close_arrays(tables)
    if btc not in arrs:
        print("缺少 BTCUSDT 价格。")
        return
    rng = np.random.default_rng(args.seed)

    lines: list[str] = []
    lines.append("# 山寨相对大饼超额（rel_strength）横截面研究\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- rel_24h = alt_ret_24h − btc_ret_24h（同一 24h 窗口），无前视，forward 从信号 bar 起")
    lines.append(f"- 分位: 每 episode 内 rel 5 分位；Q1=跑输 BTC 最多，Q5=跑赢最多")
    lines.append("- 基线参考: 全观测 fwd24 均值")

    # 1) 纯 rel 因子（每 episode）
    lines.append("\n## 一、纯相对强弱因子（每 episode 分位）\n")
    summary = []
    for name, s, e in EPISODES:
        start_ms = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
        end_ms = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
        pool: list[int] = []
        for sym, (ats, _) in arrs.items():
            sub = ats[(ats >= start_ms) & (ats <= end_ms)]
            if len(sub):
                pool.extend(sub.tolist())
        if not pool:
            lines.append(f"\n## {name} — 无数据\n")
            continue
        pool = np.array(sorted(set(pool)))
        obs = collect_observations(tables, arrs, btc, pool, 24, rng, args.n_sample)
        if obs.empty:
            lines.append(f"\n## {name} — 无观测\n")
            continue
        lines.append(f"\n### {name}（观测 n={len(obs)}）")
        base24 = obs["fwd24"].mean()
        lines.append(f"全观测 fwd24 均值: {base24:+.2f}%\n")
        lines.extend(bucket_report(obs, f"rel_24h 分位 — {name}"))
        # 记录 Q5-Q1 价差供对照表
        try:
            qq = pd.qcut(obs["rel"], 5, labels=[0, 1, 2, 3, 4], duplicates="drop")
            q1 = obs[qq == 0]["fwd24"].mean()
            q5 = obs[qq == 4]["fwd24"].mean()
            summary.append((name, len(obs), q1, q5, q5 - q1))
        except Exception:
            summary.append((name, len(obs), np.nan, np.nan, np.nan))

    lines.append("\n## 跨 episode Q1/Q5 对照\n")
    lines.append("| episode | n | Q1弱 fwd24 | Q5强 fwd24 | 价差(Q5−Q1) |")
    lines.append("|---|---|---|---|---|")
    for name, n, q1, q5, sp in summary:
        lines.append(f"| {name} | {n} | {q1:+.2f}% | {q5:+.2f}% | {sp:+.2f}% |")

    # 2) wash_cvd 事件内按 rel 分层
    lines.append("\n## 二、wash_cvd 事件内 rel 分层（二阶组合检验）\n")
    # 复用 115 的 wash_cvd 检测
    spec2 = importlib.util.spec_from_file_location(
        "m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
    m115 = importlib.util.module_from_spec(spec2)
    sys.modules["m115"] = m115
    spec2.loader.exec_module(m115)
    fundings = load_funding_series(symbols)
    ev_parts = []
    for sym, ctx in tables.items():
        ev = m115.detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(columns=["symbol", "timestamp"])
    if events.empty:
        lines.append("wash_cvd 无事件。")
    else:
        events["episode"] = episode_of(events["timestamp"].to_numpy())
        btc_ts, btc_close = arrs[btc]
        rows = []
        for _, r in events.iterrows():
            ts = int(r["timestamp"])
            sym = r["symbol"]
            ats, acl = arrs[sym]
            btc_ret = _ret_at(btc_ts, btc_close, ts, 24)
            alt_ret = _ret_at(ats, acl, ts, 24)
            fwd24 = _fwd_pct(ats, acl, ts, 24, 2 * HOUR_MS)
            fwd72 = _fwd_pct(ats, acl, ts, 72, 2 * HOUR_MS)
            if btc_ret is None or alt_ret is None or fwd24 is None or fwd72 is None:
                continue
            rows.append((r["episode"], sym, alt_ret - btc_ret, fwd24, fwd72))
        edf = pd.DataFrame(rows, columns=["episode", "symbol", "rel", "fwd24", "fwd72"])
        lines.append(f"wash_cvd 事件共 {len(edf)}（有完整 rel+forward）\n")
        lines.append("| episode | n | 全事件 fwd24 | Q1弱 fwd24 | Q5强 fwd24 | 价差 |")
        lines.append("|---|---|---|---|---|---|")
        for name, s, e in EPISODES:
            g = edf[edf["episode"] == name]
            if g.empty or len(g) < 15:
                lines.append(f"| {name} | {len(g)} | - | - | - | - |")
                continue
            try:
                qq = pd.qcut(g["rel"], 5, labels=[0, 1, 2, 3, 4], duplicates="drop")
                q1 = g[qq == 0]["fwd24"].mean()
                q5 = g[qq == 4]["fwd24"].mean()
            except Exception:
                q1 = q5 = np.nan
            lines.append(f"| {name} | {len(g)} | {g['fwd24'].mean():+.2f}% | {q1:+.2f}% | {q5:+.2f}% | {q5 - q1:+.2f}% |")
        lines.append("\n> 若 Q5 显著 > Q1 → wash_cvd 内部再加'相对强弱'可提升；若价差≈0 → rel 不提供额外信息。")

    out = REPORTS_DIR / "relative_strength_study.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
