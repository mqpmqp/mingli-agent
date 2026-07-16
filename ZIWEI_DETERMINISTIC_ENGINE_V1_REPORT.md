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
| 独立审查 RED | `pytest ... -k benchmark_rejects_inputs_that_could_false_pass` | 3 failed；空案例、过期算法版本和空期望均可 false pass |
| 独立审查 GREEN | 同一目标 | 3 passed；RED `7437c06` / GREEN `079c084` |
| 紫微聚焦 | PR A 五文件聚焦 | 44 passed |
| 覆盖率 | `pytest ... --cov=mingli.ziwei_engine --cov=mingli.ziwei --cov=mingli.ziwei_benchmark --cov=mingli.ziwei_runtime --cov-fail-under=80` | 84.19%，算法模块 95%，44 passed |
| 快测门禁 | `python -m mingli.test_gates --timeout-seconds 600 fast -- -q` | 215 passed, 1 skipped, 96 deselected, 16 subtests passed |
| Benchmark 门禁 | `python -m mingli.test_gates --timeout-seconds 3600 benchmark -- -q` | 38 passed, 274 deselected, 15 subtests passed |
| Real-case 合同门禁 | `python -m mingli.test_gates --timeout-seconds 600 real_case -- -q` | 58 passed, 254 deselected |
| Ruff（PR A 文件） | `python -m ruff check ...` | All checks passed |
| Pyright（PR A Runtime） | `python -m pyright src/mingli/ziwei_engine.py ...` | 0 errors, 0 warnings |
| Python 编译 | `python -m compileall -q src tests scripts` | PASS |
| wheel/sdist | `python -m build --wheel --sdist` | `mingli_agent-2.0.0-py3-none-any.whl` 与 `mingli_agent-2.0.0.tar.gz` 构建成功；未修改项目版本 |
| 隔离 wheel 冒烟 | `python -I` 从 wheel zip 导入并运行 `mingli.cli ziwei benchmark` | 5/5 passed，package-data 与 Schema 均存在 |
| 依赖漏洞审计 | 原实现阶段：`python -m pip_audit . --strict --progress-spinner off` | No known vulnerabilities found；本次审查无依赖变更且按禁止外部网络边界未重跑 |

独立审查补强了 benchmark 的 fail-closed 合同：schema/算法版本、来源、非空案例、唯一 case ID 与完整预期字段不满足时均拒绝生成成功报告。审核代码 SHA、验证证据和外部交付状态见 `ZIWEI_DETERMINISTIC_ENGINE_V1_MERGE_GATE.md`；当前没有 PR URL。

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
