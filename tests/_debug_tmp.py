"""临时调试脚本：精确检查 9999 泄漏"""
import sys, json, os
sys.path.insert(0, '.')
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from harness.lib.deep_research_package import build_prompt_package, render_research_prompt
from tests.test_deep_research_package import *

# test 1: post_cutoff_data_not_in_package
future_ts = REAL_SCAN_MS + 7200000
future_row = {
    "timestamp": future_ts,
    "open": 9999.0, "high": 9999.0, "low": 9999.0, "close": 9999.0,
    "volume": 99999.0, "turnover_usd": 999999.0,
    "funding_rate_8h": 0.999, "open_interest": 99999.0,
    "symbol": "ETHUSDT",
}
pkg = build_prompt_package(
    CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, CLEAN_MANIFEST, SYMBOL_META,
    SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
    SNAPSHOT_ROWS + [future_row],
    mode="HISTORICAL_REPLAY", generated_at_utc=GENERATED_AT,
)
pkg_str = json.dumps(pkg, ensure_ascii=False)

# 精确查找 9999
idx = pkg_str.find("9999")
if idx >= 0:
    print(f"Found 9999 at index {idx}:")
    print(pkg_str[max(0,idx-100):idx+200])
else:
    print("9999 not found in package (PASS)")

# 精确查找 0.999
idx2 = pkg_str.find("0.999")
if idx2 >= 0:
    print(f"Found 0.999 at index {idx2}:")
    print(pkg_str[max(0,idx2-100):idx2+200])
else:
    print("0.999 not found in package (PASS)")

print(f"3500.0 in pkg: {'3500.0' in pkg_str}")
print(f"quality status: {pkg['quality_gate']['status']}")

# test 2: future_price_999_not_in_package
ts_future2 = REAL_SCAN_MS + 86400000
rows_999 = SNAPSHOT_ROWS + [{
    "timestamp": ts_future2, "open": 999.0, "high": 999.0, "low": 999.0,
    "close": 999.0, "volume": 1.0, "turnover_usd": 999.0,
    "funding_rate_8h": 0.0, "open_interest": 0.0, "symbol": "ETHUSDT",
}]
pkg2 = build_prompt_package(
    CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, CLEAN_MANIFEST, SYMBOL_META,
    SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
    rows_999, mode="HISTORICAL_REPLAY", generated_at_utc=GENERATED_AT,
)
pkg2_str = json.dumps(pkg2, ensure_ascii=False)
print(f"\ntest_future_price_999_not_in_package:")
print(f"  '999' in pkg: {'999' in pkg2_str}")

# test 3: cutoff_after_scan_blocks_in_replay
from harness.lib.deep_research_package import MANIFEST_CUTOFF_AFTER_SCAN
try:
    build_prompt_package(
        CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, MANIFEST_CUTOFF_AFTER_SCAN, SYMBOL_META,
        SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
        SNAPSHOT_ROWS, mode="HISTORICAL_REPLAY", generated_at_utc=GENERATED_AT,
    )
    print("\ntest_cutoff_after_scan_blocks_in_replay: NO EXCEPTION (FAIL)")
except ValueError as e:
    print(f"\ntest_cutoff_after_scan_blocks_in_replay: ValueError raised (PASS)")

# test 4: 999_not_in_package_no_cutoff
from harness.lib.deep_research_package import MANIFEST_NO_CUTOFF
ts_future3 = REAL_SCAN_MS + 86400000
rows_999_nc = SNAPSHOT_ROWS + [{
    "timestamp": ts_future3, "open": 999.0, "high": 999.0, "low": 999.0,
    "close": 999.0, "volume": 1.0, "turnover_usd": 999.0,
    "funding_rate_8h": 0.0, "open_interest": 0.0, "symbol": "ETHUSDT",
}]
pkg3 = build_prompt_package(
    CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, MANIFEST_NO_CUTOFF, SYMBOL_META,
    SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
    rows_999_nc, mode="HISTORICAL_REPLAY", generated_at_utc=GENERATED_AT,
)
pkg3_str = json.dumps(pkg3, ensure_ascii=False)
print(f"\ntest_999_not_in_package_no_cutoff:")
print(f"  '999' in pkg: {'999' in pkg3_str}")
print(f"  quality: {pkg3['quality_gate']['status']}")
