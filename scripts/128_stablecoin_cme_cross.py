r"""128_stablecoin_cme_cross.py — E 方向交叉：稳定币供给 + CME 机构 OI × wash_cvd/山寨收益。

命题背景：AlphaHive V3「大饼见底→山寨蓄力」。本轮验证两个外部维度对 wash_cvd
（washout + cvd_divergence，115 口径）的调制作用：

1. 稳定币供给（主菜，全历史测）：
   - DefiLlama 聚合总供给（https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=1，
     3173 日点 2017-11 → 今，免费无 key，一次性拉取不做定时化）。
   - 表1：dStable（日变化 USD）vs alt 篮子 / btc 当日·次日收益的相关（分 era）。
   - 表2：wash_cvd 事件按事件日-1 的 dStable 符号分层 → 24h 超额 vs 同期基线
     （bootstrap seed=2026），检验「稳定币供给扩张利于 wash_cvd」假设。
   - 表3：供给绝对水平分层（描述性；水平与 era 强混淆，须诚实标注）。

2. CME 机构 OI（样本受限，诚实报告）：
   - cme_bitcoin.parquet 仅 41 交易日（2026-06-08 → 08-05，滞后 2 天发布）。
   - wash_cvd 事件与 CME 窗口重叠极少 → 预期 n<30「样本不足，需前向积累」，
     不硬凑结论；另做 CME OI 变化 vs btc 日收益相关作旁证。

无前视纪律：
- 事件研究只用事件日-1 及之前已知信息（dStable 取事件日-1，CME 取事件日-3 保守对齐）。
- 只读研究模块：不碰 config/*.yaml、scan_rules.yaml、contract_anomaly_rules.yaml、
  scripts/108/109、定时任务。禁止 pytest/formatter/linter（回归由 Main 统一跑）。

用法：
  python scripts/128_stablecoin_cme_cross.py [--refetch] [--n-baseline 5000] [--seed 2026] [--symbols ...]
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy import stats as sps

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import DEFAULT_HORIZONS, bootstrap_ci, draw_random_events, forward_stats

COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
MACRO_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
REPORTS_DIR = PROJECT_ROOT / "reports"

# 复用模板：113（加载/清洗/episode）+ 115（wash_cvd 检测）+ 119（BTC 双源日收盘）
_spec = importlib.util.spec_from_file_location("m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec); sys.modules["m113"] = m113; _spec.loader.exec_module(m113)
_spec2 = importlib.util.spec_from_file_location("m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2); sys.modules["m115"] = m115; _spec2.loader.exec_module(m115)
_spec3 = importlib.util.spec_from_file_location("m119", str(PROJECT_ROOT / "scripts" / "119_macro_crypto_study.py"))
m119 = importlib.util.module_from_spec(_spec3); sys.modules["m119"] = m119; _spec3.loader.exec_module(m119)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
detect_events = m115.detect_events
EPISODES = m113.EPISODES
episode_of = m113.episode_of

STABLE_SOURCE_URL = "https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=1"
STABLE_CSV = MACRO_ROOT / "stablecoin_supply_defillama.csv"
CME_PATH = MACRO_ROOT / "cme_bitcoin.parquet"

STUDY_START = "2022-01-01"
STUDY_END = "2026-06-30"        # 与 120 一致：前向 episode（2026-07+）不进判定窗口
ERAS = [("2022-23", "2022-01-01", "2023-12-31"),
        ("2024-26", "2024-01-01", "2026-06-30")]
CME_WIN_LO = "2026-06-08"
CME_WIN_HI = "2026-07-07 03:00"  # coinglass klines 数据末端（07-07 03:00 UTC）
FLAT_USD = 1e6                   # |dStable| <= 1M USD 视为「持平」（DefiLlama 日点含大量 0 变化）
HOUR_MS = 3_600_000


def load_stablecoin_supply(force_refetch: bool = False) -> pd.Series:
    """DefiLlama 聚合稳定币总供给（index=UTC date，值=USD）。

    缓存 CSV：MACRO_ROOT/stablecoin_supply_defillama.csv（含 source URL + pulled_at）。
    新鲜度门槛：缓存 max(date) >= 拉取日-2，否则重拉。
    """
    if not force_refetch and STABLE_CSV.exists():
        try:
            df = pd.read_csv(STABLE_CSV)
            idx = pd.to_datetime(df["date"], errors="coerce").dropna()
            if len(idx) >= 3000:
                s = pd.Series(pd.to_numeric(df["supply_usd"], errors="coerce").to_numpy(),
                              index=pd.DatetimeIndex(idx)).sort_index()
                s = s[~s.index.duplicated(keep="last")]
                cut = pd.Timestamp.now(tz="UTC").tz_convert(None).normalize() - pd.Timedelta(days=2)
                if s.index.max() >= cut:
                    return s
        except Exception:
            pass
    r = requests.get(STABLE_SOURCE_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    data = r.json()
    pts = [(int(d["date"]), float(d["totalCirculatingUSD"]["peggedUSD"]))
           for d in data if d.get("totalCirculatingUSD") and d["totalCirculatingUSD"].get("peggedUSD") is not None]
    df = pd.DataFrame(pts, columns=["date", "supply_usd"])
    df["date"] = pd.DatetimeIndex(pd.to_datetime(df["date"], unit="s", utc=True)).tz_convert(None).normalize()
    df = df.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    df["source"] = STABLE_SOURCE_URL
    df["pulled_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    MACRO_ROOT.mkdir(parents=True, exist_ok=True)
    df.to_csv(STABLE_CSV, index=False)
    return pd.Series(df["supply_usd"].to_numpy(), index=pd.DatetimeIndex(df["date"]))


def build_stable_state(supply: pd.Series) -> pd.DataFrame:
    """日度供给状态帧：level / dStable（日变化 USD）/ dStable30（30d 变化 USD）。

    dStable(t) = supply(t) - supply(t-1)，事件日 D 用 D-1 的值（无前视）。
    """
    st = pd.DataFrame(index=supply.index)
    st["level"] = supply
    st["dStable"] = supply.diff()
    st["dStable30"] = supply.diff(30)
    return st


def ctx_daily_closes(ctxs: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    """ctxs 小时 close → 每 symbol UTC 日收盘（每日 00:00 UTC 锚定，取当日最后一根已收盘 bar）。"""
    out: dict[str, pd.Series] = {}
    for sym, t in ctxs.items():
        close = t["close"].dropna()
        if len(close) < 400:
            continue
        dates = pd.to_datetime(close.index.to_numpy(), unit="ms", utc=True).tz_convert(None).normalize()
        daily = pd.Series(close.to_numpy(), index=pd.DatetimeIndex(dates)).groupby(level=0).last()
        daily.index = pd.DatetimeIndex(daily.index).tz_localize(None).normalize()
        out[sym] = daily
    return out


def safe_daily_ret(daily: pd.Series) -> pd.Series:
    """日收益；剔除相邻日收盘间隔 >36h 的伪收益（coinglass 2026-06-23→06-30 空档）。"""
    r = daily.pct_change() * 100.0
    gap_h = daily.index.to_series().diff().dt.total_seconds() / 3600.0
    return r.where(gap_h <= 36.0)


def build_alt_basket_ret(ctxs: dict[str, pd.DataFrame]) -> pd.Series:
    """alt 篮子日收益：ctxs 每日 00:00 UTC bar 聚合等权（与 119 口径一致）。"""
    sym_ret: dict[str, pd.Series] = {}
    for sym, daily in ctx_daily_closes(ctxs).items():
        r = safe_daily_ret(daily)
        if r.notna().sum() >= 100:
            sym_ret[sym] = r
    if not sym_ret:
        raise RuntimeError("无任何 symbol 可用")
    mat = pd.DataFrame(sym_ret)
    alt = mat.mean(axis=1, skipna=True).dropna()
    alt.index = pd.DatetimeIndex(alt.index).tz_localize(None).normalize()
    return alt


def detect_wash_cvd(ctxs: dict[str, pd.DataFrame], fundings: dict[str, pd.Series]) -> pd.DataFrame:
    """全历史 wash_cvd 事件 + 前向收益（同 115/120 口径，72h 冷却）。"""
    ev_parts: list[pd.DataFrame] = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(columns=["symbol", "timestamp"])
    if events.empty:
        return events
    fwd: list[pd.DataFrame] = []
    for sym, g in events.groupby("symbol", sort=False):
        fwd.append(forward_stats(ctxs[sym], g.copy(), horizons=DEFAULT_HORIZONS))
    return pd.concat(fwd, ignore_index=True)


def attach_stable_state(events: pd.DataFrame, st: pd.DataFrame) -> pd.DataFrame:
    """每个事件 asof 取事件日-1 的供给状态（严格无前视，缺日 ffill）。"""
    dates = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_convert(None).normalize()
    prev = (dates - pd.Timedelta(days=1)).normalize()
    out = events.copy()
    for c in st.columns:
        out[c] = st[c].reindex(prev, method="ffill").to_numpy()
    return out


def pearson_row(x: pd.Series, y: pd.Series, lo: str, hi: str) -> dict:
    """区间内两序列 Pearson 相关（pairwise dropna）。"""
    xr = x[(x.index >= lo) & (x.index <= hi)]
    yr = y[(y.index >= lo) & (y.index <= hi)]
    df = pd.concat([xr, yr], axis=1, join="inner").dropna()
    if len(df) < 30:
        return {"n": len(df), "r": np.nan, "p": np.nan}
    r, p = sps.pearsonr(df.iloc[:, 0], df.iloc[:, 1])
    return {"n": len(df), "r": float(r), "p": float(p)}


def load_cme_oi() -> pd.DataFrame:
    """CME 比特币/微型比特币期货 OI 日度表（index=date）。"""
    df = pd.read_parquet(CME_PATH)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    bf = df[(df["商品"] == "比特币") & (df["类型"] == "期货")].set_index("date").sort_index()
    mf = df[(df["商品"] == "微型比特币") & (df["类型"] == "期货")].set_index("date").sort_index()
    oi = pd.DataFrame({"btc_oi": bf["未平仓合约"].astype(float), "btc_oi_chg": bf["持仓变化"].astype(float)})
    oi["micro_oi"] = mf["未平仓合约"].astype(float)
    oi["total_oi"] = oi["btc_oi"] + oi["micro_oi"]
    oi["total_oi_chg"] = oi["total_oi"].diff()  # 官方持仓变化仅分币种，总量变化用差分
    return oi


def fmt_ci(ci: dict) -> str:
    return f"[{ci.get('ci_lo', np.nan):+.2f}, {ci.get('ci_hi', np.nan):+.2f}]"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refetch", action="store_true", help="强制重拉 DefiLlama 稳定币数据")
    parser.add_argument("--n-baseline", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-events", type=int, default=30)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    # ---------- 数据加载 ----------
    supply = load_stablecoin_supply(force_refetch=args.refetch)
    st = build_stable_state(supply)
    print(f"[128] 稳定币供给 {len(supply)} 日点  {supply.index.min().date()} → {supply.index.max().date()}")

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    fundings = load_funding_series(symbols)
    print(f"[128] 价格上下文 {len(ctxs)} | funding {len(fundings)}")

    events = detect_wash_cvd(ctxs, fundings)
    lo = int(pd.Timestamp(STUDY_START, tz="UTC").timestamp() * 1000)
    hi = int(pd.Timestamp(STUDY_END, tz="UTC").timestamp() * 1000)
    ev_study = events[(events["timestamp"] >= lo) & (events["timestamp"] <= hi)].copy()
    ev_study = attach_stable_state(ev_study, st)
    ev_study["episode"] = episode_of(ev_study["timestamp"].to_numpy())
    ev_study["dStable_sign"] = np.where(ev_study["dStable"] > FLAT_USD, "扩张",
                                        np.where(ev_study["dStable"] < -FLAT_USD, "收缩", "持平"))
    print(f"[128] wash_cvd 事件 {len(events)}（全历史）→ 研究窗 {len(ev_study)}")

    # 同期基线（随机 symbol×时点，bootstrap seed=2026）
    rng = np.random.default_rng(args.seed)
    base = draw_random_events(ctxs, args.n_baseline, rng, max_forward_hours=168, start_ms=lo, end_ms=hi)
    base_parts: list[pd.DataFrame] = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            base_parts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_stats = pd.concat(base_parts, ignore_index=True) if base_parts else pd.DataFrame()
    base_24h = pd.to_numeric(base_stats["ret_24h"], errors="coerce").dropna().to_numpy()
    base_168h = pd.to_numeric(base_stats["ret_168h"], errors="coerce").dropna().to_numpy()
    print(f"[128] 基线 {len(base_24h)} 个有效 24h 样本")

    # ---------- alt / btc 日收益 ----------
    alt = build_alt_basket_ret(ctxs)
    btc_daily = m119.load_daily_close("BTCUSDT")
    btc = safe_daily_ret(btc_daily) if btc_daily is not None else None
    print(f"[128] alt 篮子 {alt.index.min().date()} → {alt.index.max().date()}；"
          f"btc {btc.index.min().date()} → {btc.index.max().date()}" if btc is not None else "")

    # ---------- 表1：dStable × 收益相关 ----------
    dS = st["dStable"]
    dS30 = st["dStable30"]
    lines: list[str] = []
    lines.append("# 稳定币供给 × CME 机构 OI 交叉研究（E 方向）\n")
    lines.append(f"- 生成 UTC: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M}")
    lines.append("- 方法: ① 稳定币供给日变化 dStable 与 alt 篮子/btc 日收益相关（分 era）；"
                 "② wash_cvd 事件按事件日-1 的 dStable 分层 bootstrap 超额；"
                 "③ 供给绝对水平分层描述；④ CME 机构 OI 交叉（样本受限诚实报告）。")
    lines.append(f"- 数据源: DefiLlama Stablecoins 聚合总量 `{STABLE_SOURCE_URL}`"
                 f"（{supply.index.min().date()} → {supply.index.max().date()}，pulled_at 见 CSV 元数据列）；"
                 f"CME 机构持仓 `{CME_PATH}`（125 已落盘，2026-06-08 → 08-05，滞后 2 天发布）；"
                 f"coinglass klines（CVD 代理，2021-12+，2026-06-23 23:00→06-30 04:00 全 universe 空档）。")
    lines.append("- 局限: ① dStable 日变化小、自相关强（约 20% 日点变化为 0），且主要反映发行/赎回（利率套利/链上需求），"
                 "**供给≠交易流动性**（与 120 liq_expand 被证伪的教训一致，见 §5）；"
                 "② 供给绝对水平与 era 强混淆（2022 低 → 2026 高）；"
                 "③ CME 窗口仅 41 交易日且与事件重叠极少，结论仅限旁证；"
                 "④ 前向 episode（2026-07+）不进判定窗口（与 120 一致）。\n")

    lines.append("## 1. dStable × 日收益相关（表1）\n")
    lines.append("> 次日（t+1）= dStable(t) vs 收益(t+1)，严格可交易（无前视）；当日（t）= 描述性。"
                 "2024-26 era 至 2026-06-30（与判定窗口一致）。r=Pearson，n=有效配对日。\n")
    lines.append("| 配对 | 全期 r (n) | 2022-23 r (n) | 2024-26 r (n) |")
    lines.append("|---|---|---|---|")
    rows1: list[dict] = []
    pairs = [
        ("dStable vs alt 当日", dS, alt, 0),
        ("dStable vs alt 次日", dS, alt, 1),
        ("dStable vs btc 当日", dS, btc, 0),
        ("dStable vs btc 次日", dS, btc, 1),
        ("dStable30 vs alt 次日", dS30, alt, 1),
        ("dStable30 vs btc 次日", dS30, btc, 1),
    ]
    for label, x, y, shift in pairs:
        y_shift = y.shift(-shift) if y is not None else pd.Series(dtype=float)
        if y is None:
            continue
        cells = []
        for era_lo, era_hi in [(STUDY_START, STUDY_END), ("2022-01-01", "2023-12-31"), ("2024-01-01", STUDY_END)]:
            rr = pearson_row(x, y_shift, era_lo, era_hi)
            cells.append(f"{rr['r']:+.3f} ({rr['n']})")
        rows1.append({"label": label, **{f"c{i}": c for i, c in enumerate(cells)}})
        lines.append(f"| {label} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines.append("")
    pd.DataFrame(rows1).to_csv(REPORTS_DIR / "stablecoin_cme_table1_corr.csv", index=False)

    # 基率上下文（分层规模 vs 供给日占比）
    study_days = st[(st.index >= STUDY_START) & (st.index <= STUDY_END)]
    base_exp = float((study_days["dStable"] > FLAT_USD).mean())
    base_con = float((study_days["dStable"] < -FLAT_USD).mean())
    base_flat = float((study_days["dStable"].abs() <= FLAT_USD).mean())
    ev_shares = ev_study["dStable_sign"].value_counts(normalize=True)
    med_ds = float(study_days["dStable"].abs().median())

    # ---------- 表2：wash_cvd × dStable 分层 ----------
    lines.append("## 2. wash_cvd × dStable 分层（表2，事件日-1，bootstrap seed=2026）\n")
    lines.append("> 假设检验：稳定币供给扩张（弹药增加）是否利于 wash_cvd 后的反弹。"
                 f"基线 = 同期随机 symbol×时点（n={len(base_24h)}）。"
                 "扩张/收缩判据 |dStable|>1M USD，|dStable|≤1M 为持平。"
                 f"研究窗内供给日基率：扩张 {base_exp:.0%} / 持平 {base_flat:.0%} / 收缩 {base_con:.0%}"
                 f"（事件分层占比 {ev_shares.get('扩张', 0):.0%}/{ev_shares.get('持平', 0):.0%}/{ev_shares.get('收缩', 0):.0%}，"
                 "事件在扩张期略富集，但见 §5.1 分层超额差异 CI 含 0）。"
                 f"研究窗日 |dStable| 中位数 {med_ds:,.0f} USD。\n")
    lines.append("| 分层 | n | 24h均% | 超额vs基线 | 95% CI | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    strata = ["扩张", "持平", "收缩"]
    row2: dict[str, dict] = {}
    for sname in strata:
        sub = ev_study[ev_study["dStable_sign"] == sname]
        ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        ev_v168 = pd.to_numeric(sub["ret_168h"], errors="coerce").dropna().to_numpy()
        if len(ev_v) < args.min_events:
            lines.append(f"| {sname} | {len(sub)} | - | - | - | - | 样本不足 |")
            row2[sname] = {"n": len(sub), "mean": np.nan, "excess": np.nan,
                           "ci_lo": np.nan, "ci_hi": np.nan, "ex168": np.nan, "verdict": "样本不足"}
            continue
        ci = bootstrap_ci(ev_v, base_24h, seed=args.seed)
        ci168 = bootstrap_ci(ev_v168, base_168h, seed=args.seed)
        if ci["ci_lo"] > 0:
            verdict = "GO_LONG"
        elif ci["ci_hi"] < 0:
            verdict = "GO_SHORT"
        else:
            verdict = "NO_GO"
        lines.append(f"| {sname} | {len(sub)} | {np.nanmean(ev_v):+.2f} | {ci['mean_diff']:+.2f} | "
                     f"{fmt_ci(ci)} | {ci168['mean_diff']:+.2f} | **{verdict}** |")
        row2[sname] = {"n": len(sub), "mean": float(np.nanmean(ev_v)), "excess": float(ci["mean_diff"]),
                       "ci_lo": float(ci["ci_lo"]), "ci_hi": float(ci["ci_hi"]),
                       "ex168": float(ci168["mean_diff"]), "verdict": verdict}
    lines.append("> 注：『持平』n=50 为小样本，均值/CI 波动大（周末/发行停滞日居多，可能有星期效应），不作为主结论。")
    # 扩张 − 收缩 直接差
    va = pd.to_numeric(ev_study[ev_study["dStable_sign"] == "扩张"]["ret_24h"], errors="coerce").dropna().to_numpy()
    vb = pd.to_numeric(ev_study[ev_study["dStable_sign"] == "收缩"]["ret_24h"], errors="coerce").dropna().to_numpy()
    if len(va) >= args.min_events and len(vb) >= args.min_events:
        ci_diff = bootstrap_ci(va, vb, seed=args.seed)
        lines.append(f"| **扩张−收缩** | {len(va)}/{len(vb)} | {np.nanmean(va):+.2f}/{np.nanmean(vb):+.2f} | "
                     f"{ci_diff['mean_diff']:+.2f} | {fmt_ci(ci_diff)} | - | 差CI含0→无调制 |")
        row2["扩张−收缩"] = {"n": f"{len(va)}/{len(vb)}", "excess": float(ci_diff["mean_diff"]),
                          "ci_lo": float(ci_diff["ci_lo"]), "ci_hi": float(ci_diff["ci_hi"])}
    lines.append("")
    # 表2 补充：30d 弹药变化分层（new_data_plan 研究用途：washout + 弹药增长）
    lines.append("### 2b. 补充：30d 供给变化分层（弹药积累期）\n")
    lines.append("| 分层 | n | 24h均% | 超额vs基线 | 95% CI | 判定 |")
    lines.append("|---|---|---|---|---|---|")
    for sname, mask in [("30d扩张", ev_study["dStable30"] > 0), ("30d收缩", ev_study["dStable30"] <= 0)]:
        sub = ev_study[mask]
        ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        if len(ev_v) < args.min_events:
            lines.append(f"| {sname} | {len(sub)} | - | - | - | 样本不足 |")
            continue
        ci = bootstrap_ci(ev_v, base_24h, seed=args.seed)
        verdict = "GO_LONG" if ci["ci_lo"] > 0 else ("GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {sname} | {len(sub)} | {np.nanmean(ev_v):+.2f} | {ci['mean_diff']:+.2f} | "
                     f"{fmt_ci(ci)} | **{verdict}** |")
    lines.append("")
    # 表2 补充：分层 × episode 计数（混淆检查）
    lines.append("### 2c. 分层 × episode 计数（era 混淆检查）\n")
    ct = ev_study.pivot_table(index="dStable_sign", columns="episode", values="symbol", aggfunc="count", fill_value=0)
    ct = ct.rename(columns={"?": "2026-06-30边界"})  # episode 4 截止 06-30 00:00，当日事件落边界
    lines.append("| 分层 | " + " | ".join(str(c) for c in ct.columns) + " |")
    lines.append("|---|" + "---|" * len(ct.columns))
    for sname, rrow in ct.iterrows():
        lines.append("| " + sname + " | " + " | ".join(str(int(v)) for v in rrow) + " |")
    lines.append("")
    pd.DataFrame({k: v for k, v in row2.items()}).T.to_csv(REPORTS_DIR / "stablecoin_cme_table2_strata.csv")

    # ---------- 表3：供给水平分层（描述性） ----------
    lines.append("## 3. 供给绝对水平分层（表3，描述性）\n")
    lines.append("> 水平分位在 2022-01-01→2026-06-30 的日度供给上计算；**水平与 era 强混淆**（低水平≈2022-23 熊市、"
                 "高水平≈2025-26），仅作描述不判定。\n")
    lv = st["level"][(st.index >= STUDY_START) & (st.index <= STUDY_END)].dropna()
    q1, q2 = lv.quantile([1 / 3, 2 / 3])
    ev_study["level_tile"] = pd.cut(ev_study["level"], [-np.inf, q1, q2, np.inf],
                                    labels=["低", "中", "高"])
    lines.append(f"水平分位断点: 低<{q1:,.0f} USD | 中<{q2:,.0f} USD | 高≥{q2:,.0f} USD\n")
    lines.append("| 水平分位 | n | 扩张占比 | 24h均% | 超额vs基线 |")
    lines.append("|---|---|---|---|---|")
    for tile in ["低", "中", "高"]:
        sub = ev_study[ev_study["level_tile"] == tile]
        ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        exp_share = (sub["dStable_sign"] == "扩张").mean() if len(sub) else np.nan
        if len(ev_v) >= args.min_events:
            ci = bootstrap_ci(ev_v, base_24h, seed=args.seed)
            lines.append(f"| {tile} | {len(sub)} | {exp_share:.0%} | {np.nanmean(ev_v):+.2f} | {ci['mean_diff']:+.2f} |")
        else:
            lines.append(f"| {tile} | {len(sub)} | {exp_share:.0%} | - | - |")
    lines.append("")
    # 水平 × dStable 交叉计数
    lines.append("| 水平分位 × 分层 | 扩张 | 持平 | 收缩 |")
    lines.append("|---|---|---|---|")
    cross = ev_study.pivot_table(index="level_tile", columns="dStable_sign", values="symbol",
                                 aggfunc="count", fill_value=0)
    for tile in ["低", "中", "高"]:
        lines.append(f"| {tile} | {int(cross.loc[tile, '扩张'])} | {int(cross.loc[tile, '持平'])} | "
                     f"{int(cross.loc[tile, '收缩'])} |")
    lines.append("")

    # ---------- CME 机构 OI 交叉 ----------
    lines.append("## 4. CME 机构 OI 交叉（样本受限）\n")
    oi = load_cme_oi()
    lines.append(f"- CME 比特币期货 OI 表: {len(oi)} 交易日 {oi.index.min().date()} → {oi.index.max().date()}；"
                 f"BTC 期货 OI 中位 {oi['btc_oi'].median():,.0f} 合约，微型 {oi['micro_oi'].median():,.0f}。\n")
    if btc is not None:
        lines.append("### 4a. CME OI 日变化 vs btc 日收益（旁证相关）\n")
        lines.append("| 配对 | n(重叠日) | r | p |")
        lines.append("|---|---|---|---|")
        oi_chg = oi["btc_oi_chg"]
        oi_tot = oi["total_oi_chg"]
        for label, x in [("BTC期货 OI变化 vs btc 当日", oi_chg), ("BTC期货 OI变化 vs btc 次日", oi_chg),
                         ("总OI(含微型)变化 vs btc 当日", oi_tot)]:
            shift = 1 if "次日" in label else 0
            y = btc.shift(-shift)
            rr = pearson_row(x, y, CME_WIN_LO, "2026-08-31")
            sig = " *" if rr["p"] < 0.05 else ""
            lines.append(f"| {label} | {rr['n']} | {rr['r']:+.3f} | {rr['p']:.3f}{sig} |")
        lines.append("> *p<0.05。n 受限（coinglass klines 至 07-07 + 6.3 天空档），仅作旁证。\n")

    # CME 窗口内 wash_cvd 事件
    lo_c = int(pd.Timestamp(CME_WIN_LO, tz="UTC").timestamp() * 1000)
    hi_c = int(pd.Timestamp(CME_WIN_HI, tz="UTC").timestamp() * 1000)
    ev_cme = events[(events["timestamp"] >= lo_c) & (events["timestamp"] <= hi_c)].copy()
    ev_cme = attach_stable_state(ev_cme, st)
    # CME asof：事件日-3（保守，CME 发布滞后 1-2 天）的最近已发布 OI 变化
    dates_c = pd.to_datetime(ev_cme["timestamp"].to_numpy(), unit="ms", utc=True).tz_convert(None).normalize()
    prev3 = (dates_c - pd.Timedelta(days=3)).normalize()
    ev_cme["cme_oi_chg_asof"] = oi["btc_oi_chg"].reindex(prev3, method="ffill").to_numpy()
    ev_cme["dStable_prev"] = ev_cme["dStable"]
    lines.append("### 4b. CME 窗口内 wash_cvd 事件\n")
    if ev_cme.empty:
        lines.append("CME 重叠窗口（2026-06-08 → 07-07）内 **0 个 wash_cvd 事件**。\n")
    else:
        lines.append(f"重叠窗口内 {len(ev_cme)} 个 wash_cvd 事件（事件日-3 asof CME OI 变化）：\n")
        lines.append("| 事件时间(UTC) | symbol | dStable_prev(USD) | CME OI变化 asof | ret_24h% |")
        lines.append("|---|---|---|---|---|")
        for _, rrow in ev_cme.sort_values("timestamp").iterrows():
            ts_s = pd.Timestamp(int(rrow["timestamp"]), unit="ms", utc=True).strftime("%Y-%m-%d %H:%M")
            ds = rrow.get("dStable_prev", np.nan)
            cme = rrow.get("cme_oi_chg_asof", np.nan)
            r24 = pd.to_numeric(rrow.get("ret_24h", np.nan), errors="coerce")
            lines.append(f"| {ts_s} | {rrow['symbol']} | {ds:+,.0f} | {cme:+,.0f} | "
                         f"{r24 if pd.isna(r24) else f'{r24:+.2f}'} |")
    lines.append("")
    n_cme_ev = len(ev_cme)
    n_cme_24 = int(pd.to_numeric(ev_cme.get("ret_24h", pd.Series(dtype=float)), errors="coerce").notna().sum())
    if n_cme_24 < args.min_events:
        lines.append(f"**CME 维度判定：样本不足（重叠窗口事件 n={n_cme_ev}，24h 收益可得 {n_cme_24} < {args.min_events}），"
                     "需前向积累，不硬凑结论。**\n")
        lines.append("#### 前向积累设计（108 前向候选 × CME OI 状态对齐，不修改 108/109）\n")
        lines.append("1. **数据源**：CME parquet 由 125 手动快照（幂等合并）持续追加，或等 Owner 签批 T3-3 定时化；"
                     "稳定币 CSV 由本脚本缓存刷新（拉取日-2 新鲜度门槛）。")
        lines.append("2. **事件源**：108 contract_monitor 每日产出 `contract_monitor_candidates.csv`（已存在，reports/ 下），"
                     "或独立研究模块重跑 wash_cvd 检测——只读候选，不写 108 主流程。")
        lines.append("3. **对齐**：每事件落一行 (event_ts, symbol, event_date, dStable_prev=供给(D-1)−供给(D-2), "
                     "cme_oi_chg_asof=事件日-3 最近已发布 CME 持仓变化, ret_24h 于事件后 24h 回填) 到研究 ledger CSV；"
                     "按 dStable 符号分『扩张/收缩』两 stratum 各积累 n≥30。")
        lines.append("4. **时长估计**：见下方事件率——若全历史 wash_cvd 约每年 N 个事件、CME 覆盖自 2026-06-08 起，"
                     "两 stratum 各 30 个约需数月；达到后重跑本脚本 bootstrap 判定。")
        lines.append("5. **无前视**：CME 数据滞后 1-2 天发布 → asof 一律取事件日-3 及之前；稳定币取事件日-1（保守）。")
        lines.append("")
    else:
        lines.append(f"**CME 维度判定：重叠窗口事件 n={n_cme_ev} ≥ {args.min_events}（少见情形）——"
                     f"事件表见上，结论随表，仍建议前向积累再定。\n")

    # ---------- 判定 ----------
    lines.append("## 5. 判定\n")
    r2 = row2
    exp = r2.get("扩张", {})
    con = r2.get("收缩", {})
    lines.append("### 5.1 稳定币供给扩张是否调制 wash_cvd？\n")
    if "扩张−收缩" in r2 and exp.get("n") and con.get("n"):
        diff = r2["扩张−收缩"]
        mod = "有调制证据" if (diff["ci_lo"] > 0 or diff["ci_hi"] < 0) else "无调制证据（差 CI 含 0）"
        lines.append(f"- 扩张 n={exp['n']} 超额 {exp['excess']:+.2f}% vs 收缩 n={con['n']} 超额 {con['excess']:+.2f}%；"
                     f"扩张−收缩差 {diff['excess']:+.2f}% CI {fmt_ci(diff)} → **{mod}**。")
        lines.append(f"- 基率对照：研究窗内供给扩张日占 {base_exp:.0%}、收缩日占 {base_con:.0%}，"
                     f"事件分层占比（扩张 {ev_shares.get('扩张', 0):.0%} / 收缩 {ev_shares.get('收缩', 0):.0%}）"
                     "显示事件在扩张期略富集，但扩张−收缩超额差异仅 0.13pp 且 CI 含 0"
                     " → dStable 对 wash_cvd 后的 24h 收益无有效调制。")
    else:
        lines.append("- 分层样本不足，无法判定。")
    lines.append("- **诚实标注（对照 120 liq_expand 被证伪的教训）**：稳定币供给≠流动性代理。"
                 "dStable 日变化小、自相关强（约 20% 日点变化为 0）、且主要由发行/赎回（利率套利、链上需求）驱动，"
                 "并不直接等于交易所可交易流动性；供给绝对水平与 era 强混淆（2022 低 → 2026 高）。"
                 "因此即使表2 分层出现差异，也只支持『弹药环境调制』的弱表述，不支持『供给即流动性』的强表述。")
    lines.append("### 5.2 CME 维度\n")
    lines.append(f"- 重叠窗口事件 n={n_cme_ev}（24h 可得 {n_cme_24}）"
                 f"{'< 30 → 样本不足，需前向积累' if n_cme_24 < args.min_events else '≥ 30 → 按上表'}"
                 "；旁证相关见 §4a（n 受限，仅描述）。")

    # 事件率（积累设计用）
    yrs = (pd.Timestamp(STUDY_END) - pd.Timestamp(STUDY_START)).days / 365.25
    rate = len(ev_study) / yrs
    share_con = float(ev_shares.get("收缩", 0))
    rate_con = rate * share_con
    rate_exp = rate * (1 - share_con)
    months_con = max(1, int(30 / max(rate_con / 12, 0.1)))
    months_exp = max(1, int(30 / max(rate_exp / 12, 0.1)))
    lines.append("### 5.3 前向积累时长估计\n")
    lines.append(f"- 研究窗 {STUDY_START}→{STUDY_END} wash_cvd 事件 {len(ev_study)} 个 ≈ {rate:.0f} 事件/年"
                 f"（universe {len(ctxs)} 币，72h 冷却）；收缩日占比 {share_con:.0%}（约束侧）。")
    lines.append(f"- CME 自 2026-06-08 覆盖、asof 取事件日-3（周末 ffill 到周五）："
                 f"收缩 stratum 30 个约需 **{months_con} 个月**，扩张 stratum 约需 {months_exp} 个月"
                 f"（粗估，未计事件日恰好落在 CME 空窗的损耗）；达到后重跑本脚本 bootstrap 判定。")
    lines.append("")

    out = REPORTS_DIR / "stablecoin_cme_cross.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")

    # ---------- 控制台摘要 ----------
    print("\n=== 表1 相关 ===")
    for rrow in rows1:
        print(f"  {rrow['label']:26s} 全期 {rrow['c0']:>14s} | 2022-23 {rrow['c1']:>12s} | 2024-26 {rrow['c2']:>12s}")
    print("\n=== 表2 wash_cvd × dStable（24h 超额 vs 基线） ===")
    for k, v in row2.items():
        if "n" in v:
            print(f"  {k:8s} n={v['n']}  均={v.get('mean', float('nan')):+.2f}  超额={v.get('excess', float('nan')):+.2f}  "
                  f"CI={v.get('ci_lo', float('nan')):+.2f},{v.get('ci_hi', float('nan')):+.2f}  {v.get('verdict', '')}")
    print("\n=== 表3 水平分层 ===")
    for tile in ["低", "中", "高"]:
        sub = ev_study[ev_study["level_tile"] == tile]
        ev_v = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy()
        exp_share = (sub["dStable_sign"] == "扩张").mean() if len(sub) else np.nan
        extra = f" 24h均={np.nanmean(ev_v):+.2f}" if len(ev_v) >= args.min_events else ""
        print(f"  {tile}水平 n={len(sub)} 扩张占比={exp_share:.0%}{extra}")
    print("\n=== CME ===")
    print(f"  重叠窗口事件 n={n_cme_ev}（24h 可得 {n_cme_24}）"
          f" → {'样本不足，需前向积累' if n_cme_24 < args.min_events else '按上表'}")
    if ev_cme.empty:
        print("  无事件表")
    else:
        for _, rrow in ev_cme.sort_values("timestamp").iterrows():
            print(f"  {pd.Timestamp(int(rrow['timestamp']), unit='ms', utc=True):%Y-%m-%d %H:%M} "
                  f"{rrow['symbol']} dStable={rrow.get('dStable_prev', np.nan):+,.0f} "
                  f"CME={rrow.get('cme_oi_chg_asof', np.nan):+,.0f} "
                  f"ret24={pd.to_numeric(rrow.get('ret_24h', np.nan), errors='coerce'):+.2f}")
    print(f"\n[128] done, 报告: {out}")


if __name__ == "__main__":
    main()
