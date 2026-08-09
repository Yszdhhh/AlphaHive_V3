r"""209_short_liq_frontload.py — 因子 4：短强平脉冲新近度 × wash_cvd（codex 因子池候选 4）。

机制（E-A）：131 已证 short-liquidation intensity 有效（liq_short_z>1 → +4.44%），但同样的
24h 总量可能是"刚开始"或"已经结束"。新近度衡量挤压燃料是否仍在释放（不复活 funding，
不重测双清算）。

定义（codex 规格，事件时点 asof）：
  short_liq_frontload = short_liq_usd(近 3h) / short_liq_usd(近 24h)
  （仅在 short_liq_z>1 的 wash_cvd 子集内；按预事件历史分高/低）
数据：coinglass liquidation short_liquidation_usd 小时级（2024-06 → 2026-06，131 同源）
检验：hi/lo frontload → 24/72/168h；2024 与 2025+ 两段同号；控制 total short-liq z 档

输出：reports/short_liq_frontload.md
用法：python scripts/209_short_liq_frontload.py
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import bootstrap_ci, forward_stats  # noqa: E402

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
_spec3 = importlib.util.spec_from_file_location(
    "m131", str(PROJECT_ROOT / "scripts" / "131_liquidation_cross.py"))
m131 = importlib.util.module_from_spec(_spec3)
sys.modules["m131"] = m131
_spec3.loader.exec_module(m131)

REPORT = PROJECT_ROOT / "reports" / "short_liq_frontload.md"
Z_THR = 1.0
MIN_N = 30
SEED = 2026
HORIZONS = (24, 72, 168)
HOUR_MS = 3_600_000


def short_liq_series(sym: str) -> pd.Series | None:
    p = m113.COINGLASS_RAW1H / "liquidation" / f"{sym}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if "short_liquidation_usd" not in df.columns:
        return None
    s = pd.Series(pd.to_numeric(df["short_liquidation_usd"], errors="coerce").fillna(0).to_numpy(),
                  index=pd.Index(pd.to_numeric(df["time"], errors="coerce")))
    return s[~s.index.duplicated(keep="last")].sort_index()


def rolling_z(s: pd.Series, window: int = 720) -> pd.Series:
    mean = s.rolling(window, min_periods=window // 2).mean()
    std = s.rolling(window, min_periods=window // 2).std()
    return (s - mean) / std.replace(0, np.nan)


def main() -> int:
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

    # 复用 131 精确机制：add_liq_features + attach_liq_asof（n=123 同款子集）
    ctxs = m131.add_liq_features(ctxs)
    ev = m131.attach_liq_asof(ctxs, events)
    ev = ev[ev["liq_short_z_at_event"] > Z_THR].dropna(subset=["liq_short_z_at_event"]).copy()
    print(f"short_liq_z>{Z_THR} 子集事件 {len(ev)}（131 参考 n=123）")

    # frontload：短强平近 3h / 近 24h（reindex 到 ctx 网格，事件 asof）
    rows: list[dict] = []
    for sym, g in ev.groupby("symbol", sort=False):
        t = ctxs[sym]
        idx = t.index.to_numpy(dtype=np.int64)
        p = m131.LIQ_DIR / f"{sym}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if "time" not in df.columns or "short_liquidation_usd" not in df.columns:
            continue
        sho = pd.Series(pd.to_numeric(df["short_liquidation_usd"], errors="coerce").fillna(0).to_numpy(),
                        index=pd.Index(pd.to_numeric(df["time"], errors="coerce")))
        sho = sho[~sho.index.duplicated(keep="last")].sort_index().reindex(t.index)
        vals = sho.to_numpy(dtype=float)
        for _, e in g.iterrows():
            pos = int(np.searchsorted(idx, int(e["timestamp"]), side="right")) - 1
            if pos < 24:
                continue
            s3 = vals[pos - 3:pos].sum()
            s24 = vals[pos - 24:pos].sum()
            if s24 <= 0:
                continue
            rows.append({"symbol": sym, "timestamp": int(e["timestamp"]),
                         "frontload": float(s3 / s24),
                         "liq_z": float(e["liq_short_z_at_event"])})
    ann = pd.DataFrame(rows)
    ev = ev.merge(ann, on=["symbol", "timestamp"], how="inner")
    print(f"有 frontload 样本 {len(ev)}")

    fwd_parts = []
    for sym, g in ev.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=HORIZONS))
    ev = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else ev

    med = ev["frontload"].median()
    hi = ev[ev["frontload"] >= med]
    lo = ev[ev["frontload"] < med]
    lines = ["# 短强平脉冲新近度 × wash_cvd（209，因子 4）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 子集：short_liq_z>{Z_THR}（131 同款）；frontload = 近 3h 短强平 / 近 24h 短强平",
             f"- 高 frontload = 挤压燃料仍在释放（新近）；中位 {med:.3f}\n",
             "| 层 | n | 24h 均值 | 72h 均值 | 168h 均值 | 168h 中位 |",
             "|---|---|---:|---:|---:|---:|"]
    for label, g in [("新近高", hi), ("新近低", lo)]:
        cells = []
        for h in HORIZONS:
            v = pd.to_numeric(g[f"ret_{h}h"], errors="coerce").dropna()
            cells.append(f"{v.mean():+.2f}%（n={len(v)}）")
        med_v = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().median()
        lines.append(f"| {label} | {len(g)} | {' | '.join(cells)} | {med_v:+.2f}% |")

    v_hi = pd.to_numeric(hi["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    v_lo = pd.to_numeric(lo["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    lines.append("\n## 新近−陈旧增量（24h）\n")
    if len(v_hi) >= MIN_N and len(v_lo) >= MIN_N:
        ci = bootstrap_ci(v_hi, v_lo, seed=SEED)
        lines.append(f"| 新近−陈旧 | {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] |")
        print(f"[209] 新近−陈旧 24h {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")
    else:
        lines.append(f"样本不足（{len(v_hi)}/{len(v_lo)}，需 ≥{MIN_N}）")

    # episode 一致性（2024 vs 2025+）
    lines.append("\n## Episode 一致性（24h 均值）\n")
    lines.append("| episode | 新近高（n） | 新近低（n） | 差 |")
    lines.append("|---|---:|---:|---:|")
    for name, lo_ts, hi_ts in [("2024", "2024-06-06", "2025-01-01"), ("2025+", "2025-01-01", None)]:
        m = (ev["timestamp"] >= int(pd.Timestamp(lo_ts, tz="UTC").timestamp() * 1000))
        if hi_ts:
            m &= (ev["timestamp"] < int(pd.Timestamp(hi_ts, tz="UTC").timestamp() * 1000))
        sub = ev[m]
        vals = []
        for label, g in [("hi", sub[sub["frontload"] >= med]), ("lo", sub[sub["frontload"] < med])]:
            v = pd.to_numeric(g["ret_24h"], errors="coerce").dropna()
            vals.append((v.mean(), len(v)))
        lines.append(f"| {name} | {vals[0][0]:+.2f}%（n={vals[0][1]}） | {vals[1][0]:+.2f}%（n={vals[1][1]}） | "
                     f"{vals[0][0] - vals[1][0]:+.2f}% |")

    lines += ["\n## 解读\n",
              "- pooled 显著（+7.20% CI[+2.59,+12.54]）但**段间不一致**：2024 差 -0.15%（无增量）、",
              "  2025+ 差 +9.78%（全由 2025 驱动）→ 按验收口径（≥2 段同号）**不升级**。",
              "- 2025 单期驱动与 135（2025 语境差异）/136（2025 单期 NO_GO）同模式：2025 年 wash_cvd 事件",
              "  中短强平新近度有区分力（BTC 下跌中继语境下挤压燃料新近 = 更强轧空），2024 无。",
              "- 判定：**观察项（2025 子期有效，需独立窗口/前向复核）**；不作为条件接入。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
