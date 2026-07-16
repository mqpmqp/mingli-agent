# Ziwei deterministic engine v1 TDD evidence

## Source plan

用户 Epic 中的 PR A 验收目标直接转换为本测试计划；没有外部 `*.plan.md`。

## User journeys

1. 作为 CLI/Runtime 调用方，我希望同一规范出生身份总是得到相同完整命盘，以便缓存、审计和重放。
2. 作为审核者，我希望每个传统字段都有版本、来源和可执行测试，以便拒绝示例硬编码或伪 supported。
3. 作为未知时辰用户，我希望系统明确降级而非默认子时，以免产生伪精确结果。
4. 作为发布负责人，我希望固定盘、Schema、构建和安全门禁可独立运行，以便在 Merge Gate 审查。

## RED / GREEN checkpoints

- RED commit：`ebe5c153ae2ce204275cee2822e3b6e22d673936`
- RED 证据：当前工作树 `PYTHONPATH=src` 下，测试在导入缺失的 `run_ziwei_engine_benchmarks` 接口时失败；失败来自待实现能力，不是语法或环境。
- GREEN commit：`e82319734608aabc06166bf925e3757a1a6639f0`
- GREEN 证据：同一聚焦目标 `29 passed`。
- Fixture 纠错：最初人工期望把亥宫紫微对应的廉贞写成辰；公开口诀和独立实现都证明应为卯。测试期望被纠正，生产算法未为错误 fixture 改写。

## Test specification

| # | 保证 | 测试/命令 | 类型 | 结果 |
|---|---|---|---|---|
| 1 | 12 月×12 时辰命身宫公式完整 | `test_life_and_body_formula_covers_every_month_hour_pair` | property | PASS |
| 2 | 五行局由年干和命宫干支计算，五局均可达 | `test_five_bureaus...`、`test_table_driven_properties...` | unit/property | PASS |
| 3 | 5 局×30 日均生成十四主星且天府镜像成立 | `test_primary_placement_properties...` | property | PASS |
| 4 | 十四辅煞和十干四化完整、稳定 | `test_auxiliary_stars...`、穷举输出域 | unit/property | PASS |
| 5 | 甲子完整盘宫星、四化、profile 精确 | `test_known_time_builds_complete...` | integration | PASS |
| 6 | Chart/Palace/Star/Transformation/Brightness Schema 接受完整盘 | `test_complete_chart_and_nested_objects...` | schema | PASS |
| 7 | 五个固定盘覆盖五行局 | `test_fixed_engine_benchmark...` | benchmark | PASS |
| 8 | 未知时辰保持 degraded，Runtime 接受 complete 并保留现实硬覆盖 | 既有 Ziwei/runtime tests | integration | PASS |
| 9 | CLI 输出完整盘并可运行固定 benchmark | `tests/test_ziwei_cli.py` | CLI | PASS |

## Coverage and known gaps

目标模块覆盖率 `84.28%`，其中 `mingli.ziwei_engine` 为 `95%`，满足 80% 门禁。完整互斥门禁结果为：fast 206 passed/1 skipped，benchmark 35 passed，real_case 58 passed；无失败。规则内容、真实案例效果和商业发布不在 PR A 测试范围，分别由后续 PR B/PR C 和独立商业验收负责。

wheel/sdist 构建、从 wheel zip 的 `python -I` 五局 benchmark 和 `pip-audit . --strict` 均已通过。精确命令与结果同步写入实现报告和 Draft PR body；未运行命令不会标成 PASS。
