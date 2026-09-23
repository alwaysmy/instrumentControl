# keysight_3458a — HP/Keysight 3458A 八位半万用表控制库

**专用实现**：3458A 不是标准 SCPI 仪表，本库**不套** `common/visa_client.py` 的 SCPI 假设，
也不走 `instr_query` / `instr_write` 通用护栏（那两条面向 SCPI）。

与 34465A（`keysight_3446x`）的语法差异：

| 用途 | 3458A | 标准 SCPI（34465A） |
|---|---|---|
| 身份 | `ID?` | `*IDN?` |
| 错误 | `ERRSTR?` | `:SYST:ERR?` |
| 复位 | `RESET` | `*RST` |
| 单次读数 | `TARM SGL,1`（触发后**直接回值**） | `:MEAS:VOLT:DC?` |
| 档位 / 积分 | `DCV <range>` / `NPLC <n>` | `:CONF:VOLT:DC` / `:SENS:VOLT:DC:NPLC` |
| 档位回读 | **没有**（只能记录下发值） | `:CONF?` |
| 串尾 | **必须 LF**（CRLF 不应答） | 因设备而异 |

## 用法

```python
from keysight_3458a import DMM3458A, find_3458a

hit = find_3458a()                     # 逐个候选探测，用 ID? 核对身份（地址不写死）
print(hit["resource"], hit["idn"], hit["transport"], hit["tried"])

with DMM3458A(hit["resource"]) as d:   # 连接即做会话恢复（见下）
    print(d.idn())                     # HP3458A
    print(d.error_string())            # ERRSTR?
    d.configure_dcv(10.0, 10.0)        # 10V 档 / 10 PLC（自动丢弃首读数）
    print(d.read_dcv())                # 单次 DCV
    print(d.read_stats(10))            # {n, mean, stddev, min, max}

    burst = d.read_burst(1000, sample_interval_s=10e-6, dcv_range=10.0)
    print(burst["summary"])            # 100k rdg/s 二进制突发的统计
```

直接给地址（**不要写死 IP**，地址随环境变——见 `common/resolver.py`）：

```python
DMM3458A("visa://<host>/GPIB0::9::INSTR")   # 远端 VISA server
DMM3458A("GPIB0::9::INSTR")                 # 本机 VISA/GPIB 卡
DMM3458A("sicl:gpib0,9")                    # 本机 Keysight SICL
```

命令行/脚本里用解析层固定地址（键名 `ks3458a`）：

```powershell
python mcp_instruments/config_cli.py set ks3458a "visa://<host>/GPIB0::9::INSTR"
$env:INSTRUMENT_KS3458A_RES = "sicl:gpib0,9"
```

## 进程外 worker（`remote.RemoteDMM` / `worker.py`）——**MCP 默认走这条**

```python
from keysight_3458a.remote import RemoteDMM
with RemoteDMM("GPIB0::9::INSTR") as d:
    print(d.idn(), d.read_dcv())
```

两个必须分进程的理由（2026-09-23 实测，详见 `docs/3458a_wedge_postmortem_20260923.md` §10）：

1. **两套 VISA 不能同进程**：MCP 长驻进程里别的仪器工具会用 pyvisa 加载**系统 VISA**
   （`C:\Windows\system32\visa32.dll`，IVI 壳）；此后本库的 Keysight ctypes 通路会串味——
   `viWrite` 报 `VI_ERROR_INV_OBJECT`，在 MCP 里更严重：`viOpen` **访问违例**
   （`access violation reading 0x8`）。两种加载顺序都坏，只能分进程。
2. **卡死可 kill**：`viOpen/viRead/viWrite` 若卡在 `ioGPIB` 内，同进程无法中断
   （超时/`finally` 都执行不到）；子进程超过 `deadline_s` 无响应 → `kill()` →
   Windows 强制回收句柄 → 下次调用自动重启 worker。

接口与 `DMM3458A` **同名**（`idn/state/read_dcv/read_series/read_burst/configure_dcv/
set_autorange/configure_acv/reset/unstick/...`），白名单见 `worker.ALLOWED_METHODS`；
协议是一行一条 JSON（`{"op":"call","method":...,"kwargs":{...}}`）。
回退开关：`INSTRUMENT_KS3458A_WORKER=0`（排障用，会把上面两个问题带回来）。
用例：`TEST_SCRIPTS/ks3458a/verify_worker_isolation.py`（6/6，含硬截止 kill 与自动重启）。

## 连通前的分层诊断（连不上时先跑这个，别猜地址）

```bash
python -m keysight_3458a.preflight            # 只读分层检查（不写设备）
python -m keysight_3458a.preflight --id       # 追加一条 ID?（通路完全正常的判据）
python -m keysight_3458a.preflight --recover  # 表被留在流数据时：文档化恢复（不发 RESET）
```

它在**子进程**里跑并带**看门狗**（默认 30 s 超时即 kill）——因为 `viOpen/viRead/viWrite`
一旦卡在 `ioGPIB` 内，同进程无法中断（见 `docs/3458a_wedge_postmortem_20260923.md`）。

分层判据与对应处置：

| 层 | 现象 | 处置 |
|---|---|---|
| [1] 驱动层 | `driver_missing` / `iolib_missing` | 装 **Keysight IO Libraries Suite**（别装 NI-488.2，不支持 82357B） |
| [2] 枚举层 | GPIB 资源为空 | **拔插适配器 + 打开 Keysight Connection Expert**，等 "Initializing" 消失（~20-30 s） |
| [3] 会话层 | `0xE06D7363` / `0xC0000005` | 适配器接口卡死：杀进程 → 重置适配器节点 → **重启整机**；不要反复重试 |
| [4] 应答层 | viRead 无数据（`RSRC_NFOUND`/`TMO`） | **物理侧**：3458A 是否上电、GPIB 电缆两端、面板地址=9 |
| [4] 应答层 | viRead 有数据 | 表被留在流数据 → `--recover` |
| [5] 身份层 | `ID?` -> `HP3458A` | 通路完全正常 |

**重启后的标准动作（2026-09-23 实测有效）**：重启系统 → 若仍连不上，**拔插 82357B +
打开 Keysight Connection Expert**（让它重新发现接口）→ 等适配器名字从
"`Keysight Technologies 82357B Initializing`" 变回 "`Keysight Technologies 82357B`"
→ 再跑 `preflight --id` 确认。

## 三条传输通路（`transport.make_transport` 按资源串自动选）

| 通路 | 资源串形态 | 实现 | 何时用 |
|---|---|---|---|
| **Keysight VISA（本机首选）** | `GPIB0::9::INSTR` | `KeysightVisaTransport`（ctypes 直调 **`ktvisa32.dll`**） | **本机 82357B USB/GPIB 的实测唯一可行通路**（2026-09-23） |
| pyvisa | `visa://<host>/GPIB0::9::INSTR`、USB、串口 | `PyVisaTransport` | 远端 VISA server，或本机 VISA 确实能打开 GPIB 时 |
| SICL | `sicl:gpib0,9`、`gpib0,9` | `SiclTransport`（ctypes 直调 `sicl32.dll`） | 装了 Keysight IO Libraries 且 SICL 可用时（EmoeCalibrator 现场用的就是它） |

### 本机接通方法（2026-09-23 实测，务必照做，否则报错很难懂）

`make_transport("GPIB0::9::INSTR")` 会自动调用 `prepare_keysight_visa()` 完成下面三步：

1. 读注册表 `HKLM\SOFTWARE\VXIPNP_Alliance\VXIPNP\CurrentVersion\VXIPNPPATH` 定位
   `<VISA base>\Win64\ktvisa\ktbin`；
2. **`SetDllDirectoryW(<Keysight IO Libraries Suite>\bin)`** —— `ioGPIB.dll` 的依赖按
   "当前目录/SetDllDirectory"解析，只 `os.add_dll_directory` 会 `FileNotFoundError`；
3. 预加载 `ioGPIB.dll`、`ioGpibIntfc.dll`，然后 `viOpen("GPIB0::9::INSTR")`。

**为什么不能用系统默认 VISA**：`C:\Windows\System32\visa32.dll` 是 NI/IVI 壳，它的 GPIB
护照需要 **NI-488.2** 或 **32 位 Tulip 护照**——本机都没有，于是报
`VI_ERROR_LIBRARY_NFOUND`；SICL 的 `iopen` 在同一环境下抛 `0xE06D7363`（同因）。
不要为此去装 NI-488.2（**不支持 82357B**）。

**读前准备**：`prepare_for_read()` 发 `END ALWAYS` + `INBUF ON` + **`TRIG AUTO`**。
实测：`TRIG?`=4(HOLD) 时 `TARM SGL,1` 20 s 超时；补 `TRIG AUTO` 后 0.43 s/次出数
（NPLC=10）。参考实现的 `RESET` 顺带把触发复位成 AUTO，我们为了**不动用户设定**不发 RESET。

两者实现同一套接口（`open/close/write/read/read_bytes/query/clear/drain/set_timeout/ifc`），
驱动只依赖接口，所以离线测试可以注入假传输。

**IFC 的差异**：`SiclTransport.ifc()` 发 GPIB 接口清除（`igpibpulseifc`，**整条总线**的设备
都会被打断）；VISA 通路退化为 Device Clear（VISA 无 IFC 等价物）。GPIB0 上只有这台 3458A
时可接受，共享总线上要注意。

## 已知坑（全部有实测出处，别"优化"掉）

1. **串尾必须 LF**：pyvisa 默认 `\r\n` 会让 3458A **不应答**（`[VISA]` L529-531 实测超时）。
   `PyVisaTransport` 在 open 时强制 `write_termination="\n"` / `read_termination="\n"`。
2. **`INBUF ON` 是 `TARM SGL` 配方的前置条件**（手册 TARM 章节要求）：不打开输入缓冲
   （或不抑制 CR LF），GPIB 总线会被占住。`reset()` 里已补发，且两侧都用 LF 终止符。
3. **free-run 的现场**：上次会话可能把表留在自由运行（持续吐读数、不理查询）。
   此时**先 drain 只会一直读到数据**——实测 91 s（`[SICL]` L273-276）。
   正确顺序：**先 IFC/clear 打断序列 → 有限 drain → TARM/TRIG HOLD**。
   本库 `connect()` 默认做这套恢复，`drain()` 硬上限 ≤6 轮 × ≤250 ms（无界 drain 实测 80~91 s）。
4. **换档/换配置后必须丢弃第一次读数**（`[SICL]` L339-341）：首读数含建立时间与自校准，
   不是有效值。`configure_dcv()` / `set_range()` / `configure_acv()` 内部已自动丢一次。
5. **10V 档有 20% 超量程（可用到 ±12V）**，但 `range_for()` 仍按 1.1 倍余量选档（保守）：
   11 V 会被选到 100 V 档。确知信号 ≤12 V 又要用 10V 档时直接 `configure_dcv(10.0)`。
6. **没有档位/NPLC 回读命令**：驱动只能记录"本会话下发过什么"（`current_range` /
   `current_nplc`，`None` = 没设过）。**不要**把它当设备实测值——标定/报告里要写清。
7. **连接会做会话恢复**：只发 IFC/clear + drain + TARM/TRIG HOLD，**不发 RESET、不改档位**；
   但它会打断设备上正在进行的采集（SICL 的 IFC 影响整条总线）。要"绝对不动现场"，
   用 `connect(recover=False)`。
8. **`read_burst` 会改配置**：`PRESET DIG` 把整组采样参数复位到数字档、功能切 DCV、
   内存关闭。它取数无副作用，但跑完设备不再是原来的配置。
9. **SICL 的 `iread` 不做块分帧、也不解码**：参考实现把字节 `decode('ascii','replace')`
   返回，SINT 读数里 >0x7F 的字节会被替换掉 → **突发数组全错**。本库的 SICL 通路
   `read_raw()` 返回 bytes，`read_bytes()` 自己剥 `#<位数><长度>` TMC 头。

## 目录

| 文件 | 作用 |
|---|---|
| `commands.py` | 命令常量 + **逐条出处**（本库的白名单） |
| `transport.py` | `PyVisaTransport` / `SiclTransport` + TMC 头处理 |
| `dmm3458a.py` | `DMM3458A` 驱动（连接/恢复/复位/配置/读数/突发） |
| `discovery.py` | `find_3458a()` / `candidate_resources()`（不写死地址） |
| `docs/COMMANDS_3458A.md` | 命令表（出处 + 实现状态）+ **待手册核对项** |

## 测试

离线（**不打开任何真实仪器**，用假传输 + 假 pyvisa）：

```powershell
python TEST_SCRIPTS/ks3458a/verify_3458a_offline.py        # 库行为 62 项断言
python TEST_SCRIPTS/ks3458a/verify_mcp_ks3458a_tools.py      # MCP 注册 14 项断言（只握手 + 门校验）
```

真机验证清单（设备可达后逐条跑）：`docs/3458a_integration_20260922.md`。
