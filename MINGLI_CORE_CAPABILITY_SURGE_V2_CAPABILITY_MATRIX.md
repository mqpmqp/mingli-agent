# MINGLI Core Capability Surge V2 Capability Matrix

状态语义：`implemented` 表示确定性工程行为已实现；`conditional` 表示依赖明确输入/既有 frozen phase 且保留结论边界；`unsupported` 必须 fail closed。所有状态均不代表真实世界准确率。

## Bazi Expert Rules V2

| 能力 | 状态 | 工程实现与边界 |
| --- | --- | --- |
| 五行旺衰量化 | implemented | 复用 Phase 9 数值合同 |
| 同类/异类比例 | implemented | 输出 frozen strength ratios，不重算 |
| 格局判断 | conditional | Phase 10 candidate-only，不推导具体事件 |
| 用神和调候 | conditional | Phase 11/12 候选与季节气候需要；非经典结论保证 |
| 十神组合 | conditional | Phase 15 natal/dynamic/domain evidence |
| 刑冲合害 | implemented | 汇总既有结构 relation records |
| 大运、流年 | implemented | Phase 13/14 结构互动与趋势 |
| 流月 | unsupported | frozen Bazi temporal contract 无 `liuyue` |
| 事业、财运、感情、学业 | conditional | 结构化 domain candidates + confidence |
| 婚姻具体事件 | unsupported | 不从关系倾向推导结婚/离婚事件 |
| 家庭 | unsupported | frozen domain contract 无 family domain |
| 考公考编四项 | conditional | Phase 17 层适配：体制、考试、岗位、策略；不保证录取 |
| 感情复合四项 | conditional | Phase 17 层适配：牵引、复联、复合、稳定；不保证结果 |
| 双人基础合盘 | conditional | 双方结构对照；无评分、无关系结果断言 |
| 前事验证 | conditional | 仅 verified prior-event evidence；不是准确率证明 |
| Reality Evidence hard override | implemented | 同 `claim_id + scope`，冲突则 unresolved/low |
| confidence calibration | implemented | verified reality 才可能提升；冲突/unsupported 降权 |
| Yuan Renderer | conditional | 输入齐备时接入；单免责声明、禁保证语 |

## Ziwei Temporal and Combination Rules V2

| 能力 | 状态 | 工程实现与边界 |
| --- | --- | --- |
| 四化、主辅星组合 | implemented | versioned rule pack + canonical semantic hashes |
| 三方四正、夹拱会照 | implemented | 宫位几何 token 与行为触发 |
| 命身关系、庙旺状态 | implemented | 规范关系与 brightness state 组合 |
| 大限、流年、流月 | implemented | 严格父级、唯一 containment 与有界窗口 |
| 六主题 | implemented | 事业、财运、感情、学业、家庭、迁移行为规则 |
| 事件时间窗口 | conditional | 候选观察窗口，不是事件发生保证 |
| 冲突与降权 | implemented | 低优先级 suppressed；同优先相反方向 unresolved/low |
| unsupported fail closed | implemented | 非 complete、未知版本、越界 overlay、事件预测请求均拒绝 |
| Reality Evidence override | implemented | verified 且 exact claim/scope，受 availability cutoff 约束 |
| 行为 coverage | implemented | trigger/exclusion/conflict/unsupported 四路行为核验 |
| false-pass / mutation | implemented | 独立 frozen manifest 阻断 coordinated rewrite |

Ziwei 规则内容仍为 `draft`，`accuracy_assessment=not_assessed`。行为 coverage 证明代码路径，不证明传统内容正确或预测准确。

## Real Case Learning OS V2

| 能力 | 状态 | 工程实现与边界 |
| --- | --- | --- |
| intake / consent / anonymization | implemented | closed schema、explicit consent、HMAC pseudonym contract |
| withdrawal | implemented | trusted tombstone 或 exact case binding；递归失效依赖 |
| chart/question/reality/prediction snapshots | implemented | sealed hashes、time cutoff、future leakage closed |
| prior validation / future outcome | implemented | claim/scope/window 绑定；availability 与方向重验 |
| hit/partial/miss/unverifiable | implemented | operator-facing adjudication contract |
| error taxonomy / attribution / revision | implemented | append-only review records |
| benchmark version comparison | implemented | temporal manifest + reproducible corpus hash |
| promotion / demotion | conditional | 只生成 pending operator recommendation；永不自动应用 |
| negative archive | implemented | non-hit/unverifiable 进入审查档案 |
| train/test temporal separation | implemented | event/observation/collection time + identity graph |
| leakage prevention | implemented | closed snapshots、dependency hashes、downstream semantic reseal |
| operator review queue | implemented | approved/applied forged reseal fail closed |
| accuracy claim | unsupported | 0 independently qualified real cases；metrics null |

## Runtime 与 Renderer

| 能力 | 状态 | 边界 |
| --- | --- | --- |
| Unified Python runtime | implemented | additive V2 orchestrator；deterministic canonical hash |
| HTTP | implemented | read-only analysis surface、no request storage、no-store |
| MCP | implemented | read-only/idempotent/non-destructive tool annotation |
| Renderer | implemented | Yuan controlled language、single disclaimer、no absolute promise |
| External network/storage | unsupported | runtime 不联网、不持久化 case |
