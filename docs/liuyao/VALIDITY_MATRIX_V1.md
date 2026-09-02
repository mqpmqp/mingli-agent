# 六爻第三阶段：作用资格与冲突矩阵 v1

## 目标

本切片回答的不是“事情能不能成”，而是：

> 某爻、某变爻、某伏神候选或某条多动爻关系，在当前已确认上下文下，是否具备进入后续判断的基础资格？

固定边界：

```text
method_id=liuyao-validity-conflict-matrix@0.1.0
validity_matrix_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

## 输入

矩阵同时消费：

1. 已冻结、可重算的 `LiuYaoCaseRecord`；
2. 第二阶段 `InterpretationRequest`，用于确定事件焦点、显式用神和现实证据；
3. 第三阶段 `AdvancedContextRequest`，用于校验月建、日柱是否经过调用方来源确认。

解释请求与高级上下文的 `calendar_context_confirmed` 必须一致；两边均提供来源引用时，引用集合必须一致。任何不一致都 fail closed。

## 爻有效性状态

```text
unknown_context
available_candidate
unresolved
conditional
```

含义：

- `unknown_context`：月日上下文未通过来源门禁，不能判断作用资格；
- `available_candidate`：通过当前基础门禁，但仍不代表作用已被验证；
- `unresolved`：存在日冲、六合、旬空、墓绝等解释条件，当前不选择其中一种传统说法；
- `conditional`：存在月破等明确约束，或其他必须先闭合的条件。

矩阵不会使用“完全失效”“必然有力”等绝对化标签。

## 当前处理的条件

### 月日与旬空

- 月支六冲：登记 `month_break`；
- 日支六冲：登记 `day_clash_effect_unresolved`；
- 月合、日合：分别登记合的影响未决；
- 旬空：登记 `void_effect_unresolved`；
- 十二长生处于墓、绝：登记影响未决。

月破与旬空同时出现时，生成 `VOID_AND_MONTH_BREAK` 冲突；但这仍不是“该爻彻底无用”的结论。

### 动爻与变爻

- 动爻受约束时，生成 `MOVING_BUT_CONDITIONAL`；
- 变爻空破、墓绝或上下文不足时，生成 `CHANGED_LINE_CONDITIONAL`；
- 回头生克只有原爻与变爻都通过门禁时，才登记为 `active_candidate`；
- 多动爻图边同样需要来源与目标都通过门禁。

`active_candidate` 只表示当前基础条件允许进入下一层，不表示生克结果已经成立，更不是成功概率。

### 伏神与飞神

矩阵登记：

- 伏神候选与飞神的双向五行关系；
- 伏神候选是否月破、旬空、日冲或逢合；
- 候选状态：`candidate_only`、`constrained_candidate`、`unresolved_candidate`、`unknown_context`。

不自动判断出伏，也不把伏神候选直接升级为用神。

### 现实证据

第二阶段已经核验为 `blocking` 的现实条件，生成 `REALITY_HARD_BLOCK`，优先于盘面候选。系统仍保留结构事实用于审计，但不会用结构支持覆盖现实中的资格限制、已有新人、医学检查、法律限制或其他终局事实。

## 输出状态

```text
reality_blocked
unsupported_focus
needs_confirmation
calendar_unconfirmed
conditional
structurally_available
```

其中 `structurally_available` 也仅表示通过当前基础门禁，不等同于吉、能成或会在某时发生。

## CLI

```bash
python -m mingli.liuyao.validity_cli benchmark

python -m mingli.liuyao.validity_cli evaluate \
  --record case.json \
  --request validity-request.json
```

请求结构：

```json
{
  "interpretation": {
    "topic": "general",
    "use_relation": "妻财",
    "primary_position": 4,
    "calendar_context_confirmed": true,
    "calendar_source_refs": ["source:calendar"],
    "reality_status": "unknown"
  },
  "advanced_context": {
    "calendar_context_confirmed": true,
    "calendar_source_refs": ["source:calendar"]
  }
}
```

## 尚未实现

- 暗动、冲散的完整条件树；
- 合起、合绊、合住、合化；
- 三合成局；
- 冲墓、墓库开合；
- 伏神出伏和飞伏最终作用；
- 日月旺衰综合优先级；
- 多动爻跨位变爻传递与最终路径裁剪；
- 自动取用、事件专项最终判断；
- 应期、成功概率和付费断卦成品。

这些内容必须在本矩阵之上继续实现，不能回退到单句口诀直接下结论。
