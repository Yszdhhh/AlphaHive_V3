# PROMPT_RERENDER_AUDIT

**状态：** `GREEN`（生产重渲核验完成；外部研究仍 `UNVERIFIED`）  
**契约：** `config/deep_research_contract.yaml`  
**真实基准 run：** `20260511_1200_utc_replay`  
**候选：** `20260511_1200_utc_replay_0014 / SKYAIUSDT`  
**渲染入口：** `harness.lib.deep_research_package.build_prompt_package` + `render_research_prompt`

## 输入与输出 hash

- contract SHA-256: `025b5ca8c3d8dc575e668217cd0d2d21d5ec9b91f8a196446710c2b01be96dcc`
- rendered prompt SHA-256: `7d6dc81fb1c920ff71bd26aaa5d36a921f8edf25435dc88be6152eacb4671e1b`
- package schema: `deep_research_prompt_package_v1`

## 中立枚举核验

生产真实 YAML 渲染出的 `overall_evidence_allowed` 为：

```text
CONTINUATION_EVIDENCE_STRONGER
REVERSAL_EVIDENCE_STRONGER
MEAN_REVERSION_EVIDENCE_STRONGER
DATA_ARTIFACT_LIKELY
MIXED
NO_TRADE_BLOCKER
INSUFFICIENT_EVIDENCE
```

- `LONG_THESIS_STRONGER` in allowed: `False`
- `SHORT_THESIS_STRONGER` in allowed: `False`
- 两个旧方向枚举在完整 rendered prompt 中出现：`False`
- 本次无需修改真实 YAML；没有产生 diff。

## 其它观察

- 渲染文本保留 `no_direction_claim = true`、四竞争假设、GRAVEYARD 禁止动作和 `UNVERIFIED`/质量闸语义。
- 该真实历史 run 的旧 manifest 没有携带 P8 后的 known-list 字段，因此本次包出现 `KNOWN_LIST_NOT_AVAILABLE` 警告；这不是方向枚举泄漏。当前生产 scanner 新 manifest 已声明 `known_list_version=v1`，后续新 run 应使用新 manifest。
- OI/funding quantile 仍在研究包中标为未点火；本次没有把 F2.1 OI/funding 状态转成候选 trigger，也没有 paper 联动。
