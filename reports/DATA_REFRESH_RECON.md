# DATA_REFRESH_RECON

**状态：** `READ_ONLY / UNVERIFIED_FOR_EXTERNAL_REFRESH`  
**侦察时间：** 2026-07-14 10:19（Asia/Shanghai）  
**数据根目录：** `C:\Users\10639\Desktop\加密\coinglass_db`  
**红线：** 本报告只读本地脚本、文件元数据和 parquet 时间列；未执行 API 请求、未启动刷新、未改 DB、未读取或打印任何凭证值。

## 1. 本地数据现状

| 数据 | parquet 文件 | 可读时间范围（跨文件） | 最后数据时间 | 从最后数据到侦察日的缺口 |
|---|---:|---|---|---:|
| `raw_1h/oi_ohlc` | 123 | 2024-06-05 16:00Z → 2026-05-26 19:00Z | 2026-05-26 19:00Z | 约 49 天 |
| `raw_1h/funding_ohlc` | 123 | 2024-06-05 20:00Z → 2026-06-23 02:00Z | 2026-06-23 02:00Z | 约 21 天 |

所有 246 个 OI/funding parquet 在本次只读扫描中均可读取。`pull_summary.yaml` 记录的 OI 文件数为 124，与当前目录 glob 的 123 不一致；刷新前应由 Owner 决定是否核对这份旧 summary，不应据此假设有额外可用文件。

## 2. 拉取脚本与入库机制

### 2.1 `coinglass_db/scripts/pull_coinglass.py`

- 直接使用 CoinGlass 的 KeyStore proxy endpoint；认证头在脚本配置中，凭证值未读取。
- `DEFAULT_TASKS` 包含 `oi_ohlc` 和 `funding_ohlc`，也包含其它 6 类衍生数据；没有只刷新 OI/funding 的命令行筛选项。
- 单页 `LIMIT=1000`，以 `end_time` 向历史回分页，直到 `API_EARLIEST_TS=2024-06-05` 或返回不足一页；分页结果按时间去重后写 parquet。
- `checkpoint_1h.json` 按 `task|symbol` 记完成状态；已标记 `ok` 的任务会跳过。因此它不是安全的“自动增量尾部合并”路径，若要重拉已完成任务，必须先由 Owner 决定 checkpoint 策略。
- 写入采用 `to_parquet` 覆盖目标文件；脚本本身不是只读工具。

### 2.2 `coinglass_db/scripts/pull_coinglass_fast.py`

- 与上一脚本共用 `checkpoint_1h.json`、端点和全历史分页结构，仍包含 OI/funding 与其它任务。
- 分页间隔约 8 秒，符号间隔约 3 秒，429 退避 30 秒；脚本注释明确曾在接近 10 req/min 时触发 429。
- 同样按任务/符号写 parquet 覆盖，不能在没有 Owner 授权的情况下运行。

### 2.3 `G:\Quant test\alpha_hive\scripts\periodic_data_refresh.py`

- 这是另一个增量刷新编排器，按本地 parquet 的最后时间戳计算 gap，并将新数据合并后写回。
- `DATA_TYPES` 当前包含 `klines`、`funding_ohlc`、`liquidation`，**没有 `oi_ohlc`**；因此它不能按现状刷新本次 OI 缺口。
- 单次 `limit = min(720, gap_h + 10)`；对 1h 数据，720 是约 30 天的 bar 数，不是 720 天。OI 约 1160 小时缺口即使被加入配置，也不能靠一次 720-row 请求覆盖完整缺口，仍需分页/分段设计。
- 它依赖 `alpha_hive/scripts/keystore_client.py` 的 KeyStore proxy 和 API key；本次没有初始化 client，也没有调用刷新入口。

## 3. 增量刷新可行性判断

### OI：2026-05-26 → now

- 本地证据：123 个文件的最新 OI 数据停在 2026-05-26 19:00Z，缺口约 49 天。
- 现有全历史脚本理论上能通过分页回补，但默认还会处理其它任务，并受 checkpoint、代理、凭证和 429 退避影响；它不是本轮可直接授权运行的“只补 OI”命令。
- 现有增量编排器没有 OI 类型，不能声称 OI 增量刷新已具备。
- 720 限制：全历史脚本的物理历史下限是 2024-06-05；增量编排器的 720 是 row limit。是否会丢失更早历史、是否需要分段回补，需 Owner 在外部刷新设计中确认。
- **结论：** `UNVERIFIED / 可研究，不能执行`。

### Funding：2026-06-23 → now

- 本地证据：123 个文件的最新 funding 数据停在 2026-06-23 02:00Z，缺口约 21 天。
- 现有全历史脚本理论上能分页回补，但它仍受 checkpoint、代理、凭证和 429 限频影响，并会写覆盖 parquet。
- `periodic_data_refresh.py` 已声明 funding 类型，按 gap 计算 limit；但本次未验证 client 可用性，也未执行请求。无 `start_time` 的 funding API 语义仍需在授权后验证，不能把“有编排代码”当作“已可安全增量”。
- **结论：** `UNVERIFIED / 可研究，不能执行`。

## 4. 外部依赖与风险

| 项目 | 静态证据 | 当前结论 |
|---|---|---|
| API/代理 | `proxy.keystore.com.cn` / KeyStore client 代码 | 需要外部 proxy 可达；未测试网络 |
| 凭证 | 两套拉取脚本有认证 headers；client 有 API key 依赖 | 需要 Owner 提供/确认；本次未读取值 |
| 频率 | 约 10 req/min；429 后 30–65 秒退避 | 存在限频风险，刷新耗时不可从本地静态资料精确保证 |
| 历史窗口 | 全历史脚本到 2024-06-05 物理下限；增量器最多 720 rows/请求 | 需确认 720 天/720 rows 语义与分段策略 |
| checkpoint | `checkpoint_1h.json` 按 task/symbol 跳过 `ok` | 需先设计增量 checkpoint，不得直接重跑 |
| 写 DB | `to_parquet` / merge 后写回 | 违反本轮只读红线，必须 Owner 授权 |

## 5. Owner 决策项

1. 是否授权为 OI 单独补充增量任务，而不是运行包含 8 类任务的全历史脚本。
2. 是否确认代理、凭证、频率预算和可接受的 parquet 覆盖/合并策略。
3. 是否接受保留 2024-06-05 以后数据的窗口策略，以及 OI 约 49 天缺口的分段回补方案。
4. 在上述授权之前，实时扫描不能把 OI/funding 缺口伪装成近期可用证据；本轮只在历史回放上验证覆盖状态。

## 6. 明确未做事项

- 未运行 `pull_coinglass.py`、`pull_coinglass_fast.py`、`periodic_data_refresh.py`。
- 未调用任何 HTTP/API endpoint。
- 未改 `coinglass_db` 下任何文件，未改 checkpoint、lock、log 或 parquet。
- 未查看、复制或修改 API key、token、secret、代理配置值。
