# 来源注册表

`knowledge/sources/registry.jsonl` 保存来源元数据。ID 为文件 SHA-256 前 12 位组成的 `src_sha256_<digest>`，因此不受机器或 checkout 路径影响。记录只使用仓库相对路径，并包含完整 SHA-256、大小、媒体类型、领域、许可与导入状态。

相同哈希复用同一注册记录。symlink 默认拒绝；指向仓库外的 symlink 明确失败。注册表不得包含用户名、HOME 或绝对路径。试点不提交原始 PDF，登记的 PDF 哈希来自只读 source map。
