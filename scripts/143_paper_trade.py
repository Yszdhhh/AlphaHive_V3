"""143_paper_trade.py — wash_cvd/cvd_bear 候选双账户虚拟交易模拟（只读，不下单）。

账户 A（统计口径）：事件触发 → 下一根 1h bar open 入场 → 固定持有 24h（时间退出，
  无价格止损）→ 与 109 历史统计口径一致，验证"edge 在真交易里是否还存在"。
账户 B（风控口径）：同入场 + 旧项目 chassis/cluster1 规则（参数从 alpha_hive 抄）：
  止损 -20%（2026-08-08 Owner 签批：原 -10% 在 wash_cvd 上是负优化，180 验证 +1.12% vs
  无止损 +2.42%；-20% 折中 +1.82%、触发率 46%→13%）、trailing 峰值回落 50%、
  MDD -15% 减半 / -25% 停新仓、最大持仓 168h。
成本：taker 22bps + 滑点 5bps = 27bps 单边（cluster1 COST_BPS=22 口径 + chassis 滑点）。
两账户仓位一致（$1,000/事件，B 受 MDD 断路器缩放）→ B−A = 风控增量。

数据：事件流 = reports/forward_replay_returns.csv（108 候选 + 109 收益积累）；
入场/退出价格 = binance_free_db raw_1h klines（与 108 同源，无 emoji 路径）。
幂等：按 alert_id 去重；只结算事件 ts+24h 已过去的行；重复运行不重复记账。

输出：reports/paper_positions.csv（每事件两账户行）、paper_equity_A/B.csv（日净值）、
paper_trade_report.md（汇总对照）。接入计划任务 08:40（109 之后），feishu 通知走
alphahive_feishu_notify.py（kind=paper）。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

REPORTS = PROJECT_ROOT / "reports"
EVENTS_CSV = REPORTS / "forward_replay_returns.csv"
POSITIONS_CSV = REPORTS / "paper_positions.csv"
EQUITY_A = REPORTS / "paper_equity_A.csv"
EQUITY_B = REPORTS / "paper_equity_B.csv"
EQUITY_C = REPORTS / "paper_equity_C.csv"
EQUITY_D = REPORTS / "paper_equity_D.csv"
POSITIONS_D_CSV = REPORTS / "paper_positions_D.csv"
NL_CANDIDATES = REPORTS / "newlisting_candidates.csv"
NL_RAW = PROJECT_ROOT / "data" / "newlisting_raw"
REPORT_MD = REPORTS / "paper_trade_report.md"
BINANCE_ROOT = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h")

# 账户/成本参数（抄 alpha_hive chassis_engine + cluster1_live_sim，不新发明）
ENTRY_NOMINAL = 1000.0      # $/事件
COST_BPS = 27               # taker 22 + slippage 5（单边）
HOLD_H_A = 24               # 账户 A 固定持有
STOP_LOSS_B = -0.20         # 账户 B 止损（Owner 签批 2026-08-08：-10% 负优化→-20%，180/验证：均值 +1.12%→+1.82%、触发 46%→13%）
TRAIL_B = -0.50             # 账户 B trailing（cluster1 TRAILING_STOP，峰值回落 50%）
MAX_HOLD_B = 168            # 账户 B 最大持仓（cluster1 MAX_HOLD_HOURS）
MDD_HALVE = -0.15           # 净值回撤 -15% → 仓位减半（chassis MDD_HALVE）
MDD_CLEAR = -0.25           # 净值回撤 -25% → 停新仓（chassis MDD_CLEAR）
INIT_EQUITY = 10000.0
HOUR_MS = 3_600_000


def load_events() -> pd.DataFrame:
    df = pd.read_csv(EVENTS_CSV)
    df["timestamp_ms"] = pd.to_numeric(df["timestamp_ms"], errors="coerce").astype("Int64")
    return df


def load_price_paths(symbols: set[str]) -> dict[str, pd.DataFrame]:
    """klines 子集：open/close 按 open_time 索引（时间升序，去重）。"""
    out: dict[str, pd.DataFrame] = {}
    for s in symbols:
        p = BINANCE_ROOT / "klines" / f"{s}.parquet"
        if not p.exists():
            continue
        kl = pd.read_parquet(p)
        if "open_time" not in kl.columns or "open" not in kl.columns or "close" not in kl.columns:
            continue
        kl = kl[["open_time", "open", "close"]].dropna()
        kl = kl.drop_duplicates(subset=["open_time"], keep="last").sort_values("open_time")
        kl["open_time"] = pd.to_numeric(kl["open_time"], errors="coerce").astype(np.int64)
        out[s] = kl
    return out


def simulate_confirm(event: pd.Series, prices: pd.DataFrame, size: float) -> dict:
    """账户 C（V_confirm，148 验证口径）：事件后 4h 收盘确认反弹才入场。

    - 确认：close[pos+4]/close[pos] - 1 > 0（pos+4 收盘时可知，无前视）
    - 入场：open[pos+5]（确认后下一根 bar 开盘）
    - 出场：close[pos+168]（持有 163h，与 148 同窗口口径）
    - 无确认 → NO_ENTRY（不入场，pnl=0）
    """
    ts = int(event["timestamp_ms"])
    idx = prices["open_time"].to_numpy(dtype=np.int64)
    pos = int(np.searchsorted(idx, ts, side="right"))
    if pos < 0 or pos + 168 >= len(prices):
        return {"exit_reason": "NO_DATA", "entry": np.nan, "exit": np.nan,
                "pnl_net": np.nan, "hold_h": np.nan}
    opens = prices["open"].to_numpy(dtype=float)
    closes = prices["close"].to_numpy(dtype=float)
    r4 = closes[pos + 4] / closes[pos] - 1.0
    if not np.isfinite(r4) or r4 <= 0:
        return {"exit_reason": "NO_ENTRY", "entry": np.nan, "exit": np.nan,
                "pnl_net": 0.0, "hold_h": np.nan}
    entry = float(opens[pos + 5])
    exit_px = float(closes[pos + 168])
    cost = entry * COST_BPS / 10000.0
    gross = exit_px / (entry + cost) - 1.0
    return {"exit_reason": "TIME", "entry": entry, "exit": exit_px,
            "pnl_net": gross * ENTRY_NOMINAL * size, "hold_h": 163.0}


def simulate(event: pd.Series, prices: pd.DataFrame, hold_h: int,
             stop: float | None, trail: float | None, max_hold_h: int,
             size: float) -> dict:
    """单事件模拟。入场=事件 ts 后第一根 bar open；退出按账户规则。"""
    ts = int(event["timestamp_ms"])
    idx = prices["open_time"].to_numpy(dtype=np.int64)
    pos = int(np.searchsorted(idx, ts, side="right"))
    if pos >= len(prices):
        return {"exit_reason": "NO_DATA", "entry": np.nan, "exit": np.nan,
                "pnl_net": np.nan, "hold_h": np.nan}
    entry = float(prices["open"].iloc[pos])
    closes = prices["close"].to_numpy(dtype=float)
    cost = entry * COST_BPS / 10000.0
    net_entry = entry + cost  # 市价单吃 taker，入场即含成本

    exit_idx: int | None = None
    reason = "TIME"
    if stop is None:
        exit_idx = min(pos + hold_h, len(prices) - 1)
    else:
        peak = entry
        for i in range(pos + 1, min(pos + max_hold_h + 1, len(prices))):
            c = float(closes[i])
            peak = max(peak, c)
            if c <= entry * (1 + stop):
                exit_idx, reason = i, "STOP"
                break
            if trail is not None and c <= peak * (1 + trail):
                exit_idx, reason = i, "TRAIL"
                break
        if exit_idx is None:
            exit_idx = min(pos + max_hold_h, len(prices) - 1)
            reason = "MAX_HOLD"
    exit_px = float(closes[exit_idx])
    gross = exit_px / net_entry - 1.0
    pnl = gross * ENTRY_NOMINAL * size - cost * size  # 出场含 taker（近似，出场不再计滑点）
    return {"exit_reason": reason, "entry": entry, "exit": exit_px,
            "pnl_net": pnl, "hold_h": (exit_idx - pos) * 1.0}


def settle_newlisting() -> tuple[pd.DataFrame, float]:
    """账户 D（s009）：读 159 候选，结算 ts+168h 已过去的事件。

    入场价 = 候选 entry_px（确认后下一 bar open）；出场 = close[pos+168]。
    幂等：按 alert_id 去重。返回 (positions_df, 累计 pnl)。
    """
    if not NL_CANDIDATES.exists():
        return pd.DataFrame(), 0.0
    cand = pd.read_csv(NL_CANDIDATES)
    if cand.empty:
        return pd.DataFrame(), 0.0
    existing: dict[str, dict] = {}
    if POSITIONS_D_CSV.exists():
        try:
            existing = {r["alert_id"]: r for _, r in pd.read_csv(POSITIONS_D_CSV).iterrows()}
        except Exception:
            existing = {}
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    rows = []
    for _, ev in cand.iterrows():
        aid = str(ev["alert_id"])
        if aid in existing:
            rows.append(existing[aid].to_dict())
            continue
        t = int(ev["timestamp_ms"])
        if t + 168 * HOUR_MS > now_ms:
            continue  # 未到结算窗口
        sym = str(ev["symbol"])
        entry = float(ev["entry_px"])
        closes: np.ndarray | None = None
        axis: np.ndarray | None = None
        p = NL_RAW / f"{sym}.parquet"
        if p.exists():
            try:
                kl = pd.read_parquet(p)
                closes = pd.to_numeric(kl["close"], errors="coerce").to_numpy(dtype=float)
                axis = pd.to_numeric(kl["open_time"], errors="coerce").to_numpy(dtype=np.int64)
            except Exception:
                pass
        if closes is None:
            p2 = BINANCE_ROOT / "klines" / f"{sym}.parquet"
            if p2.exists():
                try:
                    kl = pd.read_parquet(p2)
                    closes = pd.to_numeric(kl["close"], errors="coerce").to_numpy(dtype=float)
                    axis = pd.to_numeric(kl["open_time"], errors="coerce").to_numpy(dtype=np.int64)
                except Exception:
                    pass
        if closes is None or axis is None:
            continue
        pos = int(np.searchsorted(axis, t, side="right")) - 1
        if pos < 0 or pos + 168 >= len(closes) or not np.isfinite(closes[pos + 168]):
            continue
        exit_px = float(closes[pos + 168])
        cost = entry * COST_BPS / 10000.0
        gross = exit_px / (entry + cost) - 1.0
        rows.append({
            "alert_id": aid, "symbol": sym, "timestamp_ms": t,
            "age_days": round(float(ev.get("age_days", np.nan)), 2),
            "mayer": ev.get("mayer", np.nan),
            "entry": entry, "exit": exit_px, "reason": "TIME",
            "pnl_net": gross * ENTRY_NOMINAL, "hold_h": 163.0,
        })
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    if len(df):
        df.to_csv(POSITIONS_D_CSV, index=False, encoding="utf-8")
    return df, float(df["pnl_net"].sum()) if len(df) else 0.0


def run() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity-a", default=str(EQUITY_A))
    ap.add_argument("--equity-b", default=str(EQUITY_B))
    args = ap.parse_args()

    events = load_events()
    if events.empty:
        print("[143] 无事件，跳过")
        return 0
    # 只结算事件 ts+24h 已过去的行（幂等：旧行结果保留在 positions CSV）
    # 账户 B 需 ts+168h 过去才结算（数据不足时标 PENDING，不误判 MAX_HOLD）
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    settle = events[events["timestamp_ms"] + 24 * HOUR_MS <= now_ms].copy()
    settle_a = settle[settle["timestamp_ms"] + 24 * HOUR_MS <= now_ms]
    settle_b = settle[settle["timestamp_ms"] + MAX_HOLD_B * HOUR_MS <= now_ms]
    print(f"[143] 事件 {len(events)}，A 可结算 {len(settle_a)}，B 可结算 {len(settle_b)}")
    if settle.empty:
        print("[143] 无可结算事件，跳过")
        return 0

    prices = load_price_paths(set(settle["symbol"]))
    existing = {}
    if POSITIONS_CSV.exists():
        try:
            old = pd.read_csv(POSITIONS_CSV)
            existing = {r["alert_id"]: r for _, r in old.iterrows()}
        except Exception:
            existing = {}

    rows = []
    equity = INIT_EQUITY
    peak = equity
    size = 1.0
    for _, ev in settle.sort_values("timestamp_ms").iterrows():
        aid = str(ev["alert_id"])
        if aid in existing:
            # 已有行：若 B 之前是 PENDING 而现在可结算，只更新 B 列
            old = existing[aid]
            if old.get("account_b_status") == "PENDING" and aid in settle_b["alert_id"].tolist():
                px = prices.get(ev["symbol"])
                if px is not None and len(px):
                    b = simulate(ev, px, MAX_HOLD_B, STOP_LOSS_B, TRAIL_B, MAX_HOLD_B, float(old.get("size", 1.0)))
                    old["account_b_status"] = "SETTLED"
                    old["account_b_entry"] = b["entry"]
                    old["account_b_exit"] = b["exit"]
                    old["account_b_reason"] = b["exit_reason"]
                    old["account_b_pnl"] = b["pnl_net"]
                    old["account_b_hold_h"] = b["hold_h"]
                    existing[aid] = old
            continue
        px = prices.get(ev["symbol"])
        if px is None or len(px) == 0:
            continue
        a = simulate(ev, px, HOLD_H_A, None, None, HOLD_H_A, size)
        a_status = "SETTLED" if aid in settle_a["alert_id"].tolist() else "PENDING"
        b_status = "SETTLED" if aid in settle_b["alert_id"].tolist() else "PENDING"
        c_status = "SETTLED" if aid in settle_b["alert_id"].tolist() else "PENDING"  # C 与 B 同需 168h
        b = (simulate(ev, px, MAX_HOLD_B, STOP_LOSS_B, TRAIL_B, MAX_HOLD_B, size)
             if b_status == "SETTLED" else
             {"entry": np.nan, "exit": np.nan, "exit_reason": "PENDING",
              "pnl_net": 0.0, "hold_h": np.nan})
        c = (simulate_confirm(ev, px, size) if c_status == "SETTLED" else
             {"entry": np.nan, "exit": np.nan, "exit_reason": "PENDING",
              "pnl_net": 0.0, "hold_h": np.nan})
        row = {
            "alert_id": aid, "symbol": ev["symbol"], "timestamp_ms": int(ev["timestamp_ms"]),
            "account_a_status": a_status,
            "account_a_entry": a["entry"], "account_a_exit": a["exit"],
            "account_a_reason": a["exit_reason"], "account_a_pnl": a["pnl_net"],
            "account_a_hold_h": a["hold_h"],
            "account_b_status": b_status,
            "account_b_entry": b["entry"], "account_b_exit": b["exit"],
            "account_b_reason": b["exit_reason"], "account_b_pnl": b["pnl_net"],
            "account_b_hold_h": b["hold_h"],
            "account_c_status": c_status,
            "account_c_entry": c["entry"], "account_c_exit": c["exit"],
            "account_c_reason": c["exit_reason"], "account_c_pnl": c["pnl_net"],
            "account_c_hold_h": c["hold_h"], "size": size,
        }
        rows.append(row)
        if a_status == "SETTLED":
            equity += float(a["pnl_net"])
        peak = max(peak, equity)
        if equity / peak - 1 <= MDD_CLEAR:
            size = 0.0
        elif equity / peak - 1 <= MDD_HALVE:
            size = 0.5

    if rows:
        new = pd.DataFrame(rows)
        merged = pd.concat([pd.DataFrame(list(existing.values())), new], ignore_index=True)
        merged.to_csv(POSITIONS_CSV, index=False, encoding="utf-8")
        print(f"[143] positions {len(merged)} 行 → {POSITIONS_CSV}")

    # 日净值：三账户分别用各自 SETTLED pnl 重建
    if POSITIONS_CSV.exists():
        pos = pd.read_csv(POSITIONS_CSV)
        if not pos.empty:
            for acct, pnl_col, st_col, path in [("A", "account_a_pnl", "account_a_status", args.equity_a),
                                                ("B", "account_b_pnl", "account_b_status", args.equity_b),
                                                ("C", "account_c_pnl", "account_c_status", EQUITY_C)]:
                sub = pos[pos[st_col].fillna("SETTLED") == "SETTLED"].sort_values("timestamp_ms")
                pnl = pd.to_numeric(sub[pnl_col], errors="coerce").fillna(0.0)
                eq = pd.concat([pd.Series([INIT_EQUITY]), INIT_EQUITY + pnl.cumsum()], ignore_index=True)
                eq.to_csv(path, index=False, header=["equity"], encoding="utf-8")
                print(f"[143] equity_{acct} 尾值 {eq.iloc[-1]:.2f} → {path}")

    # 账户 D（s009 新币×确认）：159 候选结算 + 净值
    df_d, pnl_d = settle_newlisting()
    if len(df_d):
        eq_d = pd.concat([pd.Series([INIT_EQUITY]),
                          INIT_EQUITY + df_d.sort_values("timestamp_ms")["pnl_net"].cumsum()],
                         ignore_index=True)
        eq_d.to_csv(EQUITY_D, index=False, header=["equity"], encoding="utf-8")
        print(f"[143] 账户 D: {len(df_d)} 笔，净盈亏 ${pnl_d:+.2f} → {POSITIONS_D_CSV}")
        # Mayer 分层统计（166/168 周期增强观察：熊市 Mayer<0.8）
        if "mayer" in df_d.columns:
            m = pd.to_numeric(df_d["mayer"], errors="coerce")
            bear = df_d[m < 0.8]
            other = df_d[m >= 0.8]
            lines2 = [f"- 账户 D 周期分层：熊市(Mayer<0.8) n={len(bear)} "
                      f"盈亏 ${bear['pnl_net'].sum():+.2f}（均值 ${bear['pnl_net'].mean():+.2f}/笔） | "
                      f"非熊市 n={len(other)} 盈亏 ${other['pnl_net'].sum():+.2f}（均值 ${other['pnl_net'].mean():+.2f}/笔）"]
            # 追加到报告文件
            report_txt = REPORT_MD.read_text(encoding="utf-8") if REPORT_MD.exists() else ""
            if "周期分层" not in report_txt:
                REPORT_MD.write_text(report_txt + "\n" + "\n".join(lines2) + "\n", encoding="utf-8")
    else:
        print("[143] 账户 D: 无结算")

    # 汇总报告
    pos = pd.read_csv(POSITIONS_CSV) if POSITIONS_CSV.exists() else pd.DataFrame()
    lines = ["# 双账户虚拟交易报告\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件源：{EVENTS_CSV.name}；入场=事件后下一 bar open；成本={COST_BPS}bps 单边",
             f"- A=固定持有 {HOLD_H_A}h 时间退出；B=止损 {STOP_LOSS_B:.0%}/trailing {TRAIL_B:.0%}/上限 {MAX_HOLD_B}h",
             f"- MDD 断路器：-15% 减半 / -25% 停新仓；仓位 ${ENTRY_NOMINAL:.0f}/事件；初始 ${INIT_EQUITY:.0f}\n"]
    if pos.empty:
        lines.append("尚无结算仓位。")
    else:
        for acct, pnl_col, st_col, reason_col in [("A", "account_a_pnl", "account_a_status", "account_a_reason"),
                                                  ("B", "account_b_pnl", "account_b_status", "account_b_reason"),
                                                  ("C", "account_c_pnl", "account_c_status", "account_c_reason")]:
            sub = pos[pos[st_col].fillna("SETTLED") == "SETTLED"]
            pnl = pd.to_numeric(sub[pnl_col], errors="coerce")
            n = int(pnl.notna().sum())
            if n == 0:
                continue
            eq = pd.concat([pd.Series([INIT_EQUITY]), INIT_EQUITY + pnl.fillna(0).cumsum()], ignore_index=True)
            mdd = float((eq / eq.cummax() - 1).min())
            lines.append(f"## 账户 {acct}\n")
            lines.append(f"- 已结算：{n} 笔；净盈亏 ${pnl.sum():+.2f}；期末净值 ${eq.iloc[-1]:.2f}")
            lines.append(f"- 胜率 {100 * (pnl > 0).mean():.1f}%；最大回撤 {mdd:.1%}")
            reason = sub[reason_col].value_counts().to_dict()
            lines.append(f"- 退出分布：{reason}")
            lines.append("")
    # 账户 D（s009 新币×确认）：前向信号主收益池
    if POSITIONS_D_CSV.exists():
        df_d2 = pd.read_csv(POSITIONS_D_CSV)
        if len(df_d2):
            pnl_d2 = pd.to_numeric(df_d2["pnl_net"], errors="coerce").fillna(0.0)
            eq_d2 = pd.concat([pd.Series([INIT_EQUITY]), INIT_EQUITY + pnl_d2.cumsum()],
                              ignore_index=True)
            mdd_d = float((eq_d2 / eq_d2.cummax() - 1).min())
            lines.append("## 账户 D\n")
            lines.append(f"- 已结算：{len(df_d2)} 笔；净盈亏 ${pnl_d2.sum():+.2f}；期末净值 ${eq_d2.iloc[-1]:.2f}")
            lines.append(f"- 胜率 {100 * (pnl_d2 > 0).mean():.1f}%；最大回撤 {mdd_d:.1%}")
            lines.append(f"- 退出分布：{df_d2['reason'].value_counts().to_dict()}")
            lines.append("")
    # 当前持仓（未结算）：A/B/C PENDING + D 未到 168h 结算窗
    open_lines: list[str] = []
    if POSITIONS_CSV.exists():
        pos_all = pd.read_csv(POSITIONS_CSV)
        for acct, st_col in [("A", "account_a_status"), ("B", "account_b_status"),
                             ("C", "account_c_status")]:
            if st_col in pos_all.columns:
                pend = pos_all[pos_all[st_col].fillna("PENDING") == "PENDING"]
                if len(pend):
                    syms = ", ".join(pend["symbol"].astype(str).head(6))
                    if len(pend) > 6:
                        syms += " ..."
                    open_lines.append(f"- {acct}：{len(pend)} 笔持仓中（{syms}）")
    if NL_CANDIDATES.exists():
        try:
            cand_d = pd.read_csv(NL_CANDIDATES)
            ts_d = pd.to_numeric(cand_d["timestamp_ms"], errors="coerce")
            pend_d = cand_d[ts_d + 168 * HOUR_MS > int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)]
            if len(pend_d):
                syms = ", ".join(pend_d["symbol"].astype(str).head(6))
                if len(pend_d) > 6:
                    syms += " ..."
                open_lines.append(f"- D：{len(pend_d)} 笔持仓中（{syms}）")
        except Exception:
            pass
    if open_lines:
        lines.append("## 当前持仓\n")
        lines.extend(open_lines)
        lines.append("")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[143] wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
