# 咨询记录模板 V1

仅保存经授权、最小化且去标识化的信息；不得填写真实示例 PII。

```text
case_id:
consultation_date:
channel:
service_tier:
payment_status:
birth_data_precision:
chart_confirmation_status:
core_question:
reality_context:
information_completeness:
initial_confidence:
engine_version:
rule_version:
knowledge_version:
renderer_version:
initial_output:
output_hash:
prediction_frozen_at:
explanation_method_and_duration:
immediate_feedback:
follow_up_events:
error_classification:
reviewer_assessment:
consent_scope:
training_eligibility:
withdrawal_status:
final_case_status:
```

初始输出和 hash 是追加式审计边界；反馈、复核和撤回不得覆盖它们。
