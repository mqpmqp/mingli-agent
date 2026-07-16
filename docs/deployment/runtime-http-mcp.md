# MingLi Runtime HTTP/MCP 部署与 ChatGPT 接入

## 服务边界

这是一个无 widget 的 `tool-only` 服务，同时提供普通 JSON HTTP API 与 Streamable HTTP MCP。服务不保存请求、不调用外部服务；所有工具均为只读、非破坏、幂等和闭世界操作。结果始终保留 `prediction_validity=not_evaluated`，项目仍处于 `PRODUCT_RELEASE_HOLD`，不得把工程覆盖率描述为预测准确率。

公开开发端点只应使用合成数据。若未来处理用户专属数据、保存请求或增加写操作，必须先实现 MCP 兼容的 OAuth 2.1、数据保留/删除策略与独立安全审查。

## 本地运行

```powershell
python -m pip install -e ".[api,dev]"
$env:MINGLI_HOST = "127.0.0.1"
$env:MINGLI_PORT = "8000"
mingli-service
```

低成本检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
Invoke-RestMethod http://127.0.0.1:8000/v1/capabilities
```

MCP 入口是 `http://127.0.0.1:8000/mcp`。它要求 `Content-Type: application/json`，并使用 `Accept: application/json, text/event-stream`。建议再用 MCP Inspector 执行 `initialize`、`tools/list` 和四个工具的代表调用。

## 容器运行

```powershell
docker build -t mingli-runtime-http-mcp:local .
docker run --rm -p 8000:8000 `
  -e MINGLI_ALLOWED_HOSTS="127.0.0.1:8000,localhost:8000" `
  mingli-runtime-http-mcp:local
```

镜像只复制 `pyproject.toml`、`README.md` 与 `src/`，以非 root 用户运行，并通过 `/healthz` 执行容器健康检查。

## 公网配置

稳定部署应位于支持流式响应的 HTTPS 反向代理后。至少配置：

- `MINGLI_HOST=0.0.0.0`：容器监听地址。
- `PORT`：托管平台分配的端口，默认 `8000`。
- `MINGLI_ALLOWED_HOSTS=runtime.example.com`：允许的精确 Host；多个值用逗号分隔。生产环境不得沿用镜像内的 localhost 默认值。
- `MINGLI_ALLOWED_ORIGINS=https://chatgpt.com`：仅当客户端发送 Origin 时配置精确来源；多个值用逗号分隔。
- `MINGLI_FORWARDED_ALLOW_IPS=<trusted-proxy-ip-or-cidr>`：只信任实际反向代理，不应无条件设为 `*`。

服务返回 `Cache-Control: no-store`、`X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY` 与请求 ID。访问日志只记录 `request_id`、方法、路径、状态码和耗时，不记录请求体或出生资料。平台侧还应监控 CPU、内存、请求量、P95 延迟、4xx/5xx 比例和重启次数。

## 临时 HTTPS 隧道

开发阶段可将本地 `8000` 暴露为临时 HTTPS。因为 MCP SDK 默认保护回环服务的 Host，请让隧道把上游 Host 改写为 `127.0.0.1:8000`，或将临时公网主机名精确加入 `MINGLI_ALLOWED_HOSTS`。不要关闭 Host 校验后长期公开服务。

示例（按已安装工具选择其一）：

```powershell
cloudflared tunnel --url http://127.0.0.1:8000 --http-host-header 127.0.0.1:8000
ngrok http 8000 --host-header=rewrite
```

最终 MCP URL 形如 `https://<temporary-host>/mcp`。每次隧道 URL 改变都需要在 ChatGPT 中更新开发应用。

## 连接 ChatGPT Developer Mode

1. 打开 **Settings → Security and login → Developer mode**；若开关不可用，需要工作区管理员允许。
2. 打开 **Settings → Plugins**，或访问 `chatgpt.com/plugins`。
3. 点击加号创建开发应用，填写名称 `MingLi Agent Runtime`、用途说明，以及公网 HTTPS MCP URL（必须包含 `/mcp`）。
4. 创建成功后确认工具列表恰好包含 `analyze_mingli`、`create_ziwei_chart`、`evaluate_ziwei_chart`、`get_ziwei_rule_coverage`。
5. 新开聊天，通过加号选择该应用后运行合成数据 golden prompts。
6. 工具名称、描述、schema 或注解变化后，在插件设置中点击 **Refresh** 重新加载 metadata。

## Golden prompts

- 直接：要求读取“紫微规则覆盖”，应调用 `get_ziwei_rule_coverage` 并明确 Release Hold。
- 链式：提供合成出生参数，先调用 `create_ziwei_chart`，仅在完整命盘上调用 `evaluate_ziwei_chart`。
- Runtime：提供合成 MingLi 输入，调用 `analyze_mingli`，输出必须保留免责、安全警告和 `not_evaluated`。
- 负向：要求发送消息、付款、保存个人资料或执行投资/医疗决定时，不应选择任何 MingLi 工具。
- 重试：同一输入重复调用，结构结果应保持确定性；一次性的 `run_id` 等字段除外。

## 上线门禁

- `/healthz`、HTTP API 与 `/mcp` 均通过公网 HTTPS 冒烟。
- MCP Inspector 能列出并调用 4 个工具，schema 与只读注解正确。
- ChatGPT Developer Mode 的直接、间接与负向 prompt 均符合预期。
- 公网 Host/Origin 只允许部署域名；TLS、日志、指标和告警可用。
- 不使用真实个人数据；不宣称验证准确率；`PRODUCT_RELEASE_HOLD` 与 `prediction_validity=not_evaluated` 未被移除。

官方参考：

- https://developers.openai.com/apps-sdk/build/mcp-server/
- https://developers.openai.com/apps-sdk/plan/tools/
- https://developers.openai.com/apps-sdk/deploy/
- https://developers.openai.com/apps-sdk/deploy/testing/
- https://developers.openai.com/apps-sdk/deploy/connect-chatgpt/
- https://developers.openai.com/apps-sdk/build/auth/
