# AlphaHive V3 已知限制

## 当前质量闸状态

- `identity_gate`：`WARN`，`GATE_NOT_IMPLEMENTED`。当前未执行真实的标的/合约身份检查；产物会登记一个 `blocking=false` 的 `required_human_check`。
- `liquidity_gate`：`WARN`，`GATE_NOT_IMPLEMENTED`。当前未执行真实的流动性、点差与深度检查；产物会登记一个 `blocking=false` 的 `required_human_check`。
- 上述任一检查未实现时，`paper_eligibility.status` 不得为 `ALLOW`，至少降为 `REVIEW_REQUIRED`；身份数据本身缺失时仍按既有规则 `BLOCK`。

## 补真计划

第 2 周，随衍生数据补齐与校验，补上身份核对、真实成交额/点差/深度检查，并保留人工复核和审计证据。在补真完成前，不得把这两个闸的 `WARN` 解释成检查已通过。
