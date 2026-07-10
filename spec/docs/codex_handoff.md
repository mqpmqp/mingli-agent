# Codex Handoff

## 目标

从本规范包实现 `mingli-agent` 最小可运行核心，不扩展紫微、奇门、风水和自动学习。

## 允许修改范围

- 新建仓库及标准 Python 包
- 实现 Schema 校验、规则加载、证据融合、现实校正、置信度与 Renderer
- 实现 CLI 与测试
- 使用外部排盘适配器接口；没有可靠依赖时使用明确的 stub，并禁止伪造真实盘面

## 强边界

- 不读取 `.env`
- 不打印密钥或环境变量
- 不接入支付
- 不做真实投资建议
- 不抓取私人数据
- 不自行实现未经验证的农历/节气算法并声称准确
- 不做无关重构

## 验证命令建议

```bash
python -m compileall src
python -m unittest discover -v
python -m pytest -q
python -m mingli.cli validate-spec ./schemas
python -m mingli.cli benchmark ./evaluation/golden_cases.jsonl
git diff --check
```

## 成功标准

- 所有 Schema 可加载
- 所有 JSONL 可解析
- Reality Override 优先级高于盘面规则
- 图片盘未确认时输出低置信
- 考公报告区分适配度与上岸
- 复合报告包含四层
- 所有输出包含免责声明
- 测试通过且无绝对化违规
