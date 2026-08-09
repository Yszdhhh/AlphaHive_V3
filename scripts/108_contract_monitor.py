"""108_contract_monitor.py — 前向合约监控（Phase 4 影子）。

在 coinglass 停更后的 binance_free_db 前向区，对 universe 山寨池检测
contract_anomaly_rules.yaml 中【事件研究判定 GO】的 trigger。只读影子，不下单。

诚实边界（重要）：
- 前向区数据维度 ≠ coinglass：binance_free_db 只有 klines/oi/taker/funding，
  【无】liquidation、ls_top_trader、真 cum_vol_delta。
  → liq_cascade_* 与 top_trader_* 前向不可测（数据源无此维度），直接跳过。
  → cvd_bear_divergence 用 klines taker 构造【近似 CVD】= cumsum(2*taker_buy_quote_vol
    - quote_volume)，信号强度未必等同 coinglass 真 CVD，标注 source=CVD_APPROX。
- Go/No-Go 门控：脚本启动时读 reports/event_study_summary.csv，只有 verdict 含 GO
  且前向可测的 trigger 才启用（数据驱动，不硬编码）。
- MC 来自 CoinGecko；suspicious(时间漂移) 的候选跳过。
- live 衍生数据触发保持 DISABLED（宪法）：本脚本只用前向影子，不点火 live。

用法：
  python scripts/108_contract_monitor.py [--symbols ...] [--mc-force]
输出：
  reports/contract_monitor_candidates.csv（contract_alert_schema）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.contract_anomaly_features import FeatureWindow, build_feature_table
from harness.lib.asset_identity_registry import AssetIdentityRegistry
from harness.lib.market_cap_provider import MarketCapProvider
from harness.lib.regime_engine import assign_regime, btc_state, load_regimes, sp500_below_50d

# 无 emoji 路径 = binance_data_puller.py 实际写入处（binance_data_config.DB_ROOT）。
# ⚠️ 历史教训：曾指向带 emoji 的 🔒 加密资产\binance_free_db，导致读到停更 5 天的旧库。
BINANCE_ROOT = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h")
RULES_PATH = PROJECT_ROOT / "config" / "contract_anomaly_rules.yaml"
SUMMARY_PATH = PROJECT_ROOT / "reports" / "event_study_summary.csv"
OUT_PATH = PROJECT_ROOT / "reports" / "contract_monitor_candidates.csv"
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "raw" / "market_caps"
BASE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# regime 标注数据源。SP500 停更超过 REGIME_STALE_DAYS → risk_off 判定降级（诚实边界）
SP500_PATH = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro\SP500.parquet")
REGIME_STALE_DAYS = 7

# VIX 门控数据源（118 每日拉取，FRED VIXCLS）。见 contract_anomaly_rules.yaml wash_cvd.vix_gate（v3，Owner 签批 2026-08-07）
VIX_PATH = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro\VIX.parquet")

# 前向可测的维度（binance_free_db 有）；其余 trigger 前向不可测 → 跳过
FORWARD_DIMS = {"klines", "cvd", "funding_ohlc"}

# 流动性门槛（用户硬约束：小资金进出自由）。候选 24h 成交额低于该值 → liquidity_ok=False。
# 影子模式下不硬跳过，只标注，人工审查时可见。
LIQUIDITY_MIN_USD = 1_000_000


def load_yaml(path: Path) -> dict:
    import yaml

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_universe_symbols() -> list[str]:
    import json

    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = json.load(f)["symbols"]
    return [item["symbol"] for item in universe if item["symbol"] not in BASE_SYMBOLS]


def load_binance_dims(symbol: str, root: Path) -> dict[str, pd.DataFrame]:
    """binance_free_db → 与 load_dim_frames 同构的 dims（[timestamp ms, 源列]）。"""
    dims: dict[str, pd.DataFrame] = {}

    kl_path = root / "klines" / f"{symbol}.parquet"
    if kl_path.exists():
        kl = pd.read_parquet(kl_path)
        if "open_time" in kl.columns and "close" in kl.columns:
            kl = kl.rename(columns={"open_time": "timestamp"})
            kl["timestamp"] = pd.to_numeric(kl["timestamp"], errors="coerce")
            kl["close"] = pd.to_numeric(kl["close"], errors="coerce")
            kl["quote_volume"] = pd.to_numeric(kl["quote_volume"], errors="coerce")
            kl = kl.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
            dims["klines"] = kl[["timestamp", "close", "quote_volume"]]
            # 近似 CVD：累计 taker 净买入流量（主动买 - 主动卖）
            if "taker_buy_quote_vol" in kl.columns:
                tb = pd.to_numeric(kl["taker_buy_quote_vol"], errors="coerce")
                net_flow = (2 * tb - kl["quote_volume"]).fillna(0.0)
                dims["cvd"] = pd.DataFrame({
                    "timestamp": kl["timestamp"].to_numpy(),
                    "cum_vol_delta": net_flow.cumsum().to_numpy(),
                })

    fund_path = root / "funding_aligned" / f"{symbol}.parquet"
    if fund_path.exists():
        fd = pd.read_parquet(fund_path)
        if "open_time" in fd.columns and "fundingRate_decimal" in fd.columns:
            fd = fd.rename(columns={"open_time": "timestamp", "fundingRate_decimal": "close"})
            fd["timestamp"] = pd.to_numeric(fd["timestamp"], errors="coerce")
            fd["close"] = pd.to_numeric(fd["close"], errors="coerce")
            fd = fd.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
            dims["funding_ohlc"] = fd[["timestamp", "close"]]
    return dims


def load_latest_oi_usd(symbol: str, root: Path) -> float | None:
    """binance oi 最新 sumOpenInterestValue（USD OI）。"""
    oi_path = root / "oi" / f"{symbol}.parquet"
    if not oi_path.exists():
        return None
    oi = pd.read_parquet(oi_path)
    if "sumOpenInterestValue" not in oi.columns:
        return None
    vals = pd.to_numeric(oi["sumOpenInterestValue"], errors="coerce").dropna()
    return float(vals.iloc[-1]) if not vals.empty else None


def latest_trigger_state(ft: pd.DataFrame, rule: dict) -> dict | None:
    """表尾（当前时点）是否满足触发条件；满足返回 {timestamp, feature, feature_value}。"""
    if ft.empty:
        return None
    feature = rule["feature"]
    if feature not in ft.columns:
        return None
    last_row = ft.iloc[-1]
    val = pd.to_numeric(last_row[feature], errors="coerce")
    if pd.isna(val):
        return None
    threshold = float(rule["threshold"])
    hit = bool(val >= threshold) if rule.get("direction", "above") == "above" else bool(val <= threshold)
    if not hit:
        return None
    pf = rule.get("price_filter")
    if pf:
        pcol = pf["feature"]
        if pcol in ft.columns:
            pv = pd.to_numeric(last_row[pcol], errors="coerce")
            if pd.isna(pv):
                return None
            ok = bool(pv >= float(pf["threshold"])) if pf.get("direction", "above") == "above" else bool(pv <= float(pf["threshold"]))
            if not ok:
                return None
    return {
        "timestamp": int(ft.index[-1]),
        "feature": feature,
        "feature_value": float(val),
    }


def go_triggers(summary_path: Path, rules: dict) -> list[str]:
    """从 event_study_summary.csv 取 verdict=GO_LONG/GO_SHORT 且规则存在 的 trigger。

    精确匹配：'NO_GO' 含子串 'GO'，不能 str.contains('GO')。
    """
    if not summary_path.exists():
        print("[108] WARNING 无 event_study_summary.csv，Go/No-Go 门控无法判定 → 不启用任何 trigger")
        return []
    df = pd.read_csv(summary_path)
    go = df[df["verdict"].isin(["GO_LONG", "GO_SHORT"])]["trigger"].tolist()
    return [t for t in go if t in rules.get("triggers", {})]


def load_regime_state(binance_root: Path, sp500_path: Path):
    """加载 regime 判定所需状态（BTC 前向 + SP500 macro）。

    返回 (btc_dd, btc_above, btc_ts, sp_below, sp_ts, sp_last_ms)。
    SP500 停更降级由调用方处理：候选时点距 SP500 最后 bar 超阈值时，
    把 sp_below 置全 False（risk_off 不判定，只留 btc_recovery/default）。
    """
    btc = pd.read_parquet(binance_root / "klines" / "BTCUSDT.parquet")
    btc_close = pd.to_numeric(btc.set_index("open_time")["close"], errors="coerce").sort_index()
    btc_ts = btc_close.index.to_numpy(dtype=np.int64)
    btc_dd, btc_above = btc_state(btc_close)
    sp = pd.read_parquet(sp500_path)
    sp_idx = sp.index.to_numpy()  # datetime64[ms] → ms int
    sp_close = pd.Series(pd.to_numeric(sp["close"], errors="coerce").to_numpy(), index=sp_idx).sort_index()
    sp_ts = sp_close.index.to_numpy(dtype=np.int64)
    sp_below = sp500_below_50d(sp_close)
    sp_last_ms = int(sp_ts[-1]) if len(sp_ts) else None
    return btc_dd, btc_above, btc_ts, sp_below, sp_ts, sp_last_ms


def load_vix_state(vix_path: Path) -> pd.Series:
    """加载 VIX 日线（index=ms int UTC，close）。缺失/空 → 空 Series。"""
    if not vix_path.exists():
        return pd.Series(dtype=float)
    vix = pd.read_parquet(vix_path)
    idx = pd.DatetimeIndex(vix.index).tz_localize(None).normalize()
    close = pd.Series(pd.to_numeric(vix["close"], errors="coerce").to_numpy(), index=idx)
    close = close.sort_index().dropna()
    return pd.Series(close.to_numpy(dtype=float), index=close.index.to_numpy(dtype="datetime64[ms]").astype("int64"))


def vix_gate_state(vix_close: pd.Series, ts_ms: int, cfg: dict) -> dict:
    """VIX 门控判定（无前视）：候选时点 asof 日-1 的 VIX 收盘 vs 1y 滚动 q75。

    cfg: wash_cvd.vix_gate 段（quantile_window_days / quantile / asof_days_back）。
    返回 {status: low|high|NA, close, q75}；缺数据或窗口不足 → NA。
    """
    if vix_close.empty or not cfg.get("enabled"):
        return {"status": "NA", "close": np.nan, "q75": np.nan}
    window = int(cfg.get("quantile_window_days", 365))
    q = float(cfg.get("quantile", 0.75))
    back = int(cfg.get("asof_days_back", 1))
    asof_ms = ts_ms - back * 86_400_000
    idx = vix_close.index.to_numpy(dtype=np.int64)
    pos = int(np.searchsorted(idx, asof_ms, side="right") - 1)
    if pos < 0:
        return {"status": "NA", "close": np.nan, "q75": np.nan}
    close_at = float(vix_close.iloc[pos])
    # 滚动 q75：只用 ≤ asof 的窗口（asof 时点已知信息），min_periods = 1/3 窗口
    hist = vix_close.iloc[: pos + 1]
    minp = max(int(window * 0.33), 60)
    if len(hist) < minp:
        return {"status": "NA", "close": close_at, "q75": np.nan}
    q75 = float(hist.iloc[-min(window, len(hist)):].quantile(q))
    status = "high" if close_at > q75 else "low"
    return {"status": status, "close": close_at, "q75": q75}


def load_score_spec() -> dict | None:
    """读取 factor_funnel.yaml 的 forward_scores.score_vol 规格（2026-08-09 新增）。

    返回 None → 无规格（score 全 NA，候选链照常）。异常只打印 WARNING 不中断。
    """
    try:
        with (PROJECT_ROOT / "config" / "factor_funnel.yaml").open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("forward_scores", {}).get("score_vol")
    except Exception as exc:  # noqa: BLE001
        print(f"[108] WARNING score 规格读取失败（score_vol 将置 NA）: {exc}")
        return None


def score_vol_at(kl: pd.DataFrame | None, event_ts_ms: int, trigger: str,
                 spec: dict | None) -> float | None:
    """事件时点 asof 的放量分数（纯标注，不改触发/候选集）。

    口径（grok 硬条件：与 scripts/213 feature_vol_ratio 完全一致）：
      qv24 = quote_volume.rolling(24).sum()
      ratio = qv24 / qv24.rolling(720, min_periods=24).median()
      score = capped_hinge(ratio, 1.0, 2.0)
    门控：spec 存在 且 status=FROZEN 且 trigger∈applicable_triggers
          且 event_ts >= forward_start；否则返回 None（NA）。
    任何异常 → None（绝不改变候选集）。
    """
    if spec is None or kl is None:
        return None
    try:
        if spec.get("status") != "FROZEN":
            return None
        fs = spec.get("forward_start")
        if not fs or event_ts_ms < int(pd.Timestamp(fs).timestamp() * 1000):
            return None
        if trigger not in spec.get("applicable_triggers", []):
            return None
        if "timestamp" in kl.columns and "quote_volume" in kl.columns:
            ts = pd.to_numeric(kl["timestamp"], errors="coerce")
            qv = pd.to_numeric(kl["quote_volume"], errors="coerce")
        else:
            return None
        mask = ts <= event_ts_ms  # asof：只用事件时点及之前的 bar
        qv = qv[mask]
        if len(qv) < spec.get("baseline_min_periods", 24):
            return None
        qv24 = qv.rolling(spec.get("qv_window_hours", 24)).sum()
        base = qv24.rolling(spec.get("baseline_window_hours", 720),
                            min_periods=spec.get("baseline_min_periods", 24)).median()
        ratio = (qv24 / base.replace(0, np.nan)).iloc[-1]
        if not np.isfinite(ratio) or ratio <= 0:
            return None
        from harness.lib.factor_funnel import capped_hinge
        score = float(capped_hinge(pd.Series([ratio]),
                                   lo=spec.get("lo", 1.0), hi=spec.get("hi", 2.0)).iloc[0])
        return None if not np.isfinite(score) else score
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=None, help="逗号分隔子集（默认 universe 山寨池）")
    parser.add_argument("--mc-force", action="store_true", help="强制刷新 MC 缓存")
    parser.add_argument("--min-liquidity-usd", type=float, default=LIQUIDITY_MIN_USD,
                        help="24h 成交额最低门槛（美元）")
    args = parser.parse_args()

    rules = load_yaml(RULES_PATH)
    enabled = go_triggers(SUMMARY_PATH, rules)
    if not enabled:
        print("[108] 无已启用 trigger（前向可测 + GO）。退出。")
        return
    print(f"[108] Go/No-Go 门控启用 triggers: {enabled}")

    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else load_universe_symbols()
    registry = AssetIdentityRegistry.from_project_config()
    provider = MarketCapProvider(registry, cache_dir=SNAPSHOT_DIR)
    if not provider.refresh(force=args.mc_force):
        print(f"[108] MC 刷新失败: {provider._last_error}")
        return
    win = FeatureWindow()

    # regime 标注（btc_recovery 用 BTC 前向数据；risk_off 依赖 SP500，停更则降级）
    try:
        btc_dd, btc_above, btc_ts, sp_below, sp_ts, sp_last_ms = load_regime_state(BINANCE_ROOT, SP500_PATH)
    except Exception as exc:  # BTC/SP500 任一缺失 → regime 整体降级，不影响候选流
        print(f"[108] WARNING regime 状态加载失败（标注将降级为 default）: {exc}")
        btc_dd = btc_above = btc_ts = sp_below = sp_ts = np.array([], dtype=np.int64)
        sp_last_ms = None
    regime_cfg = load_regimes()
    sp500_stale_ms = int(pd.Timedelta(days=REGIME_STALE_DAYS).total_seconds() * 1000)

    # VIX 门控状态（wash_cvd.vix_gate，v3；缺失 → 全 NA 标注，不影响候选流）
    try:
        vix_close = load_vix_state(VIX_PATH)
    except Exception as exc:
        print(f"[108] WARNING VIX 门控状态加载失败（vix 标注将置 NA）: {exc}")
        vix_close = pd.Series(dtype=float)
    vix_cfg = rules.get("triggers", {}).get("wash_cvd", {}).get("vix_gate", {})
    score_spec = load_score_spec()  # 2026-08-09 连续打分标注（未冻结→NA）

    rows = []
    skipped_dims = set()
    for sym in symbols:
        dims = load_binance_dims(sym, BINANCE_ROOT)
        ft = build_feature_table(dims, win)
        if len(ft) < 720:
            continue  # 不足 30d 特征窗口
        # 流动性：最近 24 根 kline 的 quote_volume 之和（≈24h 成交额 USD）
        liq_24h = None
        kl = dims.get("klines")
        if kl is not None and len(kl):
            qv = pd.to_numeric(kl["quote_volume"], errors="coerce").dropna()
            if len(qv):
                liq_24h = float(qv.iloc[-24:].sum())
        liq_ok = liq_24h is not None and liq_24h >= args.min_liquidity_usd
        oi_usd = load_latest_oi_usd(sym, BINANCE_ROOT)
        mc_res = provider.market_cap_usd(sym)
        for tname in enabled:
            rule = rules["triggers"][tname]
            hit = latest_trigger_state(ft, rule)
            if hit is None:
                continue
            if mc_res is None or mc_res.suspicious:
                continue  # MC 未覆盖或漂移 → 跳过
            oi_mc = (oi_usd / mc_res.market_cap_usd) if (oi_usd and mc_res.market_cap_usd > 0) else None
            # regime 标注：SP500 停更超阈值 → risk_off 降级（btc_recovery/default 仍有效）
            reg_status = "OK"
            eff_sp = sp_below
            if sp_last_ms is not None and (hit["timestamp"] - sp_last_ms) > sp500_stale_ms:
                eff_sp = np.zeros(len(sp_ts), dtype=bool)
                reg_status = f"SP500_STALE since {pd.Timestamp(sp_last_ms, unit='ms', tz='UTC'):%Y-%m-%d}"
            reg = "default"
            if len(btc_ts) and len(eff_sp) == len(sp_ts):
                reg = assign_regime(
                    np.array([hit["timestamp"]], dtype=np.int64),
                    btc_dd, btc_above, btc_ts, eff_sp, sp_ts, regime_cfg,
                )[0]
            # VIX 门控标注（wash_cvd 专用，annotate 不硬跳；vix_high → 研究建议跳过）
            vg = vix_gate_state(vix_close, int(hit["timestamp"]), vix_cfg)
            vix_status, vix_close_val, vix_q75 = vg["status"], vg["close"], vg["q75"]
            vix_gate_ok = None if vix_status == "NA" else (vix_status == "low")
            vix_note = ""
            if vix_status == "high":
                vix_note = " | vix_high 研究建议跳过（123 VIX 门控，Owner 签批 2026-08-07），影子保留观察"
            # 连续打分标注（score_vol，2026-08-09；纯标注不改触发/候选集；未冻结→NA）
            score_vol = score_vol_at(kl, int(hit["timestamp"]), tname, score_spec)
            rows.append({
                "schema_version": "v1",
                "alert_id": f"{tname}_{sym}_{hit['timestamp']}",
                "trigger": tname,
                "symbol": sym,
                "timestamp_ms": hit["timestamp"],
                "feature_value": hit["feature_value"],
                "direction": rule.get("signal_direction", "Long" if tname.endswith("bear_divergence") else "Short"),
                "regime": reg,
                "regime_status": reg_status,
                "vix_status": vix_status,
                "vix_close": vix_close_val,
                "vix_q75": vix_q75,
                "vix_gate_ok": vix_gate_ok,
                "market_cap_usd": mc_res.market_cap_usd,
                "mc_suspicious": mc_res.suspicious,
                "oi_to_mc_ratio": oi_mc,
                "liquidity_24h_usd": liq_24h,
                "liquidity_ok": liq_ok,
                "identity_gate_status": mc_res.mapping_status,
                "score_vol": score_vol,
                "source": "CVD_APPROX" if tname == "cvd_bear_divergence" else "COINGLASS_DIM",
                "notes": ("前向影子（binance_free_db）；CVD 为 klines taker 近似" if tname == "cvd_bear_divergence" else "") + vix_note,
            })

    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(OUT_PATH, index=False)
        print(f"[108] 写入 {OUT_PATH}  候选={len(rows)}")
        for r in rows:
            print(f"  {r['trigger']:24s} {r['symbol']:14s} ts={pd.Timestamp(r['timestamp_ms'], unit='ms', tz='UTC'):%m-%d %H:%M} "
                  f"regime={r['regime']:12s} feat={r['feature_value']:.2f} OI/MC={r['oi_to_mc_ratio']:.3f} "
                  f"MC=${r['market_cap_usd']:,.0f} 24hVol=${r['liquidity_24h_usd']:,.0f} liq_ok={r['liquidity_ok']} score_vol={r['score_vol'] if r['score_vol'] is not None else 'NA'}")
    else:
        print(f"[108] 当前无触发候选（扫描 {len(symbols)} symbols）")


if __name__ == "__main__":
    main()
