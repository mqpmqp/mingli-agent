# MingLi Core Runtime v0.1 实现报告

## 结果

已实现 `CODEX_TASK.md` 要求的最小确定性 Python 运行时，并保持 `spec/` 原样。实现不包含真实排盘、LLM、OCR、数据库、Web UI 或生产部署。

## 实现范围

- `models.py`：不可变且严格校验的 `ChartInput`、`RealityContext`、`Evidence`、`Judgement`、`DecisionReport`、`RuleCard`，以及决策选项模型。
- `schema_loader.py`：递归 UTF-8 JSON/JSONL 解析、JSON Schema 自校验、明确匹配的数据校验、文件/行号/JSON 路径错误报告。
- `rule_loader.py`：规则结构与 ID 唯一性校验、状态过滤、现实规则优先及优先级排序；状态只读。
- `evidence.py`：支持与反证分开计分、冲突标记、现实硬事实最高来源权重。
- `reality.py`：婚姻桃花、复联边界、失业、专业限制、低成本创业验证、急症就医及杠杆风控校正。
- `confidence.py`：高、中、低置信门禁；医疗和投资的高置信仅指现实处置。
- `router.py`：读取既有 YAML，返回八类意图的必需字段、章节与能力名称，不执行代理调用。
- `renderer.py`：结论优先、术语白话、最多三条建议、考公与复合专项结构、图片盘限制、禁词和唯一末行免责声明。
- `chart_provider.py`：`ChartProvider` 协议及默认显式拒绝实现，不生成或伪造命盘。
- `benchmark.py`：40 个黄金案例与 24 个实战案例的结构、禁用结论、现实校正、免责声明、章节及目标置信标签静态检查。
- `cli.py`：三条任务 CLI；错误输入返回非零状态和可读错误，不泄露 traceback。

## 设计边界

Schema 自动匹配只采用同目录的 `<name>.schema.json` / 单数文件名，以及任务明确指定的规则 schema。不会把远处同名 schema 猜测性套用到没有声明关系的数据上。

静态 benchmark 只证明策略合同和数据结构可被确定性检查，不证明预测能力或经验准确率。`ChartProvider` 必须由未来经过验证的实现显式注入。

## 测试覆盖

自动化测试覆盖 JSON/JSONL 错误定位、Schema 数据错误、模型不可变性、重复规则 ID、状态过滤、现实优先级、证据冲突、图片盘、考公四部分、复合四层、医疗与投资边界、免责声明、禁词、路由字段、排盘拒绝，以及 40+24 个静态案例。

最终验收命令及结果记录在提交前的执行报告中；所有命令必须实际退出为 0 才可提交。
