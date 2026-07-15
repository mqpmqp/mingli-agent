# Real Case Validation Report

```yaml
report_status: REAL_CASE_VALIDATION_SYSTEM_READY_DATA_COLLECTION_REQUIRED
validation_system: complete_local_verified
dataset_id: null
dataset_frozen: false
collection_period: null
unique_person_count: 0
gold_unique_person_count: 0
silver_unique_person_count: 0
bronze_count: 0
comparable_claims_count: 0
scenario_coverage: []
review_coverage_passed: false
privacy_coverage_passed: false
validation_closure_passed: false
product_accuracy_claim_allowed: false
prediction_validity: not_evaluated
product_release_status: PRODUCT_RELEASE_HOLD
```

当前仓库没有用户提供的授权私有真实案例。合成 fixture 只验证合同，不能计入人数、claims、指标或发布授权。因此 coverage、supported/partial/contradicted rate、reviewer agreement、adjudication rate、Brier score、ECE、Gold/Silver、person/claim weighted 与 strict/lenient metrics 均不可计算。

达到 validation closure 仍缺 30 个合格唯一人员，其中至少 10 个 Gold、不超过 20 个 Silver、至少 100 个可比较 claims 和三个场景。真实数据必须通过 Git 外受控 store 导入、冻结与人工盲评。

## 技术验证摘要

- pytest：219 passed、1 skipped、24 subtests passed。
- unittest：210 tests OK、1 skipped。
- P12–P24：源树与隔离 wheel 全部 benchmark `failed=0`；P22 真实案例数保持 0。
- build：wheel 与 sdist 成功；wheel 含 13 个 schema、23 个 JSON data 文件，无真实案例原始资产、无歌诀资产。
- source/wheel parity：P12–P16、P19、P24 canonical hashes 全部一致。
- privacy/package scan、`pip check`、修复工具链后的 `pip-audit`、`git diff --check` 与 protected-path 检查通过。
- 当前 placeholder manifest 不是 frozen dataset，`verify-dataset` 按设计返回 false；这不是测试失败，而是防止空数据解除 HOLD 的门禁结果。
