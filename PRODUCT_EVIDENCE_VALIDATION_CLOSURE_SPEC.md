# Product Evidence & Validation Closure

## 1. 状态与基线

- 基线分支：`main`
- 技术 RC 基线：`v0.2.0-rc1`
- 工作分支：`validation/p19-p22-product-evidence-v1`
- 当前产品状态：`technical_rc_only_product_hold`
- 当前预测有效性：`prediction_validity=not_evaluated`

本阶段不新增命理业务能力，不改写 P16–P24 已通过的技术 RC 行为，只关闭 P19 内容合规与 P22 产品证据验证缺口。

## 2. 严格范围

仅允许以下六项工作：

1. P19 核心包不含歌诀原文的发布门禁；
2. P22 Gold/Silver 分层验证闭环；
3. 盲评与评分合同；
4. 校准、覆盖、拒答及分场景表现统计；
5. 生成 `PRODUCT_VALIDATION_REPORT.md`；
6. 达到预先登记门槛后，再决定是否制作 `v0.2.0-rc2`。

## 3. 明确非目标

本阶段禁止：

- 新增或扩展八字、紫微、奇门、风水、择日等业务规则；
- 修改 P16–P24 的领域判断语义、Evidence Fusion 优先级或 Yuan 八段结构；
- 为提高指标而修改既有预测输出；
- 使用合成案例、回填标签或事后改写预测冒充真实验证；
- 把完整称骨歌诀、现代白话解释或歌诀资源写入 RC2 核心包；
- 提交原始身份信息、联系方式、精确地址或可重新识别的案例材料；
- 在验证完成前声明产品准确率、预测有效性或优于人工命理师。

## 4. P19 RC2 核心包边界

### 4.1 保留能力

- P19 确定性称骨算法；
- `chenggu-common-table-r1@0.1` 骨重表及年、月、日、时权重；
- `display_weight`、`canonical_hash` 与既有计算约定；
- 固定输出 `verse_available=false`。

### 4.2 删除范围

- 完整称骨歌诀原文不属于 RC2 范围；
- 歌诀 package-data 与现代白话解释不得进入核心包；
- 歌诀来源、版权或内容审核不再是 RC2 blocker；
- P19 数值算法与歌诀内容继续解耦，任何后续内容包不得改变骨重计算结果。

### 4.3 状态与未来扩展

- `p19_verse_blocker=removed_by_design`；
- `p19_algorithm_status=usable`；
- `p19_verse_pack_status=future_optional_pack`；
- optional verse pack 必须是后续独立版本、独立资源、独立审核，不属于 `v0.2.0-rc2` 决策门禁。

## 5. P22 合格真实案例合同

### 5.1 最低资格

每个真实案例必须同时满足：

- 明确同意：`consent_status=granted`；
- 已去标识：`deidentified=true`；
- 来源已授权：`source_ref` 使用受控授权引用；
- 有独立同意记录 ID；
- `provenance_class=external_observation`；
- 出生资料、现实背景和目标主题达到预登记的最低完整度；
- 预测生成时间早于结果确认时间；
- 预测输入、输出、模型/规则版本和 canonical hash 已冻结；
- 观察结果具有日期、来源和独立标注；
- 预测者不能看到观察标签，观察标注者不能修改预测文本。

### 5.2 数据边界

仓库只允许提交：

- 去标识后的结构化案例清单；
- 冻结预测哈希、观察标签、评分结果和聚合指标；
- 合成合同测试数据。

原始案例叙述、同意文件和可能重新识别个人的信息必须存放在授权的私有数据位置。公共仓库中的记录使用不可逆案例 ID，不保存姓名、联系方式、精确地址或证件信息。

### 5.3 数量门槛

- validation closure 允许 Gold 与 Silver 合并计数，但必须满足 `qualified_validation_cases>=30`、`gold_cases>=10`、`silver_cases<=20`、`comparable_claims>=100` 和 `scenario_coverage>=3`；
- 产品准确率声明只允许 Gold 计数，必须满足 `eligible_gold_cases>=30` 且 `prospective_only=true`；
- Silver 只能进入辅助验证与 validation closure，不能计入产品准确率声明；
- Bronze 永不计入 benchmark；
- 合成案例永不计入真实案例数量或产品指标；
- 不合格案例必须保留排除原因，禁止静默删除；
- validation closure 通过不自动产生准确率宣传权。

## 6. 盲评与评分合同

### 6.1 冻结顺序

1. 登记案例与输入完整度；
2. 运行固定版本生成预测；
3. 保存预测正文、结构化 claims、置信度、版本和 SHA-256；
4. 锁定预测记录；
5. 由独立观察标注者录入结果；
6. 两名独立评分者评分；
7. 分歧进入裁决，不覆盖原评分；
8. 生成可重复的最终评分记录。

### 6.2 评分单位

评分必须在预登记 claim 级别完成，不以整篇文本的主观“像不像”评分。每个 claim 至少包含：

- `claim_id`
- `scenario`
- `time_scope`
- `predicted_label`
- `confidence`
- `observed_label`
- `score_status`: `match | mismatch | unresolved | abstained | out_of_scope`
- 两名评分者结果与裁决结果

允许标签继续使用受控集合；新增标签必须先修改合同和测试，不能在看见结果后临时扩展。

### 6.3 盲评完整性

必须检测并阻止：

- 预测时间晚于观察结果；
- 预测冻结后内容或置信度变化；
- 同一人员同时生成预测和完成最终观察标注；
- 缺少版本、哈希、时间戳或来源；
- 用未预测内容事后解释为命中；
- 将 `unresolved` 或 `abstained` 计为正确。

## 7. 指标合同

所有指标同时输出分子、分母、样本量和不可计算原因，禁止只给百分比。

### 7.1 覆盖率

- 案例覆盖率：至少有一个可比较 claim 的合格案例数 / 合格案例数；
- claim 覆盖率：进入可比较评分的 claim 数 / 预登记且可观察的 claim 数。

### 7.2 拒答率

- claim 拒答率：`abstained` claim 数 / 预登记且可观察的 claim 数；
- 案例拒答率：全部可观察 claim 均为 `abstained` 的案例数 / 合格案例数。

拒答是安全行为，不得直接按错误处理；但必须单独报告覆盖损失。

### 7.3 校准

对带数值置信度且可比较的 claim，至少报告：

- 固定置信度分箱中的预测均值、实际命中率和样本量；
- Brier score；
- Expected Calibration Error；
- 无足够样本时返回 `insufficient_sample`，不得外推。

### 7.4 分场景表现

至少分开报告：

- `career`
- `wealth`
- `relationship`
- `career_exam`
- `reconciliation`

每个场景报告样本量、覆盖率、拒答率、match/mismatch/unresolved、校准指标及置信区间或明确的样本不足状态。禁止将总体结果替代分场景结果。

## 8. 预登记与防止事后调参

在首次解盲前必须冻结：

- 案例纳入/排除标准；
- claim 列表与标签定义；
- 评分规则；
- 指标公式；
- 分场景规则；
- RC2 的数值门槛和人工评审门槛。

数值门槛不得根据最终结果倒推。本规范不擅自设定产品准确率门槛；该门槛必须在解盲前形成单独、已审核的预登记文件。

## 9. 最终交付物

必须生成：

- P19 来源与版权登记及审核结果；
- P22 案例资格清单与排除清单；
- 盲评/评分合同及 Schema；
- 可重复执行的指标计算器；
- 合成合同测试与真实数据私有运行说明；
- `PRODUCT_VALIDATION_REPORT.md`；
- 机器可读验证摘要及 canonical hash；
- 源树与隔离 wheel 一致性证据。

`PRODUCT_VALIDATION_REPORT.md` 至少包含：

- 基线版本与数据截止日期；
- 合格案例数量及场景分布；
- 排除原因统计；
- 盲评完整性检查；
- 覆盖率、拒答率、校准和分场景表现；
- 局限性和潜在偏差；
- `prediction_validity` 状态；
- 是否允许产品准确率声明；
- 是否建议制作 `v0.2.0-rc2`。

## 10. RC2 决策门禁

只有全部满足时，才允许进入 `v0.2.0-rc2` 决策：

- P19 核心包不含歌诀原文、歌诀 package-data 或现代白话解释，且继续输出 `verse_available=false`；
- validation closure gate 通过：`qualified_validation_cases>=30`、`gold_cases>=10`、`silver_cases<=20`、`bronze_counted=0`、`comparable_claims>=100`、`scenario_coverage>=3`；
- `consent_rate=100%`、`pii_leak_count=0`、Gold 的 `freeze_hash_coverage=100%`、`double_review_coverage=100%`；
- 盲评完整性检查全部通过；
- 预登记指标计算成功且无静默排除；
- 源树与隔离 wheel 结果一致；
- unittest、pytest、sdist/wheel、隔离安装、package-data、rollback、whitespace、protected-path 全部通过；
- `PRODUCT_VALIDATION_REPORT.md` 完整生成；
- 人工评审确认结果没有过度解释。

即使通过上述门禁，也只是允许决定是否制作 RC2。只有 product accuracy claim gate 另外满足 `eligible_gold_cases>=30` 与 `prospective_only=true` 时，才可把 `product_accuracy_claim_allowed` 设为 `true`；RC2 validation closure 本身不自动允许公开准确率宣传或正式产品发布。

## 11. 受保护边界

除非验证合同无法接入且有单独批准，不修改：

- P16–P21 的业务规则与输出语义；
- P23 端到端运行链顺序；
- P18 Reality Evidence hard override；
- Yuan 八段标题、顺序和免责声明规则；
- `prediction_validity=not_evaluated` 默认值；
- 已发布 `v0.2.0-rc1` tag。

## 12. 验证要求

实现完成后至少执行：

```bash
python -m unittest discover -s tests -v
python -m pytest -q
python -m build
```

随后在全新虚拟环境中安装 wheel，重新执行 P19/P22/产品验证相关测试和报告生成，并比较源树与 wheel 的机器可读摘要及 canonical hash。
