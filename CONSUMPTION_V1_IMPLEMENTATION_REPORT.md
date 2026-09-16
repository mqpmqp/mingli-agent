# Consumption V1 Implementation Report

## CURRENT_STATE

基线 `main@e4a0ad242e526f00aab92e637f277f6acae570f2` 已具备 TrainingStore、小时训练采集、来源门禁、合同回归、人工规则批准/发布、RuleAwareRuntime 与 Phase 4.1 真人案例 intake。Real Case Learning V2 仍明确停在 review candidate，不负责人工批准后的训练案例消费。

## VERIFIED_FACTS

- 真实 TrainingStore 必须位于 Git 仓库外，并执行 PII 门禁。
- 现有规则发布链已经 fail-closed：来源审核、回归、人工 approval、release 缺一不可。
- Phase 4.1 保持 `prediction_validity=not_evaluated` 与商业 Release Hold。
- 原基线没有“已人工批准训练案例 -> 同域检索 -> 消费审计”的一等链路。

## IMPLEMENTATION

新增 `ConsumptionV1`，使用同一个 off-Git TrainingStore 根目录保存：

1. immutable REVIEW asset；
2. immutable human approval/rejection receipt；
3. immutable published consumption asset；
4. append-only consumption audit。

发布只接受精确 review hash 的最新人工决定，后续 rejection 会使旧 approval 失效。

检索严格按 `domain + scenario + topic` 精确匹配。最多返回 VERIFIED_HIT 3、PARTIAL_HIT 2、FAILURE 2；UNVERIFIED、CONTAMINATED、INPUT_ERROR 永不进入消费上下文。无匹配返回 `NO_HISTORICAL_CONTEXT`，不跨域回退。

FAILURE 在返回 contract 中固定为 `risk_warning_only_do_not_imitate`，PARTIAL 只作边界学习。

## RUNTIME / MCP

- `RuleAwareRuntime` 新增 `retrieve_training_context()`，默认读取 `MINGLI_CONSUMPTION_MODE`，缺省为 `SHADOW`。
- `TrainingReportCollector.status()` 新增 Consumption 状态，但训练自动化仍无自动批准/发布权限。
- 新增 `mingli-consumption` CLI。
- 新增独立、受认证的 `mingli-consumption-service` MCP，提供 stage review、显式人工 decision、publish、retrieve、status 五个工具。
- `decide_consumption_review` 的工具说明明确要求只有获得用户/人工明确决定后才能调用。

## SAFETY BOUNDARIES

- 不修改模型权重。
- 不把训练反馈等同于准确率。
- 不自动批准或发布。
- 不把 Consumption 资产计入 Phase 4.1 accuracy。
- 不自动切换 ACTIVE。
- 不部署生产，不修改生产数据。
- 不改变 `spec/` 和 knowledge source assets。

## TESTS

新增专项测试覆盖：标签门禁、拒绝不可发布、后续拒绝撤销旧批准、UNVERIFIED 不召回、同域/同场景/同主题检索、3/2 数量上限、跨域/跨场景/跨主题 fail-closed、审计写入、MCP 鉴权以及 MCP 端到端 REVIEW -> approval -> publish -> SHADOW retrieve。

最终验收以 PR #62 的仓库 CI（compile / fast / real-case / benchmark）为准；未完成的 CI 不应被描述为通过。

## DEPLOYMENT_BOUNDARY

本分支只完成代码、测试、文档和 PR。合并到 main、部署到 VPS、把 `MINGLI_CONSUMPTION_MODE` 改为 ACTIVE、批量导入真实历史资产都属于后续高影响动作，必须单独获得明确授权。
