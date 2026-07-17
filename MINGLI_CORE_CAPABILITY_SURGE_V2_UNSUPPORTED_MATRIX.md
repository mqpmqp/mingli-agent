# MINGLI Core Capability Surge V2 Unsupported Matrix

以下能力不是静默降级项。调用方必须收到明确 unsupported、missing-prerequisite 或 validation error；不得猜测、补全或 fail open。

| 范围 | Unsupported / 未获授权能力 | 行为 |
| --- | --- | --- |
| Bazi | frozen contract 之外的流月判断 | fail closed；不伪装为流年细化 |
| Bazi | 结婚、离婚等婚姻具体事件预测 | fail closed；仅保留关系结构倾向 |
| Bazi | family domain 结论 | fail closed；frozen domain contract 未提供 |
| Bazi | 合盘评分、关系结果保证 | comparison-only；无分数、无结果断言 |
| Bazi | 考公录取、复合成功保证 | 只给条件与策略，不给保证 |
| Ziwei | 非 complete 或算法版本不兼容的 chart | reject |
| Ziwei | 无父级、多个父级、越界的大限/流年/流月 overlay | reject |
| Ziwei | 日级具体事件点或保证性事件预测 | reject |
| Ziwei | coordinated source/fixture/hash rewrite 伪覆盖 | reject against independent frozen manifest |
| Reality Evidence | unverified、future-unavailable、scope 不匹配 evidence | 不覆盖；非法边界直接 reject |
| Reality Evidence | 同 claim/scope 的 verified 相反 future directions | `CONFLICTING_REALITY_EVIDENCE`；等待 operator reconciliation |
| Real Case OS | 未同意、可识别 PII、伪 synthetic provenance | reject |
| Real Case OS | 未可信 standalone withdrawal tombstone | reject，必须进入 trusted registry |
| Real Case OS | 自动规则 promotion/demotion/application | unsupported；只生成 pending review |
| Real Case OS | synthetic/contract fixture 进入 accuracy metrics | excluded，`accuracy_eligible=false` |
| Runtime | case 持久化、外部网络调用、自动发布 | unsupported |
| Product | 准确率、命中率、校准度或商业有效性声明 | unsupported；0 qualified real cases |
| Release | publication、tag、PyPI upload、解除 Hold | 未授权且未执行 |

全局固定边界：

```text
prediction_validity=not_evaluated
product_accuracy_claim_allowed=false
release_hold=ACTIVE
```
