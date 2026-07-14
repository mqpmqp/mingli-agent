# Codex 统一交接：Phase 16—24

## 可直接执行

- 全仓 CI：`python -m pytest && python -m build`
- 隔离 wheel 后验：本地已完成 P19—P23；在完整环境补跑 P16—P18 与 P24，并核对源树/安装包输出哈希。
- 推送分支：`git push -u origin agent/phase16-domain-contracts-base-rules-v1`
- 创建 draft PR：范围 P16—P24，附 `PHASE_16*` 至 `PHASE_24*` 报告。

## 不得由自动执行伪造完成

- P19：RC2 核心包按设计不含称骨歌诀，保持 `verse_available=false`；未来 optional verse pack 独立评审，不构成 RC2 blocker。
- P22：通过获授权流程导入至少 30 个已同意、去标识、带来源与前事标签的真实案例；合成案例不得计数。
- 产品发布：只有云端 CI、隔离安装后验、内容来源和真实案例门禁均关闭后才能重新评估。
