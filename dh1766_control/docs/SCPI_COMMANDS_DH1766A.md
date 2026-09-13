# DH1766A SCPI 命令速查

来源：`DH1766A系列电源用户手册V2.1.pdf` 第四章《远程控制与指令集》（页 21-47，PDF 页码）。
设备实测：`BJDH,DH1766A-1,0,V0.1.4.3`（USB TMC：`USB0::0x0957::0xA007::100260004670::INSTR`）

> **地址说明**：上面这个 USB 资源串是**当时实测值**，换 USB 口/换机会变（LAN 地址同理，
> 会随 DHCP 漂移）。接入前先发现：`find_dh1766()` / `resolve("psu")` / `instr_discover`。

> 通讯要点（手册 4.1）：
> - USB 连接成功后可收发 SCPI；LAN 需配 IP、端口 5025（UDP/TCP Server）
> - 上位机下发指令间隔 **≥100ms**；涉及通道切换 **≥300ms**；串并联（继电器机械动作）**≥500ms**
> - 实测（固件 V0.1.4.3，2026-08-17，40/40 项验证通过）固件差异：
>   - `VOLT:MODE?` / `CURR:MODE?` / `INIT:DEL?` / `INIT:SOUR?` 返回**空串**（手册按 V0.1.2.8 编写）；写命令正常
>   - ~~`SYST:COMM:RLST:STAT?` 返回**空串**~~ →（2026-09-13 更正：该写法**无响应（超时）**，应改用 `SYST:COMM:RLST?`；且任何远程会话都会把电源置为 REM，发 `SYST:LOC` 交还面板控制权。详见 EXPERIENCE.md §3.1）
>   - `*PSC 1` 写入后查询仍返回 0（上电清零策略不反映），写不报错
>   - `*RST` 为设备软复位：约 3s 就绪，期间查询会收到开机横幅（如 `V0.1.4.3`）；复位后设定恢复出厂值（32V/32V/6V、3A/3A/3A、TIM=1s），使用前必须完整备份
>   - 连续裸命令无间隔会导致响应错位，务必遵守上述最小间隔（驱动已内置）

## 系统指令集（4.2.1）

| 命令 | 说明 |
|---|---|
| `SYST:ERR?` | 读取错误信息（错误码表见手册页 21-22） |
| `SYST:VERS?` | 查询软件版本号 |
| `SYST:BEEP` | 蜂鸣器测试 |
| `SYST:LOC` / `SYST:REM` / `SYST:RWL` | 本地 / 远程 / 远程锁定（Lock 键不可切回）。⚠ `SYST:REM` 属远程锁定类，MCP `instr_write` 黑名单拦截；`SYST:LOC` 用于交还面板控制权 |
| `SYST:COMM:RLST:STAT?` | 查询工作模式：LOC/REM/RWL —— ⚠ **本机 V0.1.4.3 实测无响应（超时）**，实际可用写法为 **`SYST:COMM:RLST?`**（2026-09-13 实测；任何远程会话均返回 `REM`，发 `SYST:LOC` 后返回 `LOC`） |

## 输出通道设定（4.2.3）

| 命令 | 说明 |
|---|---|
| `INST CH1\|CH2\|CH3` | 选择操作通道（也可用 `INST:NSEL 1\|2\|3`） |
| `INST?` / `INST:NSEL?` | 查询当前通道 |
| `INST:COUP:TRIG CH1,CH2,CH3` | 设置组合通道（输出关断时联动设定） |

## 电压指令集（4.2.4）

| 命令 | 说明 |
|---|---|
| `VOLT <value>` | 设定当前通道电压（V） |
| `VOLT?` | 查询电压设定值（可带 MAX/MIN） |
| `VOLT:MODE FIX\|LIST` | 设定电压模式 |
| `VOLT:PROT <value>` | 设定过压保护值（V） |
| `VOLT:PROT?` | 查询过压保护值 |

## 电流指令集（4.2.6）

| 命令 | 说明 |
|---|---|
| `CURR <value>` | 设定当前通道电流（A） |
| `CURR?` | 查询电流设定值（可带 MAX/MIN） |
| `CURR:MODE FIX\|LIST` | 设定电流模式 |
| `CURR:PROT <value>` | 设定过流保护值（A） |
| `CURR:PROT?` | 查询过流保护值 |

## 输出指令集（4.2.7）—— 开关通道

| 命令 | 说明 |
|---|---|
| `OUTP ON\|OFF` | 打开/关闭**当前通道**输出（先 `INST:NSEL n` 选通道） |
| `OUTP?` | 查询当前通道输出状态，返回 0/1 |
| `OUTP:TRAC ON\|OFF` | 跟踪模式开关（CH2 跟随 CH1 输出同等值负电压，见手册 §3.8） |
| `OUTP:SERI ON\|OFF` | 串联模式开关 |
| `OUTP:PARA ON\|OFF` | 并联模式开关 |
| 三模式互斥 | 实测 2026-09-08：开一路自动清零其余两路，全程无错误；库 `output_mode()` 返回 NORM/TRAC/SERI/PARA，`set_output_mode()` 统一设置（含回读比对） |
| `OUTP:TIM:DATA <sec>` | 输出定时器（0=关闭） |

## 测量指令集（4.2.8）—— 读电压电流

| 命令 | 说明 |
|---|---|
| `MEAS:VOLT?` | 回读当前通道电压（V） |
| `MEAS:VOLT:ALL?` | 回读三路电压：`v1,v2,v3` |
| `MEAS:CURR?` | 回读当前通道电流（A） |
| `MEAS:CURR:ALL?` | 回读三路电流：`i1,i2,i3` |
| `MEAS:POW?` / `MEAS:POW:ALL?` | 回读功率（W） |

## 复合控制命令（4.2.9）—— 三路一次搞定

| 命令 | 说明 |
|---|---|
| `APPL:VOLT v1,v2,v3` | 同时设定三路电压 |
| `APPL:VOLT?` | 同时读取三路电压设定值 |
| `APPL:CURR i1,i2,i3` | 同时设定三路电流 |
| `APPL:CURR?` | 同时读取三路电流设定值 |
| `APPL:OUT s1,s2,s3` | ⚠ 不存在：`APPL:OUT ...` 报 -113（命令头无），`APPL:OUTP ...` 报 -200（查询专用不可写）——V0.1.4.3 无三路联动开关，库内 `set_output_all` 按单通道循环实现 |
| `APPL:OUTP?` | 同时读取三路输出状态，如 `0,0,0` |

## IEEE-488 子系统（4.2.10）

| 命令 | 说明 |
|---|---|
| `*IDN?` | 设备标识：`DHTECH,DH1766A-1,0,V0.1.2.8`（实测 BJDH 前缀） |
| `*CLS` / `*ESE n` / `*ESR?` | 状态寄存器 |
| `*OPC` / `*PSC` / `*RST` / `*SRE` / `*STB?` | 同步/复位/状态 |

⚠ **`*RST` 必须经用户明确允许**：复位恢复出厂设定（含蜂鸣器状态），SCPI 无 BEEP 开关命令可事后核对；自动化脚本默认跳过（见 EXPERIENCE.md §7）。


## 触发指令集（4.2.5）

| 命令 | 说明 |
|---|---|
| `INIT[:IMM] ON\|OFF` | 初始化列表状态 |
| `INIT:DEL <sec>` / `INIT:SOUR BUS\|IMM\|EXT` | 触发延时 / 触发源 |
| `*TRG` | 触发列表运行（可带 CH1\|CH2\|CH3\|ALL） |

## 状态寄存器位定义（手册页 47-49）

- INST 子寄存器 bit0-15：CAL/UNR/CV/CC/LIST/TIMER/OVP/OCP/SOFT OVP/SOFT OCP/PS/VSET DAC ERR/ISET DAC ERR/OVSET DAC ERR/OCSET DAC ERR/COMM ERR
- 查询状态寄存器 bit1-5：OT CH1/OT CH2/RT1/RT2/FAN ERR；bit13 INST
- 状态字节 bit1-7：PRO/QMA/QES/MAV/ESR/SRQ/OPS

## 规格速览（第五章，DH1766A-1）

| 项 | CH1/CH2 | CH3 |
|---|---|---|
| 额定输出 | 0~32V / 0~3A | 0~6V / 0~3A |
| 编程精度（12 月） | 电压 <0.01%+20mV，电流 <0.05%+50mA | 电压 <0.03%+10mV |
| 编程分辨率 | 10mV / 1mA | 5mV / 1mA |
| 命令处理时间 | <10ms | |
