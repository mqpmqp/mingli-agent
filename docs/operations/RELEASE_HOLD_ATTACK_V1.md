# Release Hold Attack V1 操作规程

## 目的与不可逾越的边界

本规程用于对已经冻结、具有明确授权且已去标识化的真实个案记录进行覆盖率、不可验证率和校准诊断。其唯一可能的正向结果是“可提交独立复审”；它不是准确率声明、产品发布授权或解除 Release Hold 的机制。

无论任何阈值是否满足，系统都固定输出：

- `release_hold = ACTIVE`
- `prediction_validity = not_evaluated`
- `accuracy_claim_allowed = false`
- `automatic_release = false`
- `requires_independent_authorization = true`

不得把真实个案、身份标识符、授权记录、项目盐、反馈内容或生成的报告写入 Git、测试 fixture、聊天记录或公开文档。合成数据只能用于验证拒绝路径，绝不能作为准确率、校准或发布依据。

## 冻结的协议

- 协议：`src/mingli/derived/data/release_hold_attack_v1_protocol.json`
- 协议版本：`release-hold-attack@1.0.0`
- RC 基线：`b03af9f1a7ee5199f64cdd627dd47f348c761d6e`
- canonical hash：`sha256:a9e523ef8680b73407e36d89656bcdf12aee808cb696a8a54ff1736f2171d934`

协议要求至少 30 位独立个案对象（其中至少 10 位 gold，最多 20 位 silver）、100 条可比较主张、3 个场景、规则归因及 Reality Evidence 覆盖率均不低于 0.8、不可验证率不高于 0.2、至少 100 条校准样本、Brier 不高于 0.25、ECE 不高于 0.1，且双人独立审阅覆盖率必须为 1.0。

这些是申请独立复审的最低门槛，不是对产品效果的认可。

## 受控的场外流程

1. 在受控的场外系统取得书面、可撤回的研究与 benchmark 授权；不要复制授权原件或原始身份数据。
2. 在场外完成不可逆去标识化，保留仅 `person:` 前缀的伪匿名对象 ID；不得提交反向映射或 salt。
3. 记录排盘快照、原始问题、预测时的现实上下文和初始预测，并在确认前事或接收未来反馈前冻结预测。
4. 将前事验证与冻结后的未来结果严格分开；禁止事后改写预测。
5. 两位独立人工审阅者以双盲方式评定，并由独立裁决者处理分歧；为每条可观察主张登记预先注册的规则 ID 与范围匹配的 Reality Evidence ID。
6. 在受控场外存储内执行 Case OS 的撤回、时间分割和泄漏防护；撤回后不得继续纳入任何评估。
7. 仅将经过上述检查的去标识化 JSON 数组放在仓库外的位置，执行命令生成场外报告：

```powershell
mingli-validation hold-reassessment --records D:\controlled\records.json --output D:\controlled\reassessment.json
```

输入与输出路径只要位于 Git checkout 内，命令就会失败；输出使用新文件创建语义，已有文件也会失败，以避免覆盖审计证据。

8. 将报告和底层受控证据交给独立产品授权人。即使报告为 `reassessment_eligible = true`，仍必须获得新的、独立的书面授权；CLI 不提供自动发布或解除 Hold 的路径。

## 拒绝条件

以下任一项会 fail closed，且不会写入输出报告：合成记录、非 `authorized_real_case` 分类、未获同意、预测未冻结、非双人审阅、非伪匿名 ID、不支持的比较状态、无效置信度或非 gold/silver 证据层级。

## 运行后核验

检查生成报告中的 `source_commit_sha`、`protocol_hash` 与上述冻结值相符，确认所有四个边界字段仍为固定值。将报告仅保存在受控场外存储，并通过独立的人类授权流程决定后续动作；Release Hold 在该流程中始终保持 ACTIVE。
