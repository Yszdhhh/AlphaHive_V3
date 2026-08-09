r"""175_regime_gmm.py — A2：GMM 多状态 regime × wash_cvd（外部调研 A2 + 豪仔 GMM 提示）。

假设：2-3 个市场状态（低波盘整 / 高波趋势 / 尾部）下 wash_cvd 期望显著不同。
方法（手动 EM，无 sklearn 依赖）：
1. BTC 4h 收益序列 → 2 状态 GMM（状态 0 = 低波、状态 1 = 高波）
2. wash_cvd 事件时点 → 状态后验 P(高波)
3. 分层：P(高波) ≥ 0.5（高波状态）vs < 0.5（低波状态）→ 168h 超额对比
4. 门槛 G：CI / 中位数 / 尾切

输出：reports/regime_gmm.md
用法：python scripts/175_regime_gmm.py
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

from harness.lib.event_study import (  # noqa: E402
    DEFAULT_HORIZONS,
    bootstrap_ci,
    draw_random_events,
    forward_stats,
)

REPORT = PROJECT_ROOT / "reports" / "regime_gmm.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026


def gmm_2state(x: np.ndarray, iters: int = 200) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """2 状态高斯混合 EM。x: 收益序列。返回 (mu, sigma, pi, post)。"""
    mu = np.array([np.quantile(x, 0.3), np.quantile(x, 0.7)])
    sigma = np.array([x.std(), x.std() * 2])
    pi = np.array([0.7, 0.3])
    n = len(x)
    for _ in range(iters):
        # E 步
        logl = np.empty((n, 2))
        for k in range(2):
            logl[:, k] = np.log(pi[k]) - 0.5 * np.log(2 * np.pi * sigma[k] ** 2) \
                - (x - mu[k]) ** 2 / (2 * sigma[k] ** 2)
        logl -= logl.max(axis=1, keepdims=True)
        post = np.exp(logl)
        post /= post.sum(axis=1, keepdims=True)
        # M 步
        nk = post.sum(axis=0) + 1e-9
        pi = nk / n
        mu = (post * x[:, None]).sum(axis=0) / nk
        sigma = np.sqrt((post * (x[:, None] - mu) ** 2).sum(axis=0) / nk) + 1e-9
    return mu, sigma, pi, post


def main() -> int:
    # BTC 4h 收益
    p = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    df = pd.read_parquet(p, columns=["open_time", "close"])
    ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    cl = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
    s = pd.Series(cl, index=pd.Index(ts))
    s = s[~s.index.duplicated(keep="last")].sort_index()
    ret = s.pct_change(4).dropna()
    x = ret.to_numpy(dtype=float)
    x = x[np.isfinite(x)]
    mu, sigma, pi, post = gmm_2state(x)
    hi_state = int(np.argmax(sigma))
    lo_state = 1 - hi_state
    print(f"GMM 状态: mu={mu.round(5)} sigma={sigma.round(5)} pi={pi.round(3)}")
    print(f"高波状态 = 状态{hi_state}（sigma {sigma[hi_state]:.4f}），占 {pi[hi_state]:.1%}")

    # 事件时点后验
    post_idx = ret.index.to_numpy(dtype=np.int64)
    post_hi = post[:, hi_state]

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
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)].copy()
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        if sym in ctxs:
            fwd_parts.append(forward_stats(ctxs[sym], g.copy(), DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events

    # 事件时点 asof 后验（BTC 4h 网格）
    pos = np.searchsorted(post_idx, events["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
    pos = np.clip(pos, 0, len(post_hi) - 1)
    events["p_hi"] = post_hi[pos]
    usable = events[events["p_hi"].notna()].copy()
    print(f"wash_cvd {len(events)} | 有 regime {len(usable)}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# A2：GMM 多状态 regime × wash_cvd（175）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- BTC 4h 收益 2 状态 GMM：高波 σ={sigma[hi_state]:.4f} 占 {pi[hi_state]:.1%} / 低波 σ={sigma[lo_state]:.4f}",
             "- 事件时点后验 P(高波) 分层；基线：随机横截面；门槛 G\n",
             "| 组 | n | 168h 超额 | CI | 中位数 | 尾切 | 判定 |",
             "|---|---|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n < MIN_EVENTS:
            lines.append(f"| {label} | {n} | - | - | - | - | 样本不足 |")
            return
        r = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().to_numpy()
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        thr = np.quantile(r, 0.95)
        tail = r[r <= thr].mean()
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% "
                     f"| {tail:+.2f}% | **{verdict}** |")
        print(f"[175] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    row("wash_cvd 全（锚）", usable)
    row("高波状态（P≥0.5）", usable[usable["p_hi"] >= 0.5])
    row("低波状态（P<0.5）", usable[usable["p_hi"] < 0.5])
    row("高波强（P≥0.8）", usable[usable["p_hi"] >= 0.8])

    lines.extend(["\n## 解读\n",
                   "- 高波状态显著强于低波 → GMM regime 门控有效（wash_cvd 是高波状态策略，低波少做）。",
                   "- 无差异 → 状态不影响 wash_cvd（与 120 宏观结论一致：币级内生）。",
                   "- 与 164 周期门控（Mayer）对比：GMM 是短周期状态、Mayer 是长周期位置，可叠加。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
