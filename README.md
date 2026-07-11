# MingLi Agent Core Runtime

MingLi Agent Core Runtime v0.1 是一个纯确定性的 Python 核心库。它把 `spec/` 中可验证的部分落成数据模型、规范校验、规则加载、证据融合、现实校正、置信度门禁、意图路由、中文渲染和静态策略检查。

本项目不是完整算命产品。Phase 5 只按公开约定计算四柱、历法转换、真太阳时校正以及大运顺逆和起运数值，不计算旺衰、大运序列、流年或事件预测，也不调用 LLM、OCR、数据库、Web 服务或外部排盘 API。调用方未选择确定性实现时，`UnavailableChartProvider` 仍会明确拒绝生成命盘，不会用示例盘冒充结果。

## 环境与安装

需要 Python 3.11 或更高版本。

```bash
python -m pip install -e ".[dev]"
```

运行时依赖仅有 `jsonschema`、其现代引用解析接口 `referencing` 与 `PyYAML`；Windows 额外安装 `tzdata`，为标准库 `zoneinfo` 提供 IANA 时区数据。`pytest` 是开发依赖。

## CLI

```bash
python -m mingli.cli validate-spec spec
python -m mingli.cli validate-rules spec/rules
python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl
python -m mingli.cli chart-validate --strict
python -m mingli.cli chart-benchmark --independent-only
python -m mingli.cli phase6 benchmark
```

- `validate-spec` 递归解析全部 JSON/JSONL，校验所有 JSON Schema 本身，并对同目录明确匹配的数据及规则数据执行 Schema 校验。错误包含文件、行号和 JSON 路径，任一错误返回非零状态。
- `validate-rules` 校验规则结构、状态和全局 ID 唯一性，不修改或升级规则状态。
- `benchmark-static` 检查 40 个黄金案例及 24 个实战盲测案例的确定性策略合同。结果不表示真实模型或命理预测准确率。

Phase 5 提供带版本标识的 `DeterministicBaziEngine`。每次成功结果都包含 `method_id`、完整约定与 `prediction_validity=not_evaluated`。详细口径见 `BAZI_CALCULATION_CONVENTIONS.md` 和 `BAZI_DETERMINISTIC_VERIFICATION_REPORT.md`；排盘成功不代表预测有效。

Phase 6 提供确定性静态派生结构映射层，只从 allowlisted Phase 5 结构化结果派生五项结构事实：地支藏干、可见天干十神、藏干十神、六十甲子纳音和旬空。它不计算大运/流年时间线、旺衰、格局、用神、喜忌、神煞、合冲刑害吉凶或事件预测；所有结果继续固定 `prediction_validity=not_evaluated`。

```bash
python -m mingli.cli phase6 map --input base_chart.json
python -m mingli.cli phase6 validate
python -m mingli.cli phase6 benchmark
python -m mingli.cli phase6 capabilities
python -m mingli.cli phase6 schemas
```

`phase6 map` 也可从 stdin 读取 JSON。stdout 只输出机器可读 JSON，错误写入 stderr；命令不读取网络、不调用外部模型、不修改输入文件。

Phase 7 在 Phase 5 和 Phase 6 之上构建确定性的八字事实图谱。它新增精确起运锚点、大运/流年时间线、显式年龄快照、十二长生结构事实、天干/地支结构关系以及 canonical graph SHA-256。它仍不计算旺衰、格局、用神、喜忌、吉凶、自然语言解读或事件预测。

```bash
python -m mingli.cli phase7 build --input base_chart.json
python -m mingli.cli phase7 timeline --input base_chart.json
python -m mingli.cli phase7 relations --input derived_chart.json
python -m mingli.cli phase7 validate
python -m mingli.cli phase7 benchmark
python -m mingli.cli phase7 profiles
python -m mingli.cli phase7 schemas
```

公共 API 位于 `mingli.phase7`：`build_bazi_fact_graph(...)`、`build_luck_timeline(...)`、`detect_structural_relations(...)`、`calculate_growth_stages(...)` 和 `benchmark_phase7(...)`。所有成功输出继续固定 `prediction_validity=not_evaluated`。

## 核心约束

- 生产规则检索默认只返回 `reviewed` 与 `verified`，现实规则始终先于普通结构规则，再按优先级降序排列。
- 现实硬事实在证据融合中权重最高；分数只作汇总，不会自动生成命理结论。
- 图片盘未确认时只请求确认并给出低置信限制说明。
- 考公输出分开处理体制适配、上岸、岗位与备考；复合输出分开处理缘分牵引、复联、复合与稳定。
- 医疗与投资场景优先现实专业处置；命理不能决定诊断、就医、杠杆或仓位。
- 固定免责声明只在答案末行出现一次，禁词在渲染完成前拦截。

## 测试

```bash
python -m compileall src tests
python -m unittest discover -v
python -m pytest -q
python -m mingli.cli validate-spec spec
python -m mingli.cli validate-rules spec/rules
python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl
python -m mingli.cli chart-validate --strict
python -m mingli.cli chart-benchmark --independent-only
python -m mingli.cli phase6 validate
python -m mingli.cli phase6 benchmark
python -m mingli.cli phase7 validate
python -m mingli.cli phase7 benchmark
git diff --check
```

`spec/` 是只读规范基线，开发和校验均不得改写其中的文件。
