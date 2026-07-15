# MingLi Agent V2.0 产品闭环与训练循环 Preflight

日期：2026-07-15  
分支：`codex/v2-product-training-loop`  
基线提交：`e99aa2a5d04c4cdbac6e027e2f95bffdbbcb454b`

## 1. 本轮范围与不可越界事项

本轮只关闭两个工程主题：

1. 把现有确定性能力整理为可运行、可追踪、可降级的 V2.0 产品运行链；
2. 建立由日常计算、授权反馈和后续观察驱动的 Training Loop。

本轮不收集未授权真实案例，不运行真实案例准确率 benchmark，不把用户主观反馈或已知历史事件包装成预测命中，不自动修改规则或知识库，也不执行 push、PR 或 merge。`spec/` 保持不变。

既有 ETL 安全边界继续生效：明确同意、HMAC 去标识、真实数据存储在 Git 仓库外、Rodden/来源质量边界、时区与经度派生的 local mean solar time。产品运行时不得降低这些约束。

## 2. 当前真实能力审计

### 2.1 已存在且应直接复用

- `src/mingli/phase23.py` 已经形成真实的端到端调用链，不是 mock：
  - `DeterministicBaziEngine`
  - Phase 7 事实图
  - Phase 9 日主强弱
  - Phase 10 格局
  - Phase 11 调候
  - Phase 12 喜忌
  - Phase 13 运势交互
  - Phase 14 时序趋势
  - Phase 15 领域判断
  - Phase 16 领域契约
  - Phase 17 可选场景
  - Phase 18 现实归一化与证据融合
  - Phase 19 称骨
  - Phase 21 五年边界输出
  - Phase 20 Yuan 八段模板渲染
- Phase 18 已实现 claim/scope 级现实证据硬覆盖，并保留冲突证据与 provenance；该机制必须作为产品运行时的权威现实约束。
- Phase 20 是受控模板层，只消费结构化结果，不负责新增计算；已固定八段结构、单一免责声明和禁承诺边界。
- Phase 16 已输出 `rule_set_hash`，可以作为规则追踪锚点。
- 现有结果广泛使用 `schema_version`、`method_id`、`calculation_version`、`canonical_hash` 与 `prediction_validity=not_evaluated`，新契约应沿用这套风格。
- `src/mingli/validation_privacy.py` 已提供 HMAC-SHA256 `person:<digest>` 去标识和 PII 扫描。
- `src/mingli/validation_astro_etl.py` 已提供 IANA 时区处理和经度派生 local mean solar time；产品层只消费已通过这些边界的输入，不另造简化算法。
- `src/mingli/validation_freeze.py` 已提供不可变预测快照、结构化 claim 预注册和现实证据不可见约束；商业验证继续使用这条路径。
- `src/mingli/validation_authorization.py` 与 Phase 24 已有旧版 `PRODUCT_RELEASE_HOLD/ALLOWED` 契约，必须兼容保留。

### 2.2 当前缺口

- Phase 23 结果尚缺统一产品 envelope 所需的 `created_at`、显式 engine/rule/renderer 版本、总置信度与原因、limitations、现实证据使用摘要、sections 以及可直接消费的 trace/provenance 引用。
- Phase 23 直接抛出 `Phase23InputError`；尚无稳定错误码、`blocked/degraded/error` 状态或 JSON 错误 envelope。
- 产品运行入口尚无 consent gate，也不能在明确授权时选择性写入训练存储。
- 缺少 `TrainingCase`、`AnalysisRun`、`UserFeedback`、`OutcomeObservation`、`RuleReviewCandidate`、`TrainingIteration` 契约和持久化实现。
- 缺少反馈类型边界。当前任何反馈都不能被解释成准确率；后续必须显式区分主观反馈、历史事实纠正、事后结果观察和预注册结果。
- 缺少仓库外 JSON/JSONL 训练存储、仓库内真实数据拒绝、撤回/删除、tombstone、派生记录失效和非 PII 审计。
- 顶层 `mingli` CLI 只有通用能力和 `validation` 转发，尚无 `mingli training run|feedback|outcome|show|review|candidates`。
- Phase 24 把技术就绪、真实案例 closure 与产品发布授权绑定在一起，无法表达“产品能力可供开发运行，但商业验证仍待完成”。

## 3. 目标架构与兼容策略

本轮预计新增 `src/mingli/product_runtime.py`、`src/mingli/training.py`、`src/mingli/training_cli.py`、`src/mingli/product_readiness.py` 及对应 contracts schemas/tests；修改 `src/mingli/cli.py`、package-data/schema export 和必要的发布文档。除兼容字段外，不改 Phase 7–24 的核心算法，也不改 `spec/`。

审计中存在三种合理实现：直接扩展 Phase 23、另建平行 runtime、或在 Phase 23 外增加产品兼容层。直接扩展会把 consent/storage 副作用带入现有纯计算 API；平行 runtime 会复制计算链。故选择最小的兼容层：Phase 23 仍是纯确定性核心，新产品层只负责门禁、envelope 和可选持久化。

### 3.1 产品运行链

新增产品兼容层，调用而不是复制 Phase 23：

`Intake -> consent/privacy -> deterministic chart -> reality normalization -> rules -> evidence fusion -> confidence -> Yuan renderer -> result envelope -> optional feedback`

Phase 23 继续保持既有 Python API 和返回模型，避免破坏已有测试与调用方。新产品入口负责：

- 输入契约、同意与 PII 边界；
- 将 Phase 23 的实际产物整理成稳定 envelope；
- 计算整体置信度与可解释原因，不覆盖领域级置信度；
- 输出八段 sections、limitations、现实证据使用摘要和 trace/provenance；
- 将可恢复缺口降级为 `degraded`，把无法可靠排盘或核心字段缺失返回为 `blocked`；
- 只有 `training_consent=true` 且提供合规外置 store 时才写训练记录。

`created_at` 作为输入契约的一部分进入哈希；同一输入（包括同一时间戳）必须产生完全相同的运行结果。CLI 不把运行时当前时间偷偷混入确定性计算。

### 3.2 Training Loop

训练对象使用不可变 JSON 记录和显式 lifecycle：

- `TrainingCase`：去标识 case、同意范围、数据质量、来源边界与生命周期；
- `AnalysisRun`：输入 manifest、版本/hash、产品结果摘要和可重放引用；
- `UserFeedback`：反馈类别、目标 section/claim、主观评分或纠正内容，以及 `counts_toward_accuracy=false`；
- `OutcomeObservation`：观察时间、证据类型、与先前 claim 的关系、是否预注册；
- `RuleReviewCandidate`：只生成待人工审查候选，不写规则库；
- `TrainingIteration`：锁定输入记录、候选集、审查状态与迭代结论。

反馈和准确率严格分离：

- 主观反馈只用于可读性、相关性和产品体验；
- 历史事实纠正只用于修正输入/现实上下文；
- 后续结果观察只有在满足独立商业验证协议时才可能进入验证数据；
- 只有预先冻结的结构化 claim、隔离现实证据、独立评分和可复现数据集才可计算准确率。

### 3.3 存储与隐私

默认 store 必须位于仓库外。路径解析后如果落在 Git 仓库内则拒绝；只有显式 `synthetic=true` 才允许仓库内合成测试数据。所有待写记录在落盘前运行 PII 扫描。

建议布局：

```text
training-store/
  cases/
  runs/
  feedback/
  outcomes/
  candidates/
  iterations/
  tombstones/
  audit.jsonl
```

撤回时删除或使 case 关联派生记录失效，写入只含不可逆 case 引用摘要、动作、时间和计数的 tombstone/audit；不得保留姓名、联系方式、原始身份标识或 HMAC salt。

### 3.4 双发布门

新增独立双门评估，不改变旧 Phase 24 字段语义：

- Product Readiness Gate：运行时、knowledge、rules、evidence、renderer、ETL、training、privacy、fast tests、build/static checks。
- Commercial Validation Gate：授权真实案例、预冻结 claims、结果时间边界、独立评分、泄漏控制、可复现 benchmark、准确率报告与风险审批。

目标状态为：

- `PRODUCT_CAPABILITY_READY`
- `COMMERCIAL_VALIDATION_PENDING`

该组合允许 development runtime，但必须阻止 production-commercial 模式、商业准确率声明和以未授权案例/普通反馈充当验证证据。旧 `PRODUCT_RELEASE_HOLD/ALLOWED` 仍可由原接口读取。

## 4. TDD 与验收矩阵

先写失败测试，再实现最小行为。至少覆盖：

- 合法输入完整成功；
- 缺出生字段返回结构化 blocked error；
- 未授权时不写训练存储；
- 现实证据硬覆盖规则结论；
- 低置信度和 unresolved 降级；
- 核心计算不可用时 blocked；
- 同一输入完全确定；
- 输出与存储无原始身份泄漏；
- Yuan 八段完整且渲染层不改计算；
- CLI 全部子命令为稳定 JSON 和稳定退出码；
- 仓库内真实 store 被拒绝、显式 synthetic store 可用于测试；
- 撤回产生 tombstone、派生记录失效和非 PII audit；
- rule candidates 只能进入人工 review 状态；
- 产品能力 ready 不等于商业验证 ready，commercial 模式正确阻断；
- 旧 Phase 23/24 API 与测试保持通过。

## 5. 验证与报告计划

依次运行 targeted tests、产品 runtime E2E、training/privacy/release tests、全部 fast tests、`compileall`、关键模块 `py_compile`、wheel build、`git diff --check`、secret/PII 扫描、Ruff 与 Pyright 相对历史基线的 delta 检查、`pip-audit`。真实案例和 benchmark 测试作为独立门诚实报告，不把缺数据、未运行或普通反馈描述成准确率结论。

最终实现报告必须列出命令、退出码、测试数量、已知限制和未关闭的商业验证条件。
