# AlphaHive V3 × botv2 执行层审查

## 结论先行

**不建议把 botv2 执行层整体接入 AlphaHive V3。** 当前包里的 live 路径既不完整，也没有达到可靠 OMS 的最低标准。更干净的方案是：

- 保留 AlphaHive 已有的 `PaperPlan + 离线模拟器 + 内容哈希/OwnerDecision` 基础；
- 从 botv2 提炼需求和风险案例，少量重写纯执行机制；
- 测试网和未来 live 放进与研究仓隔离的执行网关，不把 `trader.py` 搬进 AlphaHive；
- Phase 1 的离线模拟增强可先做，但连接 108 prospective 事件、测试网或 live 都必须继续 `PARK`，等 Owner 针对具体路径签批。

本次检查的实际快照为 `trader.py` 5330 行、`main.py` 7603 行、`strategy.py` 2308 行、`config.py` 1600 行，与任务描述略有差异，可能是快照或换行统计不同。

---

## 1. botv2 执行层盘点

### 组件现状

| 能力 | 代码中有什么 | 可用性判断 |
|---|---|---|
| 下单 | market、IOC limit、maker GTC；随机 `client_order_id`；开仓和 `reduceOnly` 减仓 | 有雏形，不能直接用于 live |
| 撤单 | 纸面挂单超时后直接从字典移除 | **没有交易所撤单闭环**；GTC live 订单可能遗留 |
| 成交检查 | 下单后最多轮询 5 次、每次约 350ms | 不足；部分成交被视为终态，没有后续补单/撤余单 |
| 重连 | 每次下单临时创建 CCXT adapter，完成后关闭 | 没有持久用户数据流，也谈不上订单流重连 |
| 状态恢复 | paper JSON 恢复持仓、挂单、历史；live 启动拉余额和持仓 | live 会丢失开放订单和真实成交历史 |
| 对账 | 依赖未打包的 `Reconciler`，按持仓数量做一次检查 | 不是完整的 order/fill/cash reconciliation |
| 风控闸 | 回撤、浮亏、连败、REDUCE_ONLY/HALT、相关性、持仓数、资金占用、杠杆上限、冷却、点差、快照时效、微观翻转、VolShock | 覆盖面广，但和信号、仓位、配置强耦合 |
| 仓位管理 | paper PnL、funding、止损、TP1、trailing、时间止损、部分平仓 | paper 可作研究原型，live 账务不可信 |
| 持久化 | 单个 JSON，临时文件 + `fsync` + `os.replace` + 备份 | paper 尚可；不适合作为多订单并发 OMS |
| 交易所适配 | 动态导入 `execution.binance_ccxt.BinanceExecutionAdapter` | adapter 未打包，无法验证行为 |

### 是不是币安、哪一代 API

可以确认其目标是 **Binance USDT-M Futures**：

- 使用 `positionAmt`、`positionSide`、`totalWalletBalance`、`reduceOnly`、`leverageBracket` 等 Binance Futures 字段；
- adapter 名为 `execution.binance_ccxt.BinanceExecutionAdapter`；
- 支持 `sandbox/testnet` 开关；
- 默认凭证名为 `BINANCE_API_KEY`、`BINANCE_API_SECRET`。

但**无法确认具体 Binance API 代际或 CCXT 版本**：

- `execution/binance_ccxt.py` 不在包内；
- 没有 `requirements.txt`、锁文件或 CCXT 版本；
- 配置只写了 `/leverageBracket`，不足以证明底层使用 `/fapi/v1`、`v2` 或其他版本；
- 因此不能诚实地称为“某代 Binance API”。

它不是可验证的官方 Binance SDK 集成，而是一个缺失实现的 CCXT 封装。

### 直接阻断 live 的问题

1. **执行依赖严重缺失**

   [trader.py](</G:/botv2_demo_deps/strategy_deps/trader.py:16>) 还依赖：

   - `execution.oms`
   - `execution.reconciliation`
   - `execution.binance_ccxt`
   - `data_stream`
   - `position_sizing`
   - `risk_state_store`
   - `online_metrics`
   - `indicators`

   `main.py` 还缺 `adaptive`、`shadow_learning`、`hft.md_process` 等。当前目录只能通过语法编译，不能导入或运行执行层。

2. **启动 live 会重置风控状态**

   live preflight 使用 `reset_risk_state=True`；同步时把：

   - high-water mark 重设为当前余额；
   - drawdown、连败清零；
   - `is_halted=False`；
   - 冷却和最近开仓时间清空。

   这意味着重启可能解除上一进程留下的熔断，是 live blocker。

3. **同步时重建 OMS、清空 pending**

   live snapshot 应用时重新创建 `OrderRepository`，并执行 `pending_orders = {}`。原有订单状态、未成交订单和成交序列都会丢失，只用当前持仓合成 `LIVEBOOT-*` 的 FILLED 订单。

4. **没有完整订单生命周期**

   `PARTIALLY_FILLED` 被列为轮询终态；没有：

   - 用户数据流 execution report；
   - 持久开放订单；
   - cancel/replace；
   - 撤余单；
   - 断线后的 open-order/my-trades 回补；
   - “POST 超时但交易所其实已接单”的查询恢复。

5. **maker GTC 存在孤儿订单风险**

   maker 未立即成交时可能返回 `ORDER_PLACED`，但紧接着的账户同步会重建 OMS；代码里没有交易所撤单入口。调用方把这个字符串当成普通 pending 通知，但实际订单可能继续留在交易所。

6. **幂等性不足**

   [订单 ID](</G:/botv2_demo_deps/strategy_deps/trader.py:2308>) 每次用随机 UUID 生成。事件重放或网络超时重试不能生成相同 ID，因此无法用 `client_order_id` 保证 exactly-once intent。

7. **代码质量不适合安全执行**

   - 一个 5330 行 `PaperTraderPro` 同时负责配置、信号闸、定价、仓位、OMS、交易所和报表；
   - 81 个 `except Exception`、13 个裸 `except`、43 个静默 `pass`；
   - 直接从 trader 导入 `strategy`，又从 trader 反向 `import main`，边界循环；
   - `EntryContext` 的一批字段意外写在 `resolve_runtime_label()` 的 `return` 后面，虽然 Python 允许之后动态赋值，但 dataclass 声明已失真；
   - 没有 trader、RiskManager、adapter、重启恢复或部分成交测试。

8. **配置冲突且违反 AlphaHive 纪律**

   [config.py](</G:/botv2_demo_deps/strategy_deps/config.py:497>) 同时存在重复的 `execution_mode`、`taker_ioc` 配置，并把信号分数、drought、Kelly、regime 直接映射到仓位和杠杆。AlphaHive 宪法明确规定：异常评分不能驱动仓位或杠杆，因此这些逻辑不能迁移。

### 哪些值得复用

**可以复用为需求/测试案例，而不是复制代码：**

- preflight 必须检查模式、凭证、adapter、账户同步；
- `client_order_id`、exchange order ID 双标识；
- `reduceOnly` 平仓；
- symbol filter、tick size、step size、min notional；
- stale snapshot、spread、最大滑点的 fail-closed 检查；
- `NORMAL / REDUCE_ONLY / HALT` 风控状态；
- 高水位、回撤、连续亏损持久化；
- 重启后以交易所状态为事实源进行对账。

**不建议复用：**

- `PaperTraderPro` 整类；
- `main.py` 编排；
- 1600 行 `config.py`；
- `engines_v2.VolScaledKelly`；
- `expert_mixer.py`；
- botv2 的信号→仓位→杠杆链；
- 缺失的 OMS/adapter 在补齐并单独审计前也不能算可复用资产。

---

## 2. AlphaHive 108→109→143 的执行缺口

### 当前链不是 prospective 执行链

现在的串行关系是：

```text
108 候选
  → 109 等待未来 4h/24h/72h/168h 收益
  → 143 在未来窗口结束后回放交易结果
```

这只能做历史/延迟结算。真正的 prospective paper 应改成分叉：

```text
108 CandidateEvent
  ├─→ 109 后续补 forward label，仅供研究评价
  └─→ eligibility + OwnerDecision + PaperPlan
        → OrderIntent
        → 模拟撮合 / 测试网
        → ExecutionReport / Fill
        → 持仓与账户账本
        → 143 只做 A/B/C/D 投影与对账
```

**109 不能成为下单前置条件**，否则下单时已经知道未来收益。

### 必补能力

| 缺口 | 最小实现 |
|---|---|
| 事件契约 | 以 `alert_id` 为 canonical event ID，保留 trigger、direction、事件时间、数据快照 hash |
| 去重 | 唯一键至少为 `(account_id, alert_id, plan_hash)`；109 当前按 `(symbol,timestamp)` 去重可能吞掉同时间不同 trigger |
| 事件→订单 | 明确账户 A/B/C/D 的入场时间、方向、名义金额、订单类型、有效期和取消条件 |
| 订单状态机 | `NEW → ACK → PARTIALLY_FILLED → FILLED/CANCELED/REJECTED/EXPIRED` |
| 成交回报 | 每次 fill 单独记录 qty、price、fee、slippage、exchange timestamp、累计成交量 |
| 撮合模型 | 下一 bar open、side-aware 滑点；价格跳空；同 bar 止损/止盈保守顺序；最小成交量参与率 |
| 部分成交 | 每 bar 按可成交容量撮合剩余量；超时撤余单。Phase 1 不必模拟复杂队列位置 |
| 持久化 | append-only 事件账本 + 可重建 projection；不能只靠覆盖 CSV |
| 重启恢复 | 从 orders/fills 重建持仓和现金；每根 bar 有 watermark，重复消费不重复成交 |
| 账户对账 | A/B/C/D 分账，交易、费用、现金、持仓、权益满足会计恒等式 |
| 测试网对账 | 本地 intent ↔ exchange order ↔ fills ↔ position ↔ balance 五层核对 |
| 风控隔离 | 风控只决定允许/拒绝及固定风险预算，不读取异常分数决定杠杆 |

### 143 当前的具体问题

[scripts/143_paper_trade.py](</G:/Quant test/AlphaHive_V3/scripts/143_paper_trade.py:47>) 适合报表回放，不适合作为执行账本：

- `$1000` 和 `27bps` 是脚本内 magic number，没有读取 `friction_config.yaml`；
- 方向字段没有进入 `simulate()`，逻辑实际按 long 计算；
- 成本账务量纲不一致：`gross` 已通过 `entry + cost` 扣入场成本，之后又从美元 PnL 中直接减去价格单位的 `cost`；
- B 账户要等满 168h 才整体结算，不能形成实时 open position/stop fill；
- MDD 状态只基于本轮新增事件推进，重启时不会从已有流水完整恢复；
- CSV 覆盖写没有锁、事务和 crash recovery；
- 入场全成或不成，没有部分成交、容量和交易所拒单；
- A/B/C 在同一宽表里，不是可独立审计的账户账本。

### AlphaHive 已有、应优先扩展的基础

当前 V3 已经比 botv2 更适合作为 Phase 1 起点：

- [paper_plan_engine.py](</G:/Quant test/AlphaHive_V3/harness/lib/paper_plan_engine.py:99>)：绑定 job、证据 hash、OwnerDecision、preset hash，且强制 `no_live_order_path=True`；
- [offline_execution_simulator.py](</G:/Quant test/AlphaHive_V3/harness/lib/offline_execution_simulator.py:97>)：支持方向、止损优先、跳空、分批止盈、时间退出和幂等完成事件；
- [local_paper_plan_ledger.py](</G:/Quant test/AlphaHive_V3/harness/lib/local_paper_plan_ledger.py:62>)：有 immutable plan、hash、staging、恢复和幂等发布。

局限是这些目前仍是 **local/synthetic 单计划基础设施**，未连接 production ResearchJob、108、调度器或网络。相关 15 个测试全部通过，但这不等于 Paper 已获准激活。

---

## 3. 分阶段结合规划

## Phase 1：纸面执行增强

### Phase 1A：纯离线基础，可在 T1/T2 范围内准备

保留：

- `scripts/108_contract_monitor.py`
- `scripts/109_forward_replay.py`
- `harness/lib/paper_plan_engine.py`
- `harness/lib/offline_execution_simulator.py`
- `config/paper_execution_presets.yaml`
- `config/friction_config.yaml`

新建最少两个模块：

- `harness/lib/paper_event_bridge.py`  
  验证 `alert_id`、direction、OwnerDecision/PaperPlan hash，输出确定性的 OrderIntent。禁止直接把 108 行转成订单。

- `harness/lib/paper_execution_ledger.py`  
  用 stdlib SQLite 保存 accounts、orders、fills、positions、cash events 和 bar watermark；唯一键承担幂等。

调整：

- 扩展 `offline_execution_simulator.py`，增加 order ACK、部分成交、撤余单、容量限制；不另造大型撮合框架。
- 把 `143_paper_trade.py` 降为 ledger projection/report，并在迁移期双跑：
  - legacy CSV；
  - 新账本投影；
  - 输出差异，不直接覆盖历史证据。
- 成本只从现有配置读取；`27bps` 与 `friction_config.yaml` 当前分档口径的冲突必须由 Owner 决定，不能静默统一。
- 补测试：重复事件、重启恢复、同 bar stop/TP、gap、partial fill、方向、四账户隔离、账务恒等式。

### Phase 1B：接入 prospective 108

这是 **T3 Paper 联动**，激活前必须 Owner 针对确切路径批准。

硬要求：

- 只有新的 `PROSPECTIVE_LIVE`、quality `ALLOW`、能力 `paper_plan_capability=ALLOW` job；
- 每个 job 有单独、hash-bound OwnerDecision；
- 108 事件不可直接绕过 ResearchJob/PaperPlan；
- 109 只回填研究标签；
- 调度器默认关闭，未批准时只生成 preview；
- 研究侧始终没有 exchange client。

## Phase 2：Binance 测试网

这是交易所下单路径，即使使用测试币也属于 **T3**。

建议在 AlphaHive 仓外建立独立、很小的 execution gateway，例如：

```text
AlphaHive_Execution_Gateway/
  contracts.py              # 接受签名/哈希绑定的 OrderIntent
  ledger.py                 # orders/fills/positions/checkpoints
  risk_gate.py              # fixed limits、REDUCE_ONLY、HALT
  binance_testnet.py        # 唯一交易所 adapter
  service.py                # consume → submit → reconcile
  tests/
```

AlphaHive 只输出不可变 envelope；网关返回 ExecutionReport，不反向读取研究分数。

测试网 adapter 必须具备：

- 锁定、记录确切 SDK/CCXT 版本和 Binance endpoint；
- 时间同步、`recvWindow`、rate limit；
- 确定性 client order ID；
- POST 超时后先查询再决定是否重试；
- user-data execution reports + REST 恢复；
- open orders、fills、position、balance 启动对账；
- one-way/hedge mode、margin type、leverage、symbol filters 明确校验；
- cancel、cancel-all、reduce-only；
- adapter 不可通过一个布尔 `sandbox=False` 自动切到 live。

A/B/C/D 不应直接共用一个测试网期货账户：同 symbol 仓位会净额合并。最务实的做法是：

- Phase 2 只指定一个账户，例如 B，走测试网；
- A/C/D 继续作为模拟对照；
- 若 Owner 要四账户实测，则需要四个隔离账户，或另做有完整 allocation ledger 的 omnibus 分摊；不建议第一版做后者。

## Phase 3：live

保持 `PARK`，不能因 Phase 2 跑了一段时间自动升级。

Owner 签批前至少要有：

- 测试网重启、断网、重复提交、部分成交、撤单、限频的故障测试；
- 连续运行期间零无法解释的 order/fill/position/balance divergence；
- kill switch 和 reduce-only 人工演练；
- 凭证不进仓库、不进日志；
- 独立审计；
- 明确的账户、symbol、名义金额、杠杆上限和 capability hash；
- testnet 与 live 使用不同凭证和不同进程，禁止仅改配置布尔值切换。

---

## 4. 文件级取舍

### 保留并扩展

- AlphaHive `paper_plan_engine.py`
- AlphaHive `offline_execution_simulator.py`
- AlphaHive现有 immutable local ledger 的写入、hash 和恢复思路
- `143_paper_trade.py` 的 A/B/C/D 报表语义
- botv2 的风险场景清单和 exchange filter/preflight 要求

### 只参考、重新实现

- `RiskManager`
- stale snapshot/spread guard
- `NORMAL / REDUCE_ONLY / HALT`
- client/exchange order ID
- live position normalization
- startup reconciliation

### 废弃为执行依赖

- botv2 `PaperTraderPro`
- botv2 `main.py`
- botv2 `config.py`
- `engines_v2.VolScaledKelly`
- `expert_mixer.py`
- botv2 的 paper JSON 账本
- 随机 UUID 重试方式
- maker GTC 无撤单路径
- 启动时重置风控状态

---

## 最终判断

| 选择 | Verdict |
|---|---|
| 整体复制 botv2 执行层 | **NO-GO** |
| 补齐缺失模块后直接 live | **NO-GO** |
| 把 botv2 当需求和故障案例库 | **GO** |
| 基于 AlphaHive 现有 PaperPlan/模拟器重写最小执行内核 | **推荐** |
| 108 直接触发订单 | **禁止** |
| 测试网/未来 live 独立网关 | **推荐，但 T3 PARK** |

诚实地说，botv2 真正有价值的是“它踩过哪些执行问题”，不是这 5330 行代码本身。缺失 adapter/OMS 使最关键部分无法审计；现存 live 路径又存在重置熔断、丢开放订单、无持续成交回报和无撤单闭环等硬伤。**另起一个小而可审计的执行网关，比修复并迁移这个 god class 更干净，也更符合 AlphaHive 的宪法边界。**

验证结果：botv2 文件语法编译通过、唯一 FactorGraph 测试通过；AlphaHive PaperPlan/模拟/ledger 相关 15 项测试通过。未修改两个项目的源文件，AlphaHive 原有未提交改动保持不变。
