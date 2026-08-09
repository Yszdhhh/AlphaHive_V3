"""Minimal 2-state Gaussian mixture for regime posterior (no sklearn).

Research-only filter for wash_cvd sizing / gating — not a trade signal.
Features should be pre-aligned, no look-ahead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class GMM2:
    """Diagonal 2-component GMM fitted by EM."""

    means: np.ndarray  # (2, d)
    vars_: np.ndarray  # (2, d)  per-dim variance
    weights: np.ndarray  # (2,)
    n_iter: int = 0

    def posterior(self, X: np.ndarray) -> np.ndarray:
        """Return P(k=1 | x) for the *higher-variance* component (stress state).

        Component labels: after fit we sort so k=1 is higher mean total variance.
        """
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        logp = np.zeros((len(X), 2))
        for k in range(2):
            var = np.maximum(self.vars_[k], 1e-12)
            # log N
            logp[:, k] = (
                np.log(max(self.weights[k], 1e-12))
                - 0.5 * np.sum(np.log(2 * np.pi * var))
                - 0.5 * np.sum((X - self.means[k]) ** 2 / var, axis=1)
            )
        # stable softmax
        m = logp.max(axis=1, keepdims=True)
        p = np.exp(logp - m)
        p = p / p.sum(axis=1, keepdims=True)
        return p[:, 1]  # stress = component 1


def fit_gmm2(
    X: np.ndarray,
    *,
    max_iter: int = 50,
    tol: float = 1e-5,
    seed: int = 2026,
) -> GMM2:
    """Fit 2-component diagonal GMM. X shape (n, d)."""
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    mask = np.isfinite(X).all(axis=1)
    X = X[mask]
    n, d = X.shape
    if n < 20:
        raise ValueError(f"need >=20 finite rows, got {n}")

    rng = np.random.default_rng(seed)
    # init: split by first feature median
    med = np.median(X[:, 0])
    z = (X[:, 0] >= med).astype(float)
    means = np.vstack([X[z < 0.5].mean(axis=0), X[z >= 0.5].mean(axis=0)])
    vars_ = np.vstack(
        [
            np.maximum(X[z < 0.5].var(axis=0), 1e-6),
            np.maximum(X[z >= 0.5].var(axis=0), 1e-6),
        ]
    )
    weights = np.array([1 - z.mean(), z.mean()])
    weights = np.maximum(weights, 0.05)
    weights /= weights.sum()

    prev_ll = -np.inf
    for it in range(max_iter):
        # E
        logp = np.zeros((n, 2))
        for k in range(2):
            var = np.maximum(vars_[k], 1e-12)
            logp[:, k] = (
                np.log(weights[k])
                - 0.5 * np.sum(np.log(2 * np.pi * var))
                - 0.5 * np.sum((X - means[k]) ** 2 / var, axis=1)
            )
        m = logp.max(axis=1, keepdims=True)
        resp = np.exp(logp - m)
        resp /= resp.sum(axis=1, keepdims=True)
        # M
        nk = resp.sum(axis=0) + 1e-12
        weights = nk / n
        means = (resp.T @ X) / nk[:, None]
        for k in range(2):
            diff = X - means[k]
            vars_[k] = np.maximum((resp[:, k][:, None] * diff**2).sum(axis=0) / nk[k], 1e-6)
        ll = float((m.ravel() + np.log(resp.sum(axis=1) + 1e-300)).sum())
        if abs(ll - prev_ll) < tol * (1 + abs(prev_ll)):
            break
        prev_ll = ll

    # sort: component 1 = higher total variance (stress / high-vol)
    tot_var = vars_.sum(axis=1)
    order = np.argsort(tot_var)  # low var first
    means = means[order]
    vars_ = vars_[order]
    weights = weights[order]
    return GMM2(means=means, vars_=vars_, weights=weights, n_iter=it + 1)


def stress_posterior(
    features: np.ndarray,
    model: Optional[GMM2] = None,
    *,
    fit: bool = True,
) -> tuple[np.ndarray, GMM2]:
    """Convenience: fit if needed, return P(stress) and model."""
    if model is None:
        if not fit:
            raise ValueError("model required when fit=False")
        model = fit_gmm2(features)
    return model.posterior(features), model


def build_feature_matrix(
    realized_vol: np.ndarray,
    breadth_or_proxy: np.ndarray,
) -> np.ndarray:
    """Two-feature matrix; both same length. Z-score columns for scale."""
    rv = np.asarray(realized_vol, dtype=float)
    br = np.asarray(breadth_or_proxy, dtype=float)
    X = np.column_stack([rv, br])
    mu = np.nanmean(X, axis=0)
    sd = np.nanstd(X, axis=0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    return (X - mu) / sd
