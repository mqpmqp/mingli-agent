# 付费交付合同

版本：`paid-delivery-contract@1.0`
适用入口：`mingli.paid_delivery.run_paid_delivery`

## 1. 三档模式与展示意图

付费层级和展示意图是两个不同维度：

- `PaidTier.COMMENT`：评论区短答；
- `PaidTier.PRIVATE`：私聊定向答复；
- `PaidTier.PAID_699`：九项综合交付；
- `focused_question`：默认，只回答当前专题；
- `follow_up`：只处理续问新增范围；
- `comment`：适合短答；
- `full_reading`：调用方明确要求时使用，但新路径仍不回退旧固定八段。

`follow_up` 的范围约束优先于付费层级，防止续问重复整份报告。

## 2. 699 九项合同

`paid_699` 默认且按顺序包含：

1. 资料确认；
2. 核心结论和分层置信度；
3. 前事校验；
4. 当前核心矛盾；
5. 当前主题深断；
6. 时间窗口；
7. 现实行动方案；
8. 玄学辅助；
9. 风险、反证和复盘节点。

九项是付费交付合同，不是旧 Yuan 八段模板。输出只展开 `QuestionIntent.domain` 指定的专题，不为凑长度加入其他主题。

## 3. 内容规则

### 3.1 资料确认

- 完整出生资料进入现有确定性八字引擎；
- 未确认图片明确显示限制说明；
- 已确认图片只承认四柱静态事实；
- 六爻资料只确认收件和引擎不可用，不生成卦象；
- 缺失字段逐项列出并自动降级。

### 3.2 核心结论

- 显示 `chart_confidence`、`interpretation_confidence`、`event_confidence`、`action_confidence`；
- 使用高、中、低，不使用未经校准的概率；
- 每个重大判断同时写出成立条件与反证；
- 强现实反证必须以“现实边界优先”进入正文。

### 3.3 前事校验

只列已经提供、可核对的现实字段。泛化描述、作者自述、付款记录或事后补写不算命中证据。

### 3.4 当前主题深断

感情复合固定拆为：缘分牵引、复联可能、复合可能、稳定可能，并优先处理对方新人、失联、婚姻、家庭、安全与法律边界。

考公考编固定拆为：体制适配度、上岸可能、考试运、岗位方向、备考策略、文昌与功名辅助，并优先处理官方资格、真实成绩、岗位竞争和招录目标。

其他专题只使用其对应规则包，不跨主题扩写。

### 3.5 时间窗口

没有经过 forward calibration 的具体日期依据时，输出明确拒绝具体日期。任何观察窗口都要绑定 `ReviewCheckpoint`；没有复盘点的时间性文本不得进入交付。

### 3.6 现实行动与玄学辅助

现实行动在前，传统文化辅助在后。`paid_699` 默认展示玄学辅助模块，但允许其结论为“当前不建议具体仪式”。建议模块必须包含现实动作、次数上限和预算上限。

### 3.7 风险与复盘

末节再次记录成立条件、现实反证和到期复盘点。交付时只生成 `pending_forward_test` 收据，不提前结算。

## 4. 称骨严格 opt-in

默认路径：

- 不调用 `calculate_chenggu`；
- 不在结果字段或文本中加入相关模块；
- 不输出骨重或歌诀。

只有调用方已经确认用户明确点名，并设置：

```json
{
  "question_intent": {
    "bone_weight_requested": true
  }
}
```

才会运行现有确定性权重算法。即使显式启用，仍不补写歌诀，也不把结果当作事件证据。

## 5. 续问合同

续问只输出：

- 续问结论；
- 续问现实行动；
- 玄学辅助；
- 复盘节点。

续问不得重新输出资料确认或完整九项报告，不得加入未被问及的专题。

## 6. 安全语言

交付必须拒绝：

- 包上岸、保证复合、保证发财或类似结果保证；
- 医疗替代、恐吓、灾祸营销和层层追加；
- 建议借钱、贷款或牺牲基本生活费用做仪式；
- 没有户型与可靠测量时给出具体坐向；
- 没有校准资料时使用概率或具体日期包装确定性。

术语如需出现，后面必须紧跟白话解释。当前实现示例为“确定性排盘（同一规范化输入会得到同一结果）”。

## 7. 输入与输出示例

```python
from mingli.paid_delivery import run_paid_delivery

result = run_paid_delivery(
    {
        "case_id": "synthetic:example",
        "created_at": "2026-08-29T12:00:00+08:00",
        "anchor_year": 2026,
        "paid_tier": "paid_699",
        "question_intent": {
            "question": "只看事业",
            "domain": "career",
            "render_intent": "focused_question",
            "bone_weight_requested": False,
        },
        "birth": {
            "gender": "female",
            "calendar": "solar",
            "birth_date": "1990-03-15",
            "birth_time": "10:30",
            "timezone": "Asia/Shanghai",
            "birth_location": {"country": "中国", "city": "上海"},
        },
        "reality_constraints": {},
        "evidence_quality": "self_reported",
    }
)
```

`PaidDeliveryResult` 返回输入校验收据、确定性 Runtime 收据、四维置信度、证据链、反证、规则与建议 ID、可选模块、结构化 sections、待到期评测收据、最终文本和 canonical hash。

## 8. 免责声明

最终文本使用项目固定免责声明，全文只出现一次并位于末行。本文档不改变现有 `PRODUCT_RELEASE_HOLD`，也不构成付费效果或实盘准确率证明。
