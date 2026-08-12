# TASK: s017 扩日历 + 再诊断（本地）

**Tier:** T2  
**Lead:** 不改 S1 已选 pct=1%；只扩样本看集中度是否下降。  
**输出:**  
- `scripts/s017_expand_calendar.py`  
- `scripts/s017_expand_diagnose.py`（或合并单脚本）  
- `reports/s017_expand_diagnose.md`  
- `derived_data/token_unlocks/sample_events.parquet`（更新，可备份旧文件）  
- `derived_data/token_unlocks/coverage_expanded.csv`

## 必做

1. 以 coinglass klines 全量 symbol 为候选（有价才有用），扩 Mobula `release_schedule` 拉取。  
2. 合并进 `sample_events`（保留旧事件；新币/新行追加）。  
3. **冻结** pct≥1% + ADV≥2M + 冷却 7d，重算 short_resid（复用 s017_s0_local 函数）。  
4. 诊断（同 deconcentrate 口径）：  
   - 币数、n、top1 权重、SEI 占比  
   - leave-SEI / leave-top3  
   - 簇化（7d）  
   - 稀疏 cliff（≤4/币/年）诊断列  
5. Verdict：`STRUCTURAL_MULTI` / `SINGLE_NAME_DOMINATED` / `MIXED_NEED_MORE_CALENDAR` / `IMPROVED_BUT_STILL_MIXED`  
6. **禁止** 重跑 S1 选形态、禁止 GO、禁止改 s018/s001。

## 验收

```bash
cd "G:\Quant test\AlphaHive_V3"
python scripts/s017_expand_calendar.py
python scripts/s017_expand_diagnose.py
```
