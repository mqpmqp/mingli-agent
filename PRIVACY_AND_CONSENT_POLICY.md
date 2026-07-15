# Privacy and Consent Policy

公开仓库、wheel、sdist 与 GitHub Release 禁止包含姓名、手机号、邮箱、证件号、精确家庭地址、聊天截图、原始授权文件或可反推个人的完整命盘与经历组合。原始身份映射和项目 salt 必须存放在 Git 外的独立受控系统。

每个案例必须取得明确的 research 与 benchmark consent，记录不可逆 consent reference，并支持撤回。`publication_use_allowed=false` 不影响合规的私有验证，但该案例不能进入任何公开案例资产。撤回后必须生成新 dataset version 和 manifest；旧 manifest 保留审计状态但不得继续授权发布。

导入前运行 schema、consent、provenance 与 PII 检查。默认 store 必须位于当前 Git checkout 外。命令不会自动 `git add` 或提交数据。发布资产只允许聚合指标、schema、空模板与不可逆 hashes。

发生疑似泄漏时立即停止导入，撤销相关 dataset/authorization，轮换受影响引用，并按组织隐私事件流程处理。不要在 issue、PR 或 CI log 中粘贴原始案例。
