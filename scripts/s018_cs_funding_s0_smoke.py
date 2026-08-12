r"""s018 — 截面中性 Funding Carry S0 轻量探针（非完整回测）。

检查：结算间隔对齐、funding_semantics 过滤、横截面离散度、可组 quintile 期数。
数据：binance_free_db/history/funding（最多 MAX_SYMBOLS）。
输出：reports/s018_cs_funding_s0_smoke.md
用法：python scripts/s018_cs_funding_s0_smoke.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.lib.funding_semantics import (  # noqa: E402
    annotate_series,
    load_binance_funding_parquet,
    load_measurement_config,
    settlement_hours,
)

FUNDING_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
OUT_MD = ROOT / "reports" / "s018_cs_funding_s0_smoke.md"
MAX_SYMBOLS = 40  # 本地轻量；全量 70+ 留给 VPS
EXCLUDE = {"BTCUSDT", "ETHUSDT"}
SEED = 20260812
N_LEG = 5  # 卡：n_leg 目标 5 → quintile 需 ≥25 币同时点


def main() -> int:
    if not FUNDING_DIR.exists():
        print(f"MISSING {FUNDING_DIR}")
        return 1

    cfg = load_measurement_config()
    settle_h = settlement_hours(cfg=cfg)
    files = sorted(FUNDING_DIR.glob("*.parquet"))
    files = [f for f in files if f.stem not in EXCLUDE][:MAX_SYMBOLS]

    panels = []
    settle_stats = []
    cap_rows = []
    for fp in files:
        sym = fp.stem
        try:
            raw = load_binance_funding_parquet(fp)
            if len(raw) < 10:
                continue
            ts = raw["timestamp"].sort_values()
            dt_h = ts.diff().dropna() / 3.6e6
            med_h = float(dt_h.median()) if len(dt_h) else float("nan")
            settle_stats.append({"symbol": sym, "n": len(raw), "median_settle_h": med_h})
            ann = annotate_series(raw["rate_decimal"], unit="decimal", cfg=cfg)
            ann = ann.copy()
            ann["timestamp"] = raw["timestamp"].to_numpy()
            ann["symbol"] = sym
            n_cap = int(ann["is_capped"].sum())
            cap_rows.append({"symbol": sym, "n": len(ann), "n_capped": n_cap})
            # 模型可用：未封顶
            use = ann[~ann["is_capped"]].copy()
            panels.append(use[["timestamp", "symbol", "rate_for_model"]])
        except Exception as e:
            settle_stats.append({"symbol": sym, "n": 0, "median_settle_h": float("nan"), "err": str(e)})

    if not panels:
        print("no panel")
        return 2

    panel = pd.concat(panels, ignore_index=True)
    # 对齐到结算桶（8h）
    bucket_ms = int(settle_h * 3600 * 1000)
    panel["bucket"] = (panel["timestamp"] // bucket_ms) * bucket_ms
    # 每 symbol×bucket 取最后一条
    g = (
        panel.sort_values("timestamp")
        .groupby(["bucket", "symbol"], as_index=False)
        .last()
    )

    # 每 bucket 横截面
    cs = g.groupby("bucket").agg(
        n_sym=("symbol", "nunique"),
        rate_std=("rate_for_model", "std"),
        rate_p90=("rate_for_model", lambda s: float(np.nanpercentile(s.dropna(), 90)) if s.notna().any() else np.nan),
        rate_p10=("rate_for_model", lambda s: float(np.nanpercentile(s.dropna(), 10)) if s.notna().any() else np.nan),
    )
    cs["spread_p90_p10"] = cs["rate_p90"] - cs["rate_p10"]
    # 可组 n_leg=5 的 quintile：至少 25 币
    tradable = cs[cs["n_sym"] >= N_LEG * 5]
    # 粗算：每期 top5 空 - bottom5 多 的 funding 价差（仅 funding 收入近似，无价格腿）
    rng = np.random.default_rng(SEED)
    sample_buckets = tradable.index.to_numpy()
    if len(sample_buckets) > 200:
        sample_buckets = rng.choice(sample_buckets, size=200, replace=False)
    carry_snips = []
    for b in sample_buckets:
        sub = g[g["bucket"] == b].dropna(subset=["rate_for_model"])
        if len(sub) < N_LEG * 5:
            continue
        sub = sub.sort_values("rate_for_model")
        long_leg = sub.head(N_LEG)["rate_for_model"].mean()  # 低费率多
        short_leg = sub.tail(N_LEG)["rate_for_model"].mean()  # 高费率空
        # 空高费率：收 short_leg；多低费率：付 long_leg（若为负则收）
        # 中性组合 funding 收入 ≈ short_leg - long_leg（等权半名义各 0.5？卡：两腿等权 Σ=0）
        # 每腿名义 0.5 总 1：收入 ≈ 0.5*short + 0.5*(-long) wait:
        # long 持有负方向? 多头支付 funding = rate；空头收取 = rate
        # 空高: +short_rate；多低: -long_rate → gross ≈ mean(short) - mean(long)
        carry_snips.append(float(short_leg - long_leg))

    carry = np.array(carry_snips, dtype=float) if carry_snips else np.array([])
    st = pd.DataFrame(settle_stats)
    cap_df = pd.DataFrame(cap_rows)
    total_n = int(cap_df["n"].sum()) if len(cap_df) else 0
    total_cap = int(cap_df["n_capped"].sum()) if len(cap_df) else 0
    med_settle = float(st["median_settle_h"].median()) if len(st) else float("nan")
    n_align_ok = int(((st["median_settle_h"] - settle_h).abs() < 0.5).sum()) if len(st) else 0

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    gross_mean = float(np.nanmean(carry)) if len(carry) else float("nan")
    # 成本粗对照：每 8h 调仓一轮 round-trip 悲观 27bps×2 腿换手率粗算 — 仅提示
    cost_note = (
        "完整成本需换手矩阵；本探针只报毛 funding 截面价差均值，"
        "27bps 悲观与 16.2bps 真实锚留给 S1/VPS。"
    )

    ok_settle = abs(med_settle - settle_h) < 0.5 if np.isfinite(med_settle) else False
    ok_panel = len(tradable) >= 50
    ok_disp = float(cs["spread_p90_p10"].median()) > 0 if len(cs) else False
    verdict = "PASS_LIGHT" if ok_settle and ok_panel and ok_disp else "PARTIAL"
    if total_n == 0:
        verdict = "FAIL_NO_DATA"

    md = f"""# s018 CS_MN Funding — S0 轻量探针

- date: {now}
- script: `scripts/s018_cs_funding_s0_smoke.py`
- source: `{FUNDING_DIR}`
- symbols scanned: {len(files)}（上限 {MAX_SYMBOLS}，排除 BTC/ETH）
- settlement config: {settle_h}h
- **非完整回测 / 不宣布 GO**；标题含 **CS_MN**（反 s005 / 异于 s014）

## 结论

| 项 | 值 |
|---|---|
| 中位结算间隔 (h) | {med_settle:.3f} |
| 对齐 config {settle_h}h 的币数 | {n_align_ok}/{len(st)} |
| pooled n / capped | {total_n} / {total_cap} ({(100*total_cap/total_n if total_n else 0):.3f}%) |
| 有 bucket 数 | {len(cs)} |
| 可交易 bucket（n_sym≥{N_LEG*5}） | {len(tradable)} |
| 中位 p90−p10 funding 离散 | {float(cs['spread_p90_p10'].median()) if len(cs) else float('nan'):.6g} |
| 抽样期毛截面价差均值 (short−long) | {gross_mean:.6g} （n={len(carry)}） |
| **审计判定** | **{verdict}** |

## 解释

1. **结算对齐**：本地 history 中位间隔应≈8h；偏离大的币 S1 需 per-symbol 覆盖。
2. **semantics**：`is_capped=True` 已剔除，不得当真实压力。
3. **CS_MN 信号形状**：空最高 quintile / 多最低 quintile；本探针只验证「离散度 + 可组期数 + 毛 funding 价差方向描述」。
4. **与 s014 分离**：此处无现货对冲腿；仅为永续截面。
5. **与 s005 分离**：不做「拥挤→做多价格」方向规则。

## 成本提示

{cost_note}

## 结算间隔 top 偏差

```
{st.assign(dev=(st['median_settle_h']-settle_h).abs()).sort_values('dev',ascending=False).head(8).to_string(index=False) if len(st) else 'n/a'}
```

## 下一跳

1. 全 70 币 + 全历史 + 价格腿 PnL 拆分 → **VPS**
2. 换手与 16.2/27 bps 双列成本
3. 以 2025-01 切两段同向；n≥180 调仓期
4. s014 不改

## 依赖

- `harness/lib/funding_semantics.py`
- `config/funding_measurement.yaml` v1
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)
    print(f"Wrote {OUT_MD}")
    return 0 if verdict != "FAIL_NO_DATA" else 2


if __name__ == "__main__":
    raise SystemExit(main())
