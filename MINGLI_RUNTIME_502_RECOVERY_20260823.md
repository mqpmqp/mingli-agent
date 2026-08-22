# MingLi Runtime 502 恢复报告（2026-08-23）

## 结论

当前结论是 `BLOCKED_DEPLOYMENT_ACCESS`，不是“公网已恢复”。旧入口的根因是临时 tunnel 生命周期结束；仓库报告已经明确该入口依赖本地 Runtime 与 SSH session，而本次故障期间本机不存在对应 Runtime/tunnel 进程。纯函数、本地 HTTP/MCP、最终 Docker 镜像和 VPS 内 Caddy HTTPS 均通过，因此没有证据把统一 502 归因于命理算法。

稳定替代 Runtime 已部署到 VPS loopback，Caddy 也持有有效证书，但从独立 Windows 主机复测时公网 TCP 443 仍被 Lightsail 防火墙阻断。DNS 与 TCP 80 正常。实例角色此前检查被拒绝 `lightsail:GetInstances` 和 `ec2:DescribeSecurityGroups`，当前会话没有权限开放 443。

## 根因证据

- `MINGLI_RUNTIME_HTTP_MCP_V1_REPORT.md` 明确记录旧公网入口是临时 tunnel，生命周期依赖本地 Runtime 与 SSH session。
- 当前 ChatGPT 已加载的 `analyze_mingli`、`create_ziwei_chart`、`get_ziwei_rule_coverage` 均能看到 schema，但合成调用仍统一返回 `MCP -32603 Internal error`。
- Python 3.11 纯函数 analyze/chart/evaluate/coverage 全部通过。
- 本地真实 TCP 的六个 HTTP 路由、MCP `initialize`、`tools/list` 和四个 `tools/call` 全部通过。
- VPS 最终镜像与 Caddy loopback HTTPS 的同一完整链全部通过，排除了 Runtime 代码、镜像启动、Host/Origin allowlist 与 Caddy Streamable HTTP 转发故障。
- 外部复测解析到 `43.203.122.160`，TCP 80 可连接，TCP 443 不可连接；因此 TLS、公开 `/healthz` 与公开 `/mcp` 无法开始。

## 修复

- 新增 `deploy/Caddyfile`：Caddy 只反代 `127.0.0.1:8000`，保留公网 Host，并用 `flush_interval -1` 立即转发流式响应。
- 新增非冻结 `mingli.service_gateway`：只净化 `/mcp` JSON 错误正文和异常日志，保持 `isError=true`，不伪造成功、不吞掉错误事件。
- `mingli-service` 入口改为非冻结 gateway；冻结的 `service_app.py` 已恢复为与 `origin/main` 一致。
- 新增完整 MCP 四工具回归、异常隐私、持久代理和 Docker 部署合同测试。
- VPS 小规格实例实测发现 5 秒 Python healthcheck 会在应用实际返回 200 时产生假性 `unhealthy`；以 RED/GREEN 提交将镜像 healthcheck timeout 最小上调为 15 秒。
- 部署文档明确可信代理必须使用 Runtime 实际看到的来源 IP；本次 Docker bridge 使用 `172.17.0.1`，未使用 `*`。

## 保持不变的合同

- `prediction_validity=not_evaluated`
- `commercial_release_hold=ACTIVE`
- `rule_content_hold=ACTIVE`
- `readOnlyHint=true`
- `destructiveHint=false`
- `idempotentHint=true`
- `openWorldHint=false`
- `request_storage=none`
- `external_network_calls=false`
- `spec/` 未修改，78 项冻结合同全部通过。

## 验证结果

- 聚焦 Runtime/HTTP/deployment：22 passed。
- 聚焦 branch coverage：`service.py` 100%，`service_app.py` 91%，`service_gateway.py` 88%，合计 91%。
- `test-fast`：404 passed、1 skipped、150 deselected（182.41 秒）。
- 最终完整 pytest：554 passed、1 skipped（1031.44 秒）；两条既有 warning，无失败。
- Python 3.11 editable install、`pip check`、`compileall`、sdist/wheel build、`git diff --check` 全部通过。
- 最终镜像：`sha256:0589c352244a2f61280564076fdaa3ec7279b0459f79c97b7e226fb5e7816d3e`，来源提交 `000bb8d96ee307258b5ae98738dd1c112576ed3c`。
- 候选容器：health、六路 HTTP、完整 MCP 四工具、Host/Origin 正反向、Content-Length/chunked 上限全部通过；容器用户为 `mingli`。
- 正式容器：仅绑定 `127.0.0.1:8000`，`unless-stopped`，15 秒 healthcheck，状态 `healthy`。
- Caddy loopback：真实 CA/TLS、六路 HTTP、完整 MCP 四工具全部通过。
- 公网：DNS PASS、TCP 80 PASS、TCP 443 BLOCKED；公网 TLS/HTTP/MCP 未通过。
- ChatGPT：三个独立合成调用仍为 `MCP -32603`；无法生成 chart，因此 evaluator 未调用。

## 部署与回滚

- 部署源：VPS `/opt/mingli-runtime`，提交 `000bb8d96ee307258b5ae98738dd1c112576ed3c`。
- 正式容器：`mingli-runtime`。
- 旧中间容器保留为 exited 的 `mingli-runtime-rollback-1e67ac6-20260823`，旧镜像另有 `mingli-runtime-http-mcp:rollback-1e67ac6` 标签，自动重启已关闭。
- 未修改 `/root/mingli-agent` 的独立历史分支 checkout。

## 阻塞与下一步

1. 在 AWS Lightsail 控制台为该实例开放公网 TCP 443；不要开放 Runtime 的 8000 端口。
2. 从 VPS 外部重跑 TLS、`/healthz`、`initialize`、`tools/list` 和四工具链。
3. 公开验证通过后，把 ChatGPT Developer App MCP URL 更新为 `https://mingli.43-203-122-160.sslip.io/mcp` 并 Refresh。
4. 新会话用合成 golden prompt 重跑三项独立工具和 chart→evaluate 链。
5. 当前浏览器控制运行时缺少匹配版本的 `browser-service.mjs`，本会话无法只读查看或更新 Developer App；即使浏览器可用，也不应在公网 443 未通过前切换 URL。

长期仍应迁移到静态 IP 和自有域名；`sslip.io` 仅作为本次受控恢复入口。
