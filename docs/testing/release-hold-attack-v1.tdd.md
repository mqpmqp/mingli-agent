# Release Hold Attack V1 TDD 证据

## 来源与范围

本轮没有独立的 `*.plan.md`。行为来自 Release Hold 攻防目标：真实个案必须具备有效授权、预测冻结、时间隔离、去标识化与双人审阅；任何指标都不得自动形成准确率声明或解除 Release Hold。

所有测试记录仅用于合约和拒绝路径，不构成真实个案、效果证明或发布依据。

## 用户旅程

1. 作为受控数据操作员，我只能从仓库外读取已授权、去标识化的记录，并把报告写到仓库外。
2. 作为质量审计员，我需要获得规则归因、Reality Evidence、不可验证率及校准诊断，但不产生准确率或发布结论。
3. 作为发布授权人，我需要看到即使阈值满足，结果也仅允许申请独立复审，永远不能自动解除 Hold。
4. 作为隐私与合规负责人，我需要合成、未同意、未冻结或未审阅的输入在写入任何输出前被拒绝。

## RED 证据

初始 RED checkpoint：`8aa5275a5f5b2beac908f28b0c5dc525b42a355c`

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_release_hold_attack_v1.py -q
```

初始结果：`ModuleNotFoundError: No module named 'mingli.release_hold_attack_v1'`。该失败来自目标模块尚未实现，而非语法或依赖故障。

CLI 行为的第二个 RED：

```text
argument command: invalid choice: 'hold-reassessment'
```

该失败证明缺少所需的受控 CLI 子命令；实现后同一测试进入目标拒绝路径。

## GREEN 证据

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_release_hold_attack_v1.py -q
```

结果：`14 passed in 0.28s`

```powershell
$env:PYTHONPATH='src'; python -m coverage erase
python -m coverage run --branch --source=mingli.release_hold_attack_v1 -m pytest tests/test_release_hold_attack_v1.py -q
python -m coverage report --include='*/release_hold_attack_v1.py' --show-missing --fail-under=80
```

结果：`14 passed`；`release_hold_attack_v1.py` 分支覆盖率 `87%`，满足 80% 门槛。

## 测试规格

| # | 保证 | 测试 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | 协议的版本、RC 基线和 canonical hash 均被冻结 | `test_protocol_is_hash_valid_and_pinned_to_the_rc_baseline` | 合约 | PASS |
| 2 | 诊断提供覆盖率与校准数据，但固定禁止准确率声明 | `test_metrics_expose_coverage_and_calibration_without_authorizing_accuracy_claims` | 单元 | PASS |
| 3 | 合成或未完成双人审阅的记录拒绝处理 | `test_synthetic_or_unreviewed_rows_fail_closed` | 负向 | PASS |
| 4 | 分类、同意、冻结、伪匿名、比较状态、置信度、证据层级和规则 ID 的边界均拒绝 | `test_invalid_real_case_metric_boundaries_fail_closed` | 参数化负向 | PASS |
| 5 | 全部阈值满足时也只能申请独立复审，绝不自动发布 | `test_thresholds_only_allow_independent_reassessment_never_automatic_release` | 边界 | PASS |
| 6 | 低指标列出明确 blocker，篡改协议被拒绝 | `test_reassessment_returns_explicit_blockers_and_rejects_a_tampered_protocol` | 完整性 | PASS |
| 7 | CLI 对合成输入返回失败、不写报告且说明原因 | `test_cli_rejects_synthetic_reassessment_input_without_writing` | 集成负向 | PASS |

## 已知边界

- 本提交没有也不会引入真实用户、同意书、反馈、个人标识或可反向识别的 case 数据。
- 合成测试通过不表示任何准确率、校准质量、商业可用性或 Release Hold 状态发生改变。
- 只有合规的场外真实案例与未来反馈，经过独立人工审阅和独立产品授权，才可以触发人工复审；系统继续输出 `release_hold=ACTIVE`。
