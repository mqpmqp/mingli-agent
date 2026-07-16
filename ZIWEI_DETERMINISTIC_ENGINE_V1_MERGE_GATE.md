# Ziwei Deterministic Engine v1 — Local Merge Gate

日期：2026-07-16

分支：`agent/ziwei-deterministic-engine-v1`

基线：`main@13139c500e77f757779840ca71541dde8b35e57a`

审核代码：`079c08430e4aa686efee5bf780966b7df2f121ba`

## 结论

- Local Merge Gate：**PASS**。
- 外部交付：**NOT EXECUTED**。分支没有 upstream，未推送，未创建 PR，也没有远端 CI 结果。
- Traditional Engine Hold：**ACTIVE**，直到明确授权后的远端审查、CI 与合并完成。
- Rule Content / Real Benchmark / Commercial Release Hold：**ACTIVE**。

本结论只证明声明 profile 的计算一致性、合同与工程门禁，不证明命理预测有效性，也不授权发布、商业化或自动解除任何 Hold。

## 独立审查发现与处置

确认一项高优先级 Merge Gate 缺陷：`mingli ziwei benchmark --path` 对 payload 缺少 fail-closed 校验，空案例、过期算法版本或空期望可以得到零失败报告。

- RED：`7437c06af95632a0aac8594707fdaa378d6d4445`；同一回归目标 `3 failed`，均为预期的 `DID NOT RAISE ValueError`。
- GREEN：`079c08430e4aa686efee5bf780966b7df2f121ba`；同一目标 `3 passed`。
- 修复范围：校验 benchmark schema/算法版本、非空唯一来源、非空案例、唯一非空 case ID、结构化输入、完整预期字段和非空预期值。
- 自审结果：没有发现剩余 P0/P1 代码缺陷；未做无关重构。

## 最终本地验证

| 门禁 | 结果 |
|---|---|
| 五份紫微聚焦测试 | 44 passed |
| 目标模块覆盖率 | 84.19%；`ziwei_engine` 95%；门槛 80% |
| Ruff | All checks passed |
| Pyright | 0 errors, 0 warnings |
| `compileall` | PASS |
| fast gate | 215 passed, 1 skipped, 96 deselected, 16 subtests |
| benchmark gate | 38 passed, 274 deselected, 15 subtests |
| real-case gate | 58 passed, 254 deselected |
| Ziwei Schema 元校验 | 12 schemas valid |
| CLI 固定盘 | 5/5 passed；0 failed |
| 规则覆盖门禁 | 0/168；NO-GO（预期） |
| wheel/sdist | 构建成功 |
| wheel 隔离冒烟 | 从 wheel 路径加载；五局 5/5 与打包 Schema PASS |
| `git diff --check` | PASS |

原实现阶段已记录 `pip-audit . --strict` 无已知漏洞。本次独立审查没有修改依赖；遵循仓库禁止外部网络调用的边界，没有重新发起在线漏洞查询。

## 保留边界

- PR A 不包含主星×宫位解释、组合规则、格局和时间叠盘。
- 规则覆盖保持 0/168；不得生成传统解释或把 contract-only 标为 implemented。
- 没有授权真实案例，不生成准确率或置信度校准结论。
- 固定盘与性质测试证明版本化实现的一致性，不证明预测准确率。
- 不发布 PyPI、Release、tag 或商业版本。

## 下一步

获得明确外部写操作授权后，推送当前分支并创建 Draft PR；PR 必须引用本报告、RED/GREEN commits、全部本地门禁与 Hold 状态。随后等待远端独立审查和 CI，合并前不得解除 Traditional Engine Hold。
