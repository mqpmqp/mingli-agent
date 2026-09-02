# 六爻第三阶段：高级事实有效性与冲突矩阵 v1

## 定位

本切片消费已经冻结、可重算的 `LiuYaoCaseRecord`，以及第三阶段第一批的来源门禁运行时，在不生成吉凶成品的前提下完成三件事：

- 把旬空、月破、墓、绝、合冲登记为节点的开放条件，而不是直接判成“有效”或“无效”；
- 把伏神自身条件与飞神释放候选分开；
- 围绕已确认用神建立多动爻有向候选图，并保留裁剪原因和冲突。

固定治理合同：

```text
method_id=liuyao-validity-conflict-matrix@0.1.0
validity_matrix_status=review_only
production_allowed=false
prediction_validity=not_evaluated

rule_profile_id=liuyao-shaoweihua-source-only-validity@0.1.0
rule_profile_status=draft
evidence_level=source_only
human_reviewed=false
active_rule_source_family_count=1
referenced_text_family_count=2
empirical_validation_source_family_count=0

engineering_policy_id=liuyao-validity-engineering-policy@0.1.0
engineering_policy_status=review_only
```

`review_only` 表示结果只能供规则审查和工程复算。`production_allowed=false` 是不可由调用方解除的发布边界。结构测试通过也不评估传统六爻的现实预测有效性。

## 基线与输入合同

本切片以第三阶段范围冻结点 `2ed79e324ce502fc4b248b2d4217c3aa88f015eb` 为范围依据，以第一批来源门禁审查基线 `21864a4c05e621c5b79c65905571c50b346bab9f` 为工程起点。

`ValidityRequest` 包装而不修改既有请求：

```text
interpretation          InterpretationRequest
advanced_context        AdvancedContextRequest
reality_evidence_refs   tuple[str, ...]
reality_evidence_confirmed bool
rule_profile_id         固定为本页所列 profile
canonical_sha256        可选；提供时必须与重算值一致
```

输入门禁：

1. `InterpretationRequest.calendar_context_confirmed` 必须与 `AdvancedContextRequest.calendar_context_confirmed` 一致；
2. 月日事实仍必须通过第一批的 `calendar_source_refs` 声明门禁，不能因盘中有月建、日柱就自动视为已确认；
3. `reality_status != unknown` 时必须同时设置 `reality_evidence_confirmed=true` 并绑定非空 `reality_evidence_refs`；`reality_status=unknown` 时两者必须分别为 `false` 和空列表；
4. 来源引用目前只记录调用方的声明，不读取引用内容，也不验证历法或现实材料的真实性；
5. 既有 `secondary_relations` 和 `notes` 仍只参与审计与哈希，不会被静默解释成路径指令；
6. 未知字段、请求摘要不一致或不支持的规则 profile 均拒绝处理。

未确认历法时，即使命盘记录已携带日柱及预计算旬空，原爻、变爻和伏神也只输出 `CALENDAR_PROVENANCE_UNCONFIRMED`；不得消费 `is_void/void_branches`，不得产生空破墓绝来源命中或污染 `trace_sha256`。

## 证据边界

当前规则引用如下：

| 主题 | 来源引用 |
|---|---|
| 旬空、动空冲突 | `src_039:print94-95/pdf94-95,print165-166/pdf165-166,print202/pdf202`；`src_037:print181-182/pdf196-197,print219/pdf234` |
| 月破、日冲与冲空 | `src_039:print198-200/pdf198-200`；`src_037:print215-217/pdf230-232` |
| 墓、绝与冲库 | `src_039:print219-221/pdf219-221,print335/pdf335,print338-339/pdf338-339`；`src_037:print236-238/pdf251-253,print356/pdf371,print359-360/pdf374-375` |
| 飞神、伏神 | `src_039:print169-172/pdf169-172`；`src_037:print185-188/pdf200-203` |
| 变爻作用范围 | `src_039:print193-194/pdf193-194`；`src_037:print210-211/pdf225-226` |

这些页码属于同一邵伟华文本谱系，平行版本或重复表述不能计为独立来源确认。因此 profile 固定为 `source_only`、`human_reviewed=false`、`active_rule_source_family_count=1`，且 `empirical_validation_source_family_count=0`。来源内部出现不能直接合并的说法时，矩阵输出 `AUTHOR_INTERNAL_CONFLICT`，不按加载顺序选一条。逐页证据、反例与不可补造规则见 [VALIDITY_SOURCE_AUDIT_V1.md](VALIDITY_SOURCE_AUDIT_V1.md)。

《未知之门》（`src_040`）作为不同作者的补充材料，只进入 `supplementary_scope_audit`：用于标记“终身卦世爻”等作用域限制、角色极性反例和方法边界，`activates_rules=false`。它不把作者案例升级为活动通则，也不改变活动规则来源族计数。

原页“旬空、填空”疑似“冲空、填空”和“伏神库绝于日、月飞神者”的语法歧义分别以 `VOID_FILL_WORDING_219_202`、`HIDDEN_TOMB_ABSOLUTE_GRAMMAR_172` 进入 `source_text_anomalies`，均固定 `activates_rules=false`，不静默改字或补造优先级。

## 固定优先级

数值越大，门禁越先检查：

| 顺序 | `priority_band` | 用途 |
|---:|---|---|
| 800 | `contract_integrity_gate` | 冻结合同、类型与哈希完整性前置门禁 |
| 700 | `reality_gate` | 有证据引用的现实硬阻断只覆盖行动状态 |
| 600 | `calendar_provenance_gate` | 月日轴及其来源声明门禁 |
| 500 | `use_selection_gate` | 用神必须为显式确认或唯一可见候选 |
| 400 | `node_validity` | 空、破、墓、绝及合冲条件义务 |
| 350 | `hidden_self_gate` | 伏神自身资格先于飞神释放候选 |
| 300 | `same_position_change` | 变爻只回头作用本位原爻 |
| 200 | `direct_moving_to_use` | 动爻到所选用神的直接候选边 |
| 100 | `indirect_moving_path` | 多动爻间接路径只作聚焦候选 |
| 50 | `path_validity` | 汇总保留路径的有效性与未决冲突 |

报告另固定输出运行时门禁收据：

```text
reality_gate
> calendar_provenance_gate
> use_selection_gate
> node_validity
> path_validity
```

`contract_integrity_gate` 在反序列化和进入矩阵前执行，并在 `engineering_policy.precondition_gates` 单独公开；上述 `gate_priority_receipt` 记录通过完整性门禁后的状态裁决顺序。现实阻断最先；无阻断时先判月日来源，再判用神选择、节点和路径。

该表是可复算的工程门禁顺序，不是旺衰分数、事件概率或经独立验证的传统通则。高优先级用于限制低优先级可以进入的审查范围；同层或跨层仍有冲突时保持 `unresolved`，不能用条数、分数或加载顺序强行决胜。

来源身份、页码、文本异常、来源规则合同及“变爻只回头作用本位原爻”的来源语义进入 `rule_profile.profile_sha256`；优先级、跨位边排除收据、两边/256 条枚举上限和路径状态轴进入独立的 `engineering_policy.policy_sha256`。两者分开绑定，避免把工程裁剪上限伪装成传统来源规则。

## 分轴状态

### 节点四轴

节点不会用一个布尔值混合“仍可参与结构”与“当前能否作用”。四轴中的前两个是核心有效性轴：

| 字段 | 语义 | 当前值 |
|---|---|---|
| `structural_eligibility` | 节点是否仍保留在结构图中 | v1 固定为 `retained_candidate` |
| `current_force` | 当前是否具备作用或承受条件 | `unknown_context`、`unresolved`、`constrained`、`available_candidate` |

另两个轴约束显现和角色解释：

- `manifestation_state` 区分未知、未决、待解除、条件性与候选显现；
- `role_polarity` 只区分 `selected_use` 与 `unassigned`，未确认元神、忌神等角色前，墓绝不能自动翻译为吉凶。

因此旬空、月破、墓、绝可以约束 `current_force` 或延后 `manifestation_state`，但不会把 `structural_eligibility` 改成永久删除。

### 报告焦点轴与事实清单轴

矩阵把“当前用神焦点能否进入审查”与“全盘事实是否完整”分成两个轴，防止非焦点节点拖垮焦点状态，也防止现实阻断删除盘面审计事实。

#### 焦点轴 `focus_status`

| 条件 | 状态 |
|---|---|
| 已确认且绑定引用的现实硬阻断 | `reality_blocked` |
| 月日轴未通过来源声明门禁 | `calendar_unconfirmed` |
| 来源已确认但月建或日柱缺失 | `calendar_partial` |
| 用神不存在或候选不唯一且未显式确认 | `needs_confirmation` |
| 已选节点仍有局部上下文缺口 | `unknown_context` |
| 已选用神仍有一般条件义务 | `conditional` |
| 已选用神有方向未决或规则冲突 | `unresolved` |
| 已选用神通过当前基础门禁 | `available_candidate` |

门禁严格按 `reality > calendar provenance > use selection > node > path` 执行。已选节点本身可用但仍存在到焦点的延后路径时，焦点状态降为 `conditional`。`available_candidate` 只表示通过当前 profile 的基础门禁，不能翻译为事情会成功。`focus_dependencies` 收集来源、用神选择、已选节点的开放义务，以及是否存在延后路径。

#### 事实清单轴 `inventory_status`

| 条件 | 状态 |
|---|---|
| 任一显式节点缺少月日来源上下文 | `unknown_context` |
| 任一节点尚非可用候选，或存在伏神候选 | `conditional` |
| 所有显式节点均通过当前基础门禁且没有伏神候选 | `complete` |

`inventory_dependencies` 保留全盘节点与伏神候选的开放义务。现实硬阻断只把焦点轴设为 `reality_blocked`；节点、边、路径和冲突仍留在事实清单轴供审计。

## 空、破、墓、绝的节点矩阵

原爻、变爻和伏神分别形成节点。节点输出月日地支关系、月日十二长生阶段、规则命中、开放义务和解除候选。

| 条件事实 | v1 处理 |
|---|---|
| 旬空 | 登记 `VOID_EFFECT_OPEN`；发动不能自动清空旬空义务 |
| 月支冲节点 | 登记 `MONTH_BREAK_OPEN`，不扩大成永久无效 |
| 墓 | 分别登记月墓或日墓开放义务；仍需旺衰、扶助和冲库条件 |
| 绝 | 分别登记月绝或日绝开放义务；不直接等同于失败或无力 |
| 日冲、月日合 | 登记方向未决义务，不自动解释为冲起、冲散、合起或合绊 |
| 填空、冲空、日扶月破、冲库 | 只登记 `relief_candidates`，不自动删除原有义务 |

节点状态按门禁得出：

```text
unknown_context      月日或来源信息不足
conditional          仍有一般开放义务
unresolved           存在方向未决或来源冲突
available_candidate  当前 profile 下没有开放义务
```

同一节点同时存在多项约束时输出 `MULTIPLE_EFFECT_CONSTRAINTS`；旬空与月破并存时另输出 `VOID_AND_MONTH_BREAK`。任何单一解除候选都不能一并清除其他约束。

## 飞神与伏神

处理顺序固定为：

1. 先独立计算伏神自身的空、破、墓、绝和月日来源状态；
2. 再读取同位飞神状态；
3. 分别记录 `flying_to_hidden` 与 `hidden_to_flying` 的五行有向关系；
4. 最后登记释放候选、开放义务和内部冲突。

飞神空破墓绝、飞生伏等只会进入 `release_candidates`。只要伏神自身仍有约束，就输出 `HIDDEN_RELEASE_AND_SELF_CONSTRAINT`；飞神的释放候选不能越过 `hidden_self_gate`。伏克飞的来源内部语义冲突固定保留为 `AUTHOR_INTERNAL_CONFLICT`。

`visibility_state` 始终只是 `hidden_candidate`；`activation_state` 只会是 `unknown_context`、`unresolved` 或 `conditional`。v1 不会自动“出伏”，不会把伏神自动升级为用神，也不会据此生成成败结论。

## 多动爻两边路径与裁剪

### 有向边

- 每个变爻只保留到同位原爻的 `changed_to_same_original` 边；
- 变爻到跨位用神的边明确标为 `pruned`，原因是 `CHANGED_CROSS_POSITION_EXCLUDED`，裁剪收据仍在输出中；
- 每个非用神动爻分别建立到所选用神的直接边；
- 任意两个非用神动爻建立两个彼此独立的有向候选边，例如同时保留 `A→B` 和 `B→A`，不把两边压成一条无向关系。

边的两端都为 `available_candidate` 时，边才是 `active_candidate`；任一端上下文未知或仍有条件时，边为 `deferred`。关系方向分别保留为 `supportive`、`restrictive`、`draining`、`contained` 或 `peer`，不换算为净分。

同位边先写一条来源适用范围命中，再写工程端点门禁命中；跨位边则分别写“超出来源适用范围”和“工程执行排除”两条命中。来源命中不冒充工程执行，工程命中不绑定传统页码。

### 聚焦路径

路径只围绕已确认用神枚举：

- 直接动爻到用神属于 `direct_moving_to_use`；
- 经其他动爻的路径属于 `indirect_moving_path`；
- `validity_status` 只表示端点/边事实：所有边均活动时为 `active_candidate`，否则为 `deferred`；
- `enumeration_status` 只表示工程枚举：进入聚焦图为 `retained`，循环、过长或与焦点无关时为 `profile_excluded`；具体原因写入 `enumeration_reason`；
- 需要第三条边才能继续的分支在第二条边处以 `PATH_LENGTH_LIMIT` 截止，但其 `validity_status` 仍独立保留，不能把工程排除解释成传统无效；
- 当前最多保留 256 条路径，达到上限时输出 `PATH_ENUMERATION_LIMIT`，不能把截断集说成完整路径集。

保留且活动的直接路径同时出现生与克时输出 `OPPOSING_DIRECT_PATHS`，焦点降为 `unresolved`，不按数量抵消。只有 `enumeration_status=retained`、`validity_status=active_candidate` 且路径确实终止于已选用神时，`candidate_graph_reaches_focus` 才为 `true`。该字段只表示工程候选图可达，不宣称传统生克已经兑现。间接路径的 `direction` 只标记进入焦点的最后一条边，不能据此声称已经完成整条链的能量合成。

路径枚举排除只缩小当前用神的审查图。边上的 `pruned` 和路径上的 `profile_excluded` 都不表示该关系在所有流派、所有题型或所有时点永久无效。

## Python API

```python
from mingli.liuyao.validity_matrix import ValidityRequest, build_validity_matrix

request = ValidityRequest(
    interpretation=interpretation_request,
    advanced_context=advanced_context_request,
    reality_evidence_refs=(),
    reality_evidence_confirmed=False,
)
report = build_validity_matrix(case_record, request)
payload = report.to_dict()
```

CLI：

```bash
python -m mingli.liuyao.validity_cli evaluate \
  --record case.json \
  --request validity-request.json

python -m mingli.liuyao.validity_cli benchmark
```

CLI 的 stdout 为机器可读 JSON。输入、摘要、来源或文件错误写入 stderr 并返回 `1`；命令行用法错误返回 `2`。
`evaluate` 使用严格冻结模式：案例、起卦输入、有效性请求、解释请求和高级上下文都必须携带 `canonical_sha256`；缺失时返回 `HASH_REQUIRED`，不把“可重算但未绑定摘要”的对象当作冻结输入。命盘本身仍由起卦输入重算并逐字段核对。摘要用于发现漂移，不是安全签名。

主要输出字段：

```text
method_id
validity_matrix_status
production_allowed
prediction_validity
rule_profile
engineering_policy
case_id
case_record_sha256
chart_sha256
request
interpretation_request_sha256
advanced_runtime_sha256
priority_table_sha256
engineering_policy_sha256
gate_priority_receipt
focus_selection
focus_status
inventory_status
nodes
hidden_candidates
edges
paths
conflicts
focus_dependencies
inventory_dependencies
reality_override
trace_sha256
headline
warnings
limits
canonical_sha256
```

`rule_profile` 公开活动来源、来源族别名、逐页证据等级、补充作用域审计、文本异常及来源规则合同；`engineering_policy` 另公开前置门禁、优先级表、状态裁决顺序、路径双状态轴和 `maximum_path_hops=2`。每条 `rule_hit` 区分来源规则或工程 policy，并记录 `priority_policy_id`、逐页 `source_evidence`、`source_family`、`source_level`、`source_refs`、`topic_scope`、`node_role`、义务账本与结果。来源适用范围和工程排除执行使用两条独立命中收据。

`profile_sha256` 可由删除 `rule_profile.profile_sha256` 后的公开子对象直接重算；`policy_sha256` 同理由删除 `engineering_policy.policy_sha256` 后的公开子对象重算。`priority_table_sha256` 可由公开的 `priority_bands + precondition_gates + gate_priority` 重算。`trace_sha256` 覆盖显式节点、伏神自身、飞伏规则和边上的全部规则命中；`canonical_sha256` 覆盖完整报告。摘要用于发现漂移，不是防伪签名，也不证明来源或结论真实。

## 明确不做

v1 不提供：

- 自动历法换算或月日来源真实性验证；
- 完整旺衰、暗动、真破、合化、三合成局和所有冲库条件；
- 经人工审定或多独立来源确认的传统有效性规则；
- 伏神自动出伏、自动取用或最终吉凶方向；
- 多动爻能量净分或跨位变爻作用；
- 事件成功概率、置信概率、确定日期、应期或自然语言吉凶成品；
- 对传统六爻现实预测准确率的评估或声明。

第三阶段第三、第四切片不能从本矩阵的 `available_candidate` 推导出自动取用、成功概率或确定应期，必须另建合同、规则审查和前瞻结算证据。
