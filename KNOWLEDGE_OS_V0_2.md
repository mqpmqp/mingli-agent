# Knowledge OS v0.2

本版本以文件系统和 JSON Schema 建立可审计知识仓库。对象依生命周期与领域存放；来源注册、批次清单、验证和回滚均为确定性 Python 实现，不引入数据库、向量库、Web 框架或 LLM SDK。

首个试点导入《周易与预测学》第一章的 30 个概念、14 条候选规则、8 条排除证据及 8 个草案基准。候选规则保持 `source_only`、`production_allowed=false`，不进入 verified 或生产加载。

常用命令：

```bash
python -m mingli.cli knowledge-validate knowledge
python -m mingli.cli knowledge-inventory knowledge
python -m mingli.cli knowledge-import spec/knowledge/pilots/zhouyi_yu_yucexue_ch01
python -m mingli.cli knowledge-rollback <batch_id> --dry-run
```
