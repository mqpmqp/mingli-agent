# 六爻结构解释层 v0.1

## 目标与状态

本层位于确定性排盘之后、自然语言预测之前，只把传统六爻中的条件关系整理为可复核证据。

固定状态：

```text
interpretation_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

这些标记表示：代码可以用于规则审查、案例复盘和前瞻验证，但不能据此宣传预测准确率，也不能把结构性“偏支持/偏约束”改写成“会成功/会失败”。

## 资料与转述边界

规则族参考《周易与预测学》《周易预测宝典》及《未知之门》中纳甲六爻常见的用神、月建日辰、动变、生克、六合六冲和旬空框架。实现只保留可机械核验的关系，不复制原文歌诀，不把书中案例当作现实有效性证明。

以下内容属于工程约定，而不是传统预测准确率结论：

- 支持与约束权重只用于稳定排序结构证据，不是概率；
- 月令权重高于日辰，表示解释优先级，不表示统计效应量；
- 歧义证据权重固定为零，防止单句口诀直接翻转结论；
- 最高置信度封顶为 `medium`，任何结果都不生成成功概率或应期。

## 输入合同

解释必须基于已经冻结并通过哈希重算的 `LiuYaoCaseRecord`，另提供 `InterpretationRequest`：

```json
{
  "topic": "exam",
  "focus_dimension": "current_exam",
  "use_relation": "官鬼",
  "primary_position": 3,
  "secondary_relations": ["父母", "兄弟"],
  "calendar_context_confirmed": true,
  "reality_status": "mixed",
  "reality_facts": [
    "已报名并通过资格审核",
    "最近一次模考排名仍低于计划入围线"
  ],
  "notes": []
}
```

约束：

1. `use_relation` 必须明确为父母、兄弟、子孙、妻财或官鬼。
2. 同一六亲只有一个候选爻时可自动选取；存在多个候选时必须填写 `primary_position`。
3. 指定爻位的六亲与 `use_relation` 不一致时返回 `USE_GOD_MISMATCH`。
4. 月建、日柱即使已进入排盘，也只有在 `calendar_context_confirmed=true` 时才参与解释。
5. `reality_status` 标记为 `supportive`、`blocking` 或 `mixed` 时，必须附带现实事实。
6. 已确认的现实阻断优先于盘面支持因素。

## 结构证据

### 月建与日辰

当前支持：

- 同支；
- 五行同类、生、克、泄耗；
- 月建六冲用神候选，登记为月破结构；
- 日辰六冲用神候选，登记为条件性日冲；
- 月建或日辰与用神候选六合；
- 经确认日柱计算出的旬空。

当前处理原则：

- 月破作为较强约束证据，但仍保留“是否有解”的限制；
- 日冲不自动判为暗动、冲起或冲散；
- 六合不自动判为合起、合绊、合住或合化；
- 旬空不自动判为无效，旺空、动空、冲空等条件尚未完成时只列为歧义。

例如巳与申只会输出：

```text
relation=month_combine 或 day_combine
polarity=ambiguous
weight=0
```

不会仅凭“巳申合”给出有利或不利结论。

### 动爻与变爻

当前支持：

- 其他动爻对用神候选的生、克、同类、泄耗和被制；
- 动爻与用神候选的六合、六冲，仅作条件性证据；
- 用神候选发动后的回头生、回头克、化泄、比和和耗力；
- 变爻六合、六冲、旬空只作条件性证据。

本层不分析其他动爻之变爻跨位作用，避免在规则优先级尚未冻结时扩大推断。

### 元神、忌神和其他角色

每一爻都会按其五行与用神候选五行的关系标记为：

- 用神候选；
- 元神候选；
- 忌神候选；
- 同类候选；
- 泄耗候选；
- 受用神所制候选。

“候选”不能省略。只有元素关系并不足以证明该爻在当前事件中实际发挥相应作用，还需要动静、月日、空破和其他条件。

## 证据平衡

输出分别累计：

```text
support_score
restrict_score
ambiguous evidence
```

结构状态只有四种：

- `supportive`：支持证据明显多于约束；
- `restrictive`：约束证据明显多于支持；
- `mixed`：两者接近或同时存在；
- `undetermined`：没有足够的可评分证据。

最终状态还可能是：

- `needs_confirmation`：用神爻位不唯一；
- `unsupported_focus`：当前焦点不应由单次六爻判断；
- `insufficient_context`：资料不足；
- `reality_blocked`：已确认现实阻断覆盖盘面支持因素；
- `analyzed`：仅完成结构证据分析。

## 专项主题边界

### 考公考编

固定拆为：

1. `system_fit`：体制适配度，不能由单次六爻单独推出；
2. `current_exam`：本次考试或录用事件，可做结构分析；
3. `position_direction`：必须结合专业、资格、地区和竞争数据；
4. `preparation_strategy`：必须结合真实成绩和备考数据。

“适合体制内”和“本次能否上岸”不得合并成同一个结论。

### 感情复合

固定拆为：

1. `bond`：缘分牵引；
2. `recontact`：复联可能；
3. `reconciliation`：复合可能；
4. `stability`：复合后的稳定可能。

每次只能把一个维度设为当前焦点，其余维度标记为需要独立事件合同，不能从“有缘”直接跳到“会稳定复合”。

### 求孕

固定拆为：

1. `conception_opportunity`：传统结构观察；
2. `medical_confirmation`：只能由医学检查确认；
3. `pregnancy_stability`：不能由受孕机会自动推出；
4. `medical_factors`：年龄、周期和生殖健康等现实因素优先。

### 健康

只允许输出传统结构观察并固定提示医疗优先，不允许诊断疾病、判断治疗效果或替代就医。

## CLI

```bash
mingli-liuyao interpret \
  --record case.json \
  --request interpretation-request.json

mingli-liuyao interpret-benchmark
```

解释结果包含请求哈希、命盘哈希、用神选择收据、证据、冲突、主题维度、结构评分、置信度、限制和结果哈希。

## 尚未实现

- 自动历法换算和月建、日辰来源验证；
- 伏神；
- 合化；
- 进神、退神；
- 反吟、伏吟；
- 十二长生、墓绝和复杂旺衰优先级；
- 多动爻复杂传递与三合局；
- 应期；
- 成败概率；
- 自动发布付费断卦成品；
- 真实前瞻案例准确率。

上述项目只能在规则条件、反例、冲突优先级和前瞻验证建立后逐项加入，不能因为传统资料中存在相应术语就自动进入生产运行时。
