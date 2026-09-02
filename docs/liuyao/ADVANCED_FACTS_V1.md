# 六爻第三阶段：高级结构事实层 v1

## 目标

本阶段第一切片只把可复算的高级结构转换为机器事实，不直接输出吉凶、成败、应期或成功概率。它消费第一阶段已经冻结并可重算的 `LiuYaoCaseRecord`，输出：

- 缺失六亲及伏神/飞神候选定位；
- 月支、日支下的十二长生阶段标签；
- 动爻化进、化退结构；
- 原爻与变爻的地支同、合、冲及五行有向关系；
- 内卦、外卦、全卦逐支反吟/伏吟候选；
- 多动爻之间的五行与地支关系图边。

固定状态：

```text
method_id=liuyao-advanced-structural-facts@0.1.0
advanced_fact_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

## 固定口径

### 伏神与飞神

当本卦六爻没有某一六亲时，按本卦所属八宫的本宫纯卦查找该六亲所在爻位，将纯卦该爻登记为伏神候选，将当前卦同爻位登记为飞神。

本层只记录：

- 缺失六亲；
- 伏神候选爻位、纳甲、地支和五行；
- 同位飞神；
- 飞伏之间的五行有向关系。

本层不判断伏神是否得月日、是否出伏、是否受压、是否可用，也不把“存在伏神”直接解释为事情有或没有结果。

### 十二长生

v1 使用版本化五行顺行口径：

```text
木长生亥
火长生寅
金长生巳
水长生申
土长生申
```

之后按十二地支顺行映射：长生、沐浴、冠带、临官、帝旺、衰、病、死、墓、绝、胎、养。

该标签只说明所选 profile 下的阶段位置。`墓`、`绝`不会在本层自动变成负分；`长生`、`帝旺`也不会自动变成正分。若采用其他流派口径，必须另建 profile 和表摘要，禁止静默替换。

### 进神与退神

v1 固定识别：

```text
寅→卯、巳→午、申→酉、亥→子
丑→辰、辰→未、未→戌、戌→丑
```

反向为退神。这里只识别地支变化，不判断该爻是否真正推进、衰退或应验。

### 反吟与伏吟

v1 使用明确标注的 `branchwise-fanyin-fuyin@1.0.0` 结构 profile：

- 同一范围内原卦与变卦逐爻地支全部相同，登记伏吟候选；
- 同一范围内原卦与变卦逐爻地支全部六冲，登记反吟候选；
- 范围分别为内卦、外卦和全卦；
- 对应范围没有动爻时，不把静卦误标为伏吟。

这是逐支结构识别，不等于所有传统流派对反吟、伏吟的完整定义，也不能直接推出反复、灾祸、失败或必然变动。

### 多动爻关系图

对每一对动爻登记：

- 第一动爻到第二动爻的五行有向关系；
- 两动爻地支若同、合或冲，登记对应关系边；
- 每个动爻还登记变爻相对原爻的五行关系和地支关系。

图边不自动参与最终方向评分。空、破、墓、日月、用神定位和作用优先级尚未闭合前，任何一条边都只能作为条件事实。

## Python API

```python
from mingli.liuyao.advanced_facts import build_advanced_fact_report

report = build_advanced_fact_report(case_record)
payload = report.to_dict()
```

主要输出字段：

```text
method_id
advanced_fact_status
production_allowed
prediction_validity
advanced_table_sha256
case_id
chart_sha256
facts
missing_relations
context_status
warnings
limits
canonical_sha256
```

每条事实含：

```text
fact_id
category
scope
positions
relation
branches
elements
value
profile
conditional
technical
plain
```

## 当前能力边界

尚未进入本切片：

- 从公历时间自动推算月建、日辰；
- 月日来源真实性核验；
- 伏神旺衰、出伏和飞伏作用优先级；
- 三合成局、合化；
- 暗动；
- 入墓、冲墓、墓库开合的条件树；
- 空、破、墓、绝与动变的综合有效性；
- 多动爻跨位传递和最终作用路径；
- 自动取用、元神/忌神最终裁决；
- 应期、成功概率和自然语言吉凶结论。

这些能力将在后续切片按“事实表 → 条件规则 → 冲突矩阵 → 专项主题 → 应期候选”的顺序推进，不能把口诀直接并入生产判断。
