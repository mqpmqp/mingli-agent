# Case OS V2 外部转换 TDD 证据

## 用户旅程

受控操作员从 Git checkout 外的冻结案例快照开始：先记录 prediction 前已经
发生的前事，再以新快照记录 prediction 冻结后的未来反馈，建立时间分区，生成
仅供人工处理的审查队列，或创建撤回 tombstone。每一步都只能写新文件，原快照
不会被替换；所有 fixture 均为合成合同数据，不是准确率或商业主张的证据。

## RED

Checkpoint：`921a91e`。

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_cli.py -q --basetemp .pytest-case-os-ops-red
```

结果：`1 failed, 5 passed`。`case-future` 尚未注册，错误为
`invalid choice: 'case-future'`。

## GREEN

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_cli.py tests/test_release_hold_attack_v1.py tests/test_validation_astro_etl.py -q --basetemp .pytest-case-os-cli-cov --cov=mingli.validation_cli --cov-report=term-missing
python -m compileall -q src/mingli
git diff --check
```

结果：`26 passed`；`validation_cli.py` 覆盖率 `85%`；编译与差异空白检查通过。

| 保证 | 测试 | 结果 |
|---|---|---|
| 前事只能写入冻结预测前的证据，并留下原冻结快照 | `test_case_os_cli_keeps_external_snapshots_append_only_after_start` | PASS |
| 未来反馈通过 Reality Evidence 写成新快照并执行 hard override | 同上 | PASS |
| 分区使用明确 cutoff，且案例进入 test partition | 同上 | PASS |
| 审查队列不自动应用任何规则动作 | 同上 | PASS |
| 撤回创建独立 tombstone，Release Hold 保持 ACTIVE | 同上 | PASS |

## 已知边界

- 命令只编排已经存在的 V2 不可变合同函数；不会接触真实身份资料、授权记录、
  project salt 或用户反馈。
- 规则推荐的裁决仍必须通过独立人工审查；不会自动升降级、发布、打标签或上传。
