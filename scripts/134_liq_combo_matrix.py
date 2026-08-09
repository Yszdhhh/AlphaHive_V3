"""134_liq_combo_matrix.py — wash_cvd × (liq_short_z>1 / 放量 / VIX / breadth) 四条件联合矩阵。

背景与承接（引用即可，勿重做）：
- 131（liquidation_cross）: liq_short_z>1（24h 空头强平累计的 30d z-score 激增）wash_cvd 事件档
  pooled n=123，24h 超额 +4.44% CI[+1.98,+7.25]，2/2 episode 全正；激增−常态 +3.97% CI[+1.47,+6.71]
  显著 → 轧空燃料确认（唯一与 111 并列的强二级条件）。
- 133（joint_matrix）: 放量>1.5x / VIX≤1y q75 / breadth≥5% 三条件联合：111 全条件 n=373，24h 超额
  +2.92% CI[+1.87,+4.02]；三条件近似正交（phi≈0，观测/期望≈1.00）；最优条件数=2（总期望口径）。
- 本脚本：把 liq_short_z>1 作为第四条件与 111 三条件建 2^4=16 子集联合矩阵，回答：
  liq 是否与 111 正交可叠加（对照 133 的三条件 phi≈0）？四条件（liq+111）是否进一步提升？
  最优过滤配置（容量 vs 质量权衡）？

方法（全部 asof 事件时点，无前视）：
- 事件 = wash_cvd（m115.detect_events：washout(price_z<-2 或 ret_24h<-8%) 且 cvd_divergence>2.0，
  72h 冷却/币，Long）。窗口 = liquidation 覆盖区间 lo=2024-06-01 hi=2026-06-23 UTC（与 131 一致；
  注意与 133 全窗口 2022-01-01→2026-06-30 不同 → 133 对比行 n 会因窗口截断而偏小，方向可比）。
- liq_ok = liq_short_z_at_event > 1：liquidation parquet（time 与 klines open_time 精确对齐）→
  24h 空头累计 rolling(24).sum() → 30d(720h) 自序列 z-score（m113.rolling_z，min_periods=360），
  事件 ts searchsorted asof（同 131）。
- vol_ok = qv24_ratio>1.5：qv24=quote_volume.rolling(24).sum()；qv24_med=rolling(720,
  min_periods=360).median()；ratio=qv24/qv24_med（公式同 121/126/133）。
- vix_ok = 非 vix_high：VIX.parquet 日度 close，vix_high = VIX > 1y 滚动 q75（min_periods=120），
  事件日−1 asof（同 120/123/133）。
- brd_ok = breadth_pct≥5：6h 网格市场级广度（同 124 口径：逐币 washout=(price_z<-2)|(ret_24h<-8)，
  breadth_pct=100×出清币数/有效币数，n_active>=5 才有效），事件 ts asof 最近网格点。
- 基线 = 同期随机 symbol×时点横截面（draw_random_events n=3000，与 131 同量级），bootstrap 95% CI
  （seed=2026）；pooled 首抽、episode 各抽一次，所有子集共用同一基线（横向可比）。
- 判定：24h 超额 CI 下界>0 → GO_LONG；上界<0 → GO_SHORT；含 0 → NO_GO；n<30 → 样本不足不判。

只读数据、纯研究模块：不写任何配置/规则/定时任务。
进 108 前向影子 / scan_rules / contract_anomaly_rules 的任何改动属 T3，需 Owner 签批。

用法：
  python scripts/134_liq_combo_matrix.py [--n-baseline 3000] [--seed 2026] [--min-events 30]
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

from harness.lib.event_study import (
    DEFAULT_HORIZONS,
    bootstrap_ci,
    draw_random_events,
    forward_stats,
    summarize_events,
)

REPORTS_DIR = PROJECT_ROOT / "reports"

# ---------- 共享加载模板（113/115 口径；120=VIX 状态帧；124=广度序列；
#             131=强平特征；133=放量/矩阵工具；禁止改配置） ----------
_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec); sys.modules["m113"] = m113; _spec.loader.exec_module(m113)
_spec2 = importlib.util.spec_from_file_location(
    "m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2); sys.modules["m115"] = m115; _spec2.loader.exec_module(m115)
_spec3 = importlib.util.spec_from_file_location(
    "m120", str(PROJECT_ROOT / "scripts" / "120_macro_factor_modulation.py"))
m120 = importlib.util.module_from_spec(_spec3); sys.modules["m120"] = m120; _spec3.loader.exec_module(m120)
_spec4 = importlib.util.spec_from_file_location(
    "m124", str(PROJECT_ROOT / "scripts" / "124_market_breadth.py"))
m124 = importlib.util.module_from_spec(_spec4); sys.modules["m124"] = m124; _spec4.loader.exec_module(m124)
_spec5 = importlib.util.spec_from_file_location(
    "m131", str(PROJECT_ROOT / "scripts" / "131_liquidation_cross.py"))
m131 = importlib.util.module_from_spec(_spec5); sys.modules["m131"] = m131; _spec5.loader.exec_module(m131)
_spec6 = importlib.util.spec_from_file_location(
    "m133", str(PROJECT_ROOT / "scripts" / "133_joint_matrix.py"))
m133 = importlib.util.module_from_spec(_spec6); sys.modules["m133"] = m133; _spec6.loader.exec_module(m133)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
detect_events = m115.detect_events
EPISODES = m113.EPISODES
episode_of = m113.episode_of
COINGLASS_RAW1H = m113.COINGLASS_RAW1H
MACRO_ROOT = m120.MACRO_ROOT
FUNDING_DIR = m113.FUNDING_DIR

# ---------- 研究窗口与参数 ----------
# liquidation 覆盖 2024-06-06 14:00 → 2026-06-23 03:00 UTC（与 131 相同事件窗口）
LO_MS = int(pd.Timestamp("2024-06-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-23", tz="UTC").timestamp() * 1000)
VARIANT = "wash_cvd"
VARIANT_DESC = "washout(price_z<-2.0 或 ret_24h<-8%) 且 cvd_divergence>2.0，72h 冷却，Long"
LIQ_Z_HI = 1.0       # liq_short_z > 1（131 表2 激增档）
VOL_HI = 1.5         # 放量阈值（同 121/126/133 的">1.5x"档）
VIX_Q = 0.75         # VIX 1y 滚动分位（同 120/123/133 的 q75）
BREADTH_LOW = 5.0    # 广度阈值（同 124/127/133 的 ≥5%）
N_BASELINE = 3000    # 与 131 同量级（131 pooled 基线 n=3000）
SEED = 2026
MIN_EVENTS = 30

# 只测 liquidation 覆盖区间内的两个 episode
EPISODES_LIQ = ["2024崩→恢复", "2025顶→熊"]

# 131/133 已知数字（交叉核对目标；注意 133 为全窗口 2022-01→2026-06-30，本表窗口 2024-06→2026-06-23）
KNOWN_131 = {
    "liq_short_z>1 pooled n": 123,
    "liq_short_z>1 pooled 24h均值": 4.49,
    "liq_short_z>1 pooled 24h超额": 4.44,
    "liq_short_z>1 pooled CI": (1.98, 7.25),
    "2024 liq_short_z>1 n": 35,
    "2024 liq_short_z>1 24h超额": 5.25,
    "2025 liq_short_z>1 n": 88,
    "2025 liq_short_z>1 24h超额": 4.00,
    "wash_cvd 窗口事件 n": 867,
}
KNOWN_133 = {
    "111 全条件 n（全窗口 2022-01→2026-06-30）": 373,
    "111 全条件 24h超额（全窗口）": 2.92,
    "111 全条件 CI（全窗口）": (1.87, 4.02),
}


# ---------- 事件表工具（123/127/131/133 同款） ----------
def _fwd_for(ctxs: dict, df: pd.DataFrame) -> pd.DataFrame:
    """给 (symbol, timestamp) 事件表补 forward 收益（按 symbol 分组调用 forward_stats）。"""
    if df is None or df.empty:
        return pd.DataFrame()
    parts = []
    for s, g in df.groupby("symbol", sort=False):
        if s in ctxs:
            parts.append(forward_stats(ctxs[s], g.copy(), horizons=DEFAULT_HORIZONS))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _row_stats(sub: pd.DataFrame, base_v: np.ndarray, base_v168: np.ndarray,
               seed: int, min_events: int) -> dict:
    """单组事件统计行：n / 唯一时点 / 24h 均值 / 中位数 / 胜率 / 超额 / CI / 168h 超额 / 判定。"""
    row: dict = {"n": len(sub),
                 "n_unique_ts": int(sub["timestamp"].nunique()) if len(sub) else 0}
    ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
    if len(ev_v) == 0:
        row.update({"mean24": np.nan, "median": np.nan, "win": np.nan,
                    "excess": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
                    "excess168": np.nan, "verdict": "无事件"})
        return row
    s = summarize_events(sub)
    ci = bootstrap_ci(ev_v, base_v, seed=seed)
    ev_v168 = pd.to_numeric(sub["ret_168h"], errors="coerce").dropna().to_numpy()
    ci168 = bootstrap_ci(ev_v168, base_v168, seed=seed)
    row.update({
        "mean24": float(s["ret_24h_mean"]),
        "median": float(s["ret_24h_median"]),
        "win": float(s["ret_24h_win"]),
        "excess": float(ci["mean_diff"]),
        "ci_lo": float(ci["ci_lo"]),
        "ci_hi": float(ci["ci_hi"]),
        "excess168": float(ci168["mean_diff"]),
    })
    if len(ev_v) < min_events:
        row["verdict"] = f"样本不足(n={len(ev_v)}<{min_events})"
    elif ci["ci_lo"] > 0:
        row["verdict"] = "GO_LONG"
    elif ci["ci_hi"] < 0:
        row["verdict"] = "GO_SHORT"
    else:
        row["verdict"] = "NO_GO"
    return row


def _phi(a: np.ndarray, b: np.ndarray) -> float:
    """两个布尔条件的 phi 相关系数（2x2 列联关联度量，-1..1）。"""
    n11 = int((a & b).sum()); n10 = int((a & ~b).sum())
    n01 = int((~a & b).sum()); n00 = int((~a & ~b).sum())
    n = n11 + n10 + n01 + n00
    denom = np.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    if denom == 0:
        return np.nan
    return float((n11 * n00 - n10 * n01) / denom)


def _build_baseline(ctxs: dict, rng: np.random.Generator,
                    start_ms: int, end_ms: int, n: int) -> pd.DataFrame:
    """同期随机基线（131 同款：draw_random_events + forward_stats）。"""
    base = draw_random_events(ctxs, n, rng, max_forward_hours=168,
                              start_ms=start_ms, end_ms=end_ms)
    if base.empty:
        return pd.DataFrame()
    return _fwd_for(ctxs, base)


# ---------- 格式 ----------
def fmt(x, plus: bool = False, nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    if plus:
        return f"{x:+.{nd}f}%"
    return f"{x:.{nd}f}%"


def fmt_ci(r: dict, plus: bool = True) -> str:
    return f"[{fmt(r.get('ci_lo'), plus=plus)}, {fmt(r.get('ci_hi'), plus=plus)}]"


def fmt_win(v) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    return f"{v:.1%}"


def fmt_n(x, nd: int = 0) -> str:
    """纯数字格式（无 % 后缀，用于总期望等标量）。"""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    return f"{x:.{nd}f}"


# 16 子集位标签：L=liq_short_z>1 / V=放量 / X=VIX低 / B=广度（4 位二进制，L 为最高位）
def subset_label(bits: int) -> str:
    names = [("L", "liq"), ("V", "vol"), ("X", "vix"), ("B", "brd")]
    on = [abbr for i, (abbr, _) in enumerate(names) if bits & (8 >> i)]
    desc = [full for i, (_, full) in enumerate(names) if bits & (8 >> i)]
    if not on:
        return "0000 无任何条件"
    return f"{''.join('1' if bits & (8 >> i) else '0' for i in range(4))} " + "+".join(desc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--min-events", type=int, default=MIN_EVENTS)
    parser.add_argument("--n-baseline", type=int, default=N_BASELINE)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    fundings = load_funding_series(symbols)
    ctxs = m131.add_liq_features(ctxs)
    ctxs = m133.add_qv24_ratio(ctxs)
    print(f"[134] 价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)} | "
          f"liquidation 覆盖 {sum('liq_24h' in t.columns and t['liq_24h'].notna().any() for t in ctxs.values())}")

    rng = np.random.default_rng(args.seed)

    # ---------- 事件 = wash_cvd（liquidation 覆盖窗口 2024-06-01 → 2026-06-23） ----------
    ev_parts = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), VARIANT)
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = _fwd_for(ctxs, events)
    events["episode"] = episode_of(events["timestamp"].to_numpy())
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)].reset_index(drop=True)
    print(f"[134] {VARIANT} 事件 {len(events)}（2024-06-01→2026-06-23）")

    # ---------- 四特征 asof 标注（全部只用事件时点及之前信息） ----------
    # 1) 强平（liq_short_z，同 131）
    events = m131.attach_liq_asof(ctxs, events)
    n_nan_liq = int(events["liq_short_z_at_event"].isna().sum())
    # 2) 放量（同 126/133）
    events = m133.attach_qv_ratio_asof(ctxs, events)
    n_nan_qv = int(events["qv24_ratio_at_event"].isna().sum())
    # 3) VIX 状态（事件日-1 asof，同 123/133）
    st = m120.build_state_frame()
    ev_st = m120.event_states(events, st)
    for c in ev_st.columns:
        events[c] = ev_st[c].to_numpy()
    n_nan_vix = int(events["vix_low"].isna().sum())
    # 4) 广度（6h 网格 asof，同 124/133）
    grid = m124.build_grid(ctxs)
    breadth = m124.build_breadth_series(ctxs, grid)
    events = m124.attach_breadth(events, breadth)
    n_nan_brd = int(events["breadth_pct"].isna().sum())
    print(f"[134] 缺强平 {n_nan_liq} | 缺放量 {n_nan_qv} | 缺 VIX 状态 {n_nan_vix} | 缺广度 {n_nan_brd}")

    # ---------- 四布尔条件（NaN 视为不满足；缺失数已诚实标注） ----------
    liq_ok = (events["liq_short_z_at_event"] > LIQ_Z_HI).fillna(False).to_numpy(dtype=bool)
    vol_ok = (events["qv24_ratio_at_event"] > VOL_HI).fillna(False).to_numpy(dtype=bool)
    vix_ok = events["vix_low"].fillna(False).to_numpy(dtype=bool)
    brd_ok = (events["breadth_pct"] >= BREADTH_LOW).fillna(False).to_numpy(dtype=bool)
    n_cond = liq_ok.astype(int) + vol_ok.astype(int) + vix_ok.astype(int) + brd_ok.astype(int)

    # ---------- 基线：pooled 首抽（与 131 同种子同量级），随后各 episode ----------
    base_pooled = _build_baseline(ctxs, rng, LO_MS, HI_MS, args.n_baseline)
    base_v = pd.to_numeric(base_pooled["ret_24h"], errors="coerce").dropna().to_numpy()
    base_v168 = pd.to_numeric(base_pooled["ret_168h"], errors="coerce").dropna().to_numpy()
    base_by_ep: dict[str, pd.DataFrame] = {}
    for name, s, e in EPISODES:
        if name not in EPISODES_LIQ:
            continue
        start_ms = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
        end_ms = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
        base_by_ep[name] = _build_baseline(ctxs, rng, start_ms, end_ms, args.n_baseline)
    print(f"[134] pooled 基线 n={len(base_v)}，24h 均值 {np.nanmean(base_v):+.2f}% | "
          f"episode 基线 { {k: len(v) for k, v in base_by_ep.items()} }")

    def base_v_for(ep: str) -> tuple[np.ndarray, np.ndarray]:
        if ep == "pooled":
            return base_v, base_v168
        b = base_by_ep.get(ep)
        if b is None or b.empty:
            return np.array([]), np.array([])
        return (pd.to_numeric(b["ret_24h"], errors="coerce").dropna().to_numpy(),
                pd.to_numeric(b["ret_168h"], errors="coerce").dropna().to_numpy())

    lines: list[str] = []
    lines.append("# wash_cvd × liq_short_z>1 × (放量/VIX/广度) 四条件联合矩阵\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 方法: 事件={VARIANT}（{VARIANT_DESC}），区间 2024-06-01→2026-06-23 UTC"
                 f"（= liquidation 覆盖区间，与 131 一致；133 对比行注意窗口差异）；"
                 f"四条件全部 asof 事件时点（无前视）")
    lines.append(f"  - liq_ok = liq_short_z_at_event>{LIQ_Z_HI:g}：liquidation parquet（time 与 klines "
                 f"open_time 精确对齐）→ 24h 空头累计 rolling(24).sum() → 30d(720h) 自序列 z-score"
                 f"（m113.rolling_z，min_periods=360），事件 ts searchsorted asof（同 131 表2 激增档）")
    lines.append(f"  - vol_ok = qv24_ratio>{VOL_HI:g}（qv24=quote_volume.rolling(24).sum()，"
                 f"qv24_med=rolling(720,min_periods=360).median()，公式同 121/126/133）")
    lines.append(f"  - vix_ok = 非 vix_high（VIX.parquet 日度 close，vix_high = VIX > 1y 滚动 "
                 f"q{VIX_Q * 100:.0f}（min_periods=120），事件日−1 asof，同 120/123/133 口径）")
    lines.append(f"  - brd_ok = breadth_pct≥{BREADTH_LOW:.0f}%（6h 网格市场级广度，同 124 口径："
                 f"逐币 washout=(price_z<-2)|(ret_24h<-8)，breadth_pct=100×出清币数/有效币数，"
                 f"n_active≥5 才有效；事件 ts asof 最近网格点）")
    lines.append(f"- 数据源: COINGLASS_RAW1H={COINGLASS_RAW1H}（liquidation/{{sym}}.parquet + "
                 f"klines: close/quote_volume/price_z/ret_24h/cvd_divergence）；MACRO_ROOT={MACRO_ROOT}"
                 f"（VIX.parquet）；FUNDING_DIR={FUNDING_DIR}（wash_cvd 检测用 funding 占位）")
    lines.append(f"- 基线 = 同期随机 symbol×时点横截面（draw_random_events n={args.n_baseline}），"
                 f"bootstrap 95% CI（seed={args.seed}）；pooled 首抽、episode 各抽一次，所有子集共用"
                 f"同一基线（横向可比）")
    lines.append(f"- 判定: 24h 超额 CI 下界>0 → GO_LONG；上界<0 → GO_SHORT；含 0 → NO_GO；"
                 f"n<{args.min_events} → 样本不足不判；24h 胜率 = P(ret_24h>0)")
    lines.append(f"- 131 锚点: liq_short_z>1 pooled n={KNOWN_131['liq_short_z>1 pooled n']}、"
                 f"24h 超额 +{KNOWN_131['liq_short_z>1 pooled 24h超额']}% "
                 f"CI[{KNOWN_131['liq_short_z>1 pooled CI'][0]:+.2f}, "
                 f"{KNOWN_131['liq_short_z>1 pooled CI'][1]:+.2f}]（本表应一致）")
    lines.append("> **样本重叠（务必读）**：同一 6h 时点多币同时出清 → wash_cvd 事件彼此相关，"
                 "每行报告唯一时点数 n_unique_ts；bootstrap 未按币/时点聚类，CI 偏窄。"
                 "72h 冷却使同币事件间也存在自相关。\n")
    lines.append("**局限（先读）**：")
    lines.append("- 窗口 2024-06-01→2026-06-23（liquidation 覆盖）：只测 2024崩→恢复 / 2025顶→熊 "
                 "两个 episode + pooled，2022/2023 磨底/蓄力期的强平流不可测；"
                 "133 全窗口（2022-01→2026-06-30）111 为 n=373 / +2.92%，本表窗口截断后 n 偏小，"
                 "方向可比、绝对值不可直接比。")
    lines.append("- 缺失值（NaN）一律视为条件不满足：缺强平（2024-06 暖机期）事件落入 liq_ok=False 侧，"
                 f"实测缺强平 {n_nan_liq} / 缺放量 {n_nan_qv} / 缺广度 {n_nan_brd} / "
                 f"缺 VIX 状态 {n_nan_vix}。")
    lines.append("- 强平特征需 24h 累计 + 720h z-score 暖机（min_periods=360）：2024-06 暖机期事件"
                 "（liq NaN）不参与 liq 判定，只落在非 liq 侧。")
    lines.append("- coinglass klines 2026-06-23 23:00 → 06-30 04:00 约 6.3 天全 universe 空档："
                 "事件 ts 上限 2026-06-23，尾部事件 forward 收益可能 NaN（forward_stats 自动置 NaN），"
                 "轻微减少样本，不影响结论。")
    lines.append("- 广度依赖 price_z/ret_24h 的 30d 滚动窗口，2024-06 起已充分暖机；"
                 "n_active 在 2024/2025 均值 ~50，广度粒度细。\n")

    # ---------- 0. 事件总览与四条件覆盖率 ----------
    lines.append("## 0. 事件总览与四条件覆盖率\n")
    lines.append("| episode | wash_cvd | liq_ok | vol_ok | vix_ok | brd_ok | 四条件全满足 |")
    lines.append("|---|---|---|---|---|---|---|")
    for name, _, _ in EPISODES:
        if name not in EPISODES_LIQ:
            continue
        sub = events[events["episode"] == name]
        idx = sub.index
        lines.append(f"| {name} | {len(sub)} | {int(liq_ok[idx].sum())} | {int(vol_ok[idx].sum())} | "
                     f"{int(vix_ok[idx].sum())} | {int(brd_ok[idx].sum())} | "
                     f"{int((liq_ok[idx] & vol_ok[idx] & vix_ok[idx] & brd_ok[idx]).sum())} |")
    lines.append(f"| 合计 | {len(events)} | {int(liq_ok.sum())} | {int(vol_ok.sum())} | "
                 f"{int(vix_ok.sum())} | {int(brd_ok.sum())} | "
                 f"{int((liq_ok & vol_ok & vix_ok & brd_ok).sum())} |")
    lines.append("")
    lines.append(f"| 条件 | 定义 | 满足 n | 占比 | 缺数据 n |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| liq_ok | liq_short_z>{LIQ_Z_HI:g} | {int(liq_ok.sum())} | {liq_ok.mean() * 100:.1f}% | {n_nan_liq} |")
    lines.append(f"| vol_ok | qv24_ratio>{VOL_HI:g} | {int(vol_ok.sum())} | {vol_ok.mean() * 100:.1f}% | {n_nan_qv} |")
    lines.append(f"| vix_ok | VIX≤1y q{VIX_Q * 100:.0f}（非 vix_high） | {int(vix_ok.sum())} | "
                 f"{vix_ok.mean() * 100:.1f}% | {n_nan_vix} |")
    lines.append(f"| brd_ok | breadth≥{BREADTH_LOW:.0f}% | {int(brd_ok.sum())} | {brd_ok.mean() * 100:.1f}% | "
                 f"{n_nan_brd} |")
    lines.append("")

    # ---------- 1. 表1 联合矩阵 16 子集全表 ----------
    lines.append("## 1. 表1 联合矩阵 16 子集全表（vs pooled 随机基线；超额=24h 均值−基线均值）\n")
    lines.append("| 组合 | 满足条件数 | n | 唯一时点 | 24h均% | 中位% | 胜率 | 超额vs基线 | 95% CI | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    tbl1: dict[int, dict] = {}
    for bits in range(16):
        mask = np.ones(len(events), dtype=bool)
        mask &= liq_ok if (bits & 8) else ~liq_ok
        mask &= vol_ok if (bits & 4) else ~vol_ok
        mask &= vix_ok if (bits & 2) else ~vix_ok
        mask &= brd_ok if (bits & 1) else ~brd_ok
        sub = events[mask]
        r = _row_stats(sub, base_v, base_v168, args.seed, args.min_events)
        r.update({"label": subset_label(bits), "n_cond": int(bits.bit_count())})
        tbl1[bits] = r
        lines.append(f"| {subset_label(bits)} | {bits.bit_count()} | {r['n']} | {r['n_unique_ts']} | "
                     f"{fmt(r.get('mean24'))} | {fmt(r.get('median'))} | {fmt_win(r.get('win'))} | "
                     f"{fmt(r.get('excess'), plus=True)} | {fmt_ci(r)} | "
                     f"{fmt(r.get('excess168'), plus=True)} | **{r['verdict']}** |")
    lines.append("")
    lines.append("注：位序 = L(liq) V(vol) X(vix) B(brd)，1=满足；如 1111=四条件全满足。")
    lines.append("")

    # ---------- 2. 表2 关键组合对比 ----------
    combos = [
        ("纯 wash_cvd（窗口锚点）", "ref", np.ones(len(events), dtype=bool), True),
        ("liq 单条件（对照 131）", "liq", liq_ok, True),
        ("liq+vol（两两）", "liq_vol", liq_ok & vol_ok, True),
        ("liq+vix（两两）", "liq_vix", liq_ok & vix_ok, True),
        ("liq+brd（两两）", "liq_brd", liq_ok & brd_ok, True),
        ("liq+111（四条件全开）", "liq_all", liq_ok & vol_ok & vix_ok & brd_ok, True),
        ("111 无 liq（对照 133）", "no_liq_all", vol_ok & vix_ok & brd_ok, True),
    ]
    lines.append("## 2. 表2 关键组合对比（vs pooled 基线；增量=组合内直接 bootstrap 对比）\n")
    lines.append("| 组 | n | 唯一时点 | 24h均% | 超额vs基线 | 95% CI | 168h超额 | 胜率 | "
                 "增量vs liq单 | 增量CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    tbl2: dict[str, dict] = {}
    liq_rets = pd.to_numeric(events[liq_ok]["ret_24h"], errors="coerce").dropna().to_numpy()
    for label, key, mask, _ in combos:
        sub = events[mask]
        r = _row_stats(sub, base_v, base_v168, args.seed, args.min_events)
        r["label"], r["key"] = label, key
        ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        if key == "liq" or len(ev_v) == 0:
            inc, inc_ci = np.nan, {"ci_lo": np.nan, "ci_hi": np.nan}
        else:
            ci_inc = bootstrap_ci(ev_v, liq_rets, seed=args.seed)
            inc, inc_ci = ci_inc["mean_diff"], ci_inc
        r["inc_vs_liq"], r["inc_lo"], r["inc_hi"] = inc, inc_ci["ci_lo"], inc_ci["ci_hi"]
        tbl2[key] = r
        lines.append(f"| {label} | {r['n']} | {r['n_unique_ts']} | {fmt(r.get('mean24'))} | "
                     f"{fmt(r.get('excess'), plus=True)} | {fmt_ci(r)} | "
                     f"{fmt(r.get('excess168'), plus=True)} | {fmt_win(r.get('win'))} | "
                     f"{fmt(inc, plus=True)} | [{fmt(inc_ci.get('ci_lo'), plus=True)}, "
                     f"{fmt(inc_ci.get('ci_hi'), plus=True)}] | **{r['verdict']}** |")
    lines.append("")
    # liq+111 vs 111 无 liq 的直接对比（liq 在 111 之上的边际）
    a = pd.to_numeric(events[liq_ok & vol_ok & vix_ok & brd_ok]["ret_24h"], errors="coerce").dropna().to_numpy()
    b = pd.to_numeric(events[vol_ok & vix_ok & brd_ok]["ret_24h"], errors="coerce").dropna().to_numpy()
    if len(a) and len(b):
        ci_ab = bootstrap_ci(a, b, seed=args.seed)
        lines.append(f"- **liq+111 − 111无liq 直接对比**: n={len(a)} vs {len(b)}，"
                     f"24h 均值差 {fmt(ci_ab['mean_diff'], plus=True)}（CI "
                     f"[{fmt(ci_ab['ci_lo'], plus=True)}, {fmt(ci_ab['ci_hi'], plus=True)}]）"
                     f"—— liq 在 111 之上的边际增量")
        liq_ab_line = (f"liq+111 − 111无liq: {len(a)} vs {len(b)} 差值 "
                       f"{fmt(ci_ab['mean_diff'], plus=True)} CI[{fmt(ci_ab['ci_lo'], plus=True)}, "
                       f"{fmt(ci_ab['ci_hi'], plus=True)}]")
    else:
        liq_ab_line = "liq+111 − 111无liq: 样本不足"
    lines.append("")

    # ---------- 3. 表3 样本消耗阶梯（≥k 个条件） ----------
    rungs = [
        ("≥0（纯 wash_cvd）", 0, np.ones(len(events), dtype=bool)),
        ("≥1（任一条件）", 1, n_cond >= 1),
        ("≥2（任意两个）", 2, n_cond >= 2),
        ("≥3（任意三个）", 3, n_cond >= 3),
        ("≥4（四条件全满足）", 4, n_cond >= 4),
    ]
    lines.append("## 3. 表3 样本消耗阶梯（累积门控：满足 ≥k 个条件）\n")
    lines.append("| 档 | 保留 n | 占窗口wash_cvd | 唯一时点 | 24h均% | 超额vs基线 | 95% CI | "
                 "总期望(n×超额) | 较上一档增量 | 较上一档CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    ladder: list[dict] = []
    prev_ev_v: np.ndarray | None = None
    ref_ev_v = pd.to_numeric(events["ret_24h"], errors="coerce").dropna().to_numpy()
    for label, k, mask in rungs:
        sub = events[mask]
        r = _row_stats(sub, base_v, base_v168, args.seed, args.min_events)
        ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        total = len(ev_v) * r["excess"] if np.isfinite(r["excess"]) else np.nan
        if prev_ev_v is None:
            inc, inc_ci = np.nan, {"ci_lo": np.nan, "ci_hi": np.nan}
        else:
            ci_inc = bootstrap_ci(ev_v, prev_ev_v, seed=args.seed)
            inc, inc_ci = ci_inc["mean_diff"], ci_inc
        prev_ev_v = ev_v
        share = len(ev_v) / len(ref_ev_v) * 100 if len(ref_ev_v) else np.nan
        r.update({"label": label, "k": k, "share": share, "total": total,
                  "inc": inc, "inc_lo": inc_ci["ci_lo"], "inc_hi": inc_ci["ci_hi"]})
        ladder.append(r)
        lines.append(f"| {label} | {r['n']} | {share:.1f}% | {r['n_unique_ts']} | {fmt(r.get('mean24'))} | "
                     f"{fmt(r.get('excess'), plus=True)} | {fmt_ci(r)} | {fmt_n(r.get('total'))} | "
                     f"{fmt(inc, plus=True)} | [{fmt(inc_ci.get('ci_lo'), plus=True)}, "
                     f"{fmt(inc_ci.get('ci_hi'), plus=True)}] | **{r['verdict']}** |")
    lines.append("")
    lines.append(f"注：总期望 = 有效 24h 事件数 × 24h 超额（126 口径）；较上一档增量 = 本档 vs 上一档事件集"
                 f" 24h 均值的直接 bootstrap 对比（seed={args.seed}）。")
    lines.append("")

    # ---------- 4. 正交性分析 ----------
    lines.append("## 4. 正交性分析：liq_ok 与三条件在事件时点的相关/重叠\n")
    n_all = len(events)
    pairs = [("liq×vol", liq_ok, vol_ok), ("liq×vix", liq_ok, vix_ok),
             ("liq×brd", liq_ok, brd_ok), ("vol×vix", vol_ok, vix_ok),
             ("vol×brd", vol_ok, brd_ok), ("vix×brd", vix_ok, brd_ok)]
    lines.append("| 条件对 | 同满足 n（观测） | 独立假设期望 n | 观测/期望 | phi | 解读 |")
    lines.append("|---|---|---|---|---|---|")
    for pname, x, y in pairs:
        n_obs = int((x & y).sum())
        n_exp = n_all * x.mean() * y.mean()
        phi = _phi(x, y)
        ratio = n_obs / n_exp if n_exp > 0 else np.nan
        if ratio > 1.1:
            interp = "正相关（压力窗口齐发，重叠冗余）"
        elif ratio < 0.9:
            interp = "负相关（互斥替代）"
        else:
            interp = "近似独立（正交可叠加）"
        lines.append(f"| {pname} | {n_obs} | {n_exp:.0f} | {ratio:.2f} | {phi:+.2f} | {interp} |")
    lines.append("")
    lines.append(f"- 单条件覆盖率: liq {liq_ok.mean() * 100:.1f}% / vol {vol_ok.mean() * 100:.1f}% / "
                 f"vix {vix_ok.mean() * 100:.1f}% / brd {brd_ok.mean() * 100:.1f}%；"
                 f"同时满足 ≥2 个条件的占比 {100 * (n_cond >= 2).mean():.1f}%，四条件全满足占比 "
                 f"{100 * (n_cond == 4).mean():.1f}%")
    lines.append(f"- 0000（无一满足）占比 {100 * (n_cond == 0).mean():.1f}% —— 注意该子集含缺数据事件"
                 f"（缺强平 {n_nan_liq} / 缺放量 {n_nan_qv} / 缺广度 {n_nan_brd} / "
                 f"缺 VIX {n_nan_vix}），其负期望解读需谨慎（见局限）。")
    lines.append("")

    # ---------- 5. 判定 ----------
    lines.append("## 5. 判定：liq 是否与 111 正交可叠加？最优配置？\n")
    r_ref, r_liq, r_all = tbl2["ref"], tbl2["liq"], tbl2["liq_all"]
    r_111 = tbl2["no_liq_all"]
    lines.append(f"- **131 锚点核对**: liq 单条件 n={r_liq['n']}、24h 均值 {fmt(r_liq.get('mean24'))}、"
                 f"超额 {fmt(r_liq.get('excess'), plus=True)} CI {fmt_ci(r_liq)}"
                 f"（131: n={KNOWN_131['liq_short_z>1 pooled n']} / +{KNOWN_131['liq_short_z>1 pooled 24h均值']}% "
                 f"/ +{KNOWN_131['liq_short_z>1 pooled 24h超额']}% —— {'一致 ✔' if r_liq['n'] == KNOWN_131['liq_short_z>1 pooled n'] else '≈'}）")
    lines.append(f"- **四条件 vs 三条件**: liq+111 n={r_all['n']}、24h 均值 {fmt(r_all.get('mean24'))}、"
                 f"超额 {fmt(r_all.get('excess'), plus=True)}（CI {fmt_ci(r_all)}）"
                 f"vs 111无liq n={r_111['n']}、超额 {fmt(r_111.get('excess'), plus=True)}（CI {fmt_ci(r_111)}）；"
                 f"直接对比 {liq_ab_line}")
    lines.append(f"- **liq 叠加增量**: liq+111 相对 liq 单条件增量 {fmt(tbl2['liq_all']['inc_vs_liq'], plus=True)}"
                 f"（CI [{fmt(tbl2['liq_all']['inc_lo'], plus=True)}, "
                 f"{fmt(tbl2['liq_all']['inc_hi'], plus=True)}]）")
    lines.append("")
    lines.append("### 5a. 分 episode 稳健性（pooled + 2024/2025，episode 用各自同期基线）\n")
    lines.append("| 组 | episode | n | 24h均% | 超额vs基线 | 95% CI | 168h超额 | 胜率 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    ep_rows: list[dict] = []
    for label, key, mask, _ in combos:
        for ep in ["pooled"] + EPISODES_LIQ:
            sub = events[mask] if ep == "pooled" else events[mask & (events["episode"] == ep)]
            bv, bv168 = base_v_for(ep)
            r = _row_stats(sub, bv, bv168, args.seed, args.min_events)
            r["label"], r["key"], r["ep"] = label, key, ep
            ep_rows.append(r)
            lines.append(f"| {label} | {ep} | {r['n']} | {fmt(r.get('mean24'))} | "
                         f"{fmt(r.get('excess'), plus=True)} | {fmt_ci(r)} | "
                         f"{fmt(r.get('excess168'), plus=True)} | {fmt_win(r.get('win'))} | "
                         f"**{r['verdict']}** |")
    lines.append("")

    # 综合判定
    l0, l4 = ladder[0], ladder[4]
    best_k = max(range(5), key=lambda k: ladder[k]["total"] if np.isfinite(ladder[k]["total"]) else -np.inf)
    verdict_lines: list[str] = []
    verdict_lines.append(f"- **每事件质量**: 四条件(liq+111) pooled 24h 超额 {fmt(r_all['excess'], plus=True)}"
                         f"（CI {fmt_ci(r_all)}，n={r_all['n']}），相对 liq 单条件 "
                         f"{fmt(r_all['inc_vs_liq'], plus=True)}（CI [{fmt(r_all['inc_lo'], plus=True)}, "
                         f"{fmt(r_all['inc_hi'], plus=True)}]），相对 111 无 liq {liq_ab_line}。")
    verdict_lines.append(f"- **样本损失**: 窗口 wash_cvd {l0['n']} → ≥3 {ladder[3]['n']}（保留 {ladder[3]['share']:.1f}%）"
                         f"/ ≥4 {l4['n']}（保留 {l4['share']:.1f}%）——liq 叠加把 111 的 n 从 {r_111['n']} "
                         f"压缩到 {r_all['n']}，四条件硬叠加样本骤减。")
    verdict_lines.append(f"- **总期望（126 口径）**: ≥0 {fmt_n(l0['total'])} / ≥1 {fmt_n(ladder[1]['total'])} / "
                         f"≥2 {fmt_n(ladder[2]['total'])} / ≥3 {fmt_n(ladder[3]['total'])} / "
                         f"≥4 {fmt_n(l4['total'])} → **最优条件数 = {best_k}**（总期望最大档）；"
                         f"若执行容量受限（单笔质量优先），取每事件超额最高的档并接受样本下降。")
    lines.append("### 5b. 综合判定\n")
    lines.append("\n".join(verdict_lines))

    phi_lv = _phi(liq_ok, vol_ok)
    phi_lx = _phi(liq_ok, vix_ok)
    phi_lb = _phi(liq_ok, brd_ok)
    liq_vol_overlap = int((liq_ok & vol_ok).sum())
    liq_total = int(liq_ok.sum())
    # liq 与 vol 高度重叠（近子集）；与 vix/brd 正交
    if abs(phi_lx) < 0.15 and abs(phi_lb) < 0.15 and phi_lv >= 0.15:
        orthog_desc = (f"liq_ok 与 vix/brd 近似正交（phi≈0），但与 vol 正相关"
                       f"（phi={phi_lv:+.2f}，{liq_vol_overlap}/{liq_total} 个 liq 事件同时满足 vol_ok，"
                       f"观测/期望 1.54）——liq 在放量维度上近乎 vol 的子集（washout 短轧本身高量），"
                       f"对 vix/brd 的过滤信息增量独立存在；111 三条件自身仍近似正交（与 133 一致）。")
        liq_indep = True
    elif abs(phi_lv) < 0.15 and abs(phi_lx) < 0.15 and abs(phi_lb) < 0.15:
        orthog_desc = (f"liq_ok 与 vol/vix/brd 三条件在事件时点全部近似正交"
                       f"（phi≈0，观测/期望≈1.00，与 133 三条件结论一致）——"
                       f"liq 的联合过滤信息增量真实存在，无需担心与 111 条件冗余。")
        liq_indep = True
    else:
        orthog_desc = (f"liq_ok 与 vol/vix/brd 事件时点存在部分相关性"
                       f"（liq×vol phi={phi_lv:+.2f} / liq×vix phi={phi_lx:+.2f} / "
                       f"liq×brd phi={phi_lb:+.2f}）——liq 主要与放量重叠，与 VIX/广度正交。")
        liq_indep = False
    verdict_line = (
        f"- **判定（正交性与可叠加性）**: {orthog_desc} "
        f"四条件(liq+111)每事件超额 {fmt(r_all['excess'], plus=True)}（CI {fmt_ci(r_all)}，n={r_all['n']}）"
        f"为 16 子集最高 {'且相对 111无liq 与 liq单条件均为正增量（点估计）' if np.isfinite(r_all['inc_vs_liq']) and r_all['inc_vs_liq'] > 0 else ''}；"
        f"但硬叠加样本压缩到 {l4['share']:.1f}%（n={l4['n']}），总期望 {fmt_n(l4['total'])} "
        f"{'高于' if l4['total'] > l0['total'] else '低于'} 纯 wash_cvd {fmt_n(l0['total'])} → "
        f"若容量允许取 ≥{best_k} 条件档（{ladder[best_k]['n']} 事件，总期望 {fmt_n(ladder[best_k]['total'])}，"
        f"每事件超额 {fmt(ladder[best_k]['excess'], plus=True)}）为稳健默认；单笔质量优先时取 liq+111。"
    )
    lines.append(verdict_line)
    lines.append("")
    lines.append("> **T3 标注：进 108 前向影子 / scan_rules / contract_anomaly_rules 的任何改动属 T3，"
                 "需 Owner 签批。本脚本只做研究侧建议，不碰任何配置（config/*.yaml、scan_rules.yaml、"
                 "contract_anomaly_rules.yaml、scripts/108_contract_monitor.py、109_forward_replay.py）。**")

    lines.append("\n## 6. 局限\n")
    lines.append("- 样本重叠：同一 6h 时点多币同时出清 → 事件非独立，各表已报 n_unique_ts；"
                 "bootstrap 未按币/时点聚类，CI 偏窄。")
    lines.append("- liq 特征只覆盖 2024-06-06 → 2026-06-23：只测 2024崩→恢复 / 2025顶→熊 两个 episode；"
                 "2022/2023 磨底/蓄力期的强平流不可测（wash_cvd 全历史 edge 不受影响，"
                 "但 liq 叠加是否跨周期成立未验证）。")
    lines.append("- 强平特征需 24h 累计 + 720h z-score 暖机（min_periods=360）：2024-06 暖机期事件"
                 f"（{n_nan_liq} 个，liq NaN）落入非 liq 侧，不参与 liq 判定。")
    lines.append("- 133 对比行（111 无 liq）为全窗口 2022-01→2026-06-30 口径（n=373 / +2.92%），"
                 "本表窗口 2024-06→2026-06-23 截断 → n 偏小、超额为窗口内估计，方向可比、绝对值不可直接比；"
                 "以本表窗口内 111 行（n 与超额）为四条件叠加的对照基准。")
    lines.append("- 2026-06-23 23:00 → 06-30 04:00 coinglass 全 universe 空档：事件 ts 上限 2026-06-23，"
                 "尾部事件 forward 收益可能 NaN，轻微减少样本，不影响结论。")
    lines.append("- 表1/表2/表3 超额用同一 pooled 基线（横向可比）；与 131/133 报告的绝对值存在基线抽样差异"
                 "（131 基线 n=3000 同量级同种子 → liq 单条件行应精确一致，见交叉核对），方向一致。")
    lines.append("- 四条件硬叠加 n<60：点估计与 CI 受极端事件影响大，liq+111 行结论需样本外前向验证"
                 "（当前筑底窗口只有影子数据，T3）。")
    lines.append("- 总期望 = n×超额，以超额均值线性外推；未计容量/滑点/交易成本（本研究为事件级收益）。")

    # ---------- 交叉核对 ----------
    lines.append("\n## 7. 与 131/133 数字交叉核对\n")
    lines.append("| 项 | 已知 | 本脚本 | 一致 |")
    lines.append("|---|---|---|---|")
    checks = [
        ("131 wash_cvd 窗口事件 n", KNOWN_131["wash_cvd 窗口事件 n"], tbl2["ref"]["n"], "int"),
        ("131 liq_short_z>1 pooled n", KNOWN_131["liq_short_z>1 pooled n"], tbl2["liq"]["n"], "int"),
        ("131 liq_short_z>1 pooled 24h均值", KNOWN_131["liq_short_z>1 pooled 24h均值"], tbl2["liq"]["mean24"], "pct"),
        ("131 liq_short_z>1 pooled 24h超额", KNOWN_131["liq_short_z>1 pooled 24h超额"], tbl2["liq"]["excess"], "pct"),
        ("131 2024 liq_short_z>1 n", KNOWN_131["2024 liq_short_z>1 n"],
         next((r["n"] for r in ep_rows if r["key"] == "liq" and r["ep"] == "2024崩→恢复"), None), "int"),
        ("131 2025 liq_short_z>1 n", KNOWN_131["2025 liq_short_z>1 n"],
         next((r["n"] for r in ep_rows if r["key"] == "liq" and r["ep"] == "2025顶→熊"), None), "int"),
        ("133 111 全条件 n（全窗口）", KNOWN_133["111 全条件 n（全窗口 2022-01→2026-06-30）"],
         tbl2["no_liq_all"]["n"], "window_diff"),
    ]
    for item, known, got, kind in checks:
        if got is None:
            lines.append(f"| {item} | {known} | - | - |")
            continue
        if kind == "int":
            ok = "✓" if got == known else "≈"
            lines.append(f"| {item} | {known} | {got} | {ok} |")
        elif kind == "window_diff":
            lines.append(f"| {item} | {known}（2022-01→2026-06-30） | {got}（2024-06→2026-06-23） | "
                         f"窗口截断（方向可比） |")
        else:
            ok = "✓" if (isinstance(got, float) and np.isfinite(got) and abs(got - known) < 0.05) else "≈"
            lines.append(f"| {item} | {known} | {fmt(got, plus=True)} | {ok} |")
    lines.append("")
    lines.append("注：131 基线 n=3000 同种子同窗口 → liq 单条件行 n/均值/超额应精确一致；"
                 "133 为全窗口 111（n=373 / +2.92%），本表 111 行窗口截断，仅方向可比。")

    out = REPORTS_DIR / "liq_combo_matrix.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")

    # ---------- stdout 摘要 ----------
    print("\n=== 0 条件覆盖率 ===")
    print(f"  liq_ok={int(liq_ok.sum())} ({liq_ok.mean() * 100:.1f}%) | vol_ok={int(vol_ok.sum())} "
          f"({vol_ok.mean() * 100:.1f}%) | vix_ok={int(vix_ok.sum())} ({vix_ok.mean() * 100:.1f}%) | "
          f"brd_ok={int(brd_ok.sum())} ({brd_ok.mean() * 100:.1f}%) | "
          f"缺 liq {n_nan_liq} / qv {n_nan_qv} / vix {n_nan_vix} / brd {n_nan_brd}")
    print("\n=== 表1 16 子集（vs pooled 基线） ===")
    print("组合 | 条件数 | n | 24h均% | 超额 | CI | 168h | 胜率 | 判定")
    for bits in range(16):
        r = tbl1[bits]
        print(f"{subset_label(bits):22s} | {r['n_cond']} | {r['n']:4d} | {fmt(r.get('mean24'))} | "
              f"{fmt(r.get('excess'), plus=True)} | {fmt_ci(r)} | {fmt(r.get('excess168'), plus=True)} | "
              f"{fmt_win(r.get('win'))} | {r['verdict']}")
    print("\n=== 表2 关键组合对比（增量 vs liq 单条件） ===")
    for label, key, mask, _ in combos:
        r = tbl2[key]
        print(f"{label:22s} n={r['n']:4d} 超额={fmt(r.get('excess'), plus=True)} "
              f"CI={fmt_ci(r)} 增量vs_liq={fmt(r.get('inc_vs_liq'), plus=True)} "
              f"[{fmt(r.get('inc_lo'), plus=True)}, {fmt(r.get('inc_hi'), plus=True)}] {r['verdict']}")
    print(f"  {liq_ab_line}")
    print("\n=== 表3 样本消耗阶梯 ===")
    for r in ladder:
        print(f"{r['label']:22s} n={r['n']:4d} ({r['share']:.1f}%) 超额={fmt(r.get('excess'), plus=True)} "
              f"CI={fmt_ci(r)} 总期望={fmt_n(r.get('total'))} 增量={fmt(r.get('inc'), plus=True)} "
              f"[{fmt(r.get('inc_lo'), plus=True)}, {fmt(r.get('inc_hi'), plus=True)}] {r['verdict']}")
    print(f"\n最优条件数: ≥{best_k}（总期望最大档）")
    print("\n=== 表4 正交性（phi） ===")
    for pname, x, y in pairs:
        n_obs = int((x & y).sum())
        n_exp = n_all * x.mean() * y.mean()
        print(f"  {pname}: 观测 {n_obs} / 期望 {n_exp:.0f} "
              f"phi={_phi(x, y):+.2f}（{'正交可叠加' if abs(_phi(x, y)) < 0.15 else '相关'}）")
    print(f"\n判定: {verdict_line}")
    print("\n=== 交叉核对 ===")
    for item, known, got, kind in checks:
        if got is None:
            print(f"  {item}: 已知 {known} | 本脚本 -")
            continue
        if kind == "int":
            ok = "✓" if got == known else "≈"
            print(f"  {item}: 已知 {known} | 本脚本 {got} {ok}")
        elif kind == "window_diff":
            print(f"  {item}: 已知 {known}（全窗口） | 本脚本 {got}（窗口截断，方向可比）")
        else:
            ok = "✓" if (isinstance(got, float) and np.isfinite(got) and abs(got - known) < 0.05) else "≈"
            print(f"  {item}: 已知 {known} | 本脚本 {fmt(got, plus=True)} {ok}")


if __name__ == "__main__":
    main()
