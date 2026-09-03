# 六爻确定性排盘与案例门禁 v1

## 目标

本模块把六爻工作流拆成三个互不混淆的层次：

1. **确定性结构层**：只负责六摇归一化、本卦、变卦、八宫、宫五行、世应、纳甲、六亲、六神和旬空。
2. **结构解释层**：把经确认的用神候选、月建日辰、动变、生克、冲合和旬空整理为结构化证据；有条件分歧时保留歧义，不直接生成吉凶断语。
3. **预测治理层**：冻结事件合同，保留每个预测版本，禁止覆盖旧版，并在可核验证据出现后结算。

确定性结构层已经通过工程验证。结构解释层固定为 `review_only`、`production_allowed=false`。整个六爻模块仍不声称传统六爻具有已经验证的现实预测准确率，所有结构结果和预测版本固定携带 `prediction_validity=not_evaluated`。

结构解释层的规则、证据权重、主题边界和未实现清单见 [INTERPRETATION_V1.md](INTERPRETATION_V1.md)。

第三阶段按 [PHASE3_SCOPE.md](PHASE3_SCOPE.md) 的四个切片推进。第一批高级结构事实及月日来源门禁见 [ADVANCED_FACTS_V1.md](ADVANCED_FACTS_V1.md) 和 [ADVANCED_RUNTIME_V1.md](ADVANCED_RUNTIME_V1.md)；第二批空破墓绝、飞伏与多动爻审查矩阵见 [VALIDITY_MATRIX_V1.md](VALIDITY_MATRIX_V1.md)，逐页证据边界见 [VALIDITY_SOURCE_AUDIT_V1.md](VALIDITY_SOURCE_AUDIT_V1.md)，工程决策与验收口径见 [LIUYAO_PHASE3_VALIDITY_MATRIX_V1_REPORT.md](../../LIUYAO_PHASE3_VALIDITY_MATRIX_V1_REPORT.md)。第三切片的事件合同候选运行时见 [SELECTION_RUNTIME_V1.md](SELECTION_RUNTIME_V1.md)，新增取用来源页级审计见 [SELECTION_SOURCE_AUDIT_V1.md](SELECTION_SOURCE_AUDIT_V1.md)，实施边界见 [LIUYAO_PHASE3_SELECTION_RUNTIME_V1_REPORT.md](../../LIUYAO_PHASE3_SELECTION_RUNTIME_V1_REPORT.md)。三批均固定为 `review_only`、`production_allowed=false`，来源规则仍为 `source_only`、`human_reviewed=false`，不评估预测有效性。

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

# 结构解释：必须显式提供 topic、focus_dimension、use_relation，候选不唯一时还需 primary_position
mingli-liuyao interpret \
  --record case.json \
  --request interpretation-request.json > interpretation.json

# 结构解释层内置基准
mingli-liuyao interpret-benchmark

# 第三阶段第二批：严格校验冻结摘要并生成 review-only 有效性矩阵
python -m mingli.liuyao.validity_cli evaluate \
  --record case.json \
  --request validity-request.json > validity-matrix.json

# 有效性、冲突与两边路径裁剪合成基准
python -m mingli.liuyao.validity_cli benchmark

# 第三阶段第三切片：严格校验事件合同与上下文摘要，生成待人工复核候选
python -m mingli.liuyao.selection_cli evaluate \
  --record case.json \
  --request selection-request.json > selection-report.json

# 事件合同候选、专项主题与失败关闭基准
python -m mingli.liuyao.selection_cli benchmark

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

# 内置确定性排盘基准
mingli-liuyao benchmark
```

`mingli-liuyao` 主 CLI 的冲突类错误返回退出码 `2`，其他输入、篡改或状态迁移错误返回 `1`。第二批 `python -m mingli.liuyao.validity_cli` 单独遵循 `0=成功、1=输入/哈希/领域失败、2=命令行用法错误`。

## 结构解释约束

- 解释只能消费已经冻结并可重算的案例记录，不能直接接受一张手工拼接的盘。
- `use_relation` 必须明确；同一六亲存在多个候选爻时返回 `needs_confirmation`，不能自动挑选最符合预期的一爻。
- 月建和日柱只有在 `calendar_context_confirmed=true` 时参与解释；否则即使字段存在也会跳过。
- 六合、日冲和旬空等需要附加条件的结构固定为 `ambiguous` 且权重为零，不自动解释为合起、合绊、冲起、冲散或无效。
- 月破、月日生克、动爻生克、回头生和回头克可以进入支持/约束证据，但评分只是稳定排序，不是事件概率。
- 结果最高置信度为 `medium`，不会输出成功概率、应期或“必成/必败”。
- 已确认现实阻断使结果进入 `reality_blocked`；盘面支持因素不能覆盖资格、医学、法律、关系现状等客观条件。
- 考公考编固定拆成体制适配度、本次考试、岗位方向、备考策略；感情复合固定拆成缘分牵引、复联、复合、稳定；求孕把传统机会、医学确认、稳定性和医学因素分开。

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

已进入第三阶段审查层但仍不属于生产能力的部分：

- 伏神/飞神候选、十二长生、进退神、反吟伏吟和多动爻关系图；
- 空、破、墓、绝和飞伏自身资格的条件矩阵；
- 围绕已确认用神的多动爻候选路径与可审计裁剪。
- 事件合同驱动的考试、感情复合与求孕专项候选清单；专业维度、来源范围冲突、多爻并列和伏神均失败关闭。

尚未实现并明确拒绝假装实现的部分：

- 从公历时间自动计算月建、日辰；
- 伏神自动出伏、最终用神确认和最终飞伏作用裁决；
- 合化、三合局、暗动、真破、完整墓绝条件树和复杂旺衰；
- 多动爻能量合成与跨位变爻作用；
- 条件化应期候选、事件概率和自动自然语言吉凶预测；
- 真实案例存储、身份信息处理、命中率统计和产品准确率声明。

下一切片仅允许处理条件化应期候选；必须等第三切片自身完成审查和当前 Head CI，且仍不能把 `draft` 候选规则直接升级为生产规则。
