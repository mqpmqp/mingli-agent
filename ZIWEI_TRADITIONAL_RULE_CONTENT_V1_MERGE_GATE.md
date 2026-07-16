# Ziwei Traditional Rule Content v1 — Local Merge Gate

日期：2026-07-16

分支：`agent/ziwei-traditional-rule-content-v1`

堆叠基线：`main@40bab90dde185ff97fa983f5a50ce7b8208cb11e`（PR A #28 已合并）

Restack 验证代码：`c111990a34dfee5c57d3b8fa8a786526b04e78f2`（运行时修复：`e864f71`）

规则版本：`ziwei-traditional-rule-content@1.0.0`

## 结论

- Local Merge Gate：**PASS**。
- 独立终审：**PASS**；已发现的 P2 全部关闭，未发现剩余 P0–P2。
- 外部交付：**AUTHORIZED / IN PROGRESS**。PR A #28 已合并，PR B 已 restack 到最新 `main`；本证据提交后推送并创建 Draft PR。
- 覆盖状态：`REVIEW_REQUIRED`；184 条规则均为 `draft`，Rule Content Hold 继续 **ACTIVE**。
- Prediction Validity：`not_evaluated`；工程覆盖不表示预测准确率。

## 独立审查与 TDD 闭环

首轮实现之后，独立 reviewer 与本地行为探针共发现跨规则目标 priority 压制、畸形完整盘事实注入、非主星 coverage false pass、同 state 不同星冲突、嵌套非 supported 事实、过宽 trigger 与缺失 exclusions 等 P2。

| 阶段 | Commit | 可复核结果 |
|---|---|---|
| 初始合同 RED | `cfa3500` | 2 个 collection errors，目标 API 尚不存在 |
| 初始实现 GREEN | `d37d50e` | 184 条打包规则与基础行为闭环 |
| 首轮防伪 | `fcd3681` | loader、condition、畸形命盘与 protected fact 加固 |
| 独立审查 RED | `00cb96d` | 2 failed / 9 passed |
| 独立审查 RED | `cef9774` | 4 failed / 9 passed |
| 独立审查 GREEN | `819e409` | 受影响目标 14 passed |
| 终审 RED | `7c189f6` | 6 failed |
| exclusions RED | `da20289` | 1 failed |
| 终审 GREEN | `e864f71` | 定向 7 passed；终审 PASS |
| 状态矩阵闭环 | `4448d51` | 五类嵌套字段 × 两种非 supported 状态，10 passed |

最终行为：冲突键由 domain、subject 与规范化 trigger 共同确定；完整盘必须通过 Schema、十二宫/二十八星/四化交叉约束与嵌套 supported gate；coverage 对 184 条规则校验 canonical trigger、必需 exclusions、正样本、空目标、degraded 和 unsupported 负样本。

## 最终本地验证

| 门禁 | 结果 |
|---|---|
| 规则/Runtime/CLI 聚焦与覆盖 | 63 passed；总覆盖 88.24%；`ziwei_rules` 89%，`ziwei_runtime` 86% |
| Ziwei 全集 | 96 passed |
| 全量 pytest | 363 passed，1 skipped，31 subtests；24:30 |
| fast gate | 267 passed，1 skipped，96 deselected，16 subtests；3:16 |
| benchmark gate | 38 passed，326 deselected，15 subtests；27:11 |
| real-case gate | 58 passed，306 deselected |
| Ruff（新增/核心变更文件） | PASS |
| Pyright（CLI/规则/Runtime） | 0 errors，0 warnings |
| `compileall` | PASS |
| CLI 规则校验 | 184 rules；168 主星宫位；`REVIEW_REQUIRED`；Hold ACTIVE |
| 行为 coverage | 168 + 4 + 7 + 5；0 duplicate rule IDs；0 duplicate pairs |
| wheel/sdist | 构建成功；sdist 含规则资源 |
| wheel 临时路径冒烟 | 从 wheel 路径加载；184/184；行为 168+4+7+5；`REVIEW_REQUIRED` |
| `pip-audit . --strict` | No known vulnerabilities found；此后依赖文件未变化 |
| 生成器/跟踪 JSON | 完全一致 |
| `git diff --check` | PASS |

仓库全量 `ruff check .` 与 `pyright src` 仍会命中未改动历史文件的既有 395/284 项；本 PR 的核心 Python 变更范围通过 Ruff，CLI/规则/Runtime 通过 Pyright。包装测试文件的一个 F401 位于堆叠基线已有 import，本 PR 未改该行，未做无关清理。

## 保留边界

- PR B 未修改 PR A 的排盘公式、亮度表或固定盘。
- 三方四正、对宫、完整辅煞组合、完整格局和流限仍为 contract-only。
- 184 条传统规则均为原创短句结构化转述和 `draft`；工程测试不能替代逐条内容审查或真实案例验证。
- Reality Evidence 继续按同一 claim/scope 硬覆盖；输出保持低置信与一次性免责声明。
- Traditional Engine、Rule Content、Real Benchmark、Commercial Release Hold 均保持 ACTIVE。
- 不发布 PyPI、Release、tag 或商业版本。

## 下一步

推送 restack 后的 PR B 并创建 Draft PR；等待远端 fast/benchmark/real-case CI 与内容审查。Draft PR 不解除 Rule Content、Real Benchmark 或 Commercial Release Hold。
