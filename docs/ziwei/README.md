# MingLi 紫微工程合同说明

## 当前能力边界

本模块已经完成输入、历法归一化、时间校正、十二宫空结构、fingerprint、时间上下文、隔离、规则卡、Evidence Fusion、Yuan 适配和匿名 benchmark 合同。它**没有**实现传统紫微排盘算法；命宫、身宫、局数、星曜、四化、庙旺与格局均保持 `unsupported`，不得据此生成解读。

## 数据链路

```text
Birth Input
  -> normalize_ziwei_birth (calendar/time/location)
  -> build_ziwei_chart (partial/degraded + fingerprint)
  -> source-backed ZiweiRuleCard evaluator
  -> Phase18 Evidence Fusion + Reality hard override
  -> low-confidence gate
  -> Phase20 Yuan eight-section renderer
```

确定性数据、规则推断、现实证据与渲染结果分别存放，不把模型内部推理作为数据字段。

## 字段与 Schema

`src/mingli/contracts/schemas/ziwei_*.schema.json` 包含出生输入、时间校正、命盘、宫位、星曜、四化、亮度、六级时间上下文、fingerprint、规则卡、分析结果和匿名案例合同。

命盘状态：

- `partial`：出生时间已知，时间身份可计算，但传统排盘字段不支持。
- `degraded`：出生时间未知，不默认任何时辰。
- `complete`：Schema 预留；当前实现不会返回。
- `refused`：Schema 预留给依赖不可用或输入不可接受场景。

## 时间校正

- `civil`：保留输入地民用时间，不应用经度或均时差。
- `local_mean`：应用 `4 × (经度 − 标准时区中央经线)` 分钟。
- `apparent_solar`：在地方平太阳时基础上应用均时差，并移除夏令时偏移。

输出分别记录经度、均时差、DST 和总修正分钟，并保留校正前后 ISO 时间、是否跨日、时辰索引和晚子时政策。均时差沿用仓库已测试的 NOAA fractional-year 近似；算法版本进入 fingerprint。

公历和等价农历输入先归一到同一太阳日期及规范农历身份，因此得到相同命盘 fingerprint。姓名、显示年龄、昵称和会话 ID 不参与 fingerprint。

## 规则来源与覆盖

当前没有合法纳入且经过审查的紫微传统规则卡，覆盖门禁为 NO-GO。规则卡必须包含 trigger、required_facts、exclusions、priority、confidence、plain_language、evidence_refs、生命周期、冲突策略和输出约束；同优先级反向规则稳定返回 unresolved。

14 主星、12 宫与 168 个主星×宫位组合仅作为覆盖坐标，不包含解释内容。双星、三方四正、对宫、四化、辅煞、庙旺、格局、时间叠加均为 `contract_only`。

## CLI

```powershell
mingli ziwei chart --input birth.json
mingli ziwei coverage
```

`chart` 只输出 partial/degraded 结构，不声称完成传统排盘；`coverage` 在规则缺失时明确输出 NO-GO。

## 测试与迁移

聚焦测试：

```powershell
python -m pytest -q tests/test_ziwei_time_and_contracts.py tests/test_ziwei_isolation.py tests/test_ziwei_rules_runtime_privacy.py tests/test_ziwei_cli.py
```

这是新命名空间，没有旧紫微数据迁移。未来算法实现必须提升 `algorithm_version`，重新生成 fingerprint，并在兼容层中把旧 partial 记录保留为历史证据，禁止静默重算覆盖。

## Benchmark 接入

匿名案例必须通过 `ziwei_anonymous_case.schema.json`。`summarize_ziwei_cases` 只统计已匿名、允许存储、未撤回案例；`unverifiable` 不进入严格准确率分母。当前没有真实案例，Release Gate 保持 NO-GO。

## 使用限制

- 不可把空宫位/星曜字段交给 LLM 自由补写。
- 不可把 partial 结果展示为完整命盘。
- 健康、法律、投资、婚姻等重大决定必须优先使用现实证据和专业意见。
- 输出必须保持条件化、置信度和“仅供文化研究与娱乐参考”边界。
