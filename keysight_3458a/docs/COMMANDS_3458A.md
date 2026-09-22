# 3458A 命令表（白名单 + 出处 + 实现状态）

> ## 2026-09-23 真机实测补充（本机 GPIB0::9，82357B + Keysight VISA）
>
> **接通方法（唯一可行组合，已落码）**：`ktvisa32.dll`（Keysight VISA 核心）+
> 先 `SetDllDirectoryW(<Keysight IO Libraries Suite>\bin)` 并预加载 `ioGPIB.dll` /
> `ioGpibIntfc.dll`，再 `viOpen("GPIB0::9::INSTR")`。
> 系统默认 `C:\Windows\System32\visa32.dll`（NI/IVI 壳）打开 GPIB 报
> `VI_ERROR_LIBRARY_NFOUND`——它的 GPIB 护照要 NI-488.2 或 32 位 Tulip 护照，本机都没有；
> SICL 的 `iopen` 在同一环境下抛 `0xE06D7363`。实现见
> `keysight_3458a/transport.py::KeysightVisaTransport` 与 `prepare_keysight_visa()`。
>
> **实测响应样例（这些查询都可用 → 推翻下面第 11 条"无回读命令"的旧判断）**：
> `ID?`=`HP3458A`；`ERRSTR?`=`0,"NO ERROR"`；`TEMP?`=`37.0`（数值，单位按 °C 采信）；
> `TARM?`=`4`(HOLD)/`1`(AUTO)；`TRIG?`=`1`(AUTO)/`4`(HOLD)；`NRDGS?`=`1, 1`；
> `NPLC?`=`10.0000000E+00`；`APER?`=`200.000000E-03`；`FUNC?`=`1, .1`（功能码+档位）；
> `RANGE?`=`.1`；`AZERO?`=`1`；`MEM?`=`0`；`OFORMAT?`=`1`；`MFORMAT?`=`4`；
> `INBUF?`=`1`；`END?`=`2`；`ISCALE?`=`1.00000000E+00`。
>
> **读数实测**：`TARM SGL,1` → `-2.43E-06`（0.43 s/次 @NPLC=10, 50 Hz）；
> 连续 3 次 mean≈`-2.16E-06`、sd≈`4.5E-08`（输入近零，100 mV 档）。
>
> **坑（实测）**：若 `TRIG?`=4(HOLD)（上次会话留下的挂起态），`TARM SGL,1` **永远不出数**
> （20 s 超时），必须先 `TRIG AUTO`。参考实现的 `reset()` 里 `RESET` 恰好把它复位成 AUTO，
> 所以此前未暴露。本库用 `prepare_for_read()` 显式补上，**不发 RESET**。
> 现场还实测到一次"上次会话把表留在 free-run"（持续吐读数）——已按 `recover()` 处理。

本文件是 `keysight_3458a` 的**命令白名单登记簿**。`commands.py` 只允许出现下表里的命令；
新增命令必须先在**本文件**登记并写明出处（AGENTS.md 铁律 1「命令禁止猜测」）。

## 出处代号

| 代号 | 出处 |
|---|---|
| `[SICL]` | `D:\MyProjects\EmoeR_D\研发中项目\EmoeCalibrator\Software\cal_tool\dmm_sicl.py`（实战版 SICL 驱动，行号见下表） |
| `[VISA]` | 同目录 `cal_devices.py` 的 `DMM3458A_VISA`（pyvisa 版） |
| `[SAMPLE]` | `…\EmoeCalibrator\3458\python3458A-100k\python3458A_100k.py`（Keysight 官方样例：100k rdg/s） |
| `[SAMPLE2]` | 同目录 `python3458A_10V_100NPLC.py` |
| `[TOOLS]` | 同项目 `Software\cal_tool\tools\tc_attrib_temp.py`、`tc_temp_sweep.py`——在 **3458A 会话**上查内部温度（`dmm._gpib.query("TEMP?")`） |
| `[AC]` | 同项目 `Software\cal_tool\ac_1khz_probe.py`、`ac_stability.py`、`ac_verify.py`——3458A 交流测量配方（`SETACV` / `ACBAND` / `ACV`） |
| `[TASK]` | 本项目任务书给出的命令——**参考实现与官方样例中均未出现**，一律标"未验证" |

> **重要**：`[SICL]`/`[VISA]`/`[SAMPLE]`/`[SAMPLE2]`/`[TOOLS]`/`[AC]` 六条都在真机上跑过
> （EmoeCalibrator 项目），是本库的"有出处"依据；`[TASK]` 只表示"任务书要求实现"，
> **不代表真机验证过**。

## 命令表

| 命令 | 参数 | 语义 | 出处 | 实现位置 | 状态 |
|---|---|---|---|---|---|
| `ID?` | — | 身份（3458A **没有** `*IDN?`；返回形如 `HP3458A`） | `[SICL]` L392-394、`[VISA]` L639-640 | `DMM3458A.idn()` | 已实现（真机跑过） |
| `ERRSTR?` | — | 读错误队列（**没有** `SYST:ERR?`）；形态 `<code>,"<message>"` | `[SAMPLE]` L39 | `DMM3458A.error_string()` / `is_error_clear()` | 已实现；**队列语义未核对** |
| `TEMP?` | — | 3458A **内部温度**读数 | `[TOOLS]` `tc_attrib_temp.py:96`、`tc_temp_sweep.py:135` | `DMM3458A.temperature()` | 已实现（参考项目真机跑过；**单位/精度待手册核对**） |
| `RESET` | — | 复位到开机测量配置（**不是** `*RST`） | `[SICL]` L320、`[VISA]` L569、`[SAMPLE]` L35 | `DMM3458A.reset()` | 已实现；**影响范围未核对** |
| `END ALWAYS` | — | 每次读数都置 EOI | `[SICL]` L325、`[VISA]` L571 | `reset()` 内 | 已实现 |
| `INBUF ON` | — | 打开输入缓冲（`TARM SGL` 配方的**前置条件**，否则占住 GPIB 总线） | `[SICL]` L326、`[VISA]` L575 | `reset()` 内 | 已实现 |
| `TARM HOLD` | — | 停止后续触发（free-run 的第一道闸） | `[SICL]` L318 | `recover()` / `reset()` / `close()` | 已实现 |
| `TARM SGL,1` | — | 触发**一次**读数并回值（命令不带问号） | `[SICL]` L370、`[VISA]` L615 | `read_dcv()` / `read_acv()` | 已实现（DCV 真机跑过） |
| `TARM SYN` | — | 同步触发（进入等待，由随后的读数取走） | `[SAMPLE]` L64 | `read_burst()` | 已实现（官方样例配方） |
| `TRIG HOLD` | — | 触发源保持（不自动重触发） | `[SICL]` L319、`[SAMPLE2]` L48 | `recover()` / `reset()` | 已实现 |
| `TRIG AUTO` | — | 自动触发（数字突发配方里用） | `[SAMPLE]` L56 | `read_burst()` | 已实现 |
| `DCV <range>` | 档位 V | 直流电压档位 | `[SICL]` L333、`[VISA]` L581 | `configure_dcv()` / `set_range()` / `read_burst()` | 已实现 |
| `NPLC <n>` | PLC 倍数 | 积分时间（越大越准越慢） | `[SICL]` L334、`[VISA]` L582 | `configure_dcv()` / `set_nplc()` | 已实现；**AC 下语义未核对** |
| `ACV <range>` | 档位 V | 交流电压档位 | `[AC]` `ac_stability.py:59` 一带 | `configure_acv()` | 已实现（参考项目真机跑过；**AC 配方细节待核对**） |
| `SETACV ANA` | — | 交流转换方式：模拟（>10 Hz 用） | `[AC]` `ac_1khz_probe.py:84`、`ac_verify.py:130` | `configure_acv()` | 已实现 |
| `SETACV SYNC` | — | 交流转换方式：同步采样（<10 Hz 用） | `[AC]` `ac_stability.py:55`、`ac_verify.py:125` | `configure_acv()` | 已实现 |
| `ACBAND <lo>,<hi>` | Hz | 交流带宽（显著影响起伏/噪声） | `[AC]` `ac_1khz_probe.py:85`、`ac_verify.py:133` | `configure_acv()` | 已实现 |
| `PRESET DIG` | — | 数字表预设（整组采样参数复位到数字档） | `[SAMPLE]` L43 | `read_burst()` | 已实现（官方样例配方） |
| `MFORMAT SINT` | — | 内存格式 = 2 字节有符号整数 | `[SAMPLE]` L45 | `read_burst()` | 已实现 |
| `OFORMAT SINT` | — | 输出格式 = 2 字节有符号整数 | `[SAMPLE]` L46 | `read_burst()` | 已实现 |
| `MEM OFF` | — | 关读数内存（数据直接走总线） | `[SAMPLE]` L49 | `read_burst()` | 已实现 |
| `TIMER <s>` | 秒 | 采样间隔 | `[SAMPLE]` L48 | `read_burst(sample_interval_s=…)` | 已实现 |
| `APER <s>` | 秒 | 孔径时间 | `[SAMPLE]` L47、`[SAMPLE2]` L52 | `read_burst(aperture_s=…)` | 已实现 |
| `NRDGS <n>` | 个数 | 一次触发的读数个数 | `[SAMPLE]` L55 | `read_burst(n)` | 已实现 |
| `ISCALE?` | — | 查询 SINT 读数的换算因子（V/LSB），真值 = 整数 × ISCALE | `[SAMPLE]` L59 | `read_burst()` | 已实现 |

**档位全集**：`0.1 / 1 / 10 / 100 / 1000` V；10V 档有 20% 超量程（可用到 ±12V，`[VISA]` L594）。

## 明确**不在**白名单（禁止添加）

`OHM` / `DCI` / `ACI` / `FREQ` / `AZERO` / `FUNC?` / `RANGE?` / `DCV?` / `NPLC?` /
`MATH` / `SRQ` / `TARM?` / `MEM` 系列 / `NDIG` / `DISP` 等——任务未授权，也没有参考实现
或官方样例佐证。需要时先与用户确认并补手册出处。

## 二进制突发（`read_burst`）配方与解析

逐条对应 `[SAMPLE]` L43-69：

```
PRESET DIG → [DCV <range>] → MFORMAT SINT → OFORMAT SINT
→ [APER <s>] → [TIMER <s>] → MEM OFF → NRDGS n → TRIG AUTO
→ ISCALE? → TARM SYN → 读 2n+2 字节
```

- 解析：**前 2n 字节**按 2 字节**大端有符号**整数切出 n 个，各自 × `ISCALE` 得电压；
- 样例固定多读 2 字节（`read_bytes(nrdgs*2+2)`）——**这 2 字节的含义未核对**（见下）；
- 字节数不足 **明确报错**，不返回截断数据（截断会解析出错位的"合理值"，比报错危险）。

## 待手册核对项（**未实现或标注"未验证"**）

真机可达后请逐条对照 3458A 手册（用户手册 + 编程手册）确认，并回填本表：

| # | 待核对项 | 现状 | 影响 |
|---|---|---|---|
| 1 | `TEMP?` 的单位（推测 °C）与是否需要温度选件；返回格式（纯数值还是带单位） | 参考项目 `[TOOLS]` 真机跑过（取第一个数值）；单位/选件未核对 | `ks3458a_status` 的 `temperature` 字段可信度 |
| 2 | `SETACV` 取值全集（除 `ANA`/`SYNC` 是否还有第三态） | 参考项目 `[AC]` 只用过 `ANA`/`SYNC`；全集未核对 | `ks3458a_acv(sync=…)` |
| 3 | `ACBAND` 的合法范围与默认值、单位是否只接受 Hz | 参考项目 `[AC]` 用过 `0.01,10` 等组合；范围/默认值未核对 | AC 带宽设置 |
| 4 | `ERRSTR?` 队列语义：是否每次弹一条、队列深度、如何清空（白名单无清空命令） | 未验证；`is_error_clear()` 只认错误码 0 | 错误排查的可靠性；多次调用是否耗尽队列 |
| 5 | `RESET` 的完整影响范围（档位/NPLC/功能/内存/触发/SRQ/`END`/`INBUF` 是否都复位） | `reset()` 已按参考实现补齐 `END ALWAYS` + `INBUF ON`，但复位范围未逐项核对 | `ks3458a_reset` 的破坏面 |
| 6 | 突发尾部 2 字节的含义（为何样例读 `2n+2`） | 未核对；本库只取前 `2n` 字节 | 末尾读数是否被丢弃 |
| 7 | `ISCALE?` 的返回精度/单位，是否随档位与 `PRESET DIG` 变化 | 未核对；按"取第一个数值"解析 | 突发电压的绝对精度 |
| 8 | `NRDGS` 的合法上限；`MEM OFF` 下超长突发是否会被设备截断 | 未核对；库层只设了本仓上限 `BURST_MAX_READINGS=1e6` | `ks3458a_burst(n=…)` 的可选范围 |
| 9 | AC 功能下 `NPLC` 的语义（`SETACV SYNC` 的积分含义是否同 DCV） | 未核对；`set_nplc()` 已标注 | AC 测量的正确用法 |
| 10 | AC 下单次读数的配方是否同为 `TARM SGL,1` | **未实测**（参考实现只有 DCV 路径）；`read_acv()` 沿用同一配方 | 库 `read_acv()`；MCP 暂未暴露 |
| 11 | 是否存在档位/NPLC 回读命令（`DCV?`/`RANGE?`） | 白名单里没有 → 驱动只能记录"下发过什么" | `ks3458a_status.tracked` 的语义（**非实测值**） |
| 12 | `APER` 与 `NPLC` 的互斥/优先关系（34465A 上二者互斥） | 未核对；本库不强制互斥 | 数字档之外的孔径设置 |
| 13 | 手册 TARM 章节所述"抑制 CR LF"的等价做法（本库只做 `INBUF ON` + LF 终止符） | 已按 `[VISA]` L572-576 实现，未逐字核对手册 | GPIB 是否会再次被占住 |
