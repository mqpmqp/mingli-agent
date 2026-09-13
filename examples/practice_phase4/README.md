# Phase 4 连续真人 Pilot 控制层

本目录只包含明确标记为 `synthetic=true` 的工程验收输入，不含真人资料，也不会占用真人 Pilot slot。Phase 4 复用 Phase 3 的冻结预测、OutcomeObservation、claim 裁决与 L2/L3 分池，复用既有 withdrawal tombstone 引用；新增内容只负责 Pilot 开始时间、连续筛选顺序、10 个 slot、claim 上限、显式 grace period、质量反馈独立账本和完整性汇总。

当前项目没有授权真人案例，因此实际状态必须保持：

```text
registered_real_cases = 0
eligible_real_cases = 0
accuracy = null
status = not_evaluated
product_accuracy_claim_allowed = false
commercial_release_hold = ACTIVE
```

`pilot-start` 固定目标为 10，并显式保存 `pilot_start_at` 与 `grace_period_days`。Phase 4.1 要求先通过 `pilot-candidate-intake` 写入不可覆盖的候选 receipt，再把返回的 `candidate_id` 交给 `pilot-screen`。`pilot-screen` 自动派发连续 slot；调用方不能自选 slot，也不能传入“跳过 eligible”决定。synthetic dry-run 只获得 `simulated_slot`，`assigned_real_slot` 永远为 null。重复人员、超量 claim、未授权、未去标识、校盘失败或冻结未就绪均 fail closed。

`pilot-mature` 使用 `maturity_at = event_window.end + grace_period_days`。到期前只能 pending；到期后无事实反馈不能自动记 miss，只能显式保留 lost_to_followup 或 awaiting_manual_confirmation。`pilot-quality-append` 只保存产品质量标签，合同不接受 outcome verdict；预测结果继续由 Phase 3 claim adjudication 保存。

`pilot-revision-freeze` 调用 Phase 3 的冻结入口并增加 revision receipt；v1 原记录不会被覆盖。`pilot-withdraw` 只保存绑定既有 withdrawal tombstone hash 的 Pilot 控制记录，slot 不回收，实际原始/派生资料撤回仍由现有 TrainingStore / Real Case Learning V2 执行。

在仓库根目录使用尚不存在的临时 store 运行五组入口级验收：

```powershell
$env:PYTHONPATH='src'
python examples/practice_phase4/run_examples.py --store .pytest_cache/phase4-cli-example-run1
```

五组分别覆盖 L2 hit、L2 miss、L3 pending、L3 matured + feedback、L3 matured + no feedback。它们全部是 synthetic 工程 fixture，runner 会再次确认真人 slot 仍为空、真实计数仍为 0、准确率仍为 null、发布仍 HOLD。

真实 Pilot 写入必须使用仓库外的非 synthetic store，并由现有隐私/授权流程提供去标识化 ID、冻结 hash 与 withdrawal tombstone 引用。本工单没有导入、生成或补造任何真人案例，也没有开启产品准确率声明。
