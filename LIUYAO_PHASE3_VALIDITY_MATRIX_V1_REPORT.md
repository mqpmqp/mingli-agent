# LiuYao Phase 3 Validity and Conflict Matrix v1

## Decision

第三阶段第二批已定义为“高级事实有效性与冲突矩阵”的审查实现：它可以进入代码与规则审查，但不能进入生产判断，也不能被描述成传统六爻预测有效性的验证。

固定发布边界：

```text
method_id=liuyao-validity-conflict-matrix@0.1.0
validity_matrix_status=review_only
production_allowed=false
prediction_validity=not_evaluated

rule_profile_status=draft
evidence_level=source_only
human_reviewed=false
active_rule_source_family_count=1
referenced_text_family_count=2
empirical_validation_source_family_count=0

engineering_policy_status=review_only
```

## Review base

- 第三阶段范围冻结点：`2ed79e324ce502fc4b248b2d4217c3aa88f015eb`；
- 第一批来源门禁审查基线：`21864a4c05e621c5b79c65905571c50b346bab9f`；
- 第二批必须复用 `AdvancedContextRequest` 和 `advanced_runtime.py`，不得绕过第一批月日来源声明门禁；
- 既有 `InterpretationRequest` schema 保持不变，现实证据引用及显式确认位由新的 `ValidityRequest` 承载。

## Implemented scope

核心实现位于 `src/mingli/liuyao/validity_matrix.py`，公开：

- `ValidityRequest`；
- `build_validity_matrix()`；
- 相互独立的来源规则 profile、工程优先级/枚举 policy 及各自 SHA-256；
- 节点四轴、伏神、边、路径、冲突和最终报告的不可变数据结构；
- 请求、规则轨迹和完整报告的 canonical SHA-256。

配套新增 `validity_benchmark.py`、`validity_cli.py`、`tests/test_liuyao_validity_matrix.py`、`tests/test_liuyao_validity_cli.py`、`docs/liuyao/VALIDITY_SOURCE_AUDIT_V1.md` 和本批规则文档。

规则说明见 `docs/liuyao/VALIDITY_MATRIX_V1.md`。本文档记录工程决策与验收合同，不把尚未执行的命令写成已通过结果。

## Engineering decisions

### 1. 条件义务代替二元真假

旬空、月破、墓、绝、合冲不会直接把节点改成“有效”或“失效”。实现分别保留：

```text
open_obligations
relief_candidates
rule_hits
conflicts
```

填空、冲空、日扶月破和冲库都只是解除候选。解除候选不会删除原义务；一个条件也不能顺带清除另一条件。

每个会改变 `open_obligations`、`relief_candidates`、伏神开放义务或释放候选的裁决都有独立 `RuleHit`，并进入 `trace_sha256`。候选的 `discharged_obligations` 保持为空，`remaining_obligations` 明示对应义务仍未关闭。

### 2. 来源冲突不靠顺序覆盖

当前引用材料属于同一作者文本谱系，独立来源族数量为 1。规则因此固定为 `source_only`、`human_reviewed=false`。同一谱系中“动空”等不能直接合并的说法输出 `AUTHOR_INTERNAL_CONFLICT`，不按规则加载顺序或分数决定胜负。

张志春《未知之门》只作为 `supplementary_scope_audit` 记录作用域限制、角色极性反例与方法边界，固定 `activates_rules=false`；它不把案例旁证升级为活动规则，也不改变核心规则档案的单一来源族口径。

来源命中不再把 author rule、attributed quote 与 author case 压成一个合成等级；每个 `source_ref` 在 `source_evidence` 中独立绑定等级、作用域和来源术语。“冲开库”精确绑定 `src_039:print296/pdf296` 与 `src_037:print358/pdf373`。

### 3. 固定工程优先级

运行时优先级为：

```text
800 contract_integrity_gate
700 reality_gate
600 calendar_provenance_gate
500 use_selection_gate
400 node_validity
350 hidden_self_gate
300 same_position_change
200 direct_moving_to_use
100 indirect_moving_path
50 path_validity
```

最终状态另输出固定收据 `reality > calendar_provenance > use_selection > node_validity > path_validity`；合同、类型和哈希完整性在进入该流程前检查，并单列于 `engineering_policy.precondition_gates`。优先级表、枚举上限和路径状态轴只绑定独立 `engineering_policy_sha256`；来源身份、逐页证据等级、文本异常和来源规则合同只绑定 `rule_profile.profile_sha256`。调用方均不能覆盖。该次序固定可复算的门禁和审查范围，不宣称是经独立文献审定的传统统一口诀，也不产生概率或旺衰净分。未能由显式门禁解决的冲突保持 `unresolved`。

### 4. 节点四轴和报告双状态

节点四轴中的前两个核心有效性轴把 `structural_eligibility` 与 `current_force` 分开：空破墓绝不永久删除结构节点，但可使当前力量未知、受限或未决。`manifestation_state` 记录是否待出空、填实、冲库或逢生；`role_polarity` 在 v1 只区分已选用神和未分配角色，避免把墓绝直接翻译为固定吉凶。

`focus_status` 只描述已选用神焦点：现实阻断、待确认、上下文未知、条件性、未决或基础候选。

`inventory_status` 描述全盘事实清单：未知上下文、条件性或完整。现实硬阻断只覆盖焦点行动状态，不删除节点、伏神、关系边、路径和冲突。

这两个轴避免两类误判：非焦点节点的开放条件不能自动否定已选焦点；现实硬阻断也不能反向伪造盘面结构不存在。

### 5. 飞伏分层

伏神先独立经过自身的空破墓绝门禁，再考虑同位飞神的释放候选。飞神受空破墓绝或飞生伏不能自动推出“出伏”；伏神自身仍有约束时输出显式冲突。伏神不会自动升级为用神。

### 6. 两边有向路径与可审计裁剪

多动爻之间分别保留 `A→B` 和 `B→A`，再枚举到已确认用神的聚焦路径。变爻只回头作用同位原爻；跨位变爻边保留为 `pruned` 收据。循环、需要第三条边才能继续、不能到达焦点及枚举上限均产生显式原因。

同位变爻边分别记录来源范围与工程端点门禁；跨位边分别记录来源范围排除与工程执行排除，避免把 `source_only` 规则档案伪装成可配置的裁剪器。

路径把事实有效性与工程枚举拆成两轴：`validity_status` 为 `active_candidate/deferred`，`enumeration_status` 为 `retained/profile_excluded`。未被工程排除的活动直接生与直接克同时存在时保留 `OPPOSING_DIRECT_PATHS`，并把焦点标为 `unresolved`，不做条数抵消。只有保留、活动且终止于已选用神时才标记 `candidate_graph_reaches_focus=true`；它只是工程候选图可达，不是传统作用已兑现。间接路径方向仅代表进入焦点的最后一条边，不能解释为整条链已经完成能量合成。

## Schema controls

输入控制：

- `ValidityRequest` 复用原有 `InterpretationRequest` 与 `AdvancedContextRequest`；
- 两个请求的 `calendar_context_confirmed` 必须一致；
- 未确认历法时不消费命盘中已预计算的 `is_void/void_branches`，原爻、变爻和伏神均不会泄漏旬空或其他月日来源命中；
- 非 `unknown` 的现实状态必须同时设置 `reality_evidence_confirmed=true` 并绑定证据引用；
- 既有 `secondary_relations` 和 `notes` 只进入审计与摘要，不激活额外路径；
- 未知字段和错误 canonical SHA-256 被拒绝；
- `validity_cli evaluate` 还要求案例、起卦输入、有效性请求及两个嵌套请求都显式携带 canonical SHA-256，缺失时以 `HASH_REQUIRED` 失败关闭；
- 运行时只接受固定规则 profile。

输出控制：

- 所有报告固定携带 `review_only`、`production_allowed=false` 和 `prediction_validity=not_evaluated`；
- `rule_profile` 明示 `draft`、`source_only`、`human_reviewed=false`、活动来源族计数、来源族别名、逐页证据等级、旁审来源族和两个文本异常；
- `engineering_policy` 单独绑定门禁优先级、跨位边排除执行、两边/256 条上限和路径双状态轴；来源支持的同位作用语义仍在 `rule_profile`；
- `rule_hits` 携带来源 policy、工程 `priority_policy_id`、逐页来源族/等级/作用域/原文术语、节点角色、完整义务账本、规范关系及双层文本；
- `case_record_sha256`、`chart_sha256`、请求摘要和 `advanced_runtime_sha256` 绑定完整输入链；
- `priority_table_sha256`、`engineering_policy_sha256`、`precondition_gates` 与 `gate_priority_receipt` 绑定固定工程门禁，公开子对象去除自身哈希后可独立复算；
- `trace_sha256` 绑定规则轨迹，`canonical_sha256` 绑定完整报告；
- 摘要只用于完整性复算，不是防伪签名或现实真实性证明。

## Verification contract

最低本地验收：

```text
python -m compileall -q src tests
PYTHONPATH=src python -m pytest -q tests/test_liuyao_validity_matrix.py tests/test_liuyao_validity_cli.py
PYTHONPATH=src python -m mingli.liuyao.validity_cli benchmark
PYTHONPATH=src python -m pytest -q
python -m build
```

CLI 和 benchmark 还必须验证：

- stdout 只输出机器可读 JSON；
- 输入、摘要和来源门禁错误写入 stderr 并返回非零退出码；
- 基准断言发布边界、节点四轴、飞伏自身门禁及 inventory 汇总、路径双轴的活动/延后与可达/不可达两半轴、两边路径和裁剪收据；
- 输出不含成功概率、确定日期和应期。

本文档收口时已在 Python 3.12.13 实际执行：

```text
/workspace/scratch/291516038b5a/mingli-agent-test-venv/bin/python \
  -m compileall -q src tests
# PASS

PYTHONPATH=src /workspace/scratch/291516038b5a/mingli-agent-test-venv/bin/python \
  -m pytest -q tests/test_liuyao_validity_matrix.py tests/test_liuyao_validity_cli.py
# 55 passed

PYTHONPATH=src /workspace/scratch/291516038b5a/mingli-agent-test-venv/bin/python \
  -m mingli.liuyao.validity_cli benchmark
# status=passed；31/31 checks=true

PYTHONPATH=src /workspace/scratch/291516038b5a/mingli-agent-test-venv/bin/python \
  -m pytest -q \
  --deselect tests/test_derived_contracts.py::SourceAndPackagingTests::test_wheel_contains_readable_schemas \
  --deselect tests/test_phase7_fact_graph.py::Phase7WheelTests::test_wheel_contains_phase7_resources_and_builds_fact_graph \
  --deselect tests/test_phase8_rule_evaluation.py::Phase8WheelTests::test_fresh_venv_import_origin_and_installed_phase8_benchmark \
  --deselect tests/test_phase9_strength_quantification.py::Phase9WheelTests::test_fresh_venv_import_origin_installed_benchmark_and_calculate
# 697 passed, 4 deselected, 1 warning, 31 subtests passed

/workspace/scratch/291516038b5a/mingli-agent-test-venv/bin/python \
  -m build --no-isolation
# PASS：sdist 与 wheel 均成功生成；生成物仅用于检查，未纳入交付
```

另完成 4,096 盘全排列扫测、256 份哈希重放与 256 份未确认历法请求；共检查 40,448 个节点、3,584 个伏神 wrapper、53,230 条边、114,495 条路径和 150,791 个 `RuleHit`，失败为 0。所有路径均不超过两条边；3,584/3,584 个伏神 wrapper 的自身义务与外层义务都进入 `inventory_dependencies`；禁用越界页命中为 0。

标准隔离构建和依赖隔离构建的 4 个全仓打包测试在当前受限网络环境中无法取得 `setuptools>=68`，因此未通过；同一失败已在未改动的 `21864a4` 基线以 `PIP_NO_INDEX=1` 复现，而当前树和基线的 `python -m build --no-isolation` 均通过。该结论只排除了本批代码回归，不能替代可访问构建依赖环境中的标准隔离构建。

当前分支没有获得外部写入授权，未推送、未创建 PR，因此也没有当前 Head CI 结果。推送后必须以当前 Head 重新运行仓库要求的标准隔离构建和 CI；第一批基线的绿色结果不能替代本批 Head。

## Protected scope

本切片不应修改或扩大：

- `spec/`、来源资产和真实案例数据；
- 第一、第二阶段的确定性排盘、事件合同、版本和结算语义；
- 第一批月日来源门禁；
- 八字、紫微、奇门、梅花、PWA和生产服务；
- 规则生命周期到 `reviewed` 或 `verified` 的升级。

## Known limits and risks

- 核心规则没有人工审定，且只有一个来源族；
- 来源引用是声明性收据，运行时不核验其内容；
- 尚未闭合完整旺衰、暗动、真破、合化、三合成局和全部冲库条件；
- 伏神不会自动出伏或自动取用；
- 变爻跨位作用被当前工程 policy 排除，只保留裁剪收据；
- 多动爻路径按当前工程 policy 最多两条边、256 条，间接方向不代表整链聚合；
- 没有合格的前瞻真实案例，不能评估或宣传准确率；
- 不输出事件概率、确定日期、应期或自然语言吉凶成品。

## Next gate

本批通过代码、测试、文档、全仓门禁和当前 Head CI 审查后，才可讨论第三切片的合同驱动自动取用。`available_candidate` 不得直接升级成自动取用、确定方向或成功概率。条件化应期属于第四切片，当前明确不进入。
