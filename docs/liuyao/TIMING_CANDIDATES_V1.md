# 六爻第三阶段：条件化时间候选 v1

## 目标

本切片只回答：

> 已确认的用神候选在什么“地支触发条件”下值得观察；这些条件是否与调用方提供并注明来源的现实流程窗口相交？

它不自行把地支换算成公历日期，不给确定应期，不生成成功概率。

固定边界：

```text
method_id=liuyao-conditional-timing-candidates@0.1.0
timing_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

## 上游门禁

时间候选必须同时消费：

1. 冻结案例 `LiuYaoCaseRecord`；
2. 事件合同哈希绑定后的 `SelectionRuntimeRequest`；
3. 已确认且有来源引用的月建、日柱上下文；
4. 候选取用报告和有效性矩阵。

以下任一情况都停止时间推演：

- 现实已形成硬阻断；
- 用神候选仍并列；
- 只有伏神候选且未确认；
- 事件焦点不支持单次六爻；
- 月日上下文未通过来源门禁。

## 符号触发

对已经人工可复核的可见候选，只生成地支条件：

```text
use_branch_value
use_branch_clash
use_branch_combine
void_fill
void_clash
month_break_value
month_break_combine
changed_branch_value
```

其中：

- 同支、冲、合仅是触发关系；
- 冲空不预设为冲起或冲散；
- 月破逢值、逢合不预设为自动解除；
- 变爻逢值只作次级观察，回头生克仍需通过有效性矩阵；
- 同一地支命中多个触发，不做置信度叠加。

## 现实时间锚点

系统不自行算日期。调用方若要生成日期范围候选，必须提供：

```json
{
  "anchor_id": "exam-stage",
  "label": "官方考试流程窗口",
  "start_date": "2026-09-01",
  "end_date": "2026-09-30",
  "branch_tags": ["酉"],
  "source_refs": [
    "source:official-schedule",
    "source:verified-branch-map"
  ]
}
```

硬约束：

- `source_refs` 不能为空；
- `branch_tags` 必须是有效地支；
- 锚点不得早于起卦完成日期；
- 锚点不得超过事件合同截止日期；
- 同一请求中 `anchor_id` 必须唯一。

运行时只校验字段、范围和引用存在性，不读取外部链接，也不证明日程或地支映射真实正确。

## 输出状态

```text
reality_blocked
selection_unresolved
calendar_unconfirmed
symbolic_only
anchored_candidates
no_matching_anchor
```

- `symbolic_only`：只有地支条件，没有有来源的日期锚点；
- `anchored_candidates`：外部锚点与至少一个条件匹配；
- `no_matching_anchor`：提供了锚点，但其地支标签未匹配当前条件。

所有日期候选固定为：

```text
status=candidate_only
```

不能改写为“会发生”“必应”“大概率成功”。

## CLI

```bash
python -m mingli.liuyao.timing_cli benchmark

python -m mingli.liuyao.timing_cli evaluate \
  --record case.json \
  --request timing-request.json
```

## 尚未实现

- 公历、节气、干支时间自动换算；
- 自动核验现实日程与地支标签；
- 合起、合绊、冲起、冲散、冲墓、出墓的最终条件树；
- 三合成局与合化；
- 多动爻最终作用路径对应的时间触发；
- 精确到日、时的自动应期；
- 统计概率与准确率校准；
- 付费自然语言断卦成品。
