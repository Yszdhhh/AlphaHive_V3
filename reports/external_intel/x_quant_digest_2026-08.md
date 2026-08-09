# X 量化情报 Digest — 2026-08-08

> 来源：深度调研（X 中文主 + 英文主题）。**非投资建议**；只沉淀机制与可测假设。  
> 完整蓝图见会话 plan；本文件是项目内可检索沉淀。

## 1. 账号画像（已关注）

| 账号 | 定位 | 对本项目价值 |
|---|---|---|
| @StepOneAi | 做市/资金费率**数据口径** | P0：测量语义，不是策略口号 |
| @pritipatelfgoo | 链上套利 + regime/仓位方法论 | GMM 过滤、Kelly、Alpha 五源 |
| @Dogquant0 | 费率/价差 taker + HFT maker | 「能胡就胡」小正期望；AS-HJB 库存直觉 |
| @MrRyanChi | 预测市场 | Side lab，与 wash_cvd 正交 |

## 2. 近期市场共识（合成）

1. 方向盘难、资金找**非方向**小而稳现金流（三角套利、做市、费率收租）。
2. 公开「方向型量化」叙事可信度低；真 edge 多在流动性/约束/制度流。
3. Funding 不是温度计：结算周期、TWA 权重、Impact Notional、**费率封顶删失**会污染因子。
4. 预测市场 maker rebate / oracle 延迟是第二战场（不并入主栈）。

## 3. 对 AlphaHive 的直接映射

| 外部认知 | 内部动作 |
|---|---|
| Funding 测量/删失 | `funding_semantics` + 审计脚本（见 `reports/funding_semantics_audit.md`） |
| GMM 状态过滤 | `regime_gmm` 只服务 s001 过滤/仓位缩放，不发明方向 |
| 非方向小钱 | s014 funding carry（市场中性）预注册 |
| 新币机构盲区 | s009 继续前向；s015 微观结构增强预注册 |
| s005 方向失败 | **不复活**；语义层可解释「为何 z-score 横比失败」 |

## 4. 禁止吸收

- 连赢加码 / 反马丁当 alpha  
- 黑箱卖参量化  
- 未中性化的 funding 符号当方向  
- 未预注册的因子喷泉  

## 5. 订阅清单（轻）

继续：StepOneAi / 套利豪仔 / Dogquant0。  
可选主题：预测市场 maker rebate、Avellaneda–Stoikov 库存（认知 only）。  
忽略：挑战赛喊单、保证月化截图。
