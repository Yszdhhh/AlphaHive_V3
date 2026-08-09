针对加密货币量化研究系统 **AlphaHive V3**（Python/pandas/Windows单机）的现存痛点，为您量身定制一套**高鲁棒、低耦合、轻量级**的数据工程与可视化重构方案。

---

### 一、推荐库版本 (Recommended Tech Stack)

建议在 `requirements.txt` 或 `pyproject.toml` 中固定以下依赖版本（兼容 Python 3.11+ / Windows）：

```toml
[dependencies]
python = ">=3.11,<3.13"
pandas = "^2.2.1"
polars = "^0.20.15"
duckdb = "^1.0.0"
pydantic = "^2.7.0"
pydantic-settings = "^2.2.1"
pyarrow = "^16.0.0"
plotly = "^5.20.0"
streamlit = "^1.34.0"
openbb = {version = "^4.1.4", optional = true}  # 可选
```

---

### A. 多源小时级 Klines 深度清洗与数据质量监控最佳实践

#### 1. 清洗 Pipeline 标准工作流 (5步金字塔)
```
[ Raw Ingestion ] ➔ [ 1. Deduplicate & Time Alignment ] ➔ [ 2. Hard & Soft Outlier Rules ]
                  ➔ [ 3. Gap Strategy & Zero-Fill ] ➔ [ 4. Cross-Source Reconciliation ] ➔ [ Clean Parquet + Quality Log ]
```

#### 2. 关键清洗逻辑与 Kill Rules 规则定义

##### ① 时间网格强制对齐 (Hourly Dense Grid Alignment)
*   **规则**：所有数据源强制向上/向下截断至 UTC 整点时间戳 `YYYY-MM-DD HH:00:00`。
*   **去重**：若同一时间戳有多条记录，按数据源优先级 (Binance > Coinalyze > CoinGlass) 或取最新的 `ingested_at` 时间戳。

##### ② 离群值/假 Bar 识别算法 (Kill Rules)
*   **物理常识硬校验 (Hard Rules)**：
    $$\text{Invalid Bar} \iff (High < Low) \lor (High < Open) \lor (High < Close) \lor (Low > Open) \lor (Low > Close) \lor (Volume < 0)$$
*   **中位数偏离校验 (Soft Rules - 解决 CoinGlass 50x 脏值)**：
    使用 30 天（720小时）滚动中位数及中位数绝对偏差（MAD, Median Absolute Deviation）：
    $$\text{Ratio} = \frac{P_{close}}{\text{RollingMedian}_{720h}(P_{close})}$$
    当 $\text{Ratio} > 5.0$ 或 $\text{Ratio} < 0.2$（或用户要求的 50x 阈值，建议线上设为 5x 预警、10x 剔除）时，判定为假 Bar，触发剔除并补缺。
*   **Volume > 0 截断**：对于 Klines，若连续 3 小时 $Volume = 0$，标记 `suspicious_liquidity` 预警；若为衍生品（如成交量极大的主流币），直接判定为网络中断造成的伪造 Bar。

##### ③ 断点与 Gap 填充策略 (Gap & Sparse Filling Strategy)
*   **价格类字段（Price/OI/Funding Rate）**：采用 **Forward Fill (FFill)**，最大允许连续填充长度 `max_gap = 3` 小时。若超出 3 小时，不继续盲目 FFill，而是标记 `is_datacut = True` 并告警。
*   **事件类/稀疏字段（Coinalyze 清算）**：与完整的时间序列进行 `Left Join / Reindex`，缺失值一律做 **Zero Fill (`fillna(0.0)`)**。
*   **衍生标记字段**：所有经过插值填充的 Bar，新增 `quality_flag` 位掩码（0: Raw, 1: Interpolated, 2: Outlier_Cleaned, 4: Zero_Filled）。

##### ④ 跨源一致性对账 (Cross-Source Reconciliation)
*   计算 **Binance Futures vs Pyth / CoinGlass 近邻差价率**：
    $$\Delta_{spread} = \frac{|P_{\text{Binance}} - P_{\text{Coinalyze}}|}{P_{\text{Binance}}}$$
    若 $\Delta_{spread} > 1.5\%$ 且持续超过 2 个 Bar，触发数据源异动告警（可能是单个交易所插针或 API 异常）。

#### 3. 深度清洗与监控 Core 代码实现 (Python / Pandas / Polars)

```python
import pandas as pd
import numpy as np

def clean_hourly_klines(
    df_raw: pd.DataFrame, 
    source_name: str,
    max_ffill_hours: int = 3
) -> pd.DataFrame:
    """
    小时级 Klines 深度清洗 Pipeline
    """
    df = df_raw.copy()
    
    # 1. 时间轴强制规范化与去重 (UTC)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.floor('h')
    df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp'], keep='last')
    
    # 2. 建立完整连续的时间网格 (Dense Reindex)
    start_time = df['timestamp'].min()
    end_time = df['timestamp'].max()
    full_grid = pd.date_range(start=start_time, end=end_time, freq='1h', tz='UTC', name='timestamp')
    
    df = df.set_index('timestamp').reindex(full_grid).reset_index()
    
    # 3. 初始质量标记 (位掩码)
    # 0: OK, 1: Gap_Interpolated, 2: Outlier_Removed, 4: Zero_Filled
    df['quality_flag'] = 0
    
    # 4. 稀疏数据/事件型数据零填充（针对清算/Taker Volume）
    sparse_cols = [c for c in ['liquidations_long', 'liquidations_short', 'taker_buy_vol'] if c in df.columns]
    for col in sparse_cols:
        zero_filled_mask = df[col].isna()
        df[col] = df[col].fillna(0.0)
        df.loc[zero_filled_mask, 'quality_flag'] |= 4

    # 5. 硬物理逻辑校验 (Hard Rules)
    hard_invalid = (
        (df['high'] < df['low']) | 
        (df['high'] < df['open']) | 
        (df['high'] < df['close']) | 
        (df['low'] > df['open']) | 
        (df['low'] > df['close']) |
        (df['volume'] < 0)
    )
    # 将硬违例价格置 NaN
    price_cols = ['open', 'high', 'low', 'close']
    df.loc[hard_invalid, price_cols] = np.nan
    df.loc[hard_invalid, 'quality_flag'] |= 2

    # 6. 软规则：30天 (720h) 滚动中位数偏离去脏 (解决 CoinGlass 50x 脏值)
    rolling_median = df['close'].rolling(window=720, min_periods=24).median()
    ratio = df['close'] / rolling_median
    outlier_mask = (ratio > 5.0) | (ratio < 0.2)  # 偏离超过5倍即判定异常
    
    df.loc[outlier_mask, price_cols] = np.nan
    df.loc[outlier_mask, 'quality_flag'] |= 2

    # 7. 价格字段 Gap 处理 (前向填充 + 限制最大步长)
    gap_mask = df['close'].isna()
    for col in price_cols:
        df[col] = df[col].ffill(limit=max_ffill_hours)
    
    # volume / OI 处理
    if 'volume' in df.columns:
        df['volume'] = df['volume'].fillna(0.0)
    if 'open_interest' in df.columns:
        df['open_interest'] = df['open_interest'].ffill(limit=max_ffill_hours)

    # 对被前向填充的行标记 flag
    interpolated_mask = gap_mask & df['close'].notna()
    df.loc[interpolated_mask, 'quality_flag'] |= 1
    
    # 超过 limit 依然 NaN 的标记为未修补断点
    df['is_unresolved_gap'] = df['close'].isna()

    return df

# 新鲜度告警检测函数 (SLA Monitoring)
def check_data_freshness(df: pd.DataFrame, max_delay_minutes: int = 70) -> dict:
    latest_ts = df['timestamp'].max()
    now_utc = pd.Timestamp.now(tz='UTC')
    delay = (now_utc - latest_ts).total_seconds() / 60.0
    
    is_fresh = delay <= max_delay_minutes
    return {
        "is_fresh": is_fresh,
        "latest_timestamp": str(latest_ts),
        "delay_minutes": round(delay, 2),
        "alert_level": "CRITICAL" if not is_fresh else "INFO"
    }
```

---

### B. 单机 Python 研究环境的数据整合架构

针对 **绝对路径硬编码** 及 **Emoji 路径漂移** 的痛点，架构重构核心原则是：**配置统一化 + 路径强类型化 + 数据访问层抽象 + DuckDB/Parquet 本地引擎**。

#### 1. 解决方案：路径管理与环境配置 (`pathlib` + `pydantic-settings`)
告警：绝对字符串拼接（尤其是包含 `D:\🚀Strategy\...` 等带有 Emoji 或空格的路径）在 Windows 编码 (GBK/UTF-8) 切换时必定发生 `FileNotFoundError`。

*   统一使用 Python 3.4+ 标准库 `pathlib.Path`，避免使用字符串 `+` 或 `os.path`。
*   使用 `pydantic-settings` 统一读取 `config.env` 文件。

```python
# config.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 根路径自动解析为当前配置文件所在的上一级或固定工作区
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    
    # 分层存储路径
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
    MARKET_PARQUET_DIR: Path = PROCESSED_DATA_DIR / "market_klines"
    
    # 数据库路径
    DUCKDB_PATH: Path = DATA_DIR / "alphahive.duckdb"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# 初始化配置对象（确保所有路径在系统启动时自动创建）
settings = Settings()
for path_item in [settings.RAW_DATA_DIR, settings.PROCESSED_DATA_DIR, settings.MARKET_PARQUET_DIR]:
    path_item.mkdir(parents=True, exist_ok=True)
```

#### 2. 轻量级存储与计算方案对比

| 维度 | DuckDB | Polars | Pandas | SQLite | Native Parquet |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **定位** | 单机 OLAP 嵌入式 SQL 引擎 | 高性能内存数据框 | 传统内存数据框 | 事务型 OLTP 数据库 | 文件列式存储格式 |
| **大规模 SQL 查询** | **极快 (向量化)** | 不支持/较弱 | 无 | 慢 (无列存) | N/A (需结合引擎) |
| **跨文件 Aggregation** | **原生支持 (直接查 *.parquet)** | 支持 | 依赖循环拼接 | 性能差 | N/A |
| **Schema 强约束** | **高 (SQL 表定义)** | 中 (DataFrame Schema) | 无 (弱类型) | 中 | 高 (PyArrow Schema) |
| **单机内存占用** | **极低 (Out-of-Core 内存映射)** | 低 | 极高 (3~5x 副本) | 较低 | 极低 |
| **AlphaHive 推荐度** | **首选 (数据仓/查询层)** | **首选 (ETL/清洗流)** | 仅保留策略接入层 | 弃用 (不适合时序) | **首选 (持久化底层)** |

#### 3. 统一数据注册表与访问层 (Unified Data Access Layer - UDAL)

使用 **DuckDB 作为中央查询引擎**，存储使用按 `symbol` 分区的 **Parquet** 文件。策略脚本禁止直接读写 `.csv` 或绝对路径。

```
[ Strategy / Researcher ]
          │ (调用 DataRegistry.get_klines("BTCUSDT", "1h", ...))
          ▼
[ DataRegistry (UDAL) ] ── (SQL 零拷贝查询) ──► [ DuckDB 内存/磁盘引擎 ]
                                                        │
                                                        ▼
                                           [ Partitioned Parquet Storage ]
                                           (data/processed/market_klines/*.parquet)
```

##### 统一数据访问层实现代码：

```python
# data_registry.py
import duckdb
import pandas as pd
from typing import Optional, List
from pathlib import Path
from config import settings

class DataRegistry:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or settings.DUCKDB_PATH)
        self._init_db()

    def _get_connection(self):
        return duckdb.connect(self.db_path)

    def _init_db(self):
        """初始化视图，实现对 Parquet 文件的无缝 SQL 映射"""
        with self._get_connection() as conn:
            parquet_pattern = str(settings.MARKET_PARQUET_DIR / "**" / "*.parquet").replace("\\", "/")
            # 建立零拷贝外部表视图
            conn.execute(f"""
                CREATE VIEW IF NOT EXISTS v_klines_hourly AS 
                SELECT * FROM read_parquet('{parquet_pattern}', hive_partitioning=True);
            """)

    def get_klines(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        sources: Optional[List[str]] = None,
        as_df_type: str = "pandas" # "pandas" 或 "polars" 或 "arrow"
    ):
        """
        统一策略获取数据入口，彻底抹平底层数据源差异与文件路径
        """
        sources_filter = ""
        if sources:
            src_str = ", ".join([f"'{s}'" for s in sources])
            sources_filter = f"AND source IN ({src_str})"

        query = f"""
            SELECT 
                timestamp, symbol, open, high, low, close, volume,
                open_interest, liquidations_long, liquidations_short,
                quality_flag, source
            FROM v_klines_hourly
            WHERE symbol = ? 
              AND timestamp >= ? 
              AND timestamp <= ?
              {sources_filter}
            ORDER BY timestamp ASC
        """
        
        with self._get_connection() as conn:
            rel = conn.execute(query, [symbol, start_date, end_date])
            if as_df_type == "polars":
                return rel.pl()
            elif as_df_type == "arrow":
                return rel.fetch_arrow_table()
            return rel.df()

    def save_cleaned_batch(self, df: pd.DataFrame, symbol: str):
        """写入清洗好的数据至规范分区 Parquet"""
        target_dir = settings.MARKET_PARQUET_DIR / f"symbol={symbol}"
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / "data.parquet"
        
        # 使用 DuckDB 高效写出成列存 Parquet
        with self._get_connection() as conn:
            conn.register("tmp_df", df)
            conn.execute(f"COPY tmp_df TO '{str(file_path).replace('\\', '/')}' (FORMAT PARQUET, COMPRESSION ZSTD);")
```

---

### C. 交易回撤可视化与交互式 Web 看板落地方案

#### 1. Drawdown 全景指标集定义与计算公式

量化研究中，回撤不能只看最大回撤，必须构建完整的**水下曲线 (Underwater Curve) 指标体系**：

1.  **高水位线 (High Water Mark, HWM)**：$HWM_t = \max_{0 \le \tau \le t} (Equity_\tau)$
2.  **水下百分比 (Underwater Curve)**：$Underwater_t = \frac{Equity_t - HWM_t}{HWM_t}$
3.  **最大回撤 (Max Drawdown, MDD)**：$MDD = \min_t (Underwater_t)$
4.  **谷底时刻 (Valley Point)**：触发 MDD 时的具体 Timestamp。
5.  **回撤持续期 (Drawdown Duration / Peak-to-Valley)**：从上一个历史高点到谷底的持续时间（小时数）。
6.  **恢复期 (Recovery Period / Valley-to-New-High)**：从谷底恢复到突破前高所耗费的时间（小时数）。若尚未突破，标记为 `Active Drawdown`。
7.  **Top N 经典回撤事件归因**：提取历史上跌幅最大的前 5 次回撤区间，自动匹配 FRED 宏观事件或加密市场异动（如：清算瀑布/黑天鹅）。

#### 2. 可视化框架对比与推荐

| 维度 | Plotly (Standalone) | Streamlit | Dash | Bokeh |
| :--- | :--- | :--- | :--- | :--- |
| **开发效率** | 高 (单文件写完) | **极高 (Pure Python 几行代码)** | 中 (需要设计 Callback/Layout) | 中 |
| **交互体验** | 良好 (缩放/Hover) | **优秀 (结合控件自动重绘)** | 极佳 (完全自定义) | 良好 |
| **架构复杂度** | 无需 Server (生成 HTML) | **极低 (内置静态 Web 容器)** | 中高 (Flask 封装) | 中 |
| **适合场景** | 研报导出 / 离线存档 | **本地交互式研究看板 (推荐)** | 生产级实盘监控大屏 | 极高频流式数据渲染 |

**推荐落地架构**：
*   **交互大屏**：采用 **Streamlit + Plotly** 作为本地交互看板（命令行一行 `streamlit run dashboard.py` 启动）。
*   **研报导出**：后台一键导出 Plotly 为离线可交互 `.html` 格式文件，无需依赖外部 Server。

#### 3. 交互式看板完整可运行代码 snippet

```python
# dashboard.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as gg
from plotly.subplots import make_subplots

# 页面配置
st.set_page_config(page_title="AlphaHive V3 Drawdown Analytics", layout="wide")

@st.cache_data
def calculate_drawdown_metrics(equity_series: pd.Series):
    """计算完整的 Underwater 与 Drawdown 指标集"""
    df = pd.DataFrame({'equity': equity_series})
    df['hwm'] = df['equity'].cummax()
    df['underwater'] = (df['equity'] - df['hwm']) / df['hwm']
    
    mdd = df['underwater'].min()
    end_idx = df['underwater'].idxmin()
    
    # 找到 peak index
    peak_idx = df.loc[:end_idx, 'equity'].idxmax()
    
    # 找到 recovery index
    after_valley = df.loc[end_idx:, 'equity']
    recovery_matches = after_valley[after_valley >= df.loc[peak_idx, 'equity']]
    
    recovery_idx = recovery_matches.index[0] if not recovery_matches.empty else None
    
    return df, {
        "max_drawdown": mdd,
        "peak_time": peak_idx,
        "valley_time": end_idx,
        "recovery_time": recovery_idx,
        "duration_hours": (end_idx - peak_idx).total_seconds() / 3600 if isinstance(end_idx, pd.Timestamp) else None
    }

# 示例数据生成器 (实际中使用 DataRegistry 读取)
def load_sample_data():
    dates = pd.date_range("2026-05-01", "2026-08-01", freq="1h")
    returns = np.random.normal(0.0002, 0.005, len(dates))
    # 模拟两次黑天鹅回撤
    returns[300:320] = -0.015
    returns[1200:1250] = -0.012
    equity = 100000 * np.cumprod(1 + returns)
    return pd.Series(equity, index=dates)

# Dashboard UI 布局
st.title("🛡️ AlphaHive V3 - 交易回撤与归因交互式看板")

equity_data = load_sample_data()
df_drawdown, metrics = calculate_drawdown_metrics(equity_data)

# KPI Card 呈现
col1, col2, col3, col4 = st.columns(4)
col1.metric("当前净值", f"${equity_data.iloc[-1]:,.2f}")
col2.metric("最大回撤 (MDD)", f"{metrics['max_drawdown']:.2%}")
col3.metric("峰值->谷底时长", f"{metrics['duration_hours']} 小时")
col4.metric("恢复状态", "已恢复" if metrics['recovery_time'] else "处于水下", delta_color="inverse")

# Plotly 双图联动 (净值 + 水下曲线)
fig = make_subplots(
    rows=2, cols=1, 
    shared_xaxes=True, 
    vertical_spacing=0.08,
    subplot_titles=("策略累计净值与高水位线 (HWM)", "Underwater 水下百分比曲线 (%)"),
    row_heights=[0.6, 0.4]
)

# 净值线与 HWM
fig.add_trace(gg.Scatter(x=df_drawdown.index, y=df_drawdown['equity'], name="Equity", line=dict(color="#1f77b4", width=2)), row=1, col=1)
fig.add_trace(gg.Scatter(x=df_drawdown.index, y=df_drawdown['hwm'], name="HWM", line=dict(color="#2ca02c", dash="dash")), row=1, col=1)

# 标记 MDD 区间
fig.add_vrect(
    x0=metrics['peak_time'], x1=metrics['valley_time'],
    fillcolor="red", opacity=0.2, line_width=0,
    annotation_text="Max Drawdown Phase", row="all", col=1
)

# Underwater 填充曲线
fig.add_trace(
    gg.Scatter(
        x=df_drawdown.index, y=df_drawdown['underwater'] * 100, 
        name="Underwater %", fill='tozeroy', 
        line=dict(color="#d62728", width=1.5),
        fillcolor="rgba(214, 39, 40, 0.3)"
    ), 
    row=2, col=1
)

fig.update_layout(height=650, margin=dict(l=20, r=20, t=40, b=20), hovermode="x unified", template="plotly_dark")
fig.update_yaxes(title_text="USD", row=1, col=1)
fig.update_yaxes(title_text="Drawdown %", row=2, col=1)

st.plotly_chart(fig, use_container_width=True)

# 离线 HTML 导出支持
if st.button("导出为离线 HTML 研报"):
    fig.write_html("drawdown_report.html")
    st.success("研报已成功导出至 local `drawdown_report.html`！")
```

---

### D. OpenBB v4 注册本地数据 vs 务实自研 Plotly/Streamlit 方案评估

#### 1. OpenBB v4 自定义 Provider 注册逻辑简析

OpenBB v4 采用了全新的插件式架构 (`openbb-core`)。若要插入 AlphaHive 的本地多源 Klines/Liquidation 数据，需要实现 custom `Fetcher` 和 `ProviderData` 接口：

```python
# 框架示例：OpenBB v4 自定义 Extension (仅作架构展示)
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.data import Data
from pydantic import BaseModel
from typing import List

class AlphaHiveKlineData(Data):
    symbol: str
    close: float
    open_interest: float
    liquidations: float

class AlphaHiveFetcher(Fetcher[BaseModel, List[AlphaHiveKlineData]]):
    def transform_data(self, query, data, **kwargs) -> List[AlphaHiveKlineData]:
        # 从 AlphaHive DataRegistry 读取 DuckDB 转换
        return [...]

# 必须在 pyproject.toml 注册 setuptools entry_points 才能生效
```

#### 2. 深度对比与务实建议

| 评估维度 | OpenBB v4 Custom Provider 方案 | 自研 Streamlit + Plotly + DuckDB 方案 (推荐) |
| :--- | :--- | :--- |
| **适配性** | 偏向标准美股/标准 Crypto Klines，对衍生品清算/持仓/链上数据建模僵硬 | **100% 自由定制**，任意增加位掩码、稀疏清算、链上指标 |
| **接入成本** | 高。需理解 `openbb-core` 的 Pydantic 校验、Extension 注册与 EntryPoints | **极低**。直接用 Python/pandas 代码即插即用 |
| **依赖稳定性** | OpenBB v4 升级频繁，API 经常变动 (Breaking Changes 风险大) | **零风险**。底层仅依赖通用基础设施 (`duckdb`/`plotly`/`streamlit`) |
| **图表灵活性** | 受限于 OpenBB OpenBBTerminal/Chart 类的预设 API | **完全可控**。可任意使用 Plotly 次坐标轴、三维曲面、多图联动 |

#### 务实落地结论：
**强烈建议放弃在 OpenBB v4 中注册 Custom Provider 的方案，采用“自研 Streamlit + Plotly + DuckDB”架构。**

*   **原因**：AlphaHive V3 包含大量非标衍生品数据（如 Coinalyze 稀疏清算零填充、Binance OI、Pyth 跨源对账、自定义数据质量标记 `quality_flag`），OpenBB 默认的标准 OHLCV 抽象模型无法无缝表达这些维度。使用自研轻量级方案，可以省去 80% 的框架包装代码，把全部精力和算力留在 Alpha 研究与数据质量控制本身。

---

### 二、总结与 AlphaHive V3 重构路线图 (Execution Roadmap)

1.  **第一周（路径与底层存储规范化）**：
    *   引入 `config.py` (`pathlib` + `pydantic-settings`) 替换 30+ 脚本中的字符串路径。
    *   搭建 `DataRegistry` 与 DuckDB 引擎，将历史 CSV/Parquet 转存为 `data/processed/market_klines/symbol=*/data.parquet`。
2.  **第二周（深度清洗与数据质量 Watchdog）**：
    *   在 ETL 脚本中接入 `clean_hourly_klines`，重点部署 720h 滚动中位数去脏与 Coinalyze 稀疏零填充。
    *   部署 Telegram / 邮件 / 终端日志 SLA 数据新鲜度告警 (`check_data_freshness`)。
3.  **第三周（可视化看板重构）**：
    *   放弃 Matplotlib 静态 PNG，使用 Streamlit + Plotly 搭建交互式 Underwater 曲线看板，并支持一键导出离线 HTML。
