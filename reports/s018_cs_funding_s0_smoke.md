# s018 CS_MN Funding — S0 轻量探针

- date: 2026-08-12 07:21 UTC
- script: `scripts/s018_cs_funding_s0_smoke.py`
- source: `C:\Users\10639\Desktop\加密\binance_free_db\history\funding`
- symbols scanned: 40（上限 40，排除 BTC/ETH）
- settlement config: 8h
- **非完整回测 / 不宣布 GO**；标题含 **CS_MN**（反 s005 / 异于 s014）

## 结论

| 项 | 值 |
|---|---|
| 中位结算间隔 (h) | 8.000 |
| 对齐 config 8h 的币数 | 24/40 |
| pooled n / capped | 148133 / 111 (0.075%) |
| 有 bucket 数 | 5036 |
| 可交易 bucket（n_sym≥25） | 1908 |
| 中位 p90−p10 funding 离散 | 0.000170096 |
| 抽样期毛截面价差均值 (short−long) | 0.000596351 （n=200） |
| **审计判定** | **PASS_LIGHT** |

## 解释

1. **结算对齐**：本地 history 中位间隔应≈8h；偏离大的币 S1 需 per-symbol 覆盖。
2. **semantics**：`is_capped=True` 已剔除，不得当真实压力。
3. **CS_MN 信号形状**：空最高 quintile / 多最低 quintile；本探针只验证「离散度 + 可组期数 + 毛 funding 价差方向描述」。
4. **与 s014 分离**：此处无现货对冲腿；仅为永续截面。
5. **与 s005 分离**：不做「拥挤→做多价格」方向规则。

## 成本提示

完整成本需换手矩阵；本探针只报毛 funding 截面价差均值，27bps 悲观与 16.2bps 真实锚留给 S1/VPS。

## 结算间隔 top 偏差

```
      symbol    n  median_settle_h      dev
       MUSDT 3300         3.999999 4.000001
     LABUSDT 2146         4.000000 4.000000
1000BONKUSDT 5927         4.000000 4.000000
   ASTERUSDT 1926         4.000000 4.000000
 ESPORTSUSDT 2619         4.000000 4.000000
      BZUSDT  769         4.000000 4.000000
       HUSDT 2858         4.000000 4.000000
   GRASSUSDT 3815         4.000000 4.000000
```

## 下一跳

1. 全 70 币 + 全历史 + 价格腿 PnL 拆分 → **VPS**
2. 换手与 16.2/27 bps 双列成本
3. 以 2025-01 切两段同向；n≥180 调仓期
4. s014 不改

## 依赖

- `harness/lib/funding_semantics.py`
- `config/funding_measurement.yaml` v1
