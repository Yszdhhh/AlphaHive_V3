# ARC 下一波：Runtime continuity + Quantile design — 2026-07-16

**状态：** `PAYLOAD_PREPARED_EXTERNAL_DISPATCH_PENDING`  
**主线：** 先解决 post-prune Hermes runtime 未验证，再准备未来 T3 quantile 激活的设计证据。  
**不做：** 不重启 scheduler、不补数据、不切 source、不点火 trigger、不放行 Paper。

## 分配

| 顺序 | agent | task_id | tier | 任务文件 | 精确输出 |
|---|---|---|---|---|---|
| 并行 A | Mimo | `ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001` | T1 | `agent_tasks/mimo__codex__arc_next_runtime_scheduler_verify.md` | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001.md` |
| 并行 B | Agy / Gemini 3.1 Pro | `ARC-NEXT-F21-QUANTILE-DESIGN-001` | T1/T2 | `agent_tasks/antigravity__codex__arc_next_f21_quantile_design.md` | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-QUANTILE-DESIGN-001.md` |

## 先后关系

1. Mimo 与 Agy 两单可以并行，必须分别发送完整任务原文，不能合单。
2. Mimo 若仍无新 pull report，输出 `UNVERIFIED`；Codex 不把旧报告升级为 GREEN。
3. Codex 验收两份报告：runtime 作为当前阻塞，quantile 作为未来 T3 设计输入。
4. 只有 Owner 明确批准 quantile 点火后，Codex 才能编写实现和测试；实现后再派 DeepSeek 做独立终审。

## Codex 自己的工作

- 继续只读诊断 scheduler；任何 restart/repair 先等待 Owner 指令；
- 维护 `OWNER_DECISIONS_NEEDED.md`：runtime continuity、quantile activation、trigger/Paper/source 仍分开记录；
- 不修改 `scan_rules.yaml` quantile 值，不把 dormant 规则接入候选循环。

## 不派发

- Sonnet：永久退出后续派单；本次历史报告保留但不再作为新任务输入。
- Grok：数据补缺继续冻结。
- DeepSeek：本阶段不重复派；仅在未来有 Owner 批准的实现 patch 后终审。
## 2026-07-16 handback result

- Mimo `ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001` is accepted with advisory:
  continuity and checkpoint shape pass, while the latest pull has six SSL
  transport failures. Observe the next scheduled run; do not restart Hermes.
- Agy `ARC-NEXT-F21-QUANTILE-DESIGN-001` is accepted as read-only design
  evidence. Quantile trigger ignition remains `PARK / T3`.
- No further external dispatch is needed in this wave. DeepSeek is deferred
  until a future Owner-approved implementation patch exists.
