# AlphaHive V3：D 测试设计审计与 wash_cvd 条件因子候选

> **状态：`UNVERIFIED / DESIGN_ONLY`**  
> 本报告只冻结研究设计，不批准 trigger、Paper、仓位或执行变更。未写文件、未修改仓库。  
> Dune CLI 当前返回 `401 invalid API Key`，因此未重新执行查询、未消耗 credits。

## 结论先行

1. **现有 205 结果不能作为证据使用。** 当前报告中的 `both−CEX_only = +2.52% CI[+0.74,+4.35]` 必须作废并重跑；它同时受到 symbol 混币、日内前视、稀疏日期滚动、买入侧漏算和非聚类 CI 的污染。
2. **主口径应是“地址验证后的多池/多 DEX 总量”，不是单一 Uniswap v3 WETH 池。** 单池只做稳健性复核。
3. **必须使用小时级完成 bar。** 日频数据只能使用事件日前一个完整 UTC 日；不能把事件所在完整日的 DEX 量赋给盘中事件。
4. **覆盖率闸按“可评估事件率”而非“CSV 中有行率”计算。** `<50%` 时只能描述 DEX-active 子集，不能外推整个 wash_cvd universe。
5. **季度预算建议：D 为一个主问题，DEX 方向与池分散度为两个预注册次假设。** 其余候选排队，不应同时开测。

---

# 任务 1：D 测试设计审计

## 1. 现有 205 的审计裁决

现有脚本与报告：

- [205_dex_volume_crosssection.py](G:/Quant%20test/AlphaHive_V3/scripts/205_dex_volume_crosssection.py)
- [dex_volume_crosssection.md](G:/Quant%20test/AlphaHive_V3/reports/dex_volume_crosssection.md)

当前结果：

| 格 | 24h 均值 | n |
|---|---:|---:|
| CEX 放量 + DEX 放量 | +2.53% | 166 |
| CEX 放量 + DEX 常态 | +0.01% | 128 |
| CEX 常态 + DEX 放量 | +1.44% | 45 |
| 双常态 | -0.26% | 170 |

这张表目前应标记为 **`INVALIDATED_BY_DESIGN_AUDIT`**，原因如下。

### 致命问题

1. **symbol 不是资产身份。**

   SQL 用 `token_bought_symbol` 匹配 `PEPE/PUMP/ONDO/...`，没有 chain + contract address。缓存中已经出现明显异常：

   - `PEPE` 从 2021-12-27 开始；
   - `ONDO` 从 2022-04-29 开始；
   - `PUMP` 从 2021-12-01 开始；
   - `SUI/TIA` 也出现与目标资产历史不相容的早期记录。

   这证明同名 token 已经混入。PEPE 这类多地址资产尤其不能按 symbol 聚合。

2. **完整事件日量造成日内前视。**

   事件若发生在 UTC 03:00，当前脚本使用当天 00:00–24:00 的全部 DEX 量，其中约 21 小时发生在事件后。它不是“事件时点过去 24h 量”。

3. **30 日中位数不是 30 个日历日。**

   CSV 只保留有交易的日期，pivot 后未补完整日历零值；因此 `rolling(30)` 实际是“最近 30 个活跃交易日”，可能跨越几个月。

4. **只统计 token bought 侧。**

   token 作为卖出资产的成交完全漏掉。DEX gross turnover 必须同时计入 bought leg 和 sold leg。

5. **“全 DEX 聚合”描述不实。**

   查询限定 `blockchain='ethereum'`，却把结果描述为全 DEX；SUI、TRX、Solana 原生资产等并不属于这个覆盖域。

6. **暖机与 121 不一致。**

   121 使用：

   ```text
   qv24 = hourly_quote_volume.rolling(24).sum()
   med30 = qv24.rolling(720, min_periods=360).median()
   ```

   205 使用日频 `rolling(30,min_periods=15)`，并非严格镜像。

7. **CI 偏窄。**

   同一 6h 时点可能有多币同时出现 wash_cvd；当前 bootstrap 按事件独立抽样，没有按事件时点聚类。

8. **覆盖率混合了三件不同的事。**

   “无地址映射”“没有历史”“真实零成交”被混在一起，38% 不能解释为单纯的 DEX 流动性覆盖率。

此外，Dune 官方说明 `dex.trades` 记录的是每个流动性池路由段；聚合器的一次用户交易可能对应多条池级记录。因此 `sum(amount_usd)` 是**池路由成交量**，不是唯一用户意图成交额。这与本测试的“AMM 流动性使用强度”机制相符，但必须在报告中明确。[Dune `dex.trades` 文档](https://docs.dune.com/data-catalog/curated/dex-trades/evm/dex-trades)

---

## 2. 聚合口径定稿

### 主口径：地址验证、多池、多 DEX、EVM 分析域

主分析采用：

```text
asset_id
= CEX base asset
  × verified blockchain
  × verified token contract address
  × contract valid_from / valid_to
```

对每个已验证资产：

- 同时统计 token bought 和 token sold 两侧；
- 聚合所有 DEX project、version、pool；
- 每条池路由段的 `amount_usd` 计入该 token 的 gross pool turnover；
- 只合并明确属于同一经济资产的 canonical deployment；
- bridged/wrapped token 默认不合并，除非逐地址批准；
- 合约迁移按 `valid_from/valid_to` 切开；
- symbol 仅用于展示，绝不用于 join。

`dex.trades` 当前官方 schema 包含 bought/sold symbol、address、`amount_usd`、pool/router contract、project、tx hash 等字段，且推荐按 `blockchain` 和 `block_month` 分区过滤。[表结构](https://docs.dune.com/data-catalog/curated/dex-trades/evm/dex-trades)、[性能建议](https://docs.dune.com/data-catalog/curated/dex-trades/overview)

### 单 Uniswap v3 WETH 池：只做稳健性

单池口径有以下问题，不能做主结果：

- 主池会迁移；
- WETH 不一定是主要报价资产；
- 交易可转移到 USDC、其他 fee tier、L2 或其他 DEX；
- 事后选择“最大池”会引入幸存者偏差；
- 山寨币经常没有 Ethereum v3 WETH 主池。

但它适合验证：

- 多池结果是否被路由拆分放大；
- 单一异常池是否主导 gross volume；
- pool HHI 高时，结果是否不稳。

### 非 EVM 资产

官方当前将 EVM `dex.trades` 与 Solana DEX 数据分开；Solana curated 数据通常有约 6–7 小时更新间隔，不应与 EVM 小时数据直接混池。[Dune 数据新鲜度](https://docs.dune.com/data-catalog/data-freshness)

本轮建议：

- **主研究域：地址已验证的 EVM 子集；**
- Solana/SUI/TRX 等各自作为独立 adapter 和独立稳健性表；
- 不因 base symbol 相同就合并跨链 volume；
- 结论写成“EVM DEX-active wash_cvd 子集”，不得写成“全部山寨币”。

---

## 3. 冻结后的特征定义

### 时间语义

设 wash_cvd 事件所在 CEX 小时 bar 为 `[t,t+1h)`：

```text
decision_time = t + 1h
dex_cutoff    = decision_time - 2h
```

主特征只使用 `block_time < dex_cutoff` 的 DEX trades。

采用 2h operational lag 是为了模拟 Dune curated 表的更新延迟；执行前必须做 freshness 探针：

```text
freshness_lag = query_started_at - max(block_time)
```

若近 30 次探针的 p95 freshness > 2h：

- 将 `L` 上调至下一整数小时；
- 用新 L 重算全部历史；
- 不允许历史用 L=0、前向却用滞后数据。

### 小时级 DEX 量

```text
dex_vol_1h[a,h]
  = sum(amount_usd)
    for verified token legs of asset a
    during completed hour h

dex_vol_24h[a,t]
  = sum of latest 24 completed dex_vol_1h values

dex_med30[a,t]
  = median of the latest 720 hourly dex_vol_24h observations
    with min_periods = 360

dex24_ratio[a,t]
  = dex_vol_24h / dex_med30
```

与 121 一致：

```text
DEX_HIGH = dex24_ratio > 1.5
CEX_HIGH = qv24_ratio  > 1.5
```

### 零与缺失

- 地址已验证、数据管线健康、token 已进入有效期后的无成交小时：填 `0`；
- 映射缺失、合约有效期外、Dune 分区缺失、freshness 不合格：`NA`；
- `dex_med30=0`：标记 `STRUCTURALLY_INACTIVE`，ratio 不定义；
- 不得把 `NA` 当作 DEX 常态；
- 不得只保留有成交的小时或日期再 rolling。

### 日频降级口径

只有无法取得小时级数据时才使用：

```text
feature_date = UTC date immediately preceding the event date
ratio = prior completed UTC-day volume
        / median(previous 30 completed UTC-day volumes)
```

事件当天完整日量严禁使用。

---

## 4. 推荐 DuneSQL 骨架

以下 SQL 在填入经过人工验证的地址表后可直接执行。地址必须使用 varbinary literal，不是字符串。

```sql
WITH asset_map (
    blockchain,
    token_address,
    asset_id,
    valid_from,
    valid_to
) AS (
    VALUES
        -- 示例格式，禁止把示例地址当真实映射
        -- ('ethereum', 0x..., 'PEPE', TIMESTAMP '2023-01-01', TIMESTAMP '2099-01-01')
),
base AS (
    SELECT
        t.blockchain,
        t.block_time,
        t.block_month,
        t.project,
        t.project_contract_address,
        t.tx_hash,
        t.evt_index,
        t.amount_usd,
        t.token_bought_address,
        t.token_sold_address
    FROM dex.trades t
    WHERE t.blockchain IN (
        SELECT DISTINCT blockchain FROM asset_map
    )
      AND t.block_month >= DATE '2021-11-01'
      AND t.block_month <  DATE '2026-07-01'
      AND t.block_time >= TIMESTAMP '2021-11-01 00:00:00'
      AND t.block_time <  TIMESTAMP '2026-07-01 00:00:00'
      AND t.amount_usd IS NOT NULL
      AND t.amount_usd > 0
),
legs AS (
    SELECT
        b.*,
        u.side,
        u.token_address
    FROM base b
    CROSS JOIN UNNEST(
        ARRAY[
            CAST(ROW('buy',  b.token_bought_address) AS ROW(side VARCHAR, token_address VARBINARY)),
            CAST(ROW('sell', b.token_sold_address)   AS ROW(side VARCHAR, token_address VARBINARY))
        ]
    ) AS u(side, token_address)
),
mapped AS (
    SELECT
        l.*,
        m.asset_id
    FROM legs l
    JOIN asset_map m
      ON l.blockchain = m.blockchain
     AND l.token_address = m.token_address
     AND l.block_time >= m.valid_from
     AND l.block_time <  m.valid_to
)
SELECT
    date_trunc('hour', block_time) AS hour,
    blockchain,
    asset_id,
    side,
    sum(amount_usd) AS volume_usd,
    approx_distinct(tx_hash) AS tx_count,
    approx_distinct(project) AS project_count,
    approx_distinct(project_contract_address) AS pool_or_router_count
FROM mapped
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2, 3, 4;
```

执行前 Gate 0 必须确认实际 schema；Dune CLI 当前 401，因此本轮不能确认 UNNEST row 语法在账户所用引擎版本上的行为。若失败，改为 bought/sold 两个 `UNION ALL` 分支，不改变统计语义。

---

## 5. 覆盖率处理定稿

必须同时报告四类覆盖：

| 指标 | 定义 |
|---|---|
| identity coverage | wash_cvd 事件中，存在有效 chain+address 映射的比例 |
| history coverage | identity-covered 中，有至少 360 个有效小时暖机的比例 |
| evaluable coverage | identity、暖机、freshness、`med30>0` 全通过的比例 |
| active coverage | evaluable 中，过去 24h DEX volume > 0 的比例 |

### 覆盖闸

- `evaluable coverage ≥ 50%`：允许做主矩阵，但结论仍限定在映射覆盖域；
- `30%–50%`：只做 `exploratory / DEX-active subset`，不能升级为 wash_cvd 全域门控；
- `<30%`：停止收益判定，只交付身份与流动性覆盖报告；
- 任一关键格预算不足：四格可展示，但不得解释交互作用。

必须额外比较 covered 与 uncovered 事件的：

- CEX turnover；
- listing age；
- market-cap/liquidity rank；
- washout 深度；
- 24h 原始收益。

若 covered 组本身明显偏向大币或高流动性币，DEX 分层很可能只是 universe selection。

---

## 6. 2×2 矩阵与统计判定

只在 `evaluable=true` 的事件上构造：

| 格 | CEX | DEX | 含义 |
|---|---|---|---|
| `00` | 常态 | 常态 | 无集中放量 |
| `10` | 放量 | 常态 | CEX-only |
| `01` | 常态 | 放量 | DEX-only |
| `11` | 放量 | 放量 | 双市场放量 |

### 主假设：DEX 对 121 的增量

```text
ΔDEX|CEX-high = mean(ret24_11) - mean(ret24_10)
```

这是唯一主检验。

### 次假设

```text
ΔDEX|CEX-normal = mean(ret24_01) - mean(ret24_00)

Interaction
= (mean_11 - mean_10) - (mean_01 - mean_00)
```

解释：

- `11 > 10` 且 CI 排除 0：DEX 在 CEX 放量条件下有增量；
- 两个 DEX 增量均相近、interaction≈0：DEX 是稳定的加性条件；
- 只有 interaction 为正：双市场同步可能存在协同；
- `11≈10` 且 DEX/CEX 标记高度重叠：DEX 很可能只是 121 的同族代理；
- `01/11` 均无改善：关闭 DEX volume 因子；
- 不允许仅因 `11` 的绝对收益为正就宣称增量。

每格同时报告：

```text
n_events
n_unique_6h_clusters
n_assets
n_event_days
mean / median / win rate
24h matched excess
72h / 168h secondary returns
```

### 基线

- 绝对收益：复用 121 的同期随机 symbol×time baseline；
- 增量主检验：wash_cvd 事件内直接比较；
- 再做 episode × CEX-liquidity tercile 标准化；
- 稳健性采用只保留“同一 asset 曾出现两种 DEX 状态”的 within-asset 样本。

### 聚类与功效

主 CI：

- 以 6h event-time cluster 为 bootstrap 单位；
- 同一 cluster 内所有 symbol 一起重采样；
- 次要稳健性使用 timestamp + symbol 双向聚类；
- 市场级状态不得按 1,348 条币事件假装有 1,348 个独立观测。

预算规则：

| 状态 | 要求 |
|---|---|
| 仅展示 | 每格 `n≥30` 且 unique 6h clusters `≥20` |
| 主增量可判 | `11`、`10` 各 `n≥60`，各 unique clusters `≥40`，合计资产 `≥8` |
| interaction 可判 | 四格各 `n≥50`、unique clusters `≥30` |
| 跨期稳定 | 至少两个 episode 同号；任一 episode 不得占加权样本 >60% |

新因子仍须满足项目门槛：

```text
cluster t-stat ≥ 3.0
24h marginal effect > 0
cluster CI excludes 0
```

运行前用盲化 outcome 估计 cluster variance：

```text
MDE80 = (3.0 + 0.84) × SE_cluster
```

例如总样本 1,348、可评估覆盖仅 50%、四格近似均衡时，每格约 169；若 24h 收益标准差约 10%，即使忽略聚类，两格差异的 MDE 也约为 4.2pp，interaction 约 5.9pp。实际聚类后更差。因此 38% 覆盖下声称精细协同，很可能功效不足。

### 多重检验

- 主检验只有 `ΔDEX|CEX-high @24h`；
- `ΔDEX|CEX-normal` 与 interaction 为两个预注册次假设；
- 72h、168h、阈值 1.2/2.0、单池结果均为稳健性；
- 三个正式假设使用 Holm 校正；
- 不得从 24/72/168h、多个阈值中事后挑最好值。

---

## 7. Credits 与数据滞后纪律

Dune credits 按实际计算资源消耗，不存在可提前精确计算的固定费率；复杂度、扫描范围和引擎都会影响成本。[Dune credits 说明](https://docs.dune.com/resources/credits-billing/how-credits-work)

冻结预算：

1. schema/最近 7 日探针：上限 10 credits；
2. 3 个资产 × 90 日 pilot：累计上限 25；
3. 执行前读取 `dune usage`，记录 before；
4. 根据 pilot 外推全量成本；
5. D 主查询上限 250 credits；
6. 允许一次修复性重跑，上限 50；
7. D 因子族总预算上限 300/2500；
8. 任何 query timeout 或预计超限：停止，不自动切大引擎。

降本方式：

- 必须过滤 `blockchain`、`block_month` 和精确 `block_time`；
- 只拉聚合后小时数据，不下载原始 trades；
- 一次拉取研究窗加 31 日暖机，不按每个事件重复查询；
- 地址映射先在本地审完，再上全量；
- 保存 SQL、执行 ID、query time、max block time、credits before/after；
- 锁定 Spellbook 查询日期/commit provenance，因为 curated 表可能回填或修订。

---

## 8. D 测试最终决策树

```text
地址映射未完成
  → PARK，不按 symbol 查询

可评估覆盖 <30%
  → 只做覆盖报告

30%–50%
  → 描述 DEX-active subset，不做全域结论

≥50% 但主比较两格预算不足
  → UNDERPOWERED，不判增量

预算充足但 Δ11−10 CI 含 0 或 t<3
  → NO_GO；非显著不等于严格证伪

Δ11−10 >0、cluster CI排除0、t≥3、跨episode同号
  → historical candidate

再通过地址/单池/滞后/阈值稳健性
  → 进入独立前向 shadow 资格审查

任何结果
  → 不自动接 108、不改 Paper、不改仓位
```

---

# 任务 2：wash_cvd 条件空间内的潜在因子

## 统一检验骨架

所有候选都遵守：

- 母事件固定为 115 的 wash_cvd，72h 冷却；
- 不重新做全市场裸因子；
- 主 outcome 为入场后 24h；72h/168h 为次要；
- token 级因子按 6h event-time cluster；
- 日度市场因子按 unique event day 等权，不能按币事件数量加权；
- 历史因子每组原则上 `n≥60`、unique clusters `≥40`；
- 市场日度因子至少 60 个独立事件日；
- 前向因子 30 事件预警，60–100 事件正式判定；
- 主增量需 cluster `t≥3`、CI 排除 0、至少两段同号；
- marginal effect 低于 0.75pp，即使显著也不优先升级；
- 不通过但功效不足写 `NO_GO/UNDERPOWERED`，不得冒充“已证伪”。

## 候选 1：DEX gross turnover × CEX 放量

**优先级：P0，季度主问题**

- **机制与寿命**：E-A 机制/结构摩擦；DEX 与 CEX 同时放量可能表示冲击被跨市场真实承接，而不是单一合约市场的机械换手。AMM 与 CEX 的市场分割长期存在，寿命中长。
- **数据**：地址验证后的 `dex.trades` 小时 gross turnover；121 CEX `qv24_ratio`。
- **设计**：使用任务 1 的四格矩阵；主检验 `11−10 @24h`。
- **样本/基线**：evaluable coverage≥50%；主两格各≥60；同期随机基线 + wash_cvd 内直接增量。
- **失败判据**：覆盖不足；`11−10` CI 含 0；t<3；effect<0.75pp；跨 episode 反号；加入 DEX 后只是复现 CEX volume 且重叠率>80%。

## 候选 2：DEX 净买入吸收率

**优先级：P0，D 的次假设 1**

```text
dex_buy_share_6h
= (token_bought_usd - token_sold_usd)
  / (token_bought_usd + token_sold_usd)
```

- **机制与寿命**：E-A/E-C；wash_cvd 是 CEX 卖压枯竭事件，若链上同时出现目标 token 净买入，说明另一市场正在吸收库存。跨市场信息传播会被套利压缩，寿命短中期。
- **数据**：与 D gross query 同源，只需保留 `side`；不增加新的重表扫描。
- **设计**：在 wash_cvd 且 DEX evaluable 样本中，以过去 90 日自身分布预先确定 tercile；检验 high−low。再在 CEX_HIGH 内复测，确认不是 gross volume 的代理。
- **样本/基线**：top/bottom 各≥60、unique clusters≥40；按 asset×episode 标准化。
- **失败判据**：无单调；high−low CI 含 0；控制 DEX gross ratio 后消失；不同 episode 反号；bought/sold 方向受路由段定义影响而无法稳定复现。

## 候选 3：DEX 放量质量——池分散度/HHI

**优先级：P0，D 的次假设 2**

```text
pool_hhi_24h = Σ(pool_volume_share²)
effective_pool_count = 1 / pool_hhi_24h
```

- **机制与寿命**：E-A；多池、多协议一致放量更可能是真实广泛承接，单池集中尖峰更可能是路由、激励、MEV 或局部操纵。AMM 流动性碎片化长期存在，寿命中等。
- **数据**：`project + project_contract_address + amount_usd`，与 D 主查询同 credits 家族。
- **设计**：仅在 `DEX_HIGH` 样本中比较低 HHI 与高 HHI；在 `dex24_ratio` 相近区间内匹配，防止 HHI 只是总量代理；单 v3 主池结果作为旁证。
- **样本/基线**：两层各≥50、有效 pool≥2 的资产至少 8 个。
- **失败判据**：控制总量后差异消失；pool/router 地址不能可靠区分；单池与多池结果方向冲突；结果由一个 project 或一个 token 主导。

## 候选 4：短强平脉冲的新近度/持续性

```text
short_liq_frontload
= short_liq_usd(last 3h) / short_liq_usd(last 24h)
```

- **机制与寿命**：E-A；131 已证明 short-liquidation intensity 有效，但同样的 24h 总量可能是“刚开始”或“已经结束”。新近度衡量挤压燃料是否仍在释放，不复活 funding，也不重测双清算。
- **数据**：Coinalyze/Coinglass 小时 short liquidation；事件时点 asof。
- **设计**：只在 `short_liq_z>1` 的 wash_cvd 子集中，把 frontload 按预事件历史分成高/低；比较 24h 收益，并在相同 total short-liq z 档内匹配。
- **样本/基线**：高低各≥60；2024 与 2025+ 两段同号。
- **失败判据**：控制总 short-liq 后无增量；frontload 与事件 bar 收益机械同义；CI 含 0；任一段方向反转。
- **边界**：不引入 Aave 清算、不重提双清算共振。

## 候选 5：卖压衰减斜率，而非 CVD 极值

```text
cvd_exhaustion_slope
= mean(ΔCVD last 3h) - mean(ΔCVD preceding 21h)
```

取自身 30 日尺度标准化。

- **机制与寿命**：E-A；wash_cvd 已要求 CVD 背离，新增量不是“更极端”，而是卖压速度是否正在衰减。被动承接与强制卖盘结束属于市场微结构，寿命中等。
- **数据**：现有 taker buy/sell、CVD、klines；不需要 funding/OI。
- **设计**：wash_cvd 内按 slope tercile；主对比“明显衰减”−“继续恶化”。再与已验证 4h confirmation 做增量表：该因子必须在不使用事件后 4h 信息时仍有价值。
- **样本/基线**：top/bottom 各≥100 较合适；全历史及下架池各复核一次。
- **失败判据**：无单调；只是 cvd_divergence 水平的重包装；加入 washout 深度和 CEX qv 分层后消失；不能在下架池复现；低于 4h confirmation 且无更早可用性优势。

## 候选 6：P2P 场外溢价加速度

```text
p2p_premium_state
= premium_t - median(premium, previous 7d)

p2p_premium_accel
= premium_t - premium_t-24h
```

- **机制与寿命**：E-D 结构性供需；法币入口溢价上升代表边际现货需求或资金通道紧张。P2P 市场分割、资本管制和支付摩擦不会很快消失，寿命较长，但平台参与者结构会漂移。
- **数据**：现有 `data/otc_premium.csv`/前向采集；只允许使用事件决策时点之前已抓到的快照。
- **设计**：这是**纯前向因子**，不得事后补造历史。比较 premium acceleration 高/低 wash_cvd；按地区、USDT 报价方向固定一个主市场，其余仅稳健性。
- **样本/基线**：快照覆盖≥80%；30 事件预警、100 事件正式；按事件日聚类。
- **失败判据**：100 事件后 high−low CI 含 0；报价缺货/广告商变化主导；抓取时间不稳定；地区切换后方向反转；边际效果不超过已有 CEX volume/4h confirmation。
- **优势**：真正 OOS，不受现有 1,348 条历史样本反复切片影响。

## 候选 7：注意力—情绪背离

```text
attention_resid
= GoogleTrends_z
  - z(abs(BTC 24h return))

factor
= high attention_resid AND prior-day F&G >= 60
```

- **机制与寿命**：E-B 情绪/行为偏差；Google 搜索显著超过价格冲击本身，且情绪仍偏积极，可能代表“关注增加但未全面恐慌”的承接环境。人类注意力偏差持续存在，但查询平台与用户结构会漂移，寿命中等。
- **数据**：Google Trends、Fear & Greed、BTC klines；全部使用事件日前一个已完成日。
- **设计**：比较组合状态与单独 F&G≥60；主问题是 attention 是否对已知 F&G 调制提供 marginal，而不是重新证明 F&G。
- **样本/基线**：以 unique event day 等权；≥60 个独立事件日；Google overlapping-window 必须固定归一和 stitch 方法。
- **失败判据**：组合不优于 F&G-only；Google term 改动才显著；结果被少数崩盘日主导；按 event day 聚类后 CI 含 0；Holm 后不通过。
- **身份纪律**：不按 `PEPE/PUMP` 等歧义 ticker 直接搜；主口径使用市场级主题词或锁定的 Google Topic ID。

## 候选 8：加密本地冲击 vs 全球风险冲击

```text
local_shock_score
= z(alt cross-sectional realized volatility / breadth stress)
  - z(VIX prior close)
```

- **机制与寿命**：E-A/E-C；同样的 wash_cvd，若主要是加密内部清杠杆，卖压结束后可能更容易反弹；若与全球风险压力同步，现金需求可能持续。跨市场风险传导长期存在，但领先关系会被套利，寿命短中期。
- **数据**：alt klines/breadth、BTC realized vol、VIX、宏观日历。
- **设计**：按 score 预先分 tercile；比较 crypto-local 与 global-risk。随后在固定 VIX 档内比较，要求对现有 VIX 门控有增量。
- **样本/基线**：unique event day≥60；按日等权和 episode 分层。
- **失败判据**：控制 VIX 后消失；与既有 breadth 条件高度重叠；不同波动估计窗口才出现结果；跨 episode 反号；日聚类 CI 含 0。

---

# 检验预算与执行顺序

为遵守“季度 1 主问题 + 2 个预注册次假设”，本轮只应激活：

1. **主问题 D1：DEX gross × CEX 2×2**
2. **次假设 D2：DEX 净买入吸收率**
3. **次假设 D3：DEX pool HHI/分散度**

其余候选进入后续队列：

4. CEX short-liq 脉冲新近度  
5. CVD 卖压衰减斜率  
6. P2P 溢价加速度，优先前向积累  
7. 注意力—情绪背离  
8. 本地/全球冲击分解

不应加入候选池的方向：

- funding 家族；
- 稳定币、ETF、交易所净流入再切片；
- Aave 清算负调制复测；
- 双清算共振；
- 单特征极值扫描；
- meta-labeling；
- 钱包身份/聪明钱标签；
- -10% 止损优化。

## 最终验收口径

D 因子只有同时满足以下条件，才可从设计进入 historical candidate：

```text
地址级身份通过
+ 无日内前视
+ 完整小时轴
+ evaluable coverage ≥50%
+ 主两格样本预算通过
+ 6h cluster CI 排除0
+ t-stat ≥3
+ Δ11−10 ≥0.75pp
+ 至少两个 episode 同号
+ 单池/滞后/地址稳健性不推翻
```

即使全部通过，也仍是历史候选；前向 shadow 与任何 trigger/Paper 变化需要独立流程和 Owner 决策。
