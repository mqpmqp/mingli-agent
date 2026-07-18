# Case OS Checkout 根目录边界 TDD 证据

## 用户旅程

受控操作员可以从场外存储目录运行命令；无论当前工作目录为何，Case OS、验证
store 和 Hold reassessment 都不得把真实或去标识化的记录写回源码 checkout。

## RED

Checkpoint：`db71ec5`。

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_cli.py -q --basetemp .pytest-cwd-escape-red
```

结果：`1 failed, 6 passed`。当工作目录是场外临时目录时，`case-start` 错误地接受
checkout 内输出并返回 `0`。

## GREEN

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_cli.py tests/test_release_hold_attack_v1.py tests/test_validation_astro_etl.py -q --basetemp .pytest-checkout-root-cov --cov=mingli.validation_cli --cov-report=term-missing
python -m compileall -q src/mingli
git diff --check
```

结果：`27 passed`；`validation_cli.py` 覆盖率 `86%`；编译和差异空白检查通过。

| 保证 | 测试 | 结果 |
|---|---|---|
| 默认从 checkout 调用时，checkout 内的 Case OS 输出被拒绝 | `test_case_start_rejects_a_checkout_output_without_writing` | PASS |
| 从场外受控目录调用时，checkout 内输出仍被拒绝且不写入 | `test_case_start_rejects_a_checkout_output_when_called_from_controlled_storage` | PASS |

## 实现边界

`validation_cli` 以其源文件的仓库根目录作为受保护 checkout 根，而不是使用
调用者的当前目录。该规则同样用于 validation store、Hold reassessment 和全部
Case OS 场外转换命令。
