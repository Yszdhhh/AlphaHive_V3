# AlphaHive V3 已知限制

## 当前质量闸状态

- `identity_gate`：`WARN`，`GATE_NOT_IMPLEMENTED`。当前未执行真实的标的/合约身份检查；产物会登记一个 `blocking=false` 的 `required_human_check`。
- `liquidity_gate`：`WARN`，`PARTIAL_IMPLEMENTATION`。成交额与有效 bar 检查已实现；真实 bid-ask spread 与 order-book depth 仍不可用，产物会登记一个 `blocking=false` 的 `required_human_check`。
- 上述任一检查未实现时，`paper_eligibility.status` 不得为 `ALLOW`，至少降为 `REVIEW_REQUIRED`；身份数据本身缺失时仍按既有规则 `BLOCK`。

## 补真条件

仅在获得相应数据源与治理批准后，才补上合约迁移历史、真实 bid-ask spread 与 order-book depth 检查，并保留人工复核和审计证据。在补真完成前，不得把这些闸的 `WARN` 解释成检查已通过。

## Funding 测量语义（2026-08-08）

- 资金费率序列是交易所**测量结果**，含结算周期假设、溢价 Impact Notional 深度、**费率上下限删失**。
- `harness/lib/funding_semantics.py` + `config/funding_measurement.yaml` 提供删失标记；`rate_for_model` 在 capped 时为 NaN。
- **限制**：IMN 与杠杆阶梯**参数变更历史**尚未系统回填（`parameter_change_log` 为空）→ 跨期横比 funding 仍可能错位。
- 审计报告：`reports/funding_semantics_audit.md`（脚本 170）。不得将审计通过解释为 s005 方向 edge 复活。

## Regime GMM（2026-08-08）

- `harness/lib/regime_gmm.py` 为 2 态对角 GMM（无 sklearn）；171 为 smoke，**未**接入 108/扫描。
- 在完成 wash_cvd 事件接合回测前，不得用 GMM 后验自动改 live/paper 仓位。
