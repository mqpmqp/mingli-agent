# Real Case Learning OS V2 TDD 证据

## Source plan

未提供独立 `*.plan.md`。用户旅程与验收条件直接来自 Workstream C 请求和冻结架构 `MINGLI_CORE_CAPABILITY_SURGE_V2_ARCHITECTURE.md`。

所有测试 fixture 均为明确标记的 synthetic contract fixture；它们不是真实案例，不构成准确率或产品声明证据。

## User journeys

1. 作为数据操作员，我需要在明确同意和不可逆匿名化后建立案例，以便真实身份不进入学习合同。
2. 作为预测审计员，我需要冻结排盘、原问题、预测时现实上下文和初始预测，以便事后信息不能回写预测。
3. 作为结果审阅员，我需要区分先验事件与未来结果，并按 claim/scope 应用 Reality Evidence，以便现实事实不会越界覆盖。
4. 作为规则维护者，我需要记录命中分类、错误分类、规则归因、修订和版本比较，但所有 promote/demote 决策必须由操作员审批。
5. 作为数据集维护者，我需要按事件与观察时间切分 train/test，并将同人、同预测、派生/近重复记录保持在同一分区。
6. 作为隐私负责人，我需要撤回时失效并删除全部依赖，只保留不可反识别 tombstone。
7. 作为发布审核者，我需要确保 synthetic 数据不进入 accuracy/product claims，且 `prediction_validity` 与 ACTIVE Hold 不变。

## RED evidence

Checkpoint：`b48e772e6ae86d67db394f41fdbe7a87d0980d56`

命令：

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_learning_v2.py -q
```

结果摘录：

```text
ModuleNotFoundError: No module named 'mingli.real_case_learning_v2'
ERROR tests/test_real_case_learning_v2.py
1 error in 1.00s
```

测试文件已成功编译；RED 由目标 V2 模块尚不存在这一预期缺失行为导致，不是语法、依赖或测试环境故障。

## GREEN evidence

Checkpoint：`5608f117a9c32bde42bf0317c529629ecab84d5c`

Focused 命令：

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_learning_v2.py -q
```

结果：`17 passed`。

回归命令：

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_learning_v2.py tests/test_real_case_validation_os.py tests/test_product_training_loop.py -q
```

结果：`62 passed`。

## Test specification

| # | 保证 | 测试 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | V2 schemas 可打包读取且测试进入 real_case gate | `test_v2_schemas_are_packaged_and_real_case_gate_classifies_test` | contract | PASS |
| 2 | 同输入生成确定性匿名案例、冻结快照和 canonical hash | `test_intake_anonymization_context_and_prediction_are_frozen_deterministically` | integration | PASS |
| 3 | PII、未知 chart 合同、预测时可见未来现实证据 fail closed | `test_fail_closed_on_pii_unsupported_boundaries_and_prediction_reality_visibility` | negative | PASS |
| 4 | 先验事件必须早于预测，未来结果必须晚于冻结 | `test_prior_event_and_future_outcome_enforce_prediction_time_boundary` | boundary | PASS |
| 5 | Reality Evidence 仅硬覆盖相同 claim 与 scope | `test_future_reality_hard_override_is_claim_and_scope_specific` | integration | PASS |
| 6 | miss 生成负例、修订和待人工降级建议，绝不自动应用 | `test_miss_creates_negative_archive_revision_and_review_only_demotion` | lifecycle | PASS |
| 7 | hit/partial/miss/unverifiable 四类均支持且不自动 promote | `test_all_outcome_classes_are_supported_but_never_auto_promote` | parameterized | PASS |
| 8 | 分区使用事件/观察/收集时间，忽略 ingestion order | `test_temporal_partition_uses_event_and_observation_time_not_ingestion_order` | partition | PASS |
| 9 | 重复组件跨 cutoff 时由 test 优先，结果与输入顺序无关 | `test_person_prediction_window_fingerprint_and_near_duplicates_cannot_cross_partitions` | leakage | PASS |
| 10 | cutoff 后才能获得的观察不会进入 train | `test_observation_after_cutoff_stays_test_even_when_event_window_ends_before_cutoff` | leakage | PASS |
| 11 | 撤回仅返回 tombstone，并递归失效所有依赖 | `test_withdrawal_returns_only_tombstone_and_invalidates_all_dependencies` | privacy | PASS |
| 12 | synthetic 合同记录不产生 accuracy metrics 或 product claims | `test_synthetic_contract_records_never_become_accuracy_or_product_claim_evidence` | claims | PASS |
| 13 | 冻结记录被修改后 canonical verification 失败 | `test_tampering_breaks_canonical_verification` | integrity | PASS |
| 14 | 非法裁决状态和有泄漏的 benchmark comparison fail closed | `test_invalid_adjudication_and_leaky_benchmark_comparison_fail_closed` | negative | PASS |

## Coverage and quality gates

Coverage 命令：

```powershell
$env:PYTHONPATH='src'; python -m coverage erase
python -m coverage run --branch --source=mingli.real_case_learning_v2 -m pytest tests/test_real_case_learning_v2.py -q
python -m coverage report --include='*/real_case_learning_v2.py' --show-missing --fail-under=80
```

结果：focused module branch coverage `80%`，阈值通过。

其他命令与结果：

```text
python -m ruff check ...                                    -> All checks passed!
python -m compileall -q ...                                 -> PASS
python -m mingli.contracts.freeze --root .                  -> ok=true, checked_count=78, violations=[]
git diff --check                                            -> PASS
```

## Known boundaries

- V2 只产生 review candidates，不实现人工审批后的规则写入。
- V2 不在 Git 内创建真实案例 store；真实存储继续由既有 TrainingStore 的 off-Git 边界负责。
- V2 不计算或宣称真实准确率；独立、冻结、合规真实数据集的授权流程不属于本工作流。
- Release Hold 保持 ACTIVE，`prediction_validity=not_evaluated`。
