# 梅花易数输入门禁 v1

## 目标

在排卦和解释之前，先把“问的到底是什么、怎么算成、到什么时候结算”固定下来。输入不唯一时停止，不通过补故事弥补缺项。

## 一、强制字段

### 1. 案例元数据

| 字段 | 要求 |
|---|---|
| `case_id` | 唯一、不可复用；真实案例使用外部去标识 ID |
| `cast_at` | 带时区的 ISO 8601 时间 |
| `location` | 城市级即可；不需要精确地址 |
| `casting_mode` | 数字、时间、物象、声音、文字等 |
| `profile_id` | 必须显式选择确定性排卦 profile |
| `raw_cast_input` | 保存原始数字、顺序或已规范化计数 |
| `repeat_cast` | 是否为同题重复起卦；若是，必须提供首卦 ID 和现实变化 |

### 2. 事件合同

| 字段 | 要求 |
|---|---|
| `event_class` | 从固定类别中选择，不用披露敏感细节 |
| `question_text` | 一次只问一个核心结果 |
| `target_event` | 唯一目标节点，不写“整件事顺不顺” |
| `success_criteria` | 能由第三方证据或明确事实核验 |
| `deadline` | 包含截止日整日；无截止日不得做命中统计 |
| `natural_time_unit` | `hours/days/weeks/months/quarters/years` |
| `current_stage` | 起卦当时已经走到哪一步 |
| `reality_constraints` | 资格、审批、距离、资金、法律、健康、关系状态等硬条件 |
| `privacy_mode` | `full` 或 `category_only` |

## 二、事件类别

V1 固定以下类别：

```text
message
meeting
relationship_recontact
relationship_reunion
exam
employment
contract
payment
lost_item
relocation_short
relocation_long_term
migration_identity
medical
legal
other
```

`other` 只能用于方向性研判；若仍无法判断自然时间单位，返回 `DATA_INSUFFICIENT`。

### 迁移类必须细分

- `relocation_short`：短期搬住、旅行、临时驻留，身份和长期生活结构不变。
- `relocation_long_term`：长期更换城市或国家，但不以法律身份改变为成功标准。
- `migration_identity`：法律或制度身份、长期居住地、实际生活轨迹同步变化。

这三类不能在预测后互相替换。普通搬家补充成“身份与生活轨迹彻底改变”，属于 `QUESTION_DRIFT`。

## 三、“能成”必须转成唯一节点

以下节点不能混成一个成功标准：

1. 资格或身份获批；
2. 出发日期正式确定；
3. 人实际离开原居住地；
4. 到达目标地；
5. 身份、登记或合同正式生效；
6. 在目标地稳定居住。

例如：

```text
target_event=身份正式生效并完成实际迁入
success_criteria=有可核验文件证明身份已生效，且当事人已入住目标地并连续居住 30 日
deadline=2027-06-30
natural_time_unit=months
```

如果客户只想问“何时收到批复”，必须另建事件合同，不能与“何时彻底完成迁移”混用。

## 四、隐私最小披露

`privacy_mode=category_only` 时，允许隐藏：

- 具体国家、城市、机构和证件名称；
- 涉及人物姓名；
- 敏感家庭、婚姻、法律或职业原因。

但不得隐藏：

- 事件类别；
- 成功标准；
- 当前阶段；
- 截止日；
- 是否存在现实硬阻断。

无法披露这些最小字段时，只能低置信谈“快慢、阻力、主动或被动”等一般趋势，不得给具体月份或日期。

## 五、问题漂移与合同修订

以下任一变化都构成问题漂移：

- `event_class` 改变；
- `target_event` 改变；
- `success_criteria` 改变；
- 原本未知的现实事实改变事件性质；
- 时间尺度由日级升级为月级或年级；
- 客户把“消息出现”改成“最终完成”。

处理规则：

1. 原预测版本保留，不覆盖；
2. 原版本标记 `non_countable_reason=question_drift`；
3. 创建新的事件合同和预测版本；
4. 新版本不得把起卦后获知的事实伪装成起卦前已知输入；
5. 如新增信息只是澄清原合同中已经明确的同一节点，可记录 `clarification`，但必须说明未改变成功标准。

## 六、重复起卦

同一目标事件、同一成功标准、同一截止日下短期重复起卦，默认返回 `REPEAT_CAST`。只有出现以下现实变化才允许新起一卦：

- 审批状态发生变化；
- 新合同、新考试、新一轮招聘等形成新的独立事件；
- 对方已经作出可核验的新行动；
- 原事件合同已经结算。

“焦虑了”“想再确认一次”“不喜欢上一卦”不构成新事件。

## 七、门禁判定顺序

```text
检查原始输入是否完整
  -> 检查 profile 是否唯一
  -> 检查是否重复起卦
  -> 检查事件类别和自然时间单位
  -> 检查目标事件与成功标准
  -> 检查截止日和现实阶段
  -> 检查是否发生问题漂移
  -> READY / 停止状态
```

## 八、合格与不合格示例

### 不合格

```text
问题：一件隐私事项具体哪一天能成
数字：60、70、50
```

原因：事件类别、成功标准、截止日、自然时间单位、三数字 profile 均未冻结。

### 合格的隐私表达

```text
事件类别：migration_identity
目标事件：身份正式生效并完成实际迁入
成功标准：可核验身份生效，且已实际入住目标地连续 30 日
当前阶段：申请已提交，等待决定
截止日：2027-06-30
自然时间单位：months
隐私模式：category_only
排卦 profile：meihua-numeric-three-explicit@1.0.0
原始数字：上卦 60、下卦 70、动爻 50
```

该表达保护隐私，同时足以确定事件尺度和结算节点。
