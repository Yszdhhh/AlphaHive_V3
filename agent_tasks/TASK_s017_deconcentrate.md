# TASK: s017 降集中诊断（本地，Lead 派发）

**Tier:** T2  
**前置:** `reports/s017_s1_holdout.md` Lead 验收 = CONCENTRATED  
**输出:**  
- `scripts/s017_deconcentrate.py`  
- `reports/s017_deconcentrate.md`  

## 目标

回答：Unlock 边是「多币结构」还是「SEI 线性解锁 quirk」？

## 必做（描述性，禁止改卡、禁止宣称 GO）

1. 读 `s1_eval_events.csv` / `s1_select_events.csv` / `sample_events.parquet`。
2. 报告：
   - 各币 n、mean short、占全样本权重
   - leave-one-symbol-out（至少 SEI / ARB / top3）
   - **事件簇**：同一 symbol 将间隔≤7d 的解锁并成一簇，按簇重算（降伪独立）
   - 可选过滤（仅诊断，三列并列，不选胜）：  
     a) 剔除 schedule 行数>100 的币（疑似日更线性）  
     b) 仅 `team_investor==True`  
     c) pct≥1% 且 每币每年最多 4 个事件（强制稀疏 cliff）
3. 输出 Verdict 三选一：  
   - `STRUCTURAL_MULTI`：leave-top 后仍稳  
   - `SINGLE_NAME_DOMINATED`：主要 SEI  
   - `MIXED_NEED_MORE_CALENDAR`：方向在但 n 不够

## 禁止

- 用本诊断结果回头改 S1 选中的 pct  
- 进 S2 / historical_pass  
- 碰 s018/s001 代码  

## 回传

Verdict + 一页表 + 报告路径。
