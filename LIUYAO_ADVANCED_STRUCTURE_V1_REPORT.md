# 六爻高级结构层 v1 实现报告

## 结论

本候选完成第三阶段中可以立即进入的能力：自动月建、日辰和旬空；伏神飞神；月破、日冲、六合六冲；五行十二长生、墓绝；进退神；反吟伏吟；多动爻关系图；原神、忌神、仇神条件标记；用神候选排序；规则冲突矩阵。

本层固定为：

```text
method_id=liuyao-advanced-structure@0.2.0
interpretation_status=review_only
production_allowed=false
prediction_validity=not_evaluated
```

这表示工程结构可以复算和审查，不代表现实预测准确率得到验证，也不允许直接生成应期、成功概率或自动付费断语。

## Scope

新增：

- `src/mingli/liuyao/advanced.py`
- `src/mingli/liuyao/advanced_benchmark.py`
- `tests/test_liuyao_advanced.py`
- `docs/liuyao/ADVANCED_STRUCTURE_V1.md`
- `LIUYAO_ADVANCED_STRUCTURE_V1_REPORT.md`

修改：

- `src/mingli/liuyao/__init__.py`
- `src/mingli/liuyao_cli.py`
- `src/mingli/liuyao/interpretation.py`：统一“单次六爻”边界措辞；
- `docs/liuyao/README.md`：补充第三阶段入口和能力边界。

未修改：

- `spec/`、`knowledge/`；
- 八字历法算法本身；
- 紫微、奇门、梅花模块；
- HTTP/MCP 服务与 PWA；
- 真实案例和用户资料；
- 生产规则状态。

## 关键实现决定

1. 自动历法复用现有 `DeterministicBaziEngine`，不另写节气和干支日算法。
2. 手工月建或日柱与重算不一致时返回 `CALENDAR_CONTEXT_CONFLICT`。
3. 自动月日先写入临时有效命盘，再调用第二阶段解释层；原命盘与有效命盘哈希同时留存。
4. 十二长生采用六爻卦象的五行顺行口径：木亥、火寅、金巳、水土申起长生。
5. 伏神从本卦所属八宫的本宫纯卦同位补入，只补当前盘缺失六亲。
6. 合冲、墓绝、进退、反伏吟先作为结构事实；不能单独推出成败。
7. 回头生克在变爻空破时保持条件性；进退神在原爻空破时保持条件性。
8. 用神排序保留全部因素，分数只用于复核顺序，不是吉凶分或成功概率。
9. 现实阻断优先级最高；结构支持不得覆盖资格、医学、法律或关系现状。
10. 高级结构表和排序权重纳入独立 SHA-256。

## 来源口径

- 《周易预测宝典》第 75 页：五行十二长生起点；
- 第 164 页：原神、忌神、仇神定义；
- 第 168–169 页：进神退神、飞神伏神；
- 第 204、207 页：反吟伏吟；
- 《周易与预测学》目录：纳甲、动变、四时旺衰、反伏吟、应期按不同层次组织。

这些资料只用于冻结传统算法口径，不用于证明现实预测有效性。

## 本地验证合同

在由当前 PR Python wheel 重建的完整 package 快照上执行：

```text
PYTHONPATH=src python -m compileall -q src tests
PYTHONPATH=src python -m pytest -q tests/test_liuyao_advanced.py
PYTHONPATH=src python -m mingli.liuyao_cli benchmark
PYTHONPATH=src python -m mingli.liuyao_cli interpret-benchmark
PYTHONPATH=src python -m mingli.liuyao_cli advanced-benchmark
python -m build
隔离虚拟环境安装 wheel 后重跑三组 benchmark
```

最终本地计数、wheel 哈希和 PR 最新 Head 的 CI 收据应在验证完成后记录到 PR 对话或外部收据中，不在本报告中硬编码易失效的中间 Head。

高级结构静态表 SHA-256：

```text
14c2792232fb3a8d06d29e85a566b7aba477ba368edc266acf8e9044d8e001ee
```

## 合并门禁

合并必须绑定 PR 最新 Head，并同时满足：

- `Core Runtime Verification` 全部 job 成功；
- `Mobile Offline Bazi PWA` 成功；
- fast、benchmark、real_case 三个互斥门成功；
- Python 构建及隔离 wheel 安装成功；
- `git diff --check` 成功；
- `spec/`、`knowledge/` 无变更；
- 无 `CHANGES_REQUESTED` 或未解决的阻塞 review thread。

## 剩余边界

仍未实现：合化、三合局、暗动终局、完整旺衰裁决、多动爻终局归并、伏神出伏应期、事件应期、概率校准和自动付费断语。真实前瞻已结算案例仍不足以声明预测有效性。
