# 脚本规格说明 — AlphaHive V3.1.1 Phase 1

> 这不是成品代码，是**精确 spec**（因为要接你本地真实数据路径/列名）。
> 照 spec 实现，每个脚本末尾逐条过【防坑自检】。所有脚本输出顶部先打三条诚实铁律。
> 所有随机性走 `harness/seed.py`；所有成本走 `config/friction_config.yaml`；所有数据读 `input_snapshot.csv`。
> 按依赖顺序实现：01 → 02 → 03 → 04 → 05 → 99 → 06。

---

## 01_build_universe.py

**职责**：读 coinglass_db，按 `universe_config.yaml` 产出当日 universe。

**输入**：coinglass_db klines/funding/oi（路径见 `data_contracts.yaml`）。
**输出**：`config/universe.json`（symbol 列表 + 每个的 rank/turnover/history_tier）。

**逻辑**：
1. 先跑 `data_contracts.yaml` 校验（尤其 funding 单位断言）。任一失败 → STOP_AND_REPORT_OWNER。
2. 按 rank 10-80 + 24h 成交额 ≥ $10M 过滤。
3. 排除 stablecoins/delisted/majors（BTC/ETH/SOL）。
4. 给每个标的算 history_tier（Full/Partial/Insufficient，按可用天数）。
5. 写 universe.json。

**【防坑自检】**：
- ☐ funding 单位校验通过（中位数绝对值 ≥ 1e-5，不是 1e-6 量级）。
- ☐ BTC 不在 universe（它是对冲基准，另存）。
- ☐ rank 排名源是 Binance 永续，不是现货。
- ☐ Insufficient 标的仍留在 universe（仅观察），但标记正确。

---

## 02_scan_anomalies.py

**职责**：本流水线核心。冻结快照 + 产候选 + 写主账本。

**输入**：universe.json + coinglass_db。
**输出**：
- `harness/runs/{run_id}/input_snapshot.csv`（**90d 长表**，洞2）
- `harness/runs/{run_id}/run_manifest.json`（照 template 填全）
- `harness/runs/{run_id}/candidates.csv` + 追加写 `ledger/Anomaly_Ledger.csv`

**逻辑**：
1. 生成 `run_id`（如 `{YYYYMMDD}_{HHMM}_utc`）。
2. **冻结快照**：对每个 universe 标的，取扫描时刻**往前 90 天**的每根 K 线（OHLCV+funding+OI），写成长表 input_snapshot.csv。之后所有计算只读它。算 sha256 写进 manifest。
3. **算触发指标**：分位/z-score 用**标的自身 90d 时间序列**（NOT 横截面，硬约束1）。算 large_move（abs≥10% 或 excess≥7%）。
4. **产候选**：按 `scan_rules.yaml` triggers 命中的标的成为候选。目标 10-20 个/次。
5. **Top-N 标记**：前 5 个 `is_top_candidate=true` 进人工审查；其余 `decision=AutoSkipped, direction_sign=0`（但仍要基线，03 处理）。
6. 每条候选生成 record_id，写 trigger_reason（**扫描当场写，禁止事后补**，禁止事项7）。
7. 写 manifest（config_versions + data_cutoff + snapshot + candidate_summary + integrity）。

**【防坑自检】**：
- ☐ input_snapshot 是长表且含 90d×每标的，不是单行横截面。
- ☐ 分位用自序列不是横截面。
- ☐ trigger_reason 在写入时已填，不是占位。
- ☐ entry_price_ref 留空（05 才填，此刻还没有"扫描后第一根完整K线"）。
- ☐ 快照冻结后本脚本不再回读实时数据库。
- ☐ manifest.integrity.no_lookahead_attested=true 且真实成立。

---

## 03_generate_baselines.py

**职责**：对每条候选生成双随机基线（硬约束2，三对齐）。

**输入**：candidates.csv + input_snapshot.csv。
**输出**：`harness/runs/{run_id}/baselines.csv` + 追加 `ledger/Baseline_Ledger.csv`。

**逻辑**：对每条候选（含 AutoSkipped），生成两条基线：
- **基线A candidate_pool_random**：从**候选池**随机抽一个 symbol。
- **基线B full_pool_random**：从**全 universe** 随机抽一个 symbol。
- 两者都：与父候选**同 scan_time_utc、同 holding_period、随机分配方向**（三对齐）。
- 种子 = `seed.baseline_rng(scan_time_utc, parent_record_id, baseline_type)`，方向 = `seed.random_direction(rng)`。

**【防坑自检】**：
- ☐ 种子完全来自 seed.py 的 md5 哈希，无 np.random 裸调用。
- ☐ 基线的 scan_time_utc/holding_period 与父候选逐一对齐。
- ☐ 每条候选（包括 AutoSkipped）都有恰好 A+B 两条基线。
- ☐ 重跑本脚本，baselines.csv 字节级一致（回归闸）。

---

## 04_calc_friction.py

**职责**：按 friction_config 算悲观摩擦。是成本的唯一计算点。

**输入**：Anomaly_Ledger + Baseline_Ledger（需 symbol/turnover/holding/direction）。
**输出**：回填两账本的 `friction_bps_roundtrip` + `funding_cost_component`。

**逻辑**：
1. `friction_bps_roundtrip = 2 × (taker_fee_bps + slippage_bps(turnover) + spread_bps_fallback(turnover))`。
2. `funding_cost_component`：按持有小时数 × 每8h funding，方向性（direction_sign 决定收/付）。**funding 单位严格按 friction_config，禁止链式 /100**（历史三次坑）。
3. 不含市场冲击模型（第1周已知不完整，标注）。

**【防坑自检】**：
- ☐ 成本全来自 friction_config.yaml，脚本内无 magic number。
- ☐ funding 分量量级合理（$X 名义、N 天，应是"几十刀量级"不是 $0，对照 exec_planner 教训）。
- ☐ 低容量标的（$10-30M）滑点用 20bps 档，没错档到 5bps。
- ☐ spread fallback 生效且标记 is_estimate。

---

## 05_update_returns.py

**职责**：事后回填 4h/24h/72h/7d 方向性超额收益（硬约束3+4）。

**输入**：Anomaly_Ledger + Baseline_Ledger + 事后行情（或 input_snapshot 若已覆盖持有期）。
**输出**：回填价格锚 + dir_excess_ret_* + dir_excess_ret_net_*。

**逻辑**：
1. **价格对齐**：`entry_price` = scan_time_utc 后**第一根完整 K 线的 open**；`exit_price` = entry 后 N 小时 K 线的 close；BTC 对冲价用**同一时间戳**。
2. `方向性超额收益 = direction_sign × (标的收益率 − BTC收益率)`。
3. `dir_excess_ret_net = dir_excess_ret − friction_bps_roundtrip/1e4 − funding_cost_component`。
4. 未到期的持有期填 `Pending`。
5. AutoSkipped（sign=0）超额收益恒 0，标记清楚。

**【防坑自检】**：
- ☐ entry 用"扫描后第一根完整K线"，不是扫描当根（防前视）。
- ☐ BTC 对冲价与标的严格同时间戳。
- ☐ 价格只来自 snapshot 或事后行情，不混源。
- ☐ 无 friction 的收益不写入 net 列（无 friction 不进判断）。
- ☐ 72h/7d 未到期填 Pending 不填 0。

---

## 99_validate_schema.py

**职责**：账本 schema 校验 + 回归闸。周日跑，或每次改共享代码后跑。

**输入**：两账本 + `harness/schemas/*.yaml`。
**输出**：校验报告（stdout + `reports/` 落一份）。

**逻辑**：
1. 逐行校验字段类型/范围/枚举（按 schema）。
2. 校验 cross_field_rules（如 Long↔sign=1、Paper Trade↔hypothesis 非空、非 AutoSkipped↔有两条基线）。
3. **回归闸**：对一个已存在的 run_id，用 seed.py 重跑分位/基线，与账本已存值比对，须字节级一致。
4. 任一失败列出 record_id + 违反规则。

**【防坑自检】**：
- ☐ 回归闸真重跑并 diff，不是只读现值。
- ☐ 报告列出每条违规的 record_id 和具体规则，不是只给总数。
- ☐ Tiny Live 出现 = 立即 FAIL（第1周禁用）。

---

## 06_weekly_review.py

**职责**：周末导出周账本统计，供粘给云端做复盘。

**输入**：两账本（本周切片）。
**输出**：追加 `ledger/Review_Log.csv` + `reports/weekly/{week}.md`（供粘给我）。

**逻辑**：
1. 统计：总候选/人工决策/Paper/AutoSkipped/completed_4h/completed_24h。
2. **⚠️ completed 计数只算有人工方向决策(Long/Short)的记录，AutoSkipped 不计入**（洞3）。
3. Paper Trade 的 mean/median 摩擦后超额 vs 基线A/B 均值。
4. 假设证伪/验证计数。
5. 第4周才算 GO/NO-GO；第1周只输出样本量对照 DoD。

**【防坑自检】**：
- ☐ completed_4h/24h 排除 AutoSkipped（不用结构性0凑DoD）。
- ☐ Paper vs 基线对比用摩擦后超额收益，不是绝对/毛收益。
- ☐ 第1周不下 GO/NO-GO 结论（样本不足，禁止事项对应"延迟"）。
- ☐ 输出顶部三条诚实铁律。

---

## 全脚本通用红线（每个都适用）

1. ❌ 任何 ccxt/binance/API key/下单代码 → 出现即停，报 Owner。
2. ❌ 改写历史账本记录（只追加；人工改走 manual_override_log.csv）。
3. ❌ 用未来数据算分位/收益。
4. ✅ 随机→seed.py；成本→friction_config；数据→input_snapshot。
5. ✅ git 仅本地，无 push（token 红线）。
