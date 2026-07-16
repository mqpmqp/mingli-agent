# Runtime HTTP/MCP v1 TDD Evidence

## Source and user journeys

本轮没有外部 `*.plan.md`；用户旅程来自堆叠 PR 目标与 OpenAI Apps SDK 官方合同。

1. HTTP 调用方可检查服务能力并执行 MingLi、紫微排盘、规则求值和覆盖率查询。
2. ChatGPT 可通过 Streamable HTTP MCP 发现并调用 4 个精确、只读工具。
3. 运维方可在本地、容器和 HTTPS 反向代理后运行服务，并获得有限请求日志与健康检查。
4. 公开服务只接受配置的 Host/Origin，拒绝超大或无效请求，不记录请求体。
5. 开发者可在 ChatGPT Developer Mode 中连接服务，并用合成数据运行 golden prompt。

## RED/GREEN checkpoints

| Cycle | RED evidence | GREEN evidence | Guarantee |
|---|---|---|---|
| Service adapters | `30db920`：`tests/test_runtime_service.py` 因服务模块缺失而 RED | `5193c08`：7 个 adapter tests 通过 | 纯函数 adapter 保留 Runtime、紫微与 Hold 合同 |
| HTTP/MCP | `a48f6cc`：`mingli.service_app` 缺失，HTTP/MCP 合同 RED | `7a6e1e3`：5 个 HTTP/MCP tests 通过；联合服务层 12 passed | HTTP 路由、MCP 初始化/list/call、schema 与注解可运行 |
| Public hardening | `e976988`：3 个测试分别因缺少公开 Host 策略、chunked body 限制和 telemetry 而 RED | `5f6f61f`：8 个 HTTP/MCP tests 通过 | Host/Origin allowlist、1 MB body 上限和无请求体日志生效 |
| Deployment artifacts | `02fc6f8`：Dockerfile、`.dockerignore`、部署 runbook 缺失，3 tests RED | `e9a666e`：11 个 deployment + HTTP/MCP tests 通过 | 非 root 镜像合同、最小 build context 与 ChatGPT runbook 完整 |

## Test specification

| # | What is guaranteed | Test target | Type | Result |
|---|---|---|---|---|
| 1 | `/healthz` 与 `/v1/capabilities` 返回 no-store、安全 headers 和无存储能力声明 | `test_health_and_capabilities_expose_no_store_read_only_service` | integration | PASS |
| 2 | HTTP Runtime、紫微 chart → rules 链和 coverage 返回真实确定性结果 | `test_http_api_runs_mingli_and_chains_ziwei_chart_into_rules` | integration | PASS |
| 3 | invalid JSON、错误 shape、degraded chart 和超大 body 映射为稳定 4xx errors | `test_http_api_maps_invalid_json_domain_errors_and_large_requests` | integration | PASS |
| 4 | MCP 精确暴露 4 个工具，全部为只读、非破坏、幂等、闭世界 | `test_mcp_lists_precise_read_only_tools_and_calls_real_coverage` | protocol integration | PASS |
| 5 | `analyze_mingli` 的 required fields 与 enums 为机器可读 schema | `test_mcp_analyze_tool_has_explicit_machine_friendly_input_schema` | contract | PASS |
| 6 | 公开 Host/Origin 仅接受显式 allowlist | `test_mcp_transport_allows_only_configured_public_host_and_origin` | security integration | PASS |
| 7 | 无 Content-Length 的 chunked MCP body 超过 1 MB 时返回 413 | `test_request_policy_rejects_chunked_oversized_mcp_body` | security integration | PASS |
| 8 | access log 只含 request id、method、path、status、duration | `test_request_policy_logs_sanitized_request_metadata` | observability | PASS |
| 9 | Docker 合同使用 Python 3.11、非 root 用户、健康检查与最小复制范围 | `tests/test_runtime_deployment.py` | deployment contract | PASS |
| 10 | runbook 覆盖公网配置、Developer Mode、Hold 与 `not_evaluated` | `test_deployment_runbook_covers_runtime_and_chatgpt_connection` | documentation contract | PASS |

## Validation evidence

- Focused coverage：18 passed；`mingli.service` + `mingli.service_app` 总覆盖率 88.12%，高于 80% 门槛；1m02s。
- Full pytest：381 passed，1 skipped，31 subtests passed；19m25s。
- Fast gate：隔离复跑 285 passed，1 skipped，96 deselected，16 subtests passed；4m10s，满足 300 秒门限。首次与 focused/real-case 并发的编排实例在 300 秒处被终止但无测试失败，不计为隔离 gate 结果。
- Benchmark gate：38 passed，344 deselected，15 subtests passed；13m56s。
- Real-case gate：58 passed，324 deselected；1m12s。
- Ruff：scoped Runtime、HTTP/MCP 与 deployment tests 全部通过。
- Pyright：scoped Runtime、HTTP/MCP 与 deployment files 为 0 errors / 0 warnings。
- `compileall src tests`：通过。
- Wheel/sdist：`mingli_agent-2.0.0` 构建成功。
- Isolated wheel smoke：wheel 内 `/healthz` 返回 `ok`；MCP initialize/list/call 返回 4 个工具与 `REVIEW_REQUIRED / 184 / not_evaluated`。
- `pip-audit . --strict`：No known vulnerabilities found。
- Local runtime smoke：`/healthz`、MCP `initialize`、`tools/list`、`get_ziwei_rule_coverage` 全部通过。
- Public HTTPS smoke：临时 SSH tunnel 上重复执行相同 MCP 协议链，返回 4 个工具、`REVIEW_REQUIRED` 与 `not_evaluated`。
- ChatGPT host loop：Developer Mode 应用连接成功；golden prompt 实际调用 coverage 工具并返回 `REVIEW_REQUIRED / 184 / not_evaluated`，同时明确不是预测准确率。

## Known gaps and warnings

- Starlette 现行 `TestClient` 对 `httpx` 发出迁移到 `httpx2` 的 deprecation warning；不影响当前结果，后续随 MCP/Starlette 官方兼容组合升级。
- 本机没有 Docker/Podman，因此执行了 Dockerfile 静态合同、wheel/sdist 和 wheel runtime smoke，但没有实际 `docker build`。
- 公网地址是开发用临时 tunnel，不是稳定生产托管；不能作为 Draft PR 或长期 ChatGPT 应用的最终 URL。
- 服务匿名且不保存请求。任何用户专属数据、持久化或写操作都必须先增加 OAuth 2.1、隐私/删除策略和安全评审。
- `PRODUCT_RELEASE_HOLD` 与 `prediction_validity=not_evaluated` 保持不变；测试覆盖率不是预测准确率。

## Merge evidence

PR C 已 restack 到 PR B commit `9221d434af9f5b55030d9f11a8bc8786c694416b`。restack 前后 C-only stable patch-id 均为 `eeb760b0be079caaef55cbd3d7dd0160e72915cd`，证明 9 个 Runtime 提交的内容未改变；本地全门禁通过后推送并创建以 PR B 分支为 base 的 Draft PR。
