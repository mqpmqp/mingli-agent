# Ziwei Traditional Rule Content v1 TDD evidence

## Source plan

用户 Epic 要求 stacked PR B 在 PR A `82bca1599aefde27332eab055ce7f8a57d121ed1` 上实现真实可执行的 Traditional Rule Content v1；没有单独 `*.plan.md`。

## User journeys

1. 作为内容审核者，我需要 14×12 的每个 pair 都有独立、可读、带来源和排除边界的规则，而不是空壳或改名模板。
2. 作为 Runtime 调用方，我需要完整命盘自动提取主星宫位、四化、亮度和同宫事实，并拒绝 degraded/unsupported/版本不匹配输入。
3. 作为评测负责人，我需要 coverage 由真实记录和真实 evaluator 计算，使删除、错触发和重复 pair 无法 false pass。
4. 作为产品安全负责人，我需要 priority/conflict、Reality Evidence hard override 和禁止绝对语言继续生效。
5. 作为发布负责人，我需要 CLI、Schema、wheel/sdist 和 package-data 可独立复核，同时所有 Hold 保持诚实状态。

## RED / GREEN checkpoints

- RED commit：`8ff4dd7cb1e5704621a42a75a0cfeb519f3d9cc7`。
- RED 命令：`pytest ... test_ziwei_traditional_rule_content.py ...`。
- RED 结果：2 个 collection errors，缺失 `PRIMARY_STAR_IDS`、`ZIWEI_RULE_CONTENT_VERSION` 等目标 API；失败来自待实现合同，不是环境或语法。
- GREEN commit：`940a4f99a2c2255394334c9063f4fbdefedaa94b`。
- GREEN 结果：21 个聚焦测试通过，wheel package-data 探针通过，Ruff/Pyright/compileall 通过。
- 防伪加固 commit：`cc9ec9f35a67e32b2d0b5fa0962b9491b1d8221d`；补充非法模型、递归 condition、畸形命盘、protected fact 和 loader 错误路径。
- 独立审查 RED 1：`d538241`；额外第六条组合规则仍得到 `REVIEW_REQUIRED`，重复宫名仍被提取，结果 2 failed / 9 passed。
- 独立审查 RED 2：`6e7c13e`；完整盘 14 条主星落宫证据全部被跨 subject priority 压制，非法修饰星和重复宫序仍被接受，结果 4 failed / 9 passed。
- 独立审查 GREEN：`8691d7c`；按同一 domain/subject/触发目标处理冲突，严格校验完整命盘交叉约束，并对 184 条规则逐类行为求值；受影响目标 14 passed。
- 终审 RED：`fc8036c`；同 state 不同星仍互压、四类嵌套非 supported 事实仍被接受、过宽 generic trigger 仍通过 coverage，共 6 failed。
- 终审补充 RED：`156bfa7`；移除 complete/unsupported exclusions 后 coverage 仍通过，1 failed。
- 终审 GREEN：`840872d`；规范化 trigger 冲突键、嵌套 supported gate、canonical trigger/exclusions 与四类正负行为样本闭环；定向 7 passed，规则内容文件 45 passed。
- 终审测试闭环：`cab5d73`；显式参数化五类嵌套字段与 unsupported/research_required 两种状态，10 passed。

## Test specification

| # | 可执行保证 | 测试 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | 184 条规则均通过严格 Schema、自定义验证、唯一 ID 和已登记 source_id | `test_packaged_rule_payload...` | schema/content | PASS |
| 2 | 168 个主星×宫位 pair 完整，短句和去名称后的内容均唯一 | `test_primary_star_palace_matrix...` | content mutation | PASS |
| 3 | 完整命盘实际匹配十四条基础规则，并消费四化和亮度 | `test_chart_fact_extraction...` | integration | PASS |
| 4 | 正匹配、负匹配、exclusions、priority 和同级冲突可执行 | `test_exclusions_priority...` | behavior | PASS |
| 5 | degraded、unsupported、算法不兼容和 protected fact 注入 fail closed | fail-closed tests | security/contract | PASS |
| 6 | 删除、错触发或重复 pair 都不能维持 168/168 门禁 | `test_coverage_is_computed...` | false-pass mutation | PASS |
| 7 | Reality Evidence 对同 claim/scope 保持 hard override | `test_reality_evidence...` | integration | PASS |
| 8 | CLI 校验、coverage 和命盘求值输出真实计数 | `test_ziwei_rule_content_validate...` | CLI | PASS |
| 9 | 生成器与跟踪资源完全一致 | `test_tracked_rule_resource...` | reproducibility | PASS |
| 10 | wheel 包含规则 JSON，隔离安装后可读取 184 条记录 | `test_wheel_contains_readable_schemas` | packaging | PASS |
| 11 | 不同规则目标不会跨 subject 互相压制；重复宫名/宫序、非法修饰星、额外规则及非主星错 trigger 均 fail closed | independent-review regressions | runtime/false-pass | PASS |
| 12 | 同 state 不同星不互压；嵌套非 supported 事实、过宽 trigger 和缺失安全 exclusions 均关闭门禁 | final-review regressions | runtime/false-pass | PASS |

## Coverage and gates

- PR B 目标模块：`ziwei_rules` 89%，`ziwei_runtime` 86%，合计 88.24%，超过 80% 门禁。
- 规则/Runtime/CLI 聚焦：63 passed；紫微全集：96 passed。
- 完整 gate 与 full pytest 结果在 Local Merge Gate 报告中记录；未完成命令不标记为 PASS。

## Known gaps

三方四正、对宫、辅煞完整组合、完整格局和流限仍为 contract-only。184 条规则保持 draft；工程测试不能替代独立内容审查或真实案例验证。
