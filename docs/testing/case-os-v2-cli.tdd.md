# Case OS V2 起始命令 TDD 证据

## 范围

本轮补齐受控操作员的 Case OS V2 起始命令。它只从 Git checkout 外读取
去标识化的起始负载，并将不可替换的案例快照写入 checkout 外。所有测试
fixture 均明确标记为合成合同数据，绝不构成真实案例、准确率或商业就绪证据。

## 用户旅程

受控操作员从场外 JSON 创建一个 prediction-frozen Case OS V2 快照；任何
工作树内路径、字段形状不完整或 synthetic 来源伪装为真实案例的请求必须在
写入前失败。

## RED

Checkpoint：`7da13a2`。

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_cli.py -q
```

结果：`1 failed`。`case-start` 尚未注册，错误为 `invalid choice: 'case-start'`。

## GREEN

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_cli.py tests/test_release_hold_attack_v1.py tests/test_validation_astro_etl.py -q --basetemp .pytest-validation-cli-tmp --cov=mingli.validation_cli --cov-report=term-missing
python -m compileall -q src/mingli
git diff --check
```

结果：`25 passed`；`validation_cli.py` 覆盖率为 `83%`；编译与差异空白检查通过。

| # | 保证 | 测试 | 结果 |
|---|---|---|---|
| 1 | 精确的 V2 起始字段只会生成 `prediction_frozen` 的场外快照 | `test_case_start_cli_writes_only_an_external_frozen_contract_fixture` | PASS |
| 2 | checkout 内输出路径被拒绝且不写文件 | `test_case_start_rejects_a_checkout_output_without_writing` | PASS |
| 3 | synthetic 来源不能被重标为真实案例 | `test_case_start_fails_closed_when_synthetic_provenance_is_relabelled_real` | PASS |
| 4 | 缺失或额外字段在写入前失败 | `test_case_start_rejects_an_unsealed_payload_shape_without_writing` | PASS |
| 5 | 合同 fixture 可从场外执行隐私扫描 | `test_case_start_operator_can_privacy_scan_an_external_contract_fixture` | PASS |

## 已知边界

- 不读取、不写入真实用户资料、授权记录、salt 或反馈。
- `commercial_release_hold` 仍固定为 `ACTIVE`。
- 本命令不产生准确率主张、规则自动升降级、发布、标签或 PyPI 上传。
