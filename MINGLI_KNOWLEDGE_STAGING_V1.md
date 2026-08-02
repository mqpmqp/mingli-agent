# MingLi 隔离知识参考服务 v1

## 目的和边界

本变更新增只读、人工审查优先的参考卡服务。它独立于确定性命盘 Runtime：参考卡不能被规则加载器读取，不能形成预测结论，也不能作为任何 Runtime 输入。

默认检索只返回同时满足下列条件的卡：

- 卡生命周期为 `reviewed` 或 `verified`；
- 来源审查状态为 `reviewed`；
- 卡和来源都显式标记为非 Runtime、非预测输入。

`review_mode=true` 仅用于人工审查。HTTP `/v1/knowledge/search` 与 MCP `tools/call` 的 `search_knowledge` 都要求精确的 `Authorization: Bearer <MINGLI_KNOWLEDGE_REVIEW_TOKEN>`。令牌未配置、缺失或不匹配均统一返回 `403 review_mode_forbidden`；普通检索不要求令牌。

## GitHub 引入合同

允许的声明精确固定为：

- `jinchenma94/bazi-skill@bdd7f863d4450bf0e2fac84579ad6b45cfdfa25c`
- `Renhuai123/ziwei-doushu@88194a404242bfe5c6d5cc512e4117e3e245cdd5`

导入器拒绝非小写的完整 40/64 位 commit ID、未允许的仓库或 commit、路径逃逸、可执行/规则包文件、个人示例、医疗资料、未核验现代断语和所有 PDF 或其他非文本资料。它先用声明 commit 的 `git ls-tree` 定位精确 blob，再用 `git cat-file blob` 读取字节；不会打开 mutable working tree 文件。

每个快照保存原始 blob 的 SHA-256。再次导入时，只要已有快照或元数据与该 blob 不一致，就失败并保持原文件不变。导入得到的来源固定为 `pending`，卡固定为 `draft`、`reference_only=true`、`runtime_eligible=false`、`prediction_eligible=false`；只有独立人工审查流程才能修改这些状态。

## 非目标

- 不执行文本识别或批量内容提取。
- 不导入文档包、个人案例、医疗材料、可执行规则或预测性结论。
- 不修改确定性排盘算法、规则、交易 Profile、数据库或运行时流程。
- 不执行服务部署、重启或任何生产调用。
