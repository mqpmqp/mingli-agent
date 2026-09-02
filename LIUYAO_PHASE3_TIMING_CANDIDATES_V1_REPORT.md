# LiuYao Phase 3 Conditional Timing Candidates v1

## Decision

本切片建立条件化地支触发与有来源现实窗口的对齐层，可进入代码审查；它不是确定应期算法，不生成成功概率。

固定边界：

```text
method_id=liuyao-conditional-timing-candidates@0.1.0
timing_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

## Scope

新增：

- `src/mingli/liuyao/timing_candidates.py`
  - 候选取用与有效性矩阵上游门禁；
  - 同支、六冲、六合、填空、冲空、月破逢值/逢合、变爻逢值等符号触发；
  - 有来源外部时间锚点；
  - 锚点与事件合同日期边界；
  - 条件触发与锚点匹配；
  - canonical SHA-256。
- `src/mingli/liuyao/timing_benchmark.py`
  - 符号触发、来源锚点、候选状态和非概率边界基准。
- `src/mingli/liuyao/timing_cli.py`
  - `benchmark`、`evaluate` 可执行入口。
- `tests/test_liuyao_timing_candidates.py`
  - 上游门禁、触发、锚点来源、合同时间范围、现实阻断、并列用神和确定性边界。
- `tests/test_liuyao_timing_cli.py`
  - CLI JSON与篡改门禁。
- `docs/liuyao/TIMING_CANDIDATES_V1.md`
  - 语义、输入、状态、CLI与限制。

未修改：

- 第一、第二阶段排盘、事件合同、时间完整性和保守解释；
- `.github/`、`spec/`、`knowledge/`；
- 八字、紫微、奇门、梅花、PWA和服务接口；
- 真实案例和生产配置。

## Engineering controls

1. 未唯一确认用神候选时不生成时间条件。
2. 现实硬阻断成立时不生成盘面时间候选。
3. 月建、日柱未通过来源门禁时不生成时间候选。
4. 系统只生成地支条件，不自行换算公历日期。
5. 日期范围只能来自有 `source_refs` 的外部锚点。
6. 锚点必须位于起卦完成日期和事件合同截止日期之间。
7. 同支、冲、合、填空、月破解除等均保持条件性，不提前选择传统解释。
8. 同一锚点匹配多个触发不累计为置信度。
9. 所有候选固定为 `candidate_only`。
10. 不输出成功概率、确定日期或付费吉凶成品。

## Verification contract

最低验收：

```text
python -m compileall -q src tests
python -m pytest -q tests/test_liuyao_timing_candidates.py tests/test_liuyao_timing_cli.py
python -m pytest -q <全部六爻第一至第三阶段测试>
python -m mingli.liuyao.timing_cli benchmark
python -m build
```

Draft PR当前Head必须重新通过 Core Runtime Verification 与 Mobile Offline Bazi PWA；旧Head结果不能复用。

## Known limits

- 不自动计算或核验公历、节气、干支时间。
- `branch_tags` 和日程来源由调用方声明，运行时只做存在性与范围校验。
- 不判断冲空、合破、出墓等条件最终有利或不利。
- 不实现精确日时应期、多动爻最终路径时间化或概率校准。
- 当前没有合格前瞻样本，不能宣传准确率。

## Phase 3 boundary

至本切片，第三阶段候选范围已形成四层：

```text
高级结构事实
→ 作用资格与冲突矩阵
→ 事件合同驱动候选取用
→ 条件化时间候选
```

四层全部保持 review-only、非生产。后续工作应先进行完整代码审查、当前Head全门禁和前瞻案例验证，不得直接把这些候选规则升级成商业断卦。
