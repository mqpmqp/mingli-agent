# 六爻第三阶段高级事实运行时 v1

## 目的

`advanced_facts.py` 只负责把盘面转换为低层结构事实；正式调用必须经过 `advanced_runtime.py` 的历法来源门禁。这样可以避免仅因 `cast` 中出现月建或日柱，就把十二长生等依赖历法上下文的事实当成已经确认。

固定边界：

```text
method_id=liuyao-advanced-fact-runtime@0.1.0
advanced_runtime_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

## 来源门禁

调用方必须显式提供：

```json
{
  "calendar_context_confirmed": true,
  "calendar_source_refs": ["source:verified-calendar-receipt"]
}
```

规则如下：

1. `calendar_context_confirmed=true` 时，`calendar_source_refs` 不能为空；
2. 提供来源引用但未确认上下文时，输入无效；
3. 盘面没有月建和日柱时，不能伪造“已确认”；
4. 盘面有月建或日柱，但未通过确认门禁时，十二长生事实从可用输出中移除；
5. 来源引用仅证明调用方声明了来源，当前运行时不读取链接、文件，也不自行证明历法计算正确。

输出状态：

```text
missing
provided_unconfirmed
confirmed_partial
confirmed_complete
```

对应来源状态：

```text
not_provided
blocked_unconfirmed
declared_sources_present_not_runtime_verified
```

## CLI

```bash
# 可执行高级事实基准
python -m mingli.liuyao.advanced_cli benchmark

# 从冻结案例和来源确认请求生成报告
python -m mingli.liuyao.advanced_cli facts \
  --record case.json \
  --context advanced-context.json
```

CLI输出机器可读JSON。任何输入、哈希或来源门禁错误写入stderr并返回非零退出码。

## 发布边界

该运行时不会生成：

- 吉凶结论；
- 成败概率；
- 确定日期；
- 应期；
- 医疗、法律、投资等专业结论；
- 对传统预测有效性的声明。

第三阶段后续只能在当前门禁之上继续建立空破墓绝、飞伏有效性、多动爻路径、自动取用和冲突矩阵，不能绕过来源确认直接使用月日事实。
