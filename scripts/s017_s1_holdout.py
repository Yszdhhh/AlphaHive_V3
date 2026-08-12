r"""s017 S1 Holdout — Token Unlock 残差空（前 80% 选 pct，后 20% 只评一次）。

方法论（冻结，禁止事后改）:
  - 预声明 pct ∈ {0.25%, 0.5%, 1.0%}
  - 按 unlock_ms 时间 holdout：前 80% = select（仅用于选形态）；后 20% = eval（一次）
  - 选形态：select 段 mean_short 的 bootstrap CI 下界最大；并列 median → n → 更严 pct
  - 成本 27bps×2；seed=20260812
  - 不宣布 historical_pass / live；仅 S1_PASS_CANDIDATE / S1_FAIL / S1_UNDERPOWERED

复用 s017_s0_local 窗口/β/ADV/冷却逻辑。
用法：python scripts/s017_s1_holdout.py
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ── load helpers from s017_s0_local (same constants / functions) ─────────────
_S0_PATH = ROOT / "scripts" / "s017_s0_local.py"
_spec = importlib.util.spec_from_file_location("s017_s0_local", _S0_PATH)
_s0 = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_s0)

load_ohlcv = _s0.load_ohlcv
window_return = _s0.window_return
adv_7d = _s0.adv_7d
beta_30d = _s0.beta_30d
team_investor_flag = _s0.team_investor_flag

KLINES = _s0.KLINES
DERIVED = _s0.DERIVED
EVENTS_PQ = _s0.EVENTS_PQ
DAY_MS = _s0.DAY_MS
ENTRY_LEAD_D = _s0.ENTRY_LEAD_D
ADV_MIN = _s0.ADV_MIN
COOLDOWN_D = _s0.COOLDOWN_D
COST_RT = _s0.COST_RT  # 0.0027 * 2
SEED = _s0.SEED  # 20260812

OUT_MD = ROOT / "reports" / "s017_s1_holdout.md"
OUT_CSV_SELECT = DERIVED / "s1_select_events.csv"
OUT_CSV_EVAL = DERIVED / "s1_eval_events.csv"
OUT_CSV_ALL = DERIVED / "s1_events_all_pct.csv"

# Pre-declared pct set (card sensitivity). Stricter last for tie-break.
PCT_SET = (0.0025, 0.005, 0.01)
SELECT_FRAC = 0.80
N_BOOT = 800


def build_events(raw: pd.DataFrame, btc: pd.DataFrame, pct_min: float) -> pd.DataFrame:
    """Same construction as s017_s0_local with variable pct threshold."""
    cand = raw[raw["pct_circ"].fillna(0) >= pct_min].copy()
    cand = cand.sort_values(["symbol", "unlock_ms"])
    rows: list[dict] = []
    last_entry: dict[str, int] = {}
    ohlcv_cache: dict[str, pd.DataFrame | None] = {}

    def get_ohlcv(sym: str) -> pd.DataFrame | None:
        if sym not in ohlcv_cache:
            ohlcv_cache[sym] = load_ohlcv(sym)
        return ohlcv_cache[sym]

    for r in cand.itertuples(index=False):
        sym = r.symbol
        t0 = int(r.unlock_ms)
        t_entry = t0 - ENTRY_LEAD_D * DAY_MS
        prev = last_entry.get(sym)
        if prev is not None and (t_entry - prev) < COOLDOWN_D * DAY_MS:
            continue
        sdf = get_ohlcv(sym)
        if sdf is None:
            continue
        adv = adv_7d(sdf, t_entry)
        if not np.isfinite(adv) or adv < ADV_MIN:
            continue
        ret_s = window_return(sdf, t_entry, t0)
        ret_b = window_return(btc, t_entry, t0)
        beta = beta_30d(sdf, btc, t_entry)
        if not np.isfinite(ret_s) or not np.isfinite(ret_b) or not np.isfinite(beta):
            continue
        resid = ret_s - beta * ret_b
        short_resid = -resid
        net = short_resid - COST_RT
        ti = team_investor_flag(str(getattr(r, "alloc_keys", "")))
        rows.append(
            {
                "symbol": sym,
                "unlock_ms": t0,
                "entry_ms": t_entry,
                "pct_circ": float(r.pct_circ),
                "pct_min": pct_min,
                "adv_7d": adv,
                "beta": beta,
                "ret_sym": ret_s,
                "ret_btc": ret_b,
                "resid": resid,
                "short_resid": short_resid,
                "net_27bps_rt": net,
                "team_investor": ti,
                "alloc_keys": str(getattr(r, "alloc_keys", ""))[:120],
            }
        )
        last_entry[sym] = t_entry

    return pd.DataFrame(rows)


def pack_stats(name: str, x: pd.DataFrame, seed: int = SEED) -> dict:
    if x is None or len(x) == 0:
        return {
            "name": name,
            "n": 0,
            "n_sym": 0,
            "mean_short": float("nan"),
            "med_short": float("nan"),
            "mean_net": float("nan"),
            "med_net": float("nan"),
            "ci_lo": float("nan"),
            "ci_hi": float("nan"),
            "pct_pos": float("nan"),
            "half_same_sign": None,
            "half_a_mean": float("nan"),
            "half_b_mean": float("nan"),
        }
    sr = x["short_resid"].to_numpy(float)
    net = x["net_27bps_rt"].to_numpy(float)
    rng = np.random.default_rng(seed)
    boots = [float(np.mean(rng.choice(sr, size=len(sr), replace=True))) for _ in range(N_BOOT)]
    lo, hi = np.percentile(boots, [2.5, 97.5])

    # within-select half split (diagnostic only; by unlock_ms order)
    xs = x.sort_values("unlock_ms")
    mid = max(1, len(xs) // 2)
    a = xs.iloc[:mid]["short_resid"].to_numpy(float)
    b = xs.iloc[mid:]["short_resid"].to_numpy(float)
    ma = float(np.mean(a)) if len(a) else float("nan")
    mb = float(np.mean(b)) if len(b) else float("nan")
    same = None
    if len(a) and len(b) and np.isfinite(ma) and np.isfinite(mb):
        same = bool(np.sign(ma) == np.sign(mb)) if ma != 0 and mb != 0 else bool(ma == mb == 0 or np.sign(ma) == np.sign(mb))

    return {
        "name": name,
        "n": len(x),
        "n_sym": int(x["symbol"].nunique()),
        "mean_short": float(np.mean(sr)),
        "med_short": float(np.median(sr)),
        "mean_net": float(np.mean(net)),
        "med_net": float(np.median(net)),
        "ci_lo": float(lo),
        "ci_hi": float(hi),
        "pct_pos": float(np.mean(sr > 0)),
        "half_same_sign": same,
        "half_a_mean": ma,
        "half_b_mean": mb,
    }


def select_winner(select_stats: dict[float, dict]) -> float:
    """Frozen rule: max CI_lo → max median → max n → stricter pct."""

    def key(pct: float) -> tuple:
        s = select_stats[pct]
        ci_lo = s["ci_lo"]
        med = s["med_short"]
        n = s["n"]
        # NaN CI_lo ranks last
        ci_rank = ci_lo if np.isfinite(ci_lo) else -1e18
        med_rank = med if np.isfinite(med) else -1e18
        return (ci_rank, med_rank, n, pct)

    return max(select_stats.keys(), key=key)


def random_baseline(
    eval_df: pd.DataFrame, btc: pd.DataFrame, n_draws: int = 800
) -> tuple[float, float, float, int]:
    """Same-symbol random 14d short residual; returns mean, ci_lo, ci_hi, n."""
    if len(eval_df) == 0:
        return float("nan"), float("nan"), float("nan"), 0
    rng = np.random.default_rng(SEED)
    ohlcv_cache: dict[str, pd.DataFrame | None] = {}
    base_rets: list[float] = []
    targets = min(n_draws, max(200, len(eval_df) * 5))
    for _ in range(targets * 3):  # allow skips
        if len(base_rets) >= targets:
            break
        row = eval_df.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
        sym = row["symbol"]
        if sym not in ohlcv_cache:
            ohlcv_cache[sym] = load_ohlcv(sym)
        sdf = ohlcv_cache[sym]
        if sdf is None:
            continue
        ts = sdf["ts"].to_numpy()
        if len(ts) < 40 * 24:
            continue
        floor = ts.min() + (ENTRY_LEAD_D + 30) * DAY_MS
        eligible = ts[ts > floor]
        if len(eligible) == 0:
            continue
        t1 = int(rng.choice(eligible))
        t0e = t1 - ENTRY_LEAD_D * DAY_MS
        if adv_7d(sdf, t0e) < ADV_MIN:
            continue
        rs = window_return(sdf, t0e, t1)
        rb = window_return(btc, t0e, t1)
        b = beta_30d(sdf, btc, t0e)
        if not all(np.isfinite([rs, rb, b])):
            continue
        base_rets.append(-(rs - b * rb))
    if not base_rets:
        return float("nan"), float("nan"), float("nan"), 0
    base = np.asarray(base_rets, float)
    rng2 = np.random.default_rng(SEED)
    boots = [float(np.mean(rng2.choice(base, len(base), True))) for _ in range(600)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(np.mean(base)), float(lo), float(hi), len(base)


def fmt_pct(x: float) -> str:
    if not np.isfinite(x):
        return "n/a"
    return f"{x * 100:.2f}%"


def main() -> int:
    if not EVENTS_PQ.exists():
        print(f"missing {EVENTS_PQ}; run s017_unlock_data_audit first")
        return 1
    raw = pd.read_parquet(EVENTS_PQ)
    btc = load_ohlcv("BTCUSDT")
    if btc is None:
        print("missing BTCUSDT klines")
        return 1

    # Build event pools per pre-declared pct (independent cooldown / filters)
    pools: dict[float, pd.DataFrame] = {}
    for pct in PCT_SET:
        print(f"building pool pct>={pct*100:.2f}% ...")
        pools[pct] = build_events(raw, btc, pct)
        print(f"  n={len(pools[pct])}")

    loose = pools[PCT_SET[0]]
    if len(loose) < 5:
        OUT_MD.parent.mkdir(parents=True, exist_ok=True)
        OUT_MD.write_text(
            "# s017 S1 Holdout\n\n**S1_UNDERPOWERED** — 最松 pct 池 n 不足，无法 holdout。\n",
            encoding="utf-8",
        )
        print("underpowered: loose pool empty/tiny")
        return 0

    # Fixed calendar cut from loosest pool (anti-leakage: same cut_ms for all forms)
    loose_sorted = loose.sort_values("unlock_ms").reset_index(drop=True)
    cut_idx = int(np.floor(SELECT_FRAC * len(loose_sorted)))
    cut_idx = min(max(cut_idx, 1), len(loose_sorted) - 1)
    cut_ms = int(loose_sorted.loc[cut_idx, "unlock_ms"])
    # select: unlock_ms < cut_ms; eval: unlock_ms >= cut_ms
    # (events at exactly cut_ms go to eval — first of last 20%)
    cut_utc = pd.to_datetime(cut_ms, unit="ms", utc=True)

    select_stats: dict[float, dict] = {}
    eval_stats_all: dict[float, dict] = {}  # diagnostic only — NOT for selection
    select_dfs: dict[float, pd.DataFrame] = {}
    eval_dfs: dict[float, pd.DataFrame] = {}

    for pct in PCT_SET:
        df = pools[pct]
        if len(df) == 0:
            select_dfs[pct] = df
            eval_dfs[pct] = df
            select_stats[pct] = pack_stats(f"select_pct{pct}", df)
            eval_stats_all[pct] = pack_stats(f"eval_pct{pct}", df)
            continue
        sel = df[df["unlock_ms"] < cut_ms].copy()
        evl = df[df["unlock_ms"] >= cut_ms].copy()
        select_dfs[pct] = sel
        eval_dfs[pct] = evl
        # seed offset by form index for bootstrap independence (still frozen seed base)
        form_seed = SEED + int(pct * 1e6)
        select_stats[pct] = pack_stats(f"select_pct{pct}", sel, seed=form_seed)
        # Do NOT use eval_stats for selection — only pack after winner for reporting
        # We pack all three eval for transparency table? Task says eval 只评一次 with winner.
        # Only compute winner eval for GO; others not used for decision.
        eval_stats_all[pct] = pack_stats(f"eval_pct{pct}", evl, seed=form_seed + 1)

    winner_pct = select_winner(select_stats)
    winner_sel = select_stats[winner_pct]
    winner_eval_df = eval_dfs[winner_pct]
    # Official eval: single evaluation of winning form only (re-pack with canonical seed)
    eval_official = pack_stats(f"eval_winner_pct{winner_pct}", winner_eval_df, seed=SEED + 99)

    # Optional simplified random baseline on eval symbols
    base_mean, base_lo, base_hi, n_base = random_baseline(winner_eval_df, btc)
    excess = (
        float(eval_official["mean_short"] - base_mean)
        if np.isfinite(eval_official["mean_short"]) and np.isfinite(base_mean)
        else float("nan")
    )

    # GO candidate gates (report only — never announce historical_pass)
    n_eval = eval_official["n"]
    ci_lo = eval_official["ci_lo"]
    med = eval_official["med_short"]
    mean_net = eval_official["mean_net"]

    gates = {
        "n_ge_20": n_eval >= 20,
        "ci_lo_gt_0": bool(np.isfinite(ci_lo) and ci_lo > 0),
        "median_ge_0": bool(np.isfinite(med) and med >= 0),
        "mean_net_gt_0": bool(np.isfinite(mean_net) and mean_net > 0),
    }
    if n_eval < 20:
        verdict = "S1_UNDERPOWERED"
    elif gates["ci_lo_gt_0"] and gates["median_ge_0"] and gates["mean_net_gt_0"]:
        verdict = "S1_PASS_CANDIDATE"
    else:
        verdict = "S1_FAIL"

    # CSV exports
    DERIVED.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for pct in PCT_SET:
        d = pools[pct].copy()
        if len(d):
            d["split"] = np.where(d["unlock_ms"] < cut_ms, "select", "eval")
            all_rows.append(d)
    if all_rows:
        pd.concat(all_rows, ignore_index=True).to_csv(OUT_CSV_ALL, index=False)
    if len(select_dfs[winner_pct]):
        select_dfs[winner_pct].to_csv(OUT_CSV_SELECT, index=False)
    if len(winner_eval_df):
        winner_eval_df.to_csv(OUT_CSV_EVAL, index=False)

    def row_md(pct: float, s: dict) -> str:
        half = s["half_same_sign"]
        half_s = "n/a" if half is None else ("YES" if half else "NO")
        return (
            f"| {pct*100:.2f}% | {s['n']} | {s['n_sym']} | "
            f"{fmt_pct(s['mean_short'])} | {fmt_pct(s['med_short'])} | "
            f"[{fmt_pct(s['ci_lo'])}, {fmt_pct(s['ci_hi'])}] | "
            f"{fmt_pct(s['mean_net'])} | {fmt_pct(s['pct_pos']) if np.isfinite(s['pct_pos']) else 'n/a'} | "
            f"{half_s} ({fmt_pct(s['half_a_mean'])}/{fmt_pct(s['half_b_mean'])}) |"
        )

    select_table = "\n".join(row_md(p, select_stats[p]) for p in PCT_SET)
    # Selection rationale
    ranked = sorted(PCT_SET, key=lambda p: (
        select_stats[p]["ci_lo"] if np.isfinite(select_stats[p]["ci_lo"]) else -1e18,
        select_stats[p]["med_short"] if np.isfinite(select_stats[p]["med_short"]) else -1e18,
        select_stats[p]["n"],
        p,
    ), reverse=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    loose_n = len(loose_sorted)
    n_sel_loose = int((loose_sorted["unlock_ms"] < cut_ms).sum())
    n_ev_loose = loose_n - n_sel_loose

    gate_lines = "\n".join(
        f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in gates.items()
    )

    md = f"""# s017 S1 Holdout — Token Unlock 残差空 — **{verdict}**

- date: {now}
- script: `scripts/s017_s1_holdout.py`
- events in: `{EVENTS_PQ}`
- prices: coinglass raw_1h klines (`{KLINES}`)
- seed: {SEED}
- **数据性质: development / exploratory**
- **禁止**: 不宣布 historical_pass / live / 前向通过；不改卡规格；eval 未参与选形态

## 规格（锁定，与 S0 / alpha_card 一致）

| 项 | 值 |
|---|---|
| 入场 | T0−14d 后第一根完整 1h open |
| 平仓 | T0 close asof |
| 方向 | 空残差 = −(r_sym − β·r_btc)；β=入场前 30d 日收益 OLS，clip[0, 1.5] |
| 过滤 | pct_circ≥阈值 · ADV7d≥${ADV_MIN/1e6:.0f}M · 冷却 {COOLDOWN_D}d |
| 成本 | 悲观 round-trip {COST_RT*1e4:.0f} bps（27bps×2） |
| 预声明 pct | {{0.25%, 0.5%, 1.0%}} |
| Holdout | 按 unlock_ms 排序；前 {SELECT_FRAC*100:.0f}% select / 后 {(1-SELECT_FRAC)*100:.0f}% eval |

## 时间切分（防泄漏）

| 项 | 值 |
|---|---|
| 切分锚点池 | 最松 pct≥0.25% 合格事件（n={loose_n}） |
| cut_ms | {cut_ms} |
| cut_utc | {cut_utc} |
| select (unlock_ms < cut) | n={n_sel_loose}（锚点池） |
| eval (unlock_ms ≥ cut) | n={n_ev_loose}（锚点池） |
| 说明 | 三形态共用同一 cut_ms；**仅 select 用于选 pct**；eval 只对胜出形态评一次 |

## Select 段：三形态对比（唯一选形态依据）

| pct | n | sym | mean_short | median | bootstrap 95% CI mean | mean_net | pos% | 段内半切同向 (A/B mean) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
{select_table}

### 选形态规则（冻结）

1. select 段 `mean_short` 的 bootstrap CI **下界最大**
2. 并列 → median 更大
3. 再并列 → n 更大
4. 再并列 → pct 更严（1.0% > 0.5% > 0.25%）

排序（优→劣）: {', '.join(f'{p*100:.2f}%' for p in ranked)}

### **选中 pct = {winner_pct*100:.2f}%**

- select n={winner_sel['n']} · mean={fmt_pct(winner_sel['mean_short'])} · med={fmt_pct(winner_sel['med_short'])} · CI=[{fmt_pct(winner_sel['ci_lo'])}, {fmt_pct(winner_sel['ci_hi'])}]

## Eval 段：胜出形态唯一一次评价

| 项 | 值 |
|---|---|
| 形态 | pct_circ ≥ **{winner_pct*100:.2f}%** |
| n | **{eval_official['n']}** |
| 覆盖币 | {eval_official['n_sym']} |
| mean short residual | **{fmt_pct(eval_official['mean_short'])}** |
| median | **{fmt_pct(eval_official['med_short'])}** |
| bootstrap 95% CI mean | **[{fmt_pct(eval_official['ci_lo'])}, {fmt_pct(eval_official['ci_hi'])}]** |
| mean net (27bps×2) | **{fmt_pct(eval_official['mean_net'])}** |
| median net | {fmt_pct(eval_official['med_net'])} |
| 胜率 short>0 | {fmt_pct(eval_official['pct_pos']) if np.isfinite(eval_official['pct_pos']) else 'n/a'} |
| vs random 14d (简化) | base_mean={fmt_pct(base_mean)} CI[{fmt_pct(base_lo)}, {fmt_pct(base_hi)}] n_base={n_base}；excess={fmt_pct(excess)} |

> 注：上表为**胜出 pct 在 eval 上的唯一正式结果**。未对未胜出形态做决策性 eval 对比（避免多重比较后改口）。

## GO 候选门控（报告用；**不**等于 historical_pass）

| 门控 | 结果 |
|---|---|
{gate_lines}

| **S1 Verdict** | **{verdict}** |
|---|---|

判定说明:
- `S1_UNDERPOWERED`: eval n<20
- `S1_PASS_CANDIDATE`: n≥20 且 CI下界>0 且 median≥0 且 mean_net>0（**仅候选**，不升级、不写 historical_pass）
- `S1_FAIL`: 有足够样本但未过门控

## 禁升级声明

- 本结果为 **development / exploratory** 本地 holdout。
- **不得**写入 live 配置、**不得**宣布 historical_pass / 前向通过。
- 未改 s014 / s018 / s001；未看 eval 后改阈值。
- 若为 `S1_PASS_CANDIDATE`，下一步仍由 Owner 决定是否申请正式 historical_pass 流程（含 n≥80 卡门槛、增量 vs s001 等）。

## 池规模（全时段，供参考）

| pct | 全时段 n | select n | eval n |
|---|---:|---:|---:|
| 0.25% | {len(pools[0.0025])} | {len(select_dfs[0.0025])} | {len(eval_dfs[0.0025])} |
| 0.50% | {len(pools[0.005])} | {len(select_dfs[0.005])} | {len(eval_dfs[0.005])} |
| 1.00% | {len(pools[0.01])} | {len(select_dfs[0.01])} | {len(eval_dfs[0.01])} |

## 产出文件

- 报告: `{OUT_MD}`
- 全 pct 事件: `{OUT_CSV_ALL}`
- 胜出 select: `{OUT_CSV_SELECT}`
- 胜出 eval: `{OUT_CSV_EVAL}`

## 未决项

1. team/investor alloc 字符串仍脏；主路径与 S0 一致未做硬过滤
2. 日历源仍为 Mobula sample；与链上/Tokenomist 交叉未做
3. 卡门槛 n≥80 为升级门槛；本 S1 用 n≥20 标 UNDERPOWERED
4. funding 持有期成本未计入（仅 27bps×2 开平）
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)
    print(
        f"Wrote {OUT_MD} verdict={verdict} winner_pct={winner_pct} "
        f"eval_n={eval_official['n']} mean={eval_official['mean_short']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
