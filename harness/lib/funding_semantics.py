"""Funding measurement semantics — censoring, settlement, model-safe rates.

Extends unit normalization (funding_normalize) with StepOneAi-style caveats:
rate series are exchange *measurements* with hard caps (censoring), not raw
premium pressure. Research-only; no order path.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import yaml

from harness.lib.funding_normalize import funding_sampling_policy, normalize_funding

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEASURE_PATH = PROJECT_ROOT / "config" / "funding_measurement.yaml"


def load_measurement_config(path: Optional[Path] = None) -> dict[str, Any]:
    p = Path(path) if path else MEASURE_PATH
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _binance_cfg(cfg: Optional[dict] = None) -> dict[str, Any]:
    cfg = cfg or load_measurement_config()
    return cfg["exchanges"]["binance_usdm"]


def settlement_hours(symbol: str = "*", cfg: Optional[dict] = None) -> int:
    """Return settlement period hours; default from measurement config / data_contracts."""
    b = _binance_cfg(cfg)
    # per-symbol overrides via parameter_change_log not yet automated
    h = int(b.get("default_settlement_hours", 8))
    if h <= 0:
        h = int(funding_sampling_policy()["settlement_period_hours"])
    return h


def _near_level(x: np.ndarray, level: float, rel_tol: float, abs_tol: float) -> np.ndarray:
    thr = max(abs(level) * rel_tol, abs_tol)
    return np.abs(x - level) <= thr


def mark_censoring(
    rates_decimal: pd.Series,
    *,
    cfg: Optional[dict] = None,
) -> pd.DataFrame:
    """Annotate each observation: is_capped, nearest_cap, is_structure_mode.

    Input must already be **decimal per settlement** (binance free history is;
    coinglass percent must go through normalize_funding first).
    """
    b = _binance_cfg(cfg)
    caps = [float(c) for c in b.get("candidate_cap_levels_decimal", [])]
    modes = [float(m) for m in b.get("structure_modes_decimal", [])]
    rel = float(b.get("cap_match_rel_tol", 0.02))
    atol = float(b.get("cap_match_abs_tol", 1e-6))

    vals = pd.to_numeric(rates_decimal, errors="coerce").to_numpy(dtype=float)
    n = len(vals)
    is_capped = np.zeros(n, dtype=bool)
    nearest_cap = np.full(n, np.nan)
    is_mode = np.zeros(n, dtype=bool)

    for i, v in enumerate(vals):
        if not np.isfinite(v):
            continue
        # match ±cap levels
        for c in caps:
            if _near_level(np.array([v]), c, rel, atol)[0] or _near_level(
                np.array([v]), -c, rel, atol
            )[0]:
                is_capped[i] = True
                nearest_cap[i] = c if abs(v - c) <= abs(v + c) else -c
                break
        for m in modes:
            if _near_level(np.array([v]), m, rel, atol)[0] or _near_level(
                np.array([v]), -m, rel, atol
            )[0]:
                is_mode[i] = True
                break

    out = pd.DataFrame(
        {
            "rate_decimal": vals,
            "is_capped": is_capped,
            "nearest_cap": nearest_cap,
            "is_structure_mode": is_mode,
            # true pressure unknown when capped (censoring)
            "rate_for_model": np.where(is_capped, np.nan, vals),
        }
    )
    return out


def annotate_series(
    rates: pd.Series,
    *,
    unit: str = "decimal",
    cfg: Optional[dict] = None,
) -> pd.DataFrame:
    """Full annotation pipeline. unit: 'decimal' | 'percent' (coinglass raw)."""
    if unit == "percent":
        dec = normalize_funding(rates)
    elif unit == "decimal":
        dec = pd.to_numeric(rates, errors="coerce")
    else:
        raise ValueError(f"unsupported unit: {unit}")
    ann = mark_censoring(dec, cfg=cfg)
    ann.index = rates.index
    return ann


def censor_summary(ann: pd.DataFrame) -> dict[str, Any]:
    n = len(ann)
    if n == 0:
        return {"n": 0}
    capped = int(ann["is_capped"].sum())
    modes = int(ann["is_structure_mode"].sum())
    r = ann["rate_decimal"]
    return {
        "n": n,
        "n_capped": capped,
        "pct_capped": capped / n * 100.0,
        "n_structure_mode": modes,
        "pct_structure_mode": modes / n * 100.0,
        "median_abs": float(r.abs().median()) if r.notna().any() else float("nan"),
        "max": float(r.max()) if r.notna().any() else float("nan"),
        "min": float(r.min()) if r.notna().any() else float("nan"),
        "note": "capped rows must not enter OLS / extreme quantile training as true pressure",
    }


def load_binance_funding_parquet(path: Path) -> pd.DataFrame:
    """Load binance_free_db funding file → standard columns."""
    df = pd.read_parquet(path)
    ts_col = "fundingTime" if "fundingTime" in df.columns else "timestamp"
    rate_col = "fundingRate" if "fundingRate" in df.columns else "close"
    out = pd.DataFrame(
        {
            "timestamp": pd.to_numeric(df[ts_col], errors="coerce").astype("int64"),
            "rate_decimal": pd.to_numeric(df[rate_col], errors="coerce"),
        }
    )
    if "rateType" in df.columns:
        out["rate_type"] = df["rateType"].astype(str)
    return out.dropna(subset=["timestamp", "rate_decimal"]).reset_index(drop=True)
