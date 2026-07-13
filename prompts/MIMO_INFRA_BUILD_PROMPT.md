# Mimo 并行开发任务

你在 Windows 项目 `G:\Quant test` 中工作。你的身份是 AlphaHive 前端基建开发者，不是交易审核者。你要基于 mock 的 `DeepResearchPromptPackage v1`，开发一个隔离的“候选审查与提示词”前端原型，供 Codex 主线审查后接入现有 R1 看板。

## 目标

实现一个可独立打开的候选审查页，演示：

1. 自动筛选候选队列。
2. “为什么被筛选出来”的逐因子解释。
3. 质量 `PASS/WARN/BLOCK`、缺失数据和人工核验项。
4. 深研提示词预览与一键复制。
5. 云端研究结果粘贴区和本地格式校验状态。
6. Paper 计划表单原型：方向、研究假设、结构失效条件、周期、风险 preset 和 Owner 确认。

这是 UI 原型，不负责真实 API、账本写入、真实下单或逐币研究结论。

## 文件边界

只允许新增：

- `alpha_hive/dashboard/review.html`
- `alpha_hive/dashboard/review.js`
- `alpha_hive/dashboard/review.css`
- `alpha_hive/dashboard/review_mock.json`

禁止修改：

- `alpha_hive/dashboard/index.html`
- `alpha_hive/dashboard/dashboard.js`
- `alpha_hive/server/*`
- `AlphaHive_V3/scripts/*`
- `AlphaHive_V3/ledger/*`

## 必须先阅读

- `alpha_hive/dashboard/index.html`
- `alpha_hive/dashboard/dashboard.js`
- `AlphaHive_V3/reports/INTERACTION_FRONTEND_UPGRADE_PLAN_20260710.md`
- `AlphaHive_V3/reports/AUTOMATED_SIGNAL_RESEARCH_INFRA_PLAN_20260710.md`

## 视觉和交互要求

- 继承 R1 浅色、暖色 accent、指标卡、左侧列表和 Plotly 风格。
- 三栏：候选队列 / 证据与因子 / 深研与 Paper 计划。
- 窄屏按“队列 → 证据 → 计划”单列展示。
- 首屏只展开一个最高优先候选。
- 顶部固定显示：“异常筛选 ≠ 开单推荐；当前信号无方向结论”。
- 分开显示：为什么被筛出、为什么值得深研、为什么允许/不允许 Paper。
- `NOT_COMPUTED` 显示“尚未计算”，null 显示“未提供”，绝不能显示成 0。
- BLOCK 时 Paper 区域禁用并显示具体原因。
- prompt 预览使用只读 textarea 或 textContent；复制成功/失败都有反馈，失败时提供手工选择回退。
- 外部研究结果按纯文本处理，不使用未经转义的 innerHTML。
- 研究结果回填前不得启用 Paper 最终确认。
- 页面不得出现 API Key、真实下单、杠杆或资金划转入口。

## Mock 数据要求

至少包含：

- 一个 clean/PASS 候选。
- 一个缺 OI/depth 的 WARN 候选。
- 一个 quarantined 或 hash mismatch 的 BLOCK 候选。
- 已实现的三个 trigger。
- 至少两个 NOT_COMPUTED trigger。
- prompt text、template version、package hash 和 cutoff。
- 三个风险 preset，但明确标记 DRAFT/待回放校准；默认只能选择“标准”，不得自动选择进取。

## Paper 表单规则原型

- 必填 direction、hypothesis、structural invalidation、holding horizon、preset、Owner confirmation。
- horizon 只允许 4h/24h/72h/7d。
- 研究结果未粘贴或格式校验失败时禁用。
- BLOCK 候选始终禁用。
- 明确显示“这里只生成 Paper 计划，不会发送真实订单”。
- 所有自定义风险修改显示 custom 标记和变更理由输入框。

## 验收

- 四个文件之外无改动。
- 静态服务器下可以打开并完成 mock 全流程。
- 三种质量状态展示正确。
- trigger 解释、观测值、阈值、分位和限制完整。
- NOT_COMPUTED/null 不会变成 0。
- prompt 复制成功反馈和失败回退均实现。
- 粘贴包含 `<script>` 的研究文本不会执行。
- BLOCK/未回填/未确认时不能生成 Paper 计划。
- 窄屏可用。
- 原有 R1 文件和逻辑无改动。

完成后提交：修改文件清单、启动方式、手工验收步骤、关键状态截图清单和已知限制。不要接后端，不要越过文件边界。

