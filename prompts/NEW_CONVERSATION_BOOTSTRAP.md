# New Codex conversation bootstrap

Copy this into a new AlphaHive V3 conversation:

```text
这是 AlphaHive V3 的续接对话。请先读取：
G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md
G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md
G:\Quant test\AlphaHive_V3\agent_tasks\ARC_CURRENT_WAVE_001.md

然后直接核对仓库和报告，汇报：
1. 已完成的里程碑；
2. 当前唯一阻塞项；
3. 需要 Owner 批准的 T3 项；
4. 当前可以并行派发给 Mimo、antigravity/Gemini、DeepSeek 的任务；
5. Codex 自己下一步能执行的工作。

规则：只有 Codex 写 AlphaHive_V3 仓库；外部 Agent 只写指定 Desktop 报告；路径或输入不匹配必须 PARK；T3 不得自行执行；不要从旧聊天摘要推断状态，直接以文件、测试和运行报告为证据。
```

## Agent dispatch template

```text
你是 [agent]，执行 [TASK-ID]，tier=[T1/T2/T3]。

先阅读：
- G:\Quant test\AGENTS.md
- G:\Quant test\AlphaHive_V3\AGENTS.md
- G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md
- G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md
- G:\Quant test\AlphaHive_V3\agent_tasks\[TASK-FILE].md

只执行这个 task，不要自选其他任务。正式报告只能写入：
[EXACT-DESKTOP-OUTPUT-PATH]

缺少任何必需输入或路径不匹配时，必须输出 PARK，不得猜测、替换历史包或修改任务边界。
完成后必须回传：正式报告路径、状态/最终 Verdict、完整输入列表、关键证据、未决项。聊天摘要不能替代正式 Markdown 报告。
```

## Parallel dispatch rule

Mimo runtime checks、Agy architecture research、DeepSeek independent audit can run in parallel when they are read-only and write different output files. If one task's report is a required input to another, run them sequentially. Sonnet is optional research only and is never the sole final auditor.
