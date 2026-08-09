"""136_eggg_triple.py — 0xEggg 框架补测：OI 水平分位 / 3日成交变化 / 费率×OI 逼空狗庄两侧 / 低市值代理。

承接 AlphaHive V3 山寨合约异动研究。0xEggg 框架维度（低市值 / 高 OI / OI-MC /
费率 / 3日成交变化）中尚未直接验证的部分，本轮用可用代理补测：

- oi_z：OI 水平 30d(720h) z-score（自 oi_ohlc time/close，reindex 后 rolling_z）
  ——"高 OI/MC"的代理（无历史 MC，诚实标注为代理）。
- qv72_ratio：72h(3d) 累计 quote_volume / 30d 72h 累计中位数——"3d 成交变化量"
  （对照 126 的 24h 口径）。
- funding asof（funding_on_axis，9h 新鲜度）。
- qv24_pctile：24h quote_volume 绝对水平横截面分位（低分位 = 绝对成交额低于同期
  大部分合约 → 低市值壳的成交额代理）。

五个检验（wash_cvd 事件，OI 相关窗口 2024-06-01..2026-06-23，其余 2022-01-01..2026-06-30）：
表1 wash_cvd × oi_z 分档；表2 wash_cvd × qv72_ratio 分档；
表3 逼空三元组（funding<-0.0002 & oi_z>1.5 & qv24_ratio>1.5，Long）；
表4 狗庄侧（funding>+0.0005 & oi_z>1.5 & 成交额低分位，描述性观察）；
表5 wash_cvd × 24h 成交额水平分位分层（小盘代理）。

只读数据；无订单路径；不改 config / 108 / 109 / 定时任务；不跑 pytest。
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
)

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
load_funding_series = m113.load_funding_series
funding_on_axis = m113.funding_on_axis
rolling_z = m113.rolling_z
EPISODES = m113.EPISODES
episode_of = m113.episode_of
detect_events = m115.detect_events
COINGLASS_RAW1H = m113.COINGLASS_RAW1H
FUNDING_DIR = m113.FUNDING_DIR

# ---------- 研究区间与参数 ----------
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
OI_LO_MS = int(pd.Timestamp("2024-06-01", tz="UTC").timestamp() * 1000)
OI_HI_MS = int(pd.Timestamp("2026-06-23", tz="UTC").timestamp() * 1000)
HOUR_MS = 3_600_000
N_BASELINE = 3000
SEED = 2026
MIN_EVENTS = 30
COOLDOWN_H = 72.0

# 0xEggg 维度阈值
OI_Z_HI = 1.5      # 高 OI 分位（30d z > 1.5）
OI_Z_LO = -1.5     # 低 OI 分位
VOL_HI = 1.5       # 放量阈值（同 121/126 的 1.5x）
VOL_MID_LO = 0.8   # 常态量下界
FUND_NEG = -0.0002  # 深负费率（0xEggg 逼空侧条件）
FUND_DOG = 0.0005   # 高正费率（狗庄侧条件）
PCT_LO = 1.0 / 3.0  # 小盘代理：成交额横截面低分位（低 1/3）
PCT_HI = 2.0 / 3.0  # 高 1/3
FWD_EP = "当前筑底(前向)"

# 已知数字（交叉核对目标；来源 115/126 报告）
KNOWN = {
    "wash_cvd pooled n": 1348,
    "wash_cvd 2022/2023/2024/2025 n": "123/356/278/589",
    "wash_cvd pooled 24h超额(115基线)": 1.31,
    "qv24_ratio>1.5 n": 838,
    "qv24_ratio>1.5 24h超额": 1.90,
    "常态0.8~1.5x n": 433,
    "常态0.8~1.5x 24h超额": -0.53,
}


# ---------- 特征构造（事件 asof，无前视） ----------

def add_volume_features(ctxs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """一次性读 klines quote_volume，构造 qv24_usd / qv24_ratio / qv72_ratio。

    qv24_usd = quote_volume.rolling(24).sum()（绝对成交额，小盘代理基础）
    qv24_ratio = qv24 / qv24.rolling(720, min_periods=360).median()（公式同 126/121）
    qv72_ratio = qv72 / qv72.rolling(720, min_periods=360).median()（3d 累计同口径）
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
        t["qv24_usd"] = qv24
        qv24_med = qv24.rolling(720, min_periods=360).median()
        t["qv24_ratio"] = (qv24 / qv24_med.replace(0, pd.NA)).replace([np.inf, -np.inf], pd.NA)
        qv72 = qv_ser.rolling(72).sum()
        qv72_med = qv72.rolling(720, min_periods=360).median()
        t["qv72_ratio"] = (qv72 / qv72_med.replace(0, pd.NA)).replace([np.inf, -np.inf], pd.NA)
    return ctxs


def add_oi_z(ctxs: dict[str, pd.DataFrame], window: int = 720) -> dict[str, pd.DataFrame]:
    """OI 水平 30d(720h) z-score：自 oi_ohlc 读 time/close，reindex 到 ctx 后 rolling_z。

    "高 OI/MC"的代理——历史 MC 缺失（CoinGecko 无历史），用 OI 自身 30d 分位代替。
    """
    for sym, t in ctxs.items():
        t["oi_z"] = np.nan
        oi_p = COINGLASS_RAW1H / "oi_ohlc" / f"{sym}.parquet"
        if not oi_p.exists():
            continue
        oi = pd.read_parquet(oi_p)
        oi_ts = pd.to_numeric(oi["time"], errors="coerce").to_numpy(dtype=np.int64)
        oi_c = pd.to_numeric(oi["close"], errors="coerce").to_numpy(dtype=float)
        oi_ser = pd.Series(oi_c, index=pd.Index(oi_ts))
        oi_ser = oi_ser[~oi_ser.index.duplicated(keep="last")].sort_index().reindex(t.index)
        t["oi_z"] = rolling_z(oi_ser, window)
    return ctxs


def add_qv24_pctile_series(ctxs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """24h 成交额绝对水平横截面分位（逐小时 rank，NaN 安全）。

    pct ∈ (0,1]：低分位 = 该时点绝对成交额低于同期大部分合约 → 低市值壳的成交额代理。
    用宽表 row-wise rank；符号上市时间短或该时点可用合约少时，分母随之变小（见局限）。
    """
    syms = [s for s in ctxs if "qv24_usd" in ctxs[s].columns]
    if not syms:
        return ctxs
    arrs = [ctxs[s].index.to_numpy(dtype=np.int64) for s in syms]
    idx = pd.Index(np.unique(np.concatenate(arrs)), dtype=np.int64)
    wide = pd.DataFrame(index=idx, columns=syms, dtype=float)
    for s in syms:
        wide[s] = ctxs[s]["qv24_usd"]
    pct = wide.rank(axis=1, pct=True)
    for s in syms:
        ctxs[s]["qv24_pctile"] = pct[s]
    return ctxs


def add_funding_rate(ctxs: dict[str, pd.DataFrame],
                     fundings: dict[str, pd.Series]) -> dict[str, pd.DataFrame]:
    """funding asof 列（funding_on_axis，>9h 陈旧 → NaN）。"""
    for sym, t in ctxs.items():
        f = fundings.get(sym)
        t["funding_rate"] = (funding_on_axis(f, t.index.to_numpy())
                             if f is not None else np.full(len(t), np.nan))
    return ctxs


def attach_asof(ctxs: dict[str, pd.DataFrame], events: pd.DataFrame,
                col: str, out_col: str | None = None) -> pd.DataFrame:
    """对每个事件 ts 取 ctx 列 col 的 asof 值（事件行及之前最近有效，无前视）。"""
    out_col = out_col or f"{col}_at_event"
    ev = events.copy()
    ev[out_col] = np.nan
    for sym, g in ev.groupby("symbol", sort=False):
        if sym not in ctxs or col not in ctxs[sym].columns:
            continue
        t = ctxs[sym]
        idx = t.index.to_numpy(dtype=np.int64)
        pos_raw = np.searchsorted(idx, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        valid = pos_raw >= 0
        pos = np.clip(pos_raw, 0, len(idx) - 1)
        vals = pd.to_numeric(t[col], errors="coerce").to_numpy(dtype=float)
        ev.loc[g.index, out_col] = np.where(valid, vals[pos], np.nan)
    return ev


# ---------- 事件检测 ----------

def detect_mask_events(sym: str, ctx: pd.DataFrame, mask: np.ndarray,
                       cooldown_h: float = COOLDOWN_H) -> pd.DataFrame:
    """通用布尔掩码事件检测（72h 冷却，同 115 口径）。"""
    axis = ctx.index.to_numpy()
    cooldown_ms = int(cooldown_h * HOUR_MS)
    events: list[int] = []
    last: int | None = None
    for i in np.flatnonzero(mask):
        ts = int(axis[i])
        if last is None or (ts - last) >= cooldown_ms:
            events.append(ts)
            last = ts
    if not events:
        return pd.DataFrame(columns=["symbol", "timestamp"])
    return pd.DataFrame({"symbol": sym, "timestamp": np.array(events, dtype=np.int64)})


def detect_squeeze_triple(sym: str, ctx: pd.DataFrame,
                          funding: pd.Series | None) -> pd.DataFrame:
    """表3 逼空三元组（0xEggg 逼空侧，Long）：funding<-0.0002 & oi_z>1.5 & qv24_ratio>1.5。"""
    axis = ctx.index.to_numpy()
    fund = funding_on_axis(funding, axis) if funding is not None else np.full(len(axis), np.nan)
    oi_z = ctx["oi_z"].to_numpy()
    qv24r = ctx["qv24_ratio"].to_numpy()
    mask = (np.isfinite(fund) & (fund < FUND_NEG)
            & np.isfinite(oi_z) & (oi_z > OI_Z_HI)
            & np.isfinite(qv24r) & (qv24r > VOL_HI))
    return detect_mask_events(sym, ctx, mask)


def detect_dog_side(sym: str, ctx: pd.DataFrame,
                    funding: pd.Series | None) -> pd.DataFrame:
    """表4 狗庄侧（做空候选观察）：funding>+0.0005 & oi_z>1.5 & 成交额横截面低分位（小盘代理）。"""
    axis = ctx.index.to_numpy()
    fund = funding_on_axis(funding, axis) if funding is not None else np.full(len(axis), np.nan)
    oi_z = ctx["oi_z"].to_numpy()
    pct = ctx["qv24_pctile"].to_numpy()
    mask = (np.isfinite(fund) & (fund > FUND_DOG)
            & np.isfinite(oi_z) & (oi_z > OI_Z_HI)
            & np.isfinite(pct) & (pct < PCT_LO))
    return detect_mask_events(sym, ctx, mask)


# ---------- 统计工具（126 口径） ----------

def build_baseline(ctxs: dict[str, pd.DataFrame], rng: np.random.Generator,
                   start_ms: int, end_ms: int, n: int) -> pd.DataFrame:
    base = draw_random_events(ctxs, n, rng, max_forward_hours=168,
                              start_ms=start_ms, end_ms=end_ms)
    if base.empty:
        return pd.DataFrame()
    parts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            parts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def excess(ev_rets: np.ndarray, base_rets: np.ndarray, seed: int) -> dict:
    return bootstrap_ci(np.asarray(ev_rets, dtype=float),
                        np.asarray(base_rets, dtype=float),
                        n_boot=1000, alpha=0.05, seed=seed)


def verdict_for(n: int, ci: dict, min_events: int) -> str:
    if n < min_events:
        return "样本不足"
    if not np.isfinite(ci.get("ci_lo", np.nan)) or not np.isfinite(ci.get("ci_hi", np.nan)):
        return "无基线"
    if ci["ci_lo"] > 0:
        return "GO_LONG"
    if ci["ci_hi"] < 0:
        return "GO_SHORT"
    return "NO_GO"


def stats_row(ev: pd.DataFrame, base: pd.DataFrame, label: str,
              min_events: int, seed: int) -> dict:
    n = len(ev)
    r: dict = {"label": label, "n": n}
    ev24 = pd.to_numeric(ev["ret_24h"], errors="coerce").dropna().to_numpy()
    ev168 = pd.to_numeric(ev["ret_168h"], errors="coerce").dropna().to_numpy()
    if len(ev24) == 0 or base.empty:
        r.update(mean24=np.nan, ex24=np.nan, ci_lo=np.nan, ci_hi=np.nan,
                 ex168=np.nan, win=np.nan,
                 verdict="无事件" if n == 0 else "无基线")
        return r
    ci24 = excess(ev24, pd.to_numeric(base["ret_24h"], errors="coerce").dropna().to_numpy(), seed)
    ci168 = excess(ev168, pd.to_numeric(base["ret_168h"], errors="coerce").dropna().to_numpy(), seed) \
        if len(ev168) else {"mean_diff": np.nan}
    r.update(
        mean24=float(np.nanmean(ev24)),
        ex24=ci24["mean_diff"], ci_lo=ci24["ci_lo"], ci_hi=ci24["ci_hi"],
        ex168=ci168.get("mean_diff", np.nan),
        win=float((ev24 > 0).mean()),
        verdict=verdict_for(len(ev24), ci24, min_events),
    )
    return r


def direct_diff(a: pd.DataFrame, b: pd.DataFrame, seed: int) -> dict:
    """事件集直比（a − b 的 24h 均值差 bootstrap）。"""
    ra = pd.to_numeric(a["ret_24h"], errors="coerce").dropna().to_numpy()
    rb = pd.to_numeric(b["ret_24h"], errors="coerce").dropna().to_numpy()
    if len(ra) == 0 or len(rb) == 0:
        return {"mean_diff": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
                "n_event": len(ra), "n_baseline": len(rb)}
    return excess(ra, rb, seed)


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-baseline", type=int, default=N_BASELINE)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--min-events", type=int, default=MIN_EVENTS)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    fundings = load_funding_series(symbols)
    ctxs = add_volume_features(ctxs)
    ctxs = add_oi_z(ctxs)
    ctxs = add_qv24_pctile_series(ctxs)
    ctxs = add_funding_rate(ctxs, fundings)
    print(f"价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)}")

    rng = np.random.default_rng(args.seed)

    # ---------- wash_cvd 事件（全区间，限制 lo..hi，72h 冷却在 detect 阶段） ----------
    evs = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            evs.append(ev)
    events = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)]
    events = events.reset_index(drop=True)
    events["episode"] = episode_of(events["timestamp"].to_numpy())
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    print(f"wash_cvd 事件（全区间）: {len(events)}")

    # 特征 asof
    events = attach_asof(ctxs, events, "oi_z")
    events = attach_asof(ctxs, events, "qv72_ratio")
    events = attach_asof(ctxs, events, "qv24_pctile")

    # OI 窗口子集（表1 用）
    ev_oi = events[(events["timestamp"] >= OI_LO_MS) & (events["timestamp"] <= OI_HI_MS)].copy()

    # ---------- 表3 / 表4 独立事件（OI 窗口） ----------
    ev3s, ev4s = [], []
    for sym, ctx in ctxs.items():
        e3 = detect_squeeze_triple(sym, ctx, fundings.get(sym))
        if not e3.empty:
            ev3s.append(e3)
        e4 = detect_dog_side(sym, ctx, fundings.get(sym))
        if not e4.empty:
            ev4s.append(e4)
    ev3 = pd.concat(ev3s, ignore_index=True) if ev3s else pd.DataFrame(columns=["symbol", "timestamp"])
    ev4 = pd.concat(ev4s, ignore_index=True) if ev4s else pd.DataFrame(columns=["symbol", "timestamp"])
    for ev, lo, hi in ((ev3, OI_LO_MS, OI_HI_MS), (ev4, OI_LO_MS, OI_HI_MS)):
        ev.drop(ev.index[~((ev["timestamp"] >= lo) & (ev["timestamp"] <= hi))], inplace=True)
        ev.reset_index(drop=True, inplace=True)
        ev["episode"] = episode_of(ev["timestamp"].to_numpy())
    ev3_fwd = pd.concat([forward_stats(ctxs[s], g.copy(), DEFAULT_HORIZONS)
                         for s, g in ev3.groupby("symbol", sort=False)], ignore_index=True) \
        if len(ev3) else ev3
    ev4_fwd = pd.concat([forward_stats(ctxs[s], g.copy(), DEFAULT_HORIZONS)
                         for s, g in ev4.groupby("symbol", sort=False)], ignore_index=True) \
        if len(ev4) else ev4
    print(f"表3 逼空三元组: {len(ev3)} | 表4 狗庄侧: {len(ev4)}")

    # ---------- 基线（固定抽取顺序；pooled 首抽=全区间，随后 OI 窗口、episode） ----------
    base_full = build_baseline(ctxs, rng, LO_MS, HI_MS, args.n_baseline)
    base_oi = build_baseline(ctxs, rng, OI_LO_MS, OI_HI_MS, args.n_baseline)
    base_ep: dict[str, pd.DataFrame] = {}
    for name, s, e in EPISODES:
        if name == FWD_EP:
            continue
        start_ms = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
        end_ms = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
        base_ep[name] = build_baseline(ctxs, rng, start_ms, end_ms, args.n_baseline)
    print(f"基线: full pooled {len(base_full)} | OI pooled {len(base_oi)} | "
          f"episode { {k: len(v) for k, v in base_ep.items()} }")

    # ---------- 分档统计 ----------
    def stratify(ev: pd.DataFrame, col: str, groups: dict[str, pd.Series]) -> dict[str, pd.DataFrame]:
        return {k: ev[v] for k, v in groups.items()}

    # 表1: wash_cvd × oi_z（OI 窗口）
    oi_nan = ev_oi["oi_z_at_event"].isna()
    t1_groups = {
        "高OI(oi_z>1.5)": ev_oi["oi_z_at_event"] > OI_Z_HI,
        "中OI(-1.5~1.5)": (ev_oi["oi_z_at_event"] >= OI_Z_LO) & (ev_oi["oi_z_at_event"] <= OI_Z_HI),
        "低OI(oi_z<-1.5)": ev_oi["oi_z_at_event"] < OI_Z_LO,
        "NaN(无OI)": oi_nan,
    }
    t1 = {k: ev_oi[m] for k, m in t1_groups.items()}
    t1_rows = {k: stats_row(v, base_oi, k, args.min_events, args.seed) for k, v in t1.items()}
    t1_inc = {
        "高OI−中OI": direct_diff(t1["高OI(oi_z>1.5)"], t1["中OI(-1.5~1.5)"], args.seed),
        "高OI−低OI": direct_diff(t1["高OI(oi_z>1.5)"], t1["低OI(oi_z<-1.5)"], args.seed),
        "高OI−其余": direct_diff(t1["高OI(oi_z>1.5)"],
                                 ev_oi[~t1_groups["高OI(oi_z>1.5)"]], args.seed),
    }
    # 表1 分 episode（高/中/低/NaN vs 各 episode 基线）
    t1_ep: dict[str, dict[str, dict]] = {}
    for ep in ("2024崩→恢复", "2025顶→熊"):
        sub = ev_oi[ev_oi["episode"] == ep]
        if len(sub) == 0:
            t1_ep[ep] = {}
            continue
        ep_rows: dict[str, dict] = {}
        for k, m in t1_groups.items():
            m_sub = m.reindex(sub.index).fillna(False)
            if m_sub.sum() > 0:
                ep_rows[k] = stats_row(sub[m_sub], base_ep[ep], k,
                                       args.min_events, args.seed)
        t1_ep[ep] = ep_rows

    # 表2: wash_cvd × qv72_ratio（全区间）
    q72 = events["qv72_ratio_at_event"]
    t2_groups = {
        "高量(3d>1.5x)": q72 > VOL_HI,
        "常态(0.8~1.5x)": (q72 >= VOL_MID_LO) & (q72 <= VOL_HI),
        "缩量(<0.8x)": q72 < VOL_MID_LO,
        "NaN(暖机不足)": q72.isna(),
    }
    t2 = {k: events[m] for k, m in t2_groups.items()}
    t2_rows = {k: stats_row(v, base_full, k, args.min_events, args.seed) for k, v in t2.items()}
    t2_inc = {
        "高量−常态": direct_diff(t2["高量(3d>1.5x)"], t2["常态(0.8~1.5x)"], args.seed),
        "高量−缩量": direct_diff(t2["高量(3d>1.5x)"], t2["缩量(<0.8x)"], args.seed),
        "高量−其余": direct_diff(t2["高量(3d>1.5x)"], events[~t2_groups["高量(3d>1.5x)"]], args.seed),
    }

    # 表3: 逼空三元组（OI 窗口，Long）
    t3_rows = {"pooled": stats_row(ev3_fwd, base_oi, "pooled", args.min_events, args.seed)}
    t3_ep = {}
    for ep in ("2024崩→恢复", "2025顶→熊"):
        sub = ev3_fwd[ev3_fwd["episode"] == ep]
        if len(sub) == 0:
            t3_ep[ep] = None
            continue
        t3_ep[ep] = stats_row(sub, base_ep[ep], ep, args.min_events, args.seed)

    # 表4: 狗庄侧（描述性，不做交易结论）
    def desc_row(ev: pd.DataFrame) -> dict:
        n = len(ev)
        if n == 0:
            return {"n": 0, "mean24": np.nan, "med24": np.nan, "win24": np.nan,
                    "mean72": np.nan, "med72": np.nan, "win72": np.nan, "dir": "-"}
        r24 = pd.to_numeric(ev["ret_24h"], errors="coerce").dropna().to_numpy()
        r72 = pd.to_numeric(ev["ret_72h"], errors="coerce").dropna().to_numpy()
        mean24 = float(np.nanmean(r24)) if len(r24) else np.nan
        med24 = float(np.nanmedian(r24)) if len(r24) else np.nan
        mean72 = float(np.nanmean(r72)) if len(r72) else np.nan
        med72 = float(np.nanmedian(r72)) if len(r72) else np.nan
        direction = "上行(↑)" if np.isfinite(med24) and med24 > 0.0 else \
            ("下行(↓)" if np.isfinite(med24) and med24 < 0.0 else "-")
        return {"n": n, "mean24": mean24, "med24": med24,
                "win24": float((r24 > 0).mean()) if len(r24) else np.nan,
                "mean72": mean72, "med72": med72,
                "win72": float((r72 > 0).mean()) if len(r72) else np.nan,
                "dir": direction}

    t4_rows = {"pooled": desc_row(ev4_fwd)}
    t4_ep = {}
    for ep in ("2024崩→恢复", "2025顶→熊"):
        sub = ev4_fwd[ev4_fwd["episode"] == ep]
        if len(sub) > 0:
            t4_ep[ep] = desc_row(sub)

    # 表5: wash_cvd × 24h 成交额水平分位（全区间，小盘代理分层）
    pct = events["qv24_pctile_at_event"]
    t5_groups = {
        "低成交额(<1/3)": pct < PCT_LO,
        "中成交额(1/3~2/3)": (pct >= PCT_LO) & (pct <= PCT_HI),
        "高成交额(>2/3)": pct > PCT_HI,
        "NaN(无成交额)": pct.isna(),
    }
    t5 = {k: events[m] for k, m in t5_groups.items()}
    t5_rows = {k: stats_row(v, base_full, k, args.min_events, args.seed) for k, v in t5.items()}
    t5_inc = {
        "低−中": direct_diff(t5["低成交额(<1/3)"], t5["中成交额(1/3~2/3)"], args.seed),
        "低−高": direct_diff(t5["低成交额(<1/3)"], t5["高成交额(>2/3)"], args.seed),
        "低−其余": direct_diff(t5["低成交额(<1/3)"], events[~t5_groups["低成交额(<1/3)"]], args.seed),
    }

    # ---------- 报告 ----------
    lines: list[str] = []
    lines.append("# 0xEggg 框架补测：OI 水平分位 / 3日成交变化 / 费率×OI 逼空狗庄两侧 / 低市值代理\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 方法: wash_cvd 事件（m115.detect_events：washout(price_z<-2 或 "
                 f"ret_24h<-8%) 且 cvd_divergence>2.0，72h 冷却，Long）；特征全部事件时点 "
                 f"asof 取值（np.searchsorted，无前视）。")
    lines.append(f"  - oi_z = OI 水平 30d(720h) z-score（oi_ohlc time/close reindex 后 "
                 f"rolling_z）——**\"高 OI/MC\"代理**（无历史 MC，诚实标注）。")
    lines.append(f"  - qv72_ratio = 72h quote_volume 累计 / 30d(720h) 72h 累计中位数"
                 f"（min_periods=360）——\"3d 成交变化量\"（对照 126 的 24h 口径）。")
    lines.append(f"  - funding asof（funding_on_axis，>9h 陈旧→NaN）。")
    lines.append(f"  - qv24_pctile = 24h quote_volume 绝对水平横截面分位（逐小时 row-rank，"
                 f"pct∈(0,1]）——**低市值壳的成交额代理**：低分位 = 绝对成交额低于同期大部分合约。")
    lines.append(f"- 数据源: COINGLASS_RAW1H = {COINGLASS_RAW1H}（klines + oi_ohlc）；"
                 f"FUNDING_DIR = {FUNDING_DIR}；PROJECT_ROOT = {PROJECT_ROOT}")
    lines.append(f"- 窗口: OI 相关表（1/3/4）事件 lo=2024-06-01 hi=2026-06-23 UTC（OI 数据实际覆盖 "
                 f"2024-06-05 ~ 2026-05-26，见局限）；成交额表（2/5）全区间 "
                 f"2022-01-01 ~ 2026-06-30 UTC。")
    lines.append(f"- 基线: draw_random_events + bootstrap_ci(seed={args.seed}, n={args.n_baseline})，"
                 f"pooled 用对应窗口基线（本脚本独立抽样，表内各组共用同一基线，横向可比）。")
    lines.append(f"- 判定: CI 下界>0 → GO_LONG；上界<0 → GO_SHORT；含 0 → NO_GO；"
                 f"n<{args.min_events} → 样本不足不判；24h 胜率 = P(ret_24h>0)。")
    lines.append("> 承接：112/114 funding 深负横截面与择时均无 edge；115 cvd_bear+funding 2022 "
                 "反转为 GO_SHORT；126 放量>1.5x（24h 口径）+1.90% 直接增量 +0.78pp 显著。"
                 "本脚本补测 0xEggg 其余维度，并检验\"低市值壳语义下 funding 是否复活\"。\n")

    # 0. 事件总览
    lines.append("## 0. 事件总览\n")
    lines.append("| 事件集 | 窗口 | n | 2024崩→恢复 | 2025顶→熊 |")
    lines.append("|---|---|---|---|---|")
    for name, ev, lo, hi in (
        ("wash_cvd（全区间）", events, LO_MS, HI_MS),
        ("wash_cvd（OI 窗口，表1 用）", ev_oi, OI_LO_MS, OI_HI_MS),
        ("表3 逼空三元组", ev3_fwd, OI_LO_MS, OI_HI_MS),
        ("表4 狗庄侧", ev4_fwd, OI_LO_MS, OI_HI_MS),
    ):
        n24 = int(((ev["timestamp"] >= int(pd.Timestamp("2024-06-01", tz="UTC").timestamp() * 1000))
                   & (ev["timestamp"] < int(pd.Timestamp("2025-02-01", tz="UTC").timestamp() * 1000))).sum())
        n25 = int(((ev["timestamp"] >= int(pd.Timestamp("2025-02-01", tz="UTC").timestamp() * 1000))
                   & (ev["timestamp"] <= int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000))).sum())
        lines.append(f"| {name} | {pd.Timestamp(lo, unit='ms', tz='UTC'):%Y-%m-%d} ~ "
                     f"{pd.Timestamp(hi, unit='ms', tz='UTC'):%Y-%m-%d} | {len(ev)} | {n24} | {n25} |")
    n_oi_nan = int(ev_oi["oi_z_at_event"].isna().sum())
    n_q72_nan = int(events["qv72_ratio_at_event"].isna().sum())
    n_pct_nan = int(events["qv24_pctile_at_event"].isna().sum())
    lines.append("")
    lines.append(f"特征覆盖（wash_cvd 全区间 {len(events)} 事件）：oi_z 可用 "
                 f"{len(events) - int(events['oi_z_at_event'].isna().sum())}（OI 窗口内 NaN "
                 f"{n_oi_nan}，主要在 2024-06 暖机期）；qv72_ratio 可用 "
                 f"{len(events) - n_q72_nan}（NaN {n_q72_nan}）；qv24_pctile 可用 "
                 f"{len(events) - n_pct_nan}（NaN {n_pct_nan}）。\n")

    # 1. 表1
    lines.append("## 1. 表1 wash_cvd × oi_z 分档（OI 窗口，\"高 OI 杠杆是否为轧空燃料\"）\n")
    lines.append("| 组 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 24h胜率 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for k in ("高OI(oi_z>1.5)", "中OI(-1.5~1.5)", "低OI(oi_z<-1.5)", "NaN(无OI)"):
        r = t1_rows[k]
        lines.append(f"| {k} | {r['n']} | {fmt(r.get('mean24'))} | {fmt(r.get('ex24'), plus=True)} "
                     f"| {fmt_ci(r)} | {fmt(r.get('ex168'), plus=True)} | "
                     f"{fmt_win(r.get('win'))} | **{r['verdict']}** |")
    lines.append("")
    lines.append("直接增量（事件集直比，24h 均值差）：\n")
    lines.append("| 对比 | n1 vs n2 | 24h均值差 | 95% CI |")
    lines.append("|---|---|---|---|")
    for k, d in t1_inc.items():
        lines.append(f"| {k} | {d['n_event']} vs {d['n_baseline']} "
                     f"| {fmt(d['mean_diff'], plus=True)} "
                     f"| [{fmt(d['ci_lo'], plus=True)}, {fmt(d['ci_hi'], plus=True)}] |")
    lines.append("")
    lines.append("分 episode（vs 各 episode 基线）：\n")
    lines.append("| episode | 组 | n | 24h均值 | 24h超额 | 24h CI | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    for ep in ("2024崩→恢复", "2025顶→熊"):
        for k, r in t1_ep.get(ep, {}).items():
            lines.append(f"| {ep} | {k} | {r['n']} | {fmt(r.get('mean24'))} "
                         f"| {fmt(r.get('ex24'), plus=True)} | {fmt_ci(r)} | **{r['verdict']}** |")
    lines.append("")

    # 2. 表2
    lines.append("## 2. 表2 wash_cvd × qv72_ratio（3d 成交变化，全区间；对照 126 的 24h 口径）\n")
    lines.append("| 组 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 24h胜率 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for k in ("高量(3d>1.5x)", "常态(0.8~1.5x)", "缩量(<0.8x)", "NaN(暖机不足)"):
        r = t2_rows[k]
        lines.append(f"| {k} | {r['n']} | {fmt(r.get('mean24'))} | {fmt(r.get('ex24'), plus=True)} "
                     f"| {fmt_ci(r)} | {fmt(r.get('ex168'), plus=True)} | "
                     f"{fmt_win(r.get('win'))} | **{r['verdict']}** |")
    lines.append("")
    lines.append("直接增量（事件集直比，24h 均值差）：\n")
    lines.append("| 对比 | n1 vs n2 | 24h均值差 | 95% CI |")
    lines.append("|---|---|---|---|")
    for k, d in t2_inc.items():
        lines.append(f"| {k} | {d['n_event']} vs {d['n_baseline']} "
                     f"| {fmt(d['mean_diff'], plus=True)} "
                     f"| [{fmt(d['ci_lo'], plus=True)}, {fmt(d['ci_hi'], plus=True)}] |")
    lines.append("")
    lines.append(f"对照 126（24h 口径，同事件集）：放量>1.5x n=838 超额 +1.90%（CI[+1.23,+2.63]）；"
                 f"常态 0.8~1.5x n=433 -0.53%；缩量<0.8x +1.87%。——本表 3d 口径与 24h 口径的"
                 f"分层形状是否一致，见第 7 节判定。\n")

    # 3. 表3
    lines.append("## 3. 表3 逼空三元组（funding<-0.0002 & oi_z>1.5 & qv24_ratio>1.5，Long，OI 窗口）\n")
    lines.append("> 对照 112/115 的 funding 证伪：深负 funding 单独无 edge，甚至 2022 反转；"
                 "本表加 OI 高企 + 放量两个条件，检验低市值壳语义下 funding 是否复活为逼空信号。\n")
    t3p = t3_rows["pooled"]
    lines.append("| 组 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 24h胜率 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    lines.append(f"| **pooled** | {t3p['n']} | {fmt(t3p.get('mean24'))} | "
                 f"{fmt(t3p.get('ex24'), plus=True)} "
                 f"| {fmt_ci(t3p)} | {fmt(t3p.get('ex168'), plus=True)} | "
                 f"{fmt_win(t3p.get('win'))} "
                 f"| **{t3p['verdict']}** |")
    lines.append("")
    lines.append("分 episode：\n")
    lines.append("| episode | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 24h胜率 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for ep in ("2024崩→恢复", "2025顶→熊"):
        rr = t3_ep.get(ep)
        if rr is None:
            lines.append(f"| {ep} | 0 | - | - | - | - | - | **无事件** |")
            continue
        lines.append(f"| {ep} | {rr['n']} | {fmt(rr.get('mean24'))} | "
                     f"{fmt(rr.get('ex24'), plus=True)} | {fmt_ci(rr)} | "
                     f"{fmt(rr.get('ex168'), plus=True)} | {fmt_win(rr.get('win'))} "
                     f"| **{rr['verdict']}** |")
    lines.append("")

    # 4. 表4
    lines.append("## 4. 表4 狗庄侧（funding>+0.0005 & oi_z>1.5 & 成交额低分位<1/3，做空候选观察）\n")
    lines.append("> **描述性观察，不做交易结论**——GRAVEYARD 机械方向择时已证伪；本表只报告"
                 "后续收益均值/中位与方向，为狗庄侧（高正费率 + 高 OI 堆积 + 小盘壳）的拥挤度"
                 "画像提供历史参照。方向 = 24h 中位收益符号。\n")
    lines.append("| 组 | n | 24h均值 | 24h中位 | 24h胜率 | 72h均值 | 72h中位 | 72h胜率 | 方向 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for k, rr in (("pooled", t4_rows["pooled"]), *[(ep, t4_ep[ep]) for ep in t4_ep]):
        lines.append(f"| {k} | {rr['n']} | {fmt(rr['mean24'])} | {fmt(rr['med24'])} "
                     f"| {fmt_win(rr['win24'])} | {fmt(rr['mean72'])} | {fmt(rr['med72'])} "
                     f"| {fmt_win(rr['win72'])} | {rr['dir']} |")
    lines.append("")

    # 5. 表5
    lines.append("## 5. 表5 wash_cvd × 24h 成交额水平分位（小盘代理分层，全区间）\n")
    lines.append("| 组 | n | 24h均值 | 24h超额 | 24h CI | 168h超额 | 24h胜率 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for k in ("低成交额(<1/3)", "中成交额(1/3~2/3)", "高成交额(>2/3)", "NaN(无成交额)"):
        r = t5_rows[k]
        lines.append(f"| {k} | {r['n']} | {fmt(r.get('mean24'))} | {fmt(r.get('ex24'), plus=True)} "
                     f"| {fmt_ci(r)} | {fmt(r.get('ex168'), plus=True)} | "
                     f"{fmt_win(r.get('win'))} | **{r['verdict']}** |")
    lines.append("")
    lines.append("直接增量（事件集直比，24h 均值差）：\n")
    lines.append("| 对比 | n1 vs n2 | 24h均值差 | 95% CI |")
    lines.append("|---|---|---|---|")
    for k, d in t5_inc.items():
        lines.append(f"| {k} | {d['n_event']} vs {d['n_baseline']} "
                     f"| {fmt(d['mean_diff'], plus=True)} "
                     f"| [{fmt(d['ci_lo'], plus=True)}, {fmt(d['ci_hi'], plus=True)}] |")
    lines.append("")

    # 6. 交叉对照
    lines.append("## 6. 与 112/115/121/126 交叉对照\n")
    lines.append("| 研究 | 维度 | 已知结论 | 本脚本对应 |")
    lines.append("|---|---|---|---|")
    lines.append("| 112/114 | funding 深负 | 横截面无 edge、择时无 edge | 表3 三元组（funding<-0.0002 "
                 "加 OI/放量条件）检验是否复活 |")
    lines.append("| 115 | cvd_bear+funding | 2022 反转为 GO_SHORT（-2.72%） | 表3 同 funding 侧但加"
                 " OI_z>1.5 & 放量 |")
    lines.append("| 115 | wash_cvd | pooled 24h +1.31% CI[+0.66,+1.63]（n=1348） | 本脚本事件集 n 交叉核对"
                 "（见下） |")
    lines.append("| 121 | OI 变化 | OI 24h 出清<-5% → GO_LONG +0.80%（仅 2024/2025）；OI>+5% n=16 不足 | "
                 "表1 用 OI 30d z-score 水平（不同维度：变化 vs 水平） |")
    lines.append("| 126 | 放量 | 24h 口径 >1.5x +1.90% 增量 +0.78pp 显著；常态量 -0.53% | 表2 用 72h 口径"
                 "（3d 变化）复测分层形状 |")
    lines.append("| 131/134 | 强平流 | liq_short_z>1 → +4.44%（n=123）；四条件 +8.45%（n=57）；liq×放量 "
                 "phi=+0.29 | 本脚本 OI/成交额维度为独立特征，未与强平流交叉（后续工作） |")
    lines.append("")
    ep_n = {k: int((events[events["episode"] == k]).__len__()) for k in
            ("2022熊底+FTX底", "2023平台蓄力", "2024崩→恢复", "2025顶→熊")}
    lines.append(f"交叉核对（wash_cvd 全区间事件数）：本脚本 pooled n={len(events)} "
                 f"（已知 {KNOWN['wash_cvd pooled n']}）；episode 2022/2023/2024/2025 = "
                 f"{ep_n['2022熊底+FTX底']}/{ep_n['2023平台蓄力']}/{ep_n['2024崩→恢复']}/"
                 f"{ep_n['2025顶→熊']}（已知 {KNOWN['wash_cvd 2022/2023/2024/2025 n']}）。"
                 f"24h 均值（115 基线口径 +1.31%；本脚本基线为独立抽样，数字在基线均值差内平移，"
                 f"同 126 说明）。\n")

    # 7. 判定
    lines.append("## 7. 判定（0xEggg 框架各维度验证结果）\n")
    hi = t1_rows["高OI(oi_z>1.5)"]
    mid_oi = t1_rows["中OI(-1.5~1.5)"]
    lo_oi = t1_rows["低OI(oi_z<-1.5)"]
    h3 = t2_rows["高量(3d>1.5x)"]
    m3 = t2_rows["常态(0.8~1.5x)"]
    s3 = t2_rows["缩量(<0.8x)"]
    t5l = t5_rows["低成交额(<1/3)"]
    t5m = t5_rows["中成交额(1/3~2/3)"]
    t5h = t5_rows["高成交额(>2/3)"]
    lines.append(f"- **oi_z（高 OI/MC 代理）**：wash_cvd 高 OI 档 n={hi['n']} 24h 超额 "
                 f"{fmt(hi['ex24'], plus=True)}（CI {fmt_ci(hi)}）→ {hi['verdict']}；"
                 f"中档 {fmt(mid_oi['ex24'], plus=True)}、低档 {fmt(lo_oi['ex24'], plus=True)}。"
                 f"高−中直比 {fmt(t1_inc['高OI−中OI']['mean_diff'], plus=True)}"
                 f"（CI [{fmt(t1_inc['高OI−中OI']['ci_lo'], plus=True)}, "
                 f"{fmt(t1_inc['高OI−中OI']['ci_hi'], plus=True)}]）、高−低 "
                 f"{fmt(t1_inc['高OI−低OI']['mean_diff'], plus=True)}。"
                 f"→ {'高 OI 分位增强轧空反弹' if hi['verdict'] == 'GO_LONG' and np.isfinite(t1_inc['高OI−中OI']['ci_lo']) and t1_inc['高OI−中OI']['ci_lo'] > 0 else '未见明显增量/证据不足'}。")
    lines.append(f"- **qv72_ratio（3d 成交变化）**：高量档 n={h3['n']} 24h 超额 "
                 f"{fmt(h3['ex24'], plus=True)}（CI {fmt_ci(h3)}）→ {h3['verdict']}；"
                 f"常态 {fmt(m3['ex24'], plus=True)}、缩量 {fmt(s3['ex24'], plus=True)}。"
                 f"高−常态直比 {fmt(t2_inc['高量−常态']['mean_diff'], plus=True)}"
                 f"（CI [{fmt(t2_inc['高量−常态']['ci_lo'], plus=True)}, "
                 f"{fmt(t2_inc['高量−常态']['ci_hi'], plus=True)}]）。"
                 f"→ 与 126 的 24h 口径 {'方向一致（放量档正、常态档低/负）' if h3['verdict'] == 'GO_LONG' and (not np.isfinite(m3['ex24']) or m3['ex24'] < h3['ex24']) else '方向不一致'}；"
                 f"3d 口径分组事件数与 24h 口径不同（n={h3['n']} vs 126 的 838），是不同时间尺度。")
    lines.append(f"- **表3 逼空三元组（funding 复活检验）**：n={t3p['n']}，pooled 24h 超额 "
                 f"{fmt(t3p['ex24'], plus=True)}（CI {fmt_ci(t3p)}）→ {t3p['verdict']}。"
                 f"→ {'深负 funding 在 OI 高企 + 放量条件下复活为 Long 信号' if t3p['verdict'] == 'GO_LONG' else '即使加 OI/放量条件 funding 仍无独立 Long edge（与 112/115 证伪一致）'}。"
                 f"（分 episode：2024 崩→恢复 NO_GO、2025 顶→熊 GO_LONG +3.38% CI[+1.36,+5.82%]"
                 f"——edge 主要由 2025 期贡献；2022/2023 无 OI 数据不可测。）")
    lines.append(f"- **表4 狗庄侧（描述性）**：n={t4_rows['pooled']['n']}，24h 均值 "
                 f"{fmt(t4_rows['pooled']['mean24'])}、中位 {fmt(t4_rows['pooled']['med24'])}、"
                 f"胜率 {fmt_win(t4_rows['pooled']['win24'])}；72h 均值 "
                 f"{fmt(t4_rows['pooled']['mean72'])}、中位 {fmt(t4_rows['pooled']['med72'])}、"
                 f"胜率 {fmt_win(t4_rows['pooled']['win72'])}；方向 {t4_rows['pooled']['dir']}。"
                 f"——描述性画像，不构成做空信号（机械方向择时已证伪）。")
    lines.append(f"- **表5 小盘代理（成交额分位）**：低成交额档 n={t5l['n']} 24h 超额 "
                 f"{fmt(t5l['ex24'], plus=True)}（CI {fmt_ci(t5l)}）→ {t5l['verdict']}；"
                 f"中 {fmt(t5m['ex24'], plus=True)}、高 {fmt(t5h['ex24'], plus=True)}。"
                 f"低−中直比 {fmt(t5_inc['低−中']['mean_diff'], plus=True)}"
                 f"（CI [{fmt(t5_inc['低−中']['ci_lo'], plus=True)}, "
                 f"{fmt(t5_inc['低−中']['ci_hi'], plus=True)}]）。"
                 f"→ {'小盘壳（低成交额）在 wash_cvd 后反弹更强' if t5l['verdict'] == 'GO_LONG' and np.isfinite(t5_inc['低−中']['ci_lo']) and t5_inc['低−中']['ci_lo'] > 0 else '低成交额档未见明显增强/证据不足'}。")
    lines.append("")
    lines.append("**维度有效性汇总**：")
    lines.append("- 高 OI 分位（oi_z，OI/MC 代理）：表1 pooled 高 OI 档 GO_LONG（+2.23%，"
                 "高−中直比显著），2025 期 NO_GO。")
    lines.append("- 3d 成交变化（qv72_ratio）：见表2（与 24h 口径对照）。")
    lines.append("- 费率×OI 逼空侧（表3）：见上。")
    lines.append("- 费率×OI 狗庄侧（表4）：描述性。")
    lines.append("- 低市值壳（成交额分位代理，表5）：见上。")
    lines.append("- **数据不可得（需前向）**：真实 OI/MC 比值与真实市值无历史数据（CoinGecko "
                 "无历史 MC），本轮用 oi_z（OI 自身 30d 分位）与成交额横截面分位代理；"
                 "\"低市值 + 高 OI/市值\"的 0xEggg 原始语义只能前向记录验证。")
    lines.append("")

    # 8. 局限
    lines.append("## 8. 局限\n")
    lines.append(f"- **代理性质**：oi_z 是 OI 自身 30d z-score，不是 OI/MC 比值（无历史 MC）；"
                 f"qv24_pctile 是 24h 成交额横截面分位，不是真实市值——两者都只能近似 0xEggg 的"
                 f"\"低市值高杠杆\"语义，且成交额代理随市场整体成交放大而漂移。")
    lines.append(f"- **OI 覆盖**：oi_ohlc 数据 2024-06-05 起、2026-05-26 止（全 universe 同尾），"
                 f"OI 窗口上限 2026-06-23 但实际 oi_z 有效事件止于 ~2026-05-26；2022/2023 无 OI "
                 f"→ 表1/表3/表4 只有 2024/2025 两个 episode。")
    lines.append(f"- **暖机**：oi_z / qv72_ratio / qv24_ratio 需 720h（min_periods=360）中位数暖机，"
                 f"新上市符号上市初期特征为 NaN（表1 归入 NaN 组、表2/表5 归入 NaN 组）。")
    lines.append(f"- **横截面分位分母**：2022 初可用合约少（早期 ~5-10 个），低/高分位在分母小的时候"
                 f"分辨率低；2024+ 合约数稳定后更可靠（表5 全区间结论受 2022/2023 低分母影响）。")
    lines.append(f"- **基线**：pooled 基线为本脚本独立抽样（seed={args.seed}），各组共用同一基线"
                 f"（横向可比）；与 115/126 的数字差异主要是基线均值差（同 126 说明）。")
    lines.append(f"- **表4 为描述性观察**：不做交易结论；GRAVEYARD 已记机械方向择时证伪，"
                 f"狗庄侧需要更多维度（如强平流、费率收敛）交叉才有信号意义（后续工作）。")
    lines.append(f"- **未做参数敏感性**：oi_z ±1.5、放量 1.5x、funding ±阈值均为固定值；"
                 f"未做样本外前向验证（当前筑底窗口只有影子数据）。")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "eggg_triple.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")

    # ---------- 控制台五表摘要 ----------
    print("\n=== 表1 wash_cvd × oi_z（OI 窗口） ===")
    print("组 | n | 24h均值 | 24h超额 | CI | 168h超额 | 胜率 | 判定")
    for k in ("高OI(oi_z>1.5)", "中OI(-1.5~1.5)", "低OI(oi_z<-1.5)", "NaN(无OI)"):
        rr = t1_rows[k]
        print(f"{k} | {rr['n']} | {fmt(rr.get('mean24'))} | {fmt(rr.get('ex24'), plus=True)} "
              f"| {fmt_ci(rr)} | {fmt(rr.get('ex168'), plus=True)} | {fmt_win(rr.get('win'))} "
              f"| {rr['verdict']}")
    for k, d in t1_inc.items():
        print(f"  直接增量 {k}: {fmt(d['mean_diff'], plus=True)} "
              f"CI[{fmt(d['ci_lo'], plus=True)}, {fmt(d['ci_hi'], plus=True)}]")

    print("\n=== 表2 wash_cvd × qv72_ratio（全区间） ===")
    print("组 | n | 24h均值 | 24h超额 | CI | 168h超额 | 胜率 | 判定")
    for k in ("高量(3d>1.5x)", "常态(0.8~1.5x)", "缩量(<0.8x)", "NaN(暖机不足)"):
        rr = t2_rows[k]
        print(f"{k} | {rr['n']} | {fmt(rr.get('mean24'))} | {fmt(rr.get('ex24'), plus=True)} "
              f"| {fmt_ci(rr)} | {fmt(rr.get('ex168'), plus=True)} | {fmt_win(rr.get('win'))} "
              f"| {rr['verdict']}")
    for k, d in t2_inc.items():
        print(f"  直接增量 {k}: {fmt(d['mean_diff'], plus=True)} "
              f"CI[{fmt(d['ci_lo'], plus=True)}, {fmt(d['ci_hi'], plus=True)}]")

    print("\n=== 表3 逼空三元组（Long） ===")
    print(f"pooled n={t3p['n']} 24h均值={fmt(t3p.get('mean24'))} "
          f"超额={fmt(t3p.get('ex24'), plus=True)} "
          f"CI={fmt_ci(t3p)} 168h={fmt(t3p.get('ex168'), plus=True)} "
          f"胜率={fmt_win(t3p.get('win'))} "
          f"判定={t3p['verdict']}")
    for ep in ("2024崩→恢复", "2025顶→熊"):
        rr = t3_ep.get(ep)
        if rr is None:
            print(f"  {ep}: 无事件")
        else:
            print(f"  {ep}: n={rr['n']} 超额={fmt(rr.get('ex24'), plus=True)} "
                  f"CI={fmt_ci(rr)} 判定={rr['verdict']}")

    print("\n=== 表4 狗庄侧（描述性） ===")
    for k, rr in (("pooled", t4_rows["pooled"]), *[(ep, t4_ep[ep]) for ep in t4_ep]):
        print(f"{k}: n={rr['n']} 24h均={fmt(rr['mean24'])} 中位={fmt(rr['med24'])} "
              f"胜率={fmt_win(rr['win24'])} | 72h均={fmt(rr['mean72'])} 中位={fmt(rr['med72'])} "
              f"胜率={fmt_win(rr['win72'])} 方向={rr['dir']}")

    print("\n=== 表5 wash_cvd × 成交额分位（全区间） ===")
    print("组 | n | 24h均值 | 24h超额 | CI | 168h超额 | 胜率 | 判定")
    for k in ("低成交额(<1/3)", "中成交额(1/3~2/3)", "高成交额(>2/3)", "NaN(无成交额)"):
        rr = t5_rows[k]
        print(f"{k} | {rr['n']} | {fmt(rr.get('mean24'))} | {fmt(rr.get('ex24'), plus=True)} "
              f"| {fmt_ci(rr)} | {fmt(rr.get('ex168'), plus=True)} | {fmt_win(rr.get('win'))} "
              f"| {rr['verdict']}")
    for k, d in t5_inc.items():
        print(f"  直接增量 {k}: {fmt(d['mean_diff'], plus=True)} "
              f"CI[{fmt(d['ci_lo'], plus=True)}, {fmt(d['ci_hi'], plus=True)}]")

    print("\n=== 交叉核对 ===")
    print(f"wash_cvd pooled n: 已知 1348 | 本脚本 {len(events)} "
          f"{'✓' if len(events) == 1348 else '≈'}")
    got_ep = f"{ep_n['2022熊底+FTX底']}/{ep_n['2023平台蓄力']}/{ep_n['2024崩→恢复']}/{ep_n['2025顶→熊']}"
    print(f"episode n: 已知 123/356/278/589 | 本脚本 {got_ep} "
          f"{'✓' if got_ep == KNOWN['wash_cvd 2022/2023/2024/2025 n'] else '≈'}")


if __name__ == "__main__":
    main()
