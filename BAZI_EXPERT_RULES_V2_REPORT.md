# Bazi Expert Rules V2 实现报告

## 结论

本工作流新增 `bazi-expert-orchestration-result@2.0` 确定性编排层。它直接调用既有 Phase 9—17、Phase 18 与可选 Phase 20，不复制强弱、格局、调候、喜忌、时序、十神领域、特殊场景、Evidence Fusion 或 Yuan 渲染规则。

所有输出继续固定：

```text
prediction_validity=not_evaluated
release_hold=ACTIVE
accuracy_claim_allowed=false
```

合成 fixture 只标记为 `contract_test_only` 且 `accuracy_eligible=false`，不构成准确率或真实事件证据。

## 公共接口

- 输入版本：`bazi-expert-orchestration-input@2.0`
- 输出版本：`bazi-expert-orchestration-result@2.0`
- 方法版本：`bazi-expert-orchestration@2.0.0`
- 入口：`orchestrate_bazi_expert_v2(request)`
- 输出 Schema：`src/mingli/contracts/schemas/bazi_expert_v2_result.schema.json`

输入只接受白名单字段。未知版本、未知顶层字段、损坏的 Fact Graph hash、非法 Reality Context、非法证据、非法 Renderer 输入或上游版本不兼容均 fail closed 为 `BaziExpertV2InputError`。

## 能力边界

| 状态 | Facet | 组合来源与边界 |
| --- | --- | --- |
| implemented | 五行强弱、同类/异类比例 | Phase 9 原值投影，不重新计分 |
| conditional | 格局 | Phase 10 candidate-only；不推导具体事件 |
| conditional | 用神与调候 | Phase 11/12 候选、季节气候需要和喜忌角色；古典日主逐月调候仍未评估 |
| conditional | 十神组合 | Phase 15 natal context、dynamic hits 与 cross-domain conflicts；十神主题不等于事件 |
| implemented | 刑冲合害摘要 | 汇总 Phase 7/13 已有 relation records；不新增化合或事件判断 |
| implemented | 大运、流年 | Phase 13/14 的结构互动和趋势；不输出具体断事 |
| unsupported | 流月 | 冻结 Phase 13/14 没有 `liuyue` 合同，明确 fail closed |
| conditional | 事业、财富、关系 | Phase 15/16 candidate contracts，并保留 Reality override |
| unsupported | 婚姻具体事件 | 关系倾向不能替代结婚/离婚事件规则 |
| conditional | 学业 | Phase 15 `education` 领域候选 |
| unsupported | 家庭 | 冻结领域合同没有 family domain |
| conditional | 考公考编 | Phase 17 层适配为体制适配、考试条件、岗位方向、备考策略；不保证上岸 |
| conditional | 复合 | Phase 17 层适配为吸引、联系、复合、稳定；不保证复合 |
| conditional | 双人基础兼容 | 分别调用 Phase 9—12，只做结构对照；无评分、无关系结果结论 |
| conditional | 前事验证 | 仅接收明确标识的 prior-event Reality Evidence，经 Phase 18 融合；不是准确率证明 |
| implemented | Reality Evidence | claim_id + scope 精确 hard override；冲突的 verified reality 为 unresolved/low |
| implemented | 置信度校准 | 纯结构 high 下调为 medium；未解冲突为 low；high 只可能来自已核验同 claim/scope reality |
| conditional | Yuan Renderer adapter | 仅在三个领域与连续五年输入齐备时调用 Phase 20；单一免责声明、受控文本、无绝对承诺 |

## 证据与隐私

- Phase 14 temporal evidence、Phase 15 domain evidence、Phase 17 layer-scoped reality 与 prior-event evidence 全部通过 Phase 18 汇总。
- verified Reality Evidence 只覆盖同一 `claim_id + scope`，不会跨领域、跨年份或跨场景层传播。
- 两条方向相反的 verified Reality Evidence 保持可见并输出 `unresolved_conflict`，不择一伪装确定性。
- 输入不保存、不联网、不写训练库；prior-event 输出保留结构化 code/hash，不把自由文本作为准确率材料。
- 双人兼容只输出双方结构字段和共同用神元素，不输出兼容分数或关系结果。

## TDD 检查点

- RED SHA：`178b816d7a16b4e7583c6276cd42ab449d3d2b4a`
- RED 命令：`$env:PYTHONPATH='src'; python -m pytest tests/test_bazi_expert_v2.py -q`
- RED 结果：exit 1；collection 因 `ModuleNotFoundError: No module named 'mingli.bazi_expert_v2'` 失败，属于预期缺失行为。
- GREEN SHA：本报告所在 GREEN 提交；最终交接记录完整 SHA。

## 验证结果

| 命令 | 结果 |
| --- | --- |
| `$env:PYTHONPATH='src'; python -m pytest tests/test_bazi_expert_v2.py -q` | PASS，9 passed in 16.74s |
| 临时 `COVERAGE_FILE` + `python -m coverage run --branch --source=mingli.bazi_expert_v2 -m pytest tests/test_bazi_expert_v2.py -q` | PASS，9 passed in 41.89s |
| `python -m coverage report --show-missing src/mingli/bazi_expert_v2.py` | PASS，83% branch-aware focused coverage |
| `$env:PYTHONPATH='src'; python -m ruff check src/mingli/bazi_expert_v2.py tests/test_bazi_expert_v2.py` | PASS，All checks passed |
| `$env:PYTHONPATH='src'; python -m compileall -q src` | PASS，exit 0 |
| `git diff --check` | PASS，exit 0 |
| `$env:PYTHONPATH='src'; python -m mingli.contracts.freeze --root .` | PASS，78 checked，0 violations，baseline `00eeaad66a2a36684ae2ad0b5b0074fcdf700640` |

## 变更文件

- `src/mingli/bazi_expert_v2.py`
- `src/mingli/contracts/schemas/bazi_expert_v2_result.schema.json`
- `tests/test_bazi_expert_v2.py`
- `BAZI_EXPERT_RULES_V2_REPORT.md`
- `docs/testing/bazi-expert-rules-v2.tdd.md`
