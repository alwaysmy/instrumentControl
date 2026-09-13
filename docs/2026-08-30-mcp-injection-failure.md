# MCP 工具注入失败分析与后续开发路线

> 日期：2026-08-30
> 环境：Codex v0.151.0 + DeepSeek（custom provider，`wire_api=responses`）
> 涉及文件：`mcp_instruments/server.py`、`C:\Users\AlwaysTS\.codex\cc-switch-model-catalog.json`、
> `C:\Users\AlwaysTS\.agents\skills\instrument-mcp\SKILL.md`
>
> ⚠ **历史文档（2026-09-13 标注）**：下文结论限定于当时的 Codex + DeepSeek 组合。
> 此后 MCP 工具在支持工具注入的客户端（项目内 zcode 用户级 config 已注册
> `instruments`）已正常使用，`server.py` 当前共 **31 个工具**（28 专用 + 3 通用护栏）。
> 文中"17 个 MCP 工具"为当时规模，**已过时**；第六节的"放弃 MCP 路线"决策亦不再代表现状。

## 一、结论（TL;DR）

`mcp_instruments/server.py` 注册到 Codex 后，五台仪器的 MCP 工具（`sds_/sdg_/dmm_/dho_/psu_`
前缀）在 **DeepSeek + 新版 Codex** 下"发现成功、握手成功、`tools/list` 正常，但注入不到会话"，
模型无法调用。根因是两层叠加，**配置无法解开**，因此决策改为：**放弃"MCP 工具注入"路线，
改用"skill 内置脚本"思路**（把仪器能力封装成脚本，AI 经 `exec_command` 调用）。

## 二、现象

- Codex 能连上 MCP server，MCP 初始化握手成功，`tools/list` 返回正常（server 侧日志有
  `ListToolsRequest` 记录）。
- 但发给 DeepSeek API 的请求体里，MCP 工具数为 0（20 个工具全部是内置工具
  `exec_command / write_stdin / apply_patch / view_image / ...`）。

## 三、根因（两层）

### 3.1 第一层：Windows 上声明 `prompts+resources` 的 stdio server 工具不注入

Codex（Windows）对同时声明 `prompts + resources` 能力的 stdio MCP 服务器，存在
"工具发现成功但不注入会话"的缺陷。实测能力声明对比：

| server | 能力声明 | 注入 |
|---|---|---|
| kimi-cu（kimi-cu-win 0.2.14） | 仅 `tools` | 正常 |
| node_repl（rmcp 1.5.0） | `tools` + instructions | 正常 |
| codex_apps（plugin-runtime 0.1.0） | `tools` + resources | 正常 |
| instrument（1.27.0） | `prompts` + `resources` + `tools` | 失败 |
| everything-mcp（1.28.1） | `prompts` + `resources` + `tools` | 失败 |

处理：已在 `server.py` 移除 prompts/resources 处理器，使 instrument 的能力收敛为"仅 tools"，
对齐 kimi-cu（见 [server.py:33](D:\MyProjects\AI\instrumentControl\mcp_instruments\server.py:33)）。

### 3.2 第二层（决定性）：MCP 工具默认延迟到 `tool_search`，DeepSeek Direct 模式无承接

- 新版 Codex（PR #29486 起）默认把 MCP 工具放 `tool_search` 后面，不直接注入；
  日志确认 feature `ToolSearchAlwaysDeferMcpTools` 生效。
- DeepSeek 的 model catalog 里 `tool_mode = null`（Direct 模式），没有 `tool_search` 承接
  → MCP 工具全部丢失。
- 要拿到 `tool_search` 必须开 Code Mode，但 Code Mode 的 `exec` custom tool 被 DeepSeek
  官方 Responses API 拒绝：
  `Unsupported custom tool: 'exec'. Only 'apply_patch' is supported.`
  （DeepSeek Responses 只放行 `apply_patch` 这一个 custom tool）。
- 结论：死结。`tool_search_always_defer_mcp_tools` 等旧配置已被新版忽略，无法关闭延迟。
  在这一层下，kimi-cu 也同样注入不了（实测 flash 会话列出 `mcp__` 工具返回 `NONE`）。

## 四、关键证据

- MCP 握手能力声明：`C:\Users\AlwaysTS\AppData\Local\Temp\codex_mcp_debug_20260830_123947.log`
  （各 server 的 `ServerPeerInfo` / `ServerCapabilities`）。
- 12:31 flash 会话实际工具列表：kimi-cu 13 工具 + node_repl 3 + codex_apps 13 已注入，
  instrument / everything 未注入（印证 3.1）。
- API 请求 trace（thread `01a0511e`，deepseek-v4-pro）：`mcp_tools=0 instr=0 kimi=0`，
  请求体 20 个工具全为内置。
- DeepSeek 报错：`Unsupported custom tool: 'exec'. Only 'apply_patch' is supported.`

## 五、server.py 已做改动（2026-08-30）

1. 移除 `prompts` / `resources` 处理器（`ListPromptsRequest` / `GetPromptRequest` /
   `ListResourcesRequest` / `ListResourceTemplatesRequest` / `ReadResourceRequest` 全部 pop），
   使初始化能力收敛为仅 `tools`。
2. 设备库懒加载 + 后台预热线程（启动时间约 1.9s → 1.5s）。

备份：`mcp_instruments/server.py.bak_20260830_131148`。

> 说明：第 1、2 点都是无副作用优化，但在第二层问题下不能单独让工具注入成功；保留不改回。

## 六、决策与后续路线（skill 内置脚本）

当前 MCP 工具注入路线在 DeepSeek + 新版 Codex 下走不通（除非换 OpenAI 官方模型、或上
第三方代理把 DeepSeek 包装成支持 `exec` 的 Responses）。后续开发改为 **skill 内置脚本思路**：

1. `instrument-mcp` skill 目前只有 `SKILL.md`，无 `scripts/`；后续补 `scripts/` 目录。
2. 把 17 个 MCP 工具对应的能力，封装成 CLI 脚本，复用现有设备库：
   （2026-09-13 标注：工具数已从 17 增至 31，该路线未继续；现状见 AGENTS.md §三）
   `common/`（统一发现）、`dh1766_control/`、`sds_control/`、`sdg_control/`、
   `keysight_3446x/`、`dho_control/`。
3. `SKILL.md` 改为"指引 AI 选择并调用 `scripts/` 下脚本"的决策文档（保留安全门语义：
   复位类命令不暴露、输出/信号类操作需 `confirm`、写操作备份→改→回读→恢复、留痕）。
4. AI 通过内置 `exec_command` 调脚本，绕开 MCP 工具注入，直接可用。

## 七、备注 / 待办

- `cc-switch-model-catalog.json` 由 cc-switch 管理，切换模型会被覆盖；`tool_mode` 保持
  `null`（Direct），**不要改 `code_mode`**（DeepSeek 拒绝 `exec`）。
- 相关上游 issue：openai/codex #19425、#33608、#37825；PR #29486。
- `mcp_instruments/server.py` 可保留（供支持 MCP 工具注入的客户端使用），但不再作为
  Codex + DeepSeek 的主路径。
