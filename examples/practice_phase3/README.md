# PROSPECTIVE_REAL_CASE_VALIDATION_V1

本目录只含 synthetic 工程验收样例。五组样例均不是真人，不进入真人 pilot，也不能用于准确率或商业能力宣传。`pilot_empty.json` 是首批 10 人的空登记台账，所有席位均未登记；真实导入入口仍关闭。

现有 `mingli training` CLI 增加 `case-create`、`case-show`、`freeze-prediction`、`outcome-append`、`claim-adjudicate`、`validation-summary`、`pilot-show`。每个命令都使用 `--input FILE --store PATH --synthetic --json`，stdin 可用 `--input -`。`freeze-prediction` 沿用现有 validation 命名和底层冻结实现；本适配器加入分池与 claim 门禁。

在仓库根目录执行下列命令；再次运行时换一个尚不存在的专用 store：

```powershell
$env:PYTHONPATH='src'
E:\python.exe examples/practice_phase3/run_examples.py --store .pytest_cache/phase3-cli-example-run1
```

runner 通过独立 CLI 进程执行每个 JSON 的 `steps`，检查 exit code、错误码、每池状态和空台账。它只写新建的本地 synthetic store，不访问网络、排盘或真实资料。

| 样例 | 工程验收结果 |
| --- | --- |
| l2_hit.json | L2 retrospective_blind，逐条事实与裁决完成，synthetic hit |
| l2_miss.json | L2 retrospective_blind，逐条事实与裁决完成，synthetic miss |
| l3_pending.json | L3 prospective，未来窗未结束，pending，不计 hit/miss |
| given_leakage.json | 把 GIVEN 复述伪装为 bounded claim，自动 unscorable，计分裁决 exit 2 |
| expired_window.json | L3 使用过期窗，冻结 exit 2，没有生成预测记录 |

真实证据等级与模拟轨道分开保存：所有 synthetic 案例及其预测记录的 `evidence_level` 必须是 L0；用 `simulated_validation_track` 表达 retrospective_blind / prospective 等离线模拟流程，不能将实际证据等级写成 L2/L3。时间、GIVEN 与 pending 工程逻辑依据模拟轨道执行，真实证据口径仍为 L0。

`synthetic_engineering.by_simulated_track` 及兼容 `pools` 的 population 明确为 synthetic。`cases` 按真实证据等级汇总实际存储记录，total 与 l0_synthetic 包含合成案例，角色计数也包含其离线 case_role；其中 real_registered_cases 明确为 0。`claims`、`retrospective_validation`、`prospective_validation` 只使用真人口径。顶部 `l0_synthetic_count` 统计所有 synthetic，不论它模拟什么轨道。五组 runner 汇总为 l0_synthetic_count=5；l1_historical_count / l2_retrospective_count / l3_prospective_count / prospective_pending_count 均为 0。禁止 `overall_accuracy`，模拟 pending 只出现在 synthetic_engineering。

`scorable` 仅表示离线 claim 合同满足结构和保守措辞门禁；所有记录的 `accuracy_eligible=false`。真人 `registered_cases=0`、`eligible_sample_count=0`、`accuracy=null`、`metrics=null`、`status=not_evaluated`，`commercial_release_hold=ACTIVE`、`public_accuracy_claim_allowed=false`。L2 的 confidence_calibration_status 为 insufficient_sample；L2 和 L3 的病例数、eligible/scorable/verdict 数、by_domain、by_claim_type 独立返回，L3 另有 pending/lost/refused/missing。

案例接口要求 pilot_batch_id、case_role（development / pilot_evaluation / holdout_evaluation），本批默认 pilot_evaluation。consent 只接收 synthetic_not_applicable 骨架，不伪造真人同意。给定事实放在 given_facts，依据放在 sources；hidden_answer_fields 和 future_outcome_fields 仅接收英文机器字段名空槽，禁止对象、答案内容或相互重叠。`visible_input_hash` 只覆盖 question、sources、given_facts，预测 input_manifest_sha 必须匹配该 hash。prediction、后续事实/反馈和裁决不参与可见输入 hash。

L2 hit/miss 的 GIVEN 只有“你正在求职”，不含收到面谈通知的答案。given_leakage 专门用“你已经收到面谈通知”对“你收到一次岗位面谈通知”的近义改写复述，仍自动 unscorable。检查还覆盖把已知答案错误标为 independent 来源的情况。

每条 claim 必须有 claim_id、domain、事件类型 claim_type、validation_track、predicted_event_or_state、predicted_direction、event_window、confidence、specificity_level、given_dependency_ids、exclusion_conditions、basis_source_ids，以及单一结果变量和核验标准。claim_type 使用 current_state / prior_event / future_event / timing / outcome / relationship_action / exam_result / fertility_stage / other；support/contradict 沿用 V2 方向枚举，bounded/vague 属于 specificity_level。`claim_contracts` 返回完整字段与派生 scorable，不能用调用方自填的计分标记放行。GIVEN 引用或近义复述、泛化句、免责声明、建议、风险提示、复合句不计分。保守规范化与相似度只能拦截常见改写，不能证明任意自然语言都没有泄漏；盲测独立性及文本语义仍需人工核验。

事实 `evidence_snapshot` 与 `claim-adjudicate` 裁决分开存放。事实观察时间必须在 claim 窗内，接收时间晚于冻结，裁决不得早于证据接收。即使提前收到事实，L3 窗口结束前也只能 pending。裁决要求 verdict（与兼容 status 一致）、timing_verdict、direction_verdict、adjudicator 和 adjudication_status=single_reviewer。未来的 reviewed_consensus 尚未实现，当前拒绝使用；产品质量盲评不能替代 outcome adjudication。partial 必须给 reason；没有证据不得 hit/miss/partial；`case_correct` 不属于合同。

记录由 TrainingStore 独占创建，复用 `validation_freeze` 和 `validation_reality` 冻结、完整性检查，以及 `real_case_learning_v2` 的时间窗语义与 HOLD 常量。没有重写 V2 完整案例构建、反馈回放、规则晋级或生产校准管线。Phase 1/2 的反馈隐藏、原快照保留、行为回归和人工评审仍由已有模块负责。

预测修订使用新 prediction_id 并提供 revision_of，保留原快照；修订不能变成新的独立准确率样本。裁决修订使用新 adjudication_id、较晚时间和 supersedes，旧裁决保留。摘要按 as_of 隐藏尚未接收的裁决，保留各池独立计数。JSON 摘要是离线工程读数，不能代替人工盲评或真实前瞻验证。

尚未实现：真人接入、10 人 pilot 注册、真实准确率、商业发布、生产服务和自动命理算法验证。后续解除真实接入边界需要新的明确授权和相应隐私、独立复核门禁。
