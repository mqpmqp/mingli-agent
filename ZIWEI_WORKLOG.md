# Ziwei Capability Closure Worklog

## 2026-07-16 — PR A 本地独立审查与 Merge Gate

- 审查：逐项核对 engine、Schema、Runtime、CLI、固定盘、来源和 Hold 文档；确认核心排盘范围与已声明 profile 一致。
- 修复：发现自定义 benchmark 可由空案例、过期算法版本或空期望产生 false pass；新增 RED commit `7437c06`，并以 GREEN commit `079c084` 实施 fail-closed 校验。
- 验证：紫微聚焦 44 passed，覆盖率 84.19%；Ruff/Pyright/compileall 通过；fast 215 passed/1 skipped，benchmark 38 passed，real_case 58 passed；wheel/sdist 与 wheel 内五局 benchmark/Schema 冒烟通过。
- 状态：本地 Merge Gate PASS；分支未推送、未创建 PR，Traditional Engine Hold 继续 ACTIVE；Rule Content、Real Benchmark、Commercial Release 继续 ACTIVE。
- 下一步：获得明确外部写操作授权后推送分支，创建 Draft PR 并等待远端独立审查/CI；不得在合并前解除 Hold。

## 2026-07-16 — PR A：Deterministic Ziwei Engine v1

- 来源：古籍全文入口、公开公式转写和 MIT `iztro@f3dc6c5` 三层核验；没有调用外部排盘 API。
- 实现：命身宫、五行局、十四主星、十四辅煞、四化、基础亮度、严格 Schema、CLI 和五局固定盘。
- 状态：已知时辰 `complete`，未知时辰继续 `degraded`；规则覆盖仍为 0/168。
- Hold：Traditional Engine 等待 Draft PR 独立审查与合并；Rule Content、Real Benchmark、Commercial Release 继续 ACTIVE。

## 2026-07-16 — Phase 0–1：基线与差距审查

- 完成事项：创建本地分支；读取仓库指令、技术栈、CI、Schema/Runtime/Renderer/benchmark；确认仓库无紫微实现与测试；合规观察外部公开输入流程；建立审计、能力矩阵、测试缺口矩阵与实施计划。
- 修改文件：`docs/audits/*.md`、本工作日志。
- 验证结果：快测门禁 177 passed、1 skipped、90 deselected、16 subtests passed；紫微测试 0 selected。
- 方案变化：由于不存在可审查的紫微算法或合法规则资产，实施范围固定为可验证 P0 底座；传统排盘/规则内容维持显式 NO-GO，不以猜测补齐。
- 剩余任务：Schema/时间合同、fingerprint/隔离、规则框架、Runtime/Evidence/Yuan、案例隐私合同、CLI、完整验证与发布报告。
- 阻塞：传统紫微排盘算法与规则内容缺少独立可靠来源；不阻塞 P0 工程合同。
- 下一阶段：以 RED 测试固化 P2–P4 边界，再实现 GREEN。

## 2026-07-16 — Phase 2–9：P0 工程闭环与安全 P1

- 完成事项：新增 12 类紫微 Schema；实现公农历归一、三种太阳时模式、晚子时与未知时辰降级；建立 partial 命盘壳、稳定 fingerprint、六级时间上下文、scope/cache/revision/pair 隔离；建立规则卡/冲突/覆盖门禁；接入 Phase18 reality hard override 与 Phase20 Yuan；新增同意门禁 benchmark 框架和 CLI。
- 修改文件：`src/mingli/ziwei*.py`、`src/mingli/contracts/schemas/ziwei_*.json`、`src/mingli/cli.py`、`tests/test_ziwei_*.py`、`docs/ziwei/*`。
- 验证结果：RED 检查先因缺失模块/命令失败；GREEN 聚焦测试 20 passed；benchmark 聚焦 6 passed。
- 方案变化：传统排盘和规则内容继续保持 NO-GO；Runtime 只允许 partial/degraded 与 low-only confidence。
- 剩余任务：完整测试、构建、CLI 真实进程冒烟、最终三份报告、Release Gate 与最终提交。
- 阻塞：无 P0 硬阻塞；真实紫微算法来源和授权案例不足阻塞传统引擎、规则内容、真实 benchmark 与商业发布。
- 下一阶段：Phase 10 全量验证与发布报告。

## 2026-07-16 — Phase 10：验证、报告与发布门禁

- 完成事项：生成闭环、验证、发布准备三份最终报告；更新架构、字段、时间、规则来源、测试、迁移、限制与隐私说明；提升 wheel Schema 数量门禁并校验 12 份紫微资源；完成构建与 CLI 冒烟。
- 修改文件：`ZIWEI_*REPORT.md`、`ZIWEI_RELEASE_READINESS.md`、`docs/ziwei/*`、`tests/test_derived_contracts.py`。
- 验证结果：21 个紫微聚焦测试通过；12 Schema 合法；compileall exit 0；快测 197 passed/1 skipped；完整最终 288 passed/1 skipped/31 subtests；wheel+sdist 构建成功；CLI 与 coverage 冒烟 exit 0。
- 剩余任务：需要独立可靠来源与授权案例后，才能另行实施传统排盘、规则内容和真实案例校准。
- 阻塞：对 P0 无阻塞；Deterministic Ziwei engine、Rule Layer、Real Case Benchmark、Commercial Release 保持 NO-GO。
- 下一阶段：本地分支交付；不 push、不建 PR、不合并。
