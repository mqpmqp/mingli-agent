# MingLi Runtime HTTP/MCP v1 实现报告

## Outcome

MingLi Agent Runtime 已实现为可运行的 `tool-only` ChatGPT 应用：同一 Python 进程暴露普通 JSON HTTP API 和 `/mcp` Streamable HTTP MCP，无 widget。服务已通过本地、临时公网 HTTPS 与 ChatGPT Developer Mode 端到端验证。

## Public surface

HTTP：

- `GET /healthz`
- `GET /v1/capabilities`
- `POST /v1/mingli/analyze`
- `POST /v1/ziwei/chart`
- `POST /v1/ziwei/rules/evaluate`
- `GET /v1/ziwei/coverage`

MCP：

- `analyze_mingli`
- `create_ziwei_chart`
- `evaluate_ziwei_chart`
- `get_ziwei_rule_coverage`

所有工具均标注 `readOnlyHint=true`、`destructiveHint=false`、`idempotentHint=true`、`openWorldHint=false`。服务不保存请求、不调用外部服务，并保留 `prediction_validity`、Release Hold 和规则内容 Hold。

## Architecture and hardening

- `mingli.service`：纯 Runtime adapter，不依赖 Web/MCP transport。
- `mingli.service_app`：FastMCP + Starlette 组合入口，提供 app factory 以隔离测试生命周期。
- 请求体上限 1 MB，同时覆盖 Content-Length 与 chunked body。
- 精确 Host/Origin allowlist 支持 `MINGLI_ALLOWED_HOSTS`、`MINGLI_ALLOWED_ORIGINS`。
- 代理信任由 `MINGLI_FORWARDED_ALLOW_IPS` 限定。
- 每个响应带 no-store、安全 headers 与 request id。
- telemetry 只记录 method/path/status/duration/request id，不记录请求体。
- Docker 合同仅复制 package runtime，以非 root 用户运行并检查 `/healthz`。

## ChatGPT integration result

- Developer Mode 已启用。
- 开发应用 `MingLi Agent Runtime` 创建并连接成功。
- ChatGPT 成功读取 4 个工具与输入 schema。
- Golden prompt 实际调用 `get_ziwei_rule_coverage`，返回：
  - `release_gate: REVIEW_REQUIRED`
  - `evaluated_rules: 184`
  - `prediction_validity: not_evaluated`
- ChatGPT 输出同时明确“这不是预测准确率”。

## Official references

- https://developers.openai.com/apps-sdk/build/mcp-server/
- https://developers.openai.com/apps-sdk/quickstart/
- https://developers.openai.com/apps-sdk/plan/tools/
- https://developers.openai.com/apps-sdk/reference/
- https://developers.openai.com/apps-sdk/deploy/
- https://developers.openai.com/apps-sdk/deploy/testing/
- https://developers.openai.com/apps-sdk/deploy/connect-chatgpt/
- https://developers.openai.com/apps-sdk/build/auth/
- https://github.com/modelcontextprotocol/python-sdk/tree/v1.x

## Validation summary

| Gate | Result |
|---|---|
| Focused coverage | 18 passed；88% |
| Full pytest | 381 passed，1 skipped，31 subtests |
| Fast | 285 passed，1 skipped，16 subtests |
| Benchmark | 38 passed，15 subtests |
| Real-case | 58 passed |
| Ruff / scoped Pyright | PASS / 0 errors |
| compileall | PASS |
| wheel + sdist + wheel smoke | PASS |
| pip-audit | No known vulnerabilities found |
| Local + public MCP protocol smoke | PASS |
| ChatGPT Developer Mode golden prompt | PASS |

详细命令、RED/GREEN commits 与已知边界见 `docs/testing/runtime-http-mcp-v1.tdd.md`；部署步骤见 `docs/deployment/runtime-http-mcp.md`。

## Remaining boundaries

- 当前公网入口是临时 tunnel，生命周期依赖本地 Runtime 与 SSH session；正式使用前必须部署到稳定 HTTPS host，并在 ChatGPT 中刷新 URL/metadata。
- 本机没有 Docker，因此未执行真实 image build；Dockerfile 合同与 wheel runtime 已验证。
- 目前不需要 auth，因为工具匿名、只读、无存储。只要引入用户专属数据、持久化或写操作，就必须先实现 MCP OAuth 2.1。
- `PRODUCT_RELEASE_HOLD` 保持 ACTIVE；规则与 Runtime 的工程验证不等于真实案例验证或预测准确率。
- PR C 继续保持本地；PR A 合并后再把 PR B/PR C restack 到最新 `main`，重跑全门禁并创建 Draft PR。
