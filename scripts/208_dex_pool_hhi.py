r"""208_dex_pool_hhi.py — D3：DEX 放量质量——池分散度/HHI（codex 因子池次假设 2）。

机制（E-A）：多池/多协议一致放量更可能是真实广泛承接；单池集中尖峰更可能是路由、
激励、MEV 或局部操纵。AMM 流动性碎片化长期存在。

定义（codex 规格，前一日 asof 无前视）：
  pool_hhi_24h = Σ(project_volume_share²)     （日度，project 级近似池级）
  effective_pool_count = 1 / HHI
检验（codex 验收）：
- 仅在 DEX_HIGH（dex24_ratio>1.5）样本内比较低 HHI 与高 HHI（防总量代理）
- 在 dex24_ratio 相近区间内匹配（HHI 不是总量代理的复核）
- 高分散（HHI 低）→ 24/72/168h 前向；episode 两段

输出：reports/dex_pool_hhi.md
用法：python scripts/208_dex_pool_hhi.py
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

REPORT = PROJECT_ROOT / "reports" / "dex_pool_hhi.md"
PROJ_CSV = PROJECT_ROOT / "data" / "dune" / "dex_project_daily.csv"
VOL_CSV = PROJECT_ROOT / "data" / "dune" / "dex_vol_daily.csv"
RATIO_THR = 1.5
MIN_N = 50
SEED = 2026
HORIZONS = (24, 72, 168)


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
    events = events[(events["timestamp"] >= int(pd.Timestamp("2021-12-01", tz="UTC").timestamp() * 1000))].copy()

    proj = pd.read_csv(PROJ_CSV)
    vol = pd.read_csv(VOL_CSV)
    proj["date"] = pd.to_datetime(proj["date"], utc=True)
    vol["date"] = pd.to_datetime(vol["date"], utc=True)
    for df in (proj, vol):
        df["date"] = df["date"].dt.date.astype(str)
    # 日度 HHI（project 份额平方和）→ effective pools
    proj["sh"] = pd.to_numeric(proj["vol_usd"], errors="coerce")
    hhi = proj.groupby(["date", "symbol"]).apply(
        lambda g: float((g["sh"] / g["sh"].sum()).pow(2).sum()), include_groups=False
    ).rename("hhi").reset_index()
    vp = vol.pivot_table(index="date", columns="symbol", values="vol_usd", aggfunc="sum")
    full_idx = pd.date_range(pd.to_datetime(vp.index.min()), pd.to_datetime(vp.index.max()),
                             freq="D", tz="UTC").strftime("%Y-%m-%d")
    vp = vp.reindex(full_idx).fillna(0.0)
    dex_ratio = vp / vp.rolling(30, min_periods=15).median().replace(0, np.nan)
    hhi_p = hhi.pivot_table(index="date", columns="symbol", values="hhi", aggfunc="first")

    ev_prev = (pd.to_datetime(events["timestamp"], unit="ms", utc=True).dt.floor("D")
               - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    base_sym = events["symbol"].str.replace("USDT", "")
    rows = []
    for i, (_, e) in enumerate(events.iterrows()):
        d, s = ev_prev.iloc[i], base_sym.iloc[i]
        r = {"symbol": e["symbol"], "timestamp": int(e["timestamp"])}
        r["dex_ratio"] = dex_ratio.loc[d, s] if s in dex_ratio.columns and d in dex_ratio.index else np.nan
        r["hhi"] = hhi_p.loc[d, s] if s in hhi_p.columns and d in hhi_p.index else np.nan
        rows.append(r)
    ann = pd.DataFrame(rows)
    ev = events.merge(ann, on=["symbol", "timestamp"], how="left")

    fwd_parts = []
    for sym, g in ev.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=HORIZONS))
    ev = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else ev

    dex_hi = ev[(ev["dex_ratio"] > RATIO_THR) & ev["hhi"].notna()].copy()
    med_hhi = dex_hi["hhi"].median()
    disp = dex_hi[dex_hi["hhi"] <= med_hhi]   # 低 HHI = 高分散
    conc = dex_hi[dex_hi["hhi"] > med_hhi]    # 高 HHI = 集中
    print(f"DEX_HIGH 事件 {len(dex_hi)} | 分散 {len(disp)} / 集中 {len(conc)} | HHI 中位 {med_hhi:.3f}")

    lines = ["# DEX 池分散度/HHI × wash_cvd（208，D3）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 仅在 DEX 放量（ratio>{RATIO_THR}）样本内；HHI = Σ(project 份额²)，前一日 asof",
             f"- 分散（HHI≤{med_hhi:.3f}）= 多协议广泛承接 vs 集中 = 单协议尖峰\n",
             "| 层 | n | 24h 均值 | 72h 均值 | 168h 均值 | 168h 中位 |",
             "|---|---|---:|---:|---:|---:|"]
    for label, g in [("高分散", disp), ("集中", conc)]:
        cells = []
        for h in HORIZONS:
            v = pd.to_numeric(g[f"ret_{h}h"], errors="coerce").dropna()
            cells.append(f"{v.mean():+.2f}%（n={len(v)}）")
        med = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().median()
        lines.append(f"| {label} | {len(g)} | {' | '.join(cells)} | {med:+.2f}% |")

    v_d = pd.to_numeric(disp["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    v_c = pd.to_numeric(conc["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    lines.append("\n## 分散−集中增量（24h）\n")
    if len(v_d) >= MIN_N and len(v_c) >= MIN_N:
        ci = bootstrap_ci(v_d, v_c, seed=SEED)
        lines.append(f"| 分散−集中 | {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] |")
        print(f"[208] 分散−集中 24h {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")
    else:
        lines.append(f"样本不足（分散={len(v_d)}, 集中={len(v_c)}，需 ≥{MIN_N}）")

    # ratio 匹配复核：把 dex_ratio 相近区间（1.5~2.5）内再比
    lines.append("\n## ratio 匹配复核（1.5<ratio≤2.5 区间内）\n")
    m = dex_hi[(dex_hi["dex_ratio"] > 1.5) & (dex_hi["dex_ratio"] <= 2.5)]
    d2, c2 = m[m["hhi"] <= med_hhi], m[m["hhi"] > med_hhi]
    v_d2 = pd.to_numeric(d2["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    v_c2 = pd.to_numeric(c2["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    if len(v_d2) >= MIN_N and len(v_c2) >= MIN_N:
        ci = bootstrap_ci(v_d2, v_c2, seed=SEED)
        lines.append(f"| 匹配后分散−集中 | {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]（n={len(d2)}/{len(c2)}） |")
        print(f"[208] 匹配后 {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")
    else:
        lines.append(f"样本不足（{len(d2)}/{len(c2)}）")

    lines += ["\n## 解读\n",
              "- 分散−集中显著为正 + 匹配后仍成立 → 多协议广泛承接是放量质量的真实增量（非总量代理）；",
              "- CI 含 0 / 匹配后消失 → HHI 只是 dex_ratio 的代理 → NO_GO。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
