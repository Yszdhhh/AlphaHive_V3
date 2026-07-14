# ARC-C-PACK-002｜DeepSeek V4：打包 helper 候选收紧修正

**tier：** `T1 GREEN / isolated code correction`  
**from：** DeepSeek V4  
**to：** codex  
**前提：** 对 `ARC-C-PACK-001` 候选做最小修正；不覆盖旧候选，不写 repo 或历史包。

## 开始前必须读

1. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
2. `G:\Quant test\AlphaHive_V3\agent_tasks\ARC_NEXT_STAGE_DISPATCH_PLAN.md`
3. `G:\Quant test\AlphaHive_V3\agent_tasks\deepseek__codex__arc_c_pack_helper.md`
4. 旧候选与日志：`C:\Users\10639\Desktop\AlphaHive_V3_ArcC_MC1_deliverables\agent_outputs\deepseek\ARC-C-PACK-001_*`
5. F21/F2 历史包（只读）和任务文件列出的治理前置文件。

## 必须修正

1. `create --name X` 必须创建命名后的 `X_DELIVERABLE.md`，并以七项明确标题和 `MISSING — fill by codex` 占位生成模板；不得填入虚假的回归、provenance、Owner 决策或 diff 证据。
2. 限制所有写入到解析后位于 `C:\Users\10639\Desktop\AlphaHive_V3_*_deliverables` 下的**新里程碑输出目录**；拒绝 repo 路径、历史交付包路径、根 Desktop 和路径穿越。仍不得删除或覆盖既有文件。
3. 七项验证不得只做全文件关键词匹配：至少校验七个明确段落/字段的存在与非空，并检查 `reports/OWNER_DECISIONS_NEEDED.md`、`regression/` 的实际证据。证据为 `MISSING` 时应 `FAIL/PARK`，不能通过。
4. commit diff 接收必须在非空之外验证完整 patch 基本标记（`commit <sha>` 加 `diff --git`，或有效 format-patch header）；纯摘要必须拒绝。
5. 删除重复空类定义和未使用 import；保持标准库、无网络/环境变量/git 写入。
6. 在临时目录运行 create、validate 的正例/负例和 F21/F2 readonly compat；日志必须显示真实命令和实际结果，不能以人工说明代替自动结果。F2 可为 `NEEDS_ADAPTATION`，不可伪称标准结构 `PASS`。

## 原始输出

只写：

`C:\Users\10639\Desktop\AlphaHive_V3_ArcC_MC1_deliverables\agent_outputs\deepseek\`

必交新文件：

- `ARC-C-PACK-002_milestone_pack_helper.py`
- `ARC-C-PACK-002_VALIDATION.md`
- `ARC-C-PACK-002_RUN_LOG.txt`

文件顶部须写 `agent=DeepSeek V4`、`task_id=ARC-C-PACK-002`、UTC、输入、状态、未决项。旧 `-001` 文件必须保持原样。
