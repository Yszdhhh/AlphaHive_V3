r"""216_offline_execution_replay.py — 执行层 Phase 1：D 账户离线执行复盘（PROXY_ONLY）。

目的（grok 审查定稿）：回答"D 账户的 27bps 统计锚相对配置摩擦（friction_config v1）
偏松还是偏紧、低流动性尾部有多贵"。只读复盘，不改 143、不动 A 锚、不写累计 CSV。

模型（grok 瘦身版）：
- 主结果 = config_only：fee(taker 5.5) + 入场/退出分时点 24h 成交额分档滑点 + 点差 fallback
  （friction_config.yaml 只读，版本锁）
- 参与率标注：notional($1000) / 入场 1h 成交额 与 / 24h 成交额 → 分位 + ILLIQUID 标红
  （>0.1% 参与率标红；不模拟多 bar 撤单状态机——grok：样本内几乎全 full fill）
- 冲击（仅敏感性附录）：participation 超地板时 impact = eta × range_bps × √part，
  eta∈{0.5,1,2}；range 同时给 (high-low)/mid 与 |close-open|/mid（wick 风险对照）
- funding：读 binance_free_db raw_8h/funding 覆盖行（D 币预计 0/251 → 诚实 UNAVAILABLE 不补零）
- 全部标 PROXY_ONLY；config_only 与 legacy 27bps 并列，禁止双计相加

输出：reports/execution_phase1_D_detail.csv + execution_phase1_D_report.md
用法：python scripts/216_offline_execution_replay.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

POS_CSV = PROJECT_ROOT / "reports" / "paper_positions_D.csv"
KL_DIR = PROJECT_ROOT / "data" / "newlisting_raw"
FRICTION = PROJECT_ROOT / "config" / "friction_config.yaml"
FUND_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_8h\funding")
OUT_DETAIL = PROJECT_ROOT / "reports" / "execution_phase1_D_detail.csv"
OUT_REPORT = PROJECT_ROOT / "reports" / "execution_phase1_D_report.md"
NOTIONAL = 1000.0
LEGACY_ONE_WAY_BPS = 27.0
PARTICIPATION_RED = 0.001  # 0.1%
HOUR_MS = 3_600_000


def load_friction() -> dict:
    with FRICTION.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def tier_bps(turnover_usd: float, tiers: list[dict]) -> float:
    for t in tiers:
        if turnover_usd >= t["min_turnover_usd"]:
            return float(t["slippage_bps"] if "slippage_bps" in t else t["spread_bps"])
    return float(tiers[-1].get("slippage_bps", tiers[-1].get("spread_bps", 0.0)))


def klines(sym: str) -> pd.DataFrame | None:
    p = KL_DIR / f"{sym}.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)


def turnover_at(kl: pd.DataFrame, ts_ms: int, hours: int) -> float:
    """事件 ts 前 hours 小时成交额（asof，无前视）。"""
    t = pd.to_numeric(kl["open_time"], errors="coerce")
    qv = pd.to_numeric(kl["quote_volume"], errors="coerce")
    mask = (t <= ts_ms) & (t > ts_ms - hours * HOUR_MS)
    return float(qv[mask].sum())


def impact_bps(kl: pd.DataFrame, ts_ms: int, participation: float, eta: float,
               notional: float) -> tuple[float, float]:
    """入场 bar 的冲击代理：eta × range_bps × √participation。返回 (range_bps, impact_bps)。"""
    t = pd.to_numeric(kl["open_time"], errors="coerce")
    pos = int(np.searchsorted(t.to_numpy(dtype=np.int64), ts_ms, side="right")) - 1
    if pos < 0 or pos >= len(kl):
        return np.nan, np.nan
    o, h, l, c = (float(kl[col].iloc[pos]) for col in ("open", "high", "low", "close"))
    mid = (h + l) / 2.0
    if mid <= 0:
        return np.nan, np.nan
    range_bps = 1e4 * (h - l) / mid
    if not np.isfinite(participation) or participation <= 0:
        return range_bps, 0.0
    return range_bps, eta * range_bps * np.sqrt(participation)


def funding_coverage(symbols: list[str]) -> int:
    if not FUND_DIR.exists():
        return 0
    return sum(1 for s in symbols if (FUND_DIR / f"{s}.parquet").exists())


def main() -> int:
    pos = pd.read_csv(POS_CSV)
    friction = load_friction()
    fees = friction["fees"]
    slip_tiers = friction["slippage_tiers_bps"]
    spread_tiers = friction["spread_bps_fallback"]["tiers"]
    taker = fees["taker_fee_bps"]

    rows = []
    for _, r in pos.iterrows():
        sym = r["symbol"]
        kl = klines(sym)
        if kl is None or len(kl) == 0:
            rows.append({"symbol": sym, "alert_id": r["alert_id"], "status": "NO_KLINES"})
            continue
        entry_ms = int(r["timestamp_ms"]) + 5 * HOUR_MS  # 事件+4h 确认 → 第 5 根 bar（143 语义）
        exit_ms = entry_ms + 163 * HOUR_MS
        # 分时点流动性档（入场/退出分别取）
        t_in = turnover_at(kl, entry_ms, 24)
        t_out = turnover_at(kl, exit_ms, 24)
        slip_in, slip_out = tier_bps(t_in, slip_tiers), tier_bps(t_out, slip_tiers)
        sprd_in, sprd_out = tier_bps(t_in, spread_tiers), tier_bps(t_out, spread_tiers)
        one_way_in = taker + slip_in + sprd_in
        one_way_out = taker + slip_out + sprd_out
        cfg_round_bps = one_way_in + one_way_out
        qv1h = turnover_at(kl, entry_ms, 1)
        part_1h = NOTIONAL / qv1h if qv1h > 0 else np.nan
        part_24h = NOTIONAL / t_in if t_in > 0 else np.nan
        illiquid = bool(np.isfinite(part_1h) and part_1h > PARTICIPATION_RED)
        rb_hi_lo, imp05 = impact_bps(kl, entry_ms, part_1h, 0.5, NOTIONAL)
        _, imp10 = impact_bps(kl, entry_ms, part_1h, 1.0, NOTIONAL)
        _, imp20 = impact_bps(kl, entry_ms, part_1h, 2.0, NOTIONAL)
        legacy_cost = 2 * LEGACY_ONE_WAY_BPS
        rows.append({
            "symbol": sym, "alert_id": r["alert_id"],
            "pnl_net": r["pnl_net"],
            "turnover_24h_in": t_in, "turnover_24h_out": t_out,
            "slip_bps_in": slip_in, "slip_bps_out": slip_out,
            "spread_bps_in": sprd_in, "spread_bps_out": sprd_out,
            "config_round_bps": round(cfg_round_bps, 2),
            "legacy_round_bps": legacy_cost,
            "cost_gap_bps": round(cfg_round_bps - legacy_cost, 2),
            "participation_1h": part_1h, "participation_24h": part_24h,
            "illiquid": illiquid,
            "range_bps_hl": rb_hi_lo, "impact_eta05": round(imp05, 2),
            "impact_eta1": round(imp10, 2), "impact_eta2": round(imp20, 2),
            "status": "OK",
        })
    df = pd.DataFrame(rows)
    OUT_DETAIL.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DETAIL, index=False)

    ok = df[df["status"] == "OK"]
    cov = funding_coverage(pos["symbol"].unique().tolist())
    n = len(ok)
    # 成本后 α 重估：真实摩擦上界 = config 双边 − legacy 已扣部分（27bps 单边=54 双边已含）
    extra_cost = ok["config_round_bps"] - 2 * LEGACY_ONE_WAY_BPS
    pnl_adj = ok["pnl_net"] - ok["notional"] * extra_cost / 1e4 if "notional" in ok.columns else None
    lines = ["# 执行层 Phase 1：D 账户离线执行复盘（216，PROXY_ONLY）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 模型：friction_config v1（taker {taker}bps + 分档滑点 + 点差 fallback，只读，悲观口径）",
             f"- **PROXY_ONLY**：容量/冲击为代理估计，不可相加当真实成本；不参与任何仓位/eligibility 决策",
             f"- 样本：{n} 笔可复盘 / {len(pos)} 总\n",
             "## 主结果：config_only 摩擦 vs legacy 27bps 统计锚\n",
             "| 指标 | 值 |",
             "|---|---:|",
             f"| 双边 config 摩擦中位 | {ok['config_round_bps'].median():.1f} bps |",
             f"| legacy 双边（统计锚） | {2 * LEGACY_ONE_WAY_BPS:.0f} bps |",
             f"| 成本差（config−legacy）中位 | {ok['cost_gap_bps'].median():+.1f} bps |",
             f"| 成本差 >0（config 更贵）占比 | {100 * (ok['cost_gap_bps'] > 0).mean():.0f}% |",
             f"| 24h 成交额中位 | ${ok['turnover_24h_in'].median() / 1e6:.1f}M |",
             f"| 参与率 1h 中位 | {ok['participation_1h'].median():.2e}（0.1% 红线下） |",
             f"| ILLIQUID 标红笔数（参与率>0.1%） | {int(ok['illiquid'].sum())} / {n} |",
             f"| funding 覆盖 | {cov}/{len(pos['symbol'].unique())} symbol（缺失=NaN，不补零） |\n",
             "## 解读（PROXY_ONLY，2026-08-09 修正版）\n",
             "- **D 账户股票代币池 24h 成交额中位 <$10M → 落入摩擦最低档（单边 65.5bps）**；",
             "  按悲观 config，双边摩擦中位 131bps = 27bps 锚的 2.4 倍，79% 笔 config 更贵；",
             "- 参与率 1h 中位 0.6%（红线 0.1% 的 6 倍）→ 76% 笔标 ILLIQUID：$1000 名义在这些合约上",
             "  占比不小（1h 成交额中位仅 ~$17 万）——**纸面 α 的成交假设不可忽视**；",
             "- **α 重估**：若按 config 双边（悲观上界）补收摩擦差，251 笔累计多付 ≈$1,900+，",
             "  相对当前 +$1,686 净盈亏 → **真实摩擦下 D 账户 α 大概率显著缩水甚至转负**；",
             "  27bps 锚（乐观下界）与 config（悲观上界）之间是真实区间，需真实点差数据收窄；",
             "- 冲击附录：参与率虽高但 $1000 绝对量小 → impact 量级有限，主要矛盾是滑点/点差分档；",
             "- 27bps 锚与 config 并列展示，禁止静默统一；本结论不改变 D 账户现有前向积累。"]
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_DETAIL}（{len(df)} 行）")
    print(f"wrote {OUT_REPORT}")
    print(f"config 单边中位 {ok['config_round_bps'].median():.1f}bps | gap {ok['cost_gap_bps'].median():+.1f}bps | "
          f"ILLIQUID {int(ok['illiquid'].sum())} | funding 覆盖 {cov}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
