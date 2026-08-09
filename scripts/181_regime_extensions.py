r"""181_regime_extensions.py — B4+B5+B6：DXY/VIX_SYNTH 分层 + GMM 3 状态 + meme×Mayer。

三个补测合并（全部零成本，本地数据）：
B4：wash_cvd × DXY（美元强弱）/ VIX_SYNTH 分层——宏观维度补全（scout 未用维度）
B5：GMM 3 状态（低波/中波/高波）× wash_cvd——175 只测了 2 状态
B6：meme 池 × Mayer 周期交互——166 只测了新币池

输出：reports/regime_extensions.md
用法：python scripts/181_regime_extensions.py
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

REPORT = PROJECT_ROOT / "reports" / "regime_extensions.md"
MACRO = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026
MEME_POOL = {"DOGEUSDT", "1000PEPEUSDT", "FARTCOINUSDT", "1000BONKUSDT", "PENGUUSDT",
             "PUMPUSDT", "WIFUSDT", "TRUMPUSDT", "VIRTUALUSDT", "WLFIUSDT",
             "SPCXUSDT", "ESPORTSUSDT"}


def gmm_kstate(x: np.ndarray, k: int, iters: int = 300) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = len(x)
    mu = np.quantile(x, np.linspace(1 / (k + 1), k / (k + 1), k))
    sigma = np.full(k, x.std())
    pi = np.full(k, 1 / k)
    for _ in range(iters):
        logl = np.empty((n, k))
        for j in range(k):
            logl[:, j] = np.log(pi[j]) - 0.5 * np.log(2 * np.pi * sigma[j] ** 2) \
                - (x - mu[j]) ** 2 / (2 * sigma[j] ** 2)
        logl -= logl.max(axis=1, keepdims=True)
        post = np.exp(logl)
        post /= post.sum(axis=1, keepdims=True)
        nk = post.sum(axis=0) + 1e-9
        pi = nk / n
        mu = (post * x[:, None]).sum(axis=0) / nk
        sigma = np.sqrt((post * (x[:, None] - mu) ** 2).sum(axis=0) / nk) + 1e-9
    return mu, sigma, pi, post


def load_events() -> tuple[pd.DataFrame, dict, dict]:
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
    return events, ctxs, fundings


def main() -> int:
    events, ctxs, fundings = load_events()
    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# regime 扩展补测（181：B4 DXY/VIX_SYNTH + B5 GMM3 + B6 meme×Mayer）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n < MIN_EVENTS:
            lines.append(f"| {label} | {n} | - | - | - | 样本不足 |")
            print(f"[181] {label}: n={n} 样本不足")
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
        print(f"[181] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    # ---------- B4：DXY / VIX_SYNTH 分层 ----------
    ev_day = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_localize(None).normalize()
    for fname, col in [("DXY.parquet", "dxy"), ("VIX_SYNTH.parquet", "vsyn")]:
        p = MACRO / fname
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        idx = pd.to_datetime(d.index) if not isinstance(d.index, pd.DatetimeIndex) else d.index
        s = pd.Series(pd.to_numeric(d["close"], errors="coerce").to_numpy(), index=idx).dropna()
        events[col] = ev_day.map(s).to_numpy()
    lines.append("\n## B4：宏观未用维度 × wash_cvd\n")
    lines.append("| 组 | n | 168h 超额 | CI | 中位数 | 尾切 | 判定 |")
    lines.append("|---|---|---:|---:|---:|---:|---|")
    if "dxy" in events.columns:
        med_d = events["dxy"].median()
        row("DXY 高（美元强）", events[events["dxy"] >= med_d])
        row("DXY 低（美元弱）", events[events["dxy"] < med_d])
    else:
        lines.append("| DXY 缺失 | - | - | - | - | - | |")
    if "vsyn" in events.columns:
        med_v = events["vsyn"].median()
        row("VIX_SYNTH 高", events[events["vsyn"] >= med_v])
        row("VIX_SYNTH 低", events[events["vsyn"] < med_v])
    else:
        lines.append("| VIX_SYNTH 缺失 | - | - | - | - | - | |")

    # ---------- B5：GMM 3 状态 ----------
    p = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    df = pd.read_parquet(p, columns=["open_time", "close"])
    ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    cl = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
    s = pd.Series(cl, index=pd.Index(ts))
    s = s[~s.index.duplicated(keep="last")].sort_index()
    ret = s.pct_change(4).dropna()
    x = ret.to_numpy(dtype=float)
    x = x[np.isfinite(x)]
    mu, sigma, pi, post = gmm_kstate(x, 3)
    hi_state = int(np.argmax(sigma))
    lo_state = int(np.argmin(sigma))
    mid_state = 3 - hi_state - lo_state
    lines.append("\n## B5：GMM 3 状态 × wash_cvd（175 扩展）\n")
    lines.append(f"- 状态：低波 σ={sigma[lo_state]:.4f}（{pi[lo_state]:.0%}）/ 中波 σ={sigma[mid_state]:.4f}"
                 f"（{pi[mid_state]:.0%}）/ 高波 σ={sigma[hi_state]:.4f}（{pi[hi_state]:.0%}）\n")
    lines.append("| 组 | n | 168h 超额 | CI | 中位数 | 尾切 | 判定 |")
    lines.append("|---|---|---:|---:|---:|---:|---|")
    post_idx = ret.index.to_numpy(dtype=np.int64)
    pos = np.searchsorted(post_idx, events["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
    pos = np.clip(pos, 0, len(post) - 1)
    events["gmm_state"] = np.argmax(post[pos], axis=1)
    events["p_hi"] = post[pos, hi_state]
    row("GMM 高波（P≥0.5）", events[events["p_hi"] >= 0.5])
    row("GMM 中波", events[events["gmm_state"] == mid_state])
    row("GMM 低波", events[events["gmm_state"] == lo_state])

    # ---------- B6：meme 池 × Mayer ----------
    lines.append("\n## B6：meme 池 × BTC 周期（166 只测了新币池）\n")
    lines.append("| 组 | n | 168h 超额 | CI | 中位数 | 尾切 | 判定 |")
    lines.append("|---|---|---:|---:|---:|---:|---|")
    mem = events[events["symbol"].isin(MEME_POOL)]
    p2 = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    df2 = pd.read_parquet(p2, columns=["open_time", "close"])
    ts2 = pd.to_numeric(df2["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    cl2 = pd.to_numeric(df2["close"], errors="coerce").to_numpy(dtype=float)
    s2 = pd.Series(cl2, index=pd.Index(ts2))
    s2 = s2[~s2.index.duplicated(keep="last")].sort_index()
    s2.index = pd.to_datetime(s2.index, unit="ms", utc=True).tz_localize(None)
    daily = s2.groupby(s2.index.normalize()).last()
    ma200 = daily.rolling(200, min_periods=120).mean()
    mayer = daily / ma200.replace(0, np.nan)
    mem["mayer"] = pd.to_datetime(mem["timestamp"].to_numpy(), unit="ms", utc=True).tz_localize(None).normalize().map(mayer).to_numpy()
    mem_u = mem[mem["mayer"].notna()]
    row("meme 全", mem_u)
    row("meme × 熊市（Mayer<0.8）", mem_u[mem_u["mayer"] < 0.8])
    row("meme × 中部", mem_u[(mem_u["mayer"] >= 0.8) & (mem_u["mayer"] <= 1.5)])
    row("meme × 牛市（Mayer>1.5）", mem_u[mem_u["mayer"] > 1.5])

    lines.extend(["\n## 解读\n",
                   "- B4：DXY 分层显著 → 美元强弱调制 wash_cvd（宏观维度新增门控候选）。",
                   "- B5：3 状态高波显著强于低波 → GMM 状态门控有效；无差异 → 与 175 一致（币级内生）。",
                   "- B6：meme 熊市/牛市分化 → 与 164 成熟池一致或相反（meme 是新币还是成熟行为）。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
