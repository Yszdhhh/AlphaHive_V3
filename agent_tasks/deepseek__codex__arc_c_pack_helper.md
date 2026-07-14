# ARC-C-PACK-001｜DeepSeek V4：里程碑交付包 helper 隔离候选

**tier：** `T1 GREEN / isolated code candidate`  
**from：** DeepSeek V4  
**to：** codex  
**目的：** 为 Charter 弧线 C 的 M-C1 交付一个可审查的、纯本地打包 helper 候选与双历史包验证设计。codex 是唯一可将其整合到仓库的写者。

## 开始前必须读

1. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
2. `G:\Quant test\AlphaHive_V3\agent_tasks\ARC_NEXT_STAGE_DISPATCH_PLAN.md`
3. `G:\Quant test\AGENTS.md`
4. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
5. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
6. `G:\Quant test\AlphaHive_V3\GRAVEYARD.md`
7. `G:\Quant test\AlphaHive_V3\KARPATHY_GUIDELINES.md`
8. 只读历史包：
   - `C:\Users\10639\Desktop\AlphaHive_V3_F21_deliverables\AlphaHive_V3_F21_DELIVERABLE`
   - `C:\Users\10639\Desktop\AlphaHive_V3_F2_overnight_deliverables`

## 工作

在你的 Desktop 输出目录中创建一个**候选** Python helper（不写 repo），用于由明确传入的元数据和已有文件生成/校验单个里程碑交付包。它必须：

1. 不联网、不调用 webhook、不读取环境变量、不读取凭证，不运行 git 的写操作、删改操作或任何 `push/rebase/reset`。
2. 创建或验证的目录结构至少包括：`<name>_DELIVERABLE.md`、`commit_diffs/`、`agent_outputs/`、`reports/`、`regression/`；如果输入声明使用 fallback，再包含 `pc_fallback/`。不得把缺失 agent 产物伪造为原文。
3. 校验 `DELIVERABLE.md` 的七项：状态行、批次结论、回归、SELF_CHECK、provenance、OWNER_DECISIONS_NEEDED、commit diff index。缺失必须失败并列出字段，不能自动补内容。
4. 对 commit diff 只接受**已提供**的完整 `git show` 文本或只读文件副本；不得自行修改仓库、伪造 diff 或用摘要替代全文。
5. 用 F21 和 F2_overnight 两个历史包进行只读兼容性/字段完整性验证，写出每个包通过/不兼容/需适配的明细。历史目录不一致时如实报告，不要迁移或覆盖它们。

允许输出最小、标准库优先的候选实现和运行日志。不要设计自动发现、自动提交、自动发包或自动调用其他 agent 的机制。

## 严禁

- 不得修改 `G:\Quant test\AlphaHive_V3`、历史交付目录、`_bus/`、git、数据、配置、测试或系统设置。
- 不得接触 token、secret、API key、proxy、数据库或外部网络。
- 不得涉及 trigger、paper 状态、策略、方向、仓位、真实交易或飞书真实发送。

## 原始输出

只向以下目录写：

`C:\Users\10639\Desktop\AlphaHive_V3_ArcC_MC1_deliverables\agent_outputs\deepseek\`

必交文件：

- `ARC-C-PACK-001_milestone_pack_helper.py`
- `ARC-C-PACK-001_VALIDATION.md`
- `ARC-C-PACK-001_RUN_LOG.txt`

验证文档顶部写明：`agent=DeepSeek V4`、`task_id=ARC-C-PACK-001`、UTC 时间、输入路径、`GREEN/PARK/UNVERIFIED`、未解决项。代码和日志都是候选证据，不代表已合并或已获验收。
