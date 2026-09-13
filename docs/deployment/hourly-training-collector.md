# 小时训练自动采集器部署与接线

## 实际链路

`mingli-integrated-service` 在原有只读 Runtime/紫微工具之外增加三个受认证工具：

- `submit_hourly_training_report`：写入小时训练报告，自动去重并运行来源门和合同回归；
- `get_rule_promotion_status`：读取私有训练库、活动规则版本与 Phase 4.1 状态；
- `list_rule_review_queue`：列出需要人工决定的候选和精确门禁收据。

采集器只接受以下固定绑定：

| automation_id | domain |
|---|---|
| `bazi-dual-teacher-hourly-training` | `bazi` |
| `qimen-hourly-training` | `qimen` |
| `fengshui-hourly-training` | `fengshui` |

完整顺序为：小时任务调用写入工具 → 仓库外落盘 → 内容去重 → 来源状态检查 → 合同回归 → 人工批准 → 人工发布不可变版本 → Runtime 自动读取最新发布版本 → Phase 4.1 在预测冻结前绑定 `rule_set_version`。采集回执固定包含 `auto_approved=false` 和 `auto_published=false`；采集器绝不自动批准、发布或解除 `commercial_release_hold=ACTIVE`。

## OAuth 2.1 配置

公开或 ChatGPT 连接必须使用支持 OAuth 2.1/OIDC、授权码 + PKCE 和 MCP 资源参数的既有身份提供商。服务只充当资源服务器，不自行签发令牌。配置：

```text
MINGLI_OAUTH_ISSUER=https://YOUR_TENANT/
MINGLI_OAUTH_JWKS_URL=https://YOUR_TENANT/.well-known/jwks.json
MINGLI_OAUTH_RESOURCE_URL=https://YOUR_MINGLI_HOST
```

访问令牌的 `aud` 必须等于 `MINGLI_OAUTH_RESOURCE_URL`，`iss` 必须等于 `MINGLI_OAUTH_ISSUER`，且至少包含：

- Runtime 调用：`runtime:read`
- 写入小时报告：`runtime:read training:write`
- 查看训练状态/人工队列：`runtime:read training:read`

服务使用 JWKS 校验 RS256/ES256 签名，同时验证 `iss`、`aud`、`exp`、`iat`、`sub` 和 scope。ChatGPT 会从 `/.well-known/oauth-protected-resource` 发现身份提供商；插件连接后完成一次用户登录授权。`MINGLI_TRAINING_COLLECTOR_TOKEN` 仅供本地 HTTP/MCP Inspector 测试，ChatGPT 不支持把自定义 API Key 作为替代认证。

## 容器启动

训练库必须持久挂载在 Git 仓库之外，并与 Runtime release store 使用同一个目录：

```bash
docker build -f Dockerfile.integrated -t mingli-integrated:local .
docker run --rm -p 8000:8000 \
  -v mingli-training:/var/lib/mingli \
  -e MINGLI_ALLOWED_HOSTS=mingli.example.com \
  -e MINGLI_ALLOWED_ORIGINS=https://chatgpt.com \
  -e MINGLI_OAUTH_ISSUER=https://YOUR_TENANT/ \
  -e MINGLI_OAUTH_JWKS_URL=https://YOUR_TENANT/.well-known/jwks.json \
  -e MINGLI_OAUTH_RESOURCE_URL=https://mingli.example.com \
  mingli-integrated:local
```

省略 `MINGLI_RULE_RELEASE_STORE` 时，集成服务自动从 `MINGLI_TRAINING_STORE` 加载最新发布版本。设置 `MINGLI_RULE_RELEASE_VERSION` 会固定指定版本，适合回滚或对照试验，但不会自动跟随新发布。

systemd 模板位于 `deploy/systemd/mingli-integrated-service.service.example`。必须单进程运行；服务内写锁负责三个小时任务的并发合并。不要用多 worker 共享同一 JSON store。

## 来源登记与人工来源审查

PDF 不写入训练库，服务只保存元数据和内容 SHA-256。先把授权使用的来源放到 VPS 的受控目录，再逐个登记：

```bash
mingli training source-register \
  --file /srv/mingli-sources/source.pdf \
  --input source-metadata.json \
  --store /var/lib/mingli/training \
  --repository-root /opt/mingli-agent --json
```

登记状态固定为 `pending_human_review`。人工核对文件身份、页码和候选作用域后，再运行 `source-review`。上传的 16 份资料已通过字节级 SHA-256 复核；这只确认文件身份，不等于人工审查完成，也不证明其中传统主张有效。

## ChatGPT 与三个小时任务接线

部署后在 ChatGPT 插件设置中刷新 `MingLi Agent Runtime`，工具列表必须出现 `submit_hourly_training_report`。先用合成报告验证收到 `status=accepted`，再给三个现有任务追加同一条执行要求：

```text
生成 HOURLY_TRAINING_REPORT_JSON 后，必须调用 MingLi Agent Runtime 的
submit_hourly_training_report，参数 report 必须是该 JSON 对象本身。
只有工具返回 status=accepted 才能标记 COLLECTOR_WRITE=OK；调用失败时标记
COLLECTOR_WRITE=FAILED 并保留原 JSON，禁止声称已接入规则库、Runtime 或 Phase 4.1。
不得调用或模拟人工批准与规则发布。
```

任务更新后，分别运行一次八字、奇门、风水合成冒烟。随后通过 `get_rule_promotion_status` 核对 `hourly_reports` 增量，通过 `list_rule_review_queue` 核对三个 automation/domain 绑定及门禁状态。没有这两项证据，不得宣布自动链接完成。

## 人工批准、发布和 Runtime/Phase 4.1

查看人工队列：

```bash
mingli training rules-review-queue \
  --store /var/lib/mingli/training \
  --repository-root /opt/mingli-agent --json
```

只有 `source_status=passed` 且 `regression_status=passed` 的当前 candidate hash 才能写入 `candidate-decide`。人工批准不等于发布；发布仍须显式运行：

```bash
mingli training candidate-decide --input approval.json \
  --store /var/lib/mingli/training --repository-root /opt/mingli-agent --json
mingli training rules-publish --input release.json \
  --store /var/lib/mingli/training --repository-root /opt/mingli-agent --json
```

未固定版本的集成 Runtime 会在下一次请求加载最新发布 manifest。Phase 4.1 预测在冻结前调用 `RuleAwareRuntime.bind_phase4_1_prediction`，也可执行 `mingli-rule-runtime phase4-1-bind-prediction --input prediction.json ...`；若请求中已有不同版本，系统返回 `PHASE4_1_RULE_VERSION_CONFLICT`，禁止把案例事后移动到新规则组。

## 数据边界和恢复

- 直接身份信息在落盘前由隐私扫描拒绝；小时任务只允许去标识化报告。
- 训练库保存报告、候选、门禁、批准和发布收据，不保存 HTTP 请求体日志。
- 训练库属于受控、仓库外、持久卷；备份和恢复必须保持整个目录的一致快照。
- V1 不提供远程删除或批准工具，避免自动任务或提示注入破坏审计链。发现误收敏感信息时立即停服务，隔离整个 store 快照，由管理员离线定位依赖记录并执行删除；删除后重新跑完整性和回归。
- 本服务仅限开发与真人试点，不是商业生产发布；Phase 4.1 仍以 10 个前瞻真人案例为目标，当前准确率不能由工程测试推导。

## Phase 4.1 真人案例写入

真人案例和小时训练规则使用同一个 `MINGLI_TRAINING_STORE`。客户端必须在生成正式预测前依次调用：

1. `submit_phase4_1_candidate_intake`
2. `screen_phase4_1_candidate`
3. 生成预测并调用 `freeze_phase4_1_prediction`
4. 收到现实反馈后调用 `submit_phase4_1_feedback`

MCP 与对应 `/v1/training/phase4-1/*` HTTP 路由均要求 `training:write`，状态读取要求 `training:read`。服务仅落盘不可逆 candidate/person/prediction 标识、claim/evidence 代码和 manifest hash，不接受姓名、电话、邮箱、身份证或详细地址。

如果在候选登记时预测或反馈已经存在，必须将 `prior_stage` 设为实际阶段。系统写入 `intake_sequence_violation=true`，允许再用 `submit_phase4_1_retrospective_audit` 保存去标识的验证证据，但不允许 screen、freeze、分配 slot 或计入准确率。`get_phase4_1_status` 会分别报告 `observed_real_cases` 和 `registered_real_cases`，防止事后挑选命中案例。
