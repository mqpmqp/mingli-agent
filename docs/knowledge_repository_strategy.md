# MingLi 资料仓库策略

## 当前结论

本次任务没有收到外部原始资料目录，因此没有生成真实 inventory，也不能据此确定最终采用单仓库还是双仓库。当前代码仓库内未发现 PDF、扫描图、图片或压缩档案，但这不代表待整理资料的真实总量。

最终决策必须以 `scripts/inventory_knowledge_assets.py` 对完整原始资料目录生成的报告为准：总量小于 500 MiB 采用 `single_repo`；达到或超过 500 MiB 采用 `split_repo`。

## `knowledge/` 与 `references/` 的边界

`knowledge/` 只保存经过整理、可检索的 Markdown 或结构化数据。每项内容应能回溯到来源、页码或片段，标明审核状态；候选知识不得自动升级为已验证规则。

`references/` 只保存原始来源，例如 PDF、扫描件、截图、图片、课程压缩档案和原始案例。原始来源应保持不变，并通过 inventory 中的 SHA-256 记录完整性。原始 PDF 或 OCR/转换文本不得直接混入 `knowledge/rules/`。

未经整理、复核和来源标注的 PDF 转换结果，禁止当作规则真值。规则必须经过独立的生命周期与现实边界审查。

## 单仓库方案

适用条件：完整原始资料总量小于 500 MiB。

- 代码、规范、结构化知识和原始来源都保留在 `mqpmqp/mingli-agent`。
- Markdown、JSON、JSONL、YAML、YML 和 Python 直接进入普通 Git。
- PDF、常见扫描图、图片和压缩档案通过 Git LFS 存放在 `references/`。
- 导入前仍须检查许可、隐私、重复文件和单文件大小。

优点是检索、版本和引用关系集中；代价是克隆体积和 LFS 流量随资料增长。

## 双仓库方案

适用条件：完整原始资料总量达到或超过 500 MiB。

- `mqpmqp/mingli-agent` 继续保存运行时、只读 `spec/`、文档、脚本和整理后的结构化知识。
- 新仓库 `mqpmqp/mingli-knowledge` 保存原始二进制资料、较大数据集和 inventory。
- 两仓之间使用稳定的来源 ID、相对路径和 SHA-256 关联，不复制规则真值。
- 未经确认不得创建远端仓库、移动原始文件或推送大型二进制文件。

建议的 `mingli-knowledge` 结构：

```text
mingli-knowledge/
├── references/
│   ├── books/
│   ├── papers/
│   ├── courses/
│   ├── screenshots/
│   ├── images/
│   └── cases/
├── datasets/
├── inventories/
└── README.md
```

## 阈值与 GitHub 风险

500 MiB 是本项目的仓库拆分决策阈值，按 `500 * 1024 * 1024` bytes 计算。它不是 GitHub 的技术上限，而是控制克隆成本、历史膨胀和 LFS 运维复杂度的工程门槛。

GitHub 普通 Git 对单文件 100 MB 存在硬性风险：大于 100 MiB 的文件不得直接提交到普通 Git。inventory 会分别列出大于 50 MiB 和 100 MiB 的文件；这类文件必须先人工确认 Git LFS、拆分仓库或外部存储方案。

## Git LFS

仓库 `.gitattributes` 已为 PDF、PNG、JPEG、TIFF 和常见压缩档案配置 LFS。首次使用前安装并初始化：

```bash
git lfs install
git lfs pull
```

确认属性：

```bash
git check-attr filter -- references/books/example.pdf
```

不要对 Markdown、JSON、JSONL、YAML、YML 或 Python 源码使用 LFS。提交二进制文件前必须确认本机和 CI 均支持 Git LFS。

## 导入流程

1. 对完整、只读的原始资料路径运行 inventory：

   ```powershell
   python scripts/inventory_knowledge_assets.py `
     "D:\待整理资料目录" `
     --json-output reports/knowledge_inventory.json `
     --markdown-output reports/knowledge_inventory.md
   ```

2. 检查读取错误、重复 SHA-256、许可、隐私以及大于 50/100 MiB 的文件。
3. 生成只读计划：

   ```powershell
   python scripts/plan_knowledge_import.py `
     reports/knowledge_inventory.json `
     --json-output reports/knowledge_import_plan.json `
     --markdown-output reports/knowledge_import_plan.md
   ```

4. 人工确认 `single_repo` 或 `split_repo`，并确认每类资料的领域和目标目录。
5. 另开分支，小批量复制资料；复制后重新计算 SHA-256。脚本本身不会执行复制或移动。
6. 先提交来源清单，再提交整理结果；规则晋级走独立审核流程。

报告工具拒绝覆盖已有文件。需要新一轮报告时使用新文件名，保留旧报告作为审计记录。

## 回滚方式

- 尚未提交：先核对 `git status`，仅撤销本次新增的暂存项；对手工复制的新文件，确认其仍有原始来源后再删除副本。
- 已提交但未共享：优先新增修正提交，避免改写包含 LFS 对象的历史。
- 已推送：使用 `git revert` 创建可审计的回滚提交；不要直接强推或清理 LFS 历史。
- 双仓库迁移：以 inventory SHA-256 校验原始资料仍完整，再分别回滚两个仓库中的引用提交。

任何回滚都不得删除唯一一份原始资料。
