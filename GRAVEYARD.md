# AlphaHive V3 墓地：已证伪方向先验

本文件是已证伪方向的单一真理源。研究提示词只能引用或注入本文件的约束，不得在其它位置复制一份可漂移的墓地正文。

## 1. Phase-1 七因子：全 HARD_FAIL

以下七个因子在 Phase-1 全部标记为 `HARD_FAIL`，不是待调参或待优化的因子选择问题：

- `ls_divergence_ewm`
- `ls_divergence_rank`
- `vvc_coupling`
- `lcs_susceptibility`
- `funding_level`
- `s0_combo`
- `ls_div_from_panels`（真背离）

绑定约束是交易结构（换手）与 OOS 统计功效天花板，不是因子选择。任何回看结果都不能把这些因子重新包装成可交易方向机制。

## 2. 主观量化线

固定做空 ETH 残差全样本加 10.27%，但 Sharpe 仅 0.229，结论是 beta 而不是 alpha。机械方向择时已被干净证伪：越择时越亏。底盘是 sound 的，但底盘本身不产生 alpha。

## 3. Carry / 庄家-费率

Carry / 庄家-费率机制已实测证伪：在“该赢的拥挤空头 regime”反而亏钱。`funding_level` 的 gross 边为真，但死于换手；`carry_event_probe = NO-GO`。

## 4. 总定性与历史坑

价格/衍生品数据没有可系统化收割的方向 alpha，已三次独立确认。另记 funding 100× 单位坑：P0、`exec_planner`、carry 已各咬过一次，合计三次；任何新研究必须先核对单位，不能默认可信。

墓地中的方向包括：carry/庄家-费率、跟随聪明钱、机械方向择时。它们不得作为交易机制建议复活。
