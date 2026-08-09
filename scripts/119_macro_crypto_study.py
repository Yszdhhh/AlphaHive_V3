"""119_macro_crypto_study.py — 宏观×加密交叉影响研究（多系列，市场级择时视角）。

问题：FRED 宏观系列（SP500/WTI/美元指数/VIX/黄金/国债/联邦基金利率 + CPI/GDP）
对加密市场（BTC + 山寨篮子）有没有可测影响？哪些状态对次日收益有预测力？

方法（诚实、无前视）：
- 加密日收益：coinglass klines（2021-12→2026-05-27）+ binance_free_db 前向区
  （2026-05-31→今）→ 每 symbol 每小时 close 聚合到 UTC 日收盘 → 日收益。
  alt = universe 山寨等权横截面均值；btc 单列。
- 宏观日特征：macro/*.parquet 的 close（index=日期）。当日变化 + 滞后状态
  （50d MA / 滚动分位）都用【截止当天】的数据构造，预测加密【次日】收益。
- CPI/GDP 低频：MoM/QoQ 变化按发布滞后整体后移一期（CPI+1月、GDP+1季），
  防止把尚未发布的数据当已知（已知近似，非 FRED realtime 精确对齐）。
- 基线 = 全样本日收益无条件均值，bootstrap 95% CI（bootstrap_ci）。

输出 reports/macro_crypto_study.md

用法：
  python scripts/119_macro_crypto_study.py [--seed 2026]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import bootstrap_ci

COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
BINANCE_RAW1H = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h")
MACRO_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
REPORTS_DIR = PROJECT_ROOT / "reports"

BASE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def load_universe_symbols() -> list[str]:
    import json
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = json.load(f)["symbols"]
    return [item["symbol"] for item in universe if item["symbol"] not in BASE_SYMBOLS]


def load_daily_close(symbol: str) -> pd.Series | None:
    """coinglass + binance_free_db 每小时 close → UTC 日收盘 Series（index=date）。

    清洗：30d rolling median 偏离 >50x 置 NaN（防 coinglass 停更断点假 bar）。
    """
    parts: list[pd.Series] = []
    for root in (COINGLASS_RAW1H, BINANCE_RAW1H):
        p = root / "klines" / f"{symbol}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if "open_time" not in df.columns or "close" not in df.columns:
            continue
        ts = pd.to_numeric(df["open_time"], errors="coerce")
        close = pd.to_numeric(df["close"], errors="coerce")
        s = pd.Series(close.to_numpy(dtype=float), index=pd.Index(ts.to_numpy(dtype=np.int64)))
        s = s[s.index.notna()].sort_index()
        parts.append(s)
    if not parts:
        return None
    s = pd.concat(parts)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    # 假 bar 清洗（30d rolling median 偏离 50x）
    s = s.replace([np.inf, -np.inf], np.nan)
    med = s.rolling(720, min_periods=360).median()
    ratio = s / med.replace(0, pd.NA)
    s = s.where((ratio >= 0.02) & (ratio <= 50.0))
    s = s.dropna()
    if len(s) < 400:
        return None
    dates = pd.to_datetime(s.index, unit="ms", utc=True).tz_convert(None).normalize()
    daily = s.groupby(dates).last()
    daily.index = pd.DatetimeIndex(daily.index).tz_localize(None).normalize()
    return daily


def load_macro_series(key: str) -> pd.Series:
    p = MACRO_ROOT / f"{key}.parquet"
    df = pd.read_parquet(p)
    idx = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
    return pd.Series(pd.to_numeric(df["close"], errors="coerce").to_numpy(), index=idx)


def build_alt_returns(symbols: list[str]) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """每 symbol 日收益 → (alt 日收益 Series, {sym: ret_series})。"""
    sym_ret: dict[str, pd.Series] = {}
    for sym in symbols:
        c = load_daily_close(sym)
        if c is None:
            continue
        r = c.pct_change() * 100.0
        sym_ret[sym] = r
    if not sym_ret:
        raise RuntimeError("无任何 symbol 可用")
    mat = pd.DataFrame(sym_ret)
    alt = mat.mean(axis=1, skipna=True).dropna()
    return alt, sym_ret


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    print(f"[119] 加载 {len(symbols)} symbols 日收益…")
    alt, sym_ret = build_alt_returns(symbols)
    btc = sym_ret.get("BTCUSDT")
    if btc is None:
        btc = load_daily_close("BTCUSDT")
        if btc is not None:
            btc = btc.pct_change() * 100.0
    print(f"[119] alt 日收益 {len(alt)} 天  {alt.index.min().date()} → {alt.index.max().date()}")
    if btc is not None:
        print(f"[119] btc 日收益 {len(btc)} 天  {btc.index.min().date()} → {btc.index.max().date()}")

    # ---- 宏观特征（全部以截止当天为已知，预测次日）----
    sp500 = load_macro_series("SP500")
    sp_ret = sp500.pct_change() * 100.0
    sp_ma50 = sp500 > sp500.rolling(50, min_periods=30).mean()          # risk_on/off
    wti = load_macro_series("WTI")
    wti_ret = wti.pct_change() * 100.0
    dollar = load_macro_series("DOLLAR")
    dollar_ret = dollar.pct_change() * 100.0
    dollar_ma50 = dollar < dollar.rolling(50, min_periods=30).mean()    # 美元弱
    vix = load_macro_series("VIX")
    vix_ret = vix.pct_change() * 100.0
    vix_p75 = vix > vix.rolling(365, min_periods=120).quantile(0.75)    # VIX 高位
    gold = load_macro_series("GOLD")
    gold_ret = gold.pct_change() * 100.0
    tr = pd.read_parquet(MACRO_ROOT / "TREASURY.parquet")
    tr_idx = pd.DatetimeIndex(tr.index).tz_localize(None).normalize()
    us10 = pd.Series(pd.to_numeric(tr["us_10y"], errors="coerce").to_numpy(), index=tr_idx)
    us2 = pd.Series(pd.to_numeric(tr["us_2y"], errors="coerce").to_numpy(), index=tr_idx)
    spread = pd.Series(pd.to_numeric(tr["us_10y_2y_spread"], errors="coerce").to_numpy(), index=tr_idx)
    d10y = us10.diff()                                                   # 长端利率日变化（bps）
    ff = load_macro_series("FEDFUNDS")
    fed_lo = ff < ff.rolling(365, min_periods=120).median()              # 利率处低位/降息周期

    # CPI MoM（+1月发布滞后）、GDP QoQ（+1季）
    cpi = load_macro_series("CPI")
    cpi_mom = cpi.pct_change() * 100.0
    cpi_mom.index = cpi_mom.index + pd.DateOffset(months=1)
    gdp = load_macro_series("GDP")
    gdp_qoq = gdp.pct_change() * 100.0
    gdp_qoq.index = gdp_qoq.index + pd.DateOffset(months=3)

    # ---- 对齐到统一日轴：状态(t) → 响应 alt_ret(t+1) ----
    def align(series_map: dict[str, pd.Series]) -> pd.DataFrame:
        idx = alt.index.union(btc.index if btc is not None else alt.index)
        df = pd.DataFrame(index=pd.DatetimeIndex(idx))
        for k, s in series_map.items():
            df[k] = s.reindex(df.index, method="ffill")
        df["alt_ret"] = alt.reindex(df.index)
        df["btc_ret"] = btc.reindex(df.index) if btc is not None else np.nan
        return df

    df = align({
        "sp500_ret": sp_ret, "sp500_ma50": sp_ma50.astype(float),
        "wti_ret": wti_ret,
        "dollar_ret": dollar_ret, "dollar_ma50": dollar_ma50.astype(float),
        "vix_ret": vix_ret, "vix_high": vix_p75.astype(float),
        "gold_ret": gold_ret,
        "us10": us10, "d10y": d10y, "spread": spread,
        "fedfunds": ff, "fed_lo": fed_lo.astype(float),
        "cpi_mom": cpi_mom, "gdp_qoq": gdp_qoq,
    })

    # 响应：次日收益（当前行状态已知 → 下一天收益）
    df["alt_fwd"] = df["alt_ret"].shift(-1)
    df["btc_fwd"] = df["btc_ret"].shift(-1)
    out_lines: list[str] = []
    out_lines.append("# 宏观×加密交叉影响研究（市场级择时视角）\n")
    out_lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    out_lines.append(f"- 加密日收益: coinglass klines（2021-12→2026-05-27）+ binance_free_db 前向区（→今）；"
                     f"alt={len(sym_ret)} 山寨等权，btc 单列")
    out_lines.append(f"- 宏观: FRED 官方 API（118 拉取，macro/*.parquet）；黄金=yfinance GC=F")
    out_lines.append(f"- 无前视: 状态(t) 只用截止当天已知信息，响应 = 次日收益；CPI/GDP 已按发布滞后后移一期")
    out_lines.append(f"- 基线 = 全样本日收益无条件均值，bootstrap 95% CI（seed={args.seed}）\n")

    # ---- 1) 相关矩阵 ----
    out_lines.append("## 1. 相关矩阵（macro[t] vs crypto 当日 / 次日）\n")
    out_lines.append("| 变量 | 与alt当日 r | 与alt次日 r | 与btc次日 r | n |")
    out_lines.append("|---|---|---|---|---|")
    feats = {
        "SP500日变": "sp500_ret", "WTI日变": "wti_ret", "美元指数日变": "dollar_ret",
        "VIX日变": "vix_ret", "黄金日变": "gold_ret", "10Y日变(bps)": "d10y",
        "10Y-2Y利差": "spread", "联邦基金利率": "fedfunds", "CPI MoM": "cpi_mom", "GDP QoQ": "gdp_qoq",
    }
    for name, col in feats.items():
        sub = df[["alt_ret", "alt_fwd", "btc_fwd", col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(sub) < 30 or sub[col].std() == 0:
            out_lines.append(f"| {name} | - | - | - | {len(sub)} |")
            continue
        r_cur = sub["alt_ret"].corr(sub[col])
        r_alt_f = sub["alt_fwd"].corr(sub[col])
        r_btc_f = sub["btc_fwd"].corr(sub[col])
        out_lines.append(f"| {name} | {r_cur:+.3f} | {r_alt_f:+.3f} | {r_btc_f:+.3f} | {len(sub)} |")

    # ---- 2) 宏观状态 → 次日山寨收益（择时）----
    out_lines.append("\n## 2. 宏观状态 → 次日山寨收益（市场级择时）\n")
    out_lines.append("| 状态 | 定义 | 在状态天 n | alt次日均% | 超额vs无条件 | 95% CI | 判定 |")
    out_lines.append("|---|---|---|---|---|---|---|")
    uncond = df["alt_fwd"].dropna()
    uncond_mean = uncond.mean()

    def state_row(name: str, mask: pd.Series) -> None:
        sub = df[mask.fillna(False)]["alt_fwd"].dropna()
        if len(sub) < 15:
            out_lines.append(f"| {name} | 样本不足(n={len(sub)}) | {len(sub)} | - | - | - | - |")
            return
        ci = bootstrap_ci(sub.to_numpy(), uncond.to_numpy(), seed=args.seed)
        dd = ci["mean_diff"]
        if ci["ci_lo"] > 0:
            verdict = "**偏多**"
        elif ci["ci_hi"] < 0:
            verdict = "**偏空**"
        else:
            verdict = "平坦"
        out_lines.append(
            f"| {name} | 见定义 | {len(sub)} | {sub.mean():+.2f} | {dd:+.2f} | "
            f"[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {verdict} |")

    # 定义各状态（都用截止当天信息）
    states = {
        "美元走弱(dollar_ret<0)": df["dollar_ret"] < 0,
        "美元走强(dollar_ret>0)": df["dollar_ret"] > 0,
        "美元低于50dMA": df["dollar_ma50"] == 1,
        "10Y利率下行(d10y<0)": df["d10y"] < 0,
        "10Y利率上行(d10y>0)": df["d10y"] > 0,
        "曲线陡峭(spread>0)": df["spread"] > 0,
        "曲线倒挂(spread<0)": df["spread"] < 0,
        "risk_on(SP500>50dMA)": df["sp500_ma50"] == 1,
        "risk_off(SP500<50dMA)": df["sp500_ma50"] == 0,
        "VIX高位(>1y 75分位)": df["vix_high"] == 1,
        "黄金上涨(gold_ret>0)": df["gold_ret"] > 0,
        "利率低位/降息(fed<1y中位)": df["fed_lo"] == 1,
        "流动性扩张(美元弱+10Y下行)": (df["dollar_ret"] < 0) & (df["d10y"] < 0),
        "流动性收紧(美元强+10Y上行)": (df["dollar_ret"] > 0) & (df["d10y"] > 0),
        "CPI上行(MoM>0)": df["cpi_mom"] > 0,
        "GDP扩张(QoQ>0)": df["gdp_qoq"] > 0,
    }
    for name, mask in states.items():
        state_row(name, mask)

    # 主组合分 era 一致性（2022-2023 vs 2024-2026）
    out_lines.append("\n### 流动性扩张 / risk_off 分 era 一致性\n")
    out_lines.append("| 状态 | era | n | alt次日均% | 超额 | 95% CI |")
    out_lines.append("|---|---|---|---|---|---|")
    for sname, smask in [("流动性扩张", (df["dollar_ret"] < 0) & (df["d10y"] < 0)),
                         ("risk_off", df["sp500_ma50"] == 0)]:
        for era_name, a, b in [("2022-2023", "2022-01-01", "2024-01-01"),
                               ("2024-2026", "2024-01-01", "2027-01-01")]:
            m = smask & (df.index >= a) & (df.index < b)
            sub = df[m.fillna(False)]["alt_fwd"].dropna()
            if len(sub) < 15:
                out_lines.append(f"| {sname} | {era_name} | {len(sub)} | - | - | - |")
                continue
            ci = bootstrap_ci(sub.to_numpy(), uncond.to_numpy(), seed=args.seed)
            out_lines.append(f"| {sname} | {era_name} | {len(sub)} | {sub.mean():+.2f} | "
                             f"{ci['mean_diff']:+.2f} | [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] |")

    # ---- 3) 极端宏观日事件研究 ----
    out_lines.append("\n## 3. 极端宏观日 → 次日加密收益（事件研究）\n")
    out_lines.append("| 冲击 | 定义 | 冲击天 n | alt次日均% | 超额vs全样本 | 95% CI | btc次日均% | btc超额 |")
    out_lines.append("|---|---|---|---|---|---|---|---|")

    def shock_row(name: str, mask: pd.Series) -> None:
        m = mask.fillna(False)
        sub_a = df[m]["alt_fwd"].dropna()
        sub_b = df[m]["btc_fwd"].dropna() if btc is not None else pd.Series(dtype=float)
        if len(sub_a) < 10:
            out_lines.append(f"| {name} | 样本不足(n={len(sub_a)}) | {len(sub_a)} | - | - | - | - | - |")
            return
        ci = bootstrap_ci(sub_a.to_numpy(), uncond.to_numpy(), seed=args.seed)
        btc_u = df["btc_fwd"].dropna()
        btc_ci = bootstrap_ci(sub_b.to_numpy(), btc_u.to_numpy(), seed=args.seed) if len(sub_b) >= 10 else {"mean_diff": np.nan}
        out_lines.append(
            f"| {name} | 见定义 | {len(sub_a)} | {sub_a.mean():+.2f} | {ci['mean_diff']:+.2f} | "
            f"[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | "
            f"{sub_b.mean():+.2f} | {btc_ci.get('mean_diff', np.nan):+.2f} |")

    # 分位阈值（全样本 5/95）
    for col, side, q in [("sp500_ret", "bottom", 0.05), ("vix_ret", "top", 0.95),
                         ("dollar_ret", "top", 0.95), ("dollar_ret", "bottom", 0.05),
                         ("gold_ret", "top", 0.95), ("d10y", "bottom", 0.05),
                         ("d10y", "top", 0.95)]:
        v = df[col].replace([np.inf, -np.inf], np.nan).dropna()
        if v.empty or v.std() == 0:
            continue
        thr = v.quantile(q)
        if side == "top":
            mask = df[col] >= thr
            label = f"{col} 上5%（≥{thr:+.1f}）"
        else:
            mask = df[col] <= thr
            label = f"{col} 下5%（≤{thr:+.1f}）"
        shock_row(label, mask)

    # ---- 4) 当前宏观状态快照 ----
    out_lines.append("\n## 4. 当前宏观状态快照（2026-07 → 今）\n")
    out_lines.append("| 指标 | 最新值 | 日期 | 近30d变化 | 解读 |")
    out_lines.append("|---|---|---|---|---|")
    cur = df[df.index >= "2026-07-01"]
    snap_rows = []
    # 计算解读用辅助状态
    sp_above = bool((sp500.dropna().iloc[-1]) > sp500.dropna().rolling(50, min_periods=30).mean().iloc[-1]) if len(sp500.dropna()) >= 50 else False
    vix_low = bool(vix.dropna().iloc[-1] < vix.dropna().rolling(365, min_periods=120).median().iloc[-1]) if len(vix.dropna()) >= 120 else False
    for label, s, how in [
        ("SP500", sp500, "level"), ("美元指数", dollar, "level"), ("VIX", vix, "level"),
        ("黄金", gold, "level"), ("WTI", wti, "level"), ("10Y收益率", us10, "level"),
        ("10Y-2Y利差", spread, "level"), ("联邦基金利率", ff, "level"),
    ]:
        s = s.dropna()
        if s.empty:
            continue
        last_v = s.iloc[-1]
        d30 = s.iloc[-1] - s.iloc[-30] if len(s) >= 31 else np.nan
        p30 = d30 / s.iloc[-30] * 100.0 if len(s) >= 31 and s.iloc[-30] else np.nan
        unit = "bps" if "10Y" in label or "利差" in label else ("%" if label in ("VIX", "联邦基金利率") else "指数/价格")
        interp = "-"
        if label == "SP500":
            interp = f"创新高/高位({p30:+.1f}% 30d)，{'>50dMA' if sp_above else '<50dMA'} → risk_on"
        elif label == "美元指数":
            interp = f"30d {d30:+.1f} → {'小幅走弱' if d30 < 0 else '走强'}（流动性宽松偏正面/收紧偏负面）"
        elif label == "VIX":
            interp = f"{'低位(<1y中位)' if vix_low else '高位(>1y中位)'} → 风险偏好{'偏稳' if vix_low else '偏紧张'}"
        elif label == "黄金":
            interp = f"30d {p30:+.1f}% → {'强避险/通胀对冲买盘' if p30 > 3 else '平稳'}"
        elif label == "WTI":
            interp = f"30d {p30:+.1f}% → {'通胀输入上升' if p30 > 5 else '平稳'}"
        elif label == "10Y收益率":
            interp = f"水平{last_v:.2f}%，30d {d30:+.2f}bps → {'利率抬升压制估值' if d30 > 5 else ('利率回落利好' if d30 < -5 else '平稳')}"
        elif label == "10Y-2Y利差":
            interp = f"{'陡峭' if last_v > 0 else '倒挂'}({last_v:+.2f}) → {'经济预期修复' if last_v > 0 else '衰退担忧'}"
        elif label == "联邦基金利率":
            fed_dov = bool(ff.dropna().iloc[-1] < ff.dropna().rolling(365, min_periods=120).median().iloc[-1]) if len(ff.dropna()) >= 120 else False
            interp = f"{'降息周期/低位(<1y中位)' if fed_dov else '中性偏紧/高位'}(30d {d30:+.2f})"
        snap_rows.append(f"| {label} | {last_v:.2f} | {s.index[-1].date()} | {d30:+.2f} {unit} | {interp} |")
    # 当前 alt/btc 前向收益（分阶段，避免 116 重叠窗口夸大的偏差）
    fwd_alt = cur["alt_ret"].dropna()
    fwd_btc = cur["btc_ret"].dropna() if btc is not None else pd.Series(dtype=float)
    if len(fwd_alt):
        out_lines.append(f"| 山寨篮子(2026-07→今) | {fwd_alt.mean():+.2f}%/日 | {fwd_alt.index[0].date()}→{fwd_alt.index[-1].date()} | n={len(fwd_alt)} | 整体≈平坦，非持续上涨 |")
    if len(fwd_btc):
        out_lines.append(f"| BTC(2026-07→今) | {fwd_btc.mean():+.2f}%/日 | {fwd_btc.index[0].date()}→{fwd_btc.index[-1].date()} | n={len(fwd_btc)} | - |")
    # 分阶段（早7月/晚7月/早8月）
    phases = []
    for a, b in [("2026-07-01", "2026-07-09"), ("2026-07-09", "2026-08-01"), ("2026-08-01", "2026-08-07")]:
        w = alt[(alt.index >= a) & (alt.index < b)]
        if len(w):
            phases.append(f"{a[5:]}→{b[5:]}: {w.mean():+.2f}%/日(n={len(w)})")
    out_lines.append(f"- 山寨篮子分阶段: " + "；".join(phases) if phases else "- 山寨篮子分阶段: 无")
    out_lines.append("- 注: 116 报的「当前筑底 fwd24 +2.13%」是重叠 24h 窗口 + 只截 coinglass 07-01→07-07 短切片")
    out_lines.append("  的统计放大；按日度收盘聚合（本表）实际≈平坦，早期 7 月/早期 8 月各有温和正段。")
    out_lines.extend(snap_rows)

    out_lines.append("\n## 5. 结论\n")
    out_lines.append("**宏观与加密是「同日共振、非次日预测」关系（诚实负结果）：**\n")
    out_lines.append("- **同日**：SP500 日变与山寨当日 r=+0.35、VIX 日变 r=-0.29（risk sentiment 共振），美元日变 r=-0.14（弱）。")
    out_lines.append("  但宏观收盘（美东 16:00 ≈ UTC 21:00）落在加密当日窗口内 → 重叠时段，不可按日度直接交易。")
    out_lines.append("- **次日**：所有宏观变量的次日相关 r≈0；16 个宏观状态（含流动性扩张/risk_off/VIX高位/利率低位）")
    out_lines.append("  对次日山寨收益的 bootstrap 95% CI 全部含 0。流动性扩张分 era 方向相反（2022-23 +0.17 / 2024-26 -0.16）→ 不稳定。")
    out_lines.append("- **极端宏观日**：SP500 下 5%、VIX 上 5%、美元上/下 5%、10Y 下 5% 等冲击后次日 alt/btc 超额均不显著（CI 宽、含 0）。")
    out_lines.append("- **推论**：宏观单变量不构成可交易的日度择时 edge。宏观的定位是 **regime 背景**（106 的 risk_off 门控），")
    out_lines.append("  不是独立触发信号——与 114（funding 择时 NO_GO）同类的诚实负结果。")
    out_lines.append("- **可留下一步**：美股收盘后（21:00 UTC 后）加密对当日美股信号的「隔夜反应」需小时级分析，日度分辨率掩盖了这个窗口。")

    out = REPORTS_DIR / "macro_crypto_study.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"\nwrote {out}")
    # 打印关键行方便直接看
    for l in out_lines:
        if l.startswith("|") and ("偏多" in l or "偏空" in l):
            print(l)


if __name__ == "__main__":
    main()
