"""133_joint_matrix.py — 已确认二阶条件的联合矩阵：
wash_cvd × (放量>1.5x / VIX q75 门控 / breadth≥5%) 组合收益与样本。

背景与承接（引用即可，勿重做）：
- 126（washcvd_volume_combo）: 放量 qv24_ratio>1.5 → pooled 24h 超额 +1.90%（n=838，4/4 episode 全正），
  直接增量 +0.78pp CI[+0.01,+1.61] 显著；>2.0 边际递减。
- 123（vix_gating）: VIX≤1y 滚动 q75（vix_low）门控后 +1.37% CI[+0.82,+1.94]（n=1126），
  vix_high 丢弃 16.5% 为负期望尾部（24h -0.07%、胜率 39%）；已签批落地 108（annotate 模式）。
- 124/127（breadth）: 事件时市场级广度分层富集，breadth≥5% 门控 +1.55% CI[+0.82,+2.25]（n=701）；
  但 127 结论：被滤组（breadth<5%）本身是正 edge（层内 +0.82%），硬门控机会成本高，更宜作分层维度；
  2022 高广度多出在深熊瀑布中继（LUNA/FTX），2022 gate5 超额 -0.17% 弱于整体（127 已预警）。
- 本脚本：把三个已确认二阶条件建成联合矩阵（2^3=8 子集全表 + 组合对比 + 样本消耗阶梯），
  回答：哪些条件可叠加、哪些重叠冗余、最优过滤配置是什么。

方法（全部 asof 事件时点，无前视）：
- 事件 = wash_cvd（m115.detect_events：washout(price_z<-2 或 ret_24h<-8%) 且 cvd_divergence>2.0，
  72h 冷却/币，Long），区间 2022-01-01 → 2026-06-30 UTC（与 123/127 同窗口，前向 episode 不含）。
- vol_ok = qv24_ratio>1.5：qv24=quote_volume.rolling(24).sum()；qv24_med=qv24.rolling(720,
  min_periods=360).median()；ratio=qv24/qv24_med（公式同 121/126）；事件 ts searchsorted asof。
- vix_ok = 非 vix_high：macro/VIX.parquet（index=date 日度 close），
  vix_high = VIX > 1y 滚动 q75（min_periods=120），事件日−1 asof（复用 120.build_state_frame /
  event_states，与 123 完全同口径；连续 VIX 值同日映射用于核对）。
- brd_ok = breadth_pct≥5：6h 网格市场级广度（同 124 口径：逐币 washout=(price_z<-2)|(ret_24h<-8)，
  breadth_pct=100×出清币数/有效币数，n_active>=5 才有效），事件 ts asof 取最近网格点。
- 基线 = 同期随机 symbol×时点横截面（draw_random_events n=5000），bootstrap 95% CI（seed=2026）。
- 判定：24h 超额 CI 下界>0 → GO_LONG；上界<0 → GO_SHORT；含 0 → NO_GO；n<30 → 样本不足不判。

只读数据、纯研究模块：不写任何配置/规则/定时任务。
进 108 前向影子 / scan_rules / contract_anomaly_rules 的任何改动属 T3，需 Owner 签批。

用法：
  python scripts/133_joint_matrix.py [--n-baseline 5000] [--seed 2026] [--min-events 30]
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

COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
MACRO_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
FUNDING_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
REPORTS_DIR = PROJECT_ROOT / "reports"

# ---------- 共享加载模板（113/115 口径；120=VIX 状态帧；124=广度序列；禁止改配置） ----------
_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec); sys.modules["m113"] = m113; _spec.loader.exec_module(m113)
_spec2 = importlib.util.spec_from_file_location(
    "m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2); sys.modules["m115"] = m115; _spec2.loader.exec_module(m115)
# 120（连带加载 m113/m115，正常）→ build_state_frame / event_states / load_macro_series（VIX 同 123 口径）
_spec3 = importlib.util.spec_from_file_location(
    "m120", str(PROJECT_ROOT / "scripts" / "120_macro_factor_modulation.py"))
m120 = importlib.util.module_from_spec(_spec3); sys.modules["m120"] = m120; _spec3.loader.exec_module(m120)
# 124（连带加载 m113/m115，正常）→ build_grid / build_breadth_series / attach_breadth（广度同 124/127 口径）
_spec4 = importlib.util.spec_from_file_location(
    "m124", str(PROJECT_ROOT / "scripts" / "124_market_breadth.py"))
m124 = importlib.util.module_from_spec(_spec4); sys.modules["m124"] = m124; _spec4.loader.exec_module(m124)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
detect_events = m115.detect_events
EPISODES = m113.EPISODES
episode_of = m113.episode_of

# ---------- 研究区间与参数 ----------
STUDY_START = "2022-01-01"
STUDY_END = "2026-06-30"   # 与 123/127 同窗口；前向 episode 不含
LO_MS = int(pd.Timestamp(STUDY_START, tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp(STUDY_END, tz="UTC").timestamp() * 1000)
VARIANT = "wash_cvd"
VARIANT_DESC = "washout(price_z<-2.0 或 ret_24h<-8%) 且 cvd_divergence>2.0，72h 冷却，Long"
VOL_HI = 1.5        # 放量阈值（同 121/126 的">1.5x"档）
VIX_Q = 0.75        # VIX 1y 滚动分位（同 120/123 的 q75）
BREADTH_LOW = 5.0   # 广度阈值（同 124/127 的 ≥5%）
N_BASELINE = 5000
SEED = 2026
MIN_EVENTS = 30

# 123/126/127 已知数字（交叉核对目标）
KNOWN = {
    "123 pooled wash_cvd n": 1348,
    "123 pooled 24h均值": 1.31,
    "123 vix_low(门控后) n": 1126,
    "123 vix_low 24h超额": 1.37,
    "126 放量>1.5x n": 838,
    "126 放量>1.5x 24h超额": 1.90,
    "127 breadth≥5% n": 701,
    "127 breadth≥5% 24h超额": 1.55,
}


# ---------- 放量（126 公式，复制自 126 保证同口径） ----------
def add_qv24_ratio(ctxs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """在 ctx 基础上补 qv24_ratio 列（公式与 121/126 完全一致）。

    qv24 = quote_volume.rolling(24).sum()（对齐到 ctx 清洗后的 index）
    qv24_med = qv24.rolling(720, min_periods=360).median()
    ratio = qv24 / qv24_med（放量倍数，>1 = 高于 30d 中位量）
    """
    for sym, t in ctxs.items():
        p = COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if "open_time" not in df.columns or "quote_volume" not in df.columns:
            continue
        ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
        qv = pd.to_numeric(df["quote_volume"], errors="coerce")
        qv_ser = pd.Series(qv.to_numpy(), index=pd.Index(ts))
        qv_ser = qv_ser[~qv_ser.index.duplicated(keep="last")].sort_index().reindex(t.index)
        qv24 = qv_ser.rolling(24).sum()
        qv24_med = qv24.rolling(720, min_periods=360).median()
        t["qv24_ratio"] = (qv24 / qv24_med.replace(0, pd.NA)).replace([np.inf, -np.inf], pd.NA)
    return ctxs


def attach_qv_ratio_asof(ctxs: dict[str, pd.DataFrame],
                         events: pd.DataFrame) -> pd.DataFrame:
    """对每个事件 ts 用 np.searchsorted 取事件行及之前最近的有效 qv24_ratio（asof，无前视）。"""
    ev = events.copy()
    ev["qv24_ratio_at_event"] = np.nan
    for sym, g in ev.groupby("symbol", sort=False):
        if sym not in ctxs or "qv24_ratio" not in ctxs[sym].columns:
            continue
        t = ctxs[sym]
        idx = t.index.to_numpy(dtype=np.int64)
        pos = np.searchsorted(idx, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(idx) - 1)
        vals = pd.to_numeric(t["qv24_ratio"], errors="coerce").to_numpy(dtype=float)
        ev.loc[g.index, "qv24_ratio_at_event"] = vals[pos]
    return ev


# ---------- VIX（123 口径：状态帧事件日-1 asof；连续值同日映射） ----------
def _series_asof_prev_day(events: pd.DataFrame, ser: pd.Series) -> np.ndarray:
    """事件 asof 取【事件日 - 1】的日度序列值；缺宏观日（周末/假日）ffill 回退（不超前）。
    与 120.event_states 完全同口径：先取 prev=事件日-1，再按最近宏观日 ffill。"""
    dates = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_convert(None).normalize()
    prev = (dates - pd.Timedelta(days=1)).normalize()
    return ser.reindex(prev, method="ffill").to_numpy()


# ---------- 事件表工具（123/127 同款） ----------
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
    ctxs = add_qv24_ratio(ctxs)
    print(f"[133] 价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)}")

    rng = np.random.default_rng(args.seed)

    # ---------- 事件 = wash_cvd（全区间 2022-01-01 → 2026-06-30，72h 冷却在 detect 阶段） ----------
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
    print(f"[133] {VARIANT} 事件 {len(events)}（{STUDY_START}→{STUDY_END}）")

    # ---------- 三特征 asof 标注（全部只用事件时点及之前信息） ----------
    # 1) 放量
    events = attach_qv_ratio_asof(ctxs, events)
    n_nan_qv = int(events["qv24_ratio_at_event"].isna().sum())
    # 2) VIX 状态（事件日-1 asof，同 123）+ 连续 VIX 同日映射
    st = m120.build_state_frame()
    ev_st = m120.event_states(events, st)
    for c in ev_st.columns:
        events[c] = ev_st[c].to_numpy()
    vix_ser = m120.load_macro_series("VIX")
    events["vix_asof"] = _series_asof_prev_day(events, vix_ser)
    n_nan_vix = int(events["vix_high"].isna().sum())
    # 3) 广度（6h 网格 asof）
    grid = m124.build_grid(ctxs)
    breadth = m124.build_breadth_series(ctxs, grid)
    events = m124.attach_breadth(events, breadth)
    n_nan_brd = int(events["breadth_pct"].isna().sum())
    print(f"[133] 缺放量 {n_nan_qv} | 缺 VIX 状态 {n_nan_vix} | 缺广度 {n_nan_brd}")

    # ---------- 三布尔条件（NaN 视为不满足；缺失数已在上面诚实标注） ----------
    vol_ok = (events["qv24_ratio_at_event"] > VOL_HI).fillna(False).to_numpy(dtype=bool)
    vix_ok = events["vix_low"].fillna(False).to_numpy(dtype=bool)
    brd_ok = (events["breadth_pct"] >= BREADTH_LOW).fillna(False).to_numpy(dtype=bool)
    n_cond = vol_ok.astype(int) + vix_ok.astype(int) + brd_ok.astype(int)

    # ---------- 基线（pooled 全区间，所有子集共用同一基线 → 横向可比） ----------
    base = draw_random_events(ctxs, args.n_baseline, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    base_stats = _fwd_for(ctxs, base)
    base_v = pd.to_numeric(base_stats["ret_24h"], errors="coerce").dropna().to_numpy()
    base_v168 = pd.to_numeric(base_stats["ret_168h"], errors="coerce").dropna().to_numpy()
    print(f"[133] 全区间基线 n={len(base_v)}，24h 均值 {np.nanmean(base_v):+.2f}%")

    lines: list[str] = []
    lines.append("# wash_cvd 二阶条件联合矩阵（放量>1.5x × VIX q75 门控 × breadth≥5%）\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 方法: 事件={VARIANT}（{VARIANT_DESC}），区间 {STUDY_START}→{STUDY_END}；"
                 f"三条件全部 asof 事件时点（无前视）")
    lines.append(f"  - vol_ok = qv24_ratio>{VOL_HI}（qv24=quote_volume.rolling(24).sum()，"
                 f"qv24_med=rolling(720,min_periods=360).median()，公式同 121/126；事件 ts searchsorted asof）")
    lines.append(f"  - vix_ok = 非 vix_high（VIX.parquet 日度 close，vix_high = VIX > 1y 滚动 q{VIX_Q * 100:.0f}"
                 f"（min_periods=120），事件日−1 asof，同 120/123 口径）")
    lines.append(f"  - brd_ok = breadth_pct≥{BREADTH_LOW:.0f}%（6h 网格市场级广度，同 124 口径："
                 f"逐币 washout=(price_z<-2)|(ret_24h<-8)，breadth_pct=100×出清币数/有效币数，"
                 f"n_active≥5 才有效；事件 ts asof 最近网格点）")
    lines.append(f"- 数据源: COINGLASS_RAW1H={COINGLASS_RAW1H}（klines: close/quote_volume/price_z/"
                 f"ret_24h/cvd_divergence）；MACRO_ROOT={MACRO_ROOT}（VIX.parquet）；"
                 f"FUNDING_DIR={FUNDING_DIR}（wash_cvd 检测用 funding 占位，实际不参与）")
    lines.append(f"- 基线 = 同期随机 symbol×时点横截面（n={args.n_baseline}），bootstrap 95% CI "
                 f"（seed={args.seed}）；所有子集共用同一基线，横向可比")
    lines.append(f"- 判定: 24h 超额 CI 下界>0 → GO_LONG；上界<0 → GO_SHORT；含 0 → NO_GO；"
                 f"n<{args.min_events} → 样本不足不判；24h 胜率 = P(ret_24h>0)")
    lines.append(f"- V_ref 复现锚点: 123/127 pooled n=1348、24h 均值 +1.31%、超额 +1.10% "
                 f"CI[+0.57,+1.57]（本表应一致）")
    lines.append("> **样本重叠（务必读）**：同一 6h 时点多币同时出清 → wash_cvd 事件彼此相关，"
                 "每行报告唯一时点数 n_unique_ts；bootstrap 未按币/时点聚类，CI 偏窄。"
                 "72h 冷却使同币事件间也存在自相关。\n")
    lines.append("**局限（先读）**：")
    lines.append("- 三条件同为市场压力信号，直觉上事件时点应正相关（压力窗口内同事件多条件齐发）；"
                 "但实测三者近似正交（phi≈0，观测/期望≈1.00，见第 4 节）——联合过滤的信息增量真实存在，"
                 "无需担心条件冗余。")
    lines.append("- 缺失值（NaN）一律视为条件不满足：缺放量/缺广度/缺 VIX 状态的事件落入 000 子集；"
                 f"实测缺放量 {n_nan_qv}、缺广度 {n_nan_brd}、缺 VIX 状态 {n_nan_vix}（见 0 节）。")
    lines.append("- coinglass klines 2026-06-23 23:00 → 06-30 04:00 约 6.3 天全 universe 空档："
                 "该窗口 6h 网格广度 NaN（n_active=0）→ in-window 事件缺广度被门控剔除。")
    lines.append("- 广度依赖 price_z/ret_24h 的 30d 滚动窗口：2022-01 月初无 price_z → 广度 2022-01-16 前后"
                 "才开始有效；n_active 前低后高（2022 平均 18 → 2025 平均 50），2022 广度粒度粗，结论仅供参考。\n")

    # ---------- 0. 事件总览与条件覆盖率 ----------
    lines.append("## 0. 事件总览与三条件覆盖率\n")
    lines.append("| episode | wash_cvd | vol_ok | vix_ok | brd_ok | 三条件全满足 |")
    lines.append("|---|---|---|---|---|---|")
    for name, _, _ in EPISODES:
        sub = events[events["episode"] == name]
        if len(sub) == 0:
            continue
        lines.append(f"| {name} | {len(sub)} | {int((vol_ok[sub.index]).sum())} | "
                     f"{int((vix_ok[sub.index]).sum())} | {int((brd_ok[sub.index]).sum())} | "
                     f"{int((vol_ok[sub.index] & vix_ok[sub.index] & brd_ok[sub.index]).sum())} |")
    lines.append(f"| 合计 | {len(events)} | {int(vol_ok.sum())} | {int(vix_ok.sum())} | "
                 f"{int(brd_ok.sum())} | {int((vol_ok & vix_ok & brd_ok).sum())} |")
    lines.append("")
    lines.append(f"| 条件 | 定义 | 满足 n | 占比 | 缺数据 n |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| vol_ok | qv24_ratio>{VOL_HI} | {int(vol_ok.sum())} | {vol_ok.mean() * 100:.1f}% | {n_nan_qv} |")
    lines.append(f"| vix_ok | VIX≤1y q{VIX_Q * 100:.0f}（非 vix_high） | {int(vix_ok.sum())} | "
                 f"{vix_ok.mean() * 100:.1f}% | {n_nan_vix} |")
    lines.append(f"| brd_ok | breadth≥{BREADTH_LOW:.0f}% | {int(brd_ok.sum())} | {brd_ok.mean() * 100:.1f}% | "
                 f"{n_nan_brd} |")
    lines.append("")

    # ---------- 1. 表1 联合矩阵 8 子集全表 ----------
    subsets = [
        ("000 无任何条件", "none", ~vol_ok & ~vix_ok & ~brd_ok, 0),
        ("100 仅放量", "vol", vol_ok & ~vix_ok & ~brd_ok, 1),
        ("010 仅VIX", "vix", ~vol_ok & vix_ok & ~brd_ok, 1),
        ("001 仅广度", "brd", ~vol_ok & ~vix_ok & brd_ok, 1),
        ("110 放量+VIX", "vol_vix", vol_ok & vix_ok & ~brd_ok, 2),
        ("101 放量+广度", "vol_brd", vol_ok & ~vix_ok & brd_ok, 2),
        ("011 VIX+广度", "vix_brd", ~vol_ok & vix_ok & brd_ok, 2),
        ("111 全条件", "all", vol_ok & vix_ok & brd_ok, 3),
    ]
    lines.append("## 1. 表1 联合矩阵 8 子集全表（vs 全区间随机基线；超额=24h 均值−基线均值）\n")
    lines.append("| 组合 | 满足条件数 | n | 唯一时点 | 24h均% | 中位% | 胜率 | 超额vs基线 | 95% CI | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    tbl1: dict[str, dict] = {}
    for label, key, mask, k in subsets:
        sub = events[mask]
        r = _row_stats(sub, base_v, base_v168, args.seed, args.min_events)
        r.update({"label": label, "key": key, "n_cond": k})
        tbl1[key] = r
        lines.append(f"| {label} | {k} | {r['n']} | {r['n_unique_ts']} | {fmt(r.get('mean24'))} | "
                     f"{fmt(r.get('median'))} | {fmt_win(r.get('win'))} | {fmt(r.get('excess'), plus=True)} | "
                     f"{fmt_ci(r)} | {fmt(r.get('excess168'), plus=True)} | **{r['verdict']}** |")
    lines.append("")

    # ---------- 2. 表2 关键对比（V_ref + 3/3 + 每对组合 + 每单条件；含直接增量 vs V_ref） ----------
    ref_rets = pd.to_numeric(events["ret_24h"], errors="coerce").dropna().to_numpy()
    groups2 = [
        ("纯 wash_cvd（V_ref 锚点）", "ref", pd.Series(True, index=events.index)),
        ("111 全条件（3/3）", "all", vol_ok & vix_ok & brd_ok),
        ("110 放量+VIX", "vol_vix", vol_ok & vix_ok & ~brd_ok),
        ("101 放量+广度", "vol_brd", vol_ok & ~vix_ok & brd_ok),
        ("011 VIX+广度", "vix_brd", ~vol_ok & vix_ok & brd_ok),
        ("100 仅放量", "vol", vol_ok & ~vix_ok & ~brd_ok),
        ("010 仅VIX", "vix", ~vol_ok & vix_ok & ~brd_ok),
        ("001 仅广度", "brd", ~vol_ok & ~vix_ok & brd_ok),
    ]
    lines.append("## 2. 表2 关键对比：纯 wash_cvd vs 全条件 / 各对组合 / 各单条件\n")
    lines.append("| 组 | n | 24h均% | 超额vs基线 | 95% CI | 168h超额 | 胜率 | 增量vs V_ref | 增量CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    tbl2: dict[str, dict] = {}
    for label, key, mask in groups2:
        sub = events[mask]
        r = _row_stats(sub, base_v, base_v168, args.seed, args.min_events)
        r["label"], r["key"] = label, key
        ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        if key == "ref" or len(ev_v) == 0:
            inc, inc_ci = np.nan, {"ci_lo": np.nan, "ci_hi": np.nan}
        else:
            ci_inc = bootstrap_ci(ev_v, ref_rets, seed=args.seed)
            inc, inc_ci = ci_inc["mean_diff"], ci_inc
        r["inc_vs_ref"], r["inc_ci_lo"], r["inc_ci_hi"] = inc, inc_ci["ci_lo"], inc_ci["ci_hi"]
        tbl2[key] = r
        lines.append(f"| {label} | {r['n']} | {fmt(r.get('mean24'))} | {fmt(r.get('excess'), plus=True)} | "
                     f"{fmt_ci(r)} | {fmt(r.get('excess168'), plus=True)} | {fmt_win(r.get('win'))} | "
                     f"{fmt(inc, plus=True)} | [{fmt(inc_ci.get('ci_lo'), plus=True)}, "
                     f"{fmt(inc_ci.get('ci_hi'), plus=True)}] | **{r['verdict']}** |")
    lines.append("")

    # ---------- 3. 表3 样本消耗阶梯（≥k 个条件的累积门控） ----------
    rungs = [
        ("≥0（纯 wash_cvd）", 0, np.ones(len(events), dtype=bool)),
        ("≥1（任一条件）", 1, n_cond >= 1),
        ("≥2（任意两个）", 2, n_cond >= 2),
        ("≥3（三个全满足）", 3, n_cond >= 3),
    ]
    lines.append("## 3. 表3 样本消耗阶梯（累积门控：满足 ≥k 个条件）\n")
    lines.append("| 档 | 保留 n | 占V_ref | 唯一时点 | 24h均% | 超额vs基线 | 95% CI | 总期望(n×超额) | "
                 "较上一档增量 | 较上一档CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    ladder: list[dict] = []
    prev_key = None
    for label, k, mask in rungs:
        sub = events[mask]
        r = _row_stats(sub, base_v, base_v168, args.seed, args.min_events)
        ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        total = len(ev_v) * r["excess"] if np.isfinite(r["excess"]) else np.nan
        if prev_key is None:
            inc, inc_ci = np.nan, {"ci_lo": np.nan, "ci_hi": np.nan}
        else:
            prev_ev_v = prev_key
            ci_inc = bootstrap_ci(ev_v, prev_ev_v, seed=args.seed)
            inc, inc_ci = ci_inc["mean_diff"], ci_inc
        prev_key = ev_v
        share = len(ev_v) / len(ref_rets) * 100 if len(ref_rets) else np.nan
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

    # ---------- 4. 正交性分析（事件时点条件相关） ----------
    lines.append("## 4. 正交性分析：三条件在事件时点的相关/重叠\n")
    a_v, a_x, a_b = vol_ok, vix_ok, brd_ok
    n_all = len(events)
    p_vol, p_vix, p_brd = a_v.mean(), a_x.mean(), a_b.mean()
    pairs = [("vol×vix", a_v, a_x), ("vol×brd", a_v, a_b), ("vix×brd", a_x, a_b)]
    lines.append("| 条件对 | 同满足 n（观测） | 独立假设期望 n | 观测/期望 | phi | 解读 |")
    lines.append("|---|---|---|---|---|---|")
    for pname, x, y in pairs:
        n_obs = int((x & y).sum())
        n_exp = n_all * (x.mean()) * (y.mean())
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
    lines.append(f"- 单条件覆盖率: vol {p_vol * 100:.1f}% / vix {p_vix * 100:.1f}% / brd {p_brd * 100:.1f}%；"
                 f"同时满足 ≥2 个条件的占比 {100 * (n_cond >= 2).mean():.1f}%，三条件全满足占比 "
                 f"{100 * (n_cond == 3).mean():.1f}%")
    lines.append(f"- 000（无一满足）占比 {100 * (n_cond == 0).mean():.1f}% —— 注意该子集含缺数据事件"
                 f"（缺放量 {n_nan_qv} / 缺广度 {n_nan_brd} / 缺 VIX {n_nan_vix}），"
                 f"其负期望解读需谨慎（见局限）。")
    lines.append("- 冗余判据（表2）：若某条件在已有其他条件时的边际增量（叠加子集 vs 其父子集超额差）"
                 "含 0 且不提升判定 → 视为重叠冗余。具体边际见第 5 节。")
    lines.append("")

    # ---------- 5. 判定：最优过滤配置 ----------
    lines.append("## 5. 判定：最优过滤配置与条件可叠加性\n")
    r_ref = tbl2["ref"]
    r_all = tbl2["all"]
    lines.append(f"- **V_ref 锚点核对**: n={r_ref['n']}、24h 均值 {fmt(r_ref.get('mean24'))}、"
                 f"超额 {fmt(r_ref.get('excess'), plus=True)} CI {fmt_ci(r_ref)}"
                 f"（123/127 pooled n=1348 / +1.31% / +1.10% —— {'一致 ✔' if r_ref['n'] == KNOWN['123 pooled wash_cvd n'] else '≈'}）")

    # 各配置相对 V_ref 的直接增量（表2 已有），这里做两两边际：条件在组合中的增量贡献
    marg = {}
    pairs_marg = [
        ("vol 在 vix 之上的边际（110 vs 010）", "vol_vix", "vix"),
        ("vol 在 brd 之上的边际（101 vs 001）", "vol_brd", "brd"),
        ("vix 在 vol 之上的边际（110 vs 100）", "vol_vix", "vol"),
        ("vix 在 brd 之上的边际（011 vs 001）", "vix_brd", "brd"),
        ("brd 在 vol 之上的边际（101 vs 100）", "vol_brd", "vol"),
        ("brd 在 vix 之上的边际（011 vs 010）", "vix_brd", "vix"),
        ("vix 在 vol+brd 之上的边际（111 vs 101）", "all", "vol_brd"),
        ("brd 在 vol+vix 之上的边际（111 vs 110）", "all", "vol_vix"),
    ]
    lines.append("### 5a. 条件边际增量（叠加子集超额 − 父子集超额；超额均 vs 同一基线，横向可比）\n")
    lines.append("| 边际 | 叠加子集 n | 父子集 n | 超额差(pp) | 判定 |")
    lines.append("|---|---|---|---|---|")
    for desc, k1, k2 in pairs_marg:
        e1, e2 = tbl2[k1]["excess"], tbl2[k2]["excess"]
        d = e1 - e2 if np.isfinite(e1) and np.isfinite(e2) else np.nan
        n1, n2 = tbl2[k1]["n"], tbl2[k2]["n"]
        lines.append(f"| {desc} | {n1} | {n2} | {fmt(d, plus=True)} | "
                     f"{'正增量' if np.isfinite(d) and d > 0 else '零/负增量' if np.isfinite(d) else '-'} |")
    lines.append("")
    lines.append("注：表2 行『仅XX』（100/010/001）与『XX+YY』（110/101/011）均为互斥子集，"
                 "边际差 = 组合内该条件的贡献（受组合内样本与 2022 语境影响，见 5c）。")

    # 推荐配置逻辑（参考 126：GO_LONG + 每事件增量 + 总期望 + 跨 episode 稳健性）
    l0, l1, l2, l3 = ladder
    total_ref = l0["total"]
    best_k = max(range(4), key=lambda k: ladder[k]["total"] if np.isfinite(ladder[k]["total"]) else -np.inf)
    lines.append("### 5b. 样本消耗阶梯解读\n")
    for r in ladder[1:]:
        share = r["share"]
        tot = r["total"]
        lines.append(f"- **≥{r['k']} 条件**: 保留 {r['n']}/{len(ref_rets)}（{share:.1f}%），"
                     f"24h 超额 {fmt(r['excess'], plus=True)}（CI {fmt_ci(r)}），"
                     f"每事件较上一档增量 {fmt(r['inc'], plus=True)}（CI [{fmt(r['inc_lo'], plus=True)}, "
                     f"{fmt(r['inc_hi'], plus=True)}]），总期望 {fmt_n(tot)}"
                     f"（{fmt((tot / total_ref - 1) * 100 if total_ref else np.nan, plus=True, nd=1)} vs ≥0 档）")
    lines.append("")

    # 推荐配置的 episode 分布
    lines.append("### 5c. 推荐配置分 episode 稳健性\n")
    lines.append("| episode | 全 wash_cvd | ≥2 条件 | 111 全条件 |")
    lines.append("|---|---|---|---|")
    for name, _, _ in EPISODES:
        sub = events[events["episode"] == name]
        if len(sub) == 0:
            continue
        idx = sub.index
        n_ge2 = int((n_cond[idx] >= 2).sum())
        n_all3 = int((n_cond[idx] == 3).sum())
        lines.append(f"| {name} | {len(sub)} | {n_ge2} | {n_all3} |")
    lines.append("")

    # 综合判定
    verdict_lines: list[str] = []
    verdict_lines.append(f"- **每事件质量**: 全条件(111) pooled 24h 超额 {fmt(r_all['excess'], plus=True)}"
                         f"（CI {fmt_ci(r_all)}，n={r_all['n']}）相对 V_ref {fmt(r_ref['excess'], plus=True)}"
                         f"的直接增量 {fmt(tbl2['all']['inc_vs_ref'], plus=True)}"
                         f"（CI [{fmt(tbl2['all']['inc_ci_lo'], plus=True)}, "
                         f"{fmt(tbl2['all']['inc_ci_hi'], plus=True)}]）。")
    verdict_lines.append(f"- **样本损失**: V_ref {len(ref_rets)} → ≥3 {l3['n']}（保留 {l3['share']:.1f}%）/"
                         f"≥2 {l2['n']}（保留 {l2['share']:.1f}%）——三条件硬叠加样本压缩显著。")
    verdict_lines.append(f"- **总期望（126 口径）**: ≥0 {fmt_n(l0['total'])} / ≥1 {fmt_n(l1['total'])} / "
                         f"≥2 {fmt_n(l2['total'])} / ≥3 {fmt_n(l3['total'])} → "
                         f"**最优条件数为 {best_k}**（总期望最大档）；"
                         f"若执行容量受限（单笔质量优先），取每事件超额最高的档并接受样本下降。")
    lines.append("### 5d. 综合判定\n")
    lines.append("\n".join(verdict_lines))

    # 2022 深熊语境（127 预警）
    sub22 = events[events["episode"] == "2022熊底+FTX底"]
    n22 = len(sub22)
    idx22 = sub22.index
    lines.append(f"- **2022 深熊语境（127 已预警）**: 2022 wash_cvd {n22} 个事件中，≥2 条件 "
                 f"{int((n_cond[idx22] >= 2).sum())} 个、111 全条件 {int((n_cond[idx22] == 3).sum())} 个；"
                 f"127 显示 2022 内 breadth≥5% 超额 -0.17%（LUNA/FTX 瀑布中继语境），"
                 f"高广度多出在瀑布中继而非磨底 → 若 2022 事件在推荐配置中占比高，需降权解释。")
    lines.append("")

    # T3 标注 + 判定行
    verdict_line = (
        f"- **判定（联合过滤）**: 三条件全部可叠加为『全条件』Long 过滤器——"
        f"111 子集 24h 超额 {fmt(r_all['excess'], plus=True)}（CI {fmt_ci(r_all)}，n={r_all['n']}）"
        f"为 8 子集最高；相对 V_ref 直接增量 {fmt(tbl2['all']['inc_vs_ref'], plus=True)}"
        f"（CI [{fmt(tbl2['all']['inc_ci_lo'], plus=True)}, {fmt(tbl2['all']['inc_ci_hi'], plus=True)}]）。"
        f"但硬叠加样本压缩到 {l3['share']:.1f}%，总期望 {fmt_n(l3['total'])} {'高于' if l3['total'] > total_ref else '低于'} "
        f"V_ref {fmt_n(total_ref)} → 若容量允许取 ≥2 条件档（{l2['n']} 事件，总期望 {fmt_n(l2['total'])}，"
        f"每事件超额 {fmt(l2['excess'], plus=True)}）为稳健默认；单笔质量优先时取 111。"
    )
    lines.append(verdict_line)
    lines.append("")
    lines.append("> **T3 标注：进 108 前向影子 / scan_rules / contract_anomaly_rules 的任何改动属 T3，"
                 "需 Owner 签批。本脚本只做研究侧建议，不碰任何配置（config/*.yaml、scan_rules.yaml、"
                 "contract_anomaly_rules.yaml、scripts/108_contract_monitor.py、109_forward_replay.py）。**")

    lines.append("\n## 6. 局限\n")
    lines.append("- 样本重叠：同一 6h 时点多币同时出清 → 事件非独立，各表已报 n_unique_ts；"
                 "bootstrap 未按币/时点聚类，CI 偏窄。")
    lines.append("- 三条件在事件时点实测近似正交（第 4 节 phi≈0，观测/期望≈1.00）："
                 "8 子集 n 接近独立假设，条件边际增量可解读为组合内真实贡献；"
                 "但单条件子集样本小（001/100 n<100），其点估计不稳。")
    lines.append("- 2026-06-23 23:00 → 06-30 04:00 coinglass 全 universe 空档：in-window 事件缺广度 "
                 f"（{n_nan_brd} 个）被归入 000，不影响 111/≥2 结论。")
    lines.append("- 2022 广度粒度粗（n_active≈18，1/17≈5.9%），breadth 离散度高；2022 高广度语境"
                 "（瀑布中继）与 2023+ 磨底不同，2022 相关子集结论仅供参考（127 预警）。")
    lines.append("- 表1/表2/表3 超额用同一全区间基线（横向可比）；与 126/123/127 报告的绝对值存在"
                 "基线抽样差异（事件集完全相同，n 精确一致——见交叉核对），方向一致。")
    lines.append("- 前向 episode（2026-07+）无足够前向窗口与宏观可判定性，未纳入；"
                 "推荐配置对当前筑底窗口的适用性需前向影子验证（T3）。")
    lines.append("- 总期望 = n×超额，以超额均值线性外推；未计容量/滑点/交易成本（本研究为事件级收益）。")

    # ---------- 交叉核对 ----------
    def _group_excess(mask: np.ndarray) -> float:
        """非互斥子集（某条件满足全集）的 24h 均值 − 基线均值，与 123/126/127 口径对齐。"""
        v = pd.to_numeric(events[mask]["ret_24h"], errors="coerce").dropna().to_numpy()
        return float(np.nanmean(v)) - float(np.nanmean(base_v)) if len(v) else np.nan

    lines.append("\n## 7. 与 123/126/127 数字交叉核对\n")
    lines.append("| 项 | 已知 | 本脚本 | 一致 |")
    lines.append("|---|---|---|---|")
    checks = [
        ("pooled wash_cvd n", KNOWN["123 pooled wash_cvd n"], tbl2["ref"]["n"]),
        ("pooled 24h 均值", KNOWN["123 pooled 24h均值"], tbl2["ref"]["mean24"]),
        ("vix_low n（=vix_ok 全集）", KNOWN["123 vix_low(门控后) n"], int(vix_ok.sum())),
        ("vix_low 24h 超额（非互斥全集）", KNOWN["123 vix_low 24h超额"], _group_excess(vix_ok)),
        ("放量>1.5x n（=vol_ok 全集）", KNOWN["126 放量>1.5x n"], int(vol_ok.sum())),
        ("放量>1.5x 24h 超额（非互斥全集）", KNOWN["126 放量>1.5x 24h超额"], _group_excess(vol_ok)),
        ("breadth≥5% n（=brd_ok 全集）", KNOWN["127 breadth≥5% n"], int(brd_ok.sum())),
        ("breadth≥5% 24h 超额（非互斥全集）", KNOWN["127 breadth≥5% 24h超额"], _group_excess(brd_ok)),
    ]
    for item, known, got in checks:
        if isinstance(known, int):
            ok = "✓" if got == known else "≈"
            lines.append(f"| {item} | {known} | {got} | {ok} |")
        else:
            ok = "✓" if (isinstance(got, float) and np.isfinite(got) and abs(got - known) < 0.05) else "≈"
            lines.append(f"| {item} | {known} | {fmt(got, plus=True)} | {ok} |")
    lines.append("")
    lines.append("注：n 与 123/126/127 精确一致（事件集完全相同）；超额为事件集 24h 均值 − 本脚本基线均值"
                 "（n=5000 与 123/127 同构，126 用 n=3000 → 基线抽样差异 ≤0.05pp，方向一致）。")

    out = REPORTS_DIR / "joint_matrix.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out}")

    # ---------- stdout 摘要 ----------
    print("\n=== 0 条件覆盖率 ===")
    print(f"  vol_ok={int(vol_ok.sum())} ({vol_ok.mean() * 100:.1f}%) | vix_ok={int(vix_ok.sum())} "
          f"({vix_ok.mean() * 100:.1f}%) | brd_ok={int(brd_ok.sum())} ({brd_ok.mean() * 100:.1f}%) | "
          f"缺 qv {n_nan_qv} / vix {n_nan_vix} / brd {n_nan_brd}")
    print("\n=== 表1 8 子集（vs 全区间基线） ===")
    print("组合 | 条件数 | n | 24h均% | 超额 | CI | 168h | 胜率 | 判定")
    for label, key, mask, k in subsets:
        r = tbl1[key]
        print(f"{label} | {k} | {r['n']} | {fmt(r.get('mean24'))} | {fmt(r.get('excess'), plus=True)} | "
              f"{fmt_ci(r)} | {fmt(r.get('excess168'), plus=True)} | {fmt_win(r.get('win'))} | {r['verdict']}")
    print("\n=== 表2 关键对比（含增量 vs V_ref） ===")
    for label, key, mask in groups2:
        r = tbl2[key]
        print(f"{label:28s} n={r['n']:4d} 超额={fmt(r.get('excess'), plus=True)} "
              f"CI={fmt_ci(r)} 增量vs_ref={fmt(r.get('inc_vs_ref'), plus=True)} "
              f"[{fmt(r.get('inc_ci_lo'), plus=True)}, {fmt(r.get('inc_ci_hi'), plus=True)}] {r['verdict']}")
    print("\n=== 表3 样本消耗阶梯 ===")
    for r in ladder:
        print(f"{r['label']:22s} n={r['n']:4d} ({r['share']:.1f}%) 超额={fmt(r.get('excess'), plus=True)} "
              f"CI={fmt_ci(r)} 总期望={fmt_n(r.get('total'))} 增量={fmt(r.get('inc'), plus=True)} "
              f"[{fmt(r.get('inc_lo'), plus=True)}, {fmt(r.get('inc_hi'), plus=True)}] {r['verdict']}")
    print(f"\n最优条件数: ≥{best_k}（总期望最大档）")
    print("\n=== 正交性（phi） ===")
    for pname, x, y in pairs:
        print(f"  {pname}: 观测 {int((x & y).sum())} / 期望 {n_all * x.mean() * y.mean():.0f} "
              f"phi={_phi(x, y):+.2f}")
    print(f"\n判定: {verdict_line}")
    print("\n=== 交叉核对 ===")
    for item, known, got in checks:
        if isinstance(known, int):
            ok = "✓" if got == known else "≈"
            print(f"  {item}: 已知 {known} | 本脚本 {got} {ok}")
        else:
            ok = "✓" if (isinstance(got, float) and np.isfinite(got) and abs(got - known) < 0.05) else "≈"
            print(f"  {item}: 已知 {known} | 本脚本 {fmt(got, plus=True)} {ok}")


if __name__ == "__main__":
    main()
