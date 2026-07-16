# MingLi 紫微确定性排盘 v1

## 能力与边界

算法 profile 为 `ziwei-traditional-natal@1.0.0`。出生时辰已知时，命盘状态为 `complete`，支持：

- 公历/农历、闰月、时区、经度、地方平太阳时、真太阳时和晚子时政策；
- 命宫、身宫、十二宫名称/干支映射；
- 纳音五行局；
- 紫微、天府与十四主星；
- 左辅、右弼、文昌、文曲、天魁、天钺、禄存、天马、地空、地劫、火星、铃星、擎羊、陀罗；
- 《紫微斗数全集》profile 的年干禄、权、科、忌；
- 有版本化表项的庙、旺、得/利、平、不、陷基础状态；
- Chart JSON、严格嵌套 Schema、canonical hash、fingerprint、CLI 与五局固定盘 benchmark。

出生时辰未知时状态仍为 `degraded`，命身宫、局数、星曜等字段保持空值并列入 `unsupported_fields`。本阶段不包含星曜解释、主星×宫位规则、格局、三方四正推断、流限推断、真实案例准确率或商业发布。

## 算法 profile

| 项目 | v1 约定 |
|---|---|
| 历法身份 | 时间校正和晚子时政策处理后的规范农历日期 |
| 年界 | 农历新年 |
| 闰月 | 沿用同一数字月，不前后拆月 |
| 时辰 | 子=0，丑=1，…，亥=11；未知时辰拒绝精确排盘 |
| 宫环 | 寅宫为 index 0，顺时针至丑宫 index 11 |
| 命宫 | 寅起正月顺数生月，逆数生时 |
| 身宫 | 寅起正月顺数生月，顺数生时 |
| 五行局 | 五虎遁起寅宫干，命宫干支纳音映射水二/木三/金四/土五/火六局 |
| 紫微 | 出生日补至可被局数整除；补数偶数顺加、奇数逆减，从寅起商数 |
| 天府 | 与紫微按寅宫索引镜像；其余十三主星按两星系固定偏移 |
| 四化 | `ziwei-doushu-quanji`，明确保留庚、壬等流派差异，不混用其他表 |
| 亮度 | `iztro` 固定 revision 的七级传统表，依序规范化为 temple/prosperous/beneficial/neutral/weak/unfavorable/fallen，并保留中文 source_value |

算法版本、时间政策、位置、时区、性别与规范农历身份进入 fingerprint。姓名、昵称、显示年龄和会话 ID 不进入 fingerprint。

## 来源与交叉核验

1. [维基文库《紫微斗数全书/全览》](https://zh.wikisource.org/zh-hant/%E7%B4%AB%E5%BE%AE%E6%96%97%E6%95%B8%E5%85%A8%E6%9B%B8/%E5%85%A8%E8%A6%BD)：古籍全文入口，用于传统 profile 的来源追踪。
2. [紫微斗数推算方法](https://zh.wikipedia.org/wiki/%E7%B4%AB%E5%BE%AE%E6%96%97%E6%95%B0#%E6%8E%A8%E7%AE%97%E6%96%B9%E6%B3%95)：命身宫、五行局、主星与四化的公开可复核转写；仅作为转写核对，不作为科学权威。
3. [`iztro` revision `f3dc6c547420b063109251d7c7132fa3cb41e06e`](https://github.com/SylarLong/iztro/tree/f3dc6c547420b063109251d7c7132fa3cb41e06e)：MIT 许可的独立实现交叉核验。项目没有调用其 API、没有复制其生成盘；只核对公式、表和固定示例。许可见仓库 `THIRD_PARTY_NOTICES.md`。

固定 benchmark 中木三局二十七日、火六局十三日、土五局六日的紫微落宫，直接对应版本化来源中的公开公式示例；其余盘用于覆盖五局和完整数据链路。

## JSON 与 CLI

```powershell
python -m mingli.cli ziwei chart --input birth.json
python -m mingli.cli ziwei benchmark
python -m mingli.cli ziwei coverage
```

`chart` 的已知时辰输出为 `ziwei-chart@1.0`，包含 `algorithm_profile`、`placement_lunar_date`、12 个严格宫位对象及来源。`benchmark` 从 wheel 内的固定数据运行五局回归。`coverage` 仍只统计传统解释规则；PR A 不硬编码 168 个规则覆盖率，因此该命令仍为 0/168 与 `NO-GO`。

## Release Hold

- Traditional Engine Hold：本实现完成后进入独立审查资格；Draft PR 或未合并状态下保持 ACTIVE。
- Rule Content Hold：ACTIVE，规则仍为 0/168，等待 PR B。
- Real Benchmark Hold：ACTIVE，没有授权真实案例，等待 PR C。
- Commercial Release Hold：ACTIVE，不能由前三项自动解除。

排盘的计算一致性不等于预测有效性。所有输出继续固定 `prediction_validity=not_evaluated`。
