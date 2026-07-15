# Real Case Validation Protocol v1.0.0

状态：`FROZEN_BEFORE_REALITY_IMPORT`

基线：`v2.0.0` / `393c9ff791d0091176ea8dcba5f50b8ddde6fbd9`

冻结时间：`2026-07-15T00:00:00+08:00`

Canonical hash：`sha256:1859fdc5ab61b0f6acc8bdee08c997b8eb7caaf8756327fc774b61d544d71d38`

## 预登记指标

Primary metric 为 Gold 案例的 person-weighted strict score。Secondary metrics 包括 claim-weighted strict/lenient score、person-weighted lenient score、Brier score、ECE、覆盖率、拒答率、reviewer agreement、adjudication rate，以及按场景、领域和 Gold/Silver 分层的结果。`partially_supported` 在 strict score 中不算完整命中，在 lenient score 中按 0.5；`not_comparable`、`insufficient_evidence` 和 `excluded_by_contract` 不计入命中。

## 纳入与排除

只纳入取得研究与 benchmark 授权、完成去标识、出生输入已确认、预测在现实证据揭示前冻结、现实证据有独立 provenance 且完成人工盲评的真实人员。合成、Bronze、已撤回、预测后补、含 PII 或未完成审查的记录不得进入正式 frozen dataset。

Gold、Silver 与人员级冲突处理沿用 Phase 22 R2，不降低阈值。相同 `person_case_id` 只计一人；全 Gold 为 Gold，全 Silver 为 Silver，Gold/Silver 冲突保守归 Silver并使 closure 失败。

## 场景与评分

至少覆盖三个场景。考公考编的体制适配、上岸、考试趋势、岗位方向、备考策略分别评分；感情复合的缘分牵引、复联、复合、稳定分别评分。可比较 claim 必须在 prediction snapshot 冻结时登记，并有时间窗、方向、现实证据和可证伪定义。

Gold claim 原则上由两名独立人类 reviewer 评分；分歧进入独立 adjudicator。Silver 至少一名人类 reviewer。LLM 只能辅助格式检查，不得作为唯一最终 reviewer。

## 门禁

Validation closure：唯一人员不少于 30、Gold 不少于 10、Silver 不超过 20、可比较 claims 不少于 100、至少三个场景、review/privacy 均通过且无人员 tier 冲突。Accuracy claim 独立要求不少于 30 个 Gold 唯一人员。产品发布还必须有引用当前冻结 dataset 的独立 `approved` 授权，且 P1/P2 为 0、privacy/package/main CI 门禁全部通过。

协议变更必须增加版本并重新冻结，不得追溯应用于已解盲数据。
