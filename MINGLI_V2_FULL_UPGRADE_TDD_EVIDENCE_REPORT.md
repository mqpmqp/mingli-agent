# 命理师 V2.0 完整升级 TDD 证据

日期：2026-08-29
RED checkpoint：`46e96a6`
GREEN checkpoint：`ddd1774`

## 1. 来源与用户旅程

本次没有外部 `*.plan.md`。用户旅程直接来自本任务的九阶段验收合同：

- 作为付费用户，我希望缺失资料被明确降级，而不是得到虚构命盘；
- 作为付费用户，我希望只回答当前专题，并获得可复盘的现实行动和低风险文化辅助；
- 作为续问用户，我希望只处理新增问题，不重复完整报告；
- 作为审核者，我希望非 production 规则不能进入交付；
- 作为评测者，我希望预测到期后才结算，并区分坏输入、无反馈和预测合同错误；
- 作为安全审核者，我希望默认路径完全不进入称骨模块，也不出现结果保证或未经校准的概率。

## 2. RED 证据

先提交三个测试文件，再使用仓库审计确认的 Python 3.11 虚拟环境执行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  tests\test_paid_delivery_upgrade.py `
  tests\test_rule_and_advice_governance_v2.py `
  tests\test_forward_evaluation_policy_v2.py
```

RED 结果：收集阶段出现三个预期 `ModuleNotFoundError`：

- `mingli.delivery_contracts`；
- `mingli.rule_governance`；
- `mingli.forward_evaluation`。

这些错误由测试首次引用尚未实现的新合同产生，不是语法错误、依赖缺失或旧回归。测试 commit `46e96a6` 位于当前任务分支且可由 HEAD 追溯。

一次使用系统 Python 3.13 的复跑因 package 未安装而报 `No module named mingli`，该结果属于解释器/安装方式不匹配，不计入有效 RED。随后改用审计确定的 `.venv` 获得上述有效 RED。

## 3. GREEN 证据

实现四个新模块后，复跑同一命令：

```text
..................................                                       [100%]
34 passed in 0.39s
```

同次阶段还执行：

```powershell
.\.venv\Scripts\python.exe -m py_compile `
  src\mingli\delivery_contracts.py `
  src\mingli\rule_governance.py `
  src\mingli\paid_delivery.py `
  src\mingli\forward_evaluation.py
```

退出码为 0。实现 commit `ddd1774` 位于 RED checkpoint 之后，且可由当前分支 HEAD 追溯。

## 4. 行为保证索引

| # | 保证 | 测试位置 | 类型 | GREEN |
|---|---|---|---|---|
| 1 | 统一输入支持出生、图片确认、六次结果、现实状态和复盘点 | `test_unified_case_input_supports_birth_image_divination_and_reality` | 集成 | PASS |
| 2 | 缺出生时刻时自动降级，不伪造命盘 | `test_missing_birth_fields_degrade_instead_of_fabricating` | 单元 | PASS |
| 3 | 未确认图片固定低置信且不进入时点判断 | `test_unconfirmed_image_chart_is_low_confidence_and_not_precise` | 集成 | PASS |
| 4 | 四维置信度彼此独立且没有概率文本 | `test_confidence_profile_has_four_independent_dimensions` | 单元 | PASS |
| 5 | 699 使用 focused 九项合同，不回退固定八段 | `test_paid_699_is_focused_nine_part_contract_without_fixed_eight_or_bone_weight` | 合同 | PASS |
| 6 | 称骨模块只在显式点名后启用 | `test_explicit_bone_weight_request_is_the_only_opt_in_path` | 合同 | PASS |
| 7 | 续问不重复完整报告或其他专题 | `test_follow_up_stays_focused_and_does_not_repeat_full_paid_report` | 合同 | PASS |
| 8 | 复合和考公考编包含所有必要判断层 | `test_special_paid_topics_cover_required_independent_layers` | 集成 | PASS |
| 9 | 婚姻、失联和屏蔽等现实反证覆盖象意 | `test_reality_counterevidence_has_priority_over_symbolic_interpretation` | 集成 | PASS |
| 10 | 输出包含条件、反证、复盘点、单次免责声明且通过禁词扫描 | `test_paid_output_has_conditions_counterevidence_review_point_and_safe_language` | 安全合同 | PASS |
| 11 | 同输入产生相同结构和 canonical hash | `test_same_input_has_deterministic_golden_contract` | golden | PASS |
| 12 | 生命周期固定为六状态 | `test_rule_statuses_are_the_fixed_six_state_lifecycle` | 单元 | PASS |
| 13 | 九类规则都有来源、范围、反例和审核 | `test_nine_domain_rule_packs_have_source_scope_counterexample_and_review` | 治理 | PASS |
| 14 | draft 与 pending rule 不进入 production | `test_only_production_rules_can_enter_paid_runtime` | 隔离 | PASS |
| 15 | 未知状态 fail closed | `test_unknown_rule_status_fails_closed` | 错误路径 | PASS |
| 16 | AdviceRule 完整覆盖规定字段 | `test_advice_rules_implement_the_full_structured_contract` | 合同 | PASS |
| 17 | 九个付费专题均可确定匹配安全建议 | `test_every_paid_domain_has_deterministic_advice_matching` | 参数化 | PASS |
| 18 | 财运不默认补财库，现金流风险触发拒绝 | `test_finance_advice_does_not_default_everyone_to_wealth_ritual` | 安全合同 | PASS |
| 19 | 健康医疗优先，风水资料不足不输出方向 | `test_health_and_fengshui_advice_are_fail_closed` | 安全合同 | PASS |
| 20 | 九类实盘结果枚举精确固定 | `test_evaluation_taxonomy_is_exact_and_versioned` | 单元 | PASS |
| 21 | 到期前不能结算 | `test_forward_test_cannot_settle_before_due_at` | 时间门禁 | PASS |
| 22 | 作者自述和付款截图不能成为证据 | `test_self_claim_and_payment_are_never_evidence` | 参数化安全 | PASS |
| 23 | 到期结算生成确定性收据 | `test_mature_forward_test_returns_a_deterministic_receipt` | golden | PASS |
| 24 | 无反馈、坏输入、无效预测不进入准确率 | `test_no_feedback_and_invalid_contracts_are_classified_without_accuracy_claims` | 评测合同 | PASS |

## 5. 覆盖率

使用外部临时 coverage data 文件执行 branch coverage，未写入项目文件：

```text
Name                               Cover
src/mingli/delivery_contracts.py     77%
src/mingli/forward_evaluation.py     77%
src/mingli/paid_delivery.py          82%
src/mingli/rule_governance.py        84%
TOTAL                                80%
```

测试结果为 `34 passed in 1.09s`，新模块总 branch coverage 达到本次 TDD 阈值。

## 6. 已知缺口

- 六爻引擎不存在，测试只保证输入校验和显式降级；
- 没有真实图片、Telegram 或生产 E2E，本报告不能替代这些门禁；
- 没有授权实盘数据，forward-test 测试使用合成记录，只证明到期与分类合同；
- 全量 pytest、三类 test gate、build、CLI 和 PWA 回归均已在文档完成后独立执行；真实终态、首次 PWA 环境失败与修复过程见 `MINGLI_V2_FULL_UPGRADE_IMPLEMENTATION_REPORT.md`。
