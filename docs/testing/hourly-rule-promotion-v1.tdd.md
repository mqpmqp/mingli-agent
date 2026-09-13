# Hourly Rule Promotion V1 — TDD 记录

## 验收目标

1. 小时报告可从纯 JSON 或带标记的 Markdown 代码块导入。
2. 相同规则内容不会重复创建候选；新增来源会刷新候选 hash，使旧门禁收据失效。
3. 未人工审查的来源、失败回归和未批准候选均不能发布。
4. 发布 manifest 可重算；来源撤销后 Runtime 拒绝加载。
5. 新增的版本化 Runtime adapter 只加载已发布版本，应用文本约束并保留固定免责声明；冻结基线不被修改。
6. 所有版本维持 Phase 4.1 `pilot_target=10`、零已登记真人样本、`accuracy=null` 与商业 Hold。
7. 常驻采集服务只接受三个登记自动任务，自动执行摄取、去重、来源门与合同回归；OAuth token 必须校验签名、issuer、audience、有效期和 scope。
8. 人工审核队列必须区分 `awaiting_human_approval`、`approved_not_published` 与 `published`；Phase 4.1 预测必须绑定 Runtime 实际加载的精确规则版本。

## 本地验证

安装项目 `.[dev,api]` 后执行真实测试：

- 采集器、OAuth、闭环和部署资产聚焦回归：`17 passed`；
- Fast gate：`659 passed, 159 deselected`；
- Real-case gate：`112 passed, 706 deselected`；
- 冻结合同：`ok=true`，78 个既有合同无漂移；
- `python -m build --wheel --no-isolation`：PASS，wheel 内 49 个 Schema，新增 7 个均存在；
- `python -m pip check`：PASS，无依赖冲突；
- 全量：`815 passed, 3 failed, 31 subtests passed`。3 项均在复制源码后的隔离 wheel 构建中失败；使用同样的空环境单独复现后，stderr 明确显示无法解析 `pypi.org`，因此不能下载 `setuptools>=68`。本机已安装构建依赖的非隔离 wheel 构建成功，且完整包含新增模块、命令入口和 Schema；隔离构建仍按环境失败记录，不写成 PASS。

开发中还检出了 release Schema 正则转义、来源收据缺字段、OAuth issuer/audience 归一化可能改变配置语义，以及审核队列发布状态含糊等问题，均补充测试或实现修正后复验。

这些测试是合成合同测试，不能解释为预测准确率或 Phase 4.1 真人验证结果。
