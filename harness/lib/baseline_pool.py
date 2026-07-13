"""Baseline pool construction and diversity checks."""
from __future__ import annotations

import math
from collections import Counter

import pandas as pd


def build_candidate_pool(candidates_df: pd.DataFrame) -> list[str]:
    return sorted(candidates_df["symbol"].dropna().astype(str).unique().tolist())


def build_full_pool(symbol_meta: pd.DataFrame, min_turnover_usd: float) -> list[str]:
    eligible = symbol_meta[
        pd.to_numeric(symbol_meta["turnover_24h_usd_effective"], errors="coerce")
        >= min_turnover_usd
    ]
    return sorted(eligible["symbol"].dropna().astype(str).unique().tolist())


def pool_diversity(symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {"unique": 0, "max_share": 0.0, "entropy_ratio": 0.0}
    counts = Counter(symbols)
    total = sum(counts.values())
    probs = [count / total for count in counts.values()]
    entropy = -sum(p * math.log(p) for p in probs if p > 0)
    unique = len(counts)
    entropy_ratio = entropy / math.log(unique) if unique > 1 else 0.0
    return {
        "unique": unique,
        "max_share": max(probs),
        "entropy_ratio": entropy_ratio,
    }


def pool_status(metrics: dict[str, float], rules: dict) -> str:
    if metrics["unique"] < int(rules["min_unique_symbols_candidate_pool"]):
        return "insufficient_pool"
    if metrics["max_share"] > float(rules["max_single_symbol_share"]):
        return "insufficient_pool"
    if metrics["entropy_ratio"] < float(rules["min_shannon_entropy_ratio"]):
        return "insufficient_pool"
    return "ok"
