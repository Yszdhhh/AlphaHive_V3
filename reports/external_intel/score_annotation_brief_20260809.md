# 108/109 连续打分标注改造——背景简报（2026-08-09）

> 用途：给 codex-sol 出实施规划的背景。请结合本简报 + 仓库实际代码给出文件级规划。

## 1. 现状（运行链）

- **108_contract_monitor.py**（每日 07:35）：扫 binance_free_db（前向区），检测 wash_cvd/cvd_bear_divergence 触发 → 输出 `reports/contract_monitor_candidates.csv`。候选行已有：trigger/symbol/timestamp_ms/feature_value/direction/regime/vix_status/vix_close/vix_q75/vix_gate_ok/market_cap_usd/liquidity_24h_usd/liquidity_ok/identity_gate_status/source/notes。触发规则在 `config/contract_anomaly_rules.yaml`（wash_cvd 规则含 vix_gate 标注、threshold 等；⚠️ 该规则文件当前文本含 VIX 语义冲突：vix_gate 的注释说高 VIX 建议跳过，但 EDGE_LEDGER E24b 记录高波动更强——本次改造**不动 VIX 逻辑**）。
- **109_forward_replay.py**（每日 08:35）：读 candidates CSV → 对每个候选回填 4h/24h/72h/168h 收益（binance klines，时间对齐无前视）→ `reports/forward_replay_returns.csv` → 衰减监测（事件计数窗 + CUSUM）。
- **143_paper_trade.py**（每日 08:40）：读 forward_replay_returns.csv → A/B/C/D 四账户纸面结算。
- **事件研究基线**：wash_cvd 定义在 scripts/115（washout ∧ cvd_div>2.0，72h 冷却）。

## 2. 目标：连续打分标注（不改触发、不改纸面、不影响现有判决）

- 给 108 候选**多记分数列**（当前只 FAM-001 放量分：score_vol = clip((log(qv24_ratio)-log(1))/(log(2)-log(1)), 0, 1)，qv24_ratio = 事件时点前 24h quote_volume / 30d 中位数）。
- 109 记录收益时**保留分数**，并在报告里加"按分数分桶的前向收益 uplift"（分数高是否赚更多）。
- 目的：连续打分的前向验证——不用等专门研究，前向积累自动回答。
- 约束：候选集不变（触发二元不动）；纸面账户不动；schema 向后兼容（旧候选无分数列/缺值不报错）；forward_start 纪律（分数只在冻结日后有效，冻结前历史候选分数标 NA）；现有 487 tests 全过；每日链照常跑。

## 3. 相关文件

- `scripts/108_contract_monitor.py`（候选构造 + CSV 输出）
- `scripts/109_forward_replay.py`（收益回填 + 衰减 + 报告）
- `harness/schemas/contract_alert_schema.yaml`（候选 schema，改需版本兼容）
- `harness/lib/factor_funnel.py`（capped_hinge 形态函数，可复用）
- `config/factor_funnel.yaml`（FAM-001 规格、development_cutoff、retained_modulators）
- `tests/test_contract_monitor_vix_gate.py`、`tests/test_forward_replay.py`（现有测试模式）
- `reports/contract_monitor_candidates.csv`、`reports/forward_replay_returns.csv`（现有输出样例）

## 4. 请规划

1. 文件级改动清单（新建/修改，最小面）：108 加分数计算与列、schema 可选字段、109 保留分数 + 分桶 uplift 报告、测试。
2. 分数计算放 108 还是 109？利弊（108 是扫描时点 asof 天然无前视；109 已有事件表但需回读 klines——哪个更贴合现有代码结构）。
3. schema 版本兼容方案（旧候选缺列处理）。
4. forward_start 纪律怎么落地（冻结日前的候选分数标 NA，避免历史污染）。
5. 测试清单（锁什么）。
6. 明确不做（不碰触发/纸面/VIX/rule 数值）。
7. 风险与回滚。
输出：Markdown 到 stdout，务实可直接照做，避免过度工程（个人系统、单机 pandas）。
