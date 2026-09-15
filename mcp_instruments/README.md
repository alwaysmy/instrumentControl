# instrument MCP Server

七台仪器的统一 MCP 接口（sds_control / sdg_control / keysight_3446x /
dho_control / mho_control / dg832_control / dh1766_control + common 统一发现层）。

## 启动

```powershell
python D:\MyProjects\AI\instrumentControl\mcp_instruments\server.py
```

MCP 注册（opencode/cursor 等）：command 用 python 全路径，args 为本文件路径。

## 工具清单

共 **50 个** = 46 个设备专用 + 3 个通用护栏（`instr_discover` / `instr_query` / `instr_write`）
+ 1 个**故障维护兜底**（`usb_reset`：USB-TMC 卡死时重启该仪器的 USB PnP 设备节点）。

| 工具 | 说明 | 安全 |
|---|---|---|
| `instr_discover(cidr?)` | 全网段+VISA 发现所有仪器；结果按 `*IDN?` 回写地址缓存（`recognised_now`），探测到 DH1766 会补发 `SYST:LOC` 归还面板 | 只读（+DH1766 一次 `SYST:LOC`） |
| `instr_query(resource, cmd, timeout_ms?)` | 通用 SCPI 查询（新设备零接入；cmd 必须含 `?`，且**每个 `;` 分段都须是查询**——判据＝命令头带 `?`，**问号后允许带参数**，如 `:MEASure:ITEM? VPP,CHANnel1`；多命令消息不能夹带写命令） | 只读 |
| `instr_write(resource, cmd, readback_cmd?, confirm, timeout_ms?)` | 通用 SCPI 写：黑名单拦截/drain+SYST:ERR?/自动回读/审计落盘/看门狗 | **confirm=True**；`*RST` 等一律 forbidden |
| `sds_status` | SDS 快照（采集/时基/触发/通道） | 只读 |
| `sds_auto_scale(ch, use_autoset?)` | 自动定标；use_autoset 破坏性需理解语义 | 改配置 |
| `sds_measure(item, ch)` | SIMPLE 测量（51 项：PKPK/FREQ/RMS/PER/PWID...） | 只读 |
| `sds_meas_threshold` / `sds_meas_gate` | 测量阈值 / 测量门限 | 改配置 |
| `sds_meas_statistics` / `sds_meas_dtime` | 高级统计 / 延迟测量配置 | 改配置 |
| `sds_meas_display` | 结果显示样式 / 统计模式 / 幅值策略 | 改配置 |
| `sds_measure_phase(src_a, src_b)` | 双通道相位差（度，PHA，用后自动清槽） | 只读 |
| `sds_get_waveform(ch, points=50000, save_csv)` | 读通道波形（电压+时间轴，FFT 交叉验证可信）；返回摘要 + 可选 CSV 路径，不返回完整数组防上下文爆炸 | 只读 |
| `sds_screenshot` | 截屏存 PNG 返回路径，**可直接 Read 读图**（波形形态/削顶/菜单） | 只读 |
| `sds_diagnose` | 触发链路诊断 | 只读 |
| `sds_shutdown(confirm)` | 远程关机 | **confirm=True** |
| `sdg_status` | SDG 快照 | 只读 |
| `sdg_counter(on?)` | 内置频率计 FCNT（FRQ/PW/NW/DUTY/FRQDEV）| 只读 |
| `sdg_set_wave(ch, wvtp, freq_hz, amp_v, offset_v=0)` | 设波形参数（不动输出开关） | 改配置 |
| `sdg_output(ch, on, expect_load, confirm)` | 输出开关；**expect_load 必填**（HZ/50，仅校验）；**开/关都需 confirm=True** | **confirm 必填** |
| `dmm_nplc(value?)` | 电压 DC 积分时间 NPLC（0.02~100）| 改配置 |
| `dmm_measure(function)` | 34465A 测量（10 种） | 只读 |
| `dmm_status` / `dmm_configure` | 快照 / 配置 | 只读/改配置 |
| `dho_status` / `dho_measure_item` | DHO 快照 / 测量 | 只读 |
| `mho_status` | MHO 快照（触发/采集/采样率/四通道档位；本系列采样率随通道数下降） | 只读 |
| `mho_measure_item(item, ch, ch2?)` | MHO 测量（手册 3.17.2 表：VPP/VMAX/VAVG/VRMS/PERiod/FREQuency/RTIMe…；双信源延迟·相位 RRDelay/RRPHase 需 ch2）；无有效值报错含 9.9E37 | 只读 |
| `mho_screenshot` | MHO 截屏存 PNG 返回路径（`:DISPlay:DATA? PNG` 原生位图，**可直接 Read 读图**） | 只读 |
| `mho_get_waveform(ch, points=1000, mode, fmt, save_csv)` | MHO 读波形（NORMal 1~1000 点 / RAW 需 STOP；BYTE·WORD·ASCii）；返回摘要 + 可选 CSV | 只读 |
| `mho_acquisition(action)` | run/stop/single/force（**stop 冻结采集**，RAW 读内存前必须） | 改采集状态 |
| `mho_autoset(confirm)` | `:AUToset` 一键定标；**全局破坏性**（重置所有通道/时基/触发），confirm=True | **confirm 必填** |
| `dg_status(model?)` | DG832 快照：设备信息 + CH1/2 波形配置/输出/负载（**动它之前先查**） | 只读 |
| `dg_protect(ch, high?, low?, state?)` / `dg_get_protect(ch)` | 电压保护（防超压）；**设幅度/偏移或开输出前必须先开有效保护** | 改配置 |
| `dg_set_wave(ch, shape, freq?, amp?, offset?, phase?, sample_rate?)` | 设波形（一条 `:APPL`；省略参数=保持当前值，不重置为默认） | 改配置 |
| `dg_set_param(ch, param, value)` | freq/amp/offset/phase/load 单参数设置并回读（设备钳制时返回 note） | 改配置 |
| `dg_set_dc(ch, level)` | DC 专用切换：设电平 + 返回切换前快照（切回时显式传参） | 改配置 |
| `dg_sweep(...)` / `dg_sweep_trigger(ch)` | 频率扫频配置/开关/查询 + 手动触发（限 sine/square/ramp/user） | 改配置 |
| `dg_output(ch, on, confirm)` | 输出开关；**开/关都需 confirm=True**；打开前需已开保护（库内联锁） | **confirm 必填** |
| `dg_counter()` | 内置频率计（[Counter] 输入口） | 只读 |
| `dg_query(scpi)` / `dg_check_error()` | 只读 SCPI 查询（纯查询消息） / 错误队列查询清空 | 只读 |
| `psu_status` | DH1766 状态总览（含电压/电流/模式 + safe/warnings 安全检查）| 只读 |
| `psu_mode` | 电源输出模式（NORM/TRAC/SERI/PARA，**操作前先查**） | 只读 |
| `psu_power_cycle(ch, expect_mode, cycles, off_delay_s, on_delay_s, confirm)` | 上下电循环（默认 1 次/延迟 1s）；**confirm 必填** | 改配置 |
| `psu_output(ch, on, expect_mode, confirm)` | 输出开关；**expect_mode 必填**（仅校验，不符拒绝）；**开/关都需 confirm=True** | **confirm 必填** |
| `psu_set_mode(mode)` | 电源模式设置（输出必须全关，库内强制） | 改配置 |

安全约定：复位类命令不暴露（instr_write 黑名单亦不放行）；**远程锁定类命令
（`SYSTem:REMote` / `SYST:REM` / `SYST:RWL` / `SYST:LOCK` / `:SYST:COMM:RLST`）
同样黑名单拦截**（纯查询形式放行，如 `SYST:REM?` / `SYST:COMM:RLST?`）；
关机/开输出/通用写必须 `confirm=True`；`instr_query` 只收纯查询消息、`instr_write` 的
`readback_cmd` 同受黑名单约束（2026-09-15 堵住从只读口/回读口走私复位与锁定命令）；
每次调用连接→操作→关闭（无状态）+ 全局锁串行化 +
通用写硬超时看门狗（离线资源不冻结 MCP）；错误统一
`{ok:false, error_type, error}` 分类返回。
DH1766 工具每次调用收尾自动补发 `SYST:LOC` 归还面板控制权——**任何远程会话都会把该电源
置为 REM**（2026-09-13 实测，见 dh1766_control/docs/EXPERIENCE.md §3.1）。

## 资源地址解析（**不写死 IP**）

仪器地址不是固定资产：DHCP 续租换 IP、换网段不可达、USB 换口换资源串、串口号漂移。
因此**专用工具的 `resource` 参数默认省略**（`resource=None`），server 端按
`common/resolver.py` 的优先级解析：

```
① 工具入参 resource                       显式指定（最高优先）
② 环境变量 INSTRUMENT_<KIND>_RES          如 INSTRUMENT_SDS_RES
③ 用户配置 devices.json                   长期固定部署写这里
④ 上次成功缓存 last_good_resources.json   instr_discover / 连接成功后自动回写
⑤ 自动发现 find_device(IDN)               只查 VISA 已注册资源（秒级）
                                          设 INSTRUMENT_ALLOW_SCAN=1 可放开扫网段
```

| kind | 设备 | 环境变量 | IDN 匹配串 |
|---|---|---|---|
| `sds` | Siglent SDS800X HD 示波器 | `INSTRUMENT_SDS_RES` | `SDS` |
| `sdg` | Siglent SDG2000X 信号源 | `INSTRUMENT_SDG_RES` | `SDG` |
| `dmm` | Keysight 34465A 万用表 | `INSTRUMENT_DMM_RES` | `34465A` |
| `dho` | RIGOL DHO800/900 示波器 | `INSTRUMENT_DHO_RES` | `DHO` |
| `mho` | RIGOL MHO900 系列示波器 | `INSTRUMENT_MHO_RES` | `MHO` |
| `dg` | RIGOL DG800 系列信号源 | `INSTRUMENT_DG_RES` | `DG8` |
| `psu` | DH1766 三路电源 | `INSTRUMENT_PSU_RES` | `DH1766` |

配置/缓存目录：`%LOCALAPPDATA%\instrumentControl\`（非 Windows 退 `XDG_CACHE_HOME` / `~/.cache`）。
配置值**一律是完整 VISA 资源串**（TCPIP / USB / ASRL / GPIB 同一形态，不区分传输方式）：

```json
{ "sds": "TCPIP0::<host>::inst0::INSTR",
  "dho": "TCPIP0::<host>::5555::SOCKET",
  "mho": "TCPIP0::<host>::inst0::INSTR",
  "psu": "USB0::0x0957::0xA007::<serial>::INSTR" }
```

> **不要自己拼 `IP:端口`**：协议/端口/参数因设备而异（DH1766 只认 raw 5025、
> DHO 只认 5555、SDS/SDG/DMM 走 inst0、USB 还需 vid/pid/serial）。需要从裸 host 起时，
> 用下面的 `set <kind> <host>`——它先探测协议再核对 `*IDN?`，只把规范串落盘。

维护方式（CLI 只读写本机文件；`set <host>` 形式会做一次只读探测，其余命令不连设备）：

```bash
python mcp_instruments/config_cli.py show              # 当前解析链与来源
python mcp_instruments/config_cli.py init [--force]    # 生成模板
python mcp_instruments/config_cli.py set sds "TCPIP0::<host>::inst0::INSTR"   # 完整串：直接写
python mcp_instruments/config_cli.py set sds 192.168.31.220                   # 裸 host：探测+校验后写规范串
python mcp_instruments/config_cli.py autofill [kind…]  # 把发现结果固化成配置（不联网）
python mcp_instruments/config_cli.py clear sds         # 删除条目 → 回落自动发现
```

**连接后核对 `*IDN?`**：若配置/缓存里的地址已被 DHCP 分给别的设备，工具会报
"地址校验失败…"并拒绝操作（不会把 SCPI 发给未知设备），此时重新 `instr_discover`
或用 `config_cli.py set` 更正即可。

换网段/换口后：先调一次 `instr_discover`（返回体里 `resolved` 是当前解析表、
`recognised_now` 是本次识别并写入缓存的设备），之后照常调用各工具。
工具报"未确定 XX 的资源地址"时，按报错文案给的三条路径处理即可
（`instr_discover` / 设环境变量 / 写 `devices.json`）。
`instr_query` / `instr_write` 是通用工具，**`resource` 必填**（面向任意设备，不能猜）。

## 依赖

pyvisa（完整版 NI-VISA）+ mcp 包；项目根在 sys.path（server.py 自行处理）。
