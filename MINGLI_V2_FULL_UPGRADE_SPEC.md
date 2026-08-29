# 命理师 V2.0 付费交付与评测体系升级规范

版本：`mingli-v2-full-upgrade@1.0`
日期：2026-08-29
状态：本地实现合同；不代表生产发布、实盘有效性或准确率授权

## 1. 目标与边界

本升级在现有单体 Python package 内新增一条独立、确定、现实优先的付费交付路径。它不改写 Phase 23 的兼容入口，不接触 Hermes、Telegram、PWA 业务代码、`spec/`、`knowledge/`、真实用户资料、交易项目或生产服务。

核心不变量：

- 默认问题意图仍为 `focused_question`。
- `paid_699` 使用九项交付合同，但不调用旧的固定八段 Renderer，也不机械展开全部主题。
- 已核验现实资料优先于命盘结构、规则或传统象意。
- 四维置信度只使用 `high`、`medium`、`low`，不输出未经校准的概率。
- 称骨相关计算与字段默认不进入新路径；只有调用方在确认用户明确点名后设置 `bone_weight_requested=true` 才能启用。
- 六爻只有输入合同，没有可靠引擎；收到六次结果也必须返回显式降级，不能补写卦象。
- 只有 `production` 规则可进入本路径，其他生命周期状态全部隔离。
- 所有建议都必须同时给出现实动作、频次上限、预算上限、禁用宣称和诈骗红旗。

## 2. 目标架构与代码映射

```text
CaseInput
  -> InputValidation
  -> DeterministicRuntime
  -> RealityConstraints
  -> DomainRouter
  -> EvidenceAndRuleRetrieval
  -> ConfidenceAndCounterEvidence
  -> RealityAdviceAndMetaphysicalAdvice
  -> Comment/Private/PaidRenderer
  -> EvaluationReceipt
```

| 架构节点 | 本地实现 |
|---|---|
| CaseInput / InputValidation | `mingli.delivery_contracts` |
| DeterministicRuntime | `mingli.paid_delivery` 调用现有 `DeterministicBaziEngine`；图片确认盘只保留静态边界 |
| RealityConstraints | `RealityConstraints.facts`，白名单与未知字段 fail closed |
| DomainRouter | `QuestionIntent.domain` 的九类固定枚举 |
| EvidenceAndRuleRetrieval | `mingli.rule_governance` 的 production-only 规则选择 |
| ConfidenceAndCounterEvidence | `build_confidence_profile` 与领域现实反证提取 |
| RealityAdviceAndMetaphysicalAdvice | 现实行动模板与 `AdviceRule` 匹配 |
| Comment/Private/PaidRenderer | `run_paid_delivery` 的三档输出与续问短合同 |
| EvaluationReceipt | 交付时生成 `pending_forward_test` 收据；到期结算由 `mingli.forward_evaluation` 执行 |

## 3. 统一输入合同

### 3.1 CaseInput

`CaseInput` 固定包含：

- `case_id`：假名化或合成 case 标识；
- `created_at`：带时区 ISO-8601 时刻；
- `anchor_year`：本次阅读锚点；
- `paid_tier`：`comment`、`private`、`paid_699`；
- `question_intent`：问题、专题、展示意图、称骨显式开关；
- `birth`：可缺失；缺失时降级；
- `divination`：可缺失；存在时校验六次结果并标记引擎不可用；
- `reality_constraints`：结构化现实事实；
- `evidence_quality`：`unknown`、`self_reported`、`documented`、`verified_reality`；
- `review_checkpoint`：复盘 ID、到期时刻与核对标准。

### 3.2 BirthInput

完整出生资料路径校验性别、历法、日期、时刻、时区、出生地点、真太阳时开关、闰月和 DST fold。真太阳时开启但缺经度时必须降级。

图片或文字四柱路径要求：

- `source` 为 `image_confirmed` 或 `text_confirmed`；
- `confirmation_status` 必须为 `confirmed` 才能进入静态事实；
- 年、月、日、时四柱必须为合法六十甲子；
- 未确认图片不进入时点推断；
- 即使确认，也不从四柱反推出生日、时刻、地点、真太阳时或大运时间线。

### 3.3 DivinationInput

六爻输入必须包含：

- 六个整数结果，每项只允许 6、7、8、9；
- 带时区的起卦时刻；
- 起卦地点；
- 目标事件。

当前固定返回 `liuyao_engine_unavailable`。这是能力边界，不是输入错误。

### 3.4 RealityConstraints

现实字段覆盖感情状态、失联时长、对方婚姻/新人、双方意愿、家庭与安全边界；考试成绩、模考名次、岗位和招录目标；财务现金流；健康症状和医疗评估；户型与测量；迁移和技能准备。未知字段不会静默进入规则选择。

## 4. 自动降级

| 条件 | 运行状态 | 置信度影响 | 禁止行为 |
|---|---|---|---|
| 缺出生时刻、地点或时区 | `degraded` | 四维均不得高 | 不补写命盘与时间 |
| 图片四柱未确认 | `degraded` | `chart_confidence=low` | 不进入静态或时点判断 |
| 已确认四柱但缺出生元数据 | `degraded` | 只承认静态结构 | 不推导起运与时间线 |
| 提供六爻资料 | `degraded` | 六爻部分低 | 不伪造断卦 |
| 非 production 规则 | 不进入选择结果 | 解释置信度降级 | 不进入付费生产路径 |
| 强现实反证 | 现实边界覆盖 | 事件与行动置信度降级 | 不用象意覆盖现实 |

## 5. 九类专题规则包

| domain | 必要判断层 |
|---|---|
| `finance` | 现金流、守财边界、收入与风险、现实行动 |
| `relationship` | 缘分牵引、复联可能、复合可能、稳定可能 |
| `exam_education` | 基础成绩、考试状态、学习策略、文昌辅助 |
| `civil_service_and_public_institution` | 体制适配度、上岸可能、考试运、岗位方向、备考策略、文昌与功名辅助 |
| `career` | 岗位匹配、发展矛盾、面试签约、现实行动 |
| `health` | 症状边界、医疗优先、作息压力、安康辅助 |
| `fengshui` | 资料完整度、居住问题、安全布局、复核条件 |
| `migration` | 目标地区、签证资格、语言与预算、迁移节奏 |
| `art_and_skill` | 技能基础、练习反馈、作品路径、阶段复盘 |

每条新增规则必须提供 `source_refs`、`status`、`applicability`、`counterexamples` 和 `review`。这里的 `production` 表示已通过本地安全与交付合同，可被运行时选择；它不表示术数有效性获得实证证明。

## 6. 渲染合同

- `comment`：简要结论和现实提醒；
- `private`：资料、结论、行动、辅助、风险复盘；
- `paid_699`：九项合同，详见 `PAID_DELIVERY_CONTRACT.md`；
- `follow_up`：优先进入短合同，不重复完整付费报告；
- `full_reading`：在新付费路径中仍使用九项合同，不回退旧八段；旧 Phase 23 兼容路径保持原状。

所有文本仅出现一次固定免责声明，且位于末行。输出必须通过现有禁词扫描。

## 7. 规则与评测生命周期

固定生命周期：

```text
raw -> draft -> reviewed -> pending_forward_test -> production
                       \-> rejected
```

代码不自动执行上述升级。`production_rules` 只过滤已明确为 `production` 的规则，遇到未知状态直接失败。作者自称命中、付款截图和未到期 forward test 不能成为结算依据。

## 8. 确定性与可审计性

- 同一规范化输入生成相同的 Runtime、交付与评测 canonical hash；
- 证据链只记录 chart/runtime、现实资料摘要和规则 hash；
- 交付收据初始状态为 `pending_forward_test`，结果为 `null`；
- 到期前调用结算固定报错 `FORWARD_TEST_NOT_MATURE`；
- 无反馈、坏输入和无效预测不计入准确率。

## 9. 未实现与冻结范围

- 未实现六爻算法、外部排盘、LLM 生成、仪式下单、支付或真实用户资料接入；
- 未修改 Phase 23、Phase 19、旧八段 Renderer 或旧规则状态；
- 未改 `spec/`、`knowledge/`、Hermes/Telegram、PWA 功能或任何交易项目；
- 未部署、未推送、未创建 PR、未修改生产环境；
- 未产生任何实盘准确率、商业发布或医疗效果声明。
