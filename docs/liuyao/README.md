# 六爻确定性排盘与案例门禁 v1

## 目标

本模块把六爻工作流拆成两个互不混淆的层次：

1. **确定性结构层**：只负责六摇归一化、本卦、变卦、八宫、宫五行、世应、纳甲、六亲、六神和旬空。
2. **预测治理层**：冻结事件合同，保留每个预测版本，禁止覆盖旧版，并在可核验证据出现后结算。

它不解释旺衰、生克、合冲、空破、墓绝、用神或应期，也不声称传统六爻具有已经验证的现实预测准确率。所有结构结果和预测版本固定携带 `prediction_validity=not_evaluated`。

## 固定约定

- 六次输入顺序固定为 `bottom_to_top`：第一次是初爻，第六次是上爻。
- 当前仅支持“字为阴、花为阳”：
  - 三字 = 6 = 老阴；
  - 两字一花 = 7 = 少阳；
  - 一字两花 = 8 = 少阴；
  - 三花 = 9 = 老阳。
- 纳甲 profile 固定为 `liuyao-wenwang-najia@1.0.0`，不在运行时混用其他流派。
- `static_table_sha256` 覆盖爻值语义、八卦/六十四卦、八宫世应、纳甲、五行生克、六亲所依赖表、六神和旬空表。任何这些确定性表发生变化，摘要都会变化。
- 日柱和月支由调用方显式提供；本模块不自行推算历法。缺少日柱时，六神和旬空返回 `null`，不会猜测。
- 同一 `case_id` 的六摇、问题、事件合同或起卦元数据一旦登记即冻结。六摇冲突返回 `INPUT_CONFLICT`，合同冲突返回 `CONTRACT_CONFLICT`。
- 事件合同的 `deadline` 按起卦完成时间 `completed_at` 的时区解释，并包含截止日整日。其他时间戳即使使用不同偏移，也会先换算到该时区；`miss`、`partial`、`indeterminate` 最早只能在截止日后的下一当地日期登记。
- 真实案例不得作为测试夹具提交。测试只使用去身份化的 synthetic case，不能计入真实命中率。
- 64 卦、八宫、世应与纳甲另用冻结的外部结构夹具做差分校验；该夹具只是第二实现交叉检查，不替代传统文献审查，也不证明预测有效。

## 输入示例

```json
{
  "case_id": "SYNTHETIC-001",
  "question": "本批次是否进入最终公示名单",
  "line_values": ["三个字", "两字一花", "两字一花", "一字两花", "两字一花", "两字一花"],
  "event_contract": {
    "target_event": "进入最终公示名单",
    "deadline": "2026-12-31",
    "success_criteria": "官方最终公示名单包含目标人",
    "evidence_requirement": "官方公示或可核验录用通知"
  },
  "completed_at": "2026-08-31T21:57:00+08:00",
  "location": "测试地点",
  "casting_mode": "self",
  "coin_convention": "字为阴，花为阳",
  "month_branch": "申月",
  "day_ganzhi": "丙午日",
  "reality_facts": []
}
```

## CLI

```bash
# 只做确定性排盘校验
mingli-liuyao chart --input cast.json

# 新建案例记录
mingli-liuyao register --input cast.json > case.json

# 对同一 case_id 做幂等登记或冲突检查
mingli-liuyao register --existing case.json --input cast.json

# 新增冻结草稿；草稿尚不进入前瞻结算
mingli-liuyao add-version --record case.json --version version-draft.json --not-current > case-draft.json

# 显式发布后才成为 current pending 版本，published_at 必须带时区
mingli-liuyao activate \
  --record case-draft.json \
  --version-id V1 \
  --at "2026-09-01T08:00:00+08:00" > case-v1.json

# 也可直接登记已冻结的 pending 版本；version.json 必须包含 published_at
mingli-liuyao add-version --record case.json --version version.json > case-v1.json

# 纠错：保留旧版并标记 invalid，不覆盖原文
mingli-liuyao invalidate \
  --record case-v1.json \
  --version-id V1 \
  --reason "纳甲表错误" \
  --at "2026-09-01T08:00:00+08:00" > case-v1-invalid.json

# 结算：只有 current pending 版本可结算
# occurred-at 是成功标准实际成立时间；observed-at 是取得并核验证据的时间
mingli-liuyao settle \
  --record case-v2.json \
  --version-id V2 \
  --outcome hit \
  --occurred-at "2026-09-30T16:00:00+08:00" \
  --observed-at "2026-10-01T10:00:00+08:00" \
  --source "官方公示" > case-settled.json

# 内置确定性基准
mingli-liuyao benchmark
```

冲突类错误返回退出码 `2`；其他输入、篡改或状态迁移错误返回退出码 `1`。

## 版本与结算约束

- `draft` 只是冻结草稿，不计入前瞻预测；只有显式填写 `published_at` 并转为 `pending` 后，才进入结算口径。
- `current_version_id` 只能指向一个 `draft` 或 `pending` 版本。
- `pending` 版本必须是当前版本；不能同时保留多个待结算版本。
- 发布修正版前，必须先把旧当前版本标记为 `invalid`，并填写作废原因和时间。
- `deadline` 是包含整日的事件窗口终点。`miss`、`partial`、`indeterminate` 在截止日整日内均禁止登记，最早可在起卦时区的次日 `00:00:00` 登记。
- `hit` 必须记录成功标准实际成立的 `occurred_at`，且该时间不能早于预测发布、不能晚于取证时间、不能越过事件合同截止日。CLI 省略该参数时默认等于 `observed_at`；证据晚于事件出现时应显式填写二者。
- 预测版本必须在起卦完成后创建，并在事件合同截止日当天或之前发布；截止日判断统一换算到起卦完成时间的时区，不能通过更换 UTC 偏移绕过。
- 作废、发布、事件发生和结算取证时间不得倒置。
- `occurred_at` 与 `observed_at` 必须是带时区的 ISO 8601 时间，不能只写日期。
- 案例结算后不可覆盖结算记录，不可保留开放版本，也不可重新追加预测版本。
- 载入记录时会由冻结输入重算命盘，并核对记录中已有的 SHA-256。该机制用于发现记录不一致，不是防伪签名；能修改全部内容并重新计算哈希的主体仍可生成另一份自洽记录。

## 当前边界

尚未实现并明确拒绝假装实现的部分：

- 从公历时间自动计算月建、日辰；
- 伏神、进退神、反吟、伏吟；
- 月破、日破、入墓、绝、六合、六冲及旺衰优先级；
- 用神自动选取、应期推断和自然语言断卦；
- 真实案例存储、身份信息处理、命中率统计和产品准确率声明。

下一阶段只能在独立规则审查、冲突表和前瞻结算样本建立后推进，不能把 `draft` 候选规则直接升级为生产规则。
