# s017 Token Unlock — 数据可得性审计（轻量）

- date: 2026-08-12 07:37 UTC
- script: `scripts/s017_unlock_data_audit.py`
- source: Mobula demo `metadata.release_schedule`（免费路径；非 Tokenomist）
- **非回测**；不宣布 GO

## 结论

| 项 | 值 |
|---|---|
| 探针币数 | 77 |
| API 成功 | 74 |
| 有 release_schedule | 28 |
| 展开事件行 | 15332 |
| 可算 pct_circ≥0.5% | 3094 |
| alloc 粗含 team/investor 类 | 9224 |
| **审计判定** | **PASS_LIGHT** |

## 字段可用性

- unlock_date: True
- tokens_to_unlock: True
- circulating_supply 覆盖币数: 74
- allocation_details 非空事件: 15332
- cliff vs linear: **弱**（Mobula 不标；需 Tokenomist daily-emission 或人工）

## 覆盖表（节选）

```
    symbol                                 asset  n_schedule  has_circ    ok
   SUIUSDT                                   Sui        2558      True  True
   ARBUSDT                              Arbitrum          38      True  True
   ENAUSDT                                Ethena           0      True  True
  ONDOUSDT                                  Ondo          17      True  True
PENDLEUSDT                                Pendle           0      True  True
   INJUSDT                             Injective          27      True  True
   TIAUSDT                              Celestia        1097      True  True
  LINKUSDT                             Chainlink           0      True  True
  AAVEUSDT                                  Aave           0      True  True
   UNIUSDT                               Uniswap          48      True  True
RENDERUSDT                                Render           0      True  True
  AVAXUSDT                             Avalanche          41      True  True
    OPUSDT                              Optimism          50      True  True
   LDOUSDT                              Lido DAO          29      True  True
   CRVUSDT                             Curve DAO        1460      True  True
   FILUSDT                              Filecoin           0      True  True
  ATOMUSDT                                Cosmos           0      True  True
   APTUSDT                                 Aptos           0     False False
   WLDUSDT                             Worldcoin        1462      True  True
  STRKUSDT                              Starknet           3      True  True
   SEIUSDT                                   Sei        2558      True  True
   JUPUSDT                               Jupiter           0      True  True
  PYTHUSDT                          Pyth Network           5      True  True
   JTOUSDT                                  Jito           0      True  True
     WUSDT                              Wormhole           0      True  True
   ALTUSDT                              Altlayer           0      True  True
 MANTAUSDT                         Manta Network        2192      True  True
   DYMUSDT                             Dymension           0      True  True
 PIXELUSDT                                Pixels           0      True  True
PORTALUSDT                                Portal           0      True  True
  AEVOUSDT                                  Aevo           0      True  True
 ETHFIUSDT                              ether.fi           0      True  True
   REZUSDT                                 Renzo           0      True  True
    BBUSDT                             BounceBit           0      True  True
   NOTUSDT                               Notcoin           0      True  True
    ZKUSDT                                ZKsync           0      True  True
 LISTAUSDT                             Lista DAO           0      True  True
    IOUSDT                                io.net           0      True  True
   ZROUSDT                             LayerZero           0      True  True
  DOGEUSDT                              Dogecoin           0      True  True
   ADAUSDT                               Cardano           0      True  True
  NEARUSDT                         NEAR Protocol        1827      True  True
   ICPUSDT                     Internet Computer          48      True  True
  HBARUSDT                                Hedera          18      True  True
  ALGOUSDT                              Algorand         120      True  True
  SANDUSDT                           The Sandbox          10      True  True
  MANAUSDT                          Decentraland           0      True  True
   AXSUSDT                         Axie Infinity          26      True  True
   IMXUSDT                             Immutable           0      True  True
  GALAUSDT                                  Gala           0      True  True
   APEUSDT                               ApeCoin           0      True  True
   LTCUSDT                              Litecoin           0      True  True
   BCHUSDT                          Bitcoin Cash           0      True  True
   DOTUSDT                              Polkadot           0      True  True
   TRXUSDT                                  TRON           0      True  True
   XLMUSDT                               Stellar           0      True  True
   VETUSDT                               VeChain           0      True  True
   FTMUSDT                                Fantom           0      True  True
   SFPUSDT                               SafePal          69      True  True
   CFXUSDT                               Conflux           0      True  True
  ROSEUSDT                         Oasis Network           0     False False
 1INCHUSDT                                 1inch           9      True  True
   SNXUSDT                             Synthetix          50      True  True
  COMPUSDT                              Compound           0      True  True
   MKRUSDT                                 Maker           0      True  True
   GRTUSDT                             The Graph         121      True  True
   ENSUSDT                 Ethereum Name Service           0      True  True
   LRCUSDT                              Loopring           0      True  True
  BLURUSDT                                  Blur        1341      True  True
  MASKUSDT                          Mask Network          42      True  True
   SSVUSDT                           ssv.network           0     False False
   RPLUSDT                           Rocket Pool           0      True  True
    ARUSDT                               Arweave           0      True  True
   KASUSDT                                 Kaspa           0      True  True
   TAOUSDT                             Bittensor           0      True  True
   FETUSDT Artificial Superintelligence Alliance          66      True  True
  RNDRUSDT                                Render           0      True  True
```

## 缺口 / 下一跳

1. **接收方 team/investor**：Mobula allocation 命名不标准，主规格过滤需映射表或升级 Tokenomist。
2. **ADV ≥ $2M**：需 join binance 1h 成交额（本探针未做）。
3. **n≥80 主规格事件**：全量拉 watchlist + 历史 schedule 后才可估；当前 sample 仅探针。
4. 派生目录：`G:\Quant test\derived_data\token_unlocks\`（不改 coinglass/binance 源结构）。
5. 大型全量日历回填 → **VPS / Grok Bot 侧** 跑，本地只维护探针与规格。

## 错误

```
  symbol         asset                        error
 APTUSDT         Aptos The read operation timed out
ROSEUSDT Oasis Network  HTTP Error 400: Bad Request
 SSVUSDT   ssv.network  HTTP Error 400: Bad Request
```
