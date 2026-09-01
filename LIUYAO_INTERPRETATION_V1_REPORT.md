# LiuYao Structural Interpretation v0.1 Implementation Report

## Decision

第二阶段新增保守的结构解释层，目标是把用神候选、月建日辰、动变、生克、冲合和旬空转换为可追溯证据，而不是直接输出事件成败。

固定发布边界：

```text
interpretation_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

该层可以进入工程审查和前瞻验证，不能据此宣称六爻预测准确率已经建立，也不能自动生成付费吉凶断语。

## Scope

新增：

- `src/mingli/liuyao/interpretation.py`
  - 严格的 `InterpretationRequest`；
  - 单一候选自动选取、多候选阻断、爻位与六亲不一致阻断；
  - 月建、日辰、月破、日冲、六合、旬空；
  - 动爻对用神候选的五行作用；
  - 用神候选发动后的回头生、回头克、化泄、比和与耗力；
  - 元神、忌神、同类、泄耗和受制角色候选；
  - 支持、约束、歧义证据与冲突；
  - 现实阻断优先；
  - 考公、复合、求孕和健康等主题边界；
  - canonical SHA-256。
- `src/mingli/liuyao/interpretation_benchmark.py`
  - 支持结构、六合歧义、现实阻断和置信度边界的内置基准。
- `tests/test_liuyao_interpretation.py`
  - 用神候选选择；
  - 月合、月破、日冲、旬空；
  - 回头生与动爻作用；
  - 月日来源确认门禁；
  - 现实阻断；
  - 考公四维、感情四层、求孕医学边界；
  - 请求篡改、结果稳定哈希、CLI和绝对化表述回归。
- `docs/liuyao/INTERPRETATION_V1.md`
  - 规则边界、权重语义、主题合同、CLI和未实现清单。

修改：

- `src/mingli/liuyao/__init__.py`：导出解释层API；
- `src/mingli/liuyao_cli.py`：增加 `interpret` 和 `interpret-benchmark`；
- `docs/liuyao/README.md`：把工作流扩展为结构、解释、治理三层。

未修改：

- `spec/`、`knowledge/`；
- 八字、紫微、奇门、梅花模块；
- HTTP/MCP服务和PWA；
- 真实案例及个人信息；
- 已有候选规则生命周期；
- 第一阶段排盘与结算合同的既有语义。

## Rule boundary

规则族参考《周易与预测学》《周易预测宝典》和《未知之门》中常见的纳甲用神、月建日辰、动变、生克、六合六冲与旬空框架。实现只编码可以机械核验的关系，不复制原文，也不把传统案例当成现实预测有效性证明。

工程权重只用于稳定排列结构证据：

- 月令同支或月破：权重3；
- 主要月令生克、动爻生克、回头生克：权重2；
- 日辰五行作用、同类、化泄等次级因素：权重1；
- 六合、日冲、旬空及其他条件未闭合因素：权重0并标记 `ambiguous`。

权重不是概率、命中率或统计效应量。

## Safety and conflict controls

1. 同一六亲有多个候选爻时返回 `needs_confirmation`，不自动挑选最有利的一爻。
2. 调用方指定的爻位与六亲不一致时返回 `USE_GOD_MISMATCH`。
3. 月建和日柱只有在 `calendar_context_confirmed=true` 时参与解释。
4. 六合不自动解释为合起、合绊、合住或合化。
5. 日冲不自动解释为暗动、冲起或冲散。
6. 旬空不自动解释为无效。
7. 支持与约束同时存在时显式输出 `MIXED_POLARITY`。
8. 有条件规则未闭合时显式输出 `CONDITIONAL_RULES_UNRESOLVED`。
9. 已确认现实阻断覆盖盘面支持因素，并输出 `REALITY_OVERRIDES_STRUCTURE`。
10. 最高置信度封顶为 `medium`；缺月日、现实未知或歧义过多时降为 `low`。
11. 不生成事件概率、应期、必成或必败结论。

## Topic contracts

### Exam

固定拆分：

- `system_fit`：单次六爻不支持；
- `current_exam`：允许结构分析；
- `position_direction`：需要专业、地区、资格和竞争数据；
- `preparation_strategy`：需要成绩与备考数据。

### Relationship reconciliation

固定拆分：

- `bond`；
- `recontact`；
- `reconciliation`；
- `stability`。

每次只能聚焦一个冻结事件，其他维度保持独立。

### Pregnancy

固定拆分：

- `conception_opportunity`：仅传统结构观察；
- `medical_confirmation`：医疗专业判断；
- `pregnancy_stability`：医疗专业判断；
- `medical_factors`：现实医学因素优先。

## Verification contract

最终验收必须绑定PR当前head，最低命令：

```text
python -m compileall -q src tests
python -m pytest -q tests/test_liuyao.py tests/test_liuyao_temporal_integrity.py tests/test_liuyao_interpretation.py
python -m pytest -q -m "not benchmark and not real_case"
python -m pytest -q -m benchmark
python -m pytest -q -m real_case
python -m build
python -m mingli.liuyao_cli benchmark
python -m mingli.liuyao_cli interpret-benchmark
```

PR还必须通过现有Core Runtime Verification和Mobile Offline Bazi PWA工作流。任何修复改变head后，旧head的绿色收据失效。

## Known limits

当前明确未实现：

- 自动历法换算和月建、日辰来源验证；
- 伏神；
- 合化和三合局；
- 进神、退神；
- 反吟、伏吟；
- 十二长生、墓绝和复杂旺衰优先级；
- 多动爻跨位变爻作用；
- 应期；
- 成败概率；
- 自动付费成品；
- 前瞻真实案例准确率。

## Release boundary

两阶段共同目标可以达到：

```text
TECHNICAL_REVIEW_READY
STRUCTURAL_INTERPRETATION_REVIEW_READY
```

不能自动升级为：

```text
PREDICTION_VALIDATED
PRODUCTION_COMMERCIAL_ALLOWED
PRODUCT_ACCURACY_CLAIM_ALLOWED
```

合并、部署和任何商业发布仍需独立授权。
