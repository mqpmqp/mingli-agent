# MINGLI Core Capability Surge V2 集成报告

状态：本地集成与对抗审查完成；最终集成 Draft PR 待创建。  
冻结基线：`00eeaad66a2a36684ae2ad0b5b0074fcdf700640`  
已验证代码 checkpoint：`97a50149519f84099451a8c30e2dc54310c8fce6`  
分支：`integration/mingli-core-capability-surge-v2`  
Release Hold：`ACTIVE`  
Prediction boundary：`prediction_validity=not_evaluated`

## 集成顺序

| 顺序 | 内容 | 来源分支 / checkpoint | 集成 checkpoint |
| --- | --- | --- | --- |
| 1 | frozen contracts | `codex/mingli-core-contract-freeze-v2` / `b39418ca607b1d9352c46ae1c9af3f20beea8f1d` | `325a21d` |
| 2 | Bazi Expert Rules V2 | `codex/bazi-expert-rules-v2` / `ad05254ebe2f553cffdc9374b5fd531e878b5faa` | `378aec4` |
| 3 | Ziwei Temporal and Combination Rules V2 | `codex/ziwei-temporal-combination-rules-v2` / `705f348ed310c0531d80f097b6b0c69478644814` | `8c9bf7d` |
| 4 | Real Case Learning OS V2 | `codex/real-case-learning-os-v2` / `c71dc7c6fde359b793a33394328710140829608b` | `90b69cc` |
| 5 | Runtime、Renderer、HTTP、MCP | integration-owned | `3bdd00b` |

冻结合同校验保持 `78/78`，0 violation，未重写 PR #30 合并后的公共合同。

## 三轮对抗收敛

| 审查主题 | 主要收口 | 最终结果 |
| --- | --- | --- |
| 算法与时间边界 | evidence availability cutoff、overlay 唯一父级、snapshot/partition 语义重验 | 双 reviewer PASS |
| 规则内容与伪覆盖 | 独立冻结 Ziwei 规则哈希、完整 ruleset、mutation/false-pass 阻断 | 双 reviewer PASS |
| 案例泄漏、隐私与 Reality Override | consent/PII/synthetic 重验、withdrawal trust proof、coordinated reseal 冲突阻断 | 双 reviewer PASS |

完整 RED/GREEN checkpoint 与反例证据见 `docs/testing/mingli-core-capability-surge-v2-adversarial-convergence.tdd.md`。

## Runtime 集成

- 新增 additive、versioned 的统一编排入口，不替换冻结 runtime。
- HTTP 提供只读 capabilities 与 analyze surface；请求不持久化，响应使用 `no-store`。
- MCP 工具 `analyze_capability_surge_v2` 声明 `readOnlyHint=true`、`destructiveHint=false`。
- Yuan Renderer 继续执行单免责声明、禁绝对承诺、受控置信度与 Reality override。
- unsupported 输入、未知版本、越界时间、证据泄漏、冲突 Reality Evidence 均 fail closed。

## Draft PR 清单

- Contracts：[#31](https://github.com/mqpmqp/mingli-agent/pull/31)，Draft，未合并。
- Ziwei：[#32](https://github.com/mqpmqp/mingli-agent/pull/32)，Draft，未合并。
- Real Case OS：[#33](https://github.com/mqpmqp/mingli-agent/pull/33)，Draft，未合并。
- Bazi：[#34](https://github.com/mqpmqp/mingli-agent/pull/34)，Draft，未合并。
- 最终 integration Draft PR URL 由远端创建步骤补充到交付消息与 Obsidian handoff；不得自行合并。

## 边界声明

本集成没有发布、tag、PyPI 上传或 Release Hold 解除。没有使用真实案例，也没有用 synthetic/contract fixtures 证明准确率。工程行为覆盖不等于传统规则内容已获独立认可，更不等于真实世界预测有效。
