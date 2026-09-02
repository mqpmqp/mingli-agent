# Runtime 502 Recovery TDD Evidence

## Source and user journeys

本轮范围来自 GitHub Issue #46 与 2026-08-23 P0 恢复合同。

1. ChatGPT 可通过一个持久 HTTPS `/mcp` 入口依次发现并调用四个只读工具。
2. `create_ziwei_chart` 返回的完整 chart 必须原样交给 `evaluate_ziwei_chart`。
3. Host/Origin、请求体上限、无存储、Hold 与 `not_evaluated` 合同不得因恢复部署而放宽。
4. 内部服务异常必须失败关闭，不能把合成出生标记或内部 traceback 返回给客户端或写入服务日志。
5. 部署入口必须由持久进程管理并经外部 TCP/TLS/MCP 验证；临时隧道或 VPS 内部成功不算公网恢复。

## RED/GREEN checkpoints

| Cycle | RED evidence | GREEN evidence | Guarantee |
|---|---|---|---|
| MCP full chain and exception privacy (initial) | `ab88959`：新增完整四工具链与异常隐私测试；异常标记仍泄漏到 MCP `isError` 内容和服务 traceback | `1e67ac6`：同一测试转绿，但修改了冻结的 `service_app.py`，随后被冻结合同门禁拒绝，未作为最终实现 | 四工具真实顺序调用；意外异常保持失败且只暴露通用错误 |
| Non-frozen privacy gateway (final) | `f5b0ba9`：测试改为要求 `mingli.service_gateway`，因模块尚不存在而在收集阶段 RED | `ae42c9b`：新增非冻结 gateway、恢复 `service_app.py` 与 `origin/main` 一致；聚焦测试与冻结合同均 PASS | 在不改变冻结 Runtime 的前提下净化 MCP JSON 错误正文和异常日志，且不伪造成功 |
| Persistent HTTPS proxy | `ed4f0fc`：缺少受版本控制的 Caddy 配置，部署合同测试因文件不存在而失败 | `4725487`：Caddy 合同测试通过 | Runtime 仅绑定 loopback，Caddy 保留公网 Host 校验并即时转发流式响应 |
| Slow VPS health probe | `39d978a`：部署测试要求 15 秒 healthcheck，在原 5 秒 Dockerfile 上为 1 failed、4 passed；现场同时记录应用实际 200 而 Docker 多次 timeout | `000bb8d`：同一测试 5 passed，最终容器 health=`healthy` | 小规格 VPS 上 Python health probe 的启动开销不再造成假性 unhealthy；应用内请求 timeout 仍保持 3 秒 |

## Test specification

| # | What is guaranteed | Test target | Type | Result |
|---|---|---|---|---|
| 1 | initialize、tools/list 与四个 tools/call 均返回 HTTP 200/result；四工具 `isError=false` 且有 structuredContent | `test_mcp_end_to_end_calls_all_tools_and_preserves_frozen_contracts` | protocol E2E | PASS |
| 2 | chart → evaluate 使用完整真实 chart；四工具保持 `prediction_validity=not_evaluated` | 同上 | contract integration | PASS |
| 3 | 工具注解保持只读、非破坏、幂等、闭世界，Commercial/Rule Content Hold 保持 ACTIVE | 同上 | safety contract | PASS |
| 4 | HTTP/MCP 意外异常不回显出生标记或 traceback，仍返回失败而非伪成功 | `test_service_exceptions_do_not_leak_birth_data_or_tracebacks` | security integration | PASS |
| 5 | 公网 Host/ChatGPT Origin 正向与未允许 Host/Origin 反向仍受保护 | `test_mcp_transport_allows_only_configured_public_host_and_origin` | security integration | PASS |
| 6 | Content-Length 与 chunked 超限请求均返回 413 | 现有 request-policy tests + 容器协议冒烟 | security E2E | PASS |
| 7 | 持久 HTTPS 反代只指向 loopback，且不重写 Host 绕过 Runtime allowlist | `test_stable_https_proxy_keeps_runtime_private_and_preserves_host_checks` | deployment contract | PASS |

## Validation evidence

- 聚焦测试：22 passed，2 warnings。
- 聚焦覆盖率：`mingli.service` 100%，`mingli.service_app` 91%，`mingli.service_gateway` 88%，合计 91%，高于 80% 门槛。
- `test-fast`：404 passed、1 skipped、150 deselected（182.41 秒）。
- 最终完整 pytest：554 passed、1 skipped（1031.44 秒）；两条既有 warning，无失败。
- Python 3.11.15：纯函数 analyze/chart/evaluate/coverage 全部 PASS。
- 真实本地 TCP Runtime：六个 HTTP 路由与完整 MCP 四工具链 PASS。
- 最终 Docker image `sha256:0589c352…`（来源 `000bb8d`）：build、health、六路由、四工具 MCP、Host/Origin、Content-Length/chunked limits 全部 PASS；运行用户为 `mingli`。
- Caddy/真实 Let's Encrypt 证书经 VPS loopback 完整四工具链 PASS。
- 公网 DNS 与 TCP 80 PASS；公网 TCP 443 被 Lightsail 防火墙阻断，因此公网 MCP 与 ChatGPT golden prompt 不计为 PASS。
- 一次并发启动 `test-fast` 与完整 pytest 的尝试因两个 pytest 进程争用同一 Windows temp root 而产生 `WinError 5` setup errors，已中止且不计入测试结果；最终结果只采信独立 ASCII temp root 下的串行重跑。

## Known gaps

- Starlette `TestClient` 仍报告项目既有的 `httpx` 迁移 warning；本轮没有升级传输栈。
- 公网 443 需要 Lightsail 管理权限开放；实例角色被拒绝 Lightsail/EC2 防火墙读取权限。
- `sslip.io` 解析跟随公网 IP，不替代长期静态 IP 与自有域名。
