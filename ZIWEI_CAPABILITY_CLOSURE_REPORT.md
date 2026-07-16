# Ziwei Capability Closure Report

> 历史基线：本报告记录 PR #27 合并时的 P0 状态。PR A 当前引擎状态与证据见 `ZIWEI_DETERMINISTIC_ENGINE_V1_REPORT.md`；以下历史结论不作为当前分支能力清单。

日期：2026-07-16

实现基线：`532f8ea4570db6ddb126ad39e07b8d7e0a8446d9`

已验证实现提交：`0bcbce6`（后续仅含报告、打包门禁更新与验证记录）

## 总体结论

P0 工程闭环已完成：紫微输入与时间合同、partial/degraded 命盘结构、稳定 fingerprint、上下文与异步隔离、规则合同、Evidence Fusion/Yuan 适配、隐私授权和 benchmark 框架均已落地并有自动化测试。

这不等于传统紫微排盘完成。仓库没有可合法复用且经过验证的命宫/身宫/局数/安星/四化/庙旺算法或规则来源，因此相关字段始终为空并列入 `unsupported_fields`；传统排盘引擎与规则内容保持 NO-GO。

## 完成能力

- 公历、农历与闰月输入归一化；等价输入共享命盘身份。
- 分钟级输入、IANA/固定偏移时区、民用/地方平太阳/真太阳时三模式。
- 经度、均时差、DST 分项记录，支持跨时辰、跨日和晚子时政策。
- 未知出生时间返回 degraded，不默认子时。
- 十二宫完整 Schema 与空结构；命宫、身宫、局数、星曜、四化、亮度显式 unsupported。
- natal/decade/annual/monthly/daily/hourly 六级上下文合同。
- fingerprint 排除姓名、显示年龄、昵称、会话 ID，包含校正身份、性别、地理/模式、闰月规范身份、晚子时政策和算法版本。
- user/case/cache namespace 隔离、chart/request revision、context hash、陈旧异步拒绝和有序合盘身份。
- 规则卡校验、required facts、exclusions、priority、稳定冲突和禁止绝对语言。
- 14 主星、12 宫、168 组合覆盖门禁；当前诚实显示 0/168 与 NO-GO。
- 紫微规则证据进入 Phase18，Reality Evidence 保持 claim/scope hard override。
- Phase20 Yuan 八段适配、low-only confidence、免责声明一次且位于末尾。
- 匿名案例 consent/匿名化/撤回 Schema 与不统计撤回数据的 benchmark 汇总。
- `mingli ziwei chart` 与 `mingli ziwei coverage` 最小 CLI。

## 未实现与原因

- 传统紫微确定性排盘：缺少独立可靠、可审查的算法来源与 benchmark。
- 传统规则内容：仓库无已审核来源；不为覆盖率编造规则。
- 真实案例有效性：没有经授权案例；不制造虚假案例。
- 外部产品输出对比：公开页面输出无法可靠观察，且不得用作唯一 Oracle。
- 商业发布、支付、生产部署、远端 push/PR：不在授权范围。

## 最终数据链路

```text
Input -> Calendar/Solar-Time Normalization -> Partial/Degraded Ziwei Chart
      -> Source-backed Rule Cards -> Evidence Fusion -> Reality Override
      -> Low-confidence Gate -> Yuan Eight Sections -> Disclaimer
```

只有规范化与隔离属于当前可验证确定性层；传统排盘字段不会进入规则求值。
