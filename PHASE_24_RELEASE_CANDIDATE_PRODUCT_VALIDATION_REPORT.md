# Phase 24：Release Candidate 与产品化验证

P24 已实现 P16—P23 聚合门禁、技术候选判定、产品发布判定、阻塞项和 Codex 交接合同。

当前预期结论为 `technical_rc_only_product_hold`：本地确定性基准全部通过时，可形成技术 RC；但产品仍不可发布，也不可宣称准确率。开放阻塞项为完整称骨歌诀来源未核验、合格真实案例未达到 30 个、完整依赖环境下的全仓 CI/构建/隔离安装后验尚未执行。

## 统一交给 Codex 执行

1. 在完整依赖环境运行 `python -m pytest && python -m build`。
2. 隔离安装 wheel，重跑 P16—P24 benchmark，并比对源树与安装包 canonical hash。
3. 推送 `agent/phase16-domain-contracts-base-rules-v1`。
4. 创建覆盖 P16—P24 的 draft PR，附阶段报告、测试结果和产品阻塞项。

内容审核与真实案例授权不属于自动 Codex 执行范围，必须由相应负责人补齐；在此之前 `prediction_validity=not_evaluated` 与产品 hold 不得解除。
