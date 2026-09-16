# Consumption V1：人工批准训练资产的受控消费

## 目标

Consumption V1 解决 REVIEW/人工批准后的结构化训练资产如何进入后续实盘检索的问题。它不修改模型权重，不改变 Real Case Learning V2 的准确率声明，也不绕过现有规则发布与 Phase 4.1 Release Hold。

固定链路：

`REVIEW asset -> human decision -> published consumption asset -> exact-match retrieval -> audit receipt`

## 资产门禁

- domain 仅允许 `bazi`、`qimen`、`fengshui`。
- REVIEW 阶段必须有 `scenario`、`topic`、`source_case_ids` 和结构化 `content`。
- outcome 支持 `VERIFIED_HIT / PARTIAL_HIT / FAILURE / UNVERIFIED / CONTAMINATED / INPUT_ERROR`。
- 人工决定通过不可变 approval receipt 绑定精确 `review_hash`。
- 发布时只认同一 `review_hash` 的**最新**人工决定。
- 同一 REVIEW 使用确定性 `asset_id`，原子创建保证即使并发请求也只能成功发布一次。
- 如果发布后最新人工决定变成 `rejected`，该资产立即失去检索资格；重新 approved 后仍以最新人工决定为准。
- 如果任一 `source_case_id` 已产生 `CONSENT_WITHDRAWN` tombstone，REVIEW、发布和后续检索均 fail closed；已发布资产保留审计记录但不再返回。
- `UNVERIFIED / CONTAMINATED / INPUT_ERROR` 可归档，但永远不进入检索上下文。

## 检索规则

检索必须精确匹配 `domain + scenario + topic`，禁止跨 domain、跨 scenario 或跨 topic 放宽。每次检索前重新验证：最新人工决定仍为 approved，且来源案例未撤回。

返回上限：

- VERIFIED_HIT：最多 3 条；
- PARTIAL_HIT：最多 2 条，仅作边界学习；
- FAILURE：最多 2 条，仅作风险提醒，不直接模仿。

无匹配、缺标签、批准被撤销或来源案例撤回时返回 `NO_HISTORICAL_CONTEXT`，不得回退到不相关历史案例。

每次检索写入 `consumption_audit.jsonl`，记录 query、domain/scenario/topic、mode、实际选中的 asset IDs 和时间。

## SHADOW 与 ACTIVE

默认 `SHADOW`。`SHADOW` 允许检索、记录审计和验证上下文质量，但不代表线上回答已经受其影响。

`ACTIVE` 只是显式消费模式标记，不会自行改变模型权重、规则版本或 Phase 4.1 结论。是否把返回 context pack 注入某个上层推理器，必须由调用方明确实现和审计。

## CLI

入口：`mingli-consumption`

```text
mingli-consumption --store <off-git-store> --repository-root <repo> stage-review --input review.json
mingli-consumption --store <off-git-store> --repository-root <repo> decide --input decision.json
mingli-consumption --store <off-git-store> --repository-root <repo> publish --input publish.json
mingli-consumption --store <off-git-store> --repository-root <repo> retrieve --domain bazi --scenario career_exam --topic civil_service_exam --query-id q1 --consumed-at 2026-09-16T08:30:00+00:00 --mode SHADOW
mingli-consumption --store <off-git-store> --repository-root <repo> status
```

## 现有 MingLi Integrated Runtime

`mingli-integrated-service` 保持原服务名、端口、OAuth 资源与 off-Git `MINGLI_TRAINING_STORE`，并在同一 MCP 上增加：

- `stage_consumption_review_asset`
- `decide_consumption_review`
- `publish_consumption_asset`
- `retrieve_training_context`
- `get_consumption_status`

OAuth 权限固定分离：

- `stage_consumption_review_asset`：`training:write`
- `decide_consumption_review` / `publish_consumption_asset`：独立 `training:approve`
- `retrieve_training_context` / `get_consumption_status`：`training:read`

因此现有自动小时训练即使持有 `training:write`，也不能自行批准或发布 Consumption 资产。非 OAuth 本地测试同样使用独立 `MINGLI_CONSUMPTION_APPROVAL_TOKEN`，不得复用采集 token。

所有会产生新记录或审计的 Consumption 工具均标记为非幂等，避免 MCP 客户端自动重试导致重复记录。

## 与现有链路关系

- `TrainingStore`：继续作为仓库外私有存储边界和 consent tombstone 来源。
- `Real Case Learning V2`：继续负责预测冻结、现实证据与 outcome 分类；不自动 promote。
- `RulePromotionPipeline`：继续负责规则来源审核、回归、人工批准、release；不被 Consumption 替代。
- `Phase 4.1`：继续用于真人试点验证；Consumption 资产不自动计入 Phase 4.1 accuracy。
- `RuleAwareRuntime`：受控 `retrieve_training_context()` 默认 SHADOW，并暴露 Consumption 状态。

## 安全边界

Consumption V1 不自动批准、不自动发布、不跨域召回、不把训练反馈等同准确率、不把失败样本当示范答案。生产部署和切换 ACTIVE 必须单独审批；本次部署目标固定为 SHADOW。
