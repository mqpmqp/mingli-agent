# 六爻确定性排盘与案例门禁 v1

## 目标

本模块把六爻工作流拆成四个互不混淆的层次：

1. **确定性排盘层**：六摇归一化、本卦、变卦、八宫、宫五行、世应、纳甲、六亲、六神和旬空。
2. **基础结构解释层**：把经确认的用神候选、月建日辰、动变、生克、冲合和旬空整理为结构化证据；有条件分歧时保留歧义。
3. **高级结构层**：自动生成月建、日辰、旬空，计算伏神飞神、月破日冲、六合六冲、十二长生、墓绝、进退神、反吟伏吟、多动爻关系图、六神角色候选、用神候选排序和规则冲突矩阵。
4. **预测治理层**：冻结事件合同，保留每个预测版本，禁止覆盖旧版，并在可核验证据出现后结算。

前三层均为可审计结构能力。解释结果固定为 `review_only`、`production_allowed=false`，所有结果继续携带 `prediction_validity=not_evaluated`。结构计算通过不代表传统预测有效，也不授权宣传准确率。

详细规则与边界：

- [基础结构解释层](INTERPRETATION_V1.md)
- [高级结构层](ADVANCED_STRUCTURE_V1.md)

## 固定约定

- 六次输入顺序固定为 `bottom_to_top`：第一次是初爻，第六次是上爻。
- 当前仅支持“字为阴、花为阳”：三字=6老阴；两字一花=7少阳；一字两花=8少阴；三花=9老阳。
- 纳甲 profile 固定为 `liuyao-wenwang-najia@1.0.0`，不在运行时混用其他流派。
- 同一 `case_id` 的六摇、问题、事件合同或起卦元数据一旦登记即冻结。六摇冲突返回 `INPUT_CONFLICT`，其他合同冲突返回 `CONTRACT_CONFLICT`。
- 高级层复用仓库现有确定性八字历法引擎，从 `completed_at` 的当地时间和固定 UTC 偏移生成节气月建、日柱和旬空。若手工月日与重算不一致，返回 `CALENDAR_CONTEXT_CONFLICT`。
- `location` 仍只是文本，不自动推断经纬度或 IANA 时区，也不自动做真太阳时校正。
- `static_table_sha256` 和高级结构表摘要用于发现版本或记录不一致，不是防伪签名。
- 测试只使用 synthetic case，不计入真实命中率。

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

# 新建或校验冻结案例
mingli-liuyao register --input cast.json > case.json
mingli-liuyao register --existing case.json --input cast.json

# 基础结构解释
mingli-liuyao interpret \
  --record case.json \
  --request interpretation-request.json > interpretation.json

# 自动月建、日辰和旬空收据
mingli-liuyao calendar-context --record case.json > calendar-context.json

# 高级结构解释
mingli-liuyao advanced-interpret \
  --record case.json \
  --request interpretation-request.json > advanced-interpretation.json

# 三层内置基准
mingli-liuyao benchmark
mingli-liuyao interpret-benchmark
mingli-liuyao advanced-benchmark

# 预测版本治理
mingli-liuyao add-version --record case.json --version version-draft.json --not-current > case-draft.json
mingli-liuyao activate --record case-draft.json --version-id V1 --at "2026-09-01T08:00:00+08:00" > case-v1.json
mingli-liuyao invalidate --record case-v1.json --version-id V1 --reason "排盘或解释错误" --at "2026-09-01T09:00:00+08:00" > case-v1-invalid.json
mingli-liuyao settle --record case-v2.json --version-id V2 --outcome hit --occurred-at "2026-09-30T16:00:00+08:00" --observed-at "2026-10-01T10:00:00+08:00" --source "官方公示" > case-settled.json
```

冲突类错误返回退出码 `2`；其他输入、篡改或状态迁移错误返回退出码 `1`。

## 解释约束

- 解释只能消费已经冻结并可重算的案例记录，不能直接接受手工拼接盘。
- `use_relation` 必须明确。多候选时，高级层可以排序，但排序领先项只是复核建议，不能静默替换显式确认的主爻。
- 排序分值只用于稳定排列证据，不是事件概率、命中率或吉凶分。
- 六合、日冲、旬空、墓绝、进退、反吟伏吟等结构出现，不自动等同于有利或不利。
- 动爻或变爻空破时，其跨位生克、回头生克和进退作用保持条件性。
- 现实阻断优先于盘面结构；资格、医学、法律、关系现状等客观条件不得被结构支持覆盖。
- 考公考编固定拆成体制适配度、本次考试、岗位方向、备考策略；感情复合固定拆成缘分牵引、复联、复合、稳定；求孕固定区分传统机会、医学确认、妊娠稳定和现实医学因素。
- 单次六爻不能独立推出体制适配度，也不能替代医疗、法律、财务等专业判断。

## 版本与结算约束

- `draft` 只是冻结草稿；只有显式发布为 `pending` 后才进入前瞻结算口径。
- 修正版发布前必须先作废旧当前版本，旧版原文、原因和时间均保留。
- `deadline` 包含截止日整日。`miss`、`partial`、`indeterminate` 最早只能在起卦时区次日登记。
- `hit` 必须记录成功标准实际成立的 `occurred_at`，且不得早于预测发布、晚于取证或越过合同截止日。
- 结算后不可覆盖记录、保留开放版本或重新追加预测。

## 当前边界

尚未实现并明确拒绝假装实现：

- 从地点文本自动推断 IANA 时区或经纬度；
- 真太阳时起卦日历；
- 合起、合绊、合住、合化的终局分类；
- 三合局、三刑、六害等完整关系体系；
- 暗动、伏神出伏和多动爻作用链的终局裁决；
- 完整旺衰总裁决；
- 应期、事件成功概率和自动付费吉凶断语；
- 真实案例准确率声明。

后续规则必须继续经过版本化、冲突测试和前瞻结算，不能把传统口诀直接升级为生产规则。
