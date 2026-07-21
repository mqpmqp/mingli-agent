# 内部 Beta 案例闭环

本说明仅适用于 Git checkout 外的受控案例存储。它不代表产品准确率、商业可用性或解除发布限制的授权。

## 固定状态

- `prediction_validity=not_evaluated`
- `commercial_release_hold=ACTIVE`
- `commercial_validation_eligibility=false`
- `product_accuracy_claim=prohibited`

工程完成或内部 Beta 就绪不会改变以上任一状态。合成 fixture、测试通过、性能 benchmark 和用户满意度都不能作为准确率证据。

## 案例分类与资格

`case_classification` 必须是以下之一：

- `development_case`：可作为未来规则改进候选，但仍须经过人工审查与回归测试。
- `blind_evaluation_case`：预测冻结后不得由结果回写原预测，不能混入开发指标。
- `test_fixture`、`synthetic_case`：必须标记为 `synthetic=true`，只用于工程合同测试，永不计入真实案例数。
- `imported_historical_case`：须有可核验来源、授权和事件证据；不能替代事前冻结的盲测证据。

未获研究与 benchmark 同意、未完成匿名化、已撤回、或包含 PII 的记录一律不能进入训练、benchmark 或商业验证路径。撤回生成独立 tombstone；原预测、反馈、审查和每次修订仍保留不可篡改的审计关联。

## 生命周期和审计字段

`case-start` 冻结原始问题、排盘快照、预测时现实上下文、原始输出、输出哈希和 chart/rule/knowledge/runtime 版本。预测冻结完成后才可写入即时反馈或后续事件；这些记录是追加快照，不能覆盖原始输出。

`case-adjudicate` 追加人工审查、错误分类、版本化 revision、规则归因和 test-partition 比较。验证等级由冻结证据与人工审查导出为 `not_yet_verifiable`、`evidence_collected` 或 `human_review_pending`；系统不会自动标记 `verified`。

支持的错误分类包含：`deterministic_chart_error`、`input_precision_insufficient`、`reality_context_missing`、`rule_misapplication`、`unsupported_claim`、`vague_or_non_falsifiable`、`post_hoc_interpretation`、`incorrect_prediction`、`partially_supported`、`not_yet_verifiable` 和 `user_satisfaction_only`。事实反馈与满意度必须分开；“很准”不能自动构成命中事件。

## 受控操作

```powershell
python -m mingli.cli validation case-inspect --case D:\controlled\case-frozen.json
python -m mingli.cli validation case-summary --cases D:\controlled\cases.json
python -m mingli.cli validation case-export-review-pack --cases D:\controlled\cases.json --output D:\controlled\review-pack.json
python -m mingli.cli validation case-hold-status
```

`case-inspect` 只读显示冻结输出、哈希和版本；`case-summary` 仅报告分类数量，不计算准确率；`case-export-review-pack` 输出去标识人工审查包，移除人员标识和同意记录引用；`case-hold-status` 始终显示当前 Hold。输入和输出均会拒绝 checkout 内路径，写入使用新文件模式，避免覆盖冻结快照。

每累计 10 个开发案例，操作员必须执行：收集 → 冻结预测 → 接收反馈 → 分类证据 → 人工审查 → 提议规则变更 → 添加回归测试 → 运行门禁 → 创建新的规则版本。真实案例在持续内测中逐步积累，不是本轮工程完成的前置条件。

## 解除 Hold 的人工门槛

只有独立授权人可依据当前冻结、可复现且合规的真实数据集进行人工复审。要求和统计口径见 `VALIDATION_PROTOCOL.md`、`COMMERCIAL_VALIDATION_GATE.md` 与 `PRODUCT_RELEASE_HOLD_DECISION.md`；本 CLI 不提供解除 Hold、发布、推送或准确率声明的功能。
