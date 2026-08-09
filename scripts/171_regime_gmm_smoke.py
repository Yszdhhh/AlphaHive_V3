"""171 — Regime GMM smoke: fit on BTC realized vol + simple proxy, write report.

Does NOT wire into 108. Read-only research smoke.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.lib.regime_gmm import build_feature_matrix, fit_gmm2  # noqa: E402

OUT = ROOT / "reports" / "regime_gmm_smoke.md"


def _load_btc_close() -> pd.Series | None:
    # try canonical snapshot current → any BTC path
    snap = ROOT / "harness" / "canonical_price_snapshots" / "current.json"
    if snap.exists():
        import json

        cur = json.loads(snap.read_text(encoding="utf-8"))
        # flexible: look for klines dir
        for key in ("path", "klines_dir", "version_path"):
            pass
        vdir = snap.parent / cur.get("current", cur.get("version", "v0002"))
        # current.json format may be {"version":"v0002"} or path
        if isinstance(cur, dict):
            ver = cur.get("version") or cur.get("current")
            if ver:
                vdir = snap.parent / str(ver)
        cand = list((snap.parent).glob("v*/klines/BTCUSDT.parquet"))
        if not cand:
            cand = list((snap.parent).glob("v*/klines/*BTC*.parquet"))
        if cand:
            df = pd.read_parquet(cand[-1])
            ts = pd.to_numeric(df.get("timestamp", df.get("open_time")), errors="coerce")
            close = pd.to_numeric(df["close"], errors="coerce")
            s = pd.Series(close.values, index=ts.values).dropna()
            s = s[~s.index.duplicated(keep="last")].sort_index()
            return s
    # binance free
    p = Path(r"C:\Users\10639\Desktop\加密\binance_free_db")
    for pattern in ["**/BTCUSDT*.parquet", "**/klines/**/BTCUSDT.parquet"]:
        hits = list(p.glob(pattern))
        if hits:
            df = pd.read_parquet(hits[0])
            cols = {c.lower(): c for c in df.columns}
            ts = pd.to_numeric(df[cols.get("timestamp", cols.get("open_time", list(df.columns)[0]))], errors="coerce")
            close = pd.to_numeric(df[cols.get("close", "close")], errors="coerce")
            s = pd.Series(close.values, index=ts.values).dropna().sort_index()
            return s[~s.index.duplicated(keep="last")]
    return None


def main() -> int:
    btc = _load_btc_close()
    if btc is None or len(btc) < 500:
        # synthetic fallback so CI still has a path
        rng = np.random.default_rng(2026)
        n = 2000
        vol = np.concatenate(
            [rng.normal(0.5, 0.1, n // 2), rng.normal(2.0, 0.3, n // 2)]
        )
        br = rng.normal(0, 1, n)
        X = build_feature_matrix(vol, br)
        model = fit_gmm2(X)
        post = model.posterior(X)
        src = "synthetic_fallback"
    else:
        ret = np.log(btc).diff()
        # 24h realized vol on 1h bars
        rv = ret.rolling(24).std()
        # proxy breadth: |ret| z as second feature (honest proxy when breadth unavailable)
        br = ret.abs().rolling(24).mean()
        df = pd.DataFrame({"rv": rv, "br": br}).dropna()
        X = build_feature_matrix(df["rv"].values, df["br"].values)
        model = fit_gmm2(X)
        post = model.posterior(X)
        src = f"btc_bars n={len(df)}"

    md = f"""# Regime GMM Smoke (171)

- source: {src}
- components: 2 (sorted: k1 = higher total variance = stress)
- means:
{model.means}
- vars:
{model.vars_}
- weights: {model.weights}
- n_iter: {model.n_iter}
- stress posterior mean: {float(np.mean(post)):.4f}
- stress posterior p90: {float(np.quantile(post, 0.9)):.4f}

## Usage rule

- Use as **filter / size scale** for s001 only after event-study shows lift.
- Do **not** trade the posterior itself.
- Next: join posterior asof onto wash_cvd events (script TBD, needs Owner research slot).
"""
    OUT.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
