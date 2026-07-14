# P22 Case Qualification Contract

## Evidence tiers

每条记录必须显式声明 `evidence_tier`，且只能取 `gold`、`silver` 或 `bronze`。

### Gold

Gold 必须同时满足：

- `prospective_prediction=true`；
- 观察结果产生前已经冻结预测，并保存不可变的 `prediction_freeze_hash`；
- `prediction_frozen_at < observed_at`；
- 预测者不能看到观察标签，观察标注者不能修改预测；
- 两名独立评审者完成盲评，分歧必须进入裁决；
- 明确同意、完成去标识并具有外部观察证据。

Gold 可计入 validation closure，也可计入 product accuracy claim gate。

### Silver

Silver 是具有外部证据支持的回顾性案例。它仍须满足明确同意、去标识、独立来源与双人评审，但不满足“观察前冻结预测”的前瞻性条件。

Silver 只能计入 validation closure 和辅助指标，不能计入产品准确率声明，不能用于把 `product_accuracy_claim_allowed` 设为 `true`。

### Bronze

Bronze 包括缺少必要外部证据、同意、去标识、可靠时间顺序或独立评审的记录。Bronze 必须保留排除原因，永不计入 benchmark、validation closure 或产品准确率声明。

## Public repository boundary

GitHub 只允许提交 schema、空模板、不可逆案例 ID、冻结哈希摘要和聚合指标。以下内容不得提交：原始 PII、同意书、聊天记录、身份证明、联系方式、精确地址及可重新识别个人的原始叙述。

每个可计数案例必须使用一个不可逆 `person_case_id`。同一人的多个场景记录只增加 `qualified_scenario_records`，不能重复增加 `unique_person_cases` 或 `qualified_validation_cases`。
