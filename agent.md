# agent.md — 接管本仓库的 Agent 入口

本文件是**上手路径**（怎么跑、代码在哪、加设备改哪些文件）。
**操作仪器的硬规矩不在本文件**，在 [`AGENTS.md`](AGENTS.md)——动手前必读，
本文件不重复其内容以免两处漂移。

| 文件 | 定位 | 谁该读 |
|---|---|---|
| `agent.md`（本文件） | 上手路径：目录地图、运行方式、加设备的改动清单 | 第一次接手本仓库的 Agent |
| `AGENTS.md` | **工作规范与安全红线**：SCPI 铁律 15 条、禁发命令、排查流程 | 每次操作仪器前 |
| `README.md` | 项目定位、用户视角用法、MCP 注册、文档导航 | 用户/新同事 |
| `mcp_instruments/SKILL.md` | MCP 工具选择决策树、参数语义、安全门（AI 侧使用指引） | 调 MCP 工具的 Agent |
| `docs/AI_OPERATION_GUIDE.md` | 各库 API 速查、固件特性、闭环范例 | 写脚本时 |
| `docs/TEST_RECORDS.md` | 历轮实测时间线（证据链） | 想知道"什么被实测过" |

## 一、一条命令上手

```bash
pip install -r requirements.txt        # pyvisa（+ 跑 MCP 需 mcp 包）
python mcp_instruments/config_cli.py show         # 看地址解析链现状（不连设备）
python TEST_SCRIPTS/common/verify_all_devices.py  # 真机只读全链路验收（约 1 分钟）
python TEST_SCRIPTS/common/audit_all_commands.py  # SCPI 命令审计（代码 vs 手册提取版）
python TEST_SCRIPTS/common/audit_guardrail_coverage.py  # 护栏覆盖性审计（查误伤/漏项）
python mcp_instruments/server.py                  # 启动 MCP 服务器（stdio）
```

Python 需 **3.10+**（代码用了 `X | None` 写法与 walrus）。Windows 下 MCP 注册必须用
python **全路径**（WindowsApps 别名会 spawn 失败）。项目根自动进 `sys.path`（各库自己处理），
`dh1766_control` 是 src 布局、需额外 `sys.path.insert` 或 `pip install -e ./dh1766_control`。

## 二、目录地图

```
common/            VISA 客户端 + 统一发现 + 地址解析（所有设备共用，改动影响面最大）
  visa_client.py     VisaClient：query/write/query_raw/close（\n 终止符、open_timeout）
  discovery.py       find_device 四层查找链、identify/identify_lan、CIDR 扫描
  resolver.py        resolve(kind)：显式 > env > devices.json > 缓存 > 自动发现；DEVICE_KINDS 表
mcp_instruments/
  server.py          MCP 服务器：50 工具 + 安全护栏（黑名单/confirm/看门狗/审计落盘）
                     含 1 个故障兜底 usb_reset（USB-TMC 卡死→重启该仪器 USB 节点）
  config_cli.py      本机地址配置 CLI（show/init/set/autofill/clear）
  SKILL.md           AI 使用指引（工具决策树/参数语义/安全门）
<device>_control/    各设备库：commands.py(命令常量) + <name>.py(封装) + docs/(手册提取版)
  sds_control/       Siglent SDS800X HD（功能最全：波形/截图/测量/自动定标/触发诊断）
  sdg_control/       Siglent SDG2000X 信号源（BSWV 键值对）
  keysight_3446x/    Keysight 34465A 万用表
  rigol_scope/       RIGOL 示波器共享内核（DHO800/900 与 MHO900 命令集 97% 重合，一份实现）
  dho_control/       RIGOL DHO800/900 示波器（薄封装，实现见 rigol_scope/）
  mho_control/       RIGOL MHO900 系列示波器（薄封装，MHO984D 实测基准）
  dg832_control/     RIGOL DG800 系列信号源（DG832 基准；保护联锁/DC 快照/扫频）
  dh1766_control/    DH1766 三路电源（src 布局、可 pip install、有 EXPERIENCE.md）
  emoe_control/      Emoe 校准器（骨架：仅发现 + *IDN?）
TEST_SCRIPTS/<dev>/  实测/验证脚本（真机跑，必须 try/finally 恢复设定）
TEST_DATA/<dev>/     实测留痕（JSON/CSV/PNG，时间戳命名，防覆盖）
docs/                审计报告、实测记录、AI 操作手册、设计文档
archive/             历史版本归档（旧驱动）
```

## 三、设备 ↔ 库 ↔ 解析 kind ↔ MCP 前缀

| 设备 | 库 | `resolve(kind)` | MCP 工具前缀 | 手册提取版 |
|---|---|---|---|---|
| DH1766A-1 电源 | `dh1766_control` | `psu` | `psu_*` | `dh1766_control/docs/SCPI_COMMANDS_DH1766A.md` |
| RIGOL DHO924S | `dho_control` | `dho` | `dho_*` | `dho_control/docs/DHO800编程手册_output/` |
| Siglent SDS824X HD | `sds_control` | `sds` | `sds_*` | `sds_control/docs/SDS800XHD_…_output/` |
| Siglent SDG2122X | `sdg_control` | `sdg` | `sdg_*` | `sdg_control/docs/SDG_…_output/` |
| Keysight 34465A | `keysight_3446x` | `dmm` | `dmm_*` | `keysight_3446x/docs/Truevolt_…_output/` |
| Emoe 校准器 | `emoe_control` | —（只发现） | — | 未提供 |
| **RIGOL MHO984D** | `mho_control` | `mho` | `mho_*` | `mho_control/docs/MHO900编程手册_output/` |
| **RIGOL DG832** | `dg832_control` | `dg` | `dg_*` | `dg832_control/docs/02_编程手册.txt` |

**表里只列发现入口，不列地址**（DHCP/换网段/换 USB 口/串口号漂移，写死必失效）。

## 四、地址解析（唯一合法来源）

`common/resolver.py::resolve(kind)`：
**显式入参 > `INSTRUMENT_<KIND>_RES` > `devices.json` > `last_good_resources.json` > `find_device()`**。
配置/缓存目录 `%LOCALAPPDATA%\instrumentControl\`。值一律**完整 VISA 资源串**；
裸 IP/host 只能喂给 `config_cli.py set <kind> <host>`（探测协议 + 核对 `*IDN?` 后落库）。
用 `config_cli.py autofill` 把 `instr_discover` 的发现结果固化下来。
每个专用工具连接后都会 `_verify_idn()` 核对身份，不符即拒绝（地址被 DHCP 分给别的设备时不误发 SCPI）。

## 五、加一台新设备的标准流程（照做即可）

1. **手册先行**：把设备编程手册提取成 markdown 放 `<lib>/docs/<手册>_output/`（沿用既有目录命名）；
2. **命令常量** `commands.py`：每条命令附手册出处（章节/页），**禁止凭记忆写**；
3. **封装库** `<name>.py`：`connect/close/query/write/query_raw/idn/snapshot` + 设备能力方法；
   写操作按铁律"写入 → 查 `SYST:ERR?` → 回读比对（容差）"；
4. **解析层**：`common/resolver.py::DEVICE_KINDS` 加 `kind:(IDN匹配串, 显示名, 环境变量名)`；
5. **MCP**：`server.py` 加 `_<kind>()` 连接函数、`_MODEL_KIND` 映射、若干 `@mcp.tool()`；
   危险动作必须走 `confirm`/`expect_*` 状态声明门；
6. **审计**：`TEST_SCRIPTS/common/audit_all_commands.py` 的 `TARGETS` 加该库与手册路径，跑到零 MISS；
7. **实测留痕**：`TEST_SCRIPTS/<dev>/` 加脚本，输出落 `TEST_DATA/<dev>/`；
8. **文档同步**：`README.md`、`AGENTS.md`（设备表/待办）、`mcp_instruments/README.md`、
   `SKILL.md`、`docs/AI_OPERATION_GUIDE.md`、`docs/TEST_RECORDS.md` 六处一起改——
   本仓库有过"文档漂移专项审计"，只改代码不改文档算未完成。

## 六、高频坑（详见 AGENTS.md 铁律）

- 命令**只吃短形式**的库（SDS）与**只吃长形式**的库（Keysight/RIGOL）不能互抄；
- 查询响应可能带**回显头/单位后缀/短格式**，解析要兼容，浮点比较必须带容差；
- 示波器**超屏读数被钳制**在屏界，判断削顶/有无波形用**截图**（PNG 可直接读图）；
- 测量引擎有**过渡期**：切档/切测量项后要等稳定再读数，必要时重发；
- 写序列前先 **drain 错误队列**，否则滞后报错张冠李戴；
- 全局只有**一把设备锁**（MCP 内串行），超时挂起线程会占锁拖慢后续调用。

## 七、本次会话（2026-09-15）状态

- 已 clone 主仓到本机并跑通只读验收/审计脚本；
- 项目缺陷审阅结论见 [`docs/review_20260915.md`](docs/review_20260915.md)（按 A/B/C/D/E/F 分类，
  含严重度与修复建议，高severity项均已回到代码实测复核）；
  **本轮已修**：`instr_query` / `instr_write.readback_cmd` 两条黑名单走私通道、
  黑名单中间缩写漏网（`SYST:RESE` 类）、看门狗超时的审计语义；回归
  `TEST_SCRIPTS/common/verify_remote_lock_block.py` 47 用例全 PASS；
- **新增 MHO900（MHO984D）接入**：库 `mho_control/`（手册 480 页提取 + 47 条命令）、
  解析 kind `mho`、MCP 6 个 `mho_*` 工具（服务器 31→37 工具）；
  真机验收 `TEST_SCRIPTS/mho/verify_mho.py` **45/45 PASS**
  （留痕 `TEST_DATA/mho/verify_mho_20260915_*.json`；冻结态 BYTE/WORD 差 0.196% 证明
  WORD 低字节在前；RAW `xinc` 与采样率自洽）；
- 本机只挂了 MHO984D 这一台（`resolve("mho")` 走 `devices.json`，其余 kind 未配置）；
- **待办**：DHO 真机复验（本机无 DHO）——按交接单 `docs/dho_live_verification_handoff.md`
  跑 6 项检查并回填；离线部分 `verify_rigol_scope_shared.py`（74 断言）已全 PASS。
