# Commercial Validation Gate

Commercial Validation Gate 与 Product Readiness Gate 独立。开发链可运行，不等于可商业化，也不等于准确率已验证。

## 必须满足的证据

商业化前至少需要：

1. 明确授权且去标识的真实案例集；未经授权案例计数恒为零；
2. 结果发生前冻结的结构化 claims、版本、输入 manifest 与现实证据不可见边界；
3. 可证明的 event_time、observed_at 和 outcome 时间顺序；
4. 独立审查/评分，预测生成者不能自评分；
5. 泄漏检测，已知历史事件不得进入事前预测输入；
6. 可复现 frozen dataset benchmark；
7. 准确率、分层样本量、失效模式、不确定性和 exclusions 报告；
8. 产品、隐私、法律与商业风险审批。

只有 independently verified 且引用 preregistered claim 的 outcome 才能标记为“可能具备商业验证资格”；该标记仍不等于已纳入 benchmark。最终纳入必须由 validation dataset/freeze/review/authorization 流程决定。

## 明确不计入

- 用户总体评分或“觉得准”；
- clarity、actionability、useful sections；
- 历史事实纠正；
- 未冻结的后续叙述；
- 未授权、无法证明来源或有泄漏风险的案例；
- synthetic/anonymized fixtures；
- Training Loop 自动生成的规则候选。

因此当前状态保持 `COMMERCIAL_VALIDATION_PENDING`，`production-commercial=false`，旧字段保持 `PRODUCT_RELEASE_HOLD`。本轮没有运行真实案例准确率 benchmark，也没有生成准确率数字。
