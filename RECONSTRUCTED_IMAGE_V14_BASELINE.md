# MingLi 图片确认链路 V14 重建基线

## 状态

本分支是显式的 `RECONSTRUCTED` 基线，不等同于已经丢失或未发布的
`1b93df7f1256d0701f299a882a17052ad37513d8`、`8680ad1...` 或
`8f6a2bcd5e89a8dd2eb75b09f3e82e525511a243`。

重建目的仅是为 Hermes/Telegram 图片命盘确认链路提供一个可读取、
可安装、可测试并可被 CI 固定的 MingLi Git 对象。

## 可验证归档与远端父节点

- 远端重建 commit 的父节点：
  `a5fde49f8d50d6332f94d5f5ce7f2bfff0b30907`
- 归档 Git 快照 HEAD：
  `49c51378ae4d9b20628d08203c8d7cf870a4c829`
- 归档 HEAD 主题：`feat: add confirmed image chart intake contract`
- 与远端 `main` 的 merge-base：
  `b03af9f1a7ee5199f64cdd627dd47f348c761d6e`
- 归档 ZIP SHA-256：
  `4c4248b9e2b02dbff4086278b777d872cce923fa07da80d29bb6ab3d6eaf3318`
- 归档 Git 对象连通性：通过；`git fsck --connectivity-only --no-reflogs`
  未报告缺失对象。

归档工作树在 `49c5137...` 上有两处未提交差异：

- `src/mingli/intake/image_chart.py`
- `tests/test_image_chart_intake.py`

这两处差异被作为重建输入保留，没有伪造为原历史提交。

远端分支以已经存在于 GitHub 的 `a5fde49...` 为父节点，并把
`a5fde49...` 到归档快照、归档工作树差异、V12 patch、生产加固 patch
以及本报告的合并结果写入一个新的重建 commit。这样不依赖未发布的
`49c5137...` 对象，也不改写任何现有分支。

## 叠加输入

### V12 部署包

- 文件：`MINGLI_IMAGE_RUNTIME_V12_DEPLOYMENT_BUNDLE.zip`
- ZIP SHA-256：
  `8ff44ddd77104740123b6b81334a3eab5e0b5bc81aa041fce638bb203e3cd2ad`
- MingLi patch SHA-256：
  `56d8b0c49a8081fa95862294e5f220568aec8a2d5ba31e8aa9bd6badcc1d73f6`

### 生产 E2E 包

- 文件：`MINGLI_IMAGE_CONFIRMATION_E2E_FINAL_20260725.zip`
- ZIP SHA-256：
  `6a618b6792f819241c864ffecdc693bc4ca53b106e0217fbefec7c5ec83025a3`
- 包内 `SHA256SUMS.txt`：全部通过。
- 原 patch 标识 `8f6a2bcd...` 只作为来源标签记录，不作为 Git 父节点或
  已存在提交声明。

## 最终生产模块

- `src/mingli/intake/image_chart.py`
  - SHA-256：
    `8dab8da0d61da48bafd56c639d6e095e2570e9e9fe9d789ca64921c22dfc6b81`
- `src/mingli/confirmed_pillar_runtime.py`
  - SHA-256：
    `0bc9e288fb44329f3955d04d8b07a4af68c3cd4971165e0b36f83c00a2b221ed`

两个最终模块均与生产 E2E 包内 payload 逐字节一致。

## 保护范围

本次不修改：

- `spec/`
- `knowledge/`
- 规则来源、Schema 来源和 provenance 资产
- PDF/古籍资产
- 锁文件、凭证、SQLite、服务定义和生产环境

## 验证

已实际完成：

- 两个图片确认模块的逐字节 payload 对比：通过。
- focused pytest：`30 passed`。
- compileall：通过。
- fast gate：`432 passed, 150 deselected, 16 subtests passed`。
- real-case gate：`112 passed, 470 deselected`。
- wheel 构建：通过。
  - wheel SHA-256：
    `02b60227b0f1a2a8da2767ebdbeb591c447be381011bbc7bd76f9836a2417555`
  - wheel 包含两个目标模块。
- 全新隔离环境安装、`pip check`、图片候选解析及 confirmed-pillar
  Runtime 冒烟：通过。
- `validate-spec`、`validate-rules`、严格 chart validation 和
  Phase 8 checkout provenance：通过。
- `git diff --check`：通过。
- `spec/`、`knowledge/` 和 `pyproject.toml` 差异门禁：通过，差异为 0。

未运行 benchmark gate。它与本次图片 intake/confirmed-pillar 变更无直接
执行路径，且既有完整 benchmark 运行成本约为 10 分钟；本次不据此声明
benchmark 新证据。
