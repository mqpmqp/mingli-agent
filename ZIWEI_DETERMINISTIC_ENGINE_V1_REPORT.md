# Ziwei Deterministic Engine v1 Implementation Report

日期：2026-07-16

分支：`agent/ziwei-deterministic-engine-v1`

算法：`ziwei-traditional-natal@1.0.0`

## 实现结果

PR A 将已知时辰命盘从 `partial` 提升为 `complete`，实现命身宫、十二宫干支、五行局、十四主星、十四辅煞、四化和基础亮度状态。未知时辰保持 `degraded`；没有任何输入生日特判、LLM 排盘、模拟结果、第三方 API 输出或把 unsupported 字段伪装为 supported 的路径。

算法使用纯函数和表驱动实现。公农历转换、时区、经度、均时差、DST 与晚子时沿用仓库既有已测试模块；星曜计算只消费规范农历年月日和时辰索引。

## TDD 证据摘要

| 阶段 | 命令 | 结果 |
|---|---|---|
| 基线 | `python -m pytest -q tests/test_ziwei_time_and_contracts.py tests/test_ziwei_cli.py tests/test_ziwei_isolation.py tests/test_ziwei_rules_runtime_privacy.py` | 23 passed |
| RED | `python -m pytest -q tests/test_ziwei_deterministic_engine.py ...` | 预期 collection error：确定性 benchmark/engine 接口不存在 |
| GREEN | 同一聚焦目标 | 29 passed；纠正一项人工 fixture 推导后通过 |
| 紫微聚焦 | `python -m pytest -q -k ziwei` | 32 passed, 268 deselected |
| 扩展性质/边界 | PR A 五文件聚焦 | 40 passed |
| 覆盖率 | `pytest ... --cov=mingli.ziwei_engine --cov=mingli.ziwei --cov=mingli.ziwei_benchmark --cov=mingli.ziwei_runtime --cov-fail-under=80` | 84.28%，算法模块 95%，40 passed |
| 快测门禁 | `python -m mingli.test_gates --timeout-seconds 600 fast -- -q` | 206 passed, 1 skipped, 93 deselected, 16 subtests passed |
| Benchmark 门禁 | `python -m mingli.test_gates --timeout-seconds 3600 benchmark -- -q` | 35 passed, 273 deselected, 15 subtests passed |
| Real-case 合同门禁 | `python -m mingli.test_gates --timeout-seconds 600 real_case -- -q` | 58 passed, 250 deselected |
| Ruff（PR A 文件） | `python -m ruff check ...` | All checks passed |
| Pyright（PR A Runtime） | `python -m pyright src/mingli/ziwei_engine.py ...` | 0 errors, 0 warnings |
| Python 编译 | `python -m compileall -q src tests scripts` | PASS |

构建、供应链审计和最终 SHA 在 Draft PR 创建前补入本报告。

## 覆盖范围

- 12×12 命身宫月时组合；
- 5 局×30 农历日的十四主星性质测试；
- 10 年干×12 命宫的五行局域检查；
- 10 年干×12 年支×12 月×12 时辰的十四辅煞输出域检查；
- 甲子完整盘的宫位、主星、辅煞、四化精确断言；
- 水二、木三、金四、土五、火六五个固定盘；
- 公农历等价、闰月、真太阳时跨时辰/跨日、晚子时、未知时辰、fingerprint 和 Schema；
- CLI chart/benchmark、Runtime complete 兼容与 Reality Evidence hard override。

## Hold 评估

| Hold | PR A 判断 |
|---|---|
| Traditional Engine Hold | ACTIVE，完成门禁后可提交独立审查；不在 Draft PR 中自行解除 |
| Rule Content Hold | ACTIVE，0/168，等待 PR B |
| Real Benchmark Hold | ACTIVE，无授权真实案例，等待 PR C |
| Commercial Release Hold | ACTIVE，仍需独立商业化验收 |

## 未实现边界

- 主星×宫位解释、组合规则、格局和时间叠盘不属于 PR A。
- 传统四化和亮度存在流派差异；v1 只实现已声明 profile，不声称覆盖所有流派。
- 固定盘证明实现一致性，不证明命理预测准确率。
- 不发布 PyPI、Release、tag 或商业版本。
