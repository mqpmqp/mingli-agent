# Case OS V2 裁决命令 TDD 证据

## 用户旅程

受控审查员以场外的 future-outcome 快照和冻结的无泄漏 temporal partition 为输入，
创建一份 case adjudication 快照。该操作必须归档 miss、保留 revision 与 rule
recommendation 为 `pending_operator_review`，而不是自动改变规则或解除 Hold。

## RED

Checkpoint：`668778c`。

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_cli.py -q --basetemp .pytest-case-adjudication-red
```

结果：`1 failed, 5 passed`。`case-adjudicate` 尚未注册，错误为
`invalid choice: 'case-adjudicate'`。

## GREEN

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_cli.py tests/test_release_hold_attack_v1.py tests/test_validation_astro_etl.py -q --basetemp .pytest-case-adjudication-cov --cov=mingli.validation_cli --cov-report=term-missing
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_learning_v2.py -q --basetemp .pytest-real-case-v2-adjudication
$env:PYTHONPATH='src'; python -m pytest tests/test_product_training_loop.py -q --basetemp .pytest-training-adjudication
python -m compileall -q src/mingli
git diff --check
```

结果：CLI 组合 `26 passed`、覆盖率 `85%`；Case OS V2 `54 passed`；TrainingStore
`17 passed`；编译与差异空白检查通过。

| 保证 | 测试 | 结果 |
|---|---|---|
| 裁决请求必须绑定存在的未来证据、test partition 与一致的案例依赖 | `test_case_os_cli_keeps_external_snapshots_append_only_after_start` | PASS |
| miss 形成负样本归档和人工审查中的 demote 建议 | 同上 | PASS |
| 审查队列仅列出建议，`automatic_actions_applied` 恒为 0 | 同上 | PASS |
| 撤回从裁决后的独立快照生成 tombstone，Hold 保持 ACTIVE | 同上 | PASS |

## 已知边界

- 测试仅使用清晰标注的合成合同 fixture，不存在真实用户、真实反馈或准确率证明。
- 本命令不会执行人工裁决本身、规则升降级、发布、tag、PyPI 上传或 Hold 解除。
