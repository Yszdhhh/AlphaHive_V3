import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_ranked_candidates_and_reference_benchmarks_are_explicit_and_disjoint():
    config = json.loads((PROJECT_ROOT / "config" / "universe.json").read_text(encoding="utf-8"))
    symbols = config["symbols"]
    candidates = [item["symbol"] for item in symbols]
    benchmarks = config["benchmark_symbols"]
    disabled = config["disabled_pull_symbols"]

    assert len(candidates) == 66
    assert len(set(candidates)) == len(candidates)
    assert all(10 <= item["rank"] <= 80 for item in symbols)
    assert len(benchmarks) == 3
    assert set(candidates).isdisjoint(benchmarks)
    assert set(disabled).issubset(candidates)
    assert len(set(candidates) - set(disabled) | set(benchmarks)) == 59
    assert benchmarks == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
