# Phase 2 Knowledge OS 架构审查

## 审查结论

**结论：PR #1 暂不适合直接合并。**

它适合作为 Tianfu Agent 知识层的仓储与资料治理起点，但还不是完整的 Knowledge OS 基础。当前方案正确建立了“原始来源与整理知识分离”、只读 inventory、SHA-256 去重、Git LFS 和单/双仓决策边界；缺口是缺少稳定来源登记、派生物追踪，以及 concept / rule / evidence / benchmark 四层的显式目录与数据合同。

建议在 PR #1 内完成小范围架构调整后再合并。不需要导入 PDF，不需要修改 Core Runtime，也不应改动现有 `spec/`。

## 审查范围

- `.gitattributes`
- `references/`
- `datasets/`
- `knowledge/`
- `scripts/inventory_knowledge_assets.py`
- `scripts/plan_knowledge_import.py`
- `docs/knowledge_repository_strategy.md`
- `tests/test_knowledge_tools.py`
- 现有 `spec/knowledge/ingestion/`、`spec/schemas/evidence.schema.json` 与 `spec/evaluation/` 合同

## 是否适合作为 Tianfu Agent 知识层基础？

**有条件适合。**

可保留的基础：

- 原始资料放在 `references/`，整理结果放在 `knowledge/`，边界正确。
- inventory 只读扫描、计算 SHA-256、识别重复项和大文件，适合导入前审计。
- import planner 只生成计划，不复制、移动或升级规则，安全边界正确。
- 500 MiB 作为工程分仓门槛是可接受的初始策略。
- 未经复核的 OCR、摘要和候选规则不能成为 verified 真值，与现有 ingestion policy 一致。

合并前必须补齐：

- 稳定 `source_id` 和来源登记表。
- concept / rule / evidence / benchmark 四层的明确落点。
- raw、derived、reviewed、runtime 之间的晋级边界。
- 可机器校验的导入批次 manifest 与回滚信息。
- datasets 的职责、隐私边界和版本策略。
- PR #1 需要基于已合并 PR #2 后的最新 `main` 更新，当前分支已落后且存在合并冲突。

## 四层结构支持度

| 层 | 当前支持 | 判断 | 缺口 |
| --- | --- | --- | --- |
| Concept | `knowledge/<domain>/` 可存 Markdown/结构化知识 | 部分支持 | 没有统一 concept 路径、ID、来源和审核状态合同 |
| Rule | `knowledge/rules/` 空目录；`spec/rules/` 已有运行时规则 | 部分支持 | 容易与生产规则混淆；缺少 candidate/reviewed 边界和晋级说明 |
| Evidence | inventory 有 SHA-256；现有 spec 有 Evidence schema | 不足 | 没有 evidence 层目录、citation/case/source linkage，也没有反证资产位置 |
| Benchmark | `knowledge/benchmark_notes/` 仅作为笔记目录 | 不足 | 没有案例、期望、rubric、结果与版本的明确结构；不能替代 `spec/evaluation/` |

因此，PR #1 **尚未完整支持 concept / rule / evidence / benchmark 四层结构**。

## 建议的最小目录调整

建议把“领域”作为四层内部属性或次级目录，不让领域目录替代知识生命周期：

```text
knowledge/
├── README.md
├── registry/
│   └── sources.jsonl
├── concepts/
│   ├── bazi/
│   ├── ziwei/
│   ├── qimen/
│   ├── fengshui/
│   ├── yijing/
│   └── yuan/
├── rules/
│   └── candidates/
├── evidence/
│   ├── citations/
│   └── cases/
└── benchmarks/
    ├── cases/
    ├── rubrics/
    └── results/

references/
├── README.md
├── books/
├── papers/
├── courses/
├── images/
├── screenshots/
└── cases/

datasets/
├── README.md
├── derived/
│   ├── chunks/
│   ├── evidence/
│   └── benchmarks/
└── manifests/
```

约束：

- `knowledge/rules/candidates/` 只存候选或审核工作资产，不被 Core Runtime 自动加载。
- 生产规则仍以现有 `spec/rules/` 合同为准，晋级必须经过人工审核和 benchmark。
- `knowledge/benchmarks/` 是研究和构建区；已冻结的验收基线仍由 `spec/evaluation/` 管理。
- `datasets/derived/` 只放可重建的结构化派生物，不放唯一原始资料。
- 每个派生物必须包含或关联 `source_id`、源 SHA-256、生成方式、生成版本和审核状态。

## Git LFS 策略

### 正确部分

- PDF、PNG、JPEG、TIFF 与常见压缩包使用 LFS，方向正确。
- Markdown、JSON、JSONL、YAML 与 Python 保持普通 Git，便于 diff 和审查。
- 文档明确不能把 LFS 当作来源审核或规则晋级机制。

### 合并前建议调整

当前规则是全仓库扩展名匹配，会影响未来任何目录下的图片，而不只是 `references/`。建议明确选择：

- 原始二进制只在 `references/**` 和必要的 `datasets/**` 使用 LFS；或
- 保持全仓规则，但在文档中明确所有仓库图片都走 LFS。

推荐第一种，以免小型文档图、测试 fixture 和 UI 资产无意进入 LFS。

当前 planner 将 `.tar`、`.gz` 视为原始压缩档案，但 `.gitattributes` 没有对应 LFS 规则；`.epub`、`.docx` 等原始文档同样未覆盖。应让 planner 分类与 LFS 策略使用同一扩展名清单，避免“计划认为是大二进制，Git 属性却未接管”。

LFS 不能替代：

- 许可和隐私检查
- 单文件/总量配额管理
- 来源登记
- 备份
- 双仓决策

## references 结构

当前 `books/papers/courses/screenshots/images/cases` 分类可作为物理来源目录，但缺少每项来源的最小元数据。

每个来源至少需要：

- `source_id`
- 原始文件相对路径
- SHA-256
- 来源名称与类型
- 许可或版权模式
- 获取日期
- 隐私等级
- 是否允许 OCR、引用、训练或外部分享
- supersedes / duplicate_of
- review status

建议通过 `knowledge/registry/sources.jsonl` 或 `datasets/manifests/source_registry.jsonl` 统一登记，而不是依赖文件名表达语义。

`references/cases/` 必须只接受经许可和去敏的案例。含个人信息的原始案例不应默认进入 Git 或 LFS；需要在 README 中增加明确拒绝条件。

## datasets 结构

当前只有 `datasets/.gitkeep`，不足以形成治理边界。

应补充 `datasets/README.md`，明确：

- 只存结构化数据和可重建派生物。
- 不把原始 PDF 或唯一来源放入 datasets。
- 区分 chunks、evidence、benchmarks 和 manifests。
- 大型 CSV、Parquet、SQLite 的存储策略必须单独评估，不能只按扩展名自动导入。
- 私密、未去敏或无许可数据不得提交。
- 每个 dataset 记录 schema version、生成命令、源 manifest 和内容 hash。

## Inventory 脚本

### 优点

- 只读。
- SHA-256 分块计算。
- 识别重复内容。
- 汇总扩展名和体积。
- 报告超过 50/100 MiB 文件。
- 输出拒绝覆盖已有报告。
- 对读取失败返回非零状态。

### 风险与调整建议

1. 报告保存绝对路径，可能暴露用户名、盘符和私人目录结构。持久化报告应优先使用相对扫描根的路径；绝对根路径可选择性脱敏。
2. inventory 没有生成稳定 `source_id`，无法可靠连接 concept、rule、evidence 和 benchmark。
3. 文件 symlink 会被 resolve 为目标路径，可能扫描根目录之外的文件并丢失逻辑来源路径。应明确拒绝 symlink，或同时记录 logical path 与 resolved path，并标记越界。
4. 缺少许可、隐私和可处理权限字段。脚本无需自动判断，但应为人工审核状态预留字段。
5. planner 对 inventory 的逐文件字段校验较弱，`path`、`size_bytes`、`sha256` 可能缺失仍生成计划。
6. 500 MiB 决策使用 inventory 总量；文档描述的是“原始资料总量”。若输入混合结构化派生物，应按 raw-source 体积决策或明确要求 inventory 输入只能包含原始来源。

## 导入与回滚机制

现有方案是“计划但不执行”，因此当前不会破坏来源，安全性良好。文档也正确要求已推送变更使用 `git revert`，不强推或清理 LFS 历史。

但它还不是完整的可回滚导入机制。真实导入前需要一个批次 manifest，至少记录：

- `batch_id`
- inventory schema/version
- source path 与 source SHA-256
- destination repository/path
- destination SHA-256
- action（copy/skip/reject）
- LFS expectation
- operator/reviewer
- timestamp
- commit SHA
- rollback status

导入应采用 copy → destination hash verify → commit 的顺序，不移动或删除唯一来源。回滚应以 batch manifest 精确定位本批新增文件，禁止依赖人工回忆或模糊的 `git status`。

本阶段不建议实现自动复制器；先补齐 manifest 合同和 dry-run 验收即可。

## 合并建议

PR #1 当前建议状态：**REQUEST CHANGES / 保持 Draft**。

合并门槛：

1. 更新分支到最新 `main`，解决 PR #2 合并后的冲突。
2. 调整为显式四层 Knowledge OS 结构。
3. 补充 `datasets/README.md` 和来源 registry/manifest 设计。
4. 对齐 planner 分类与 Git LFS 扩展名策略。
5. inventory 持久化路径去敏，并定义 symlink 边界。
6. 增加 import batch manifest 与回滚合同。
7. 保持 `spec/`、`src/mingli/` 和 Core Runtime 不变。
8. 重新运行现有测试及 knowledge tools 测试。

## 最终回答

- 是否适合作为 Tianfu Agent 知识层基础：**适合作为资料治理骨架，但需调整后才能作为 Knowledge OS 基础。**
- 是否支持 concept/rule/evidence/benchmark 四层：**目前仅部分支持 concept 和 rule，evidence 与 benchmark 不足。**
- 是否需要调整目录：**需要；应从纯领域目录改为“知识生命周期四层 + 层内领域分类”。**
