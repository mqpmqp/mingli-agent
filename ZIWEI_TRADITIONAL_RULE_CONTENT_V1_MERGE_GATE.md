# Ziwei Traditional Rule Content v1 — Local Merge Gate

日期：2026-07-16

分支：`agent/ziwei-traditional-rule-content-v1`

堆叠基线：`82bca1599aefde27332eab055ce7f8a57d121ed1`

最终验证代码：`cab5d73`（运行时修复：`840872d`）

规则版本：`ziwei-traditional-rule-content@1.0.0`

## 结论

- Local Merge Gate：**PASS**。
- 独立终审：**PASS**；已发现的 P2 全部关闭，未发现剩余 P0–P2。
- 外部交付：**NOT EXECUTED**。PR B 未推送、未创建远端 PR；PR A Draft #28 合并前保持本地。
- 覆盖状态：`REVIEW_REQUIRED`；184 条规则均为 `draft`，Rule Content Hold 继续 **ACTIVE**。
- Prediction Validity：`not_evaluated`；工程覆盖不表示预测准确率。

## 独立审查与 TDD 闭环

首轮实现之后，独立 reviewer 与本地行为探针共发现跨规则目标 priority 压制、畸形完整盘事实注入、非主星 coverage false pass、同 state 不同星冲突、嵌套非 supported 事实、过宽 trigger 与缺失 exclusions 等 P2。

| 阶段 | Commit | 可复核结果 |
|---|---|---|
| 初始合同 RED | `8ff4dd7` | 2 个 collection errors，目标 API 尚不存在 |
| 初始实现 GREEN | `940a4f9` | 184 条打包规则与基础行为闭环 |
| 首轮防伪 | `cc9ec9f` | loader、condition、畸形命盘与 protected fact 加固 |
| 独立审查 RED | `d538241` | 2 failed / 9 passed |
| 独立审查 RED | `6e7c13e` | 4 failed / 9 passed |
| 独立审查 GREEN | `8691d7c` | 受影响目标 14 passed |
| 终审 RED | `fc8036c` | 6 failed |
| exclusions RED | `156bfa7` | 1 failed |
| 终审 GREEN | `840872d` | 定向 7 passed；终审 PASS |
| 状态矩阵闭环 | `cab5d73` | 五类嵌套字段 × 两种非 supported 状态，10 passed |

最终行为：冲突键由 domain、subject 与规范化 trigger 共同确定；完整盘必须通过 Schema、十二宫/二十八星/四化交叉约束与嵌套 supported gate；coverage 对 184 条规则校验 canonical trigger、必需 exclusions、正样本、空目标、degraded 和 unsupported 负样本。

## 最终本地验证

| 门禁 | 结果 |
|---|---|
| 规则/Runtime/CLI 聚焦与覆盖 | 63 passed；总覆盖 88.24%；`ziwei_rules` 89%，`ziwei_runtime` 86% |
| Ziwei 全集 | 96 passed |
| 全量 pytest | 363 passed，1 skipped，31 subtests；24:25 |
| fast gate | 267 passed，1 skipped，96 deselected，16 subtests；3:28 |
| benchmark gate | 38 passed，326 deselected，15 subtests；21:58 |
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

等待 PR A Draft #28 完成审查并合并；随后将 PR B 整理到最新 `main`，重新运行本报告全部门禁，再创建正式 Draft PR B。PR A 合并前不得推送 PR B，也不得解除任何 Hold。
