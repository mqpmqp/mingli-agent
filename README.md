# MingLi Agent Core Runtime

MingLi Agent Core Runtime v0.1 是一个纯确定性的 Python 核心库。它把 `spec/` 中可验证的部分落成数据模型、规范校验、规则加载、证据融合、现实校正、置信度门禁、意图路由、中文渲染和静态策略检查。

本项目不是完整算命产品，不计算真实四柱、旺衰、大运或流年，也不调用 LLM、OCR、数据库、Web 服务或外部排盘 API。未配置经过验证的 `ChartProvider` 时，运行时会明确拒绝生成命盘，不会用示例盘冒充结果。

## 环境与安装

需要 Python 3.11 或更高版本。

```bash
python -m pip install -e ".[dev]"
```

运行时依赖仅有 `jsonschema`、其现代引用解析接口 `referencing` 与 `PyYAML`；`pytest` 是开发依赖。

## CLI

```bash
python -m mingli.cli validate-spec spec
python -m mingli.cli validate-rules spec/rules
python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl
```

- `validate-spec` 递归解析全部 JSON/JSONL，校验所有 JSON Schema 本身，并对同目录明确匹配的数据及规则数据执行 Schema 校验。错误包含文件、行号和 JSON 路径，任一错误返回非零状态。
- `validate-rules` 校验规则结构、状态和全局 ID 唯一性，不修改或升级规则状态。
- `benchmark-static` 检查 40 个黄金案例及 24 个实战盲测案例的确定性策略合同。结果不表示真实模型或命理预测准确率。

## 核心约束

- 生产规则检索默认只返回 `reviewed` 与 `verified`，现实规则始终先于普通结构规则，再按优先级降序排列。
- 现实硬事实在证据融合中权重最高；分数只作汇总，不会自动生成命理结论。
- 图片盘未确认时只请求确认并给出低置信限制说明。
- 考公输出分开处理体制适配、上岸、岗位与备考；复合输出分开处理缘分牵引、复联、复合与稳定。
- 医疗与投资场景优先现实专业处置；命理不能决定诊断、就医、杠杆或仓位。
- 固定免责声明只在答案末行出现一次，禁词在渲染完成前拦截。

## 资料仓库

`knowledge/` 保存经过整理、可检索的 Markdown 或结构化知识；`references/` 保存 PDF、扫描件、图片、课程档案和案例等原始来源。原始来源不得直接混入规则目录，未经复核的 PDF/OCR 转换结果不得当作规则真值。

先对完整原始资料目录生成只读清单：

```powershell
python scripts/inventory_knowledge_assets.py `
  "D:\待整理资料目录" `
  --json-output reports/knowledge_inventory.json `
  --markdown-output reports/knowledge_inventory.md
```

再生成不执行迁移的导入计划：

```powershell
python scripts/plan_knowledge_import.py `
  reports/knowledge_inventory.json `
  --json-output reports/knowledge_import_plan.json `
  --markdown-output reports/knowledge_import_plan.md
```

原始资料总量小于 500 MiB 时采用单仓库并放入 `references/`；达到或超过 500 MiB 时，原始二进制资料建议进入独立的 `mqpmqp/mingli-knowledge`。本次没有提供外部原始资料路径，因此没有生成真实 inventory，也尚未作最终分仓决定。完整策略见 [`docs/knowledge_repository_strategy.md`](docs/knowledge_repository_strategy.md)。

仓库已为 PDF、常见扫描图、图片和压缩档案配置 Git LFS。提交这些二进制文件前必须安装 Git LFS 并运行：

```bash
git lfs install
```

## 测试

```bash
python -m compileall src tests scripts
python -m unittest discover -v
python -m pytest -q
python -m mingli.cli validate-spec spec
python -m mingli.cli validate-rules spec/rules
python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl
git diff --check
```

`spec/` 是只读规范基线，开发和校验均不得改写其中的文件。
