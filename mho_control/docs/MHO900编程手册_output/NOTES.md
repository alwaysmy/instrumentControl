# MHO900 系列编程手册 — 关键调研笔记

本文档记录为编写 Python 驱动而必须确认的事实。**所有引用均为手册原文逐字摘录**（中文原文，命令名保留原大小写）。
凡手册未记载的内容，本文明确标注「手册未记载」，不做推断。

- 源 PDF：`D:\Downloads\Datasheets\仪器手册\MHO900-编程手册.pdf`
- 提取正文：同目录 `MHO900编程手册.md`
- 命令索引：同目录 `COMMAND_INDEX.md`
- 页码约定：本文「物理页 n」= PDF 文件内第 n 页（也等于提取件中 `<!-- PAGE n -->`，也等于 PyMuPDF 书签页码）。**手册页脚印刷页码 = 物理页 − 24**（例如物理页 455 页脚印的是 431）。

---

## 1. 手册基本信息（语言 / 版本 / 页数）

| 项目 | 值 | 出处 |
|---|---|---|
| 语言 | **简体中文**（正文全为中文，仅 SCPI 关键字、单位、型号为 ASCII） | 全书 |
| 标题 | `MHO900系列编程手册`（PDF 元数据 title 亦为「MHO900系列编程手册」） | PDF 元数据 |
| 页数 | **480 页**（物理页）；封面页与末页无正文 | 全文 |
| 文档编号 | **`PGA46002-1110`** | 物理页 25 |
| 软件版本 | **`00.01.00`** | 物理页 25 |
| 版权年份 | `© 2026 普源精电科技股份有限公司` | 物理页 2 |
| 适用范围 | 「本手册指导用户如何使用 SCPI 命令通过远程接口编程控制 MHO900 系列数字示波器。该系列示波器可通过 USB 和 LAN 接口与计算机进行通信。」 | 物理页 25 |

手册原文（物理页 25）：

> 文档编号
> PGA46002-1110
> 软件版本
> 00.01.00

注意：**手册没有单独查询固件版本的 SCPI 命令**。` :SYSTem:VERSion?` 返回的是 SCPI 版本号而非固件版本：

> 3.24.13 `:SYSTem:VERSion?` … 功能描述 查询系统使用的 SCPI 版本号。 … 举例 `:SYSTem:VERSion?    /*查询返回3.0*/`

（物理页 291）固件/软件版本只能从 `*IDN?` 的第 4 个字段获得。

---

## 2. 仪器识别 / 型号命名

### 2.1 识别命令：`*IDN?`（IEEE-488.2 通用命令，节 3.12.1，物理页 154–155）

> 3.12.1 `*IDN?`
> 命令格式 `*IDN?`
> 功能描述 查询仪器的 ID 字符串。
> 参数 无。
> 说明 无。
> 返回格式 查询返回 `RIGOL TECHNOLOGIES,<model>,<serial number>,<software version>`。
> - `<model>`：仪器型号。
> - `<serial number>`：仪器序列号。
> - `<software version>`：仪器软件版本。

即 4 个逗号分隔字段，厂商固定为 `RIGOL TECHNOLOGIES`。

### 2.2 本系列覆盖的型号（物理页 25–26）

> MHO900 系列数字示波器包含以下型号。如无特殊说明，本手册以 MHO984 为例说明 MHO900 系列示波器基本操作。

| 型号 | 最大模拟带宽 | 模拟通道数 |
|---|---|---|
| MHO984 | 800 MHz（单通道[1]&半通道[2]）400 MHz（全通道[3]） | 4 |
| MHO954 | 500 MHz（单通道[1]&半通道[2]） | 4 |
| MHO934 | 350 MHz（任意通道数） | 4 |

> 说明
> [1]：单通道模式：任意开启一个通道。
> [2]：半通道模式：任意开启两个通道。
> [3]：全通道模式：任意开启三个通道或开启全部通道。

**结论：MHO984、MHO954、MHO934 三个型号都存在**（问题中提到的三个型号全部命中）。对全文做 `MHO\d{3}` 正则扫描，仅得到 `MHO900`（系列名）、`MHO984`、`MHO954`、`MHO934` —— **不存在 MHO939 或其它型号**。

注意：`<model>` 字段手册只说要「仪器型号」，**未给出字符串大小写或格式样例**（例如是否回 `MHO984` 还是含更高精度后缀），驱动侧应按「不区分大小写、前缀匹配 `MHO9` 后接型号」来解析。

---

## 3. 二进制波形数据传输

### 3.1 涉及命令（子系统 3.28 波形读取命令子系统，物理页 452–464）

读取命令是 **`:WAVeform:DATA?`**（无参数），手册 4.3 节的实例中写作短格式 `:WAV:DATA?`：

> 3.28.5 `:WAVeform:DATA?`
> 命令格式 `:WAVeform:DATA?`
> 功能描述 读取波形数据。
> 参数 无。

配套命令（见 `COMMAND_INDEX.md` 的 3.28 节，共 14 条）：
`:WAVeform:SOURce` / `:MODE` / `:FORMat` / `:POINts` / `:DATA?` / `:XINCrement?` / `:XORigin?` / `:XREFerence?` / `:YINCrement?` / `:YORigin?` / `:YREFerence?` / `:STARt` / `:STOP` / `:PREamble?`

### 3.2 `:WAVeform:FORMat` 的取值（节 3.28.3，物理页 456）

> 3.28.3 `:WAVeform:FORMat`
> 命令格式 `:WAVeform:FORMat <format>` / `:WAVeform:FORMat?`
> 功能描述 设置或查询波形数据的返回格式。
> 参数 `<format>` 离散型 **`{WORD|BYTE|ASCii}`** 默认值 **`BYTE`**
> 说明
> - WORD：一个波形点占两个字节（即 16 位）。
> - BYTE： 一个波形点占一个字节（即 8 位）。
> - ASCii： 以科学计数形式返回各波形点的实际电压值， 各电压值之间以逗号分隔。
> 返回格式 查询返回 **WORD、BYTE 或 ASC**。

注意返回缩写是 `ASC`（不是 `ASCIi`／`ASCII`）。

### 3.3 `:WAVeform:SOURce`（节 3.28.1，物理页 455）

> 参数 `<source>` 离散型 `{CHANnel1|CHANnel2|CHANnel3|CHANnel4|MATH1|MATH2|MATH3|MATH4}` 默认值 `CHANnel1`
> 说明 通道源设为 MATH1~MATH4 时，`:WAVeform:MODE` 仅可选择 NORMal 模式。
> 返回格式 查询返回 CHAN1、CHAN2、CHAN3、CHAN4、MATH1、MATH2、MATH3 或 MATH4。

**驱动注意：发送时用 `CHANnel1`（或其短格式 `CHAN1`），查询返回的是 `CHAN1` 形式，两者不相等**，解析时需归一化。手册未记载 `D0..D15`（数字通道）能否作为 `:WAVeform:SOURce` —— 不在取值列表内。

### 3.4 `:WAVeform:MODE` 与 `:WAVeform:POINts` / `:STARt` / `:STOP`

`:WAVeform:MODE`（节 3.28.2，物理页 455–456）：

> 参数 `<mode>` 离散型 `{NORMal|MAXimum|RAW}` 默认值 `NORMal`
> 说明
> - NORMal： 读取当前屏幕显示的波形数据。
> - MAXimum： 运行状态下，读取屏幕显示的波形数据； 停止状态下，读取内存中的波形数据。
> - RAW： 读取内存中的波形数据。注意：内存中的数据必须在示波器停止状态下进行读取，且读取过程中不可操作示波器。
> - 通道源选择 MATH 时，仅 NORMal 模式有效。
> 返回格式 查询返回 **NORM、MAX 或 RAW**。

`:WAVeform:POINts`（节 3.28.4，物理页 456–457）：

> `<point>` 的范围与当前的波形数据读取模式有关。
> - NORMal 模式：1 至 1000
> - RAW 模式：1 至当前最大的存储深度
> - MAXimum 模式：运行状态下，读取 1 至当前屏幕的有效点数；停止状态下，读取 1 至当前内存中的有效点数

`:WAVeform:STARt` 默认值 `1`；`:WAVeform:STOP` 默认值 `1000`（节 3.28.12/3.28.13，物理页 461–463）：

> - NORMal 模式下，范围是 1 至 1000
> - MAX 模式下，仪器处于 RUN 状态时，范围是 1 至 1000；仪器处于 STOP 状态时，范围是 1 至当前最大存储深度
> - RAW 模式下，范围是 1 至当前最大的存储深度

### 3.5 TMC 块头格式（物理页 454，节 3.28 引言「波形数据读取」）

> 波形数据读取
> - WORD 或 BYTE 格式： 读取的数据格式为 **TMC 头+波形数据点+结束符**。 TMC 头为 **`#NXXXXXX`** 的形式， `#` 为 TMC 规定的头标志符， `N` 表示后面含有 N 个字节，以 ASCII 字符的形式描述波形数据点的长度，结束符用于表示通讯的终止。例如，一次读取的数据为：`#9000001000XXXX` 表示 9 个字节描述数据的长度，`000001000` 表示波形数据的长度，即 1000 字节。
> - ASCii 格式：读取的数据格式为 波形数据点+结束符。波形数据点以科学计数形式返回波形中每一点的实际电压值，各电压值之间以「,」隔开。
> - 分批次读取内存数据时，每次读回的数据只是内存中一块区域的数据。分块读回的数据，每块开头都含有 TMC 数据描述头（WORD 或 BYTE 格式）。相邻两块间的波形数据连续。

**驱动注意（重要）：分批读取内存波形时，每一块都自带 TMC 头**，不能只在第一块解析块头。

### 3.6 BYTE/WORD 数据到电压的换算（物理页 453–454）

图 3.15 / 3.16（NORMAL / RAW 模式下的参数定义）为示意图，其正文给出的公式：

- NORMAL 模式：`XINCrement = TimeScale/100`，`YINCrement = Verticalscale/7500`
- RAW 模式：`YINCrement[1]`，注 [1]：「RAW 模式下，YINCrement 与内存波形的 Verticalscale 和当前选择的 Verticalscale 有关。」

> 下图为读取的波形数据（BYTE 格式下）。… 从第十二个字节（即 8E）开始为波形数据，用户可以使用公式 **`(0x8E - YORigin - YREFerence) × YINCrement`** 将读取的波形数据转换为波形中每一点的电压值。
> 相关命令 `:WAVeform:MODE` `:WAVeform:YINCrement?` `:WAVeform:YORigin?`

各查询的单位说明（散见 3.28.6–3.28.11）：`XINCrement`「单位与当前的通道源相关」；`XORigin`「单位与当前的通道源相关」；`YINCrement?` 返回「单位电压值」；`YORigin?` 返回「相对于垂直参考位置的垂直偏移」（整数）；`YREFerence?`「查询返回一个整数」且「YREFerence 的值与 `:WAVeform:FORMat` 命令的配置有关。不同波形数据的返回格式下参考位置不同。」；`XREFerence?`「查询返回 0（即屏幕或内存中第一个波形点）」。

### 3.7 `:WAVeform:PREamble?` 字段布局（节 3.28.14，物理页 463–464）

> 命令格式 `:WAVeform:PREamble?`
> 功能描述 查询并返回全部的波形参数。
> 返回格式 查询返回 **10 个**波形参数以「,」分隔：
> `<format>,<type>,<points>,<count>,<xincrement>,<xorigin>,<xreference>,<yincrement>,<yorigin>,<yreference>`
> 其中，
> - `<format>`： 0（BYTE）、 1（WORD）或 2（ASC）。
> - `<type>`： 0（NORMal）、 1（MAXimum）或 2（RAW）。
> - `<points>`： `<points>` 为 1 至 50000000 之间的整数。
> - `<count>`：在平均采样方式下为平均次数，其它方式下为 1。
> - `<xincrement>`： X 方向上的相邻两点之间的时间差。
> - `<xorigin>`： X 方向上波形数据的起始时间。
> - `<xreference>`： X 方向上数据点的参考时间基准。
> - `<yincrement>`： Y 方向上波形的步进值。
> - `<yorigin>`： Y 方向上相对于「垂直参考位置」 的垂直偏移。
> - `<yreference>`： Y 方向的垂直参考位置。

手册给出的完整返回样例（物理页 463–464）：

> `:WAVeform:PREamble?` /*查询返回
> `0,0,1000,1,1.000000E-8,-5.000000E-6,0.000000E-12,4.000000E-03,0,128*`

字段顺序与单位汇总（第 1–4 项为整数枚举/计数，后 6 项为科学计数法浮点）：

| # | 字段 | 含义 | 单位/取值 |
|---|---|---|---|
| 1 | `<format>` | 数据格式枚举 | 0=BYTE, 1=WORD, 2=ASC |
| 2 | `<type>` | 读取模式枚举 | 0=NORMal, 1=MAXimum, 2=RAW |
| 3 | `<points>` | 点数 | 整数，1…50000000 |
| 4 | `<count>` | 平均次数 | 平均采样下为平均次数，否则 1 |
| 5 | `<xincrement>` | X 相邻两点时间差 | 时间（与通道源单位相关），如 1.000000E-8 |
| 6 | `<xorigin>` | X 起始时间 | 时间，如 -5.000000E-6 |
| 7 | `<xreference>` | X 参考时间基准 | 时间，样例 0.000000E-12 |
| 8 | `<yincrement>` | Y 步进值 | 电压/格值，如 4.000000E-03 |
| 9 | `<yorigin>` | Y 垂直偏移 | 整数（样例 0） |
| 10 | `<yreference>` | Y 垂直参考位置 | 整数（样例 128） |

### 3.8 字节序 / 端序（Endianness）

**手册未记载 WORD 格式波形数据的字节序（大端/小端）**。全库检索 `字节序`、`大端`、`小端`、`低位在前`、`高位在前`、`字节顺序` 均为 0 命中（`ENDian` 仅出现在总线解码 `:BUS<n>:SPI:ENDian` / `:BUS<n>:RS232:ENDian` / `:BUS<n>:PARallel:ENDian` 命令中，与波形数据无关）。

手册也没有给出 WORD 模式下 `:WAVeform:PREamble?` 的 `<yincrement>` 与 7500 系数的 WORD 对应关系说明。**结论：WORD 模式的端序必须实测确认，不得照搬其它 RIGOL 型号的假设。**

---

## 4. 远程截屏（屏幕图像获取）

### 4.1 唯一命令：`:DISPlay:DATA?`（节 3.9.8，物理页 140–141）

> 3.9.8 `:DISPlay:DATA?`
> 命令格式 **`:DISPlay:DATA? [<type>]`**
> 功能描述 查询当前显示图像的位图数据流。
> 参数 `<type>` 离散型 **`{BMP|PNG|JPG}`** 默认值 **`BMP`**
> 说明 读取的数据格式为 TMC 头+屏幕截图的二进制数据流+结束符。 TMC 头为 `#NXXXXXX` 的形式， `#` 为 TMC 规定的头标志符， `N` 表示后面含有 N 个字节，以 ASCII 字符的形式描述屏幕截图二进制数据流的长度，结束符用于表示通讯的终止。例如，一次读取的数据为：`#9000387356` 表示 9 个字节描述数据的长度，`000387356` 表示二进制数据流的长度，即 387356 字节。
> 返回格式 查询返回指定格式的屏幕截图的二进制数据流。
> 举例 无。

即 **`:DISPlay:DATA?`、`:DISPlay:DATA? PNG`、`:DISPlay:DATA? JPG` 三种写法**（方括号 `[]` 在手册 2.1 节定义为「可省略」）。

### 4.2 明确否定的命令（手册未定义）

全文检索结果：

| 命令 | 命中 | 结论 |
|---|---|---|
| `:DISPlay:DATA:FORMat` / `DATA:FORM` | 0 | **手册未记载** |
| `:DISPlay:DATA:COLor` / `DATA:COL` | 0 | **手册未记载** |
| `:DISPlay:DATA:INVert` / `DATA:INV` | 0 | **手册未记载** |
| `:HARDcopy` / `:HCOPy` / `:PRINt` / `:SCReen` | 0 | **手册未记载** |

**结论：本型号不是「`:DISPlay:DATA:FORM` + `:DISPlay:DATA:COLor` + `:DISPlay:DATA:INVert` 再 `.DATA?`」的那套 RIGOL 命令结构；格式是通过 `:DISPlay:DATA?` 的可选参数 `<type>` 指定的。** 驱动不要照抄其它型号的三段式写法。

`DISPlay` 子系统的全部 12 条命令（见 `COMMAND_INDEX.md` 3.9 节）为：
`:DISPlay:CLEar`、`:DISPlay:TYPE`、`:DISPlay:GRADing:TIME`、`:DISPlay:WBRightness`、`:DISPlay:GRID`、`:DISPlay:GBRightness`、`:DISPlay:CBRightness`、`:DISPlay:DATA?`、`:DISPlay:RULers`、`:DISPlay:MOVE`、`:DISPlay:COLor`、`:DISPlay:WHOLd`。
（注意 `:DISPlay:COLor` 是「色温显示」开关，**不是**截图颜色设置。）

### 4.3 TMC 块头格式

与波形数据同一规则：`#NXXXXXX`，`#` 为头标志符，`N` 为随后的长度字段字节数（ASCII 数字），再接 N 位 ASCII 十进制长度值，然后是二进制数据流，最后是结束符（换行）。示例 `#9000387356` → 数据长度 387356 字节。

---

## 5. 运行 / 停止 / 等待 相关命令

### 5.1 有记载的执行控制命令（3.1 根命令系统，物理页 32–34）

| 命令 | 手册原文功能描述 | 节 |
|---|---|---|
| `:RUN` | 「`:RUN` 命令使示波器开始运行。」 | 3.1.2 |
| `:STOP` | 「`:STOP` 命令使示波器停止运行。」 | 3.1.3 |
| `:SINGle` | 「单次触发操作。将示波器设置为单次触发方式。该命令功能等同于发送 `:TRIGger:SWEep SINGle` 命令。」 | 3.1.4 |
| `:TFORce` | 「强制产生一个触发信号。适用于普通和单次触发方式，请参考 `:TRIGger:SWEep` 命令。」 | 3.1.5 |
| `:CLEar` | 「清除屏幕上所有的波形。」 | 3.1.1 |

`:SINGle` 的补充说明（物理页 34）：

> - 单次触发方式下，示波器将在符合触发条件时触发一次，然后停止。
> - 波形录制功能打开时或回放录制的波形时，该命令无效。
> - 单次触发时，您可以使用 `:TFORce` 命令强制进行一次触发。

### 5.2 触发状态查询：`:TRIGger:STATus?`（节 3.27.3，物理页 328）

> 命令格式 `:TRIGger:STATus?`
> 功能描述 查询当前的触发状态。
> 返回格式 查询返回 **TD、WAIT、RUN、AUTO 或 STOP**。

### 5.3 `*WAI`（节 3.12.9，物理页 159）—— 注意是空操作

> 3.12.9 `*WAI`
> 命令格式 `*WAI`
> 功能描述 等待操作完成。
> 说明 **当前操作命令是为了兼容其他机器，在示波器上没有任何功能。**
> 返回格式 无。

**结论：本型号的 `*WAI` 不实现任何同步功能，不可依赖它做命令完成同步。** 同步应改用 `*OPC?`（节 2.3 与 3.12.6）：

> - `*OPC`：设备接收到 `*OPC` 命令之后，会等待之前收到的命令全部执行完成，同时将标准事件寄存器的 bit0 位置 1，然后再执行后续指令。
> - `*OPC?`：设备接收到 `*OPC?` 命令之后，查询设备是否已经执行完成之前收到的全部命令。如果已经完成，则返回 1；如果未完成，则等待命令全部执行完成之后再返回 1。`*OPC?` 命令不会对寄存器进行操作。

（物理页 30）手册 2.3 节还说明：**`*RST` 是 Overlapped 类型命令**（物理页 31 的表格「下表为 Overlapped 类型命令，支持 OPC 功能」中列出 `*RST`，约束条件为 `-`），因此连续发送后需要 `*OPC?`／足够延时。

### 5.4 明确否定的命令

**`:SYSTem:WAIT` 手册未记载**（全文 0 命中）。等待只能靠 `*OPC?`、`:TRIGger:STATus?` 轮询或固定延时。

---

## 6. 远程/本地锁定 与 复位 命令

### 6.1 锁定：只有 `:SYSTem:LOCKed`（节 3.24.14，物理页 291）

> 3.24.14 `:SYSTem:LOCKed`
> 命令格式 `:SYSTem:LOCKed <bool>` / `:SYSTem:LOCKed?`
> 功能描述 打开或关闭屏幕和键盘锁定功能，或者查询屏幕和键盘锁定功能的状态。
> 参数 `<bool>` 布尔型 `{{1|ON}|{0|OFF}}` 默认值 `0|OFF`
> 返回格式 查询返回 1 或 0。
> 举例 `:SYSTem:LOCKed ON` /*打开屏幕和键盘锁定功能*/

注意：这是**前面板（屏幕+键盘）锁定**，用途是防止本地误操作，属于「远程控制时锁定本地面板」的功能，但命令名是 `LOCKed` 语义。

### 6.2 明确否定的锁定命令

| 命令 | 命中 | 结论 |
|---|---|---|
| `:SYSTem:REMote` | 0 | **手册未记载** |
| `:SYSTem:COMMunicate:RLSTate` | 0 | **手册未记载**（`COMMunicate` 全文 0 命中） |
| `:SYSTem:LOCK`（无 ed） | — | 不存在，唯一形式是 **`:SYSTem:LOCKed`** |

### 6.3 复位类命令

| 命令 | 手册原文 | 节 / 物理页 |
|---|---|---|
| `*RST` | 「将仪器恢复至出厂默认状态。」 | 3.12.2 / 155 |
| `:SYSTem:RESet` | 「使系统重新上电。」 | 3.24.12 / 290 |
| `:SYSTem:PON {LATest\|DEFault}` | 「设置或查询示波器重新上电时所调用的配置类型。」（查询返回 `LAT` 或 `DEF`） | 3.24.10 / 289 |
| `:SYSTem:PSTatus {DEFault\|OPEN}` | 「设置或查询仪器的电源状态。」 | 3.24.11 / 289–290 |
| `:SYSTem:SETup` | 系统设置 | 3.24.20 |
| `*CLS` | 「将所有事件寄存器的值清零，同时清除错误队列。」 | 3.12.3 / 155 |

**⚠️ 重要区别：`:SYSTem:RESet` 是「使系统重新上电」（重启仪器），不是「恢复默认设置」。** 恢复出厂默认设置要用 `*RST`。

### 6.4 明确否定的复位命令

| 命令 | 命中 | 结论 |
|---|---|---|
| `:SYSTem:PRESet` | 0 | **手册未记载** |
| `:SYSTem:FACTory` | 0 | **手册未记载**（`FACTory` 全文 0 命中） |
| `*SAV` / `*RCL` | 0 | **手册未记载** |
| `*TRG` | 0 | **手册未记载** |

---

## 7. LAN / 远程接口细节

### 7.1 接口类型（2.2 远程控制，物理页 29）

> 本仪器支持通过 **USB 接口和 LAN 接口** 与计算机通信，从而实现使用 SCPI（Standard Commands for Programmable Instruments）命令集对仪器进行远程控制。
> 通过 Web Control 发送 SCPI 命令
> 在通过 LAN 接口连接设备的情况下，也可以通过 Web Control 控制界面，实现从 PC 端向设备发送 SCPI 命令行。操作步骤如下：
> 1. 获取仪器的 IP 地址，通过浏览器访问仪器的 Web Control 控制界面。
> 2. 登录 Web Control 控制界面后，点击左侧的 SCPI Panel Control 功能栏，进入 SCPI Command 界面。
> 3. 在对话框中输入 SCPI 命令行，点击 Send&Read 按钮可执行命令…

### 7.2 VISA 地址查询：`:LAN:VISA?`（节 3.14.11，物理页 171）

> 命令格式 **`:LAN:VISA? [<type>]`**
> 功能描述 查询仪器 VISA 地址。
> 参数 `<type>` 离散型 **`{USB|LXI|SOCKet}`**
> 说明 此命令包含一个可选参数 type 来设置查询的地址类型，**默认返回网络 LXI 地址**。
> 返回格式 查询以字符串形式返回 VISA 地址。

这是手册中**唯一**提到 `SOCKet` 的地方，说明仪器支持原始 socket 的 VISA 地址形式（`TCPIP0::<ip>::<port>::SOCKET`），但——

### 7.3 端口号 / 协议细节：手册未记载

全文检索结果（均为 0 命中）：

| 检索词 | 命中 | 结论 |
|---|---|---|
| `5025`（RIGOL/VISA 常用 raw socket 端口） | 0 | 手册未给出端口号 |
| `5555` | 0 | — |
| `端口` / `端口号` | 0 | 手册未给出任何端口号 |
| `VXI-11` / `VXI11` | 0 | 手册未提及 VXI-11 |
| `HiSLIP` / `hislip` | 0 | 手册未提及 HiSLIP |
| `socket`（小写） | 0 | 仅 `SOCKet` 出现在 `:LAN:VISA?` 的参数枚举中 |

**结论：手册只说明「支持 USB 和 LAN / LXI」，未记载 LXI 端口号、VXI-11、HiSLIP 或 raw socket 服务端口。驱动侧端口号需从仪器实际配置（`:LAN:VISA? SOCKet` 返回值）或 LXI 发现机制获得，不可从本手册推断。**

### 7.4 LAN 配置命令（子系统 3.14，物理页 165–173，共 15 条）

`:LAN:DHCP`、`:LAN:AUToip`、`:LAN:GATeway`、`:LAN:DNS`、`:LAN:MAC?`、`:LAN:DSERver?`、`:LAN:MANual`、`:LAN:IPADdress`、`:LAN:SMASk`、`:LAN:STATus?`、`:LAN:VISA?`、`:LAN:MDNS`、`:LAN:HOST:NAME`、`:LAN:DESCription`、`:LAN:APPLy`

手册特别说明（物理页 165）：

> 其他 `:LAN` 命令设置完，需要发送 `:LAN:APPLy` 命令使配置生效。

`:LAN:STATus?` 返回枚举（物理页 170–171）：`UNLINK`、`CONNECTED`、`INIT`、`IPCONFLICT`、`BUSY`、`CONFIGURED`、`DHCPFAILED`、`INVALIDIP`、`IPLOSE`。

---

## 8. 提取质量与需人工复核之处

### 8.1 文本层情况

**源 PDF 有完整文本层，未使用 OCR。** 用 PyMuPDF 抽取全书 480 页共 371,644 字符；`read-pdf` 技能判定为文本型 PDF，走 `pdfmux + pdfplumber` 双引擎（无 OCR、无识别误差）。

- 每页字符数：仅 6 页 < 200 字符 —— 物理页 1（封面，0 字符）、26、464、472、479、480（0 字符）。这些页为纯图或空白（封面、章节间隔页）。
- 其余页面文本完整，中文无乱码（UTF-8），SCPI 命令大小写原样保留。

### 8.2 提取件结构

`MHO900编程手册.md` 由 `read-pdf` 输出 + 后处理组成：

1. 每页前有 `<!-- PAGE n -->` 标记（n = PDF 物理页）。
2. 页正文逐字保留（pdfmux 从文本层重建）。
3. 每页末尾 `[TABLES]` 段是 pdfplumber 还原的 Markdown 表格（全书 396 个表格块）。
4. **后处理**：把手册大纲中的标题行合并为 Markdown 标题（`### 3.28.5 :WAVeform:DATA?`），共转换 731/732 条；正文文字未做任何改写。唯一未转换的是 TOC 页的「目录」标题（物理页 3）。

### 8.3 需人工复核的点

| 位置 | 问题 | 建议 |
|---|---|---|
| 物理页 25–26（型号表） | 表格跨页，`MHO984` 行的带宽单元格在 pdfmux 正文里被拆成「800 MHz（单通道[1]&半通道[2]）/ 400 MHz（全通道[3]）」，`[TABLES]` 段中该单元格为多行文本 | 已在本文第 2.2 节人工整理为正确表格 |
| 物理页 31（Overlapped 命令表） | pdfplumber 未识别该小表，`[TABLES]` 段为空；正文仍含 `*RST` / `-` 两行 | 已从正文确认：表中仅 `*RST`，约束条件 `-` |
| 物理页 194（`:MATH<n>:FFT:AVCNt`） | 手册把标题写成「命令」而非「命令格式」（全大书仅此一处），且该节「描述」而非「功能描述」 | 已单独适配，命令内容无误 |
| 全书插图 | **所有图形/示意图未提取**（`imgs/` 为空）。涉及图 3.15 / 3.16「NORMAL/RAW 模式下的参数定义」（物理页 453）、物理页 454 的十六进制波形数据截图、各类时序图与菜单截图 | 相关公式已由正文文字覆盖（见 3.6），但 WORD 模式系数与端序图无法佐证，建议人工翻页确认 |
| 物理页 464 | 仅含续行 `0,0,1000,1,1.000000E-8,-5.000000E-6,0.000000E-12,4.000000E-03,0,128*`（PREamble 返回样例的续行） | 已在 3.7 节与上一页拼接 |
| 长命令名跨行 | 正文中长命令名偶被断行（如 `:SOURce<n>:MOD:AM:INTernal:FREQuency`） | `COMMAND_INDEX.md` 的命令名取自 PDF 书签（大纲），不受断行影响，可作为权威列表 |
| 中文标点 | pdfmux 输出中的全角括号/逗号在部分段落被转为半角（如 `(` `)`） | 不影响命令与参数；`COMMAND_INDEX.md` 中的命令名逐字取自 `命令格式` 段，保持原样 |

### 8.4 命令清单的可信度

`COMMAND_INDEX.md` 的 654 条命令来自两层交叉验证：

1. **PDF 书签（大纲）** 共 732 条，其中 686 条标题为命令形式（`:...` 或 `*...`）。
2. **正文解析**：对每条目录项，在正文中定位其标题位置、按「下一个标题」为界切出该节，再从该节中提取 `命令格式`（或「命令」）区块的原文行。

结果：**654 条成功提取到 `命令格式` 原文**；其余 **32 条**是子系统分组标题（本身不作为命令定义），已确认列表如下，均**不是**可发送命令：

```
:BUS<n>:PARallel   :BUS<n>:RS232   :BUS<n>:IIC    :BUS<n>:SPI    :BUS<n>:CAN
:BUS<n>:LIN        :BUS<n>:FLEXray :BUS<n>:IIS    :BUS<n>:M1553  :CURSor:MANual
:CURSor:TRACk      :CURSor:XY      :TRIGger:EDGE   :TRIGger:PULSe :TRIGger:SLOPe
:TRIGger:VIDeo     :TRIGger:PATTern :TRIGger:DURation :TRIGger:TIMeout
:TRIGger:RUNT      :TRIGger:WINDows :TRIGger:DELay :TRIGger:SHOLd :TRIGger:NEDGe
:TRIGger:RS232     :TRIGger:IIC    :TRIGger:SPI    :TRIGger:CAN  :TRIGger:LIN
:TRIGger:FLEXray   :TRIGger:IIS    :TRIGger:M1553
```

（这些是 3.4 总线解码、3.8 光标、3.27 各触发类型的**分组标题**，其下属子命令如 `:TRIGger:EDGE:SOURce` 均已单独收录。）

各子系统命令数合计 654，与逐节计数一致（见 `COMMAND_INDEX.md` 顶部「子系统总览」表）。

---

## 9. 给驱动作者的要点速查

| 需求 | 手册确认的命令 |
|---|---|
| 识别仪器 | `*IDN?` → `RIGOL TECHNOLOGIES,<model>,<serial>,<sw version>` |
| 运行 / 停止 / 单次 / 强制触发 | `:RUN` / `:STOP` / `:SINGle` / `:TFORce` |
| 触发状态轮询 | `:TRIGger:STATus?` → `TD`\|`WAIT`\|`RUN`\|`AUTO`\|`STOP` |
| 命令完成同步 | `*OPC?`（**`*WAI` 为空操作，不可用**） |
| 读波形 | `:WAVeform:SOURce` + `:MODE` + `:FORMat` + `:STARt`/`:STOP`/`:POINts` + `:WAVeform:DATA?` |
| 波形参数 | `:WAVeform:PREamble?`（10 字段，见 3.7） |
| 截屏 | `:DISPlay:DATA?`（可选 `BMP`\|`PNG`\|`JPG`，默认 `BMP`） |
| 恢复出厂设置 | `*RST`（**不是** `:SYSTem:RESet`，后者是重启） |
| 锁前面板 | `:SYSTem:LOCKed ON` |
| 查询 VISA 地址 | `:LAN:VISA?` / `:LAN:VISA? USB` / `:LAN:VISA? SOCKet` / `:LAN:VISA? LXI` |
| 采样率 | `:ACQuire:SRATe?`（只读） |
| 存储深度 | `:ACQuire:MDEPth` |
| 采样方式 | `:ACQuire:TYPE` |

**手册未定义、驱动不可使用（避免猜测）：** `:SYSTem:WAIT`、`:SYSTem:REMote`、`:SYSTem:COMMunicate:RLSTate`、`:SYSTem:PRESet`、`:SYSTem:FACTory`、`:DISPlay:DATA:FORMat`、`:DISPlay:DATA:COLor`、`:DISPlay:DATA:INVert`、`:HARDcopy`、`*TRG`、`*SAV`、`*RCL`。
