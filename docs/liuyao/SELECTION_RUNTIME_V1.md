# 六爻第三阶段：事件合同驱动候选取用运行时 v1

## 定位

本切片消费已经冻结的 `LiuYaoCaseRecord`、事件合同、第一批历法来源门禁和第二批有效性矩阵，为专项主题生成可审计的六亲与爻位候选。

运行时只允许输出“待人工复核的临时候选”。它不输出最终用神，也不把候选状态解释为事件成败、概率、吉凶或应期。

固定治理合同：

```text
method_id=liuyao-event-contract-selection-runtime@0.1.0
selection_runtime_status=review_only
production_allowed=false
prediction_validity=not_evaluated

source_profile_id=liuyao-shaoweihua-source-only-selection@0.1.0
source_profile_status=draft
source_evidence_level=source_only
source_human_reviewed=false
active_rule_source_family_count=1
empirical_validation_source_family_count=0

topic_policy_id=liuyao-selection-topic-policy@0.1.0
topic_policy_status=review_only

engineering_policy_id=liuyao-selection-engineering-policy@0.1.0
engineering_policy_status=review_only
```

`review_only` 表示报告只能用于规则审查、候选复核和工程重放。结构测试通过不代表传统六爻预测有效，也不能解除 `production_allowed=false`。

## 基线与公开入口

本切片以第二批审查 Head `a24a384037eae5a5d3a52ac6d81597fcd9fd3423` 为工程基线，直接复用：

- `LiuYaoCaseRecord` 与确定性命盘；
- `AdvancedContextRequest` 与 `build_advanced_runtime_report()`；
- `InterpretationRequest`；
- `ValidityRequest` 与 `build_validity_matrix()`；
- 第二批来源规则、工程 policy、优先级表和矩阵摘要。

唯一执行候选推导的公开运行入口为：

```python
build_selection_runtime_report(record, request)
```

不存在公开的低层 core builder；库不提供绕过事件合同、现实、主题、历法、主体、来源范围或方法门禁的候选推导函数。公开 dataclass 是序列化和值类型，不是认证边界：手工构造或 `dataclasses.replace()` 得到的对象不具备运行时来源资格，外部消费者必须用冻结输入重跑上述入口，不能把可重算摘要当成签名。

## 三类独立档案

### 来源规则 profile

`source_profile` 只记录资料实际支持的六亲映射、适用范围、方法冲突和来源偏好。它不包含工程门禁或候选决胜算法。

两本活动资料属于同一邵伟华文本谱系，因此两个页码收据不能计为两个独立来源验证。逐页证据和排除项见 [SELECTION_SOURCE_AUDIT_V1.md](SELECTION_SOURCE_AUDIT_V1.md)。

### 专项主题 policy

`topic_policy` 固定第三切片支持的三个主题和每个主题的维度边界。它来自项目事件合同分层，不冒充传统资料规则。

### 工程 policy

`engineering_policy` 固定单入口、门禁次序、一关系假设一矩阵、多候选不伪造确认爻位、伏神不贡献、发动不决胜和禁止输出项。

三者分别提供可独立重算的 SHA-256。删除公开子对象自身的 `profile_sha256` 或 `policy_sha256` 后，可以用规范 JSON 重算；这些摘要只是完整性收据，不是安全签名，也不证明来源或预测真实。

## 输入合同

`SelectionRequest` 为冻结、不可变对象。主要字段如下：

| 字段 | 语义 |
|---|---|
| `topic` | `exam`、`relationship_reconciliation` 或 `pregnancy`；接受 profile 中的中文别名 |
| `focus_dimension` | 当前事件合同唯一聚焦的专项维度 |
| `case_record_sha256` | `record.canonical_sha256`，把请求固定到当前案例、起卦输入和排盘 |
| `event_contract_sha256` | `digest(record.cast.event_contract.to_dict())`，固定为 64 位小写 SHA-256 |
| `advanced_context` | 复用 `AdvancedContextRequest`，承载历法确认位和来源引用 |
| `contract_focus_confirmed` | 调用方是否确认 topic/focus 与冻结事件合同一致 |
| `contract_source_refs` | 上述确认的声明性引用 |
| `reality_status` | `unknown`、`supportive`、`blocking` 或 `mixed` |
| `reality_facts` | 非 `unknown` 现实状态的事实描述 |
| `reality_evidence_confirmed` | 是否显式确认现实证据引用 |
| `reality_evidence_refs` | 现实证据的声明性引用 |
| `subject_mapping_confirmed` | 代摇主体位置是否确认 |
| `subject_position` | 经确认的代摇主体爻位，范围 1 到 6 |
| `subject_mapping_refs` | 代摇主体映射引用 |
| `exam_scope` | 考试来源范围 |
| `exam_scope_confirmed` / `exam_scope_refs` | 考试范围确认位和引用 |
| `relationship_pairing_scope` | 传统关系角色适用范围 |
| `relationship_pairing_confirmed` / `relationship_pairing_refs` | 关系角色确认位和引用 |
| `pregnancy_method` | 求孕方法选择 |
| `pregnancy_method_confirmed` / `pregnancy_method_refs` | 求孕方法确认位和引用 |
| `relation_choice` | 从来源候选关系中人工收窄的六亲 |
| `relation_choice_confirmed` / `relation_choice_refs` | 六亲选择确认位和引用 |
| `relation_choice_reason` | 来源范围外人工映射时的理由 |
| `primary_position` | 调用方显式确认的原爻位置 |
| `primary_position_confirmed` / `primary_position_refs` | 爻位确认位和引用 |
| `review_notes` | 只进入请求审计和摘要的备注 |
| `source_profile_id` | 固定来源 profile，调用方不可替换 |
| `topic_policy_id` | 固定专项 policy，调用方不可替换 |
| `engineering_policy_id` | 固定工程 policy，调用方不可替换 |
| `canonical_sha256` | 序列化映射的派生摘要；`from_mapping()` 接收时可选，提供后必须与规范重算结果一致，不是 dataclass 构造字段 |

输入采用成对门禁：确认位为 `true` 时必须有对应值和引用；未确认时不得携带会伪装确认的引用。未知字段、错误摘要或不支持的 profile/policy 均拒绝。

严格文件 CLI 还要求 case、cast、chart、selection request 与 advanced context 的全部规范摘要存在，并按每个输入文件 1 MiB、JSON 最大 64 层执行资源门禁；重复键、`NaN`/`Infinity` 等非标准常量和超深 JSON 返回 `INVALID_JSON`，畸形摘要返回 `HASH_INVALID`，超限文件返回 `INPUT_TOO_LARGE`。

`case_record_sha256` 与 `event_contract_sha256` 始终必填。前者阻止同一事件合同下的旧请求跨盘重放，后者单独证明请求引用的是当前冻结合同。`contract_focus_confirmed` 是另一项声明性收据，只记录调用方确认 topic/focus 已与该合同对齐。

如果冻结 cast 已携带 `reality_facts`，选择请求不得保持 `reality_status=unknown`，也不得遗漏这些事实。运行时不会静默丢弃起卦时已冻结的现实上下文。

## 专项主题包

### 考试

| 维度 | `scope` | 处理 |
|---|---|---|
| `system_fit` | `outside_single_cast` | 单次六爻不能推出体制适配，矩阵前停止 |
| `current_exam` | `structural` | 可生成当前冻结考试事件的候选收据 |
| `position_direction` | `reality_required` | 必须依赖专业、地区、资格和竞争资料，矩阵前停止 |
| `preparation_strategy` | `reality_required` | 必须依赖成绩、时间和薄弱项资料，矩阵前停止 |

`exam_scope` 允许：

```text
not_applicable
unknown
written_or_cultural
martial
modern_civil_service_unspecified
```

- `written_or_cultural` 保留官鬼与父母两个并列来源角色；默认不压成主次；
- `martial` 只登记官鬼关系；
- `modern_civil_service_unspecified` 返回 `exam_scope_unresolved`；资料没有把现代考公无条件等同于古代文试或武试；
- 对官父双用进行人工收窄时，`relation_decision.status=caller_narrowed_source_relations`，但仍不表示最终用神。

兄弟、动静或路径数量不能被选择层补成考公取用关系或竞争分数。

### 感情复合

主题固定拆为：

```text
bond
recontact
reconciliation
stability
```

每次只能聚焦一个维度；其余维度不能由当前候选外推。`stability` 使用 `structural_with_reality_gate`，没有经确认的现实关系条件时返回 `reality_context_required`。

`relationship_pairing_scope` 允许：

```text
not_applicable
unknown
male_subject_female_spouse
female_subject_male_spouse
outside_traditional_scope
```

资料只支持经确认的传统异性婚姻角色映射：

```text
male_subject_female_spouse -> 妻财
female_subject_male_spouse -> 官鬼
```

同性、非二元、未确认关系、第三人关系和其他来源范围外情形不会套用“男财女官”。来源范围外允许显式人工映射进入审计，但 `manual_unvalidated=true`，所有候选 `contributes=false`，不会生成临时候选。

### 求孕

| 维度 | `scope` | 处理 |
|---|---|---|
| `conception_opportunity` | `advisory_only` | 只允许传统结构候选，并先处理来源方法冲突 |
| `medical_confirmation` | `professional_only` | 只能由医学检查确认，矩阵前停止 |
| `pregnancy_stability` | `professional_only` | 不由传统结构推出，矩阵前停止 |
| `medical_factors` | `professional_only` | 年龄、周期与生殖健康属于医学范围，矩阵前停止 |

`pregnancy_method` 允许：

```text
not_applicable
unresolved
children_relation
fetal_marker
```

资料同时登记子孙法和胎爻法。作者偏好子孙不会自动解除方法冲突：

- 未显式确认方法时返回 `source_method_conflict`；
- 选择 `fetal_marker` 时返回 `unsupported_method`，因为当前模型没有胎爻 selector；
- 只有显式选择 `children_relation` 后才建立子孙关系角色，同时继续保留 `FETAL_MARKER_NOT_IMPLEMENTED` 收据。

运行时不得因为胎爻未实现而静默退回子孙，也不得输出是否已孕、能否受孕、妊娠稳定、胎儿状态或医疗行动建议。

## 主体映射

- 本人摇卦固定生成 `bound_to_shi` 收据，主体位置来自 `chart.original.shi_line`；收据同时公开 `SELF-TO-SHI` 与逐页 `source_refs`，调用方不得覆盖。
- 代摇不会从 `proxy_relationship` 自行猜主体爻位。缺少确认位置和引用时返回 `subject_mapping_required`；确认后生成 `caller_confirmed` 收据。
- 代摇主体位置即使已确认，也不会把第三人婚恋升级为传统配偶自动映射；该场景仍按来源范围外处理，最多形成不贡献的人工审计候选。

主体映射只是角色收据，不改变排盘、不重算六亲，也不替代专项来源范围确认。

## 固定门禁顺序

数值越大，越先裁决：

| 顺序 | `gate_id` | 用途 |
|---:|---|---|
| 1100 | `contract_integrity_gate` | 类型、请求摘要、cast/chart 和事件合同绑定 |
| 1000 | `reality_gate` | 有证据的现实硬阻断先于结构候选 |
| 900 | `topic_safety_gate` | 专业、现实依赖或单卦范围外维度停止 |
| 800 | `contract_focus_gate` | topic/focus 必须由事件合同确认 |
| 700 | `calendar_provenance_gate` | 月建、日柱和来源声明必须完整 |
| 600 | `subject_mapping_gate` | 本人绑定世爻；代摇主体必须确认 |
| 500 | `source_scope_method_gate` | 来源适用范围和方法冲突 |
| 400 | `relation_resolution_gate` | 关系角色未决不得形成单一候选 |
| 300 | `use_position_gate` | 多爻不自动决胜；显式位置必须有收据 |
| 200 | `validity_matrix_gate` | 消费第二切片焦点、节点和路径有效性 |
| 100 | `candidate_review_gate` | 只产生待人工复核的临时候选 |

字段形状、确认位和引用配对在进入上述门禁前由 `SelectionRequest` 校验。这样专业或范围早退不能掩盖畸形现实证据。

现实硬阻断返回 `reality_blocked`，并停止在矩阵前。月日来源未确认返回 `calendar_unconfirmed`；来源已确认但月建或日柱缺一返回 `calendar_partial`。这三种状态均不生成矩阵、候选或临时候选。

所有未到达门禁仍会生成 `status=not_reached`、`reason_code=EARLIER_GATE_STOPPED` 的收据，避免报告看起来像已通过后续检查。

## 有效性矩阵调用策略

工程 policy 固定为“一份活动关系假设一份矩阵”，不是为每个可见爻伪造一次确认调用。

每个活动关系生成独立 `InterpretationRequest` 和 `ValidityRequest`：

- topic/focus 继承选择请求；
- `secondary_relations=()`，官父双用分别生成矩阵，不能借该字段激活副用神；
- 月日、现实状态和证据引用原样绑定；
- 仅当调用方显式确认 `primary_position` 并绑定引用时，才把位置传入 `InterpretationRequest`；
- 未确认位置时不伪造 `primary_position`。

因此：

- 唯一可见候选由矩阵自然生成 `focus_selection.status=unique_candidate`，可以展开到该焦点的路径；
- 多个同六亲候选保持 `focus_selection.status=ambiguous`，`path_evaluation_status=not_run_use_line_unconfirmed`；
- 调用方确认位置后生成 `focus_selection.status=confirmed` 和 `evaluation_mode=caller_confirmed_position`；
- 没有可见候选时保留伏神清单，`path_evaluation_status=not_run_no_visible_candidate`。

选择层不调用第二批私有节点、边或路径函数，也不自行复制空、破、墓、绝和多动爻算法。每份矩阵必须重新绑定当前 case record、chart、请求、上游 profile/policy 与规则轨迹；选择边界还会按当前命盘独立核对完整候选全集、焦点选择语义、原/变爻节点身份和 `selected_use` 一致性。被截断或把开放义务伪装成 `available_candidate` 的矩阵以 `VALIDITY_MATRIX_BINDING_MISMATCH` 拒绝。

## 候选与贡献条件

`SelectionCandidate` 保留：

- 候选、矩阵收据、关系角色、来源种类和节点标识；
- 爻位、动静、世应标签；
- `structural_eligibility`、`current_force`、`manifestation_state`、`role_polarity`；
- `node_state`、开放义务、解除候选；
- 矩阵 `focus_status`、路径双轴收据和冲突代码；
- 伏神可见性、激活状态、飞神和释放候选；
- 来源偏好命中；
- `contributes` 与决策代码。

来源偏好命中可以记录动爻、不空、不月破和近世，但输出固定：

```text
source_preferences_applied_to_ranking=false
```

只有同时满足以下条件，候选才可 `contributes=true`：

1. 关系角色允许贡献；
2. 候选是可见原爻；
3. 矩阵通过 `unique_candidate` 或调用方真实确认的 `confirmed` 选择该爻；
4. 节点 `selected_use=true`；
5. 矩阵最终 `focus_status=available_candidate`。

即使这些条件全部满足，输出也只使用：

```text
selection_status=single_review_candidate
provisional_candidate_id=<candidate_id>
```

`available_candidate` 和 `candidate_graph_reaches_focus` 都不表示事件会成功。伏神、变爻、多候选未确认、条件性焦点、未决焦点和来源范围外人工映射都不能贡献。

## 选择状态

正常的失败关闭或审查状态不会伪装成异常：

```text
reality_blocked
focus_outside_single_cast
professional_only
reality_context_required
contract_unconfirmed
calendar_unconfirmed
calendar_partial
subject_mapping_required
exam_scope_required
exam_scope_unresolved
relation_context_required
manual_relation_required
source_method_conflict
unsupported_method
relation_confirmation_required
manual_unvalidated_mapping
tie_needs_confirmation
hidden_candidate_needs_confirmation
no_candidate
multiple_review_candidates
single_review_candidate
validity_unresolved
validity_conditional
candidate_review_required
```

其中 `relation_confirmation_required` 既可表示来源双关系尚未收窄，也可表示调用方提供了尚未确认的关系选择。具体原因必须读取 `relation_decision`、`dependencies` 和门禁收据。

`no_candidate`、`multiple_review_candidates` 与 `candidate_review_required` 是防御性保留状态；在当前三套 profile 的完整排盘路径中预计不可达，但保留它们用于未来 profile 扩展时失败关闭，不能据此声称已有对应现实样本。

## 输出与哈希链

主要输出字段：

```text
method_id
selection_runtime_status
production_allowed
prediction_validity
source_profile
topic_policy
engineering_policy
selection_priority_table_sha256
gate_priority_receipt
upstream_validity_hashes
case_id
case_record_sha256
cast_sha256
chart_sha256
event_contract_sha256
request
selection_request_sha256
advanced_runtime_sha256
topic_pack_dimensions
selection_status
subject_mapping
relation_decision
gate_receipts
matrix_receipts
matrix_receipts_sha256
candidates
candidate_inventory_sha256
provisional_candidate_id
dependencies
trace_sha256
headline
warnings
limits
canonical_sha256
```

摘要链为：

```text
cast + event contract
  -> case record + chart
  -> selection request（内含 AdvancedContextRequest）
  -> advanced runtime
  -> generated ValidityRequest（内含 generated InterpretationRequest）
  -> ValidityMatrixReport + validity trace
  -> matrix receipts + candidate inventory + selection trace
  -> SelectionRuntimeReport
```

公开的显式摘要字段依次是 `selection_request_sha256`、`advanced_runtime_sha256`、每份矩阵收据的 `validity_request_sha256` / `validity_matrix_sha256` / `validity_trace_sha256`、`matrix_receipts_sha256`、`candidate_inventory_sha256`、`trace_sha256` 和报告 `canonical_sha256`。`AdvancedContextRequest` 与生成的 `InterpretationRequest` 位于序列化请求内部，各自的 `to_dict()` 携带规范摘要；报告没有另造一个顶层 `interpretation_request_sha256` 字段。

`matrix_receipts` 保存生成的完整 `ValidityRequest`、请求摘要、矩阵摘要、矩阵 trace、焦点选择、焦点状态、依赖、冲突代码、候选节点和路径评估状态。候选通过 `matrix_receipt_id` 回指该收据。

`upstream_validity_hashes` 另固定绑定第二批的来源 profile、工程 policy 和优先级表摘要。选择层不能用自己的 policy 覆盖第二批空破墓绝或路径裁剪合同。

## Python API

```python
from mingli.liuyao.advanced_runtime import AdvancedContextRequest
from mingli.liuyao.selection_runtime import (
    SelectionRequest,
    build_selection_runtime_report,
)
from mingli.liuyao.tables import digest

request = SelectionRequest(
    topic="exam",
    focus_dimension="current_exam",
    case_record_sha256=case_record.canonical_sha256,
    event_contract_sha256=digest(case_record.cast.event_contract.to_dict()),
    advanced_context=AdvancedContextRequest(
        calendar_context_confirmed=True,
        calendar_source_refs=("source:calendar-receipt",),
    ),
    contract_focus_confirmed=True,
    contract_source_refs=("source:event-contract",),
    exam_scope="written_or_cultural",
    exam_scope_confirmed=True,
    exam_scope_refs=("source:exam-scope",),
)

report = build_selection_runtime_report(case_record, request)
payload = report.to_dict()
```

该示例保留官父双用，因此正常结果是关系待确认，而不是自动选出一个最终用神。若调用方按冻结事件合同收窄关系或爻位，还必须同时提供相应确认位和引用。

## 明确不做

v1 不提供：

- 自由文本自动推断事件类型、考试范围、性别、关系角色、求孕方法或代摇主体；
- 将现代考公无条件等同于古代文试或武试；
- 同性、非二元或其他来源范围外关系的传统自动映射；
- 胎爻 selector；
- 多候选间的旺衰净分、动静决胜或路径条数抵消；
- 伏神自动出伏或自动取用；
- 最终用神、事件成败、成功概率、吉凶成品、确定日期或应期；
- 医疗、生育结果或专业行动建议；
- 对传统六爻现实预测准确率的评估或声明。

条件化应期属于第三阶段第四切片。本切片不会因空、破、墓、绝的解除候选或事件合同 deadline 生成任何日期候选；第四切片必须另建合同、来源审查和当前 Head 门禁，不能从本报告直接外推。
