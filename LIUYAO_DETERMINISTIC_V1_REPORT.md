# LiuYao Deterministic Gate v1 Implementation Report

## Decision

本次实现完成六爻的确定性基础层与案例版本门禁，可以进入代码审查；不能据此宣称已具备稳定断卦准确率。实现结果固定为 `prediction_validity=not_evaluated`，未加入用神、旺衰、合冲或应期解释规则。

## Scope

新增：

- `src/mingli/liuyao/`
  - 按 `tables`、`validation`、`models`、`chart`、`prediction`、`case_record`、`benchmark` 分层；
  - 六摇中文/数字输入归一化；
  - 本卦、变卦及动爻；
  - 64 卦、八宫、宫五行、世应；
  - 京房纳甲固定表、六亲；
  - 调用方显式提供日柱时的六神与旬空；
  - 输入、盘面、案例 canonical SHA-256 与独立静态表 SHA-256；
  - 同 case 输入冲突门禁；
  - 事件合同、预测版本、作废与结算状态机。
- `src/mingli/liuyao_cli.py`
  - `chart`、`register`、`add-version`、`activate`、`invalidate`、`settle`、`benchmark`。
- `tests/test_liuyao.py`
  - 两组已知本卦/变卦结构测试；
  - 冻结外部结构夹具，对 64 卦、八宫、世应和纳甲逐项差分；
  - 4096 种六爻动静组合的本卦、变卦和动爻覆盖；
  - 纳甲、世应、六神、旬空；
  - 输入冲突、合同冲突、记录篡改；
  - 版本作废、截止日前禁止负向结算、结算后不可重开；
  - CLI 退出码。
- `tests/fixtures/liuyao_structure_oracle_v1.json`
  - 固定外部 commit/blob 的 64 卦、八宫、世应和纳甲次级差分夹具。
- `docs/liuyao/README.md`
  - 固定约定、输入格式、命令与明确边界。
- `pyproject.toml`
  - 新增 `mingli-liuyao` 命令入口。

未修改：

- `spec/`、`knowledge/`；
- 八字、紫微、奇门、梅花模块；
- HTTP/MCP 服务和 PWA；
- 任何真实案例或个人信息；
- 任何候选规则的 lifecycle/status。

## Engineering controls

1. `line_values` 必须恰好六项，顺序固定为初爻到上爻。
2. 当前只接受“字阴花阳”，其他约定 fail closed。
3. 同 `case_id` 的六摇不一致时返回 `INPUT_CONFLICT`；其他材料差异返回 `CONTRACT_CONFLICT`。
4. 命盘从冻结输入重算，载入时校验盘面与 canonical SHA-256，避免手工改盘。
5. 修正版不能覆盖旧版；旧版必须保留为 `invalid` 并记录原因和时间。
6. `draft` 与已发布的 `pending` 明确分离；只有带 `published_at` 的 pending 才计入前瞻结算。
7. 预测版本只能在起卦完成后创建、截止日当天或之前发布；作废不得早于发布时间，发布与结算时间倒置均 fail closed。
8. 只有 current `pending` 版本可结算；结算时间必须带时区，负向或不确定结果在截止日前不能登记。
9. 结算记录 append-only；结算后禁止保留开放版本或重开案例。
10. 日柱和月支不由本模块推算，防止引入未经独立验证的历法实现。

## Local verification

在隔离的本地重建目录执行：

```text
PYTHONPATH=src python -m compileall -q src tests
PYTHONPATH=src python -m pytest -q tests/test_liuyao.py
PYTHONPATH=src python -m mingli.liuyao_cli benchmark
PYTHONPATH=src python -m mingli.liuyao_cli chart --input cast.json
# register -> draft -> activate -> invalidate -> replacement pending -> settle
PYTHONPATH=src python -c 'from mingli.test_gates import run_gate; ...'  # isolated gate compatibility
python -m pip wheel . --no-deps --no-build-isolation -w dist
# install wheel into an isolated venv, then run benchmark and chart smoke
```

结果：

| Command | Exit | Result |
| --- | ---: | --- |
| `compileall` | 0 | PASS |
| targeted pytest | 0 | 29 passed |
| CLI benchmark | 0 | PASS，8/8 内置检查通过 |
| CLI chart smoke | 0 | `巽为风 → 风天小畜`，初爻动，初爻 `辛丑 → 甲子` |
| CLI lifecycle smoke | 0 | `draft → pending → invalid`，修正版 `pending → settled`；旧版未被覆盖 |
| isolated fast-gate compatibility | 0 | 28 passed，1 benchmark test deselected |
| isolated benchmark-gate compatibility | 0 | 1 passed，28 tests deselected |
| PEP 517 wheel via `pip wheel` | 0 | PASS；wheel 内容检查、隔离安装、入口命令与排盘 smoke 均通过 |

外部结构夹具 SHA-256：`2d53b63751f7aba92abba68f881ed69cde2957fbd6c4b15dca78ecbf751775f8`。运行时静态表 SHA-256：`f9375a79912a033cc149f65df9acefab465df1748ff6435e6540b6af2cc11b3b`。
本次最小集成构建 wheel SHA-256：`426bcee11277cdd72e0e05e739260669fd09b502b738bbe66ae2b2265e2caf0c`；该值是本次环境收据，不作为跨环境固定常量。

## Verification limits

当前执行环境无法通过网络克隆完整仓库，因此尚未在完整目标工作树运行：

- 全仓 `test-fast`；
- 全仓 `test-benchmark`；
- `test-real-case`；
- CI 中的 `python -m build`；
- 基于完整 `origin/main...HEAD` 的 `git diff --check`。

已在重建的最小集成工作树完成定向测试、门禁分类兼容、PEP 517 wheel 构建、隔离安装和 CLI smoke，但这些不能替代全仓回归。目标分支的普通 push 不在现有 `test.yml` 的分支触发白名单中；在未获创建 PR 授权前，不通过 PR 触发全量 CI。上述全仓项目必须在最终合并前补齐。

## Known limits

- 固定表已与 `yaomancy/liuyao-engine` 冻结 commit/blob 生成的结构夹具做差分；该外部项目自身仍不是权威证明，因此本项目继续把它定位为次级交叉检查。
- 当前只计算结构，不判断吉凶，不自动选用神，不给应期。
- 月建与日辰由调用方提供；输入错误仍会得到结构一致但现实上下文错误的结果。
- 真实案例仍为 0 个合格前瞻结算样本，不能计算准确率。
- 高风险问题仍必须以现实检查和专业意见为先。
