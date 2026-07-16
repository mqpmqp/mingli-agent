# Bazi Expert Rules V2 TDD 证据

## 来源与边界

本轮没有外部 plan 文件。用户旅程来自 Workstream A 合同与冻结架构。测试使用 Phase 7 生成的合成图，fixture 明确标记 `synthetic=true`、`purpose=contract_test_only`、`accuracy_eligible=false`；这些测试只证明工程合同，不证明预测准确率。

## 用户旅程

1. 作为 Bazi 编排调用方，我需要一次调用组合 Phase 9—18，并取得版本、来源 hash 和明确能力状态，而不是另一套重复规则。
2. 作为审查者，我需要看到五行强弱、同异类、格局、用神调候、十神、刑冲合害、大运流年和领域结果均可追溯到既有阶段。
3. 作为安全负责人，我需要流月、婚姻具体事件和家庭领域在没有冻结合同支持时明确 unsupported。
4. 作为考公用户，我需要体制适配、考试条件、岗位方向和备考策略，但不能得到“保证上岸”。
5. 作为关系用户，我需要吸引、联系、复合和稳定四层条件，但不能得到“必复合”或婚姻事件。
6. 作为双人比较调用方，我需要基础结构对照，但不能得到兼容分数或关系结果承诺。
7. 作为已有现实证据的调用方，我需要 Reality Evidence 只覆盖同一 claim/scope；冲突 reality 必须 unresolved/low。
8. 作为 Renderer 调用方，我需要复用 Phase 20 的受控八段文本、连续五年门禁和单一免责声明。
9. 作为发布审查者，我需要 synthetic fixture、`prediction_validity=not_evaluated` 与 ACTIVE Release Hold 不可被工程覆盖率改变。

## RED / GREEN

- RED checkpoint：`178b816d7a16b4e7583c6276cd42ab449d3d2b4a`
- RED 命令：`$env:PYTHONPATH='src'; python -m pytest tests/test_bazi_expert_v2.py -q`
- RED 证据：exit 1；测试在 collection 阶段引用预期的新模块，因 `ModuleNotFoundError: mingli.bazi_expert_v2` 失败。失败来自缺失实现，不是语法、环境或依赖错误。
- GREEN 命令：同一 focused pytest target。
- GREEN 证据：exit 0；`9 passed in 16.74s`。
- GREEN checkpoint：本 TDD 报告所在 GREEN 提交；完整 SHA 在最终交接中记录。

## 测试规格

| # | 保证 | 测试 | 类型 | 结果 |
| --- | --- | --- | --- | --- |
| 1 | 输出版本、canonical hash、Schema、not_evaluated、ACTIVE Hold 和 accuracy=false 一致 | `test_versioned_result_validates_and_preserves_non_accuracy_boundaries` | contract | PASS |
| 2 | 22 个 facets 完整分入 implemented / conditional / unsupported | `test_facets_distinguish_implemented_conditional_and_unsupported` | contract | PASS |
| 3 | 强弱、同异类、格局、调候、十神、relations、大运流年和领域视图均有来源 | `test_composed_structural_temporal_and_domain_views_are_source_backed` | integration | PASS |
| 4 | 考公、复合、双人比较、前事验证保持边界，不产生评分或具体结果 | `test_exam_reunion_compatibility_and_prior_events_remain_bounded` | integration | PASS |
| 5 | verified Reality Evidence 只 hard override 同 claim/scope | `test_reality_evidence_hard_override_is_claim_and_scope_specific` | integration | PASS |
| 6 | 相反 verified Reality Evidence 输出 unresolved/low，不静默择一 | `test_conflicting_verified_reality_is_unresolved_and_low_confidence` | integration | PASS |
| 7 | Yuan adapter 复用 Phase 20 八段、单一免责声明和禁承诺门禁 | `test_yuan_adapter_uses_phase20_without_inventing_text` | integration | PASS |
| 8 | JSON key 重排不改变完整输出或 canonical hash | `test_hash_is_deterministic_across_json_key_order` | determinism | PASS |
| 9 | 未知版本、未知私密字段和 tampered Fact Graph fail closed | `test_fail_closed_for_unknown_versions_tampering_and_private_fields` | negative contract | PASS |

## 任务—证据映射

| 任务 | 实现摘要 | 实际验证 |
| --- | --- | --- |
| Phase 9—16 组合 | 依次调用公开 evaluator，最终只投影上游字段与 hashes | focused pytest 9/9 PASS |
| Phase 17 特殊场景 | 把已有层适配为用户要求的四组 facet，不重写规则 | focused pytest 9/9 PASS |
| Phase 18 hard override | domain/temporal/scenario/prior-event 证据统一进入 claim+scope fusion | 两个 Reality Evidence 测试 PASS |
| 置信度校准 | 结构 high 封顶 medium；现实冲突 low | focused pytest 9/9 PASS |
| Phase 20 adapter | 仅连续五年和三个领域齐备时调用 renderer | Yuan adapter 测试 PASS |
| 显式 unsupported | monthly、marriage concrete event、family 不做 fallback 猜测 | facet partition 测试 PASS |

## 覆盖率与质量门禁

- Coverage.py 使用临时 `COVERAGE_FILE`，避免在工作树留下生成文件。
- 命令：`python -m coverage run --branch --source=mingli.bazi_expert_v2 -m pytest tests/test_bazi_expert_v2.py -q`
- 结果：9 passed；`src/mingli/bazi_expert_v2.py` 为 **83%** branch-aware focused coverage（481 statements、56 missed、170 branches、47 partial）。
- Ruff：owned Python files PASS。
- compileall：`src` PASS。
- `git diff --check`：PASS。
- frozen contracts：78 checked、0 violations、baseline SHA 不变。

## 已知缺口

- 冻结阶段没有流月 evaluator，因此 monthly 明确 unsupported。
- 冻结领域没有 family 合同；关系倾向也不构成婚姻具体事件合同。
- 双人能力只做双方 Phase 9—12 结构对照，不提供兼容分数。
- 本轮没有授权真实案例；所有 synthetic contract tests 都不进入 accuracy 统计，Release Hold 继续 ACTIVE。
