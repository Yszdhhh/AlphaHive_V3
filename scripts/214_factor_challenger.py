r"""214_factor_challenger.py — S1 挑战者：冻结 FAM-001 唯一规格（一次时间 holdout）。

S0（213）已确认放量家族有梯度（IC +0.127、单调、两段同号）。S1 的职责（codex/grok 合成版，
不用嵌套 WF）：**一次时间 holdout**——前 80% 事件只做形态选择，后 20% 只评估一次冻结规格。

候选规格（S0 预声明，config/factor_funnel.yaml forward_scores.score_vol）：
  spec_A = capped_hinge(qv24_ratio, 1.0, 2.0)   ← 部署口径（108 可算，纯函数）
  spec_B = log_ratio（signed-log + 720h robust z）
流程：
  1. 事件按时间排序 → 前 80% train / 后 20% holdout
  2. train 上按 24h 成本后净收益选形态（IC + uplift）
  3. holdout 只评估选中形态一次：uplift + 6h 事件时点聚类 bootstrap CI
  4. 验收（冻结条件）：holdout CI 下界 > 0 且 n≥30 且方向与 train 一致 → 冻结候选；
     否则 NO_GO/UNDERPOWERED（不冒充证伪）。
  5. 输出冻结规格提案（form/lo/hi/forward_start 建议），实际激活（config 置 FROZEN）由 Owner 签批。

输出：reports/challenger_volume_v1.md
用法：python scripts/214_factor_challenger.py
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

from harness.lib.event_study import forward_stats  # noqa: E402
from harness.lib.factor_funnel import capped_hinge, log_ratio_form  # noqa: E402

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
    "m213", str(PROJECT_ROOT / "scripts" / "213_factor_sandbox.py"))
m213 = importlib.util.module_from_spec(_spec3)
sys.modules["m213"] = m213
_spec3.loader.exec_module(m213)

REPORT = PROJECT_ROOT / "reports" / "challenger_volume_v1.md"
HORIZON = 24
TRAIN_FRAC = 0.8
MIN_HOLDOUT = 30
SEED = 2026
HOUR_MS = 3_600_000


def cluster_ci(diff_samples: np.ndarray, ev_ts: np.ndarray, n_boot: int = 1000,
               seed: int = SEED) -> tuple[float, float, float]:
    """6h 时点聚类 bootstrap（均值差 CI）。"""
    rng = np.random.default_rng(seed)
    buckets = (ev_ts / (6 * HOUR_MS)).astype(np.int64)
    u = np.unique(buckets)
    mean_a = np.array([diff_samples[buckets == b].mean() for b in u])
    if len(mean_a) < 3:
        return float("nan"), float("nan"), float("nan")
    point = float(mean_a.mean())
    dist = np.array([rng.choice(mean_a, size=len(mean_a), replace=True).mean() for _ in range(n_boot)])
    return point, float(np.quantile(dist, 0.025)), float(np.quantile(dist, 0.975))


def main() -> int:
    # 事件 + 原始放量 ratio（复用 213 口径，确保与 S0/部署一致）
    events, ctxs = m213.load_events()
    raw = m213.feature_vol_ratio(events)
    fwd = []
    for sym, g in events.groupby("symbol", sort=False):
        fwd.append(forward_stats(ctxs[sym], g.copy(), horizons=(HORIZON,)))
    ev = pd.concat(fwd, ignore_index=True) if fwd else events
    y = pd.to_numeric(ev[f"ret_{HORIZON}h"], errors="coerce") - 0.27
    ev["raw"] = raw.to_numpy()
    ev["y"] = y
    ev = ev.dropna(subset=["raw", "y"]).sort_values("timestamp").reset_index(drop=True)
    print(f"事件（有 raw+y）: {len(ev)}")

    # 时间切分（按事件时间，非打乱）
    n = len(ev)
    cut = int(n * TRAIN_FRAC)
    train, hold = ev.iloc[:cut].copy(), ev.iloc[cut:].copy()
    print(f"train {len(train)} / holdout {len(hold)}")

    # 形态（预声明 ≤2）
    forms = {
        "capped_hinge(1,2)": capped_hinge(train["raw"], 1.0, 2.0),
        "log_ratio": log_ratio_form(train["raw"]),
    }
    scores = {}
    for fname, f in forms.items():
        valid = pd.DataFrame({"f": f, "y": train["y"]}).dropna()
        ic = valid["f"].corr(valid["y"], method="spearman")
        med = valid["f"].median()
        up = float(valid.loc[valid["f"] >= med, "y"].mean() - valid.loc[valid["f"] < med, "y"].mean())
        scores[fname] = (ic, up, len(valid))
        print(f"  train {fname}: IC {ic:+.3f} uplift {up:+.2f}% n={len(valid)}")
    chosen = max(scores, key=lambda k: scores[k][0] if np.isfinite(scores[k][0]) else -9)
    print(f"→ 选中形态: {chosen}")

    # holdout 只评估一次
    if chosen == "capped_hinge(1,2)":
        hf = capped_hinge(hold["raw"], 1.0, 2.0)
    else:
        hf = log_ratio_form(hold["raw"])
    hv = pd.DataFrame({"f": hf, "y": hold["y"], "ts": hold["timestamp"].to_numpy(dtype=np.int64)}).dropna()
    hmed = hv["f"].median()
    hi_m, lo_m = hv["f"] >= hmed, hv["f"] < hmed
    hi_y, lo_y = hv.loc[hi_m, "y"].to_numpy(), hv.loc[lo_m, "y"].to_numpy()
    uplift = float(hi_y.mean() - lo_y.mean())
    point, lo, hi = cluster_ci(hi_y, hv.loc[hi_m, "ts"].to_numpy())
    n_h = len(hv)
    ic_h = float(hv["f"].corr(hv["y"], method="spearman"))
    verdict = "样本不足" if n_h < MIN_HOLDOUT else (
        "FROZEN_CANDIDATE" if (lo > 0 and np.sign(point) == np.sign(scores[chosen][1])) else
        "NO_GO/UNDERPOWERED")
    print(f"  holdout {chosen}: IC {ic_h:+.3f} uplift {uplift:+.2f}% "
          f"聚类CI [{lo:+.2f}, {hi:+.2f}] n={n_h} → {verdict}")

    lines = ["# S1 挑战者：FAM-001 冻结（214，一次时间 holdout）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 切分：前 {TRAIN_FRAC:.0%} train / 后 {1 - TRAIN_FRAC:.0%} holdout（按事件时间，非打乱）",
             f"- 标签：{HORIZON}h 成本后净收益；holdout 只评估选中形态一次\n",
             "## train 形态选择\n",
             "| 形态 | IC | uplift | n |",
             "|---|---|---:|---:|"]
    for fname, (ic, up, nn) in scores.items():
        lines.append(f"| {fname} | {ic:+.3f} | {up:+.2f}% | {nn} |")
    lines += ["\n## holdout 一次评估（选中形态）\n",
              f"| 形态 | IC | uplift | 6h 聚类 CI | n | 判定 |",
              "|---|---|---:|---:|---:|---|",
              f"| {chosen} | {ic_h:+.3f} | {uplift:+.2f}% | [{lo:+.2f}, {hi:+.2f}] | {n_h} | **{verdict}** |",
              "\n## 冻结提案\n",
              f"- 形态：{'capped_hinge(lo=1.0, hi=2.0)' if chosen.startswith('capped') else 'log_ratio'}",
              f"- forward_start：{'待 Owner 签批激活时取部署后首个完整 1h bar' if verdict == 'FROZEN_CANDIDATE' else '不适用'}",
              "- 激活动作（Owner 签批后）：config/factor_funnel.yaml score_vol.status → FROZEN + 填 forward_start",
              "- 激活后：108/109 自动开始标注与分桶前向积累（纯标注，不改触发/verdict/纸面）",
              "\n## 纪律\n",
              "- S1 通过只授予冻结规格资格，不授予历史结论；前向 30/60-100 事件块才是唯一确认。",
              "- 若 NO_GO/UNDERPOWERED：FAM-001 记台账后关闭，禁止换皮重测（除非新数据/新机制）。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
