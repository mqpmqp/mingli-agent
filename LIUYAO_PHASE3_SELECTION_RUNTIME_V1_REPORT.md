# LiuYao Phase 3 Event-Contract Selection Runtime v1

## Decision

第三阶段第三切片定义为“事件合同驱动候选取用与专项主题包”的审查实现。它可以生成绑定来源、门禁和有效性矩阵的六亲/爻位候选，但只能交给人工复核，不能发布为最终用神、事件成败或生产断卦结论。

固定发布边界：

```text
method_id=liuyao-event-contract-selection-runtime@0.1.0
selection_runtime_status=review_only
production_allowed=false
prediction_validity=not_evaluated

source_profile_status=draft
source_evidence_level=source_only
source_human_reviewed=false
active_rule_source_family_count=1
empirical_validation_source_family_count=0

topic_policy_status=review_only
engineering_policy_status=review_only
```

## Review base

- 第三阶段范围冻结点：`2ed79e324ce502fc4b248b2d4217c3aa88f015eb`；
- 第一批来源门禁审查提交：`21864a4c05e621c5b79c65905571c50b346bab9f`；
- 第二批有效性矩阵审查 Head：`a24a384037eae5a5d3a52ac6d81597fcd9fd3423`；
- 本切片从第二批 Head 建立独立分支，不移植旧 `liuyao-full-interpretation-core` 原型；
- `EventContract`、`InterpretationRequest`、`AdvancedContextRequest` 和 `ValidityRequest` 的既有 schema 保持不变。

旧原型依赖已废弃的 `line_validity/matrix_status` 字段、缺少严格 CLI、允许未确认历法进入推荐，并可通过公开 core builder 绕过运行时。因此旧代码只作为需求反例，不作为实现基线。

## Implemented scope

核心实现分为：

- `src/mingli/liuyao/selection_profile.py`：来源 profile、专项主题 policy、工程 policy、优先级及独立摘要；
- `src/mingli/liuyao/selection_runtime.py`：冻结请求、门禁收据、来源关系裁决、矩阵收据、候选和唯一运行时入口；
- `docs/liuyao/SELECTION_SOURCE_AUDIT_V1.md`：逐页来源、来源族、作用域冲突和排除项；
- `docs/liuyao/SELECTION_RUNTIME_V1.md`：运行时合同与 API 说明。

配套 CLI、benchmark、测试、README 接线及包级导出与上述合同一致；本报告只在对应命令实际完成后记录实绩。

## Engineering decisions

### 1. 单一公开运行时入口

公开执行候选推导的运行入口只有 `build_selection_runtime_report(record, request)`。没有可绕过事件合同、现实、主题、历法、主体或来源范围门禁的低层 report builder。公开 dataclass 只是序列化和值类型，并非认证边界；手工构造或 `dataclasses.replace()` 得到的对象不具运行时来源资格，外部消费者必须用冻结输入重跑该入口，不能把可重算摘要当成签名。

请求同时固定绑定当前案例摘要与事件合同摘要：

```python
record.canonical_sha256
digest(record.cast.event_contract.to_dict())
```

事件合同自身不增加字段；两个显式摘要放在新 `SelectionRequest` 中，避免修改冻结 schema，并拒绝同合同下的跨盘旧请求。

### 2. 来源、主题和工程 policy 分离

来源 profile 只说明资料能支持哪些候选、偏好、范围和方法冲突；专项 policy 只说明项目题型拆层；工程 policy 只说明门禁与候选贡献条件。

三者使用不同 ID 和 SHA-256，公开子对象去除自身摘要后可以独立重算。第二批有效性矩阵的来源 profile、工程 policy 与优先级摘要另由 `upstream_validity_hashes` 绑定，不被第三切片覆盖。

### 3. 失败关闭的门禁次序

运行时固定优先级：

```text
1100 contract_integrity_gate
1000 reality_gate
 900 topic_safety_gate
 800 contract_focus_gate
 700 calendar_provenance_gate
 600 subject_mapping_gate
 500 source_scope_method_gate
 400 relation_resolution_gate
 300 use_position_gate
 200 validity_matrix_gate
 100 candidate_review_gate
```

字段形状、确认位和引用配对在运行时门禁前完成。早退报告把所有未到达门禁明确标成 `not_reached`，而不是省略后让调用方误判为已通过。

现实硬阻断、专业/范围外维度、未确认合同焦点、未确认或不完整历法、代摇主体缺失，以及来源范围/方法冲突均在各自门禁停止。现实阻断和历法失败不生成有效性矩阵或候选。

### 4. 一关系假设一矩阵

每个活动 `RelationRole` 生成一份 `InterpretationRequest`、`ValidityRequest` 和 `ValidityMatrixReport`。官父双用分别进入两份矩阵，不能依赖 `secondary_relations` 激活第二焦点。

选择层不会为多候选伪造 `primary_position`：

- 唯一可见候选由矩阵自然标为 `unique_candidate`；
- 多个同六亲候选保持 `ambiguous`，不展开候选专属路径；
- 只有调用方显式确认爻位并绑定引用时，矩阵才标为 `confirmed`；
- 没有可见候选时只保留伏神清单。

每份 `ValidityMatrixReceipt` 绑定生成请求、请求摘要、矩阵摘要、矩阵 trace、焦点状态、依赖、冲突代码、候选节点与路径评估状态。选择边界另按当前命盘独立校验完整候选全集、焦点选择语义、原/变爻节点身份与 `selected_use`；候选截断或把开放义务伪装成可用焦点时稳定拒绝。

### 5. 候选只形成临时复核对象

候选同时满足“来源角色允许贡献、可见原爻、矩阵真实选中、节点 `selected_use=true` 且自身为 `available_candidate`、矩阵焦点为 `available_candidate` 且没有开放焦点依赖”时，才可标记 `contributes=true`。

只有恰好一个候选贡献时，报告输出：

```text
selection_status=single_review_candidate
provisional_candidate_id=<candidate_id>
```

这不是最终用神。`available_candidate` 只表示通过第二批当前 profile 的基础门禁；`candidate_graph_reaches_focus` 只表示工程候选图可达。

发动、不空、不月破和近世可以进入来源偏好收据，但固定 `source_preferences_applied_to_ranking=false`。多候选不按偏好条数、路径数量或加载顺序决胜；伏神永不贡献；变爻不会成为独立用神候选。

## Source boundary decisions

### 考试

来源对文试保留官鬼与父母双用，对武试只登记官鬼。现代考公与古代题型的等价范围没有闭合，因此：

- `written_or_cultural` 默认输出官父双关系并要求收窄；
- `martial` 可生成官鬼单关系候选；
- `modern_civil_service_unspecified` 返回 `exam_scope_unresolved`；
- 人工收窄保留调用方收据，不改写成来源已经确定主次。

`system_fit`、`position_direction` 和 `preparation_strategy` 均在候选矩阵前停止；只有事件合同冻结的 `current_exam` 可进入结构候选。

### 感情复合

来源映射只适用于经确认的传统异性婚姻角色：男性主体问女性配偶取妻财，女性主体问男性配偶取官鬼。同性、非二元、关系未确认、第三人关系及其他范围外情形不自动套用。

范围外人工映射固定为 `manual_unvalidated_mapping`；候选只供审计，`contributes=false`。缘分、复联、复合和稳定保持四个独立事件焦点，稳定性另设现实资料门禁。

### 求孕

资料中的子孙法与胎爻法并存。作者偏好子孙不能自动解除来源方法冲突：

- 默认返回 `source_method_conflict`；
- 胎爻法返回 `unsupported_method`，不能静默回退；
- 显式选择子孙法后仍保留胎爻未实现收据；
- 医学确认、妊娠稳定和医学因素全部在专业门禁停止。

任何医疗、生育结果、概率、胎儿状态或行动建议都不进入活动规则。

## Schema and audit controls

### 输入控制

- `SelectionRequest` 使用 frozen dataclass 和 slots；
- topic/focus 只允许本切片三个专项包；
- 案例摘要与事件合同摘要始终必填，并分别与当前冻结 case 及其事件合同重算结果一致；
- 合同焦点、现实证据、代摇主体、考试范围、关系角色、求孕方法、六亲和爻位确认分别绑定确认位与引用；
- 非 `unknown` 现实状态必须同时具备 facts、显式确认和 evidence refs；
- 冻结 cast 中的现实事实不能被请求忽略；
- 本人摇卦不能覆盖主体位置，代摇不能从关系字符串猜位置；
- 固定 profile/policy 不能由调用方替换；
- 未知字段和错误 canonical SHA-256 被拒绝；
- Python `from_mapping()` 在摘要存在时重算；严格文件 CLI 还必须在反序列化前要求 case、cast、chart、selection request 与 advanced context 的全部摘要存在，并拒绝重复键、非标准 JSON 常量、超过 64 层或单文件 1 MiB 的输入。

### 输出控制

- 报告固定携带 `review_only`、`production_allowed=false` 和 `prediction_validity=not_evaluated`；
- 来源 profile 公开单一活动来源族、逐页证据、规则冲突、排除项和 `human_reviewed=false`；
- topic policy 公开三个主题的完整维度及作用域；
- engineering policy 公开门禁、候选策略、伏神/变爻边界和禁止输出；
- `gate_receipts` 为每个门禁保留顺序、状态、原因代码和明细；
- `relation_decision` 同时保留活动角色、来源候选、方法选项、冲突和人工未验证标志；
- `matrix_receipts_sha256` 与 `candidate_inventory_sha256` 分别绑定矩阵收据和候选清单；
- `trace_sha256` 绑定门禁、主体、关系、矩阵、候选、临时候选和依赖；
- `canonical_sha256` 绑定完整报告；
- 摘要用于发现漂移，不是签名，也不验证外部引用内容真实性。

主要正常状态包括：

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

其中 `no_candidate`、`multiple_review_candidates` 与 `candidate_review_required` 是防御性保留状态；当前三套 profile 的完整排盘路径预计不可达，保留它们只为未来扩展时失败关闭，不表示本批已有相应现实样本。

## Hash binding chain

```text
event contract
  -> cast_sha256
  -> case_record_sha256 + chart_sha256
  -> selection_request_sha256（请求内含 AdvancedContextRequest 及其摘要）
  -> advanced_runtime_sha256
  -> validity_request_sha256（请求内含生成的 InterpretationRequest 及其摘要）
  -> validity_matrix_sha256 + validity_trace_sha256
  -> matrix_receipts_sha256 + candidate_inventory_sha256 + selection trace_sha256
  -> selection report canonical_sha256
```

上述标签对应公开 payload 的实际摘要字段；其中最后两项的字段名分别为 `trace_sha256` 与 `canonical_sha256`。报告没有另设顶层 `advanced_context_sha256` 或 `interpretation_request_sha256`：前者位于 `SelectionRequest.advanced_context` 的序列化对象中，后者位于 `ValidityRequest.interpretation` 的序列化对象中。

报告同时绑定 selection source/topic/engineering 三类摘要，以及上游 validity source/engineering/priority 三类摘要。任何事件合同、来源确认、现实事实、主体映射、范围、方法、关系或爻位的语义变化都会改变相应请求和下游摘要。

## Verification contract

最低本地验收命令与冻结实绩如下：

| 验收 | 命令 | 实际结果 |
|---|---|---|
| 编译 | `python -m compileall -q src tests scripts` | PASS |
| 聚焦测试 | `PYTHONPATH=src python -m pytest -q tests/test_liuyao_selection_runtime.py tests/test_liuyao_selection_cli.py` | `100 passed` |
| 候选基准 | `PYTHONPATH=src python -m mingli.liuyao.selection_cli benchmark` | `61/61 checks=true` |
| 全部六爻测试 | `PYTHONPATH=src python -m pytest -q tests/test_liuyao*.py` | `241 passed` |
| 全仓三门禁分区 | 下列 fast + benchmark + real-case；每项由 `test_gates` 唯一分派 | `797 passed, 4 environment-deselected, 31 subtests passed`；共覆盖 `801/801` 个收集项 |
| Fast gate | `PYTHONPATH=src python -m mingli.test_gates --timeout-seconds 300 fast -- -q` | `642 passed, 159 deselected, 16 subtests passed` |
| Benchmark gate | `PYTHONPATH=src python -m mingli.test_gates --timeout-seconds 3600 benchmark -- -q`，另精确排除下述 4 个隔离打包用例 | `43 passed, 758 deselected, 15 subtests passed` |
| Real-case gate | `PYTHONPATH=src python -m mingli.test_gates --timeout-seconds 600 real_case -- -q` | `112 passed, 689 deselected` |
| 无隔离构建 | `python -m build --no-isolation` | PASS；sdist、wheel 及 wheel 内 `61/61` 基准均通过 |
| 标准隔离构建 | `python -m build` | ENVIRONMENT BLOCKED；受限网络无法取得 `setuptools>=68`，第二批基线可复现 |
| 差异与受保护范围 | `git diff --check` 及受保护路径 diff | PASS；`spec/`、`knowledge/`、`.github/` 零改动 |
| 远端 CI 边界 | GitHub Actions | 父级 #58 `a24a384` 的 Core/PWA 均成功；本切片为非 `main` Base 的堆叠 PR，工作流待改基 `main` 后运行 |

4 个环境排除项都是会清空代理并在新隔离环境安装构建依赖的既有包装测试：`test_derived_contracts`、`test_phase7_fact_graph`、`test_phase8_rule_evaluation` 与 `test_phase9_strength_quantification` 各 1 项。未排除任何规则、运行时或第三切片测试；相同安装失败已在未修改的父级基线复现，不能归因于本切片，也不能替代后续联网 CI。

组合和对抗验收另完成：

- `4,096` 个动静组合 × `3` 个主题生成 `12,288` 份主报告，另加 `27` 份前置门禁报告，共 `12,315` 份；
- 共核验 `12,288` 份有效性矩阵、`16,000` 个候选和 `795` 次确定性重放；
- case、event contract、异请求矩阵、候选全集截断、开放义务伪装、未决路径伪装和 validity trace 篡改共 `7/7` 个对抗负例稳定拒绝；
- 哈希复算、唯一贡献、多候选不伪造 primary、伏神/变爻不贡献及递归禁止输出检查失败 `0`；
- 运行时、来源、公开合同三路独立终审均为 blocker/major/minor/nit `0`。

冻结摘要快照：

```text
source_profile_sha256=0c4e07fd72831aa2bfd2f5a7647a693efa0b2c3c366847c0ff6529689887dc50
topic_policy_sha256=58f1a12fdd95cd754860c06604199f44e269099ea7d074a8997790b4e5029c0f
engineering_policy_sha256=957b4da225e881bd52d2981d3c9bf7860663d6b9158b3625cc7457095a8544f5
selection_priority_table_sha256=2d9d4919eb98f1175d4a20b91b31aa41c7705224f3fa5525bda6daacf2b9f27e
benchmark_report_sha256=4de131fe4b82e588878c2dc1bb7c5bb0db53ef089a88c9b4c2faae4015f3a4b8
```

聚焦测试和 benchmark 至少覆盖：

- 合同绑定、未知字段和嵌套摘要篡改；
- 三个公开子档案独立重算和不可变性；
- 三个主题包的全部维度；
- 官父双用、现代考公范围、关系适用范围和求孕方法冲突；
- 本人世爻与代摇主体门禁；
- 现实阻断、历法未确认和历法部分上下文；
- 唯一候选、多候选、条件性、未决、相反路径和仅伏神；
- 发动不决胜、伏神不贡献、变爻不独立取用；
- 请求、矩阵、候选、轨迹和完整报告的确定性哈希；
- 递归禁止最终用神、成败、概率、确定日期和应期字段。

上述通过项只证明当前工程合同、确定性和失败关闭行为，不证明传统规则有效或现实预测准确。

## Protected scope

本切片不修改或扩大：

- `spec/`、`knowledge/`、来源 PDF、真实案例和 CI 配置；
- 第一、第二阶段的排盘、事件合同、预测版本与结算语义；
- 第一批高级事实和历法来源门禁；
- 第二批有效性矩阵、空破墓绝、飞伏和路径裁剪合同；
- 八字、紫微、奇门、梅花、PWA 或生产服务；
- 任一规则生命周期到 `reviewed` 或 `verified` 的升级。

## Known limits and risks

- 活动规则只有一个来源族，且 `human_reviewed=false`；
- 来源、事件合同、历法、现实、主体和范围引用只检查调用方声明存在，不读取或验证引用内容；
- 没有自动语义解析将自由文本事件映射为考试范围、关系角色或求孕方法；
- 现代考公与古代文武试的对应未闭合；
- 资料没有覆盖同性、非二元、第三人或其他非传统婚姻关系的自动六亲映射；
- 胎爻 selector 未实现；
- 多候选不在未确认状态下展开候选专属路径；
- 来源偏好没有总排序，不参与候选决胜；
- 伏神不会自动出伏或取用，变爻不会成为独立取用候选；
- 第二批矩阵仍受其自身旺衰、暗动、合化、三合、真破和冲库未闭合范围限制；
- 尚无合格前瞻真实案例，不能评估或宣传预测准确率；
- 不输出最终用神、事件成败、概率、吉凶、确定日期或应期。

## Next gate

当前结果允许创建以 #58 分支为 Base 的堆叠评审 PR，但不允许合并。只有 #58 合并、本 PR 改指 `main`，并以届时不变的当前 Head 通过 Core/PWA CI 后，第三切片才具备合并评审资格；标准隔离构建的联网门禁也必须在该 CI 中补跑。

第三阶段第四切片是条件化应期候选，当前明确不进入。即使本报告产生 `single_review_candidate`，也不能从空破墓绝解除候选、事件合同 deadline 或路径状态直接生成日期；第四切片必须另建请求合同、来源 profile、工程 policy、测试和当前 Head CI 门禁。
