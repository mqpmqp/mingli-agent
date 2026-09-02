# 六爻第三阶段：事件合同驱动的候选取用 v1

## 目标

本切片不宣称“自动定准用神”，只回答：

> 在事件合同、主题、主体关系、历法来源和现实证据均已登记的前提下，哪些可见爻或伏神候选值得优先交给人工复核？

固定边界：

```text
method_id=liuyao-contract-driven-selection-runtime@0.1.0
selection_runtime_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

## 两层结构

- `selection_core.py`：生成主题维度、六亲候选和底层排序收据；
- `selection_runtime.py`：绑定冻结事件合同哈希，校验现实证据形态，阻断不允许自动取用的焦点，并撤销“仅因发动而决胜”的候选排序。

正式调用应使用 `selection_runtime.py`，不能直接把底层 core 的排序当成最终用神。

## 事件合同绑定

调用方必须提供冻结事件合同的 SHA-256：

```text
event_contract_sha256 = sha256(canonical(event_contract))
```

运行时会与案例中的 `event_contract` 重算结果比较。哈希不一致时返回 `CONTRACT_BINDING_MISMATCH`，防止把一个事件的取用请求套到另一个事件上。

`contract_source_refs` 只用于保留来源引用；运行时不会自行读取或验证外部内容。

## 专项主题映射

### 考公考编

固定拆分：

1. `system_fit`：体制适配度，不允许由单次六爻自动取用；
2. `current_exam`：本次考试/录用事件，主候选六亲为官鬼，父母与兄弟作为次级观察；
3. `position_direction`：岗位方向，需要专业、地区、资格、岗位表和竞争数据；
4. `preparation_strategy`：备考策略，需要真实成绩、剩余时间和薄弱科目。

只允许第二项进入结构候选排序。

### 感情复合

固定拆分：缘分牵引、复联、复合、稳定。男性问感情默认配偶六亲候选为妻财，女性为官鬼；性别未知时返回 `gender_required`。稳定性必须补充现实关系条件，不能只看盘面。

### 求孕

- `conception_opportunity`：子孙爻候选，只作传统结构观察；
- `medical_confirmation`、`pregnancy_stability`、`medical_factors`：专业判断范围，任何六亲 override 都不能绕过。

### 综合事件

`general/current_event` 不内置默认六亲。调用方必须显式提供 `primary_relation_override` 和 `override_reason`，并接受审计。

## 主体映射

本人摇卦时，世爻作为本人结构位置；显式 `subject_position` 必须与世爻一致。

代摇时不得自动把世爻等同被测者。必须同时提供：

```text
subject_mapping_confirmed=true
subject_position=1..6
```

否则返回 `subject_mapping_required`。

## 候选排序

候选先按有效性矩阵的离散状态排序：

```text
available_candidate
unresolved
conditional
unknown_context
```

发动只作为描述性提示，不允许在同一有效性层级中自动决定最终用神。多个可见候选同层级时返回 `tie_needs_confirmation`。

只有伏神候选时返回 `hidden_candidate_needs_confirmation`，不会自动升级为最终用神。

显式爻位若与六亲不一致，沿用解释层的 `USE_GOD_MISMATCH` 门禁。

## 现实证据

`reality_status` 只能是：

```text
unknown
supportive
blocking
mixed
```

非 `unknown` 时必须同时提供 `reality_facts` 和 `reality_evidence_refs`。现实阻断优先于候选排序，输出 `reality_blocked`。

## CLI

```bash
python -m mingli.liuyao.selection_cli benchmark

python -m mingli.liuyao.selection_cli evaluate \
  --record case.json \
  --request selection-request.json
```

请求示例：

```json
{
  "selection": {
    "topic": "exam",
    "focus_dimension": "current_exam",
    "querent_gender": "unknown",
    "contract_focus_confirmed": true,
    "contract_source_refs": ["source:event-contract"],
    "calendar_context_confirmed": false,
    "reality_status": "unknown"
  },
  "event_contract_sha256": "<64-hex>"
}
```

## 输出状态

```text
contract_unconfirmed
subject_mapping_required
gender_required
manual_relation_required
unsupported_focus
reality_context_required
reality_blocked
no_candidate
hidden_candidate_needs_confirmation
tie_needs_confirmation
recommended_visible_candidate
explicit_position_confirmed
```

`recommended_visible_candidate` 仍只是人工复核建议，不是最终用神、吉凶结论、应期或成功概率。

## 尚未实现

- 对题意与事件合同语义的自然语言自动核验；
- 自动判断世应所代表的全部人物关系；
- 伏神出伏和最终可用性；
- 完整旺衰、暗动、合化、冲墓和多动爻最终路径；
- 专项成败判断；
- 条件化应期候选；
- 概率校准和付费自然语言成品。
