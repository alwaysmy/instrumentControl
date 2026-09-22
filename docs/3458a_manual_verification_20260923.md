# 3458A 手册核对记录（2026-09-23）

**来源**：`E:\手册与技术支持\设备资料与文档\3458A\Ag_3458A_UserGuide_en.pdf`
（Agilent 3458A Multimeter User's Guide，374 页；命令条目页码 = PDF 页码，与目录页 8-11 的页码索引一致）。

**用途**：把 `keysight_3458a` 的命令白名单、数值码语义与边界逐条对照手册，关闭此前
`docs/COMMANDS_3458A.md` 里的"待手册核对"项，并留下引用页码备查。本文只记录手册口径与实测口径的
对齐结果，不替代手册。

---

## 1. 手册明确支持的查询约定（重要）

p.153「Additional Query Commands」：

> "In addition to the standard query commands, you can create others by **appending a
> question mark to any command** that can be used to configure or program the multimeter.
> (Query commands of this type are not documented individually in this chapter. Instead,
> they are combined with the parent command. That is, the AZERO command page contains
> information on both AZERO and AZERO?.)"

→ 本库 `state()` 用的 `TARM? / TRIG? / NRDGS? / NPLC? / APER? / FUNC? / RANGE? / AZERO? /
MEM? / OFORMAT? / MFORMAT? / INBUF? / END?` 全部属于这类查询，**合规**；
`ID? / ERRSTR? / TEMP? / ISCALE?` 等是手册单独列出的标准查询。

## 2. 数值码表（手册原值，逐条引用）

| 命令 | 码值 | 出处 |
|---|---|---|
| `TARM` | **1=AUTO**（always armed）、**2=EXT**、**3=SGL**、**4=HOLD**；上电/默认 = AUTO | p.251 |
| `TARM SGL,n` | n 有效范围 **0 – 2.1E+9**，仅对 SGL 事件有效；SGL **触发一次后自动回到 HOLD** | p.251 |
| `TRIG` | **1=AUTO**（"triggers whenever the multimeter is not busy"）、**2=EXT**、**3=SGL**（收到 `TRIG SGL` 触发一次后回 HOLD）、**4=HOLD**；上电=AUTO、**默认=SGL**；`TRIG?` 可查 | p.257 |
| `END` | 0=EOI never、**1=ON**、**2=ALWAYS**；上电=OFF、**默认=ALWAYS**；`END?` 可查；ASCII 读数以 **CR,LF** 结尾 | p.176 |
| `INBUF` | **ON=1**；上电=OFF、**默认=ON**；OFF 时"只接受一条命令、执行完才放总线" | p.186-187 |
| `OFORMAT` | **1=ASCII**、**2=SINT**、**3=DINT**、**4=SREAL**；上电/默认 = ASCII | p.210 |
| `MFORMAT` | **1=ASCII**、**2=SINT**、**3=DINT**、**4=SREAL**；上电/默认 = **SREAL**；执行会**清空读数内存** | p.198-199 |
| `AZERO` | ON / OFF / **ONCE**；上电 = ON；仅作用于 DCV/DCI/电阻 | p.162-163、p.26 |
| `MEM` | 上电 = OFF（"disable reading memory, last memory operation = FIFO"） | p.26、p.196 |
| `NPLC` | **0–1 PLC** 步进 0.000006（60 Hz）/ 0.000005（50 Hz）、**1–10 PLC** 步进 1、**10–1000 PLC** 步进 10；上电 = **10** | p.205、p.26 |
| `NRDGS` | `NRDGS [n][,event]`；**n 有效范围 1 – 16777215**；上电 = `1, AUTO`（event 码 AUTO=1） | p.207、p.26 |
| `ACBAND` | 指定**输入信号的频率含量**；上电 = `20, 2E6`（20 Hz – 2 MHz） | p.66、p.26 |
| `SETACV` | `SETACV [type]`，type = **analog / random / synchronous** …；上电 = **ANA** | p.233-234、p.26 |
| `APER` | 孔径时间（秒），数字/子采样通路用（模拟通路由 NPLC 决定） | p.60、p.114 |
| `ISCALE?` | 返回 **SINT/DINT** 格式读数的换算因子 | p.187 |
| `ERRSTR?` | 读**并清除**错误寄存器/辅助寄存器中**最低置位**的一位（100 系=错误寄存器、200 系=辅助寄存器），返回 `code,"message"`；需**反复查询**逐位清除；最长 255 字符 | p.178 |
| `TEMP?` | 内部温度，单位 **摄氏度**（"internal temperature in degrees Centigrade / Celsius"） | p.37、p.50 |
| 10 V 档超量程 | 手册以 **120% of range** 表述（10 V 档 → 12 V）；>120% 时应改用 **DINT** 内存/输出格式（SINT 会溢出） | p.136、p.138、p.173 |

**Table 5. Power-On State（p.26，完整上电状态，RESET 的归宿）** 摘录：
`ACBAND 20,2E6` · `AZERO ON` · `DCV AUTO` · `DEFEAT OFF` · `END OFF` · `INBUF OFF` ·
`LEVEL 0,AC` · `LFREQ 50 or 60` · `MATH OFF` · `MEM OFF` · `MFORMAT SREAL` · `MMATH OFF` ·
`NDIG 7` · **`NPLC 10`** · **`NRDGS 1, AUTO`** · `OCOMP OFF` · **`OFORMAT ASCII`** ·
`QFORMAT NORM` · `RATIO OFF` · **`SETACV ANA`** · `SLOPE POS` · `SWEEP 100E-9,1024` ·
**`TARM AUTO`** · `TBUFF OFF` · `TIMER 1` · **`TRIG AUTO`**。
（p.32：前面板 Reset 键"returns you to the power-on state"——即回到上表。）

## 3. 2026-09-23 真机实测 ↔ 手册默认值对照

| 实测读回 | 手册默认 | 结论 |
|---|---|---|
| `ID?` = `HP3458A` | — | 标准查询（条目 p.185） |
| `ERRSTR?` = `0,"NO ERROR"` | 无错时码 0 | ✓ 与 p.178 语义一致 |
| `TEMP?` = `37.0` / `36.9` | 内部温度 | ✓ 单位 °C（p.37/50） |
| `TARM?` = 4 | 默认 1 | 4 = HOLD：本次会话发过 `TARM HOLD`（**符合**；SGL 触发后本来就会回 HOLD，p.251） |
| `TRIG?` = 1 | 默认 1 | 1 = AUTO ✓ |
| `NRDGS?` = `1, 1` | 默认 `1, AUTO` | 第二字段 = 采样事件码，**AUTO = 1** ✓ |
| `NPLC?` = `10.0000000E+00` | 10 | ✓ |
| `APER?` = `200.000000E-03` | — | = NPLC 10 @50 Hz 的等效积分时间（0.2 s） |
| `RANGE?` = `.1` | DCV AUTO | 设备当前是**固定 0.1 V 档**（被上次会话设定，非上电默认） |
| `FUNC?` = `1, .1` | DCV AUTO | 功能码 1 = DCV，第二字段 = max_input（0.1 V） |
| `AZERO?` = 1 | ON(=1) | ✓ |
| `INBUF?` = 1 | OFF(=0) | 本次发过 `INBUF ON` ✓（也是 `TARM SGL` 配方要求） |
| `END?` = 2 | OFF(=0) | 本次发过 `END ALWAYS`(=2) ✓ |
| `MEM?` = 0 | OFF | ✓ |
| `MFORMAT?` = 4 | **SREAL** | ⚠ 此前误读为 SINT；**4 = SREAL**（p.199），**SINT = 2** |
| `OFORMAT?` = 1 | ASCII | ✓ 1 = ASCII |
| `ISCALE?` = 1.0 | — | ✓ |

## 4. 实测行为的手册依据（本次最关键的现场结论）

1. **"`TRIG HOLD` 下 `TARM SGL,1` 永不出数"**：`TRIG` 事件为 HOLD(4) 时没有触发源
   （p.257：AUTO 才"triggers whenever not busy"；SGL 要"upon receipt of **TRIG SGL**"）。
   手册 p.256 的官方示例正是 `TRIG HOLD` 配 `TRIG SGL`。→ 本库 `prepare_for_read()` 发
   `TRIG AUTO` 合规（备选是发 `TRIG SGL`），且**不改档位/NPLC/功能**。
2. **"free-run / 上电吐数"**：`recover()` 的 `TARM HOLD` + `TRIG HOLD` + 有界 drain 与
   p.256 示例同构（先 `TRIG HOLD` 挂起测量）。
3. **`TARM SGL,1` 后 `TARM?`=4**：p.251 明确 SGL 触发一次后"reverts to the HOLD state"，
   属预期行为。
4. **串尾 LF / CR,LF**：p.176/p.210 说明 ASCII 输出以 `cr,lf` 结尾 → 按 LF 终止读取正确。
5. **`INBUF OFF` 会占住总线**（p.187）→ 解释了 `INBUF ON` 是 `TARM SGL` 配方前置条件。
6. **突发尾部 2 字节**：手册**未**描述 Keysight 样例"读 2n+2 字节"的尾部含义（属样例实现
   细节）→ 仍按"只取前 2n 字节、字节数不足即报错"处理（不猜）。
7. **`MFORMAT SINT` 的溢出边界**：p.173 —— 输入信号 >120% 档位时应改用 **DINT**；本库
   burst 固定用 SINT（与 Keysight 100k rdg/s 样例一致），>120% 场景需另行支持。

## 5. 本次核对带来的修正清单

1. `commands.py`：补 `[MANUAL p.xxx]` 出处与码表常量（TARM/TRIG/END/INBUF/OFORMAT/
   MFORMAT/AZERO），写清 `TEMP?` 单位、`ACBAND` 默认、`NRDGS` 上限。
2. `dmm3458a.py::state()`：把裸码值**解码**为可读语义（`tarm=4(HOLD)`、`oformat=1(ASCII)`、
   `mformat=4(SREAL)`），杜绝"4=SINT"这类误读。
3. `docs/COMMANDS_3458A.md`：关闭已核对的条目，改为引用本文页码；保留仍未覆盖项
   （尾部 2 字节、AC 单次读数配方、SINT 溢出边界、APER/NPLC 细节）。
4. skill `instrument-mcp`：`ks3458a_status` 说明里写清"码值已解码"与 `TEMP?` 单位。

---

## 6. 后续实测补齐（2026-09-23 晚，同一台 3458A）

### 6.1 自动挡 / 固定档（手册 p.160-161、p.183-184）

- 固定档：`DCV <数值>`（原有能力，`ks3458a_configure(dcv_range=0.1/1/10/100/1000)`）。
- 自动挡：新增 `ARANGE ON|OFF`（手册 p.160：Autorange，control = ON / OFF / ONCE）与
  `DCV AUTO`（手册 p.184：max_input=AUTO）。真机实测：
  `ARANGE ON → ARANGE?=1(ON)`、`ARANGE OFF → 0(OFF)`、`DCV AUTO → ARANGE?=1`。
- **重要实测**：`FUNC?` 在自动挡下仍返回固定档数值（如 `1, .1`），**自动挡状态只能看
  `ARANGE?`**——`state()` 已据此修正（此前误用 `FUNC?` 推导，恒为 None）。

### 6.2 突发（SINT / DINT）与跑完收尾

- **DINT 通路已实现并实测**：`MFORMAT/OFORMAT DINT`（4 字节/读数）× ISCALE，
  n=100 → 读 400 字节，与 SINT 同源同档结果一致。手册 p.173：direct-sampling 下
  DINT 满量程是档位的 **500%**（SINT 约 120%）→ **信号可能超 120% 档位时必须用 DINT**。
- **跑完必须收尾**：`PRESET DIG` + `TRIG AUTO` + `NRDGS n` + `MEM OFF` 之下，表取满后
  仍会继续触发/输出——实测紧接着发 `PRESET DIG` 直接 `VI_ERROR_TMO`。
  现在 `read_burst()` 结束时会 `clear()` + `TARM HOLD` + `TRIG HOLD` + **有界** drain。
- **必须恢复输出格式**：`PRESET DIG` 把输出留在 **SINT**（无换行符），此后普通 ASCII
  读数会超时。现在 `read_burst(restore=True)`（默认）在收尾后发
  **`PRESET NORM`**（手册 p.217："similar to RESET but optimizes for remote operation"，
  **不是 `RESET` 命令**）+ `END ALWAYS`/`INBUF ON`/`TRIG AUTO`。实测恢复后
  `oformat=1(ASCII)`、`mformat=4(SREAL)`，ASCII 读数正常。

### 6.3 AC 单次读数配方（原"未实测"项 → 已实测）

`ACV 10` + `SETACV ANA` + `ACBAND 20,1E5` 下，`TARM SGL,1` **可以**读出交流电压：
实测 `4.113401E-03 V AC`（读数返回单一数值、无单位后缀）。即 AC 沿用与 DCV 相同的
`TARM SGL,1` 配方（ANA 转换）；`SETACV SYNC/RNDM`（采样法）未测——手册 p.256 另注
TIMER/SWEEP 不能与采样法 AC 同用。

### 6.4 性能：把"恢复"从必经路径改成按需（关键改动）

计时实测（本机 82357B + Keysight VISA）：

| 阶段 | 改前 | 改后 |
|---|---|---|
| `transport.open`（clear + settle） | 0.46 s | **0.18 s**（settle 0.3→0.05 s） |
| **`connect()`（recover + prepare）** | **5.11 s** | **0.27 s**（`recover="auto"`） |
| `state()`（20 条查询） | 0.17 s | 0.17 s |
| 单次读数（NPLC 10 @50 Hz） | 0.43 s | 0.43 s（物理下限） |

原因与做法：恢复里的每轮 drain 实测 ≈2 s（**VISA 的 `VI_ATTR_TMO_VALUE` 有 ≈2 s 最小
粒度**，250 ms 设不下去），两轮就 ~4 s；而"表被留在 free-run"是少数情况。现在
`connect(recover="auto")` 只做 `prepare_for_read()`（3 条写，≈0.01 s），**读数失败时**
才由 `_with_recover_retry()` 做一次完整恢复并重试——把成本只花在真正需要的场合。
`connect(recover=True)` 仍保留强制恢复（排障/共享台被占时用）。
