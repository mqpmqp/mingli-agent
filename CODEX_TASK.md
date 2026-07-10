# Codex 执行任务：MingLi Core Runtime v0.1

## 目标

将 `spec/` 中的 MingLi Agent v0.7 规范落成一个最小可运行、可测试的 Python 核心库。

这不是完整算命产品。首版只实现可确定验证的基础设施，不实现真实排盘算法、LLM 调用、OCR、数据库、Web UI 或生产部署。

## 启动前检查

1. 读取 `AGENTS.md`。
2. 检查当前仓库、默认分支、远端、HEAD 和工作树。
3. 如果当前目录不是目标仓库或存在未说明的修改，停止并报告。
4. 新建分支：
   `codex/mingli-core-runtime-v0.1`
5. 不读取 `.env`，不输出环境变量。

## 应实现的目录

```text
pyproject.toml
README.md
src/mingli/
  __init__.py
  cli.py
  models.py
  errors.py
  schema_loader.py
  rule_loader.py
  evidence.py
  reality.py
  confidence.py
  renderer.py
  router.py
  chart_provider.py
tests/
spec/                    # 保持原样
IMPLEMENTATION_REPORT.md
```

## 功能要求

### 1. 数据模型

实现不可变或严格校验的数据模型：

- `ChartInput`
- `RealityContext`
- `Evidence`
- `Judgement`
- `DecisionReport`
- `RuleCard`

可使用 `dataclasses` 或 `pydantic`，优先减少依赖。

### 2. Schema 校验

实现：

```bash
python -m mingli.cli validate-spec spec
```

要求：

- 递归解析所有 `.json` 和 `.jsonl`
- 使用 JSON Schema 校验 Schema 本身和数据文件
- 报告文件、行号、错误路径
- 任一错误返回非零退出码
- 不修改源文件

### 3. Rule Loader

实现：

- 读取 `spec/rules/**/*.jsonl`
- 检查唯一规则 ID
- 支持状态过滤：`draft`、`reviewed`、`verified`、`deprecated`
- 默认生产检索只允许 `reviewed` 和 `verified`
- 规则优先级高值优先
- Reality 规则优先于普通结构规则
- 不允许自动改变规则状态

CLI：

```bash
python -m mingli.cli validate-rules spec/rules
```

### 4. Evidence Fusion

实现纯确定性融合器：

- 支持 `support` 与 `contradict`
- 来源类型：`chart`、`timing`、`rule`、`case`、`reality`
- Reality 硬事实权重最高
- 输出支持分、反证分和冲突标志
- 不根据分数自动生成命理事实

### 5. Reality Override

至少实现并测试：

- 已婚 + 桃花：不得直接输出出轨
- 对方已婚 / 拉黑 / 长期失联：降低复联、复合和稳定
- 失业：事业主题不得写成升职
- 专业不符合：考公岗位不可行
- 低资本且无客户验证：创业只能低成本验证
- 持续胸痛：医疗评估优先
- 合约重仓：命理不得决定杠杆

### 6. Confidence Gate

实现高、中、低置信：

- 信息缺失、图片盘未确认或只有单一象意：低
- 有多项支持但存在反证：中
- 现实硬事实和多项证据一致：高
- 医疗、投资案例中的“高置信”必须明确针对现实处置，不是命理预测

### 7. Intent Router

读取 `spec/routing/intent_router.yaml`，支持：

- `full_bazi`
- `career_exam`
- `relationship_reunion`
- `startup`
- `wealth`
- `education`
- `migration`
- `fengshui`

返回所需字段、章节和代理能力，不执行真实代理调用。

### 8. Renderer

实现确定性中文渲染器：

- 短问题第一句直接给结论，不强制 `## 结论`
- 术语后附白话
- 默认最多三条建议
- 复合逻辑必须覆盖四层，但允许自然段合并
- 考公必须区分适配度与上岸
- 图片盘未确认时只输出确认请求和低置信限制
- 禁词扫描
- 免责声明仅在末行出现一次：
  `仅供文化研究与娱乐参考。`

### 9. ChartProvider 协议

定义协议或抽象接口。

默认实现必须明确返回：

- 未配置可靠排盘器
- 不可生成四柱或旺衰
- 不得使用硬编码示例盘冒充结果

### 10. 静态 Benchmark

实现：

```bash
python -m mingli.cli benchmark-static   spec/evaluation/golden_cases_v0.2.jsonl
```

以及针对实战盲测数据的结构检查。

首版 Benchmark 只做确定性策略校验：

- 必需章节是否存在
- 禁止结论是否被拦截
- Reality Override 是否触发
- 免责声明是否唯一
- 置信度是否满足目标级别

不得伪装成真实模型准确率。

## 测试要求

至少覆盖：

1. JSON / JSONL 解析错误
2. 重复规则 ID
3. 规则状态过滤
4. Reality 优先级
5. 支持与反证冲突
6. 图片盘未确认
7. 考公四部分
8. 复合四层
9. 医疗边界
10. 投资杠杆边界
11. 免责声明唯一
12. 禁词拦截
13. Router 所需字段
14. ChartProvider 显式拒绝
15. 40 个黄金案例静态校验

## 依赖

只加入当前实现确实需要的依赖。建议：

- `jsonschema`
- `PyYAML`
- `pytest` 仅作为开发依赖

不要加入数据库、Web 框架、向量库或 LLM SDK。

## 验证命令

必须实际执行：

```bash
python -m compileall src tests
python -m unittest discover -v
python -m pytest -q
python -m mingli.cli validate-spec spec
python -m mingli.cli validate-rules spec/rules
python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl
git diff --check
```

## 成功判断

- 所有命令退出码为 0
- 测试全部通过
- 不存在未处理 traceback
- CLI 对错误输入返回非零退出码与明确错误信息
- `spec/` 未被改写
- 工作树在提交后无已跟踪修改

## 停止条件

出现以下情况立即停止，不自行扩大范围：

- 目标仓库不明确
- 工作树存在用户未说明的修改
- 需要真实排盘算法或外部 API
- 需要读取 `.env`
- 规范文件自身存在冲突且无法无损解释
- 无法推送远端

## Git 交付

提交信息：

```text
feat: implement MingLi core runtime v0.1
```

推送当前分支，不合并默认分支，不创建 tag。

## 最终报告格式

```text
MINGLI_CORE_RUNTIME_V0_1_COMPLETE

repository:
branch:
commit:
pushed: yes/no

implemented:
- ...

changed_files:
- ...

validation:
- command: ...
  result: PASS/FAIL

known_limits:
- no deterministic bazi calculator
- no LLM runtime
- no OCR
- no production deployment

spec_modified: no
worktree_clean: yes/no
```
