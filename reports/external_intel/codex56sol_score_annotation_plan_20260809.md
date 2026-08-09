# AlphaHive V3 108/109 连续打分标注实施规划

## 结论与前置条件

方案保持为纯标注链：

```text
108 事件触发不变
  → 触发后按事件时点计算 score_vol
  → candidates CSV 增加可选列
  → 109 原样累计该列
  → 仅在 Markdown 报告增加分桶 uplift
  → 现有 verdict、衰减监测、143 纸面账户完全不读取分数
```

当前存在一个需要先解决的 T2 配置事实差异：

- `config/factor_funnel.yaml` 目前只有 `development_cutoff: "2026-08-09"`，没有 FAM-001 的冻结规格或 `forward_start`。
- `EDGE_LEDGER.md` 当前明确记录 FAM-001 为“未冻结（S0 合格）”、`forward_start=待定`。
- 因此不能静默把 `development_cutoff` 当成 `forward_start`。

实施前应先确定一个精确 UTC `forward_start`，建议取“规格冻结并部署后的首个完整 1h bar”，而不是倒填到历史日期。未冻结时，108/109 应正常运行，但 `score_vol` 全部输出 NA。

FAM-001 是在 `wash_cvd` 条件集上开发的，规划默认只给 `wash_cvd` 标注；不能无证据外推到 `cvd_bear_divergence` 等其他 trigger。

---

## 1. 文件级改动清单

### 1.1 修改 `config/factor_funnel.yaml`

增加唯一的前向冻结规格，例如：

```yaml
forward_scores:
  score_vol:
    spec_id: FAM-001
    status: FROZEN
    applicable_triggers: [wash_cvd]
    forward_start: "待确认的精确 UTC 时间"
    form: capped_hinge
    source_feature: qv24_ratio
    qv_window_hours: 24
    baseline_window_hours: 720
    baseline_min_periods: 24
    lo: 1.0
    hi: 2.0
```

约束：

- `development_cutoff` 保持原值和原语义。
- 不修改 `contract_anomaly_rules.yaml`。
- 冻结后不原地改变公式；未来变更应使用新 spec/新列名。
- 这里的数值是分数定义，不是 trigger、VIX 或 Paper 规则。

### 1.2 修改 `EDGE_LEDGER.md`

仅更新 FAM-001 冻结绑定表：

- 填写具体 `spec_id`。
- 记录与配置一致的精确 `forward_start`。
- 状态改为已冻结。
- 引用 `config/factor_funnel.yaml`，不复制另一套可漂移的治理正文。

如果尚未完成 S1 冻结，这一步和 score 激活均保持 `PARK`。

### 1.3 修改 `scripts/108_contract_monitor.py`

增加一个小型纯函数，例如 `score_vol_at(klines, event_ts_ms, spec)`：

1. 只保留 `timestamp <= event_ts_ms` 的 bar。
2. 按现有 S0 口径计算：
   - `qv24 = quote_volume.rolling(24).sum()`
   - `baseline = qv24.rolling(720, min_periods=24).median()`
   - `qv24_ratio = qv24 / baseline`
3. 调用现有 `harness.lib.factor_funnel.capped_hinge`，不复制对数公式。
4. 事件早于 `forward_start`、规格未冻结、trigger 不适用、窗口不足、分母无效或数据缺失时返回 `NaN`。
5. 分数计算必须位于 `latest_trigger_state()` 已命中之后；任何分数异常都只产生 NA，绝不能 `continue` 或改变候选集合。
6. 候选字典增加 `"score_vol": score_vol`。
7. 控制台明细可追加 `score_vol=.../NA`，方便每日人工检查。

不改：

- `latest_trigger_state`
- `go_triggers`
- VIX 加载和 `vix_gate_state`
- liquidity/identity/MC 判断
- `direction`
- 任何候选跳过条件

### 1.4 修改 `harness/schemas/contract_alert_schema.yaml`

保持 `schema_version: v1` 和 `accepted_versions: [v1]`，只增加：

```yaml
score_vol:
  type: float
  required: false
  min: 0
  max: 1
```

这是 v1 的可选字段扩展：

- 旧 CSV 没有该列仍合法。
- 新 CSV 的空值合法。
- 老消费者依靠 `unknown_fields: ignore` 忽略该列。
- 不引入 v2，避免迫使 109、143 和历史积累文件迁移。

### 1.5 修改 `scripts/109_forward_replay.py`

增加两段独立逻辑。

第一段是兼容读取：

- 若 `score_vol` 不存在，补成全 NA。
- 使用 `pd.to_numeric(..., errors="coerce")`。
- 从同一个 `factor_funnel.yaml` 读取 `forward_start`。
- 防御性地把 `timestamp_ms < forward_start` 的任何分数清为 NA。
- 109 绝不回读 klines 重算历史分数。
- 默认模式合并候选和收益时保留 `score_vol`；旧累计行由 pandas 对齐为 NA。
- `--all` 模式也把候选键上的分数重新接到报告分析表。

第二段是报告追加：

```markdown
## 连续分数前向验证（描述性，不参与 verdict）
```

建议按 `score_vol × trigger × direction × horizon` 输出：

- 有效样本数与覆盖率
- 分位桶
- 每桶均值、中位数、胜率
- 最高桶减最低桶的 uplift
- 分数无变化或有效样本不足时明确输出 `INSUFFICIENT_VARIATION` / `NOT_ENOUGH_DATA`

复用 `factor_funnel.bucket_stats`。调用前先检查至少两个不同的有效分值，规避全相同分数时空分桶。

CSV 中现有 `ret_4h` 等字段保持原始标的收益。分桶报告为回答“是否赚更多”，可临时构造方向化收益：

```text
Long  → ret
Short → -ret
```

该方向化值只用于新增报告，不覆盖 CSV 收益，也不进入现有 bootstrap verdict 或 decay/CUSUM。

### 1.6 不修改 `harness/lib/factor_funnel.py`

直接复用现有：

- `capped_hinge`
- `bucket_stats`

本次不新增通用框架、不重构 213、不改变现有分桶语义。

### 1.7 测试文件

新建 `tests/test_contract_monitor_score_annotation.py`，避免把 score 语义混入 VIX 专属测试文件。

修改 `tests/test_forward_replay.py`，增加向后兼容和报告测试。

不手工编辑以下运行产物：

- `reports/contract_monitor_candidates.csv`
- `reports/forward_replay_returns.csv`
- `reports/forward_replay_report.md`

它们由 108/109 首次部署运行自然升级。

---

## 2. 分数应放在 108 还是 109

选择：在 108 计算，109 只传递和分析。

### 放在 108 的优点

- 108 已持有事件时点的 klines 与 `quote_volume`。
- 扫描时点天然形成 as-of 边界。
- 分数与候选同时冻结，后续数据更新不会改变既有事件分数。
- 109 不需要再次读取特征历史，职责仍是收益回填和报告。
- 可明确证明分数只是候选注释，不参与触发。

### 放在 108 的代价

- 108 需读取一个额外的冻结规格配置。
- 需要小心排除事件时点之后的 bar。
- 当前扫描只保留当天候选，因此历史行不会自动获得分数——这正符合 forward-only 纪律。

### 放在 109 的问题

- 需要重新读取全部 klines。
- 重跑历史积累时容易给冻结日前事件补出“事后分数”。
- 特征可能随数据修订而变化，破坏候选冻结时点的可审计性。
- 会把收益回填脚本扩成第二套特征计算器。

因此 109 不应计算或补算 `score_vol`。

---

## 3. Schema 与旧文件兼容

兼容策略是“v1 可选列扩展”：

- 108 新行包含 `score_vol`。
- 旧 candidates 无该列时，109 自动补 NA。
- 旧 accumulated returns 与新行 `concat` 时由 pandas 自动列对齐。
- 109 写出的累计 CSV会逐渐出现 `score_vol` 列；历史行保持空值。
- 143 使用 `pd.read_csv` 后按所需字段取值，不要求精确列集合，因此新增列不会改变纸面逻辑。
- 不清理当前累计 CSV 中已有的 `timestamp_new`、`mfe_pct_new` 等旁支问题，避免扩大改动面。

---

## 4. `forward_start` 落地纪律

采用一个精确 UTC 时间作为唯一边界：

```python
eligible = (
    spec_status == "FROZEN"
    and trigger in applicable_triggers
    and timestamp_ms >= forward_start_ms
)
```

规则：

- `< forward_start`：`score_vol = NaN`
- `== forward_start`：允许计算
- 配置缺失、格式非法或状态未冻结：分数全 NA，但候选链继续运行并打印 WARNING
- 108 只计算当前触发事件
- 109 绝不回算分数，并再次清空边界前的异常值
- CSV 中 NA 使用空单元格，不使用 `0`；0 是合法的低分，不能与“不适用/不可用”混淆
- 报告分桶只使用 forward-start 后的非空值，并单独展示覆盖率

---

## 5. 测试与验收

### 5.1 108 新增测试

`tests/test_contract_monitor_score_annotation.py` 锁定：

1. 与 FAM-001 公式一致，包括 ratio=1 → 0、ratio=2 → 1、中间值按 log 插值。
2. `timestamp > event_ts` 的巨量未来 bar 不改变事件分数。
3. 事件早于 `forward_start` 返回 NA。
4. 事件恰好等于边界可计算。
5. 非 `wash_cvd` trigger 返回 NA。
6. 缺列、窗口不足、无效分母返回 NA，不抛异常。
7. 分数恒在 `[0, 1]`。

现有 `tests/test_contract_monitor_vix_gate.py` 原样通过，证明 VIX 行为未漂移。

### 5.2 109 新增测试

在 `tests/test_forward_replay.py` 增加：

1. 旧 candidates 没有 `score_vol` 时正常运行并补 NA。
2. 新候选分数进入累计 CSV 后保持数值不变。
3. pre-forward-start 的非空分数被清成 NA。
4. `--all` 分析路径能重新接回 score。
5. 正常五桶样本的 high-low uplift 数值正确。
6. 全 NA、单一分值、重复边界和小样本不崩溃，并输出明确状态。
7. 新分桶段不改变原有 `verdicts`。
8. Short 样本只在新增报告中进行方向化，原始 `ret_*` 不变。

### 5.3 测试命令

先跑局部回归：

```powershell
python -m pytest tests/test_contract_monitor_vix_gate.py tests/test_contract_monitor_score_annotation.py tests/test_forward_replay.py tests/test_factor_funnel.py -q
```

再跑全量：

```powershell
python -m pytest -q
git diff --check
```

验收要求：

- 原有 487 tests 全部保持通过。
- 新增测试全部通过，因此最终总数应大于 487。
- `config/contract_anomaly_rules.yaml` 和 `scripts/143_paper_trade.py` 没有 diff：

```powershell
git diff -- config/contract_anomaly_rules.yaml scripts/143_paper_trade.py
```

### 5.4 每日链运行验收

先运行 108：

```powershell
python scripts/108_contract_monitor.py
```

检查：

- 脚本正常结束。
- 相同冻结输入下，`alert_id` 集合和候选数与改造前一致。
- CSV 出现可选 `score_vol` 列。
- 非适用 trigger、冻结日前事件或数据不足显示为空值。
- VIX、liquidity、identity、direction 列值未变化。

再运行 109 默认模式：

```powershell
python scripts/109_forward_replay.py --seed 0
```

检查：

- 旧累计 CSV 可正常读取。
- `forward_replay_returns.csv` 保留 `score_vol`。
- 现有 horizon verdict 与相同数据、相同 seed 的改造前结果一致。
- `forward_replay_report.md` 新增“连续分数前向验证”段。

最后运行全量观察模式：

```powershell
python scripts/109_forward_replay.py --all --seed 0
```

检查：

- 历史无 score 行不报错。
- 只用有效前向分数分桶。
- 小样本明确标注，不产生新的 GO/NO_GO。
- 原 decay/CUSUM 段仍存在且输出正常。

不运行 143 作为本改造的写入验收，避免无必要地改动纸面账户产物。

---

## 6. 明确不做

本批次不做以下事项：

- 不修改任何 trigger 条件、阈值、冷却期或 Go/No-Go 门控。
- 不修改 `config/contract_anomaly_rules.yaml`。
- 不解决 VIX 注释与 E24b 的语义冲突。
- 不改变 `vix_gate_state`、`vix_gate_ok` 或 VIX 对候选的现有处理。
- 不让 score 过滤、增加或删除候选。
- 不让 score 进入既有 bootstrap verdict、decay/CUSUM。
- 不修改 143、A/B/C/D 账户、方向、仓位、成本、止损或持有期。
- 不回填冻结日前的历史分数。
- 不给 FAM-001 未研究的 trigger 强行打分。
- 不新增数据库、依赖、服务、抽象注册中心或通用评分框架。
- 不顺手清理累计 CSV 的现有旁支列问题。

---

## 7. 风险与回滚

### 主要风险

- **冻结状态不真实**：当前 Ledger 仍是未冻结。未明确 `forward_start` 前只能部署 NA-safe 代码，不能激活分数。
- **适用域外推**：FAM-001 来自 wash_cvd 条件集；对其他 trigger 打分会形成未经验证的解释。
- **as-of 前视**：若直接取表尾而非 `timestamp <= event_ts`，未来 bar 会污染分数。
- **0 与 NA 混淆**：0 是有效低分，历史不可用必须写 NA。
- **稀疏或大量并列**：`qcut` 可能减少桶数；必须报告实际桶数，不能硬凑五桶。
- **历史文件列漂移**：旧/new CSV 混合时 pandas 会自动扩列；测试需覆盖缺列和重复运行。
- **运行数据更新导致误判候选变化**：候选集前后比较必须使用同一份冻结输入快照，不能跨每日数据拉取比较。

### 回滚方案

把整个改造做成一个独立、可逆提交：

1. 回退 108、109、schema、配置、Ledger 和测试的该提交。
2. 无数据库迁移，无需数据修复。
3. 已产生 CSV 中的 `score_vol` 是可选未知列，旧消费者可安全忽略。
4. 若要求字节级恢复运行产物，部署前保留三个 report 文件的副本并恢复；不要删除历史证据。
5. 回滚不触碰 trigger、Paper 或 VIX，因为这些文件从始至终没有修改。

本轮仅完成规划，未修改仓库。
