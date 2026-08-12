# TASK: s017 S1 Holdout（本地执行）

**Tier:** T2 研究脚本  
**派给:** code / general-purpose 执行 agent  
**Lead 冻结日:** 2026-08-12  
**输出只允许写:**  
- `G:\Quant test\AlphaHive_V3\scripts\s017_s1_holdout.py`  
- `G:\Quant test\AlphaHive_V3\reports\s017_s1_holdout.md`  
- `G:\Quant test\derived_data\token_unlocks\s1_*.csv`（可选）

## 背景（只读）

- 卡：`strategies/s017_token_unlock/alpha_card.md`
- S0：`reports/s017_s0_local.md` + `derived_data/token_unlocks/s0_events.csv` + `sample_events.parquet`
- 方法论：S0 选形态 → S1 **前 80% 时间** 只用于在预声明集合里选一个 pct 阈值 → **后 20% 只评一次**
- 预声明 pct：`{0.0025, 0.005, 0.01}`（主卡默认 0.5%，但族内敏感性已预注册）
- 价格：`C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h\klines`
- seed=`20260812`；成本 round-trip `0.0027*2`；空残差定义同 `scripts/s017_s0_local.py`

## 必须实现

1. 复用 s017_s0_local 的窗口/β/ADV/冷却逻辑（可 import 或复制最小函数，禁止改卡定义）。
2. 事件池：`sample_events.parquet`；过滤 ADV≥2e6、冷却 7d、有 BTC/币 klines。
3. **时间 holdout**：按 `unlock_ms` 排序；前 80% = select；后 20% = eval（一次）。
4. 在 select 段，对三个 pct 各算 mean/median/CI(short_resid)、两段内同向（select 内再切半仅诊断）、n。
5. **选形态规则（冻结，禁止事后改）**：  
   - 主分：select 段 mean_short 的 bootstrap CI 下界最大者；  
   - 若并列：median 更大；再并列：n 更大；再并列：pct 更严（0.01>0.005>0.0025）。
6. 用**胜出 pct** 在 eval 段算一次：n、mean、median、CI、mean_net、pos%、vs 随机基线（可选简化）。
7. **GO 候选条件（报告写清是否满足，禁止自行宣布 historical_pass）**：  
   - eval n≥20（不足标 UNDERPOWERED）  
   - eval CI 下界 > 0 且 median ≥ 0  
   - mean_net > 0  
   - 不在报告标题写 GO_LONG；只用 `S1_PASS_CANDIDATE` / `S1_FAIL` / `S1_UNDERPOWERED`
8. 报告必须含：选中 pct、select 三形态表、eval 唯一结果、数据性质=development/exploratory、禁升级声明。

## 禁止

- 看 eval 后再改选形态或阈值
- 合并 select+eval 调参
- 改 s014/s018/s001
- 宣称 live / 前向通过
- 依赖 VPS 或新付费 API

## 验收

```bash
cd "G:\Quant test\AlphaHive_V3"
python scripts/s017_s1_holdout.py
# 退出码 0；写出 reports/s017_s1_holdout.md
```

## 回传格式

- 正式报告路径  
- Verdict 三选一  
- 选中 pct + eval mean/CI/n  
- 未决项  
