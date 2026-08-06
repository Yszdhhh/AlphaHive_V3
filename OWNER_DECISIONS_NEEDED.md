# OWNER_DECISIONS_NEEDED

## 2026-07-17 Hermes post-fix closure

Gemini `HERMES-POSTFIX-VERIFY-001-GEMINI` is accepted `RECOVERED`. The
`2026-07-17 04:07:48 UTC` pull refreshed all four engines for 59/59 symbols
with zero stale entries and zero final failures; the prior six SSL failures are
closed. This removes only the runtime-health advisory. Trigger ignition, Paper
changes, source/credential changes and trading remain separate Owner gates.

更新时间：2026-07-16（Asia/Shanghai）

以下事项保持 `PARK`，本轮没有自动批准、没有点火、没有真实交易：

0. **ARC-NEXT T3/D5 边界（2026-07-16）**：N1–N5 的 T1/T2 基础工作已获限范围授权，但以下事项仍需 Owner 逐项签字：scanner 从 CoinGlass 切换到 Binance、OI/taker 断洞的 S3 gap-fill、trigger 点火、`paper_eligibility=ALLOW`、凭证/代理或下单路径变化，以及 Tardis/自建 WS 的 order-book 采集。

1. **F2.1 OI/funding 候选 trigger 点火（T3）**：历史回放现在只计算 OI/funding 数据覆盖状态；即使状态为 `COMPUTED`，也不会把 OI/funding 加入候选触发条件。等架构席确认 P3 的 90d 覆盖阈值数字并审 F2.1 代码后，再由 Owner 决定是否点火。
2. **任何 paper 联动变化（T3）**：不因 OI/funding 状态或历史回放结果改变 `paper ALLOW`、方向、仓位或执行路径。
3. **未授权的数据源/凭证变更（T3）**：CoinGlass、任何 API key、凭证、代理配置、触发器或 paper 相关数据通路仍须逐项 Owner 批准。已获准的 Binance 公共数据拉取和 ARC-NEXT 逻辑视图仅限 `OWNER_APPROVALS.md` 所载范围，不构成对本项的泛化授权。
4. **F2.1 独立 PC 预审**：批次 A 打包前必须附上 Agy / Gemini 3.1 Pro 的 `ARC-NEXT-F21-PC-PREVIEW-002` 原文；未收到前不得把 F2.1 作为已审结论发架构席。Sonnet 不再作为后续派单模型。
5. **Hermes post-prune runtime validation**：Mimo 已确认剪枝后出现新 pull report，scheduler 已恢复 scheduled 且 `next_run_at` 在未来；但该次运行仍有 klines 3、funding 2、taker 1 个 SSL 失败。状态保持 `PARTIAL / TRANSIENT_TRANSPORT_FAILURE`，待下一次 pull 验证恢复或由 Owner 明确接受 advisory。
6. **F2.1 quantile 规则保持未激活**：`scan_rules.yaml` 已定义 OI/funding quantile 参数，但候选构建循环当前不读取它们。未来若要点火，必须先补实现、边界测试和独立审计，再由 Owner 单独批准；本轮不做任何代码激活。

本文件不是批准记录；它只记录仍未获得 Owner 签字的闸门。

## 2026-07-16 evidence correction

The Hermes post-prune blocker is narrowed, not closed as fully healthy. Mimo
verified a new report at `2026-07-16T09:06:07Z` after the prune, an enabled and
scheduled job, a future next run, and 8×59 checkpoint partitions. The same run
contains six SSL transport failures (klines 3, funding 2, taker 1; OI 0).
Keep the Hermes item as `PARTIAL / TRANSIENT_TRANSPORT_FAILURE` until the next
scheduled pull demonstrates recovery or the Owner explicitly accepts the
advisory.

Agy's `ARC-NEXT-F21-QUANTILE-DESIGN-001` is accepted as read-only design
evidence. Quantile trigger ignition remains a separate T3 Owner decision; no
implementation, rule activation, Paper change, source switch or gap-fill is
authorized by this report.

## 2026-07-17 prompt/framework decision

`F21-PROMPT-003-FRAMEWORK-FREEZE-001` is accepted with advisory and is
`FREEZE_READY_WITH_OWNER_DOC`. The direction-neutral framework, cutoff rules,
denylist, GRAVEYARD constraints and dormant OI/funding semantics pass. The
remaining Owner/Codex decision is whether to change
`config/deep_research_contract.yaml` from `contract_version: v1.0.0-draft`,
`status: draft` to explicitly approved frozen-v1 values. This does not
authorize trigger ignition, Paper `ALLOW`, provider automation or trading.

## 2026-07-18 prospective candidate inventory closure

Codex added a read-only inventory and confirmed that the newest overnight run
still has one `1000BONKUSDT` row, a completed bar ending at
`2026-07-07T03:00:00Z`, and no registry authorization. The multi-row older
runs are superseded/quarantined or historical replay. This is a runtime data
readiness blocker, not an Owner approval to relax thresholds or reuse old
rows. The next action is a fresh normal scan after refreshed klines are
present; source switch, trigger ignition, Paper `ALLOW`, and trading remain
PARK.

## 2026-07-18 candidate-data bridge activation gate

The additive dual-source adapter and full-file coverage report are available,
but neither changes the active scanner. Before a canonical snapshot may be
published or used as scanner input, the Owner must explicitly decide: (1) the
source precedence rule per data dimension, (2) the permitted gap policy for
the 59 live symbols versus 73 Binance and 124 CoinGlass files, and (3) whether
current OHLCV may publish when required derivative dimensions are absent or
stale. This is a T3 source-path/canonical-activation choice, not an adapter
implementation detail.

## 2026-07-18 recommended price-gap policy awaiting confirmation

The non-active bridge observed 94 missing hourly bars across 24 effective
symbols in their latest 90-day windows, with no observed gap in the latest 48
completed hours. Codex recommends: no interpolation; block any latest-48-hour
gap; outside that guard allow only gaps of at most four bars and at most six
missing bars per 90 days, with `HISTORICAL_GAP_WARNING`; make any metric whose
window crosses a gap unavailable; block larger gaps. This is a proposed source
publication/scan policy and remains `PARK` until the Owner confirms it.

## 2026-07-18 canonical price scanner activation closure

The Owner confirmed the proposed gap policy and explicitly authorized the
scanner to consume a validated canonical price snapshot. The first local
publication is `canonical_price_snapshots/v0001`; scan
`20260718_canonical_activation` records 57 canonical price inputs, a validated
pointer/manifest reference, and zero candidates. This closes only the price
scanner source-path and gap-policy gates. Historical backfill, derivative
source changes, trigger ignition, Paper `ALLOW`, notification delivery and
trading remain `PARK`.

## 2026-07-18 OwnerDecision implementation status

The one-time governance choices are resolved: stable Owner label,
`interactive_owner_confirmation_in_Codex`, exact confirmation text and
`immutable_exact_file_hash` preset binding. The resulting MVP003 persistence
implementation is awaiting independent final audit only. This resolves no
per-job decision: an actual future Paper decision still needs a fresh explicit
Owner reply for that exact, fully bound, prospective and capability-ALLOW job.
The current `paper_execution_presets.yaml` is `DRAFT`, which independently
blocks `APPROVE_PAPER`; PaperPlan creation, Paper execution, trigger ignition,
notification delivery and trading remain `PARK`.

## 2026-07-18 preset configuration gate resolved

The Owner approved `paper_execution_presets.yaml` as `v0.1.0 / APPROVED`,
PAPER_ONLY, with its exact canonical hash recorded in `OWNER_APPROVALS.md`.
This closes only the preset-configuration gate. The remaining production gate
is runtime truth: a fresh `PROSPECTIVE_LIVE`, quality-ALLOW ResearchJob must
reach `RESEARCH_ASSESSMENT_READY`, then receive a separate exact per-job Owner
approval. Historical/BLOCK jobs, including BONK, remain permanently ineligible;
Paper execution, trigger ignition, notification and trading remain `PARK`.

## 2026-07-19 prospective lifecycle architecture closure

The T1/T2 lifecycle design correction is accepted: `cutoff_policy` separates
historical replay (`performance_eligible: false`) from a future prospective
path (`performance_eligible: true`), and PaperPlan eligibility begins only at
`PAPER_APPROVED` after the immutable OwnerDecision. This resolves an internal
design contradiction; it is not an Owner approval or an authorization to
create a PaperPlan.

The immediate blocker is data readiness, not a new Owner decision. The latest
scan lacks prospective mode and registry authorization and has a stale
completed bar. Wait for a fresh, registry-authorized `PROSPECTIVE_LIVE`
candidate. After that, the existing per-job Owner confirmation, bound to the
exact candidate/evidence/assessment/decision/preset hashes, remains required
before any real PaperPlan. Paper execution, triggers, Feishu delivery and
trading remain separate T3 decisions.
