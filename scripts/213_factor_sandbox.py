r"""213_factor_sandbox.py — S0 沙盒：廉价因子概念筛选（替代 212，可复用漏斗）。

三级漏斗的 S0 层：对 wash_cvd 事件条件集，低成本判断"这个因子概念有没有稳定梯度"，
**不宣布 GO/NO_GO、不消耗季度正式预算、不触发任何部署语义**。

输出（固定模板，禁止加花样指标凑显著）：
1. 条件 Spearman IC（事件后 24h 净收益）
2. Q1-Q5 分桶 + 高−低 uplift（允许末端饱和，无机制的 U 型不当 edge）
3. 覆盖率（<30% 降级窄域观察）
4. 两段时间段方向一致性（2022-23 vs 2024-26）
5. 与已保留调制器的相关（|ρ| 高 → 只报 residual 描述）

形态：每概念 ≤2 预声明形态（config/factor_funnel.yaml allowed_forms），先写后算。
事件宽表：data/research/wash_cvd_events_master.parquet（grok 建议：一张表取代 21x 拼接）。

用法：
  python scripts/213_factor_sandbox.py --list
  python scripts/213_factor_sandbox.py --family volume_participation
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import forward_stats  # noqa: E402
from harness.lib.factor_funnel import (  # noqa: E402
    FORM_FUNCS,
    bucket_stats,
    conditional_ic,
    segment_consistency,
)

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

FUNNEL = PROJECT_ROOT / "config" / "factor_funnel.yaml"
MASTER = PROJECT_ROOT / "data" / "research" / "wash_cvd_events_master.parquet"
REPORTS = PROJECT_ROOT / "reports"
HORIZON = 24


# ---------- 概念特征（事件时点 asof，无前视） ----------

def _asof_series(events: pd.DataFrame, per_symbol_series: dict[str, pd.Series]) -> pd.Series:
    """事件 ts → 每 symbol 序列的 asof 值（side='right'-1）。"""
    out = np.full(len(events), np.nan)
    for sym, g in events.groupby("symbol", sort=False):
        s = per_symbol_series.get(sym)
        if s is None:
            continue
        axis = s.index.to_numpy(dtype=np.int64)
        vals = s.to_numpy(dtype=float)
        for _, e in g.iterrows():
            pos = int(np.searchsorted(axis, int(e["timestamp"]), side="right")) - 1
            if 0 <= pos < len(vals):
                out[e.name] = vals[pos]
    return pd.Series(out, index=events.index)


def _qv_series(sym: str) -> pd.Series:
    p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
    if not p.exists():
        return pd.Series(dtype=float)
    kl = pd.read_parquet(p)
    ts_col = "time" if "time" in kl.columns else "open_time"
    return pd.Series(pd.to_numeric(kl["quote_volume"], errors="coerce").to_numpy(),
                     index=pd.Index(pd.to_numeric(kl[ts_col], errors="coerce")))


def feature_vol_ratio(events: pd.DataFrame, ctxs: dict | None = None) -> pd.Series:
    """放量：qv24 / 30d 中位数（E03 同款，事件 asof）。"""
    cache: dict[str, pd.Series] = {}
    per = {}
    for sym in events["symbol"].unique():
        qv = cache.setdefault(sym, _qv_series(sym))
        if len(qv) == 0:
            continue
        qv24 = qv.rolling(24).sum()
        per[sym] = qv24 / qv24.rolling(30 * 24, min_periods=24).median().replace(0, np.nan)
    return _asof_series(events, per)


def feature_price_z(events: pd.DataFrame, ctxs: dict) -> pd.Series:
    """washout 深度：price_z（事件 asof）。"""
    per = {sym: pd.to_numeric(ctx["price_z"], errors="coerce")
           for sym, ctx in ctxs.items() if "price_z" in ctx.columns}
    return _asof_series(events, per)


def feature_cvd_div(events: pd.DataFrame, ctxs: dict) -> pd.Series:
    """CVD 背离强度（事件 asof）。"""
    per = {sym: pd.to_numeric(ctx["cvd_divergence"], errors="coerce")
           for sym, ctx in ctxs.items() if "cvd_divergence" in ctx.columns}
    return _asof_series(events, per)


def feature_vol_ratio_2d(events: pd.DataFrame, ctxs: dict | None = None) -> pd.Series:
    """3d 成交变化（qv72/30d，136 同款 3d 口径）。"""
    cache: dict[str, pd.Series] = {}
    per = {}
    for sym in events["symbol"].unique():
        qv = cache.setdefault(sym, _qv_series(sym))
        if len(qv) == 0:
            continue
        qv72 = qv.rolling(72).sum()
        per[sym] = qv72 / qv72.rolling(30 * 24, min_periods=24).median().replace(0, np.nan)
    return _asof_series(events, per)


# 概念注册表：name → (feature 函数, 允许形态列表[≤2])
CONCEPTS: dict[str, tuple] = {
    "volume_participation": (feature_vol_ratio, ["log_ratio", "capped_hinge"]),
    "volume_3d": (feature_vol_ratio_2d, ["log_ratio", "rank"]),
    "washout_depth": (feature_price_z, ["rank", "binary_diag"]),
    "cvd_divergence": (feature_cvd_div, ["rank", "log_ratio"]),
}


def load_events() -> pd.DataFrame:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    fundings = m113.load_funding_series(symbols)
    ev_parts = []
    for sym, ctx in ctxs.items():
        ev = m115.detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = events[(events["timestamp"] >= int(pd.Timestamp("2021-12-01", tz="UTC").timestamp() * 1000))].copy()
    events = events.reset_index(drop=True)
    return events, ctxs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", type=str, default=None)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for name, (_, forms) in CONCEPTS.items():
            print(f"  {name}: 形态 {forms}")
        return 0

    events, ctxs = load_events()
    print(f"wash_cvd 事件（2021-12+，development 样本）: {len(events)}")

    # 前向收益（24h 主 horizon）+ 事件日（两段一致性用）
    fwd = []
    for sym, g in events.groupby("symbol", sort=False):
        fwd.append(forward_stats(ctxs[sym], g.copy(), horizons=(HORIZON,)))
    ev = pd.concat(fwd, ignore_index=True) if fwd else events
    y = pd.to_numeric(ev[f"ret_{HORIZON}h"], errors="coerce") - 0.27  # 成本后
    ev_day = pd.to_datetime(ev["timestamp"], unit="ms", utc=True).dt.floor("D")

    # 事件宽表（grok B 项）
    features_all = {}
    for name, (fn, _) in CONCEPTS.items():
        features_all[name] = fn(ev, ctxs)
    MASTER.parent.mkdir(parents=True, exist_ok=True)
    out = ev[["symbol", "timestamp"]].copy()
    for name, s in features_all.items():
        out[name] = s.to_numpy()
    out["ret_24h_net"] = y.to_numpy()
    out["ev_day"] = ev_day.dt.strftime("%Y-%m-%d")
    out.to_parquet(MASTER, index=False)
    print(f"事件宽表: {MASTER}")

    family = args.family
    if family is None:
        print("--family 必填；--list 查看可用概念")
        return 1
    if family not in CONCEPTS:
        print(f"未知概念 {family}")
        return 1
    fn, forms = CONCEPTS[family]
    raw = fn(ev, ctxs)
    if len(forms) > 2:
        print(f"形态超限（≤2）：{forms}")
        return 1

    lines = ["# S0 沙盒报告（213）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 概念：{family} | 样本：development（2021-12→今）| 主 horizon：{HORIZON}h 成本后",
             f"- 性质：探索性描述，不宣布 GO/NO_GO，不消耗季度正式预算\n",
             "| 形态 | IC | 高−低 uplift | 覆盖率 | 单调性 | 2022-23 uplift | 2024-26 uplift |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for fname in forms:
        if fname not in FORM_FUNCS:
            continue
        f = FORM_FUNCS[fname](raw)
        ic = conditional_ic(f, y)
        bs = bucket_stats(f, y)
        segs = segment_consistency(f, y, ev_day, [("2022-23", "2022-01-01", "2024-01-01"),
                                                  ("2024-26", "2024-01-01", None)])
        s22 = next((s["uplift"] for s in segs if s["segment"] == "2022-23"), None)
        s24 = next((s["uplift"] for s in segs if s["segment"] == "2024-26"), None)
        cov = bs["coverage"]
        mono = bs["monotonicity"]
        lines.append(f"| {fname} | {ic:+.3f} | {bs['high_low_uplift']:+.2f}% | {cov:.0%} | "
                     f"{mono:.2f} | {s22:+.2f}% | {s24:+.2f}% |")
        # 每桶明细
        lines.append(f"  - Q1-Q5 均值: " +
                     " ".join(f"Q{b+1}={r['mean']:+.2f}%(n={r['n']})" for b, r in enumerate(bs["buckets"])))
        print(f"[213] {family}×{fname}: IC {ic:+.3f} uplift {bs['high_low_uplift']:+.2f}% "
              f"覆盖 {cov:.0%} 两段 {s22:+.2f}%/{s24:+.2f}%")

    lines += ["\n## 解读（只作描述）\n",
              "- IC>0.03 且 uplift 单调到饱和 + 两段同号 → 值得进 S1 挑战者（冻结一次 holdout）；",
              "- 覆盖 <30% → 降级窄域观察；两段反号 → 概念族弱，记台账后关闭。",
              "- 本报告不授予任何历史结论；最终确认只认前向影子（109/143 事件块）。"]
    out_md = REPORTS / f"sandbox_{family}.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
