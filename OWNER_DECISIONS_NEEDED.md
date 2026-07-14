# OWNER_DECISIONS_NEEDED

更新时间：2026-07-14（Asia/Shanghai）

以下事项保持 `PARK`，本轮没有自动批准、没有点火、没有真实交易：

1. **F2.1 OI/funding 候选 trigger 点火（T3）**：历史回放现在只计算 OI/funding 数据覆盖状态；即使状态为 `COMPUTED`，也不会把 OI/funding 加入候选触发条件。等架构席确认 P3 的 90d 覆盖阈值数字并审 F2.1 代码后，再由 Owner 决定是否点火。
2. **任何 paper 联动变化（T3）**：不因 OI/funding 状态或历史回放结果改变 `paper ALLOW`、方向、仓位或执行路径。
3. **数据刷新（T3/外部状态）**：OI 缺口 `2026-05-26 → now`、funding 缺口 `2026-06-23 → now` 只做只读侦察；任何 API key、凭证、代理配置、频率策略或 DB 写入必须等 Owner 明确授权。
4. **Sonnet PC 端预审**：批次 A 打包前必须附上 `F21-PREVIEW-001` 原文；未收到前不得把 F2.1 作为已审结论发架构席。

本文件不是批准记录；它只记录仍未获得 Owner 签字的闸门。
