# instrumentControl

**给 AI/Agent 用的仪器控制 MCP**：把实验室仪器（示波器 ×2 / 信号源 / 万用表 / 电源 / 校准器）
统一封装为 VISA-SCPI 驱动库，再由 `mcp_instruments/` 暴露成 MCP 工具，
让 AI 能安全地发现设备、查询状态、自动定标、测量、截屏、上下电。

设计前提：**AI 会看手册、会截图，也会犯错**。所以本项目把"命令不许猜、状态要回读、
危险动作要装门"做成**代码里的硬约束**，而不是文档里的建议。

```
AI 客户端（DSH / Codex / Claude / opencode …，经 MCP stdio）
        │
        ▼
mcp_instruments/server.py ─── 31 工具（28 专用 + 3 通用护栏），无状态连接+全局锁串行化
        │
        ├─▶ sds_control       Siglent SDS800X HD 示波器（波形/截图/测量/触发诊断/auto_scale）
        ├─▶ sdg_control       Siglent SDG2000X 信号源（BSWV 键值对）
        ├─▶ keysight_3446x    Keysight 34465A 万用表（CONF/MEAS/NPLC）
        ├─▶ dho_control       RIGOL DHO800/900 示波器
        ├─▶ dh1766_control    DH1766 三路可编程电源（唯一 pip 可安装，自带手册/经验文档）
        └─▶ emoe_control      Emoe 校准器（骨架：仅发现 + `*IDN?`）
                 ▲
        common/ ─┴─ 统一发现 find_device（resource → hosts → VISA 列表 → CIDR 扫描）+ VisaClient
```

## 三条设计主线

1. **命令零猜测**：每条 SCPI 都对照手册提取版落码；新增命令必过
   `TEST_SCRIPTS/common/audit_all_commands.py` 审计。写操作固定三步
   ——写入 → 查 `SYST:ERR?` → 回读比对（含容差比较与短格式/单位后缀兼容）。
2. **安全门写进代码**（不只是文档约定）：
   - 复位/存储覆写类命令零暴露（MCP 通用写黑名单拦截 `*RST/*SAV/*RCL/:SYST:RES|FACT|PRES`）；
   - 远程锁定类命令禁止（`SYST:REM/SYST:RWL/SYST:LOCK`）——面板要留给现场操作；
   - 输出类操作必须声明当前拓扑/负载并通过校验：
     `sdg_output(..., expect_load)`、`psu_output(..., expect_mode)`、`psu_power_cycle(..., confirm)`；
   - 电源切换输出模式前强制"输出全关"（继电器联动，库内无条件拦截）；
   - 新设备**零代码接入**：`instr_query` / `instr_write` 通用护栏（写前 drain、写后查错、
     自动回读、审计落盘、离线资源硬超时看门狗）。
3. **实测留痕与可回溯**：所有实测输出落 `TEST_DATA/<device>/`（时间戳命名），
   测试脚本放 `TEST_SCRIPTS/<device>/`，注入/回归/审计均有留痕文件。

## 快速开始

```bash
pip install -r requirements.txt          # pyvisa（+ 运行 MCP 服务器需 mcp 包）
pip install -e ./dh1766_control          # 电源库走 src 布局，可独立安装
python mcp_instruments/server.py         # 启动 MCP 服务器（stdio）
```

MCP 注册（示例，路径按需替换）：

```jsonc
// DSH: ~/.dsh/cordis.patch.yml 的 insert 列表；zcode: ~/.zcode/cli/config.json
{ "serverName": "instruments", "transport": "stdio",
  "command": "C:/Users/<you>/AppData/Local/Programs/Python/Python311/python.exe",
  "args": ["D:/MyProjects/AI/instrumentControl/mcp_instruments/server.py"] }
```

> Windows 下必须用 python **全路径**（WindowsApps 别名的 python 在部分客户端 spawn 时失败）。
> AI 侧的使用指引见 skill `instrument-mcp`（工具选择决策树/参数语义/安全门/工作流）。

## 目录结构

| 目录 | 说明 |
|---|---|
| `common/` | VISA 客户端 `VisaClient` + 统一发现 `find_device`（多设备共用） |
| `mcp_instruments/` | MCP 服务器（`server.py`）+ 工具清单（`README.md`）+ AI 使用指引（`SKILL.md`） |
| `dh1766_control/` | 电源库（可 pip 安装；手册提取/命令速查/经验总结在 `docs/`） |
| `dho_control/`、`sds_control/`、`sdg_control/`、`keysight_3446x/`、`emoe_control/` | 各设备库 + 手册提取 |
| `TEST_SCRIPTS/` | 实测/验证脚本，按设备分目录 |
| `TEST_DATA/` | 实测留痕（JSON/CSV/PNG，时间戳命名） |
| `docs/` | 使用手册、命令审计报告、实测记录、设计文档 |
| `dg832-control/` | DG832 信号源独立嵌套 git 仓库（历史库，勿混入主仓提交） |
| `archive/` | 历史版本归档（旧版驱动，可回溯） |

## 设备与资源

| 设备 | 库 | 资源 |
|---|---|---|
| DH1766A-1 三路电源 | `dh1766_control` | USB 或 `TCPIP0::192.168.31.144::5025::SOCKET` |
| RIGOL DHO924S | `dho_control` | `TCPIP0::192.168.31.146::5555::SOCKET` |
| Siglent SDS824X HD | `sds_control` | VXI-11 `192.168.31.220::inst0` |
| Siglent SDG2122X | `sdg_control` | VXI-11 `192.168.31.206::inst0` |
| Keysight 34465A | `keysight_3446x` | VXI-11 `192.168.31.123::inst0` |
| Emoe 校准器 | `emoe_control` | 串口（ASRL 端口号会漂移，接入前先 `instr_discover`） |

## 安全摘要（完整红线见 `AGENTS.md`）

- **输出/信号类操作**（`sdg_output`/`psu_output`/`psu_power_cycle`）开与关都需 `confirm=True`：
  它代表"**已获得关断授权**"（用户本轮明确要求，或明确声明独占使用），不是"我知道要关"。
- **操作电源前先查模式**（`psu_status`/`psu_mode`）：TRAC 下 CH2 跟随 CH1 输出**负压**是正常现象。
- **禁止远程锁定与复位**：`SYST:REM/SYST:RWL/SYST:LOCK`、`*RST/:SYST:RES/:SYST:FACT` 一律不可用。
- **测试脚本必须 `try/finally` 恢复**被改设定并关闭输出。
- 示波器读数超屏会被钳制 → "有无波形/是否削顶"用**截图**判断，不要迷信设备测量值。

## 扩展新设备

1. `instr_discover` 定位资源 → 2. `instr_query`（只读）跑通手册里的查询
→ 3. `instr_write(confirm=True, readback_cmd=...)` 验证写命令 → 4. 命令有了出处后
再落库（`commands.py` 常量 + 库方法 + 可选 MCP 工具），最后跑命令审计器防回归。

## 文档导航

| 文档 | 内容 |
|---|---|
| `AGENTS.md` | **Agent 工作规范（铁律/安全红线/排查流程）——操作仪器前必读** |
| `mcp_instruments/SKILL.md` | MCP 使用指引：工具选择决策树、参数语义、安全门、典型工作流 |
| `mcp_instruments/README.md` | MCP 工具清单与安全约定 |
| `docs/AI_OPERATION_GUIDE.md` | AI 操作手册：各库 API、固件特性、闭环范例 |
| `docs/TEST_RECORDS.md` | **历轮实测记录（时间线）** |
| `docs/command_audit_20260823.md` | SCPI 命令审计报告（零猜测命令结论） |
| `dh1766_control/docs/EXPERIENCE.md` | DH1766 时序/固件差异/上电过渡态等实测经验 |
