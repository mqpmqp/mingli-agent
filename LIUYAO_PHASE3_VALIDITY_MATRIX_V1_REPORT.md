# LiuYao Phase 3 Validity and Conflict Matrix v1

## Decision

本切片建立空、月破、日冲、六合、墓绝、动变、伏神和现实阻断的作用资格矩阵，可进入代码审查；不授权把矩阵状态作为成败预测、应期或成功概率。

固定边界：

```text
method_id=liuyao-validity-conflict-matrix@0.1.0
validity_matrix_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

## Scope

新增：

- `src/mingli/liuyao/validity_matrix.py`
  - 解释请求与高级历法上下文的一致性门禁；
  - 原爻、变爻有效性矩阵；
  - 月破、日冲、六合、旬空、墓绝条件；
  - 回头生克与多动爻图边资格；
  - 伏神候选及飞伏双向五行关系；
  - 现实硬阻断；
  - 条件冲突和未闭合依赖；
  - canonical SHA-256。
- `src/mingli/liuyao/validity_benchmark.py`
  - 月破与旬空叠加、变爻条件性、现实阻断和非生产边界基准。
- `src/mingli/liuyao/validity_cli.py`
  - `benchmark` 和 `evaluate` 可执行入口。
- `tests/test_liuyao_validity_matrix.py`
  - 历法门禁一致性、空破动爻、变爻、现实阻断、伏神、多动爻和确定性边界。
- `tests/test_liuyao_validity_cli.py`
  - CLI JSON输出和篡改门禁。
- `docs/liuyao/VALIDITY_MATRIX_V1.md`
  - 状态语义、输入、CLI和限制。

未修改：

- 第一、第二阶段既有排盘和时间完整性；
- `.github/`、`spec/`、`knowledge/`；
- 八字、紫微、奇门、梅花、PWA和服务接口；
- 真实案例；
- 生产发布配置。

## Engineering controls

1. 月建、日柱只有在解释请求和高级上下文都确认、且来源引用一致时才参与矩阵。
2. 旬空、日冲、六合、墓绝默认保持未决，不直接解释为有效、无效、有利或不利。
3. 月破作为约束条件，但不会被扩大为“彻底无用”。
4. 动爻和变爻必须分别通过门禁；发动本身不能覆盖空破墓绝。
5. 回头生克和多动爻图边只有两端通过当前基础门禁时才是 `active_candidate`。
6. 伏神仍是候选；矩阵不自动判断出伏或将其升级为用神。
7. 已核验现实阻断生成 `REALITY_HARD_BLOCK`，优先于结构候选。
8. 矩阵不做简单加减分，不输出概率，也不生成应期。
9. 所有输出保持 review-only、非生产和 `prediction_validity=not_evaluated`。

## Verification contract

最低验收：

```text
python -m compileall -q src tests
python -m pytest -q tests/test_liuyao_validity_matrix.py tests/test_liuyao_validity_cli.py
python -m pytest -q tests/test_liuyao.py tests/test_liuyao_temporal_integrity.py tests/test_liuyao_interpretation.py tests/test_liuyao_advanced_facts.py tests/test_liuyao_advanced_runtime.py tests/test_liuyao_validity_matrix.py tests/test_liuyao_validity_cli.py
python -m mingli.liuyao.validity_cli benchmark
python -m build
```

Draft PR当前Head还必须重新通过：

```text
Core Runtime Verification
Mobile Offline Bazi PWA
```

旧Head绿色结果不能复用。

## Known limits

- 没有自动历法或来源内容真实性验证。
- 没有暗动、冲散、合起、合绊、合住、合化、三合成局和冲墓条件树。
- 没有伏神出伏和飞伏最终作用优先级。
- 没有完整月日旺衰排序或多动爻最终路径裁剪。
- 没有自动取用、专项主题最终判断、应期和概率校准。
- 当前无合格前瞻案例，不能宣传预测准确率。

## Next slice

下一切片建立事件合同驱动的自动取用候选排序与专项主题包；它必须消费本矩阵，不得绕过用神确认、现实硬覆盖或有效性条件。
