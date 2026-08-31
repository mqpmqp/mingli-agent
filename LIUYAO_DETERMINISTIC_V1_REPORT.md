# LiuYao Deterministic Gate v1 Implementation Report

## Decision

本次实现完成六爻确定性结构层、输入冲突门禁和预测版本/结算治理，可以进入正式代码审查。

该结论只表示工程实现达到技术审查条件，不表示传统六爻的现实预测准确率已经得到验证。所有结果继续固定为 `prediction_validity=not_evaluated`；本 PR 不加入自动选用神、旺衰、合冲、应期或自然语言吉凶判断。

## Scope

新增：

- `src/mingli/liuyao/`
  - `tables`、`validation`、`models`、`chart`、`prediction`、`case_record`、`benchmark` 分层；
  - 六摇中文/数字输入归一化；
  - 本卦、变卦、动爻、64 卦、八宫、宫五行、世应；
  - 京房纳甲固定表、六亲；
  - 调用方显式提供日柱时的六神与旬空；
  - 输入、盘面、案例 canonical SHA-256 与确定性表 SHA-256；
  - 同案输入/合同冲突门禁；
  - 事件合同、预测版本、作废与结算状态机。
- `src/mingli/liuyao_cli.py`
  - `chart`、`register`、`add-version`、`activate`、`invalidate`、`settle`、`benchmark`。
- `tests/test_liuyao.py`
  - 已知本卦/变卦结构；
  - 64 卦、八宫、世应、纳甲外部冻结夹具差分；
  - 4096 种六爻动静组合；
  - 输入冲突、记录篡改、版本与结算状态机；
  - 确定性表摘要冻结。
- `tests/test_liuyao_temporal_integrity.py`
  - 跨时区截止日、截止日整日边界、成功事件发生时间与取证时间的完整性回归。
- `tests/fixtures/liuyao_structure_oracle_v1.json`
  - 固定外部 commit/blob 的次级结构差分夹具。
- `docs/liuyao/README.md`
  - 输入约定、CLI、事件合同、时区及明确能力边界。
- `pyproject.toml`
  - 新增 `mingli-liuyao` 命令入口。

未修改：

- `spec/`、`knowledge/`；
- 八字、紫微、奇门、梅花模块；
- HTTP/MCP 服务和 PWA 实现；
- 真实案例或个人信息；
- 候选规则 lifecycle/status。

## Engineering controls

1. `line_values` 必须恰好六项，顺序固定为初爻到上爻。
2. 当前只接受“字阴花阳”，其他约定 fail closed。
3. 同一 `case_id` 的六摇不一致返回 `INPUT_CONFLICT`；问题、事件合同或起卦元数据变化返回 `CONTRACT_CONFLICT`。
4. 载入案例时依据冻结输入重新排盘，并核对盘面和已有 canonical SHA-256，发现不一致即拒绝。
5. 修正版不得覆盖旧版；旧版必须保留为 `invalid` 并记录原因和时间。
6. `draft` 与正式发布的 `pending` 分离；只有带 `published_at` 的 pending 版本进入前瞻结算口径。
7. 预测创建和发布不得早于起卦完成时间，也不得晚于事件合同截止日。
8. 所有截止日判断统一换算到起卦完成时间 `completed_at` 的时区，不能通过更换 UTC 偏移绕过。
9. 事件合同 `deadline` 包含截止日整日；`miss`、`partial`、`indeterminate` 最早只能在起卦时区的下一当地日期登记。
10. `hit` 必须区分成功标准实际成立时间 `occurred_at` 与证据核验时间 `observed_at`；事件发生不得早于预测发布、晚于取证或超过合同截止日。
11. 只有 current `pending` 版本可结算；结算记录 append-only，结算后禁止保留开放版本或重开案例。
12. 日柱和月支不由本模块推算，避免引入未经独立验证的历法实现。
13. `static_table_sha256` 覆盖爻值语义、卦表、八宫世应、纳甲、五行生克、六神和旬空等全部确定性排盘表。

## Audit findings fixed

PR 审查期间发现并修复以下真实问题：

1. **跨时区截止日绕过**：原实现按各时间戳自身日历日期比较，极端 UTC 偏移可能提前登记负向结算。现统一换算到起卦时区再判断。
2. **截止日后事件误记为命中**：原结算只记录取证时间，无法证明目标事件在合同窗口内发生。现为 `hit` 增加 `occurred_at`，并验证其位于预测发布后、合同截止日前且不晚于 `observed_at`。
3. **迟到证据语义不清**：现允许截止日后取得证据，但只在证据明确证明事件于截止日前发生时登记为 `hit`。
4. **校验和边界表述过强**：文档明确 SHA-256 用于发现自洽性差异，不是数字签名；能修改全部内容并重算哈希的主体仍可生成另一份自洽记录。
5. **截止日当天提前判负**：原实现允许在截止日 `00:00` 后登记 `miss/partial/indeterminate`，实际事件窗口尚未结束。现截止日整日均保持 pending，最早于次日登记负向结果。
6. **静态摘要覆盖不完整**：原摘要未覆盖爻值语义、五行关系、六神和旬空等输出相关表。现统一纳入摘要，并补充表完整性启动校验。

以上问题均有专门回归测试或冻结摘要测试。

## Verification contract

最终验收必须绑定 PR 当前 head，不接受历史 head 的绿色结果替代。最低验证集合：

```text
python -m compileall -q src tests
python -m pytest -q -m "not benchmark and not real_case"
python -m pytest -q -m benchmark
python -m pytest -q -m real_case
python -m build
python -m mingli.liuyao_cli benchmark
```

仓库 GitHub Actions 还必须完成：

- `Core Runtime Verification / fast_tests`；
- `Core Runtime Verification / benchmark_tests`；
- `Core Runtime Verification / real_case_tests`；
- `Mobile Offline Bazi PWA / Verify offline mobile PWA`；
- spec、knowledge 保护范围检查；
- Python 构建与隔离 wheel 校验；
- 前端单测、浏览器 parity、移动端 E2E 和离线 PWA 回归。

本报告不硬编码易失效的 workflow run ID 或中间 head SHA。最终 head、run ID、测试计数和结论应记录在 PR 对话或合并收据中，避免文档提交再次触发 CI 后造成“报告引用旧运行”的循环。

外部结构夹具 SHA-256：

```text
2d53b63751f7aba92abba68f881ed69cde2957fbd6c4b15dca78ecbf751775f8
```

运行时确定性表 SHA-256：

```text
503d5339505e5ca77db270f5a046591980153c78970f54b756c2f8bb2d54709e
```

## Known limits

- 外部结构夹具来自冻结的第二实现，只用于交叉检查，不构成权威文献证明，也不证明预测有效。
- 当前只计算确定性结构，不判断吉凶，不自动选用神，不计算旺衰、合冲空破墓绝、伏神、反吟伏吟或应期。
- 月建与日辰由调用方提供；错误上下文仍会产生结构自洽但现实前提错误的结果。
- SHA-256 是一致性校验，不是抗篡改签名。
- 当前没有合格前瞻结算样本，不能计算或宣传准确率。
- 高风险健康、法律、投资等事项仍必须以现实证据和专业意见为先。

## Release boundary

本 PR 的目标状态是：

```text
TECHNICAL_REVIEW_READY
```

不是：

```text
PREDICTION_VALIDATED
PRODUCTION_COMMERCIAL_ALLOWED
PRODUCT_ACCURACY_CLAIM_ALLOWED
```

合并与任何产品发布授权必须独立决策，不能由测试通过自动推导。
