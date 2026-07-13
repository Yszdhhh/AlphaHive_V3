"""
05_update_returns.py — AlphaHive V3.1.1 Phase 1
================================================
事后回填 4h/24h/72h/7d 方向性超额收益。

铁律:
1. Anomaly_Ledger 写分周期列：exit_price_ref_4h/24h/72h/7d, btc_exit_price_4h/24h/72h/7d, dir_excess_ret_*_4h/24h/72h/7d, dir_excess_ret_net_*_4h/24h/72h/7d
2. Baseline_Ledger 写非分周期列：exit_price_ref, btc_exit_price, dir_excess_ret, dir_excess_ret_net
3. 只用独立 return_tape.csv 回填收益，不扩写 frozen input_snapshot.csv
4. 未到期的持仓期填 NaN
5. AutoSkipped (sign=0) 收益标记清楚，不计入 DoD
6. Anomaly funding_cost_component 留 NaN（无 holding_period_hours），05 按周期计算 net 时逐期扣 funding
7. Baseline funding_cost_component 来自 04，按其 holding_period_hours 已正确计算
"""

import argparse
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# === 路径配置 ===
PROJECT_ROOT = Path(r"G:\Quant test\AlphaHive_V3")
sys.path.insert(0, str(PROJECT_ROOT))
from harness.lib.funding_normalize import assert_normalized_funding
LEDGER_DIR = PROJECT_ROOT / "ledger"
RUNS_DIR = PROJECT_ROOT / "harness" / "runs"
ANOMALY_LEDGER = LEDGER_DIR / "Anomaly_Ledger.csv"
BASELINE_LEDGER = LEDGER_DIR / "Baseline_Ledger.csv"

# 持仓期配置（小时）
HOLDING_PERIODS = {
    "4h": 4,
    "24h": 24,
    "72h": 72,
    "168h": 168,  # 7d
}

# Anomaly_Ledger 列名映射（分周期）
ANOMALY_ENTRY_COL = "entry_price_ref"
ANOMALY_BTC_ENTRY_COL = "btc_entry_price"
ANOMALY_EXIT_COLS = {
    4: "exit_price_ref_4h", 24: "exit_price_ref_24h",
    72: "exit_price_ref_72h", 168: "exit_price_ref_7d",
}
ANOMALY_BTC_EXIT_COLS = {
    4: "btc_exit_price_4h", 24: "btc_exit_price_24h",
    72: "btc_exit_price_72h", 168: "btc_exit_price_7d",
}
ANOMALY_DIR_COLS = {
    4: "dir_excess_ret_4h", 24: "dir_excess_ret_24h",
    72: "dir_excess_ret_72h", 168: "dir_excess_ret_7d",
}
ANOMALY_NET_COLS = {
    4: "dir_excess_ret_net_4h", 24: "dir_excess_ret_net_24h",
    72: "dir_excess_ret_net_72h", 168: "dir_excess_ret_net_7d",
}

# Baseline_Ledger 列名映射（非分周期，每条 baseline 只有一个 holding_period）
BASELINE_ENTRY_COL = "entry_price_ref"
BASELINE_BTC_ENTRY_COL = "btc_entry_price"
BASELINE_EXIT_COL = "exit_price_ref"
BASELINE_BTC_EXIT_COL = "btc_exit_price"
BASELINE_DIR_COL = "dir_excess_ret"
BASELINE_NET_COL = "dir_excess_ret_net"

BTC_SYMBOL = "BTCUSDT"


def ms_to_dt(ms: int) -> pd.Timestamp:
    return pd.to_datetime(ms, unit="ms", utc=True)


def dt_to_ms(dt) -> int:
    return int(pd.Timestamp(dt).value / 1e6)


def load_return_tape(run_id: str) -> pd.DataFrame:
    path = RUNS_DIR / run_id / "return_tape.csv"
    if not path.exists():
        raise SystemExit(f"return_tape.csv missing for {run_id}; run 06_build_return_tape.py first")
    df = pd.read_csv(path)
    df["timestamp_ms"] = df["timestamp"]
    return df


def find_entry_bar(snapshot_df, scan_time, symbol):
    """
    找 scan_time 后第一根完整 K 线。
    若 scan_time 在数据末尾之后（snapshot 冻结早于 scan），返回 scan_after_data。
    不允许用 scan 前最后一根 K 线作为 entry。
    """
    symbol_df = snapshot_df[snapshot_df["symbol"] == symbol]
    if symbol_df.empty:
        return None, "symbol_not_found"
    symbol_df = symbol_df.sort_values("timestamp_ms")
    scan_ms = dt_to_ms(scan_time)
    latest_ms = symbol_df["timestamp_ms"].max()

    if scan_ms > latest_ms:
        return None, "scan_after_data"

    for _, row in symbol_df.iterrows():
        if row["timestamp_ms"] >= scan_ms:
            return row, "found"

    return None, "scan_after_data"


def find_exit_bar(snapshot_df, entry_row, holding_hours, symbol):
    symbol_df = snapshot_df[snapshot_df["symbol"] == symbol]
    if symbol_df.empty:
        return None, "symbol_not_found"
    symbol_df = symbol_df.sort_values("timestamp_ms")
    target_ms = entry_row["timestamp_ms"] + holding_hours * 3600 * 1000
    for _, row in symbol_df.iterrows():
        if row["timestamp_ms"] >= target_ms:
            return row, "found"
    return None, "no_data_for_period"


def get_btc_price(snapshot_df, timestamp_ms):
    btc_df = snapshot_df[snapshot_df["symbol"] == BTC_SYMBOL].sort_values("timestamp_ms")
    if btc_df.empty:
        return None
    exact = btc_df[btc_df["timestamp_ms"] == timestamp_ms]
    if not exact.empty:
        return float(exact.iloc[0]["open"])
    for _, row in btc_df.iterrows():
        if row["timestamp_ms"] >= timestamp_ms:
            return float(row["open"])
    return None


def calc_dir_excess(entry, exit_price, btc_entry, btc_exit, direction_sign):
    if direction_sign == 0:
        return 0.0
    symbol_ret = (exit_price - entry) / entry
    btc_ret = (btc_exit - btc_entry) / btc_entry if btc_entry > 0 else 0.0
    return direction_sign * (symbol_ret - btc_ret)


def parse_direction_sign(value) -> int:
    """CSV round-trips can turn 1/-1 into 1.0/-1.0 strings."""
    if value is None or pd.isna(value) or value == "":
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def calc_funding_cost_for_period(funding_rate_8h, holding_hours, direction_sign):
    """按指定 holding_hours 计算 funding cost。"""
    if direction_sign == 0 or pd.isna(funding_rate_8h) or funding_rate_8h == 0:
        return 0.0
    return direction_sign * (holding_hours / 8.0) * funding_rate_8h


def process_anomaly_record(record, snapshot_df, friction):
    """
    处理 Anomaly 记录 → 返回分周期列的 dict。

    Anomaly 没有 holding_period_hours，需要按 4/24/72/168 分别计算：
    - exit_price_ref_Nh
    - btc_exit_price_Nh
    - dir_excess_ret_Nh
    - dir_excess_ret_net_Nh（含该周期的 funding cost）
    """
    symbol = record["symbol"]
    scan_time = pd.to_datetime(record.get("scan_time_utc", ""), utc=True)
    direction_sign = parse_direction_sign(record.get("direction_sign", 0))
    funding_rate_8h = record.get("funding_rate_8h_decimal", record.get("funding_rate_8h", 0.0))
    if pd.isna(funding_rate_8h):
        funding_rate_8h = 0.0
    friction_decimal = friction / 1e4 if friction else 0.0

    result = {
        ANOMALY_ENTRY_COL: None,
        ANOMALY_BTC_ENTRY_COL: None,
    }
    for period_h in [4, 24, 72, 168]:
        result[ANOMALY_EXIT_COLS[period_h]] = None
        result[ANOMALY_DIR_COLS[period_h]] = None
        result[ANOMALY_NET_COLS[period_h]] = None

    entry_row, entry_status = find_entry_bar(snapshot_df, scan_time, symbol)
    if entry_status != "found":
        return result

    entry_price = entry_row["open"]
    entry_ts = entry_row["timestamp_ms"]
    result[ANOMALY_ENTRY_COL] = entry_price

    btc_entry_price = get_btc_price(snapshot_df, entry_ts)
    if btc_entry_price:
        result[ANOMALY_BTC_ENTRY_COL] = btc_entry_price

    for period_name, period_h in HOLDING_PERIODS.items():
        exit_row, exit_status = find_exit_bar(snapshot_df, entry_row, period_h, symbol)
        if exit_status != "found":
            result[ANOMALY_EXIT_COLS[period_h]] = np.nan
            result[ANOMALY_DIR_COLS[period_h]] = np.nan
            result[ANOMALY_NET_COLS[period_h]] = np.nan
            continue

        exit_price = exit_row["close"]
        result[ANOMALY_EXIT_COLS[period_h]] = exit_price

        btc_exit = get_btc_price(snapshot_df, exit_row["timestamp_ms"])

        if btc_entry_price and btc_exit:
            dir_excess = calc_dir_excess(entry_price, exit_price, btc_entry_price, btc_exit, direction_sign)
            result[ANOMALY_DIR_COLS[period_h]] = dir_excess

            if direction_sign == 0:
                result[ANOMALY_NET_COLS[period_h]] = 0.0
            else:
                funding_cost = calc_funding_cost_for_period(funding_rate_8h, period_h, direction_sign)
                result[ANOMALY_NET_COLS[period_h]] = dir_excess - friction_decimal - funding_cost
        else:
            result[ANOMALY_DIR_COLS[period_h]] = np.nan
            result[ANOMALY_NET_COLS[period_h]] = np.nan

    return result


def process_baseline_record(record, snapshot_df, friction, funding_cost):
    """
    处理 Baseline 记录 → 返回非分周期列的 dict。

    Baseline 有 holding_period_hours，只需算一个 exit 和一个 return。
    funding_cost_component 来自 04，已按 holding_period_hours 正确计算。
    """
    symbol = record["symbol"]
    scan_time = pd.to_datetime(record.get("scan_time_utc", ""), utc=True)
    direction_sign = parse_direction_sign(record.get("direction_sign", 0))
    holding_hours = int(record.get("holding_period_hours", 24))
    friction_decimal = friction / 1e4 if friction else 0.0

    result = {
        BASELINE_ENTRY_COL: None,
        BASELINE_BTC_ENTRY_COL: None,
        BASELINE_EXIT_COL: None,
        BASELINE_BTC_EXIT_COL: None,
        BASELINE_DIR_COL: None,
        BASELINE_NET_COL: None,
    }

    entry_row, entry_status = find_entry_bar(snapshot_df, scan_time, symbol)
    if entry_status != "found":
        return result

    entry_price = entry_row["open"]
    entry_ts = entry_row["timestamp_ms"]
    result[BASELINE_ENTRY_COL] = entry_price

    btc_entry_price = get_btc_price(snapshot_df, entry_ts)
    if btc_entry_price:
        result[BASELINE_BTC_ENTRY_COL] = btc_entry_price

    exit_row, exit_status = find_exit_bar(snapshot_df, entry_row, holding_hours, symbol)
    if exit_status != "found":
        return result

    exit_price = exit_row["close"]
    result[BASELINE_EXIT_COL] = exit_price

    btc_exit = get_btc_price(snapshot_df, exit_row["timestamp_ms"])

    if btc_entry_price and btc_exit:
        dir_excess = calc_dir_excess(entry_price, exit_price, btc_entry_price, btc_exit, direction_sign)
        result[BASELINE_DIR_COL] = dir_excess
        result[BASELINE_NET_COL] = dir_excess - friction_decimal - funding_cost

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", default="20260707_0804_utc")
    args = parser.parse_args()
    TARGET_RUN = args.run_id

    print("=" * 60)
    print("05_update_returns.py - AlphaHive V3.1.1 Phase 1")
    print("=" * 60)

    # 1. 读取账本
    print("\n[1/4] 读取账本...")
    anomaly_df = pd.read_csv(ANOMALY_LEDGER)
    baseline_df = pd.read_csv(BASELINE_LEDGER)

    anomaly_df = anomaly_df[anomaly_df["run_id"] == TARGET_RUN].copy()
    baseline_df = baseline_df[baseline_df["run_id"] == TARGET_RUN].copy()

    print(f"  Anomaly_Ledger ({TARGET_RUN}): {len(anomaly_df)} 条")
    print(f"  Baseline_Ledger ({TARGET_RUN}): {len(baseline_df)} 条")

    if anomaly_df.empty:
        print("  [WARN] 无数据，跳过")
        return

    # 2. 加载 snapshot
    print(f"\n[2/4] 加载 return_tape ({TARGET_RUN})...")
    snapshot_df = load_return_tape(TARGET_RUN)
    print(f"  snapshot 时间范围: {ms_to_dt(snapshot_df['timestamp_ms'].min())} ~ {ms_to_dt(snapshot_df['timestamp_ms'].max())}")
    print(f"  symbols: {snapshot_df['symbol'].nunique()} 个")

    # 3. 处理收益回填
    print("\n[3/4] 计算收益回填...")

    # Anomaly 回填（分周期，含 per-period funding）
    anomaly_updates = []
    for _, row in anomaly_df.iterrows():
        record = row.to_dict()
        # 预处理 funding_rate 为小数
        rate_raw = record.get("funding_rate_8h", 0)
        if pd.notna(rate_raw) and rate_raw != 0:
            assert_normalized_funding(pd.Series([rate_raw]))
            record["funding_rate_8h_decimal"] = float(rate_raw)
        else:
            record["funding_rate_8h_decimal"] = rate_raw

        result = process_anomaly_record(
            record=record,
            snapshot_df=snapshot_df,
            friction=record.get("friction_bps_roundtrip", 0) or 0,
        )
        result["record_id"] = row["record_id"]
        anomaly_updates.append(result)

    # Baseline 回填（非分周期，用 04 已算好的 funding_cost）
    baseline_updates = []
    for _, row in baseline_df.iterrows():
        record = row.to_dict()
        result = process_baseline_record(
            record=record,
            snapshot_df=snapshot_df,
            friction=row.get("friction_bps_roundtrip", 0) or 0,
            funding_cost=row.get("funding_cost_component", 0) or 0,
        )
        result["baseline_id"] = row["baseline_id"]
        baseline_updates.append(result)

    # 4. 回填账本
    print("\n[4/4] 回填账本...")

    anomaly_original = pd.read_csv(ANOMALY_LEDGER)
    baseline_original = pd.read_csv(BASELINE_LEDGER)

    for update in anomaly_updates:
        record_id = update["record_id"]  # 不 pop，保留给样例输出
        mask = anomaly_original["record_id"] == record_id
        if mask.any():
            for col, val in update.items():
                if col in anomaly_original.columns:
                    anomaly_original.loc[mask, col] = val

    for update in baseline_updates:
        baseline_id = update["baseline_id"]  # 不 pop，保留给样例输出
        mask = baseline_original["baseline_id"] == baseline_id
        if mask.any():
            for col, val in update.items():
                if col in baseline_original.columns:
                    baseline_original.loc[mask, col] = val

    anomaly_original.to_csv(ANOMALY_LEDGER, index=False)
    baseline_original.to_csv(BASELINE_LEDGER, index=False)

    print(f"  回填完成: Anomaly ({len(anomaly_updates)} 条), Baseline ({len(baseline_updates)} 条)")

    # 样例输出
    print("\n" + "=" * 60)
    print(f"样例输出 ({TARGET_RUN})")
    print("=" * 60)

    # Anomaly 样例（分周期）
    print(f"\n--- Anomaly_Ledger 样例 (分周期列) ---")
    for res in anomaly_updates[:3]:
        rid = res["record_id"]
        print(f"  {rid}")
        print(f"    entry_price_ref: {res.get(ANOMALY_ENTRY_COL)}")
        for ph in [4, 24, 72, 168]:
            ex = res.get(ANOMALY_EXIT_COLS[ph])
            de = res.get(ANOMALY_DIR_COLS[ph])
            dn = res.get(ANOMALY_NET_COLS[ph])
            if pd.notna(ex):
                print(f"    {ph}h: exit={ex:.4f}, excess={de:.6f}, net={dn:.6f}")
            else:
                print(f"    {ph}h: Pending")
        print()

    # Baseline 样例（非分周期）
    print(f"\n--- Baseline_Ledger 样例 (非分周期列) ---")
    baseline_with_dir = [r for r in baseline_updates if r.get("direction_sign", 0) != 0]
    for res in baseline_with_dir[:5]:
        bid = res["baseline_id"]
        print(f"  {bid}")
        print(f"    symbol: {res['symbol']}, direction_sign: {res['direction_sign']}")
        print(f"    entry_price_ref: {res.get(BASELINE_ENTRY_COL)}")
        print(f"    exit_price_ref: {res.get(BASELINE_EXIT_COL)}")
        print(f"    btc_entry_price: {res.get(BASELINE_BTC_ENTRY_COL)}")
        print(f"    btc_exit_price: {res.get(BASELINE_BTC_EXIT_COL)}")
        print(f"    dir_excess_ret: {res.get(BASELINE_DIR_COL)}")
        print(f"    dir_excess_ret_net: {res.get(BASELINE_NET_COL)}")
        print()

    # 统计
    print("\n--- 统计摘要 ---")
    # Anomaly stats
    a_entry = sum(1 for r in anomaly_updates if r.get(ANOMALY_ENTRY_COL) is not None and not pd.isna(r.get(ANOMALY_ENTRY_COL)))
    print(f"Anomaly ({TARGET_RUN}):")
    print(f"  total: {len(anomaly_updates)}")
    print(f"  entry_price filled: {a_entry}/{len(anomaly_updates)}")
    for ph in [4, 24, 72, 168]:
        n = sum(1 for r in anomaly_updates if r.get(ANOMALY_DIR_COLS[ph]) is not None and not pd.isna(r.get(ANOMALY_DIR_COLS[ph])))
        print(f"  dir_excess_ret_{ph}h filled: {n}/{len(anomaly_updates)}")

    # Baseline stats
    b_entry = sum(1 for r in baseline_updates if r.get(BASELINE_ENTRY_COL) is not None and not pd.isna(r.get(BASELINE_ENTRY_COL)))
    b_exit = sum(1 for r in baseline_updates if r.get(BASELINE_EXIT_COL) is not None and not pd.isna(r.get(BASELINE_EXIT_COL)))
    b_dir = sum(1 for r in baseline_updates if r.get(BASELINE_DIR_COL) is not None and not pd.isna(r.get(BASELINE_DIR_COL)))
    b_net = sum(1 for r in baseline_updates if r.get(BASELINE_NET_COL) is not None and not pd.isna(r.get(BASELINE_NET_COL)))
    print(f"\nBaseline ({TARGET_RUN}):")
    print(f"  total: {len(baseline_updates)}")
    print(f"  entry_price_ref filled: {b_entry}/{len(baseline_updates)}")
    print(f"  exit_price_ref filled: {b_exit}/{len(baseline_updates)}")
    print(f"  dir_excess_ret filled: {b_dir}/{len(baseline_updates)}")
    print(f"  dir_excess_ret_net filled: {b_net}/{len(baseline_updates)}")

    print("\n" + "=" * 60)
    print("05_update_returns.py 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()








