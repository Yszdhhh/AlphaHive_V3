先按项目入口读取规范，再核对 108/109 与 factor_funnel 相关实现，再给出审查结论。继续核对 108/109 的 schema、候选写出与 verdict 路径，以及是否已有 score_vol / FAM-001 相关痕迹。## 结论：**需修改后实施**（方向可接受，不是直接开干；更简路径优先考虑）

对照 `108` / `109` / `factor_funnel` / `factor_funnel.yaml` / `EDGE_LEDGER` FAM-001：方案主轴正确——**纯标注、不碰 trigger/VIX/paper/规则、verdict/143/decay 不读分**——与现有 VIX「只标注不硬跳」一致。但有几处口径与生命周期缺口，修完再动代码。

---

### a) 泄漏 / 口径 / 兼容

| 点 | 判定 |
|---|---|
| 事件时点 asof + rolling 历史 | **OK**。108 已是 tip bar；score 与 trigger 同 bar 一致，不新增前视。 |
| 分数异常 → NA、候选集不变 | **OK**，对齐 regime/VIX 失败降级路径。 |
| 109 不重算历史分 | **必须写死**；当前 109 会回填 `ret_*`、concat 积累，**绝不能**回读 klines 补 `score_vol`。 |
| Verdict 隔离 | **现状安全**：109 bootstrap / decay 只用收益；143 不读 `contract_monitor_candidates` 的分数列。 |
| Schema v1 可选列 | **兼容可行**（`unknown_fields: ignore`；积累 CSV 已有列漂移先例）。但 `contract_alert_schema.yaml` 本就落后（regime/vix 未登记），加列时应一并登记 `score_vol: required:false`。 |
| **口径漏洞（要改）** | 规划写「qv24/720h 中位 ratio」，S0 实装在 `213` 是：`qv24=sum(24)` / `qv24.rolling(720, min_periods=24).median()`；`121` 则是 `min_periods=360`。**不钉死 = 与 FAM-001 S0 不是同一分数。** `capped_hinge(lo=1,hi=2)` 与 `EDGE_LEDGER` 一致；必须复用 `factor_funnel.capped_hinge` + 与 213 **同一 raw ratio**，禁止 108 另写一套。 |
| 软泄漏 | 同报告里「verdict + 分桶 uplift」会污染人读，虽非统计泄漏。**硬标题**：描述性 / exploratory / 不参与 verdict。 |
| 未满 1h bar | 与现 108 tip 一致，不算新洞；`forward_start=部署后首个完整 1h bar` 合理。 |

---

### b) 「冻结门控 + NA」vs「先冻结再上线」

- FAM-001 仍是 **S0 合格、S1 未冻结**（`EDGE_LEDGER` / `QUANT_PRE_REGISTRY`）。
- **仅作管道标注、且全 NA 直到 S1 冻结 + 写死 `forward_start`**：**合理**，比「未冻结就当真分数」干净。
- **若要拿分桶 uplift 当前向证据 / S2**：必须 **先 S1 冻结再计分**；否则 uplift 只能算工程调试，不能进漏斗确认。
- 建议：冻结状态读 **单一真理源**（如 ledger 的 `forward_start` / `spec_id`，勿散落 if 字符串）；未冻结路径甚至可不写列或恒 NA。

---

### c) 报告分桶 uplift 注意点

- 前向影子本就 **n 小**；再分桶 → 每桶更碎，**禁止**当显著性叙事。
- `capped_hinge` 大量贴 0/1 → `qcut` 易塌缩；固定阈值桶或 ≤2–3 档更稳。
- 同 ts 多币、持有期重叠 → 相关事件，CI 偏窄（方法论已写）；最多报 n / mean·median / high−low，**不要**给分桶 bootstrap「GO」。
- 只对 **非 NA 且 `timestamp ≥ forward_start`** 分桶；NA 单独报 coverage。
- 样本不足（如有效 n&lt;30 或每桶 n&lt;10）→ 整段 **「样本不足，不展示 uplift」**。

---

### d) 更简单替代（更符合 YAGNI）

1. **最优**：先跑 S1（214）冻结 `score_vol`；用 `forward_replay_returns.csv` **离线 asof join** 出分桶表——**零改 108/109 热路径、零 schema 风险**。  
2. 次优：108 只落 **raw `qv24_ratio`**（可选列），形态变换离线再做。  
3. 现方案（108 内算分 → 109 透传 → 报告加一节）工程上可行，但是 **为未冻结因子提前接线**，复杂度高于收益。

---

### e) 终裁

**需修改后实施**——不是否决。

实施前硬条件：

1. **钉死公式** = 213 的 `feature_vol_ratio` + `capped_hinge(1,2)`（写进注释/单测）。  
2. **冻结门控** 绑 `forward_start`；未冻结全 NA；**禁止**历史回填分数。  
3. 报告分桶 **显式 non-verdict**；n 不足不展示。  
4. 异常只 NA，**不改**候选集 / trigger / VIX / paper / 规则。  
5. 优先评估是否改为 **离线标注**；若坚持接线，改动面仍应 ≤108 写列 + 109 透传/报告一节 + schema 可选字段。

**一句话**：标注链纪律对；**先钉口径与冻结语义，再动 108/109**；真要省事，**S1 冻结 + 离线 join** 比生产接线更干净。
