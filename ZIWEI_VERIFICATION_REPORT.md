# Ziwei Verification Report

日期：2026-07-16  
Python：3.11.15  
验证实现提交：`0bcbce6`

## 已执行验证

| 验证 | 精确命令 | 结果 |
|---|---|---|
| 任务前快测基线 | `python -m mingli.test_gates --timeout-seconds 600 fast -- -q` | 177 passed, 1 skipped, 90 deselected, 16 subtests passed |
| TDD RED（核心） | `python -m pytest -q tests/test_ziwei_time_and_contracts.py tests/test_ziwei_isolation.py tests/test_ziwei_rules_runtime_privacy.py` | 预期失败：3 collection errors，模块不存在 |
| TDD RED（CLI） | `python -m pytest -q tests/test_ziwei_cli.py` | 预期失败：2，命令不存在；另一次环境临时目录权限错误已从测试依赖中移除 |
| 紫微聚焦 | `python -m pytest -q tests/test_ziwei_time_and_contracts.py tests/test_ziwei_isolation.py tests/test_ziwei_rules_runtime_privacy.py tests/test_ziwei_cli.py` | 21 passed |
| Python 编译 | `python -m compileall -q src` | exit 0 |
| Ziwei Schema 元校验 | `Draft202012Validator.check_schema` 遍历 `ziwei_*.json` | 12 schemas valid |
| 修改后快测 | `python -m mingli.test_gates --timeout-seconds 600 fast -- -q` | 197 passed, 1 skipped, 91 deselected, 16 subtests passed |
| 完整测试首次 | `python -m pytest -q` | 287 passed, 1 skipped, 1 failed；唯一失败为旧打包 Schema 数量 21→实际 33 |
| 打包门禁修复后聚焦 | `python -m pytest -q tests/test_derived_contracts.py::SourceAndPackagingTests::test_wheel_contains_readable_schemas` | 1 passed |
| 完整测试最终 | `python -m pytest -q` | 288 passed, 1 skipped, 31 subtests passed；exit 0；1075.51s |
| 构建 | `python -m build --wheel --sdist --outdir <system-temp>` | wheel 与 sdist 成功；wheel 335094 bytes，sdist 311726 bytes |
| CLI 进程冒烟 | `python -m mingli.cli ziwei chart --input -` | `partial`、12 palaces、`not_evaluated`；exit 0 |
| 覆盖门禁冒烟 | `python -m mingli.cli ziwei coverage` | 0/168，`NO-GO`；exit 0 |

## 边界覆盖

- 公农历等价与闰月；算法版本/姓名/显示年龄对 fingerprint 的正确影响。
- 经度与均时差分项、跨时辰、跨日、23:00 晚子时、未知时辰降级。
- 六级时间上下文以及月/时父上下文完整性。
- 命盘、用户、案例、年份、合盘双方与陈旧异步隔离。
- 规则 required facts、exclusions、priority、同级冲突、来源与绝对语言门禁。
- Reality hard override、Yuan 八段和免责声明。
- consent/匿名化/撤回与空 benchmark 行为。

## 工具门禁说明

仓库未配置独立 formatter、lint 或静态类型检查命令，因此没有虚构这些结果。Python compileall、JSON Schema 元校验、聚焦/快测/完整 pytest、wheel/sdist 构建和 CLI 进程冒烟用于实际门禁。

## 未验证内容

- 传统命宫、身宫、局数、安星、四化、庙旺与格局算法：未实现。
- 传统规则准确性与覆盖：规则内容为 0。
- 真实案例准确率和置信度校准：无授权数据。
- 外部 Metis 输出等价：未使用其输出作为 Oracle。

所有计划内本地门禁均已执行。未配置的 formatter/lint/typecheck 不以其他命令冒充。
