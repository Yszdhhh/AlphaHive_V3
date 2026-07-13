"""临时调试脚本：检查 9999 泄漏"""
import sys, json
sys.path.insert(0, '.')

from harness.lib.deep_research_package import build_prompt_package
from tests.test_deep_research_package import *

# 1. test_post_cutoff_data_not_in_package
future_ts = REAL_SCAN_MS + 7200000
future_row = {
    'timestamp': future_ts,
    'open': 9999.0, 'high': 9999.0, 'low': 9999.0, 'close': 9999.0,
    'volume': 99999.0, 'turnover_usd': 999999.0,
    'funding_rate_8h': 0.999, 'open_interest': 99999.0,
    'symbol': 'ETHUSDT',
}
pkg = build_prompt_package(
    CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, CLEAN_MANIFEST, SYMBOL_META,
    SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
    SNAPSHOT_ROWS + [future_row],
    mode='HISTORICAL_REPLAY', generated_at_utc=GENERATED_AT,
)
pkg_str = json.dumps(pkg, ensure_ascii=False)

# 检查各种 999 的形式
for pattern in ['9999', '9999.0', '0.999']:
    found = pattern in pkg_str
    print(f'test_post_cutoff_data_not_in_package: "{pattern}" in package: {found}')

print(f'quality status: {pkg["quality_gate"]["status"]}')
print(f'blockers: {pkg["quality_gate"]["blockers"]}')

# 查找含 999 的位置
if '999' in pkg_str:
    lines = pkg_str.split(',')
    for i, line in enumerate(lines):
        if '999' in line and '4.199' not in line:  # 排除 4.199...
            print(f'  Line {i}: {line.strip()}')

# 2. test_future_price_999_not_in_package
ts_future = REAL_SCAN_MS + 86400000
rows_999 = SNAPSHOT_ROWS + [{
    'timestamp': ts_future, 'open': 999.0, 'high': 999.0, 'low': 999.0,
    'close': 999.0, 'volume': 1.0, 'turnover_usd': 999.0,
    'funding_rate_8h': 0.0, 'open_interest': 0.0, 'symbol': 'ETHUSDT',
}]
pkg2 = build_prompt_package(
    CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, CLEAN_MANIFEST, SYMBOL_META,
    SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
    rows_999, mode='HISTORICAL_REPLAY', generated_at_utc=GENERATED_AT,
)
pkg2_str = json.dumps(pkg2, ensure_ascii=False)
print(f'\ntest_future_price_999_not_in_package: "999" in package: {"999" in pkg2_str}')

# 3. test_cutoff_after_scan_blocks_in_replay
from harness.lib.deep_research_package import MANIFEST_CUTOFF_AFTER_SCAN
try:
    build_prompt_package(
        CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, MANIFEST_CUTOFF_AFTER_SCAN, SYMBOL_META,
        SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
        SNAPSHOT_ROWS, mode='HISTORICAL_REPLAY', generated_at_utc=GENERATED_AT,
    )
    print('\ntest_cutoff_after_scan_blocks_in_replay: NO EXCEPTION (FAIL)')
except ValueError as e:
    print(f'\ntest_cutoff_after_scan_blocks_in_replay: ValueError raised (PASS)')

# 4. test_999_not_in_package_no_cutoff
from harness.lib.deep_research_package import MANIFEST_NO_CUTOFF
ts_future = REAL_SCAN_MS + 86400000
rows_999_nc = SNAPSHOT_ROWS + [{
    'timestamp': ts_future, 'open': 999.0, 'high': 999.0, 'low': 999.0,
    'close': 999.0, 'volume': 1.0, 'turnover_usd': 999.0,
    'funding_rate_8h': 0.0, 'open_interest': 0.0, 'symbol': 'ETHUSDT',
}]
pkg3 = build_prompt_package(
    CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, MANIFEST_NO_CUTOFF, SYMBOL_META,
    SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
    rows_999_nc, mode='HISTORICAL_REPLAY', generated_at_utc=GENERATED_AT,
)
pkg3_str = json.dumps(pkg3, ensure_ascii=False)
print(f'\ntest_999_not_in_package_no_cutoff:')
print(f'  "999" in package: {"999" in pkg3_str}')
print(f'  quality status: {pkg3["quality_gate"]["status"]}')
