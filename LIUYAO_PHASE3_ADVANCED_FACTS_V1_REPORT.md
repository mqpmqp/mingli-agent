# LiuYao Phase 3 Advanced Structural Facts v1

## Decision

本切片把第三阶段第一组能力实现为独立的高级结构事实层，可进入代码审查；不授权将其作为生产断卦规则，也不表示传统六爻预测有效性已经验证。

固定边界：

```text
method_id=liuyao-advanced-structural-facts@0.1.0
advanced_fact_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

## What

新增：

- `src/mingli/liuyao/advanced_facts.py`
  - 本宫纯卦伏神候选与同位飞神定位；
  - 五行顺行十二长生 profile；
  - 进神、退神地支变化；
  - 原爻/变爻地支和五行关系；
  - 内、外、全卦逐支反吟/伏吟候选；
  - 多动爻五行和地支关系图；
  - 版本化高级事实表 SHA-256；
  - 报告 canonical SHA-256。
- `src/mingli/liuyao/advanced_benchmark.py`
  - 伏神、十二长生、进退神和发布边界的合成基准。
- `tests/test_liuyao_advanced_facts.py`
  - 固定表关键点、方向性关系、伏神候选、上下文缺失、多动爻图和非生产边界测试。
- `docs/liuyao/ADVANCED_FACTS_V1.md`
  - profile、API、限制和后续顺序。

未修改：

- 第一、第二阶段既有排盘、事件合同、时间完整性和解释评分；
- `.github/`、`spec/`、`knowledge/`；
- 八字、紫微、奇门、梅花、PWA和服务接口；
- 真实案例和候选规则生命周期；
- 生产发布设置。

## Engineering controls

1. 所有高级事实只消费已经冻结并可重算的 `LiuYaoCaseRecord`。
2. 伏神只在本卦缺少某六亲时按本宫纯卦定位；不会自动断为出伏或有力。
3. 十二长生采用明确的版本化五行顺行 profile；流派差异必须另建 profile。
4. 进退神只识别地支变换，不直接加入成败权重。
5. 反吟伏吟采用明确标注的逐支 profile；静卦不会被误标为伏吟。
6. 多动爻只形成图边，不在事实层裁定哪条作用链有效。
7. 缺月建或日柱时，对应十二长生事实不生成，并返回上下文警告。
8. 所有输出继续固定 `production_allowed=false` 和 `prediction_validity=not_evaluated`。
9. 本切片不生成应期、概率或自然语言吉凶判断。

## Verification contract

最低验收：

```text
python -m compileall -q src tests
python -m pytest -q tests/test_liuyao_advanced_facts.py
python -m pytest -q tests/test_liuyao.py tests/test_liuyao_temporal_integrity.py tests/test_liuyao_interpretation.py tests/test_liuyao_advanced_facts.py
python -m mingli.liuyao.advanced_benchmark
python -m build
```

创建 Draft PR 后还必须以当前 Head 重新运行：

```text
Core Runtime Verification
Mobile Offline Bazi PWA
```

任何后续提交都会使旧 Head 的绿色结果失效。

## Known limits

- 没有自动历法换算或来源真实性验证。
- 伏神尚未进入飞伏旺衰、出伏和作用优先级。
- `墓`、`绝`仅作为十二长生标签，不自动视为负面；`长生`、`帝旺`也不自动视为正面。
- 尚未实现三合局、合化、暗动、冲墓、复杂旺衰和跨位作用链。
- 尚未实现自动取用、专项主题决策、应期候选和概率校准。
- 没有合格前瞻真实案例，不能宣传准确率。

## Next slice

下一切片应建立“高级事实有效性与冲突矩阵”，处理：

- 空、破、墓、绝对动静爻和变爻作用能力的门禁；
- 伏神与飞神之间的生克、空破和出伏候选；
- 多动爻路径裁剪；
- 合、冲、反吟、伏吟、进退神的条件优先级；
- 现实证据硬覆盖。

在该矩阵通过审查前，不进入应期和成功概率。
