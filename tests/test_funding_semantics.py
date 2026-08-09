"""Unit tests for funding_semantics + regime_gmm (stdlib/numpy only)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from harness.lib.funding_semantics import annotate_series, censor_summary, mark_censoring
from harness.lib.regime_gmm import build_feature_matrix, fit_gmm2


def test_mark_censoring_detects_cap():
    s = pd.Series([0.0001, 0.00005, 0.0075, -0.0075, 0.001, 0.02])
    ann = mark_censoring(s)
    assert bool(ann.loc[2, "is_capped"])
    assert bool(ann.loc[3, "is_capped"])
    assert bool(ann.loc[5, "is_capped"])
    assert not bool(ann.loc[4, "is_capped"])
    # model rate NaN when capped
    assert np.isnan(ann.loc[2, "rate_for_model"])
    assert ann.loc[4, "rate_for_model"] == 0.001


def test_structure_mode_0p0001():
    s = pd.Series([0.0001, 0.00010001, 0.0002])
    ann = mark_censoring(s)
    assert bool(ann.loc[0, "is_structure_mode"])
    summ = censor_summary(ann)
    assert summ["n"] == 3
    assert summ["n_structure_mode"] >= 1


def test_annotate_percent_unit_path():
    # percent raw ~ 0.01 means 0.01%? contract: percent then /100
    # 0.01 percent-unit → 0.0001 decimal after normalize
    # Use values that pass raw assertion: median abs ~0.01-ish scale in percent
    raw = pd.Series([0.01, 0.02, 0.015, 0.75, -0.75])  # percent units
    ann = annotate_series(raw, unit="percent")
    assert "rate_decimal" in ann.columns
    assert ann["rate_decimal"].iloc[0] == 0.0001


def test_gmm2_separates_two_blobs():
    rng = np.random.default_rng(0)
    low = rng.normal(0, 0.3, size=(80, 2))
    high = rng.normal([0, 3], [0.3, 0.5], size=(80, 2))
    X = np.vstack([low, high])
    model = fit_gmm2(X, seed=0)
    post = model.posterior(X)
    # high-var cluster should get higher mean posterior
    assert post[80:].mean() > post[:80].mean()


def test_build_feature_matrix_zscore():
    rv = np.array([1.0, 2.0, 3.0, 4.0])
    br = np.array([10.0, 10.0, 20.0, 20.0])
    X = build_feature_matrix(rv, br)
    assert X.shape == (4, 2)
    assert abs(X[:, 0].mean()) < 1e-9
