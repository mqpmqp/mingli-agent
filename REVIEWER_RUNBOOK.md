# Reviewer Runbook

1. 确认 assignment、blind mode 与 reviewer 身份；不得查看不必要的身份信息。
2. 校验 prediction snapshot 为 frozen、hash 可重算且生成时间早于 reality evidence。
3. 只评分 snapshot 中预登记的 claims。宽泛性格套话、无时间边界、不可证伪内容、免责声明与建议标为 `not_comparable` 或 `excluded_by_contract`。
4. 对每条 claim 选择 `supported`、`partially_supported`、`contradicted`、`not_comparable`、`insufficient_evidence` 或 `excluded_by_contract`，并引用现实证据。
5. Gold 需要两名独立人类 reviewer，Silver 至少一名。原预测生成者不能是唯一 reviewer；LLM 不能是唯一最终 reviewer。
6. Reviewer 分歧必须由独立 adjudicator 裁决，保留两份原始评分、原因、时间与 provenance，不覆盖历史记录。
7. 考公五层和复合四层分别评分，不得合并为主观总分。
8. 完成后运行 reviewer coverage 和 dataset manifest 验证。发现 PII、预测事后修改、证据冲突或潜在泄盲时停止并记录 blocker。
