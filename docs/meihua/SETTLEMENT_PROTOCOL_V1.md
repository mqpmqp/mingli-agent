# 梅花易数前瞻结算协议 v1

## 目标

把预测与结果分开保存，禁止覆盖旧判断，区分“方向是否正确”和“时间是否命中”，并明确哪些案例不能进入统计。

## 一、版本状态

```text
draft -> pending -> settled
             \-> invalid
```

- `draft`：尚未正式发送给客户，不计入前瞻样本；
- `pending`：已经发布，等待事件结果；
- `settled`：已取得证据并完成结算；
- `invalid`：排卦、输入、合同或发布过程存在错误，保留原文但不计数。

任何修正都必须新增版本；不得覆盖原版本文本、时间窗口或置信度。

## 二、发布前冻结字段

```text
case_id
contract_version
prediction_version
created_at
published_at
event_class
target_event
success_criteria
deadline
natural_time_unit
direction_claim
confidence
primary_window
backup_window
process_events
conditions
falsification_condition
known_reality_facts
unknowns
profile_id
chart_hash
countable
```

`published_at` 必须带时区，且不得早于起卦完成时间、不得晚于合同截止日。

## 三、结算字段

```text
outcome
occurred_at
observed_at
evidence_source
evidence_quality
direction_result
timing_result
notes
reviewer
```

- `occurred_at`：成功标准实际成立的时间；
- `observed_at`：取得并核验证据的时间；
- 两者必须分开，且 `occurred_at <= observed_at`；
- 迟到证据可以证明事件在截止日前发生，但不能把截止日后发生的事件记为命中。

## 四、结果类别

### 事件结果

```text
hit
partial
miss
indeterminate
cancelled
```

- `hit`：完整成功标准在截止日前成立；
- `partial`：只有过程节点成立，完整成功标准未成立；
- `miss`：截止日后确认目标未发生，或发生了明确相反结果；
- `indeterminate`：证据不足、失联或无法判断；
- `cancelled`：事件被现实原因取消；取消不自动等于预测正确或错误。

### 方向结果

```text
correct
incorrect
not_scored
```

### 时间结果

```text
primary_window
backup_window
outside_windows_before_deadline
outside_deadline
not_applicable
not_scored
```

方向与时间必须分开。例如“最终成了，但在主、备窗口之外”可记为方向正确、时间错误，不能整体写成命中。

## 五、多节点事件的结算

迁移类可以记录过程节点，但只按冻结的 `target_event` 结算：

```text
approval_received
travel_date_fixed
departed
arrived
status_effective
stable_residence_reached
```

若目标事件是“身份生效并稳定居住”，收到批复只能作为 `process_event`，不能记为 `hit`。

## 六、不可计数条件

以下案例固定 `countable=false`：

- 问题在发布后发生 `QUESTION_DRIFT`；
- 结果或关键事实在发布前已经被解释者知晓；
- 没有成功标准或截止日；
- 排卦 profile 未冻结；
- 同题重复起卦后只挑选最像结果的一卦；
- 客户只反馈“感觉准”，无可核验事件；
- 解释者本人负责最终评分且无独立复核；
- 合成夹具、经典旧例或回顾性案例；
- 真实案例未经授权或无法充分去标识。

不可计数不等于删除。案例仍应保留失败原因，以便改进输入门禁。

## 七、反证和停止规则

每个 pending 版本必须写明：

```text
到哪个日期
若仍未出现哪个关键事实
则方向判断降级或记为 miss/indeterminate
```

主窗口未发生时只能进入预先冻结的后备窗口；后备窗口也未发生后，禁止继续无限顺延。

## 八、评估指标

初始校准阶段至少分别统计：

1. 排卦结构错误率；
2. 输入门禁拦截率；
3. 问题漂移率；
4. 方向正确率及事件基准率；
5. 主窗口、后备窗口覆盖率；
6. 窗口宽度；
7. 高/中/低置信度校准；
8. `partial` 与 `indeterminate` 比例；
9. 按事件类别分层后的样本量和错误类型。

“总命中率”不能把感情、考试、迁移、消息和失物混在一起，也不能把宽时间窗与窄时间窗视为同等难度。

前 30 个合格前瞻案例只作为流程校准批次，不构成产品准确率证明。任何准确率声明仍需预注册评估方案、独立评分、基准比较、置信区间和隐私/商业审核。

## 九、存储边界

- 仓库只允许合成夹具、空模板和不含私人信息的聚合报告；
- 真实案例存入 Git 外受控位置；
- 保存授权、撤回、用途和保留期限；
- 删除直接标识符，并评估年龄、地点、职业、日期组合造成的间接识别风险；
- 客户撤回授权后，派生摘要和统计也必须按政策处理。

## 十、人工复盘格式

```text
原预测：
实际结果：
方向结果：
时间结果：
错误发生在：输入 / 排卦 / 体用 / 主题映射 / 应期尺度 / 现实变化 / 其他
是否有问题漂移：
是否存在事后解释：
本案是否计数：
需要修改的规则：
需要保留的反例：
```

失败案例不得因“不好看”而删除；高置信失败优先复盘。
