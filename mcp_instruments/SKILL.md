---
name: instrument-mcp
description: instrument MCP 服务器使用指引 — 七台仪器（SDS 示波器/SDG 信号源/Keysight 34465A 万用表/DHO 示波器/MHO900 示波器/DG832 信号源/DH1766 电源）的 MCP 工具选择、参数语义、安全门、典型工作流。触发条件：使用 instrument MCP 工具、sds_/sdg_/dmm_/dho_/mho_/dg_/psu_ 前缀工具、仪器测量/定标/截图/关机决策。
---

# instrument MCP 使用指引

MCP server：`mcp_instruments/server.py`（50 工具 = 46 专用 + 3 通用护栏 + 1 故障兜底，七台设备）。
本文是 AI 选择工具/参数时的决策依据。DG832 的详细 SOP/踩坑见 skill `dg832-control`。

## 一、工具选择决策树

```
需要知道有哪些设备在线？
  → instr_discover（LAN 网段 + USB/GPIB/串口全探测；串口被占用给提示，
    驱动挂起 6s 硬超时；代理 fake-IP 干扰 LAN 时降级 warning 不影响 VISA 结果；
    串口换号/新设备进场后用它重新定位）

新设备 / 无专用库的设备 / 库里没有的能力？
  → instr_query + instr_write（对照手册直发 SCPI，零代码接入，见下方"通用护栏"）

示波器（SDS）：
  看波形显示是否正常 → sds_diagnose（触发链路）→ 异常则 sds_auto_scale
  读测量值 → sds_measure（item 见下）
  判断削顶/居中/有无波形 → sds_screenshot（返回 PNG 路径，**直接 Read 即可看图**；
  设备测量值超屏被钳制不可信，截图是物理真相）
  测量判据/统计/门限 → sds_meas_threshold / sds_meas_statistics / sds_meas_gate
  延迟测量/显示策略 → sds_meas_dtime / sds_meas_display
  全量状态 → sds_status

信号源（SDG）：
  设波形 → sdg_set_wave（不动输出开关）
  开/关输出 → sdg_output（**开/关都需 confirm=True**，expect_load 必填）
  看当前配置 → sdg_status

万用表（DMM）：
  测量 → dmm_measure（先 dmm_configure 设功能/量程更稳）
  看配置 → dmm_status

DHO 示波器 → dho_status / dho_measure_item

MHO900 示波器（MHO984D 实测基准）：
  全量状态 → mho_status（注意采样率随开启通道数下降：1~2ch 4GSa/s、3~4ch 1GSa/s）
  读测量值 → mho_measure_item（单信源 VPP/VMAX/VAVG/VRMS/FREQuency…；
    双信源延迟/相位 RRDelay/RFDelay/FRDelay/FFDelay、RRPHase/RFPHase/FRPHase/FFPHase 需 ch2）
  判断削顶/居中/有无波形 → mho_screenshot（返回 PNG 路径，**直接 Read 看图**）
  读波形 → mho_get_waveform（NORMal 1~1000 点最常用；RAW 内存波形需先 mho_acquisition("stop")）
  无波形且确认"信号简单周期 + 无他人在用通道" → mho_autoset(confirm=True)（**全局破坏性**）

DG832 信号源（RIGOL DG800 系列）：
  **强制流程（顺序不可变）**：dg_status 查现状 → dg_protect 开电压保护（state=True 且 high>low）
    → dg_set_wave/dg_set_param 设参数 → dg_output(on,confirm=True) 开输出 → dg_check_error
  看现状 → dg_status（波形/频率/幅度/偏移/输出/负载）
  设波形 → dg_set_wave（省略参数=保持当前值；amp/offset 需已开保护，否则 protect_required）
  单参数 → dg_set_param（freq/amp/offset/phase/load；设备钳制时返回 note）
  DC 电平 → dg_set_dc（返回切换前快照 restore，切回时**显式**传参）
  扫频 → dg_sweep / dg_sweep_trigger（仅 sine/square/ramp/user）
  开关输出 → dg_output（**开/关都需 confirm=True**）
  诊断 → dg_query（纯查询 SCPI）/ dg_check_error

电源（DH1766）→ **psu_status（先查！含安全 warnings）** / psu_mode / psu_set_mode / psu_output / psu_power_cycle
```

### 资源地址：专用工具的 `resource` 默认不传

仪器地址**不是固定资产**（DHCP/换网段/换 USB 口/串口号漂移），**不要**在任何地方
把具体 IP 当成设备资源记住或写死。专用工具的 `resource` 参数默认省略，server 端按
`显式入参 > 环境变量 INSTRUMENT_<KIND>_RES > 用户配置 devices.json > 上次成功缓存 > 自动发现`
解析（`common/resolver.py`）。

- 工具报"未确定 XX 的资源地址"→ 先跑一次 **`instr_discover`**（结果按 `*IDN?` 自动记住），
  再重试原工具即可；也可让用户设 `INSTRUMENT_<KIND>_RES` 或写 `devices.json`
  （本机默认地址：`python mcp_instruments/config_cli.py set <kind> <resource>`）。
- **地址一律用完整 VISA 资源串**（`TCPIP0::…::inst0::INSTR` / `USB0::…::INSTR` /
  `ASRL5::INSTR` 同一形态，不区分传输方式），**不要自己拼 `IP:端口`**——协议/端口/
  参数因设备而异，拼错就是对未知设备发 SCPI。只有用户明确给出某台设备的 IP/host 时，
  才用 `config_cli.py set <kind> <host>` 让工具探测协议并核对身份后落库。
- 工具报"**地址校验失败**"→ 该地址上的设备 `*IDN?` 与目标不符（DHCP 把旧 IP 分给了
  别的设备）。**不要重试硬连**，先 `instr_discover` 重新定位，或让用户更正 `devices.json`。
- `instr_discover` 的返回体里 `resolved` = 当前解析表、`recognised_now` = 本次识别的设备、
  `psu_local_restored` = 是否已把 DH1766 面板控制权归还现场。
- 只有通用工具 `instr_query` / `instr_write` 必须显式给 `resource`（面向任意设备，不能猜）。

## 一.五、通用护栏工具（新设备零代码接入）

有专用库的设备优先用专用工具；以下用于骨架设备（如 emoe）、临时设备、
或库尚未覆盖的能力。命令语法必须先对照该设备手册/`commands.py`（铁律1），
**禁止猜测**——设备对不认识的命令静默不应答→超时（如 SDG 不支持
`C1:BSWV WVTP?` 单键查询，只支持整查 `C1:BSWV?`，见 sdg_control/commands.py）。

| 工具 | 用法要点 |
|---|---|
| `instr_query(resource, cmd, timeout_ms?)` | cmd 必须含 `?`；**问号后允许带参数**（`:MEASure:ITEM? VPP,CHANnel1`）；**可用 `;` 串联多段纯查询**（如 `:CHANnel4:DISPlay?;:CHANnel4:SCALe?`），但夹带写/复位/锁定会被拒；只读不留痕 |
| `instr_write(resource, cmd, readback_cmd?, confirm, timeout_ms?)` | **必须 confirm=True**；写前 drain、写后 SYST:ERR?、readback_cmd 给定即自动回读（铁律2/3）；每次调用含拒绝均落盘 `TEST_DATA/common/mcp_scpi_audit_*.jsonl` |

护栏语义：查询判据＝**逐段检查每段都是查询单元**（命令头以 `?` 结尾、问号后可带参数）——多段纯查询放行，夹带写命令即拒（SCPI 里 `;` 是同消息内的命令单元分隔符、设备逐个执行，实测写单元会生效）；原写法偶有歧义（不是"整条以 ? 结尾"——SCPI 允许问号后带参数）；复位/存储覆写类（`*RST`/`*SAV`/`*RCL`/`:SYST:RES|FACT|PRES`，长短形式均拦）
一律 `forbidden` 拒绝，confirm 也不放行（复位需显式授权场景走测试脚本）；
设备无响应有硬超时看门狗（≥30s），离线资源不会冻结 MCP；
串口(ASRL)按 9600 波特。

## 二、参数语义速查

| 工具 | 参数 | 语义 |
|---|---|---|
| sds_auto_scale | ch=1-4；use_autoset | **use_autoset=True 破坏性**（重置所有通道），仅简单周期信号+无其他已调通道时用；无信号/小信号时逐档重试最长约 60s，最终优雅报错 |
| sds_measure | item | SIMPle:ITEM 表 51 项：PKPK/MAX/MIN/AMPL/TOP/BASE/RMS/CRMS/MEAN/STDEV/MEDIAN/OVSP/OVSN/PER/FREQ/TMAX/TMIN/PWID/NWID/DUTY/NDUTY/RISE/FALL/EDGES/PPULSES...；ch=1-4 |
| sds_get_waveform | ch, points=50000, save_csv | 读通道波形（电压+时间轴，**FFT 交叉验证可信**）：返回摘要（点数/时间窗/Vpp/interval/档位），save_csv=True 存 CSV 到 TEST_DATA/common/ 并返回路径；**不返回完整数组**（防上下文爆炸）；分析频率用 FFT/自相关，朴素过零对调幅信号会误判 |
| sds_screenshot | resource（可省略） | 截屏存 PNG 并返回路径，**可直接 Read 读图**；看波形形态/削顶/居中/菜单/光标/测量栏；无视觉能力时用 analyze_screen 像素分析兜底 |
| sds_meas_threshold | source, thr_type, absolute, percent | 测量阈值源/类型/绝对值/百分比（边沿判据基础，手册 p.183-185）|
| sds_meas_gate | on, ga, gb | 测量门限：只统计 GA~GB 窗口内波形（p.179-180）|
| sds_meas_statistics | on, max_count, histogram, reset, slot, which | 统计开关/次数/直方图/重置；给 slot 查该槽统计（p.166-174）|
| sds_meas_dtime | index, edge1/2, slope1/2, threshold1/2 | 延迟测量 ΔTime 配置（p.176-178）|
| sds_meas_display | rdisplay, style, linenumber, strategy, astra_base/top | 结果显示样式/统计模式/幅值策略（p.174-181）|
| sds_measure_phase | src_a, src_b | 双通道相位差（度）= B 相对 A（PHA）；用后自动清槽恢复模式；两通道都要有完整周期（C1 无信号时正确报 device_error）|
| sds_measure | 无信号测 FREQ | 超时报 device_error（正常现象，非故障） |
| sdg_counter | on? | 内置频率计 FCNT（SDG2000X；SDG7000A 才是 :SENSe:COUNTer:*）；返回 FRQ/PW/NW/DUTY/FRQDEV 等；无信号 FRQ=0HZ |
| sdg_set_wave | wvtp | SINE/SQUARE/RAMP/PULSE/NOISE/DC；amp_v 高阻下即 Vpp |
| sdg_output | ch, on, **expect_load**, confirm | 输出开关；**expect_load 必填**（HZ/50Ω，仅校验，不符拒绝）；**开/关都需 confirm=True**（关闭可能打断测试/他人实验）|
| dmm_nplc | value? | 电压 DC 积分时间 NPLC（0.02/0.2/1/10/100，越大越准越慢）；无参查询，有参设置后回读 |
| dmm_measure | function | volt_dc/volt_ac/curr_dc/curr_ac/res/fres/cont/cap/diod/freq |
| dmm_configure | range_v | 设定量程后 :CONF? 回读滞后一拍，以实测为准 |
| dho_measure_item | item | RIGOL 长名：VPP/VMAX/VAVG/PERiod/FREQuency...；无值报 param_validation 错误（文案含 9.9E37）|
| mho_measure_item | item, ch, ch2? | 手册 3.17.2 表：单信源 VMAX/VMIN/VPP/VTOP/VBASe/VAMP/VAVG/VRMS/MARea/MPARea/PERiod/FREQuency/RTIMe/FTIMe/PWIDth/PDUTy/PPULses/PEDGes/ACRMs…；双信源 RRDelay/RRPHase 等需给 ch2；无有效值报错含 9.9E37（RIGOL 哨兵） |
| mho_get_waveform | ch, points=1000, mode, fmt, save_csv | NORMal **最多 1000 点**（超限报 param_validation）；RAW/MAXimum 可多但 RAW 必须已 STOP；fmt=BYTE/WORD/ASCii；voltage=(raw-YORigin-YREFerence)*YINCrement；RAW xinc 与采样率自洽（实测 5e-10s @2GSa/s） |
| mho_screenshot | resource? | `:DISPlay:DATA? PNG` 原生 PNG（**无需转码**），存 TEST_DATA/mho/ 并返回路径，可直接 Read 读图 |
| mho_acquisition | action=run\|stop\|single\|force | **stop 会冻结采集**（共享实验台上可能打断他人观察）；RAW 读内存波形前必须 stop，读完记得 run |
| mho_autoset | confirm | **全局破坏性**：重置**所有**通道档位/时基/触发；仅在"信号简单周期 + 无其他已调通道"时用 |
| dg_output | ch, on, confirm | 开/关都需 confirm=True；打开前需已开保护（库内联锁 protect_required） |
| dg_protect | ch, high, low, state | **设幅度/偏移或开输出前必须先开**（state=True 且 high>low）；越界设置报 protect_range，不静默超压 |
| dg_set_wave | shape, freq, amp, offset, phase, sample_rate | 各波形 `:APPL` 参数模板不同（DC/DUAL/PRBS 无 phase、NOISE/RS232 无 freq、SEQ 首参是采样率），库已按模板生成；频率上限随波形变（square/pulse 10MHz、ramp 1MHz）|
| dg_set_param | param, value | freq/amp/offset/phase/load；写后回读，设备钳制时 note 提示 |
| psu_status | — | **电源状态总览（操作前先调）**：三路电压/电流/功率/设定/OVP/OCP/输出/模式/耦合 + **safe/warnings** 安全检查（原 measure 与 pre_check 已并入）|
| psu_power_cycle | ch, expect_mode, cycles=1, off_delay_s=1.0, on_delay_s=1.0, confirm | 上下电循环（关→延迟→开→延迟）；**confirm 必填**（授权同输出开关）；放电不足时调大 off_delay_s（电容残留需 ≥6s）|
| psu_mode / psu_set_mode | mode | **操作电源前先查模式**：NORM/TRAC/SERI/PARA；TRAC 下 CH2 跟随 CH1 输出负压（非故障，手册§3.8）；切换前输出必须全关（库内强制）|
| psu_output | ch, on, **expect_mode**, confirm | 单通道输出开关；**expect_mode 必填**（仅校验，不符拒绝并回传实际模式）；**开/关都需 confirm=True**（关闭可能中断供电）|

## 三、安全门

| 工具 | 门 | 说明 |
|---|---|---|
| sds_shutdown | confirm=True | 设备离线需面板手动开机 |
| sdg_output（开/关） | confirm=True | 开=真实信号；关=可能打断测试/他人实验 |
| mho_autoset | confirm=True | 全局破坏性：重置所有通道/时基/触发（多信号台面慎用） |
| dg_output（开/关） | confirm=True | 开=真实信号输出；关=可能打断测试/他人实验 |
| dg_protect → set_wave/output | 库内联锁 | 未开有效电压保护时设 amp/offset 或开输出一律被拒（protect_required） |
| psu_output（开/关） | confirm=True | 开=真实电压；关=可能中断供电 |
| （未暴露）| — | 复位类命令一律不可用 |

### 输出关断的授权确认（重要纪律）

`confirm=True` 不是"我知道要关"就填——它代表**已获得关断授权**。满足以下之一才可关断：

1. **用户本轮明确要求关闭**该输出（如"把信号源关掉"），或**明确要求做上下电/上下电循环**；
2. **用户明确声明独占使用**："只有你在用这块供电/供信号的板子"、"没有别人在用"。

不满足时**不要关断**：实验台可能是共享的（同一电源可能给别人的板子供电、
同一信号源可能接在别人的测试链路里），贸然断电会打断正在进行的测试/实验。
需要关断但无授权时，**先向用户确认**再执行。

同理，`psu_output`/`sdg_output` 的 `expect_mode`/`expect_load` 也必须在**先查询
确认**后填写（`psu_mode`/`sdg_status`），不能凭记忆或猜测填——填错会被拒绝，
但正确做法是查了再填。

### 禁止远程锁定命令（面板保护）

**不要发送远程锁定类命令**：`:SYSTem:REMote ON`（SDS 实测：禁用触摸屏、前面板
按键和其他外设，界面显示 "Remote"）、串口/GPIB 通用的 `SYST:REM` / `SYST:LOCK`、
以及 **DH1766 的 `SYST:RWL`**（面板 Lock 键不可切回本地，需 `SYST:LOC` 恢复）
和标准形式 `:SYST:COMM:RLST <state>`（RWL 值同样锁面板）。

理由：实验台是共享的，锁定面板会妨碍人工操作（现场调试/检查往往需要直接按面板）。
SDS 的远程锁定**不是连接自动触发的**，是显式命令——所以只要不发就永远不锁
（2026-09-09 实测：连接+查询不改变 REM 状态；残留 ON 多来自 Web/noVNC 控制界面）。

- MCP `instr_write` 已黑名单拦截（`error_type=forbidden`，confirm=True 也不放行）；
  2026-09-13 补齐 `SYST:RWL` / `:SYST:COMM:RLST` 缺口；
- **纯查询放行**（`SYST:REM?`/`SYST:COMM:RLST?`）——纯查询不改变锁定状态，用于诊断；
- 若发现面板已被锁（`SYST:REM?` 返回 ON），提示用户用面板或 Web 界面退出远程模式。

### DH1766 特例："一连就进远程模式"（2026-09-13 实测）

DH1766 与 SDS 不同：**任何远程会话都会把电源置为 `REM`**——新建会话第一条命令查
`SYST:COMM:RLST?` 即返回 `REM`（手册写的 `SYST:COMM:RLST:STAT?` 在本机 V0.1.4.3
**无响应**，不是"返回空串"）。这是设备行为，不是锁定命令被误发。

- 发 `SYST:LOC` 立即回到 `LOC`（只交还面板控制权，**不影响输出/电压/模式**）；
- MCP 电源工具已内置：每次调用收尾自动补发 `SYST:LOC`（`server.py::_psu_close`），
  所以 AI 用过之后现场面板仍可用；
- 用 `psu_status` 前不必纠结 REM，它会如实回报当前模式（TRAC/SERI/PARA/NORM）。

## 四、典型工作流

**信号链验证**（SDG 输出 → SDS 测量）：
1. `sdg_set_wave(ch=2, wvtp="SINE", freq_hz=1000, amp_v=2)` 
2. `sdg_output(ch=2, on=True, expect_load="HZ", confirm=True)`
3. `sds_auto_scale(ch=4)`（信号接在 C4）
4. `sds_measure(item="PKPK")` + `sds_measure(item="FREQ")` 断言
5. 结束 `sdg_output(ch=2, on=False, expect_load="HZ", confirm=True)`

**示波器无波形**：
1. `sds_diagnose` 看触发源/电平/模式
2. `sds_auto_scale` 修正
3. `sds_screenshot` → **Read 返回的 PNG 看图**确认（测量值超屏被钳制不可信）

**截图能力（2026-09-09 修复 alpha 后）**：
- `sds_screenshot` 返回 PNG 路径，**直接 Read 即可看图**（视觉判断最直观）
- 看得到：波形形态/有无信号/削顶/居中/面板菜单/光标读数/底部测量栏
- 与 SCPI 配合：截图看形态，SCPI 读精确数值
- 无视觉能力时用库 `analyze_screen()` 像素分析兜底（轨迹 Y 分布/削顶判定）

## 四.五、USB-TMC 卡死（故障兜底 `usb_reset`）

`*IDN?` 超时 / `VI_ERROR_TMO` / `VI_ERROR_SYSTEM_ERROR` 时：**先重连一次**（多数即恢复）；
仍不行 → `usb_reset(kind="dg", confirm=True, verify_idn=True)`（**重启该仪器的 USB
PnP 设备节点**：USB 重新枚举，**固件不重启、通道设定/输出/保护全部保留**，实测 2.4s）。
⚠ 该操作需**管理员权限**，而**MCP 进程不能自行提权、不会弹 UAC**：本机 zcode 里的
MCP 进程通常已带管理员（可直接用）；若工具报"需要管理员权限"，退出 MCP 走 CLI 提权：
`python common/usb_reset.py --kind dg --allow-reset --escalate --verify-idn`（弹 UAC）。
**不要**让人去拔插 USB，更不要给仪器断电（那是最后手段）。LAN 设备卡死不属此场景
（重连或换协议 inst0 ↔ raw socket）。

## 五、错误处理

统一返回 `{ok, error_type, error}`：
- `confirm_required`：补 confirm=True 重试
- `forbidden`：复位/存储覆写类，不可重试（不经 MCP，走测试脚本+显式授权）
- `param_validation`：改参数（枚举/范围错、查询缺 `?`）
- `connection`：设备离线（instr_discover 确认）
- `device_error`：设备拒绝/测量超时（读 error 文本，多为信号/触发问题）
- `communication`：IO 异常（重试一次，仍失败检查连接）
- `timeout`：调用超墙钟上限（默认 150s，可用 `INSTRUMENT_CALL_BUDGET_S` 调）——
  设备离线/总线挂起；**命令可能已下发**（写操作请回读确认）
- `device_busy`：设备锁被占超 `INSTRUMENT_LOCK_WAIT_S`（默认 30s），通常是**上一
  次调用挂在某台离线设备上还没释放**。本次**未向任何设备下发命令**；重试多半无效，
  正解是重启 MCP 服务（或等那个挂起调用自己超时）

### 超时/卡死语义（所有 50 个工具一致）

- 每个工具调用都有**墙钟看门狗**：专用工具 150s、通用工具按 `timeout_ms` 推算
  （下限 30s），预热期再放宽 90s；
- 设备锁用**限时获取**：等不到就报 `device_busy`，不会无限排队（旧版会全体卡死，
  连救火的 `instr_discover` 都进不来）；
- 看门狗**不释放设备锁**（Python 无法中断持锁线程）。所以某次超时后，服务器进入
  "快速失败"模式：所有调用立即报 `device_busy`，直到重启。这是有意的取舍——
  宁可明确报错，也不让整个服务假死。
- 串口探测在**子进程**里做：某些串口会让驱动层 open 永久挂起，在本进程里探测会
  留下卡死线程、导致**之后任何 VISA 调用都把服务器进程打死**（2026-09-15 实测）。
  子进程超时可杀，卡住的句柄随之消失。
