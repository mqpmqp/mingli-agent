# LiuYao Phase 3 Contract-Driven Selection v1

## Decision

本切片建立事件合同驱动的六亲/爻位候选排序，可进入代码审查；它不自动宣布最终用神，不生成成败、应期或成功概率。

固定边界：

```text
method_id=liuyao-contract-driven-selection-runtime@0.1.0
selection_runtime_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

## Scope

新增：

- `src/mingli/liuyao/selection_core.py`
  - 主题与焦点 profile；
  - 考编、复合、求孕等专项维度；
  - 可见爻/伏神候选；
  - 世应与代摇主体映射；
  - 候选排序收据。
- `src/mingli/liuyao/selection_runtime.py`
  - 冻结事件合同 SHA-256 绑定；
  - 现实证据形态校验；
  - 专业/现实焦点 override 阻断；
  - 感情稳定现实上下文门禁；
  - 同有效性层级候选不因单纯发动自动决胜；
  - review-only 运行时报告及 canonical SHA-256。
- `src/mingli/liuyao/selection_benchmark.py`
  - 考编四维、可见候选、伏神候选、同层级并列和边界基准。
- `src/mingli/liuyao/selection_cli.py`
  - `benchmark`、`evaluate` 可执行入口。
- `tests/test_liuyao_selection_runtime.py`
  - 合同绑定、主题映射、代摇、性别、现实阻断、并列候选、伏神和非生产边界。
- `tests/test_liuyao_selection_cli.py`
  - CLI JSON、合同哈希和错误退出。
- `docs/liuyao/SELECTION_CORE_V1.md`
  - 使用方式、状态、映射和限制。

未修改：

- 第一、第二阶段确定性排盘、事件合同和时间完整性；
- `.github/`、`spec/`、`knowledge/`；
- 八字、紫微、奇门、梅花、PWA和服务接口；
- 真实案例和生产配置。

## Engineering controls

1. 事件焦点确认必须绑定案例中冻结事件合同的 canonical SHA-256。
2. `system_fit`、岗位方向、备考策略、医学确认、妊娠稳定、医疗因素和健康专业评估不能被六亲 override 绕过。
3. 考编当前事件固定输出体制适配、本次考试、岗位方向、备考策略四维，但只对本次考试做结构候选排序。
4. 感情复合固定输出缘分、复联、复合、稳定四维；性别未知时不自动选配偶六亲。
5. 代摇必须确认主体爻位，禁止默认世爻等同被测者。
6. 非 unknown 现实状态必须有事实和证据引用；现实阻断优先。
7. 发动只作为提示，不在同一有效性层级中自动决胜。
8. 伏神候选永不自动升级为最终用神。
9. 所有输出保持 review-only、非生产和 `prediction_validity=not_evaluated`。
10. 不输出应期、概率或付费吉凶成品。

## Verification contract

最低验收：

```text
python -m compileall -q src tests
python -m pytest -q tests/test_liuyao_selection_runtime.py tests/test_liuyao_selection_cli.py
python -m pytest -q tests/test_liuyao.py tests/test_liuyao_temporal_integrity.py tests/test_liuyao_interpretation.py tests/test_liuyao_advanced_facts.py tests/test_liuyao_advanced_runtime.py tests/test_liuyao_validity_matrix.py tests/test_liuyao_validity_cli.py tests/test_liuyao_selection_runtime.py tests/test_liuyao_selection_cli.py
python -m mingli.liuyao.selection_cli benchmark
python -m build
```

Draft PR当前Head必须重新通过 Core Runtime Verification 与 Mobile Offline Bazi PWA；旧Head收据无效。

## Known limits

- 事件合同采用哈希绑定，但不自动理解自然语言题意是否与焦点完全一致。
- 候选排序不是最终用神判断，也不是统计概率。
- 尚未实现完整空破墓绝、暗动、合化、冲墓和多动爻最终路径。
- 尚未实现专项成败结论和条件化应期。
- 当前没有合格前瞻样本，不能宣传准确率。

## Next slice

下一切片只生成条件化应期候选，必须消费事件合同、候选取用报告和有效性矩阵；现实流程日程与来源缺失时不得给具体窗口，更不得输出确定日期或成功概率。
