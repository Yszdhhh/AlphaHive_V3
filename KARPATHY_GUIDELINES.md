# Karpathy 行为守则（Alpha Hive 执行前必读）

> 跨轨道统一的 LLM 编码行为守则，omx-r10 / alpha_pure_factor 已采用，Alpha Hive 同步纳入。
> **正文与其它两轨道逐字一致**（守则是标准，不按项目改），仅头尾加 Alpha Hive 接入说明。
>
> **AlphaHive V3 接入方式**：本文件位于仓库根
> `G:\Quant test\AlphaHive_V3\`，并由 `PROJECT_REQUIRED_READING.md`
> 统一列入所有 agent 的前置必读；`CLAUDE.md` 只保留到 `AGENTS.md` 的兼容入口。
> 每份 handoff 仍须先读共享必读与自身被点名的任务文件。

---

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Alpha Hive 接入备注（为什么这条守则对本项目尤其要紧）

本项目已发生过守则正对症的失误，纳入不是走形式：
- **§1 不藏困惑**：P1.5.B changelog 把回归闸里漂移的 `bootstrap_p` 从对照表里漏掉（看着"全 PASS"）；P1.1 的 s0/ls 受益不对称用"数据涨 8h"搪塞而非标红上报。→ 异常一律**显式 surface**，停下报告，别"修"、别美化。
- **§2/§3 最小且外科手术**：harness 收敛批次只新增、不重写；接因子只加 dispatch 分支与 helper，不碰共享逻辑。每改一行都能追溯到 handoff 的明确要求。
- **§4 可验证成功判据**：本项目的判据已具象为 **gauntlet receipt + 回归闸字节级一致**。把"跑通"翻译成"哪个数必须等于哪个值"，照判据 loop。

与项目宪法 `STRATEGY_CONTEXT_v1` 及各 handoff 的「§纪律 / 不要做的事」叠加生效；冲突时**宪法与 handoff 红线优先**，本守则补足通用工程纪律。
