r"""s017 降集中诊断 — Unlock 是多币结构还是 SEI 线性 quirk？

描述性 only：
  - 不改 S1 选中 pct
  - 不宣称 GO / historical_pass / 进 S2
  - 复用 s1_select / s1_eval 已算好的 short_resid

用法：python scripts/s017_deconcentrate.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DERIVED = Path(r"G:\Quant test\derived_data\token_unlocks")
EVENTS_PQ = DERIVED / "sample_events.parquet"
SELECT_CSV = DERIVED / "s1_select_events.csv"
EVAL_CSV = DERIVED / "s1_eval_events.csv"
OUT_MD = ROOT / "reports" / "s017_deconcentrate.md"

SEED = 20260812
N_BOOT = 800
DAY_MS = 86_400_000
CLUSTER_GAP_D = 7
DENSE_SCHEDULE_ROWS = 100
SPARSE_MAX_PER_YEAR = 4
COST_RT = 0.0027 * 2


def boot_ci(x: np.ndarray, seed: int = SEED, n: int = N_BOOT) -> tuple[float, float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan"), float("nan")
    if len(x) == 1:
        v = float(x[0])
        return v, v
    rng = np.random.default_rng(seed)
    boots = [float(np.mean(rng.choice(x, size=len(x), replace=True))) for _ in range(n)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(lo), float(hi)


def pack(name: str, df: pd.DataFrame, seed: int = SEED) -> dict:
    if df is None or len(df) == 0:
        return {
            "name": name,
            "n": 0,
            "n_sym": 0,
            "mean_short": float("nan"),
            "med_short": float("nan"),
            "mean_net": float("nan"),
            "ci_lo": float("nan"),
            "ci_hi": float("nan"),
            "pct_pos": float("nan"),
            "top_sym": "",
            "top_w": float("nan"),
        }
    sr = df["short_resid"].to_numpy(float)
    net = df["net_27bps_rt"].to_numpy(float) if "net_27bps_rt" in df.columns else sr - COST_RT
    lo, hi = boot_ci(sr, seed=seed)
    vc = df["symbol"].value_counts()
    top_sym = str(vc.index[0]) if len(vc) else ""
    top_w = float(vc.iloc[0] / len(df)) if len(vc) else float("nan")
    return {
        "name": name,
        "n": int(len(df)),
        "n_sym": int(df["symbol"].nunique()),
        "mean_short": float(np.mean(sr)),
        "med_short": float(np.median(sr)),
        "mean_net": float(np.mean(net)),
        "ci_lo": float(lo),
        "ci_hi": float(hi),
        "pct_pos": float(np.mean(sr > 0)),
        "top_sym": top_sym,
        "top_w": top_w,
    }


def pct(x: float) -> str:
    if not np.isfinite(x):
        return "n/a"
    return f"{x * 100:.2f}%"


def fmt_row(s: dict) -> str:
    return (
        f"| {s['name']} | {s['n']} | {s['n_sym']} | {pct(s['mean_short'])} | "
        f"{pct(s['med_short'])} | [{pct(s['ci_lo'])}, {pct(s['ci_hi'])}] | "
        f"{pct(s['mean_net'])} | {pct(s['pct_pos'])} | {s['top_sym']} {pct(s['top_w'])} |"
    )


def symbol_table(df: pd.DataFrame, total_n: int | None = None) -> pd.DataFrame:
    if len(df) == 0:
        return pd.DataFrame(columns=["symbol", "n", "mean_short", "med_short", "weight", "mean_net", "pct_pos"])
    tn = total_n if total_n is not None else len(df)
    rows = []
    for sym, g in df.groupby("symbol"):
        rows.append(
            {
                "symbol": sym,
                "n": len(g),
                "mean_short": float(g["short_resid"].mean()),
                "med_short": float(g["short_resid"].median()),
                "weight": len(g) / tn if tn else float("nan"),
                "mean_net": float(g["net_27bps_rt"].mean()) if "net_27bps_rt" in g else float("nan"),
                "pct_pos": float((g["short_resid"] > 0).mean()),
            }
        )
    out = pd.DataFrame(rows).sort_values(["n", "mean_short"], ascending=[False, False])
    return out.reset_index(drop=True)


def leave_one_out(df: pd.DataFrame, symbols: list[str]) -> list[dict]:
    stats = []
    for sym in symbols:
        sub = df[df["symbol"] != sym]
        stats.append(pack(f"leave-{sym}", sub))
    # leave top-k by n
    top = df["symbol"].value_counts()
    for k in (1, 2, 3):
        drop = list(top.head(k).index)
        sub = df[~df["symbol"].isin(drop)]
        label = f"leave-top{k}({'+'.join(s.replace('USDT','') for s in drop)})"
        stats.append(pack(label, sub))
    return stats


def cluster_events(df: pd.DataFrame, gap_d: int = CLUSTER_GAP_D) -> pd.DataFrame:
    """Merge same-symbol events with gap<=gap_d into clusters; one row per cluster.

    Cluster short_resid = mean of member events (equal-weight within cluster).
    Reduces pseudo-independence from dense linear unlocks.
    """
    if len(df) == 0:
        return df.copy()
    gap_ms = gap_d * DAY_MS
    rows: list[dict] = []
    for sym, g in df.sort_values("unlock_ms").groupby("symbol", sort=False):
        g = g.sort_values("unlock_ms").reset_index(drop=True)
        cluster_id = 0
        members: list[pd.Series] = []
        prev_ms: int | None = None
        for _, r in g.iterrows():
            ms = int(r["unlock_ms"])
            if prev_ms is not None and (ms - prev_ms) > gap_ms:
                # flush
                rows.append(_flush_cluster(sym, cluster_id, members))
                cluster_id += 1
                members = []
            members.append(r)
            prev_ms = ms
        if members:
            rows.append(_flush_cluster(sym, cluster_id, members))
    return pd.DataFrame(rows)


def _flush_cluster(sym: str, cid: int, members: list[pd.Series]) -> dict:
    m = pd.DataFrame(members)
    sr = float(m["short_resid"].mean())
    net = float(m["net_27bps_rt"].mean()) if "net_27bps_rt" in m.columns else sr - COST_RT
    return {
        "symbol": sym,
        "cluster_id": cid,
        "n_events": len(m),
        "unlock_ms": int(m["unlock_ms"].iloc[0]),
        "unlock_ms_last": int(m["unlock_ms"].iloc[-1]),
        "span_d": (int(m["unlock_ms"].iloc[-1]) - int(m["unlock_ms"].iloc[0])) / DAY_MS,
        "pct_circ": float(m["pct_circ"].mean()) if "pct_circ" in m.columns else float("nan"),
        "short_resid": sr,
        "net_27bps_rt": net,
        "team_investor": bool(m["team_investor"].any()) if "team_investor" in m.columns else False,
    }


def sparse_per_year(df: pd.DataFrame, max_per_year: int = SPARSE_MAX_PER_YEAR) -> pd.DataFrame:
    """Keep at most max_per_year events per symbol per calendar year (earliest first)."""
    if len(df) == 0:
        return df.copy()
    d = df.copy()
    d["_year"] = pd.to_datetime(d["unlock_ms"], unit="ms", utc=True).dt.year
    d = d.sort_values(["symbol", "unlock_ms"])
    kept = d.groupby(["symbol", "_year"], group_keys=False).head(max_per_year)
    return kept.drop(columns=["_year"]).reset_index(drop=True)


def decide_verdict(
    full: dict,
    leave_sei: dict,
    leave_top3: dict,
    cluster_full: dict,
    filt_a: dict,
    filt_b: dict,
    filt_c: dict,
    sei_weight_full: float,
    sei_weight_eval: float,
    sei_events: int,
    sei_clusters: int,
) -> tuple[str, str]:
    """Return (verdict, rationale).

    STRUCTURAL_MULTI: leave-top 后仍稳（leave-SEI 与 leave-top3 的 mean 与 CI 均支撑）
    SINGLE_NAME_DOMINATED: 主要 SEI（去 SEI 后边塌）
    MIXED_NEED_MORE_CALENDAR: 方向在但 n 不够 / 集中未消解
    """
    leave_sei_mean_pos = np.isfinite(leave_sei["mean_short"]) and leave_sei["mean_short"] > 0
    leave_sei_ci_ok = np.isfinite(leave_sei["ci_lo"]) and leave_sei["ci_lo"] > 0
    leave_sei_ok = leave_sei["n"] >= 20 and leave_sei_mean_pos and leave_sei_ci_ok

    leave_top3_mean_pos = np.isfinite(leave_top3["mean_short"]) and leave_top3["mean_short"] > 0
    leave_top3_ci_ok = np.isfinite(leave_top3["ci_lo"]) and leave_top3["ci_lo"] > 0
    leave_top3_stable = leave_top3["n"] >= 20 and leave_top3_mean_pos and leave_top3_ci_ok

    filt_a_ci_ok = (
        filt_a["n"] >= 20
        and np.isfinite(filt_a["mean_short"])
        and filt_a["mean_short"] > 0
        and np.isfinite(filt_a["ci_lo"])
        and filt_a["ci_lo"] > 0
    )
    filt_c_ci_ok = (
        filt_c["n"] >= 20
        and np.isfinite(filt_c["mean_short"])
        and filt_c["mean_short"] > 0
        and np.isfinite(filt_c["ci_lo"])
        and filt_c["ci_lo"] > 0
    )

    # SEI as linear chain: heavy event count collapses under 7d clustering
    sei_linear_chain = sei_events >= 20 and sei_clusters <= max(3, sei_events // 10)

    # SINGLE_NAME: without SEI the edge dies
    if leave_sei["n"] < 15 or (
        not leave_sei_mean_pos
        and sei_weight_full >= 0.35
    ):
        return (
            "SINGLE_NAME_DOMINATED",
            "去 SEI 后样本不足或 mean≤0 → 边主要挂在 SEI 上",
        )
    if (
        sei_weight_eval >= 0.70
        and not leave_sei_ok
        and leave_sei["n"] < 25
        and not filt_a_ci_ok
    ):
        return (
            "SINGLE_NAME_DOMINATED",
            "eval 高度 SEI 集中且 leave-SEI / 剔密集 schedule 无法支撑 → 单名/线性 quirk",
        )

    # STRUCTURAL_MULTI: leave-top3 仍稳 + 剔密集/稀疏 cliff 仍稳
    if leave_sei_ok and leave_top3_stable and (filt_a_ci_ok or filt_c_ci_ok):
        return (
            "STRUCTURAL_MULTI",
            "leave-SEI 与 leave-top3 的 CI 下界均>0，且非密集过滤后仍稳 → 多币结构",
        )

    # Directional multi-coin evidence exists but leave-top3 / eval dispersion weak
    multi_direction = leave_sei_ok or (leave_sei_mean_pos and filt_a_ci_ok) or filt_c_ci_ok
    underpowered_top = not leave_top3_stable
    eval_concentrated = sei_weight_eval >= 0.50
    if multi_direction and (underpowered_top or eval_concentrated or sei_linear_chain):
        bits = []
        if leave_sei_ok:
            bits.append(
                f"leave-SEI full 仍正 (n={leave_sei['n']}, mean={leave_sei['mean_short']*100:.2f}%, "
                f"CI_lo={leave_sei['ci_lo']*100:.2f}%)"
            )
        if filt_a_ci_ok:
            bits.append(
                f"剔密集 schedule 仍正 (n={filt_a['n']}, CI_lo={filt_a['ci_lo']*100:.2f}%)"
            )
        if filt_c_ci_ok:
            bits.append(
                f"稀疏 cliff 仍正 (n={filt_c['n']}, CI_lo={filt_c['ci_lo']*100:.2f}%)"
            )
        if sei_linear_chain:
            bits.append(f"SEI 事件簇压缩 {sei_events}→{sei_clusters}（线性密集伪独立）")
        if eval_concentrated:
            bits.append(f"eval SEI 权重 {sei_weight_eval*100:.0f}% 集中未消解")
        if underpowered_top:
            bits.append(
                f"leave-top3 n={leave_top3['n']} mean={leave_top3['mean_short']*100:.2f}% "
                f"但 CI_lo={leave_top3['ci_lo']*100:.2f}% 不稳"
            )
        return (
            "MIXED_NEED_MORE_CALENDAR",
            "；".join(bits) + " → 方向偏多币，但需扩日历降集中后再判结构稳性",
        )

    if sei_weight_full >= 0.40 and not leave_sei_ok:
        return (
            "SINGLE_NAME_DOMINATED",
            "SEI 权重大且 leave-SEI 不稳 → 单名主导",
        )

    return (
        "MIXED_NEED_MORE_CALENDAR",
        "信号混杂、样本分散不足，无法判定结构多币或单名主导",
    )


def main() -> int:
    if not SELECT_CSV.exists() or not EVAL_CSV.exists():
        print("missing s1_select/s1_eval csv; run s017_s1_holdout first")
        return 1
    if not EVENTS_PQ.exists():
        print(f"missing {EVENTS_PQ}")
        return 1

    select = pd.read_csv(SELECT_CSV)
    eval_df = pd.read_csv(EVAL_CSV)
    raw = pd.read_parquet(EVENTS_PQ)
    full = pd.concat([select, eval_df], ignore_index=True)

    # schedule density from raw calendar
    schedule_n = raw.groupby("symbol").size().rename("schedule_rows")
    dense_syms = set(schedule_n[schedule_n > DENSE_SCHEDULE_ROWS].index.tolist())

    # ── per-symbol tables ────────────────────────────────────────────────
    tbl_sel = symbol_table(select)
    tbl_ev = symbol_table(eval_df)
    tbl_full = symbol_table(full)

    sei_w_full = float(tbl_full.loc[tbl_full["symbol"] == "SEIUSDT", "weight"].sum()) if len(tbl_full) else 0.0
    sei_w_eval = float(tbl_ev.loc[tbl_ev["symbol"] == "SEIUSDT", "weight"].sum()) if len(tbl_ev) else 0.0

    # ── leave-one-out ────────────────────────────────────────────────────
    # at least SEI / ARB / top3
    top_syms = full["symbol"].value_counts().head(5).index.tolist()
    must = ["SEIUSDT", "ARBUSDT"]
    loo_targets = list(dict.fromkeys(must + top_syms))  # preserve order, unique

    loo_full = leave_one_out(full, loo_targets)
    loo_eval = leave_one_out(eval_df, [s for s in loo_targets if s in set(eval_df["symbol"])])
    loo_select = leave_one_out(select, [s for s in loo_targets if s in set(select["symbol"])])

    leave_sei_full = next(s for s in loo_full if s["name"] == "leave-SEIUSDT")
    leave_top3_full = next(s for s in loo_full if s["name"].startswith("leave-top3"))

    # ── event clusters ───────────────────────────────────────────────────
    cl_full = cluster_events(full)
    cl_eval = cluster_events(eval_df)
    cl_select = cluster_events(select)
    st_cl_full = pack("cluster_full", cl_full)
    st_cl_eval = pack("cluster_eval", cl_eval)
    st_cl_select = pack("cluster_select", cl_select)
    cl_sym = symbol_table(cl_full.rename(columns={}) if "short_resid" in cl_full.columns else cl_full)

    # SEI cluster compression
    sei_ev_n = int((full["symbol"] == "SEIUSDT").sum())
    sei_cl_n = int((cl_full["symbol"] == "SEIUSDT").sum()) if len(cl_full) else 0

    # ── optional filters (diagnostic, side-by-side) ──────────────────────
    # a) drop dense schedule symbols (>100 raw rows)
    fa_full = full[~full["symbol"].isin(dense_syms)]
    fa_eval = eval_df[~eval_df["symbol"].isin(dense_syms)]
    fa_sel = select[~select["symbol"].isin(dense_syms)]
    st_fa = pack("filt_a_drop_dense_sched", fa_full)
    st_fa_ev = pack("filt_a_eval", fa_eval)
    st_fa_sel = pack("filt_a_select", fa_sel)

    # b) team_investor only
    fb_full = full[full["team_investor"] == True]  # noqa: E712
    fb_eval = eval_df[eval_df["team_investor"] == True]  # noqa: E712
    fb_sel = select[select["team_investor"] == True]  # noqa: E712
    st_fb = pack("filt_b_team_investor", fb_full)
    st_fb_ev = pack("filt_b_eval", fb_eval)
    st_fb_sel = pack("filt_b_select", fb_sel)

    # c) pct>=1% (already) + max 4 events / symbol / year
    fc_full = sparse_per_year(full, SPARSE_MAX_PER_YEAR)
    fc_eval = sparse_per_year(eval_df, SPARSE_MAX_PER_YEAR)
    fc_sel = sparse_per_year(select, SPARSE_MAX_PER_YEAR)
    st_fc = pack("filt_c_sparse_cliff", fc_full)
    st_fc_ev = pack("filt_c_eval", fc_eval)
    st_fc_sel = pack("filt_c_select", fc_sel)

    st_full = pack("full_s1_pct1", full)
    st_eval = pack("eval_s1_pct1", eval_df)
    st_sel = pack("select_s1_pct1", select)

    verdict, rationale = decide_verdict(
        st_full,
        leave_sei_full,
        leave_top3_full,
        st_cl_full,
        st_fa,
        st_fb,
        st_fc,
        sei_w_full,
        sei_w_eval,
        sei_ev_n,
        sei_cl_n,
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── markdown report ──────────────────────────────────────────────────
    lines: list[str] = []
    lines.append("# s017 降集中诊断 — Unlock 多币结构 vs SEI 线性 quirk")
    lines.append("")
    lines.append(f"- date: {now}")
    lines.append("- script: `scripts/s017_deconcentrate.py`")
    lines.append("- inputs: `s1_select_events.csv` / `s1_eval_events.csv` / `sample_events.parquet`")
    lines.append("- S1 胜出形态（冻结，本诊断不改）: pct_circ ≥ **1.00%**")
    lines.append("- **数据性质: development / exploratory / descriptive**")
    lines.append("- **禁止**: 不改 S1 pct；不进 S2；不宣称 GO / historical_pass")
    lines.append("")
    lines.append(f"## Verdict: **{verdict}**")
    lines.append("")
    lines.append(f"> {rationale}")
    lines.append("")
    lines.append("### 判定键（三选一，描述性）")
    lines.append("")
    lines.append("| Verdict | 含义 |")
    lines.append("|---|---|")
    lines.append("| `STRUCTURAL_MULTI` | leave-top 后仍稳 |")
    lines.append("| `SINGLE_NAME_DOMINATED` | 主要 SEI |")
    lines.append("| `MIXED_NEED_MORE_CALENDAR` | 方向在但 n 不够 |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 0. 基线（S1 已算 short_resid，原样汇总）")
    lines.append("")
    lines.append("| slice | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top symbol weight |")
    lines.append("|---|---:|---:|---:|---:|---|---:|---:|---|")
    for s in (st_sel, st_eval, st_full):
        lines.append(fmt_row(s))
    lines.append("")
    lines.append(
        f"- SEI weight: **full {sei_w_full*100:.1f}%** · **eval {sei_w_eval*100:.1f}%** · "
        f"schedule_rows(SEI)={int(schedule_n.get('SEIUSDT', 0))}"
    )
    lines.append(
        f"- dense schedule symbols (raw rows>{DENSE_SCHEDULE_ROWS}): "
        + ", ".join(sorted(dense_syms))
        + f" （共 {len(dense_syms)}）"
    )
    lines.append("")
    lines.append("## 1. 各币 n / mean short / 权重")
    lines.append("")
    lines.append("### 1.1 Full（select+eval，n=195 池中 S1 合格 138+57）")
    lines.append("")
    lines.append("| symbol | n | mean_short | median | weight | mean_net | pos% | schedule_rows | dense? |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for _, r in tbl_full.iterrows():
        sr = int(schedule_n.get(r["symbol"], 0))
        dense = "Y" if r["symbol"] in dense_syms else ""
        lines.append(
            f"| {r['symbol']} | {int(r['n'])} | {pct(r['mean_short'])} | {pct(r['med_short'])} | "
            f"{pct(r['weight'])} | {pct(r['mean_net'])} | {pct(r['pct_pos'])} | {sr} | {dense} |"
        )
    lines.append("")
    lines.append("### 1.2 Select")
    lines.append("")
    lines.append("| symbol | n | mean_short | median | weight | pos% |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for _, r in tbl_sel.iterrows():
        lines.append(
            f"| {r['symbol']} | {int(r['n'])} | {pct(r['mean_short'])} | {pct(r['med_short'])} | "
            f"{pct(r['weight'])} | {pct(r['pct_pos'])} |"
        )
    lines.append("")
    lines.append("### 1.3 Eval（Lead 已标 CONCENTRATED）")
    lines.append("")
    lines.append("| symbol | n | mean_short | median | weight | pos% |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for _, r in tbl_ev.iterrows():
        lines.append(
            f"| {r['symbol']} | {int(r['n'])} | {pct(r['mean_short'])} | {pct(r['med_short'])} | "
            f"{pct(r['weight'])} | {pct(r['pct_pos'])} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Leave-one-symbol-out")
    lines.append("")
    lines.append("至少 SEI / ARB / top3（按 full 事件数）。")
    lines.append("")
    lines.append("### 2.1 Full")
    lines.append("")
    lines.append("| slice | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top remaining |")
    lines.append("|---|---:|---:|---:|---:|---|---:|---:|---|")
    lines.append(fmt_row(st_full))
    for s in loo_full:
        lines.append(fmt_row(s))
    lines.append("")
    lines.append("### 2.2 Eval")
    lines.append("")
    lines.append("| slice | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top remaining |")
    lines.append("|---|---:|---:|---:|---:|---|---:|---:|---|")
    lines.append(fmt_row(st_eval))
    for s in loo_eval:
        lines.append(fmt_row(s))
    lines.append("")
    lines.append("### 2.3 Select")
    lines.append("")
    lines.append("| slice | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top remaining |")
    lines.append("|---|---:|---:|---:|---:|---|---:|---:|---|")
    lines.append(fmt_row(st_sel))
    for s in loo_select:
        lines.append(fmt_row(s))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. 事件簇（同 symbol 间隔 ≤7d 并簇，降伪独立）")
    lines.append("")
    lines.append(
        f"规则：按 symbol 排序 unlock_ms；相邻间隔 ≤{CLUSTER_GAP_D}d 并入同一簇；"
        "簇收益 = 成员 `short_resid` 等权均值。冷却已在 S1 建池时应用，"
        "故簇主要压缩「刚好卡在冷却边界上的密集线性解锁」。"
    )
    lines.append("")
    lines.append("| slice | n_events | n_clusters | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top |")
    lines.append("|---|---:|---:|---:|---:|---:|---|---:|---:|---|")
    for st, n_ev in (
        (st_cl_select, len(select)),
        (st_cl_eval, len(eval_df)),
        (st_cl_full, len(full)),
    ):
        lines.append(
            f"| {st['name']} | {n_ev} | {st['n']} | {st['n_sym']} | {pct(st['mean_short'])} | "
            f"{pct(st['med_short'])} | [{pct(st['ci_lo'])}, {pct(st['ci_hi'])}] | "
            f"{pct(st['mean_net'])} | {pct(st['pct_pos'])} | {st['top_sym']} {pct(st['top_w'])} |"
        )
    lines.append("")
    lines.append(f"- SEI 事件→簇压缩: **{sei_ev_n} → {sei_cl_n}** clusters")
    if len(cl_full):
        multi = cl_full[cl_full["n_events"] > 1]
        lines.append(
            f"- 多事件簇数: {len(multi)} / {len(cl_full)} "
            f"(mean n_events in multi={multi['n_events'].mean():.2f})" if len(multi) else
            f"- 多事件簇数: 0 / {len(cl_full)}"
        )
    lines.append("")
    lines.append("### 3.1 簇级各币（full）")
    lines.append("")
    lines.append("| symbol | n_clusters | mean_short | median | weight | mean n_events/cluster |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    if len(cl_full):
        for sym, g in cl_full.groupby("symbol"):
            w = len(g) / len(cl_full)
            lines.append(
                f"| {sym} | {len(g)} | {pct(float(g['short_resid'].mean()))} | "
                f"{pct(float(g['short_resid'].median()))} | {pct(w)} | "
                f"{float(g['n_events'].mean()):.2f} |"
            )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. 可选过滤（仅诊断，三列并列，不选胜）")
    lines.append("")
    lines.append("| filter | 定义 |")
    lines.append("|---|---|")
    lines.append(
        f"| **a** | 剔除 raw schedule 行数 >{DENSE_SCHEDULE_ROWS} 的币（疑似日更线性） |"
    )
    lines.append("| **b** | 仅 `team_investor==True` |")
    lines.append(
        f"| **c** | 已在 pct≥1% 池上，每币每年最多 {SPARSE_MAX_PER_YEAR} 个事件（强制稀疏 cliff） |"
    )
    lines.append("")
    lines.append("### 4.1 Full 并列")
    lines.append("")
    lines.append("| filter | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top weight |")
    lines.append("|---|---:|---:|---:|---:|---|---:|---:|---|")
    lines.append(fmt_row(st_full))
    lines.append(fmt_row(st_fa))
    lines.append(fmt_row(st_fb))
    lines.append(fmt_row(st_fc))
    lines.append("")
    lines.append("### 4.2 Eval 并列")
    lines.append("")
    lines.append("| filter | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top weight |")
    lines.append("|---|---:|---:|---:|---:|---|---:|---:|---|")
    lines.append(fmt_row(st_eval))
    lines.append(fmt_row(st_fa_ev))
    lines.append(fmt_row(st_fb_ev))
    lines.append(fmt_row(st_fc_ev))
    lines.append("")
    lines.append("### 4.3 Select 并列")
    lines.append("")
    lines.append("| filter | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top weight |")
    lines.append("|---|---:|---:|---:|---:|---|---:|---:|---|")
    lines.append(fmt_row(st_sel))
    lines.append(fmt_row(st_fa_sel))
    lines.append(fmt_row(st_fb_sel))
    lines.append(fmt_row(st_fc_sel))
    lines.append("")
    lines.append(
        f"- filter a 从 full 剔除币: "
        + ", ".join(sorted(set(full["symbol"]) & dense_syms))
        + f" → 剩余 n={st_fa['n']}"
    )
    lines.append(
        f"- filter b full: team_investor {int(full['team_investor'].sum())}/{len(full)} "
        f"({full['team_investor'].mean()*100:.1f}%)"
    )
    lines.append(
        f"- filter c full: {len(full)} → {st_fc['n']} "
        f"(压缩 {len(full) - st_fc['n']} 个同年超额事件)"
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. 综合解读（描述性）")
    lines.append("")
    lines.append("| 检查 | 结果 |")
    lines.append("|---|---|")
    lines.append(
        f"| eval SEI 占比 | {sei_w_eval*100:.1f}% "
        f"({'≥50% 单名主导风险' if sei_w_eval >= 0.5 else '<50%'}) |"
    )
    lines.append(
        f"| full SEI 占比 | {sei_w_full*100:.1f}% "
        f"({'≥40% 偏高' if sei_w_full >= 0.4 else '可接受区间'}) |"
    )
    lines.append(
        f"| leave-SEI full | n={leave_sei_full['n']} mean={pct(leave_sei_full['mean_short'])} "
        f"CI=[{pct(leave_sei_full['ci_lo'])}, {pct(leave_sei_full['ci_hi'])}] "
        f"med={pct(leave_sei_full['med_short'])} |"
    )
    lines.append(
        f"| leave-top3 full | n={leave_top3_full['n']} mean={pct(leave_top3_full['mean_short'])} "
        f"CI=[{pct(leave_top3_full['ci_lo'])}, {pct(leave_top3_full['ci_hi'])}] |"
    )
    lines.append(
        f"| 簇化 full | events {len(full)}→clusters {st_cl_full['n']}; "
        f"mean={pct(st_cl_full['mean_short'])} CI_lo={pct(st_cl_full['ci_lo'])} |"
    )
    lines.append(
        f"| 剔密集 schedule (a) | n={st_fa['n']} mean={pct(st_fa['mean_short'])} "
        f"CI_lo={pct(st_fa['ci_lo'])} |"
    )
    lines.append(
        f"| team_investor (b) | n={st_fb['n']} mean={pct(st_fb['mean_short'])} "
        f"CI_lo={pct(st_fb['ci_lo'])} |"
    )
    lines.append(
        f"| 稀疏 cliff (c) | n={st_fc['n']} mean={pct(st_fc['mean_short'])} "
        f"CI_lo={pct(st_fc['ci_lo'])} |"
    )
    lines.append(f"| **Verdict** | **{verdict}** |")
    lines.append("")
    lines.append("### 关键数字（一页表）")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| S1 pct（冻结） | 1.00% |")
    lines.append(f"| full n / n_sym | {st_full['n']} / {st_full['n_sym']} |")
    lines.append(f"| full mean_short | {pct(st_full['mean_short'])} |")
    lines.append(f"| eval n / SEI_n / SEI_w | {st_eval['n']} / {int((eval_df.symbol=='SEIUSDT').sum())} / {pct(sei_w_eval)} |")
    lines.append(
        f"| leave-SEI mean / n / CI_lo | {pct(leave_sei_full['mean_short'])} / "
        f"{leave_sei_full['n']} / {pct(leave_sei_full['ci_lo'])} |"
    )
    lines.append(
        f"| leave-top3 mean / n / CI_lo | {pct(leave_top3_full['mean_short'])} / "
        f"{leave_top3_full['n']} / {pct(leave_top3_full['ci_lo'])} |"
    )
    lines.append(
        f"| cluster mean / n / CI_lo | {pct(st_cl_full['mean_short'])} / "
        f"{st_cl_full['n']} / {pct(st_cl_full['ci_lo'])} |"
    )
    lines.append(
        f"| filt_a mean / n / CI_lo | {pct(st_fa['mean_short'])} / {st_fa['n']} / {pct(st_fa['ci_lo'])} |"
    )
    lines.append(
        f"| filt_b mean / n / CI_lo | {pct(st_fb['mean_short'])} / {st_fb['n']} / {pct(st_fb['ci_lo'])} |"
    )
    lines.append(
        f"| filt_c mean / n / CI_lo | {pct(st_fc['mean_short'])} / {st_fc['n']} / {pct(st_fc['ci_lo'])} |"
    )
    lines.append(f"| **Verdict** | **{verdict}** |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. 禁令与未决")
    lines.append("")
    lines.append("- 本诊断 **未** 改 S1 选中 pct，**未** 用过滤结果回写形态。")
    lines.append("- **不得** 据此宣布 GO / historical_pass / 进 S2。")
    lines.append("- 若未来要「剔线性密集解锁」作新形态，须 **预注册** 后重跑 holdout（新卡/新形态），不可事后贴。")
    lines.append("- 日历源仍为 Mobula sample；扩币/交叉 Tokenomist 未做。")
    lines.append("- 未碰 s018 / s001 代码。")
    lines.append("")
    lines.append("## 产出")
    lines.append("")
    lines.append(f"- 报告: `{OUT_MD}`")
    lines.append("- 脚本: `scripts/s017_deconcentrate.py`")
    lines.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}")
    print(f"VERDICT={verdict}")
    print(
        f"full n={st_full['n']} mean={st_full['mean_short']*100:.2f}% | "
        f"SEI_w_eval={sei_w_eval*100:.1f}% | "
        f"leave-SEI n={leave_sei_full['n']} mean={leave_sei_full['mean_short']*100:.2f}% "
        f"CI_lo={leave_sei_full['ci_lo']*100:.2f}% | "
        f"leave-top3 n={leave_top3_full['n']} mean={leave_top3_full['mean_short']*100:.2f}% | "
        f"cluster n={st_cl_full['n']} mean={st_cl_full['mean_short']*100:.2f}% | "
        f"filt_a n={st_fa['n']} mean={st_fa['mean_short']*100:.2f}% | "
        f"filt_c n={st_fc['n']} mean={st_fc['mean_short']*100:.2f}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
