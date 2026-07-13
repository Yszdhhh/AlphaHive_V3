# AlphaHive_V3 地基纠偏独立验收

- 验收角色：Codex（架构 / 验收；未修改建设代码、配置或执行层）
- 验收时间：2026-07-13（Asia/Shanghai）
- 验收范围：本轮所列 DoD；工作目录 `G:\Quant test\AlphaHive_V3`
- 结论：**FAIL — 退回建设会话。不得进入下一批（F2/F3 补地基）。**

## DoD 逐条核验

| # | DoD | 结果 | 独立核验事实 |
|---|---|---|---|
| 1 | repo 是 git、有 baseline commit、无 remote/push | **FAIL** | `AlphaHive_V3` 目录不存在可用 Git 工作树：`git status`、`git log`、`git remote -v` 均报 `fatal: not a git repository`。故 baseline commit、remote/push 状态及每任务独立 commit 均不可验证。 |
| 2 | root `PROJECT_CONSTITUTION.md` 存在且覆盖规定内容 | **FAIL** | 根目录不存在该文件，故系统本质/KPI、打分参考不驱动杠杆、Capacity Edge caveat、`GRAVEYARD.md` 引用、四条强约束、数据边界及决策权红线均未交付。 |
| 3 | root `GRAVEYARD.md` 存在且三块墓地、funding 坑、总定性齐全 | **FAIL** | 根目录不存在该文件；无法核验 Phase-1 七因子、主观量化线 beta≠alpha、carry 实测证伪、funding 100× 坑及“价格数据无方向 alpha 三次确认”。 |
| 4 | root `CLAUDE.md` 引用宪法和墓地 | **FAIL** | 文件存在，但仅含“Read `KARPATHY_GUIDELINES.md` before making code changes.”；未引用 `PROJECT_CONSTITUTION.md` 或 `GRAVEYARD.md`。 |
| 5 | 渲染研究提示词的禁止动作含“不得复活墓地已证伪方向” | **FAIL** | 全仓文本检索未发现该精确约束；墓地文件亦不存在。因此不能证明任一渲染样例具有该禁止动作。 |
| 6 | `liquidity_gate` / `identity_gate` 不再是 PASS；二者 `NOT_IMPLEMENTED` 时 paper 不 ALLOW | **FAIL** | `harness/lib/deep_research_package.py`：identity 完整时为 `PASS`；liquidity 有成交额时也为 `PASS`，缺失仅为 `WARN`。代码与测试均未出现 `NOT_IMPLEMENTED`，且没有覆盖“任一 NOT_IMPLEMENTED → paper 非 ALLOW”的 fail-closed 断言。 |
| 7 | 除闸相关断言外测试全绿；mock 包可构建；测试断言改动有说明 | **FAIL** | `python -m pytest -q` 无法启动（环境无 `pytest`）。`python -m unittest discover -s tests -v`：252 项中 249 通过、3 个模块导入失败（`test_external_evidence_envelope`、`test_mimo_ext_007`、`test_mimo_ext_008`，均因 `ModuleNotFoundError: pytest`）。无 Git 历史与说明文件，无法审计测试断言变更；mock 包构建也未获可复现的绿色证据。 |
| 8 | 无 token/secret 改动、无执行层改动、无越界扩产 | **FAIL（不可验收）** | 静态扫描未发现 Python 源码中的明显密钥字面量，也未见直接下单调用的明确证据；但由于无 Git 基线、无提交差异，无法确认“本轮无改动”或范围未越界。 |
| 9 | 每个任务独立 commit、git log 可查 | **FAIL** | 同第 1 项：仓库不可作为 Git 工作树读取，`git log` 不可用，无法核验独立提交。 |

## 必须返工项（按验收顺序）

1. 将 `AlphaHive_V3` 初始化/恢复为独立 Git 工作树，建立可识别 baseline commit；保持无 remote、无 push，并以独立 commit 提交每个任务。
2. 在项目根目录补齐 `PROJECT_CONSTITUTION.md` 和 `GRAVEYARD.md`，逐字覆盖本轮 DoD 指定的治理内容；将二者显式写入根 `CLAUDE.md` 的建设区自动加载指引。
3. 在研究提示词渲染产物及回归测试中加入“不得复活墓地已证伪方向”这一禁止动作。
4. 为 identity/liquidity 两个基础能力建立明确 `NOT_IMPLEMENTED` 语义；其任一状态时必须 fail closed，`paper_eligibility.status` 不得为 `ALLOW`。补充对应的正反例测试；不以 `WARN` 代替未实现的硬闸。
5. 提供可复现测试环境/依赖清单，安装或声明 `pytest`；全量测试绿色后提交测试日志。随提交说明每个变更测试断言及原因，并给出 mock 包构建命令与成功证据。
6. 提交可审计 diff，供复核 token/secret、执行层与扩产边界。

## 下一批方向 stub

**未授权进入 F2/F3。** 本批全部 FAIL 项关闭并经复验后，才可进入“F2/F3 补地基”方向：仅继续建设区的治理、fail-closed 闸与审计可复现性；外部研究产物保持 `UNVERIFIED` 隔离，不新增执行能力、不改变 Owner 唯一决策权、不产生任何下单行为。

## 签字

**Codex 独立验收：不通过（退回建设会话）**
