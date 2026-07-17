# Real Case Learning OS V2 实现报告

## 结论

Workstream C 已实现为新增的 V2 生命周期层，未修改冻结合同。系统保持：

- `prediction_validity=not_evaluated`
- `commercial_release_hold=ACTIVE`
- 真实存储必须为 `controlled_off_git`
- 合成记录只用于合同测试，`accuracy_eligible=false`
- 规则升级、降级、修订均进入人工队列，永不自动应用
- 未使用合成案例或虚构案例证明预测准确率

本交付仅证明工程合同与边界行为，不证明真实世界预测准确率，也不解除任何 Release Hold。

## 生命周期

`src/mingli/real_case_learning_v2.py` 组合现有 intake、privacy、prediction freeze、Reality Evidence、claims、dataset hash、review 与 training 版本边界：

1. 校验明确研究/基准同意，并要求支持撤回。
2. 使用既有 HMAC-SHA256 匿名化合同；真实身份与盐不进入记录。
3. 冻结排盘快照、原始问题、预测时现实上下文。
4. 冻结初始预测，强制未来现实证据在生成时不可见。
5. 先验事件必须在预测生成前观察并收集。
6. 未来结果必须在预测冻结后观察，且绑定已冻结的 `claim_id + scope + event_window`。
7. 复用 Phase 18，使已验证 Reality Evidence 只硬覆盖相同 claim 与 scope；冲突证据保留。
8. 支持 `hit / partial / miss / unverifiable`、错误分类、规则归因、修订和版本基准比较。
9. `promote / demote / retain / investigate` 仅产生 `pending_operator_review` 建议；`applied_to_rules=false`。
10. partial、miss 与 unverifiable 进入负例档案，但不自动改变规则。
11. train/test 依据事件窗口结束、观察时间和收集时间，不使用摄入顺序。
12. 同人、同预测、派生指纹或近重复指纹形成不可拆分组件；任一记录属于 test 时，全组件进入 test。
13. 撤回仅保留不可反识别 tombstone，并递归列出全部失效依赖哈希，不保留问题、排盘、预测或结果正文。

## 新增合同

- `real_case_learning_v2_case.schema.json`：完整 V2 case 生命周期记录。
- `real_case_learning_v2_partition.schema.json`：时间切分、重复隔离与泄漏防护清单。
- `real_case_learning_v2_withdrawal.schema.json`：撤回 tombstone 与依赖失效合同。

三个 schema 均为 Draft 2020-12，可由已打包的 `get_schema()` 读取。新测试文件被归入 `real_case` gate。

## 隐私、真实性与声明边界

- 模块不创建真实数据文件；只生成确定性、可哈希的内存合同记录。
- 原始身份仅作为匿名化函数输入，不进入返回值。
- 直接身份字段、手机号、邮箱、身份证样式内容在边界处拒绝。
- 标记 synthetic 的 intake/evidence 不得伪装成真实记录。
- 合成 fixture 均显式标记 `synthetic=true`，摘要不计算 accuracy metrics。
- 所有 V2 输出均保持 `product_claim_eligible=false` 与 ACTIVE Hold。

## TDD 与提交证据

- Base：`ae0f0cc182427a8b5ff6834a2bb324abcac1c9c0`
- RED：`b48e772e6ae86d67db394f41fdbe7a87d0980d56`
- RED 命令：`$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_learning_v2.py -q`
- RED 结果：collection 失败，唯一原因是 `ModuleNotFoundError: No module named 'mingli.real_case_learning_v2'`。
- GREEN：`5608f117a9c32bde42bf0317c529629ecab84d5c`
- GREEN 命令：同一 focused pytest 命令。
- GREEN 结果：`17 passed`。

详细测试映射见 `docs/testing/real-case-learning-os-v2.tdd.md`。

## 验证结果

- focused：`17 passed`
- 回归：V2、既有 real-case validation 与 training tests 合计 `62 passed`
- focused branch coverage：`80%`，满足 `>=80%`
- Ruff：`All checks passed!`
- compileall：通过
- frozen contracts：`ok=true`，检查 78 个冻结文件，0 violations
- `git diff --check`：通过

## 变更范围

- `src/mingli/real_case_learning_v2.py`
- `src/mingli/contracts/schemas/real_case_learning_v2_case.schema.json`
- `src/mingli/contracts/schemas/real_case_learning_v2_partition.schema.json`
- `src/mingli/contracts/schemas/real_case_learning_v2_withdrawal.schema.json`
- `src/mingli/test_gates.py`
- `tests/test_real_case_learning_v2.py`
- `docs/testing/real-case-learning-os-v2.tdd.md`
- `REAL_CASE_LEARNING_OS_V2_REPORT.md`

未修改上述范围外文件，未 push、publish、tag、merge、upload，也未更改 Release Hold。
