# DH1766 控制经验总结

实测环境：Windows 10 Pro + Python 3.11 + pyvisa 1.13（厂商 VISA `C:\Windows\system32\visa32.dll`）
设备：北京大华 DH1766A-1，固件 V0.1.4.3，USB TMC：`USB0::0x0957::0xA007::100260004670::INSTR`
实测日期：2026-08-17（全功能验证 40/40 PASS，留痕见 `TEST_DATA/dh1766/dh1766_full_*.json`）

## 1. Windows 平台访问约束（重要）

- **禁止用 pyusb/libusb 直接访问仪器**。Windows 上 libusb 打开设备需要 WinUSB/libusb 驱动，
  未安装时抛 `NotImplementedError: Operation not supported or unimplemented on this platform`（实测踩坑）。
- **一律走 VISA**：pyvisa 加载厂商 `visa32.dll`（NI-VISA 或 Keysight IO Libraries 安装），
  USB TMC 设备经 `USB0::0x0957::0xA007::<serial>::INSTR` 访问，无需任何 USB 驱动开发。
- 串口设备走 `ASRL::INSTR`，同样 VISA 统一处理。
- 检测后端：`pyvisa.ResourceManager().visalib` 输出 DLL 路径。

## 2. 设备识别

- VID 0x0957 是 **Keysight** 的 ID —— DH1766A 伪装之以便用 Keysight VISA 驱动，属国产仪器常见做法。
  **不要以 VID/PID 判定设备身份，以 `*IDN?` 为准。**
- `*IDN?` = `BJDH,DH1766A-1,0,V0.1.4.3`（IEEE 488.2 四字段：厂商,型号,序列号,版本）。
  BJDH = 北京大华（Beijing DHTECH）。
- Windows 设备类 `USBTestAndMeasurementDevice`（友好名 "USB Test and Measurement Device (IVI)"）。

## 3. 固件差异（V0.1.4.3 vs 手册基于的 V0.1.2.8）

| 命令 | 手册声称 | 实测 | 处理 |
|---|---|---|---|
| `VOLT:MODE?` / `CURR:MODE?` | 返回 FIX\|LIST | 返回**空串** | 驱动返回 None，写正常 |
| `INIT:DEL?` / `INIT:SOUR?` | 返回数值/枚举 | 返回**空串** | 驱动返回 None，写正常 |
| `SYST:COMM:RLST:STAT?` | 返回 LOC/REM/RWL | 返回**空串** | 驱动返回 None |
| `*PSC 1` | 设置上电清零策略 | 写后查询仍 0 | 固件行为，写不报错即可 |
| `OUTP:TIM:DATA 0` | 0 秒为关闭定时器（手册 4.2.8 第 9 条） | **写 0 被静默忽略**（保持原值、错误队列无报错）；写 1~999999 正常生效 | 固件 V0.1.4.3 无法用 SCPI 关闭定时器；定时功能开关（Off Timer On/Off）仅面板 3.11/3.9 节可操作 |
| `*RST` | 复位参数 | **设备软复位**：约 3s 就绪，期间查询返回开机横幅 `V0.1.4.3`；复位后设定回出厂值（32V/32V/6V、3A/3A/3A、TIM=1s） | 驱动内置 3s 等待；使用前必须完整备份 |
| `*TST?` / `*WAI` | IEEE 488.2 必需 | 手册 4.2.10 未列出 | 未封装 |

## 4. 时序规范（手册 4.1，实测必需）

| 操作 | 最小间隔 |
|---|---|
| 一般指令 | ≥100ms |
| 通道切换（INST:NSEL 等） | ≥300ms |
| 串并联/跟踪模式（继电器机械动作） | ≥500ms |

**踩坑案例**：裸 `write()` 连续下发无间隔（如 `APPL:VOLT` 紧跟 `APPL:CURR`），
导致**响应错位** —— `APPL:VOLT?` 读到上一查询的响应、查询返回错位值。
所有写操作必须带间隔（驱动已内置 `CMD_DELAY_S`），恢复类脚本务必用驱动封装而非裸命令。

## 5. 数值处理

- **浮点回读**：设备返回二进制浮点（`12.1` → `12.099998`、`4.1` → `4.099995`），
  编程精度内（电压 <0.01%+20mV）。**比较必须用容差**（建议 1e-3），不能 `==`。
- **区分两类值**：`MEAS:*` = 回读（实际输出，空载≈0，天然零漂波动）；`VOLT?`/`APPL:VOLT?` = 设定值。
  恢复完整性比对时**跳过回读值**，只比对设定类。
- SCPI-99 §7.2：设备可舍入参数，**设值后必须查询验证实际值**。
- 查询 `VOLT? MAX` 可获取量程上限（CH1/CH2=32.5V，CH3 上限见手册）。

### 5.1 上电过渡态（2026-08-17 实测补充，带载场景）

**现象**：CH1 输出开启后 **0.5s** 立即读数：9.351V / 0.198A（明显偏离设定 12V）；
等待 **2s+** 后读数：11.99V / 0.353A，连读三次一致（0.3528/0.3529/0.3530A）。
期间未触碰任何设置，输出状态保持 ON。

**结论**：
- 输出开启瞬间存在上电过渡态（负载电容充电/初始化，CV 建立过程），
  **过早读数会得到错误值**，且电流从低到高（0.198A→0.353A）趋势明显；
- 稳定后电压回到设定值（偏差 0.01V，精度内），负载等效阻抗 ≈34Ω 工作正常；
- **规范：输出开启后延迟 ≥2s 再读数；或连续采样多次确认读数一致**。

**驱动封装**：`DH1766.measure_stable(samples=3, settle_s=2.0, interval_s=1.0)`
——先等待再采样，返回末次读数与全部采样序列（详见驱动 docstring）。

## 6. SCPI-99 合规要点

- 布尔：写接受 `ON|OFF|1|0`，查询返回 `0|1`（§7.3）。`APPL:OUTP?` 实测返回 `0,0,0`。
- 事件寄存器（`STATus:*?`/`*ESR?`/`*STB?`）**读取即清零** —— IEEE 488.2 标准行为（手册明示）。
- 命令失败查错误队列 `SYST:ERR?`（FIFO），错误码表见手册 4.2.1。
- 设备扩展命令（SCPI-99 无此标准，按手册实现）：`APPLy:*` 复合控制、`OUTP:TRAC/SERI/PARA` 模式、
  `INIT[:IMM] ON|OFF`、`*TRG` 带通道参数。
- 通道参数 `CH1|CH2|CH3`（`INST`）或 `1|2|3`（`INST:NSEL`）为设备自定义，非标准数字后缀。

## 7. 安全操作规范

- **safe_mode**（`DH1766(client, safe_mode=True)`）：目标通道输出 ON 时拒绝改设定（电压/电流/OVP/OCP/模式），
  防带载误操作。输出开关本身不拦截。接入负载后必须启用。
- **写操作备份-恢复模式**：备份→写→读确认→恢复→读确认，全过程留痕。
- **`*RST` 必须经用户明确允许**（2026-08-17 约定）：
  - 复位恢复出厂设定（32V/32V/6V、3A/3A/3A、TIM=1s），恢复范围含**蜂鸣器状态**（手册 3.8/3.9 Default Setting 列表⑥）；
  - SCPI **无 BEEP 开关命令**（`SYST:BEEP` 仅测试鸣叫一声，不改状态；开关仅面板 Config 菜单），复位后无法经 SCPI 核对蜂鸣器开关；
  - 自动化脚本默认跳过 `*RST`，需 `--allow-rst` 显式授权（test_dh1766_full.py）。
- `*RST` 前必须完整备份：`APPL:VOLT?`+`APPL:CURR?`+三路 `VOLT:PROT?`/`CURR:PROT?`+`OUTP:TIM:DATA?`+`INST:COUP:TRIG?`。
- 输出模式切换（TRAC/SERI/PARA）仅在**输出全关**时进行（继电器联动拓扑变化）。

## 8. 手册差异（DH1766 系列 vs DH1766A 系列）

两本手册指令集不同，**以设备型号为准**：
- `DH1766 系列`（2017 V1.5，43 页）：命令更标准（`[:SOURce]:VOLTage[:LEVel][:IMMediate][:AMPLitude]` 全路径），
  4.2.1 仅 `*IDN?`；无 APPLy 复合命令。
- `DH1766A 系列`（2018 V2.1）：命令简写（`VOLTage` 直接可用），新增 `APPLy:*` 复合命令、
  `VOLT:MODE`/`CURR:MODE`、`MEAS:POWer`、`INST:COUP:TRIG`、`OUTP:TIM:DATA`。
- 规格差异：DH1766（老款）约 11Kg、441.5mm 深；DH1766A-1 约 9Kg、371.5mm 深。
- 提取文档：`docs/DH1766 系列三路可编程直流电源用户手册.md`（read-pdf 完整提取，43 页）。
  速查：`docs/SCPI_COMMANDS_DH1766A.md`。

## 9. 工具链约定

- 测试脚本放 `TEST_SCRIPTS/<device>/`，输出留痕到 `TEST_DATA/<device>/`，**文件名带时间戳**防覆盖。
- 实测脚本模式：Phase A 只读快照 → Phase B 写验证（备份-恢复）→ Phase C 完整性比对 → JSON 留痕。
- 手册提取用 read-pdf skill（文本层 PDF 走 pdfmux+pdfplumber，缺层页自动 RapidOCR）。
- 留痕 JSON 含 before/after 快照与逐项结果，可回溯。
