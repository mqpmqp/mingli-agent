# PHASE_16_DOMAIN_CONTRACT_BASE_RULES_V1 Report

## 范围

Phase 16 在 P15 动态十神领域判断候选之上，新增事业、财运、感情三个基础领域的确定性判断合同与 reviewed 基础规则。

实现领域：

- `career`
- `wealth`
- `relationship`

每个目标、每个领域固定输出四个基础维度：

- 事业：角色结构、交付路径、资历支持、商业执行
- 财运：收入转化、资源管理、风险纪律、分配压力
- 感情：沟通表达、边界承诺、现实交换、照顾依赖

## 实现内容

- P16 版本化合同、记录摘要和 canonical hash
- 12 条 reviewed 基础规则，每个领域 4 条
- P15 顶层哈希与嵌套领域判断摘要校验
- 基于 P15 `active_theme_codes` 的确定性规则匹配
- 完整基础维度分区；无匹配证据的维度保持 `unresolved`
- P15 判断标签、置信度、现实硬覆盖方向和证据 ID 原样继承
- 年份、年龄、目标和领域索引及查询
- CLI：`evaluate`、`query`、`validate`、`benchmark`、`rules`、`schemas`、`provenance`
- 源码与隔离 wheel 的 P16 校验、基准和 canonical hash 一致性检查

## 边界

- P16 只消费 P15 结果，不重算四柱、旺衰、喜忌、大运、流年或十神。
- 基础规则只把已激活主题归入固定判断维度，不把主题转换为具体事件。
- P15 现实硬覆盖只在原目标和原领域内保留，不扩张到其他目标、领域或维度。
- 结构规则不提升为 `verified`；规则清单固定为 `reviewed`。
- 不输出升职、解雇、录用、收入金额、盈亏、投资建议、结婚、复合、分手、外遇或对象数量。
- 不输出吉凶保证或自然语言命理解答。
- 所有成功结果固定 `prediction_validity=not_evaluated` 与 `domain_contract_validity=base_rules_only`。
- `spec/`、`knowledge/` 和 P1-P15 算法未修改。

## 附件处理

本阶段收到的附件主要属于风水、河图洛书、八卦和周易背景资料，不足以直接支持事业、财运、感情八字基础规则的 verified 升级。本阶段未导入附件、未执行全书 OCR，也未把附件内容写入生产规则。

## 文件

- `src/mingli/phase16.py`
- `src/mingli/phase16_cli.py`
- `src/mingli/phase16_contracts.py`
- `src/mingli/derived/data/phase16_base_domain_rules_v0.1.json`
- `src/mingli/derived/data/phase16_base_domain_assertions_v0.1.json`
- `tests/test_phase16_domain_contracts.py`
- `pyproject.toml`
- `.github/workflows/test.yml`
- `README.md`

## 基准结果

`python -m mingli.phase16_cli benchmark` 的结果：

- `assertions_total`: 4207
- `passed`: 4207
- `failed`: 0
- `unresolved`: 0
- `schema_failures`: 0
- `provenance_failures`: 0
- `hash_mismatches`: 0
- `rule_coverage_failures`: 0
- `contract_partition_failures`: 0
- `reality_preservation_failures`: 0
- `query_failures`: 0
- `prediction_boundary_failures`: 0

矩阵覆盖 10 个日干 × 12 个月支，另含现实硬覆盖保留、年份/年龄/目标查询、输入篡改拒绝和具体事件输出阻断。

## 验证计划

最终验证包括：

- Python 编译
- P16 规则校验与完整基准
- 全量 unittest 与 pytest
- spec、规则、静态基准、knowledge、确定性排盘和 P6-P15 回归门禁
- sdist/wheel 构建
- 临时隔离虚拟环境安装 wheel
- 隔离 wheel 下 P16 校验、基准与 source/install canonical hash 相等
- `git diff --check`
- `spec/` 和 `knowledge/` 相对 `origin/main` 无差异

本地已完成 P16 聚焦测试、P15 直接上游回归、P16 源码基准、wheel 构建、隔离 wheel 基准、source/install canonical hash 一致性、编译和 diff 检查。全仓 `unittest` / `pytest` 及依赖这些测试库的既有门禁由 GitHub Actions 执行；本地第一次运行因未安装 `jsonschema` / `pytest` 在导入阶段失败，随后依赖镜像持续代理超时，未将该环境失败计为代码测试结果。
