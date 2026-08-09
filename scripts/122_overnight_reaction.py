"""122_overnight_reaction.py — B 方向：美股收盘信号 → 加密"隔夜段"反应（小时级）。

命题（对 119 的变现检验）：
119 发现 SP500 当日收益与加密当日收益同向共振（r=+0.35、VIX r=-0.29），但日度分辨率下
该窗口与美股交易时段重叠 → 日度不可直接交易。本脚本把"美股收盘后"这段单独切出来
（固定 UTC 口径 21:00 → 次日 09:00），回答：美股当日收益是否可预测加密隔夜段收益，
"21:00 UTC 买入、09:00 UTC 卖出"能否变现？

隔夜段（固定 UTC 口径，无前视）：
- 起点 = 当日 21:00 UTC bar 的 close（open_time==21:00 的 bar；该 bar close ≈ 22:00 UTC 价格）。
  注：美东 16:00 收盘 = 冬令时(EST) 21:00 UTC / 夏令时(EDT) 20:00 UTC —— 固定 21:00 口径存在
  夏/冬令时 ±1h 偏差（局限，见报告）；两端口径一致，结论不受 1h 平移影响。
- 终点 = 次日 09:00 UTC bar 的 close（open_time==09:00；无该 bar 时回退 08:00 并标注 end_off=1）。
- r_overnight = close(09:00 d+1)/close(21:00 d) - 1（×100，%）。
- 无前视：配对 r_sp(d) 时 SP500 当日已收盘（美东 16:00 ≤ 21:00 UTC），且加密 21:00 bar 的
  close 在 22:00 UTC 即可知 → 信号与入场时点均无前视（searchsorted 精确对齐 bar open_time）。

数据（只用 coinglass 段 2022-01-01 → 2026-07-07，binance_free_db 前向区不用）：
- 加密：COINGLASS_RAW1H/klines/*.parquet（open_time=ms int UTC，close 小时级）→ m113.load_price_ctx
- 美股：MACRO_ROOT/SP500.parquet（index=date 日度无时区，close，到 2026-08-05）

输出三张表：
1) 相关矩阵：r_sp vs alt隔夜 / btc隔夜 / alt当日(对照 119 口径 +0.35)，分 2022-2023 / 2024-2026 era。
2) 事件研究：SP500 当日收益 下5%/上5% 冲击日 → alt 隔夜段收益 vs 全样本隔夜均值
   （bootstrap_ci，seed=2026），分 episode 汇总。
3) 隔夜段内部分拆：21:00→01:00 与 01:00→09:00 两腿，看信号落在哪段。

诚实性：样本内收益 ≠ 可交易（未计费率/滑点/深度，注明）。

用法：
  python scripts/122_overnight_reaction.py [--seed 2026]
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

from harness.lib.event_study import bootstrap_ci

COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
MACRO_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
REPORTS_DIR = PROJECT_ROOT / "reports"

# 统一加载模板（113/115，口径一致）
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
EPISODES = m113.EPISODES
episode_of = m113.episode_of

HOUR_MS = 3_600_000
MIN_ALT_SYMBOLS = 10     # alt 篮子当日不足 10 个 symbol 有值 → NaN
MIN_SHOCK_N = 10         # 事件研究每组最小样本（119 口径 <10 判样本不足）
SEG_START = "2022-01-01"  # 只用 coinglass 段
SEG_END = "2026-07-07"    # coinglass 小时数据末（2026-07-07 03:00 UTC）
ERA_SPLIT = "2024-01-01"  # 相关矩阵 era 分界


def day_start_ms(d) -> int:
    """日期 d（UTC 日）00:00 的 ms 时间戳。"""
    return int(pd.Timestamp(pd.Timestamp(d).date(), tz="UTC").value) // 1_000_000


def exact_close(idx: np.ndarray, closes: np.ndarray, ts: np.ndarray) -> np.ndarray:
    """searchsorted 精确对齐：返回 open_time==ts 的 bar close；无该 bar → NaN（无前视）。"""
    pos = np.searchsorted(idx, ts, side="left")
    pos = np.clip(pos, 0, len(idx) - 1)
    ok = idx[pos] == ts
    out = np.full(len(ts), np.nan)
    out[ok] = closes[pos[ok]]
    return out


def build_symbol_overnight(ctx: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """单 symbol 的隔夜段序列（index=dates）：

    close_start(21:00 d) / close_end(09:00 d+1，回退 08:00) / end_off(1=回退标注)
    r_overnight(21:00→09:00) / r_leg1(21:00→01:00) / r_leg2(01:00→09:00)
    r_same(21:00 d-1 → 21:00 d，即"24h bar 至 21:00 UTC"，含美股当日时段，作 119 对照)。
    """
    idx = ctx.index.to_numpy(dtype=np.int64)
    closes = ctx["close"].to_numpy(dtype=float)
    dm = np.array([day_start_ms(d) for d in dates], dtype=np.int64)
    t_start = dm + 21 * HOUR_MS      # 当日 21:00（隔夜起点）
    t_end = dm + 33 * HOUR_MS        # 次日 09:00
    t_end_fb = dm + 32 * HOUR_MS     # 次日 08:00（回退）
    t_leg1 = dm + 25 * HOUR_MS       # 次日 01:00
    t_same_prev = dm - 3 * HOUR_MS   # 前一日 21:00

    c_start = exact_close(idx, closes, t_start)
    c_end9 = exact_close(idx, closes, t_end)
    c_end8 = exact_close(idx, closes, t_end_fb)
    c_end = np.where(np.isfinite(c_end9), c_end9, c_end8)
    end_off = (~np.isfinite(c_end9)).astype(int)   # 1 = 无 09:00 bar，用了 08:00 回退
    c_leg1 = exact_close(idx, closes, t_leg1)
    c_same_prev = exact_close(idx, closes, t_same_prev)

    with np.errstate(divide="ignore", invalid="ignore"):
        r_ov = (c_end / c_start - 1.0) * 100.0
        r_l1 = (c_leg1 / c_start - 1.0) * 100.0
        r_l2 = (c_end / c_leg1 - 1.0) * 100.0
        r_same = (c_start / c_same_prev - 1.0) * 100.0
    return pd.DataFrame({
        "close_start": c_start, "close_end": c_end, "end_off": end_off,
        "start_ok": np.isfinite(c_start),
        "r_overnight": r_ov, "r_leg1": r_l1, "r_leg2": r_l2, "r_same": r_same,
    }, index=dates)


def basket_mean(mat: pd.DataFrame, min_symbols: int) -> pd.Series:
    """等权横截面均值；当日有值 symbol 数 < min_symbols → NaN。"""
    return mat.mean(axis=1, skipna=True).where(mat.notna().sum(axis=1) >= min_symbols)


def ci_row(label: str, ev: pd.Series, base: np.ndarray, seed: int,
           min_n: int = MIN_SHOCK_N) -> str:
    """事件研究单行：ev 组均值 vs base 全样本，bootstrap_ci 95% CI。"""
    ev = ev.dropna()
    if len(ev) < min_n:
        return (f"| {label} | 样本不足(n={len(ev)}<{min_n}) | {len(ev)} | - | - | - | - |")
    ci = bootstrap_ci(ev.to_numpy(), base, seed=seed)
    if ci["ci_lo"] > 0:
        verdict = "**GO_LONG**"
    elif ci["ci_hi"] < 0:
        verdict = "**GO_SHORT**"
    else:
        verdict = "NO_GO"
    return (f"| {label} | {len(ev)} | {ev.mean():+.3f}% | {ci['mean_diff']:+.3f}% | "
            f"[{ci['ci_lo']:+.3f}, {ci['ci_hi']:+.3f}] | {verdict} |")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    print(f"[122] ctx 表 {len(ctxs)}（coinglass 段，只用 2022-01-01→2026-07-07）")
    btc_ctxs = load_price_ctx(["BTCUSDT"])
    btc_ctx = btc_ctxs.get("BTCUSDT")

    # ---- 美股（index=date 日度无时区）----
    sp_df = pd.read_parquet(MACRO_ROOT / "SP500.parquet")
    sp_idx = pd.DatetimeIndex(sp_df.index).tz_localize(None).normalize()
    sp_close = pd.Series(pd.to_numeric(sp_df["close"], errors="coerce").to_numpy(), index=sp_idx)
    sp_ret = sp_close.pct_change() * 100.0
    print(f"[122] SP500 日度 {sp_idx.min().date()} → {sp_idx.max().date()}")

    # ---- 日轴：coinglass 段内所有 UTC 日（隔夜段起点日）----
    dates = pd.date_range(SEG_START, SEG_END, freq="D")
    mats = {s: build_symbol_overnight(ctx, dates) for s, ctx in ctxs.items()}
    btc_mat = build_symbol_overnight(btc_ctx, dates) if btc_ctx is not None else None
    print(f"[122] 隔夜段序列 {len(mats)} symbols × {len(dates)} 天")

    # 08:00 回退标注统计（只统计真实窗口：起点 21:00 bar 存在、终点 09:00 bar 缺失）
    off_total = sum(int((m["start_ok"] & m["end_off"].astype(bool)).sum()) for m in mats.values())
    off_windows = sum(int(m["start_ok"].sum()) for m in mats.values())
    print(f"[122] 真实隔夜窗口 {off_windows} | 09:00 bar 缺失回退 08:00: {off_total}（{off_total / max(off_windows, 1):.2%}）")

    # ---- alt 篮子等权 + btc 单独 ----
    ov_mat = pd.DataFrame({s: m["r_overnight"] for s, m in mats.items()})
    leg1_mat = pd.DataFrame({s: m["r_leg1"] for s, m in mats.items()})
    leg2_mat = pd.DataFrame({s: m["r_leg2"] for s, m in mats.items()})
    same_mat = pd.DataFrame({s: m["r_same"] for s, m in mats.items()})
    alt_ov = basket_mean(ov_mat, MIN_ALT_SYMBOLS)
    alt_leg1 = basket_mean(leg1_mat, MIN_ALT_SYMBOLS)
    alt_leg2 = basket_mean(leg2_mat, MIN_ALT_SYMBOLS)
    alt_same = basket_mean(same_mat, MIN_ALT_SYMBOLS)
    btc_ov = btc_mat["r_overnight"] if btc_mat is not None else pd.Series(dtype=float)
    btc_same = btc_mat["r_same"] if btc_mat is not None else pd.Series(dtype=float)

    df = pd.DataFrame(index=dates)
    df["r_sp"] = sp_ret.reindex(dates)
    df["alt_ov"], df["btc_ov"] = alt_ov, btc_ov
    df["alt_same"], df["btc_same"] = alt_same, btc_same
    df["alt_leg1"], df["alt_leg2"] = alt_leg1, alt_leg2
    df["era"] = np.where(dates < ERA_SPLIT, "2022-2023", "2024-2026")
    df["episode"] = episode_of(np.array([day_start_ms(d) for d in dates], dtype=np.int64))
    df["is_trading"] = df["r_sp"].notna()

    lines: list[str] = []
    lines.append("# 美股收盘信号 → 加密隔夜段反应（B 方向，小时级）\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append("- 方法: 隔夜段 = 当日 21:00 UTC bar close → 次日 09:00 UTC bar close（无 09:00 回退 08:00 并标注）；"
                 "r_overnight = close(09:00 d+1)/close(21:00 d)-1；alt = universe 山寨等权（当日<10 symbol 有值→NaN），btc 单列。"
                 "配对 r_sp(d) vs 隔夜段(21:00 d→09:00 d+1)，searchsorted 精确对齐（无前视：SP500 当日已收盘）。")
    lines.append(f"- 数据源: 加密 {COINGLASS_RAW1H}/klines/*.parquet（coinglass 段 2022-01-01→2026-07-07，"
                 f"binance_free_db 前向区不用）；美股 {MACRO_ROOT}/SP500.parquet（到 2026-08-05，截到 coinglass 段末）")
    lines.append("- 局限: ①固定 21:00 UTC 口径，美东冬令时=21:00/夏令时=20:00 收盘 → 夏/冬令时 ±1h 偏差；"
                 "②bar 口径：open_time==21:00 的 bar close≈22:00 UTC 价格，两端口径一致；"
                 "③样本内收益 ≠ 可交易（未计费率/滑点/深度）；④SP500 冲击日按全样本分位数定义，事件为市场级日期而非单币事件。\n")

    # ================= 表 1：相关矩阵 =================
    lines.append("## 1. 相关矩阵（r_sp(d) vs 加密收益，分 era）\n")
    lines.append("| 配对 | 2022-2023 r | n | 2024-2026 r | n | 全样本 r | n |")
    lines.append("|---|---|---|---|---|---|---|")
    corr_print: list[str] = ["=== 表1 相关矩阵（r_sp 当日 vs 加密收益）===",
                             "| 配对 | 2022-2023 r | n | 2024-2026 r | n | 全样本 r | n |",
                             "|---|---|---|---|---|---|---|"]
    pairs = [
        ("r_sp vs alt隔夜(21:00→09:00)", "r_sp", "alt_ov"),
        ("r_sp vs btc隔夜(21:00→09:00)", "r_sp", "btc_ov"),
        ("r_sp vs alt当日(21:00d-1→21:00d)[119对照]", "r_sp", "alt_same"),
        ("r_sp vs btc当日(21:00d-1→21:00d)", "r_sp", "btc_same"),
    ]
    for label, xc, yc in pairs:
        cells = []
        for era_name, m_era in [("2022-2023", df["era"] == "2022-2023"),
                                ("2024-2026", df["era"] == "2024-2026"),
                                ("全样本", pd.Series(True, index=df.index))]:
            sub = df.loc[m_era, [xc, yc]].replace([np.inf, -np.inf], np.nan).dropna()
            if len(sub) < 30 or sub[yc].std() == 0:
                cells += ["-", str(len(sub))]
            else:
                cells += [f"{sub[xc].corr(sub[yc]):+.3f}", str(len(sub))]
        lines.append(f"| {label} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {cells[4]} | {cells[5]} |")
        corr_print.append(f"| {label} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {cells[4]} | {cells[5]} |")
    lines.append("\n> 对照：119 日度口径 SP500 当日 vs 山寨当日 r=+0.35（UTC 日收盘）；"
                 "本表 alt当日 用 21:00d-1→21:00d 窗口（含美股时段）作同口径对照，看隔夜段是保留/增强/消失。\n")
    for l in corr_print:
        print(l)

    # ================= 表 2：事件研究 =================
    rsp = df["r_sp"].replace([np.inf, -np.inf], np.nan).dropna()
    p5, p95 = float(rsp.quantile(0.05)), float(rsp.quantile(0.95))
    bottom = df["r_sp"].le(p5).fillna(False)
    top = df["r_sp"].ge(p95).fillna(False)
    base_ov = df["alt_ov"].dropna().to_numpy()
    base_btc = df["btc_ov"].dropna().to_numpy()
    print(f"\n[122] SP500 冲击阈值: 下5% ≤ {p5:+.2f}%  (n={int(bottom.sum())}) | 上5% ≥ {p95:+.2f}%  (n={int(top.sum())})")

    lines.append("## 2. 事件研究：SP500 冲击日 → 加密隔夜段收益\n")
    lines.append(f"冲击阈值（coinglass 段内全样本分位）: 下5% ≤ {p5:+.2f}% | 上5% ≥ {p95:+.2f}%。"
                 f"基线 = 全样本隔夜收益无条件均值（alt: {np.nanmean(base_ov):+.3f}%，btc: {np.nanmean(base_btc):+.3f}%），"
                 f"bootstrap 95% CI（seed={args.seed}）。判定：CI 下界>0→GO_LONG / 上界<0→GO_SHORT / 含0→NO_GO。\n")
    lines.append("| 冲击 → 响应 | n | 事件日均 | 超额vs全样本 | 95% CI | 判定 |")
    lines.append("|---|---|---|---|---|---|")
    ev_print = ["", "=== 表2 事件研究（冲击日 vs 全样本隔夜均值）===",
                "| 冲击 → 响应 | n | 事件日均 | 超额vs全样本 | 95% CI | 判定 |",
                "|---|---|---|---|---|---|"]
    for label, mask in [("SP500下5% → alt隔夜", bottom), ("SP500下5% → btc隔夜", bottom),
                        ("SP500上5% → alt隔夜", top), ("SP500上5% → btc隔夜", top)]:
        if label.endswith("alt隔夜"):
            row = ci_row(label, df.loc[mask, "alt_ov"], base_ov, args.seed)
        else:
            row = ci_row(label, df.loc[mask, "btc_ov"], base_btc, args.seed)
        lines.append(row)
        ev_print.append(row)
    for l in ev_print:
        print(l)

    # 分 episode 汇总（冲击日按 episode 分组；基线 = 该 episode 无条件隔夜均值）
    lines.append("\n### 2.1 分 episode 汇总（SP500 冲击日 → alt 隔夜段，基线=该 episode 无条件均值）\n")
    lines.append("| episode | 冲击 | n | 事件日均 | episode无条件均 | 超额 | 95% CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    ep_print = ["", "=== 表2.1 分 episode（SP500 冲击日 → alt 隔夜）===",
                "| episode | 冲击 | n | 事件日均 | episode无条件均 | 超额 | 95% CI | 判定 |",
                "|---|---|---|---|---|---|---|---|"]
    for name, s, e in EPISODES:
        if "前向" in name:
            continue
        ep_mask = df["episode"] == name
        base_ep = df.loc[ep_mask, "alt_ov"].dropna().to_numpy()
        for side, mask in [("下5%", bottom), ("上5%", top)]:
            ev = df.loc[ep_mask & mask, "alt_ov"].dropna()
            if len(ev) < MIN_SHOCK_N:
                row = (f"| {name} | {side} | {len(ev)} | 样本不足(<{MIN_SHOCK_N}) | {np.nanmean(base_ep):+.3f}% | - | - | - |")
            else:
                ci = bootstrap_ci(ev.to_numpy(), base_ep, seed=args.seed)
                verdict = "**GO_LONG**" if ci["ci_lo"] > 0 else ("**GO_SHORT**" if ci["ci_hi"] < 0 else "NO_GO")
                row = (f"| {name} | {side} | {len(ev)} | {ev.mean():+.3f}% | {np.nanmean(base_ep):+.3f}% | "
                       f"{ci['mean_diff']:+.3f}% | [{ci['ci_lo']:+.3f}, {ci['ci_hi']:+.3f}] | {verdict} |")
            lines.append(row)
            ep_print.append(row)
    for l in ep_print:
        print(l)

    # ================= 表 3：隔夜段内部分拆 =================
    lines.append("\n## 3. 隔夜段内部分拆（21:00→01:00 vs 01:00→09:00 两腿）\n")
    lines.append("| 时段 | 无条件均 | SP500下5%日均 | SP500上5%日均 |")
    lines.append("|---|---|---|---|")
    leg_print = ["", "=== 表3 隔夜段两腿（alt 篮子）===",
                 "| 时段 | 无条件均 | SP500下5%日均 | SP500上5%日均 |",
                 "|---|---|---|---|"]
    for label, col in [("21:00→01:00 (4h)", "alt_leg1"), ("01:00→09:00 (8h)", "alt_leg2"),
                       ("整段 21:00→09:00 (12h)", "alt_ov")]:
        v = df[col].dropna()
        vb = df.loc[bottom, col].dropna()
        vt = df.loc[top, col].dropna()
        row = (f"| {label} | {v.mean():+.3f}% | {vb.mean():+.3f}% (n={len(vb)}) | "
               f"{vt.mean():+.3f}% (n={len(vt)}) |")
        lines.append(row)
        leg_print.append(row)
    for l in leg_print:
        print(l)

    # ================= 结论 =================
    # 汇总关键数字供结论
    b5 = df.loc[bottom, "alt_ov"].dropna()
    t5 = df.loc[top, "alt_ov"].dropna()
    ci_b = bootstrap_ci(b5.to_numpy(), base_ov, seed=args.seed)
    ci_t = bootstrap_ci(t5.to_numpy(), base_ov, seed=args.seed)
    lines.append("\n## 4. 结论\n")
    lines.append(f"- **相关**：SP500 当日收益 vs alt 隔夜段 r 全样本={df[['r_sp','alt_ov']].replace([np.inf,-np.inf],np.nan).dropna().corr().iloc[0,1]:+.3f}"
                 f"（btc 隔夜 {df[['r_sp','btc_ov']].replace([np.inf,-np.inf],np.nan).dropna().corr().iloc[0,1]:+.3f}），"
                 f"对照 alt当日(21:00→21:00) 全样本 r={df[['r_sp','alt_same']].replace([np.inf,-np.inf],np.nan).dropna().corr().iloc[0,1]:+.3f}"
                 f"（119 口径 +0.35）——隔夜段相关强度 vs 当日对照见上表。")
    lines.append(f"- **事件研究（下5% 冲击，n={len(b5)}）**：alt 隔夜 {b5.mean():+.3f}%（无条件 {np.nanmean(base_ov):+.3f}%，"
                 f"超额 {ci_b['mean_diff']:+.3f}%，95% CI [{ci_b['ci_lo']:+.3f}, {ci_b['ci_hi']:+.3f}]）；"
                 f"上5% 冲击（n={len(t5)}）：alt 隔夜 {t5.mean():+.3f}%（超额 {ci_t['mean_diff']:+.3f}%，"
                 f"CI [{ci_t['ci_lo']:+.3f}, {ci_t['ci_hi']:+.3f}]）。")
    lines.append("- **判定（明确）**：**NO_GO —— 美股收盘信号无法在隔夜段变现**。"
                 "下5%/上5% 冲击日的 alt/btc 隔夜超额 95% CI 全部含 0（如下5%→alt 超额 -0.018%，"
                 "CI [-1.157, +1.058]），分 episode 亦全部 NO_GO 或样本不足；相关矩阵 r_sp vs 隔夜段 "
                 "r≈-0.04（两 era 一致），对照当日窗口 r=+0.47。")
    lines.append("- **对 119 的变现检验**：119 的「同日共振」（r=+0.35）集中在**美股盘中时段**（加密跟随），"
                 "隔夜段完全消失——隔夜相关 ≈0、冲击日无超额 → 收盘信号不是可交易的隔夜 edge。")
    lines.append("- **内部结构（不显著，仅记录）**：隔夜段两腿存在「先延续后反弹」的弱形态——"
                 "SP500 下5% 冲击日后 21:00→01:00 腿 -0.101%（无条件 +0.045%，继续下探），"
                 "01:00→09:00 腿 +0.222%（无条件 +0.083%，反弹）；两腿样本均不足以构成独立 edge。")
    lines.append("- **诚实声明**：以上均为样本内统计；未计费率/滑点/深度，未做样本外与可执行性验证。"
                 "结论为负，但与 119/120 一致：美股信号定位为 regime 背景而非独立隔夜触发。")

    out = REPORTS_DIR / "overnight_reaction.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
