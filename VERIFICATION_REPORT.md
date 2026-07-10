# MingLi Core Runtime v0.1 Final Verification

## 范围

本轮仅关闭代码审查发现，不新增业务功能：

- 所有 `*.schema.json` 的顶层必须是 JSON object。
- 已核验且方向一致的 Reality Evidence 作为 hard override，覆盖普通盘面、规则、时机和案例证据。
- 增加已婚与桃花、失业与升职、胸痛与五行、杠杆投资与偏财的合同测试。
- 增加 GitHub Actions 验收流程。
- `spec/` 保持不变。

未实现排盘算法，未接入 LLM。

## 变更文件

- `src/mingli/schema_loader.py`
- `src/mingli/evidence.py`
- `tests/test_runtime.py`
- `.github/workflows/test.yml`
- `VERIFICATION_REPORT.md`

## 验证

GitHub Actions 将在本分支 push 和 PR 上执行：

- `python -m compileall src tests`
- `python -m unittest discover -v`
- `python -m pytest -q`
- `python -m mingli.cli validate-spec spec`
- `python -m mingli.cli validate-rules spec/rules`
- `python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl`
- `git diff --check`
- `git diff --exit-code origin/main...HEAD -- spec`

当前状态：等待 GitHub Actions 首次执行。本报告只会在取得真实 CI 结果后标记 PASS。

## 保持边界

- no deterministic bazi calculator
- no LLM runtime
- no OCR
- no database or production deployment
- spec modified: no
