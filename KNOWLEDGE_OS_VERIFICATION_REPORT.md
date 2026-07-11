# Knowledge OS v0.2 验证报告

执行环境：Python 3.12（项目要求 Python >= 3.11）。提交前实际结果：

| 命令 | 结果 |
|---|---|
| `python -m compileall src tests` | 通过 |
| `python -m unittest discover -v` | 28 tests，OK |
| `python -m pytest -q` | 28 passed |
| `python -m mingli.cli validate-spec spec` | 通过 |
| `python -m mingli.cli validate-rules spec/rules` | 36 条规则通过 |
| `python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl` | 黄金案例 40/40、实战结构 24/24 |
| `python -m mingli.cli knowledge-validate knowledge` | 通过 |
| `python -m mingli.cli knowledge-inventory knowledge` | 30 concepts、14 rules、8 evidence、8 benchmarks、1 source、1 batch |
| `git diff --check` | 通过 |

临时 checkout 中已执行：回滚已提交试点至空库存、重新导入、核对 30/14/8/8、dry-run、真实回滚、再次校验。最终库存回到 0/0/0/0，回滚成功。另经文件扫描确认 `spec/` 无修改、无 PDF/EPUB/MOBI 提交、知识与 manifest 无本机绝对路径。

覆盖范围包括 schema、稳定来源 ID、相对路径、重复哈希、symlink、统一资产策略、生命周期门禁、生产规则过滤、批次完整性、可复现导入、哈希保护回滚，以及 30/14/8 试点计数与逐对象页码追踪。

已知边界：首版仅支持仓库内受控试点的 JSONL 确定性导入；不做 OCR、全文复制、自动知识升级或预测有效性认证。
