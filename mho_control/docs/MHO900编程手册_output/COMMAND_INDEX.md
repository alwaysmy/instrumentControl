# MHO900 系列示波器 SCPI 命令索引

> 来源：`MHO900-编程手册.pdf`（RIGOL MHO900 系列编程手册）。命令名与说明逐字取自手册原文，未改写、未推断。
> 对应正文提取件：`MHO900编程手册.md`（同目录）。

## 使用约定

- **命令（手册原文）**：与手册正文 `命令格式` 段完全一致的大小写，例如 `:WAVeform:DATA?`。表格即以此列为准。
- **长格式 / 短格式**：按手册 2.1 节「命令缩写」规则推导——关键字对大小写不敏感，但缩写必须输入命令格式中的大写字母。
  例如手册原文 `:WAVeform:FORMat` → 长格式 `:WAVEFORM:FORMAT`，短格式 `:WAV:FORM`。`<n>` 占位符保持不变（实际发送时替换为编号）。
- **页**：`<!-- PAGE n -->` 对应的 **PDF 物理页码**。手册页脚印刷页码 = 物理页 − 24。
- **节**：手册章节号，可直接在提取件中搜索（提取件已把标题写成 `### 3.28.5 :WAVeform:DATA?` 形式）。
- 命令总数：**654**（手册第 3 章「命令系统」逐条列出的命令/查询）。

## 子系统总览

| 节 | 子系统 | 命令数 | 手册页 (PDF 物理页) |
|---|---|---|---|
| 3.1 | 根命令系统 | 5 | 32 |
| 3.2 | 波形自动设置命令子系统 | 7 | 35 |
| 3.3 | 采样命令子系统 | 5 | 39 |
| 3.4 | 总线命令子系统 | 68 | 43 |
| 3.5 | 伯德图命令子系统 （选件） | 11 | 92 |
| 3.6 | 通道命令子系统 | 14 | 99 |
| 3.7 | 频率计命令子系统 | 7 | 109 |
| 3.8 | 光标命令子系统 | 41 | 114 |
| 3.9 | 显示命令子系统 | 12 | 136 |
| 3.10 | 电压表命令子系统 | 4 | 143 |
| 3.11 | 直方图命令子系统 | 11 | 146 |
| 3.12 | IEEE488.2通用命令 | 10 | 154 |
| 3.13 | 数字通道命令子系统 | 8 | 160 |
| 3.14 | 局域网命令子系统 | 15 | 165 |
| 3.15 | 通过/失败测试命令子系统 | 13 | 174 |
| 3.16 | 数学运算命令子系统 | 42 | 183 |
| 3.17 | 测量命令子系统 | 33 | 215 |
| 3.18 | 快捷操作命令子系统 | 1 | 237 |
| 3.19 | 波形录制命令子系统 | 24 | 238 |
| 3.20 | 参考波形命令子系统 | 9 | 251 |
| 3.21 | 存储功能命令子系统 | 23 | 256 |
| 3.22 | 搜索命令子系统 | 14 | 270 |
| 3.23 | 导航命令子系统 | 12 | 278 |
| 3.24 | 辅助命令子系统 | 24 | 284 |
| 3.25 | 函数/任意波形发生器命令子系统（选件） | 25 | 299 |
| 3.26 | 时基命令子系统 | 15 | 317 |
| 3.27 | 触发命令子系统 | 187 | 326 |
| 3.28 | 波形读取命令子系统 | 14 | 455 |
| | **合计** | **654** | |

## 3.1 根命令系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:CLEar` | `:CLEAR` / `:CLE` | 清除屏幕上所有的波形 | 3.1.1 | 32 |
| `:RUN` | `:RUN` / `:RUN` | :RUN命令使示波器开始运行 | 3.1.2 | 32 |
| `:STOP` | `:STOP` / `:STOP` | :STOP命令使示波器停止运行 | 3.1.3 | 33 |
| `:SINGle` | `:SINGLE` / `:SING` | 单次触发操作 | 3.1.4 | 33 |
| `:TFORce` | `:TFORCE` / `:TFOR` | 强制产生一个触发信号 | 3.1.5 | 34 |

<details><summary>3.1 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.1.1 | `:CLEar` |
| 3.1.2 | `:RUN` |
| 3.1.3 | `:STOP` |
| 3.1.4 | `:SINGle` |
| 3.1.5 | `:TFORce` |

</details>

## 3.2 波形自动设置命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:AUToset` | `:AUTOSET` / `:AUT` | 启用波形自动设置功能 | 3.2.1 | 35 |
| `:AUToset:PEAK` | `:AUTOSET:PEAK` / `:AUT:PEAK` | 设置或查询峰峰优先是否打开 | 3.2.2 | 35 |
| `:AUToset:OPENch` | `:AUTOSET:OPENCH` / `:AUT:OPEN` | 设置或查询执行AUTO操作时，是否只检测已打开的通道 | 3.2.3 | 36 |
| `:AUToset:OVERlap` | `:AUTOSET:OVERLAP` / `:AUT:OVER` | 设置或查询是否打开波形重叠显示功能 | 3.2.4 | 36 |
| `:AUToset:KEEPcoup` | `:AUTOSET:KEEPCOUP` / `:AUT:KEEP` | 设置或查询是否打开耦合保持 | 3.2.5 | 37 |
| `:AUToset:LOCK` | `:AUTOSET:LOCK` / `:AUT:LOCK` | 设置或查询AUTO功能锁状态 | 3.2.6 | 38 |
| `:AUToset:ENAble` | `:AUTOSET:ENABLE` / `:AUT:ENA` | 设置或查询“自动设置启用/禁用”特性 | 3.2.7 | 38 |

<details><summary>3.2 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.2.1 | `:AUToset` |
| 3.2.2 | `:AUToset:PEAK <bool>` ; `:AUToset:PEAK?` |
| 3.2.3 | `:AUToset:OPENch <bool>` ; `:AUToset:OPENch?` |
| 3.2.4 | `:AUToset:OVERlap <bool>` ; `:AUToset:OVERlap?` |
| 3.2.5 | `:AUToset:KEEPcoup <bool>` ; `:AUToset:KEEPcoup?` |
| 3.2.6 | `:AUToset:LOCK <bool>` ; `:AUToset:LOCK?` |
| 3.2.7 | `:AUToset:ENAble <bool>` ; `:AUToset:ENAble?` |

</details>

## 3.3 采样命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:ACQuire:AVERages` | `:ACQUIRE:AVERAGES` / `:ACQ:AVER` | 设置或查询平均获取方式下的平均次数 | 3.3.1 | 39 |
| `:ACQuire:MDEPth` | `:ACQUIRE:MDEPTH` / `:ACQ:MDEP` | 设置或查询示波器的存储深度（即在一次触发采集中所能存储的波形点数），默认单位为pts（点） | 3.3.2 | 40 |
| `:ACQuire:TYPE` | `:ACQUIRE:TYPE` / `:ACQ:TYPE` | 设置或查询示波器采样的获取方式 | 3.3.3 | 41 |
| `:ACQuire:SRATe?` | `:ACQUIRE:SRATE?` / `:ACQ:SRAT?` | 查询当前的采样率，默认单位为Sa/s | 3.3.4 | 42 |
| `:ACQuire:BITS` | `:ACQUIRE:BITS` / `:ACQ:BITS` | 设置或查询示波器在高分辨率采样模式下支持的分辨率bit数 | 3.3.5 | 42 |

<details><summary>3.3 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.3.1 | `:ACQuire:AVERages <count>` ; `:ACQuire:AVERages?` |
| 3.3.2 | `:ACQuire:MDEPth <mdep>` ; `:ACQuire:MDEPth?` |
| 3.3.3 | `:ACQuire:TYPE <type>` ; `:ACQuire:TYPE?` |
| 3.3.4 | `:ACQuire:SRATe?` |
| 3.3.5 | `:ACQuire:BITS <bit>` ; `:ACQuire:BITS?` |

</details>

## 3.4 总线命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:BUS<n>:MODE` | `:BUS<N>:MODE` / `:BUS<>:MODE` | 设置或查询指定解码总线的解码类型 | 3.4.1 | 43 |
| `:BUS<n>:DISPlay` | `:BUS<N>:DISPLAY` / `:BUS<>:DISP` | 打开或关闭指定解码总线开关，或查询指定解码总线的开/关状态 | 3.4.2 | 43 |
| `:BUS<n>:FORMat` | `:BUS<N>:FORMAT` / `:BUS<>:FORM` | 设置或查询指定解码总线解码数据的格式 | 3.4.3 | 44 |
| `:BUS<n>:EVENt` | `:BUS<N>:EVENT` / `:BUS<>:EVEN` | 打开或关闭指定解码总线的事件表，或查询指定解码总线事件表的开/关状态 | 3.4.4 | 45 |
| `:BUS<n>:LABel` | `:BUS<N>:LABEL` / `:BUS<>:LAB` | 打开或关闭指定解码总线的标签，或查询指定解码总线标签的开/关状态 | 3.4.5 | 45 |
| `:BUS<n>:DATA?` | `:BUS<N>:DATA?` / `:BUS<>:DATA?` | 读取指定解码总线的事件表数据 | 3.4.6 | 46 |
| `:BUS<n>:EEXPort` | `:BUS<N>:EEXPORT` / `:BUS<>:EEXP` | 将指定解码总线事件表中的解码信息以CSV格式导出 | 3.4.7 | 47 |
| `:BUS<n>:POSition` | `:BUS<N>:POSITION` / `:BUS<>:POS` | 设置或查询指定解码总线在屏幕中的垂直位置 | 3.4.8 | 48 |
| `:BUS<n>:THReshold` | `:BUS<N>:THRESHOLD` / `:BUS<>:THR` | 设置或查询指定解码总线的指定解码源的阈值 | 3.4.9 | 48 |
| `:BUS<n>:PARallel:BUS` | `:BUS<N>:PARALLEL:BUS` / `:BUS<>:PAR:BUS` | 设置或查询指定解码总线为并行解码时数据总线的通道源 | 3.4.10.1 | 50 |
| `:BUS<n>:PARallel:CLK` | `:BUS<N>:PARALLEL:CLK` / `:BUS<>:PAR:CLK` | 设置或查询指定解码总线为并行解码时的时钟源 | 3.4.10.2 | 51 |
| `:BUS<n>:PARallel:SLOPe` | `:BUS<N>:PARALLEL:SLOPE` / `:BUS<>:PAR:SLOP` | 设置或查询并行解码对数据通道进行采样时时钟通道的边沿类型 | 3.4.10.3 | 51 |
| `:BUS<n>:PARallel:WIDTh` | `:BUS<N>:PARALLEL:WIDTH` / `:BUS<>:PAR:WIDT` | 设置或查询指定解码总线为并行解码时数据宽度，即每帧数据的位数 | 3.4.10.4 | 52 |
| `:BUS<n>:PARallel:BITX` | `:BUS<N>:PARALLEL:BITX` / `:BUS<>:PAR:BITX` | 设置或查询指定解码总线为并行解码时需要设定通道源的数据位 | 3.4.10.5 | 53 |
| `:BUS<n>:PARallel:SOURce` | `:BUS<N>:PARALLEL:SOURCE` / `:BUS<>:PAR:SOUR` | 设置或查询指定解码总线为并行解码时当前选中数据位的通道源 | 3.4.10.6 | 53 |
| `:BUS<n>:PARallel:ENDian` | `:BUS<N>:PARALLEL:ENDIAN` / `:BUS<>:PAR:END` | 设置或查询指定解码总线的并行解码的位序 | 3.4.10.7 | 54 |
| `:BUS<n>:PARallel:POLarity` | `:BUS<N>:PARALLEL:POLARITY` / `:BUS<>:PAR:POL` | 设置或查询指定解码总线为并行解码时的数据极性 | 3.4.10.8 | 55 |
| `:BUS<n>:RS232:TX` | `:BUS<N>:RS232:TX` / `:BUS<>:RS232:TX` | 设置或查询指定解码总线为RS232解码时的TX通道源 | 3.4.11.1 | 56 |
| `:BUS<n>:RS232:RX` | `:BUS<N>:RS232:RX` / `:BUS<>:RS232:RX` | 设置或查询指定解码总线为RS232解码时的RX通道源 | 3.4.11.2 | 57 |
| `:BUS<n>:RS232:POLarity` | `:BUS<N>:RS232:POLARITY` / `:BUS<>:RS232:POL` | 设置或查询指定解码总线为RS232解码时的极性 | 3.4.11.3 | 58 |
| `:BUS<n>:RS232:PARity` | `:BUS<N>:RS232:PARITY` / `:BUS<>:RS232:PAR` | 设置或查询指定解码总线为RS232解码时数据传输的奇偶校验方式 | 3.4.11.4 | 58 |
| `:BUS<n>:RS232:ENDian` | `:BUS<N>:RS232:ENDIAN` / `:BUS<>:RS232:END` | 设置或查询指定解码总线为RS232解码时数据传输的位序 | 3.4.11.5 | 59 |
| `:BUS<n>:RS232:BAUD` | `:BUS<N>:RS232:BAUD` / `:BUS<>:RS232:BAUD` | 设置或查询指定解码总线为RS232解码时数据传输的波特率，默认单位为bps | 3.4.11.6 | 60 |
| `:BUS<n>:RS232:DBITs` | `:BUS<N>:RS232:DBITS` / `:BUS<>:RS232:DBIT` | 设置或查询指定解码总线为RS232解码时的数据位宽 | 3.4.11.7 | 60 |
| `:BUS<n>:RS232:SBITs` | `:BUS<N>:RS232:SBITS` / `:BUS<>:RS232:SBIT` | 设置或查询指定解码总线为RS232解码时每帧数据后的停止位数 | 3.4.11.8 | 61 |
| `:BUS<n>:IIC:SCLK:SOURce` | `:BUS<N>:IIC:SCLK:SOURCE` / `:BUS<>:IIC:SCLK:SOUR` | 设置或查询指定解码总线为I2C解码时的时钟源 | 3.4.12.1 | 62 |
| `:BUS<n>:IIC:SDA:SOURce` | `:BUS<N>:IIC:SDA:SOURCE` / `:BUS<>:IIC:SDA:SOUR` | 设置或查询指定解码总线为I2C解码时的数据源 | 3.4.12.2 | 62 |
| `:BUS<n>:IIC:EXCHange` | `:BUS<N>:IIC:EXCHANGE` / `:BUS<>:IIC:EXCH` | 设置指定解码总线的I2C解码时钟源和数据源进行交换，查询指定解码总线的I2C解码时钟源和数据源是否进行了交换 | 3.4.12.3 | 63 |
| `:BUS<n>:IIC:ADDBits` | `:BUS<N>:IIC:ADDBITS` / `:BUS<>:IIC:ADDB` | 设置或查询指定解码总线为I2C解码时的地址位宽 | 3.4.12.4 | 64 |
| `:BUS<n>:SPI:SCLK:SOURce` | `:BUS<N>:SPI:SCLK:SOURCE` / `:BUS<>:SPI:SCLK:SOUR` | 设置或查询指定解码总线为SPI解码时的时钟源 | 3.4.13.1 | 65 |
| `:BUS<n>:SPI:SCLK:SLOPe` | `:BUS<N>:SPI:SCLK:SLOPE` / `:BUS<>:SPI:SCLK:SLOP` | 设置或查询指定解码总线为SPI解码时的时钟边沿类型 | 3.4.13.2 | 66 |
| `:BUS<n>:SPI:MISO:SOURce` | `:BUS<N>:SPI:MISO:SOURCE` / `:BUS<>:SPI:MISO:SOUR` | 设置或查询指定解码总线为SPI解码时的MISO数据源 | 3.4.13.3 | 66 |
| `:BUS<n>:SPI:MOSI:SOURce` | `:BUS<N>:SPI:MOSI:SOURCE` / `:BUS<>:SPI:MOSI:SOUR` | 设置或查询指定解码总线为SPI解码时的MOSI数据源 | 3.4.13.4 | 67 |
| `:BUS<n>:SPI:POLarity` | `:BUS<N>:SPI:POLARITY` / `:BUS<>:SPI:POL` | 设置或查询指定解码总线为SPI数据解码时的极性 | 3.4.13.5 | 68 |
| `:BUS<n>:SPI:MISO:POLarity` | `:BUS<N>:SPI:MISO:POLARITY` / `:BUS<>:SPI:MISO:POL` | 设置或查询SPI解码时MISO数据线的极性 | 3.4.13.6 | 68 |
| `:BUS<n>:SPI:MOSI:POLarity` | `:BUS<N>:SPI:MOSI:POLARITY` / `:BUS<>:SPI:MOSI:POL` | 设置或查询SPI解码时MOSI数据线的极性 | 3.4.13.7 | 69 |
| `:BUS<n>:SPI:DBITs` | `:BUS<N>:SPI:DBITS` / `:BUS<>:SPI:DBIT` | 设置或查询指定解码总线为SPI解码时的数据位宽 | 3.4.13.8 | 70 |
| `:BUS<n>:SPI:ENDian` | `:BUS<N>:SPI:ENDIAN` / `:BUS<>:SPI:END` | 设置或查询指定解码总线为SPI解码时数据传输的位序 | 3.4.13.9 | 70 |
| `:BUS<n>:SPI:MODE` | `:BUS<N>:SPI:MODE` / `:BUS<>:SPI:MODE` | 设置或查询指定解码总线为SPI解码时的解码模式 | 3.4.13.10 | 71 |
| `:BUS<n>:SPI:TIMeout:TIME` | `:BUS<N>:SPI:TIMEOUT:TIME` / `:BUS<>:SPI:TIM:TIME` | 设置或查询指定解码总线为SPI解码时的超时时间，单位为s | 3.4.13.11 | 72 |
| `:BUS<n>:SPI:SS:SOURce` | `:BUS<N>:SPI:SS:SOURCE` / `:BUS<>:SPI:SS:SOUR` | 设置或查询指定解码总线为SPI解码时片选线的通道源 | 3.4.13.12 | 72 |
| `:BUS<n>:SPI:SS:POLarity` | `:BUS<N>:SPI:SS:POLARITY` / `:BUS<>:SPI:SS:POL` | 设置或查询指定解码总线为SPI解码时片选线的极性 | 3.4.13.13 | 73 |
| `:BUS<n>:CAN:SOURce` | `:BUS<N>:CAN:SOURCE` / `:BUS<>:CAN:SOUR` | 设置或查询指定解码总线为CAN解码时的通道源 | 3.4.14.1 | 74 |
| `:BUS<n>:CAN:STYPe` | `:BUS<N>:CAN:STYPE` / `:BUS<>:CAN:STYP` | 设置或查询指定解码总线为CAN解码时的信号类型 | 3.4.14.2 | 75 |
| `:BUS<n>:CAN:BAUD` | `:BUS<N>:CAN:BAUD` / `:BUS<>:CAN:BAUD` | 设置或查询指定解码总线为CAN解码时的信号速率，单位为bps | 3.4.14.3 | 76 |
| `:BUS<n>:CAN:FDBaud (选件)` | `:BUS<N>:CAN:FDBAUD (选件)` / `:BUS<>:CAN:FDB ()` | 设置或查询指定解码总线为CAN-FD解码时的可变速率，单位bps | 3.4.14.4 | 76 |
| `:BUS<n>:CAN:SPOint` | `:BUS<N>:CAN:SPOINT` / `:BUS<>:CAN:SPO` | 设置或查询指定解码总线为CAN解码时的采样点位置（以百分比形式表示） | 3.4.14.5 | 77 |
| `:BUS<n>:CAN:FDSPoint （选件）` | `:BUS<N>:CAN:FDSPOINT （选件）` / `:BUS<>:CAN:FDSP （）` | 设置或查询指定解码总线为CAN-FD解码时的采样点位置（以百分比形式表示） | 3.4.14.6 | 78 |
| `:BUS<n>:LIN:PARity` | `:BUS<N>:LIN:PARITY` / `:BUS<>:LIN:PAR` | 设置或查询指定解码总线的LIN解码是否包含校验位 | 3.4.15.1 | 78 |
| `:BUS<n>:LIN:SOURce` | `:BUS<N>:LIN:SOURCE` / `:BUS<>:LIN:SOUR` | 设置或查询指定解码总线为LIN解码时的信号源 | 3.4.15.2 | 79 |
| `:BUS<n>:LIN:STANdard` | `:BUS<N>:LIN:STANDARD` / `:BUS<>:LIN:STAN` | 设置或查询指定解码总线为LIN解码时的版本 | 3.4.15.3 | 80 |
| `:BUS<n>:LIN:BAUD` | `:BUS<N>:LIN:BAUD` / `:BUS<>:LIN:BAUD` | 设置或查询LIN解码的信号波特率 | 3.4.15.4 | 80 |
| `:BUS<n>:FLEXray:BAUD` | `:BUS<N>:FLEXRAY:BAUD` / `:BUS<>:FLEX:BAUD` | 设置或查询指定解码总线为FlexRay解码时的信号速率，默认单位为bps | 3.4.16.1 | 81 |
| `:BUS<n>:FLEXray:SOURce` | `:BUS<N>:FLEXRAY:SOURCE` / `:BUS<>:FLEX:SOUR` | 设置或查询指定解码总线为FlexRay解码时的通道源 | 3.4.16.2 | 82 |
| `:BUS<n>:FLEXray:SPOint` | `:BUS<N>:FLEXRAY:SPOINT` / `:BUS<>:FLEX:SPO` | 设置或查询指定解码总线为FlexRay解码时的采样点位置（以百分比形式表示） | 3.4.16.3 | 82 |
| `:BUS<n>:FLEXray:STYPe` | `:BUS<N>:FLEXRAY:STYPE` / `:BUS<>:FLEX:STYP` | 设置或查询指定解码总线为FlexRay解码时的信号类型 | 3.4.16.4 | 83 |
| `:BUS<n>:FLEXray:CHANnel` | `:BUS<N>:FLEXRAY:CHANNEL` / `:BUS<>:FLEX:CHAN` | 设置或查询指定解码总线的FlexRay解码时的信道选择 | 3.4.16.5 | 84 |
| `:BUS<n>:IIS:SOURce:CLOCk` | `:BUS<N>:IIS:SOURCE:CLOCK` / `:BUS<>:IIS:SOUR:CLOC` | 设置或查询指定解码总线为I2S解码时的时钟源 | 3.4.17.1 | 84 |
| `:BUS<n>:IIS:SOURce:DATA` | `:BUS<N>:IIS:SOURCE:DATA` / `:BUS<>:IIS:SOUR:DATA` | 设置或查询指定解码总线为I2S解码时的数据源 | 3.4.17.2 | 85 |
| `:BUS<n>:IIS:SOURce:WSELect` | `:BUS<N>:IIS:SOURCE:WSELECT` / `:BUS<>:IIS:SOUR:WSEL` | 设置或查询指定解码总线为I2S解码时的声道(WS)信号源 | 3.4.17.3 | 86 |
| `:BUS<n>:IIS:ALIGnment` | `:BUS<N>:IIS:ALIGNMENT` / `:BUS<>:IIS:ALIG` | 设置或查询指定解码总线为I2S解码时的对齐方式 | 3.4.17.4 | 86 |
| `:BUS<n>:IIS:CLOCk:SLOPe` | `:BUS<N>:IIS:CLOCK:SLOPE` / `:BUS<>:IIS:CLOC:SLOP` | 设置或查询指定解码总线为I2S解码时的时钟边沿类型 | 3.4.17.5 | 87 |
| `:BUS<n>:IIS:RWIDth` | `:BUS<N>:IIS:RWIDTH` / `:BUS<>:IIS:RWID` | 设置或查询指定解码总线为I2S解码时的字位宽 | 3.4.17.6 | 88 |
| `:BUS<n>:IIS:RECewidth` | `:BUS<N>:IIS:RECEWIDTH` / `:BUS<>:IIS:REC` | 设置或查询指定解码总线的I2S解码的接收位宽 | 3.4.17.7 | 88 |
| `:BUS<n>:IIS:WSLow` | `:BUS<N>:IIS:WSLOW` / `:BUS<>:IIS:WSL` | 设置或查询指定解码总线为I2S解码时的声道极性 | 3.4.17.8 | 89 |
| `:BUS<n>:IIS:ENDian` | `:BUS<N>:IIS:ENDIAN` / `:BUS<>:IIS:END` | 设置或查询指定解码总线为I2S解码时的位序 | 3.4.17.9 | 89 |
| `:BUS<n>:IIS:POLarity` | `:BUS<N>:IIS:POLARITY` / `:BUS<>:IIS:POL` | 设置或查询指定解码总线为I2S解码时的数据极性 | 3.4.17.10 | 90 |
| `:BUS<n>:M1553:SOURce` | `:BUS<N>:M1553:SOURCE` / `:BUS<>:M1553:SOUR` | 设置或查询指定解码总线为M1553解码时的信源 | 3.4.18.1 | 91 |

<details><summary>3.4 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.4.1 | `:BUS<n>:MODE <mode>` ; `:BUS<n>:MODE?` |
| 3.4.2 | `:BUS<n>:DISPlay <bool>` ; `:BUS<n>:DISPlay?` |
| 3.4.3 | `:BUS<n>:FORMat <format>` ; `:BUS<n>:FORMat?` |
| 3.4.4 | `:BUS<n>:EVENt <bool>` ; `:BUS<n>:EVENt?` |
| 3.4.5 | `:BUS<n>:LABel <bool>` ; `:BUS<n>:LABel?` |
| 3.4.6 | `:BUS<n>:DATA?` |
| 3.4.7 | `:BUS<n>:EEXPort <path>` |
| 3.4.8 | `:BUS<n>:POSition <pos>` ; `:BUS<n>:POSition?` |
| 3.4.9 | `:BUS<n>:THReshold <value>,<type>` ; `:BUS<n>:THReshold? <type>` |
| 3.4.10.1 | `:BUS<n>:PARallel:BUS <source>` ; `:BUS<n>:PARallel:BUS?` |
| 3.4.10.2 | `:BUS<n>:PARallel:CLK <source>` ; `:BUS<n>:PARallel:CLK?` |
| 3.4.10.3 | `:BUS<n>:PARallel:SLOPe <slope>` ; `:BUS<n>:PARallel:SLOPe?` |
| 3.4.10.4 | `:BUS<n>:PARallel:WIDTh <wid>` ; `:BUS<n>:PARallel:WIDTh?` |
| 3.4.10.5 | `:BUS<n>:PARallel:BITX <bit>` ; `:BUS<n>:PARallel:BITX?` |
| 3.4.10.6 | `:BUS<n>:PARallel:SOURce <src>` ; `:BUS<n>:PARallel:SOURce?` |
| 3.4.10.7 | `:BUS <n>:PARallel:ENDian <pol>` ; `:BUS <n>:PARallel:ENDian?` |
| 3.4.10.8 | `:BUS<n>:PARallel:POLarity <pol>` ; `:BUS<n>:PARallel:POLarity?` |
| 3.4.11.1 | `:BUS<n>:RS232:TX <source>` ; `:BUS<n>:RS232:TX?` |
| 3.4.11.2 | `:BUS<n>:RS232:RX <source>` ; `:BUS<n>:RS232:RX?` |
| 3.4.11.3 | `:BUS<n>:RS232:POLarity <pol>` ; `:BUS<n>:RS232:POLarity?` |
| 3.4.11.4 | `:BUS<n>:RS232:PARity <parity>` ; `:BUS<n>:RS232:PARity?` |
| 3.4.11.5 | `:BUS<n>:RS232:ENDian <endian>` ; `:BUS<n>:RS232:ENDian?` |
| 3.4.11.6 | `:BUS<n>:RS232:BAUD <baud>` ; `:BUS<n>:RS232:BAUD?` |
| 3.4.11.7 | `:BUS<n>:RS232:DBITs <bits>` ; `:BUS<n>:RS232:DBITs?` |
| 3.4.11.8 | `:BUS<n>:RS232:SBITs <stop bits>` ; `:BUS<n>:RS232:SBITs?` |
| 3.4.12.1 | `:BUS<n>:IIC:SCLK:SOURce <source>` ; `:BUS<n>:IIC:SCLK:SOURce?` |
| 3.4.12.2 | `:BUS<n>:IIC:SDA:SOURce <source>` ; `:BUS<n>:IIC:SDA:SOURce?` |
| 3.4.12.3 | `:BUS<n>:IIC:EXCHange <bool>` ; `:BUS<n>:IIC:EXCHange?` |
| 3.4.12.4 | `:BUS<n>:IIC:ADDBits <bits>` ; `:BUS<n>:IIC:ADDBits?` |
| 3.4.13.1 | `:BUS<n>:SPI:SCLK:SOURce <source>` ; `:BUS<n>:SPI:SCLK:SOURce?` |
| 3.4.13.2 | `:BUS<n>:SPI:SCLK:SLOPe <slope>` ; `:BUS<n>:SPI:SCLK:SLOPe?` |
| 3.4.13.3 | `:BUS<n>:SPI:MISO:SOURce <source>` ; `:BUS<n>:SPI:MISO:SOURce?` |
| 3.4.13.4 | `:BUS<n>:SPI:MOSI:SOURce <source>` ; `:BUS<n>:SPI:MOSI:SOURce?` |
| 3.4.13.5 | `:BUS<n>:SPI:POLarity <polarity>` ; `:BUS<n>:SPI:POLarity?` |
| 3.4.13.6 | `:BUS<n>:SPI:MISO:POLarity <polarity>` ; `:BUS<n>:SPI:MISO:POLarity?` |
| 3.4.13.7 | `:BUS<n>:SPI:MOSI:POLarity <polarity>` ; `:BUS<n>:SPI:MOSI:POLarity?` |
| 3.4.13.8 | `:BUS<n>:SPI:DBITs <width>` ; `:BUS<n>:SPI:DBITs?` |
| 3.4.13.9 | `:BUS<n>:SPI:ENDian <endian>` ; `:BUS<n>:SPI:ENDian?` |
| 3.4.13.10 | `:BUS<n>:SPI:MODE <mode>` ; `:BUS<n>:SPI:MODE?` |
| 3.4.13.11 | `:BUS<n>:SPI:TIMeout:TIME <time>` ; `:BUS<n>:SPI:TIMeout:TIME?` |
| 3.4.13.12 | `:BUS<n>:SPI:SS:SOURce <source>` ; `:BUS<n>:SPI:SS:SOURce?` |
| 3.4.13.13 | `:BUS<n>:SPI:SS:POLarity <polarity>` ; `:BUS<n>:SPI:SS:POLarity?` |
| 3.4.14.1 | `:BUS<n>:CAN:SOURce <source>` ; `:BUS<n>:CAN:SOURce?` |
| 3.4.14.2 | `:BUS<n>:CAN:STYPe <stype>` ; `:BUS<n>:CAN:STYPe?` |
| 3.4.14.3 | `:BUS<n>:CAN:BAUD <baud>` ; `:BUS<n>:CAN:BAUD?` |
| 3.4.14.4 | `:BUS<n>:CAN:FDBaud <baud>` ; `:BUS<n>:CAN:FDBaud?` |
| 3.4.14.5 | `:BUS<n>:CAN:SPOint <spoint>` ; `:BUS<n>:CAN:SPOint?` |
| 3.4.14.6 | `:BUS<n>:CAN:FDSPoint <spoint>` ; `:BUS<n>:CAN:FDSPoint?` |
| 3.4.15.1 | `:BUS<n>:LIN:PARity <bool>` ; `:BUS<n>:LIN:PARity?` |
| 3.4.15.2 | `:BUS<n>:LIN:SOURce <source>` ; `:BUS<n>:LIN:SOURce?` |
| 3.4.15.3 | `:BUS<n>:LIN:STANdard <value>` ; `:BUS<n>:LIN:STANdard?` |
| 3.4.15.4 | `:BUS<n>:LIN:BAUD <baud>` ; `:BUS<n>:LIN:BAUD?` |
| 3.4.16.1 | `:BUS<n>:FLEXray:BAUD <baud>` ; `:BUS<n>:FLEXray:BAUD?` |
| 3.4.16.2 | `:BUS<n>:FLEXray:SOURce <source>` ; `:BUS<n>:FLEXray:SOURce?` |
| 3.4.16.3 | `:BUS<n>:FLEXray:SPOint <spoint>` ; `:BUS<n>:FLEXray:SPOint?` |
| 3.4.16.4 | `:BUS<n>:FLEXray:STYPe <stype>` ; `:BUS<n>:FLEXray:STYPe?` |
| 3.4.16.5 | `:BUS <n>:FLEXray:CHANnel <ch>` ; `:BUS <n>:FLEXray:CHANnel?` |
| 3.4.17.1 | `:BUS<n>:IIS:SOURce:CLOCk <source>` ; `:BUS<n>:IIS:SOURce:CLOCk?` |
| 3.4.17.2 | `:BUS<n>:IIS:SOURce:DATA <source>` ; `:BUS<n>:IIS:SOURce:DATA?` |
| 3.4.17.3 | `:BUS<n>:IIS:SOURce:WSELect <source>` ; `:BUS<n>:IIS:SOURce:WSELect?` |
| 3.4.17.4 | `:BUS<n>:IIS:ALIGnment <align>` ; `:BUS<n>:IIS:ALIGnment?` |
| 3.4.17.5 | `:BUS<n>:IIS:CLOCk:SLOPe <slope>` ; `:BUS<n>:IIS:CLOCk:SLOPe?` |
| 3.4.17.6 | `:BUS<n>:IIS:RWIDth <val>` ; `:BUS<n>:IIS:RWIDth?` |
| 3.4.17.7 | `:BUS<n>:IIS:RECewidth <val>` ; `:BUS<n>:IIS:RECewidth?` |
| 3.4.17.8 | `:BUS<n>:IIS:WSLow <val>` ; `:BUS<n>:IIS:WSLow?` |
| 3.4.17.9 | `:BUS<n>:IIS:ENDian <endian>` ; `:BUS<n>:IIS:ENDian?` |
| 3.4.17.10 | `:BUS<n>:IIS:POLarity <pol>` ; `:BUS<n>:IIS:POLarity?` |
| 3.4.18.1 | `:BUS<n>:M1553:SOURce <source>` ; `:BUS<n>:M1553:SOURce?` |

</details>

## 3.5 伯德图命令子系统 （选件）

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:BODeplot:ENABle` | `:BODEPLOT:ENABLE` / `:BOD:ENAB` | 设置或查询伯德图功能的使能状态 | 3.5.1 | 92 |
| `:BODeplot:RUNStop` | `:BODEPLOT:RUNSTOP` / `:BOD:RUNS` | 设置或查询伯德图运行状态 | 3.5.2 | 92 |
| `:BODeplot:SWEeptype` | `:BODEPLOT:SWEEPTYPE` / `:BOD:SWE` | 设置或查询伯德图的扫频类型 | 3.5.3 | 93 |
| `:BODeplot:REF:IN` | `:BODEPLOT:REF:IN` / `:BOD:REF:IN` | 设置或查询伯德图输入源 | 3.5.4 | 94 |
| `:BODeplot:REF:OUT` | `:BODEPLOT:REF:OUT` / `:BOD:REF:OUT` | 设置或查询伯德图输出源 | 3.5.5 | 94 |
| `:BODeplot:STARt` | `:BODEPLOT:START` / `:BOD:STAR` | 设置或查询伯德图功能扫频信号的起始频率，默认单位为Hz | 3.5.6 | 95 |
| `:BODeplot:STOP` | `:BODEPLOT:STOP` / `:BOD:STOP` | 设置或查询伯德图功能扫频信号的终止频率，默认单位为Hz | 3.5.7 | 95 |
| `:BODeplot:POINts` | `:BODEPLOT:POINTS` / `:BOD:POIN` | 设置或查询十倍频点数 | 3.5.8 | 96 |
| `:BODeplot:VOLTage` | `:BODEPLOT:VOLTAGE` / `:BOD:VOLT` | 设置或查询伯德图功能指定频率范围的扫频信号的电压幅值，电压默认单位为V，频率默认单位为Hz | 3.5.9 | 97 |
| `:BODeplot:GAINcurve:ENABle` | `:BODEPLOT:GAINCURVE:ENABLE` / `:BOD:GAIN:ENAB` | 设置或查询是否显示幅频曲线 | 3.5.10 | 97 |
| `:BODeplot:PHASEcurve:ENABle` | `:BODEPLOT:PHASECURVE:ENABLE` / `:BOD:PHASE:ENAB` | 设置或查询是否显示相频曲线 | 3.5.11 | 98 |

<details><summary>3.5 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.5.1 | `:BODeplot:ENABle <bool>` ; `:BODeplot:ENABle?` |
| 3.5.2 | `:BODeplot:RUNStop <bool>` ; `:BODeplot:RUNStop?` |
| 3.5.3 | `:BODeplot:SWEeptype <type>` ; `:BODeplot:SWEeptype?` |
| 3.5.4 | `:BODeplot:REF:IN <source>` ; `:BODeplot:REF:IN?` |
| 3.5.5 | `:BODeplot:REF:OUT <source>` ; `:BODeplot:REF:OUT?` |
| 3.5.6 | `:BODeplot:STARt <freq>` ; `:BODeplot:STARt?` |
| 3.5.7 | `:BODeplot:STOP <freq>` ; `:BODeplot:STOP?` |
| 3.5.8 | `:BODeplot:POINts <num>` ; `:BODeplot:POINts?` |
| 3.5.9 | `:BODeplot:VOLTage <range>,<amp>` ; `:BODeplot:VOLTage? <range>` |
| 3.5.10 | `:BODeplot:GAINcurve:ENABle <bool>` ; `:BODeplot:GAINcurve:ENABle?` |
| 3.5.11 | `:BODeplot:PHASEcurve:ENABle <bool>` ; `:BODeplot:PHASEcurve:ENABle?` |

</details>

## 3.6 通道命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:CHANnel<n>:BWLimit` | `:CHANNEL<N>:BWLIMIT` / `:CHAN<>:BWL` | 设置或查询指定通道的带宽限制参数 | 3.6.1 | 99 |
| `:CHANnel<n>:COUPling` | `:CHANNEL<N>:COUPLING` / `:CHAN<>:COUP` | 设置或查询指定通道的耦合方式 | 3.6.2 | 100 |
| `:CHANnel<n>:DISPlay` | `:CHANNEL<N>:DISPLAY` / `:CHAN<>:DISP` | 打开或关闭指定通道，或查询指定通道的开关状态 | 3.6.3 | 100 |
| `:CHANnel<n>:INVert` | `:CHANNEL<N>:INVERT` / `:CHAN<>:INV` | 打开或关闭指定通道的波形反相，或查询指定通道波形反相的开关状态 | 3.6.4 | 101 |
| `:CHANnel<n>:OFFSet` | `:CHANNEL<N>:OFFSET` / `:CHAN<>:OFFS` | 设置或查询指定通道的垂直偏移，默认单位为V | 3.6.5 | 102 |
| `:CHANnel<n>:TCALibrate` | `:CHANNEL<N>:TCALIBRATE` / `:CHAN<>:TCAL` | 设置或查询指定通道的延时校正时间，用于校正对应通道的零点偏移，单位为s | 3.6.6 | 103 |
| `:CHANnel<n>:IMPedance` | `:CHANNEL<N>:IMPEDANCE` / `:CHAN<>:IMP` | 设置或查询指定模拟通道的输入阻抗 | 3.6.7 | 103 |
| `:CHANnel<n>:SCALe` | `:CHANNEL<N>:SCALE` / `:CHAN<>:SCAL` | 设置或查询指定通道的垂直档位，单位默认为V/div | 3.6.8 | 104 |
| `:CHANnel<n>:PROBe` | `:CHANNEL<N>:PROBE` / `:CHAN<>:PROB` | 设置或查询指定通道的探头比 | 3.6.9 | 105 |
| `:CHANnel<n>:LABel:SHOW` | `:CHANNEL<N>:LABEL:SHOW` / `:CHAN<>:LAB:SHOW` | 设置或查询指定通道标签的显示状态 | 3.6.10 | 106 |
| `:CHANnel<n>:LABel:CONTent` | `:CHANNEL<N>:LABEL:CONTENT` / `:CHAN<>:LAB:CONT` | 设置或查询指定通道的标签 | 3.6.11 | 106 |
| `:CHANnel<n>:UNITs` | `:CHANNEL<N>:UNITS` / `:CHAN<>:UNIT` | 设置或查询指定通道的幅度显示单位 | 3.6.12 | 107 |
| `:CHANnel<n>:VERNier` | `:CHANNEL<N>:VERNIER` / `:CHAN<>:VERN` | 打开或关闭指定通道垂直档位的微调功能，或查询指定通道垂直档位的微调功能状态 | 3.6.13 | 107 |
| `:CHANnel<n>:POSition` | `:CHANNEL<N>:POSITION` / `:CHAN<>:POS` | 设置或查询指定通道的偏置电压，单位默认为V | 3.6.14 | 108 |

<details><summary>3.6 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.6.1 | `:CHANnel<n>:BWLimit <val>` ; `:CHANnel<n>:BWLimit?` |
| 3.6.2 | `:CHANnel<n>:COUPling <coupling>` ; `:CHANnel<n>:COUPling?` |
| 3.6.3 | `:CHANnel<n>:DISPlay <bool>` ; `:CHANnel<n>:DISPlay?` |
| 3.6.4 | `:CHANnel<n>:INVert <bool>` ; `:CHANnel<n>:INVert?` |
| 3.6.5 | `:CHANnel<n>:OFFSet <offset>` ; `:CHANnel<n>:OFFSet?` |
| 3.6.6 | `:CHANnel<n>:TCALibrate <val>` ; `:CHANnel<n>:TCALibrate?` |
| 3.6.7 | `:CHANnel<n>:IMPedance <impedance>` ; `:CHANnel<n>:IMPedance?` |
| 3.6.8 | `:CHANnel<n>:SCALe <scale>` ; `:CHANnel<n>:SCALe?` |
| 3.6.9 | `:CHANnel<n>:PROBe <atten>` ; `:CHANnel<n>:PROBe?` |
| 3.6.10 | `:CHANnel<n>:LABel:SHOW <bool>` ; `:CHANnel<n>:LABel:SHOW?` |
| 3.6.11 | `:CHANnel<n>:LABel:CONTent <str>` ; `:CHANnel<n>:LABel:CONTent?` |
| 3.6.12 | `:CHANnel<n>:UNITs <units>` ; `:CHANnel<n>:UNITs?` |
| 3.6.13 | `:CHANnel<n>:VERNier <bool>` ; `:CHANnel<n>:VERNier?` |
| 3.6.14 | `:CHANnel<n>:POSition <offset>` ; `:CHANnel<n>:POSition?` |

</details>

## 3.7 频率计命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:COUNter:CURRent?` | `:COUNTER:CURRENT?` / `:COUN:CURR?` | 查询频率计测量值 | 3.7.1 | 109 |
| `:COUNter:ENABle` | `:COUNTER:ENABLE` / `:COUN:ENAB` | 打开或关闭频率计，或查询频率计开关的状态 | 3.7.2 | 110 |
| `:COUNter:SOURce` | `:COUNTER:SOURCE` / `:COUN:SOUR` | 设置或查询频率计信源 | 3.7.3 | 110 |
| `:COUNter:MODE` | `:COUNTER:MODE` / `:COUN:MODE` | 设置或查询频率计模式 | 3.7.4 | 111 |
| `:COUNter:NDIGits` | `:COUNTER:NDIGITS` / `:COUN:NDIG` | 设置或查询频率计分辨率 | 3.7.5 | 111 |
| `:COUNter:TOTalize:ENABle` | `:COUNTER:TOTALIZE:ENABLE` / `:COUN:TOT:ENAB` | 打开或关闭频率计统计功能，或查询频率计统计功能的状态 | 3.7.6 | 112 |
| `:COUNter:TOTalize:CLEar` | `:COUNTER:TOTALIZE:CLEAR` / `:COUN:TOT:CLE` | 清除总计数 | 3.7.7 | 113 |

<details><summary>3.7 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.7.1 | `:COUNter:CURRent?` |
| 3.7.2 | `:COUNter:ENABle <bool>` ; `:COUNter:ENABle?` |
| 3.7.3 | `:COUNter:SOURce <source>` ; `:COUNter:SOURce?` |
| 3.7.4 | `:COUNter:MODE <mode>` ; `:COUNter:MODE?` |
| 3.7.5 | `:COUNter:NDIGits <val>` ; `:COUNter:NDIGits?` |
| 3.7.6 | `:COUNter:TOTalize:ENABle <bool>` ; `:COUNter:TOTalize:ENABle?` |
| 3.7.7 | `:COUNter:TOTalize:CLEar` |

</details>

## 3.8 光标命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:CURSor:MODE` | `:CURSOR:MODE` / `:CURS:MODE` | 设置或查询光标测量的模式 | 3.8.1 | 114 |
| `:CURSor:MEASure:INDicator` | `:CURSOR:MEASURE:INDICATOR` / `:CURS:MEAS:IND` | 设置或查询测量功能的光标指示的状态为打开或关闭 | 3.8.2 | 115 |
| `:CURSor:MANual:TYPE` | `:CURSOR:MANUAL:TYPE` / `:CURS:MAN:TYPE` | 设置或查询手动光标的光标类型 | 3.8.3.1 | 116 |
| `:CURSor:MANual:SOURce` | `:CURSOR:MANUAL:SOURCE` / `:CURS:MAN:SOUR` | 设置或查询手动光标的通道源 | 3.8.3.2 | 116 |
| `:CURSor:MANual:TUNit` | `:CURSOR:MANUAL:TUNIT` / `:CURS:MAN:TUN` | 设置或查询手动光标测量模式下的水平单位 | 3.8.3.3 | 117 |
| `:CURSor:MANual:VUNit` | `:CURSOR:MANUAL:VUNIT` / `:CURS:MAN:VUN` | 设置或查询手动光标测量模式下的垂直单位 | 3.8.3.4 | 118 |
| `:CURSor:MANual:CAX` | `:CURSOR:MANUAL:CAX` / `:CURS:MAN:CAX` | 设置或查询手动光标测量时，光标A的水平位置 | 3.8.3.5 | 118 |
| `:CURSor:MANual:CAY` | `:CURSOR:MANUAL:CAY` / `:CURS:MAN:CAY` | 设置或查询手动光标测量时，光标A的垂直位置 | 3.8.3.6 | 119 |
| `:CURSor:MANual:CBX` | `:CURSOR:MANUAL:CBX` / `:CURS:MAN:CBX` | 设置或查询手动光标测量时，光标B的水平位置 | 3.8.3.7 | 119 |
| `:CURSor:MANual:CBY` | `:CURSOR:MANUAL:CBY` / `:CURS:MAN:CBY` | 设置或查询手动光标测量时，光标B的垂直位置 | 3.8.3.8 | 120 |
| `:CURSor:MANual:AXValue?` | `:CURSOR:MANUAL:AXVALUE?` / `:CURS:MAN:AXV?` | 查询手动光标测量时，光标A处的X值 | 3.8.3.9 | 120 |
| `:CURSor:MANual:AYValue?` | `:CURSOR:MANUAL:AYVALUE?` / `:CURS:MAN:AYV?` | 查询手动光标测量时，光标A处的Y值 | 3.8.3.10 | 121 |
| `:CURSor:MANual:BXValue?` | `:CURSOR:MANUAL:BXVALUE?` / `:CURS:MAN:BXV?` | 查询手动光标测量时，光标B处的X值 | 3.8.3.11 | 121 |
| `:CURSor:MANual:BYValue?` | `:CURSOR:MANUAL:BYVALUE?` / `:CURS:MAN:BYV?` | 查询手动光标测量时，光标B处的Y值 | 3.8.3.12 | 122 |
| `:CURSor:MANual:XDELta?` | `:CURSOR:MANUAL:XDELTA?` / `:CURS:MAN:XDEL?` | 查询手动光标测量时，光标A处和光标B处的X值之间的差值∆X | 3.8.3.13 | 122 |
| `:CURSor:MANual:IXDelta?` | `:CURSOR:MANUAL:IXDELTA?` / `:CURS:MAN:IXD?` | 查询手动光标测量时，光标A处和光标B处的X值之差的绝对值的倒数1/∆X | 3.8.3.14 | 123 |
| `:CURSor:MANual:YDELta?` | `:CURSOR:MANUAL:YDELTA?` / `:CURS:MAN:YDEL?` | 查询手动光标测量时，光标A处和光标B处的Y值之间的差值∆Y | 3.8.3.15 | 123 |
| `:CURSor:TRACk:SOURce1` | `:CURSOR:TRACK:SOURCE1` / `:CURS:TRAC:SOUR1` | 设置或查询光标追踪测量时，光标A测量的通道源 | 3.8.4.1 | 124 |
| `:CURSor:TRACk:SOURce2` | `:CURSOR:TRACK:SOURCE2` / `:CURS:TRAC:SOUR2` | 设置或查询光标追踪测量时，光标B测量的通道源 | 3.8.4.2 | 124 |
| `:CURSor:TRACk:CAX` | `:CURSOR:TRACK:CAX` / `:CURS:TRAC:CAX` | 设置或查询光标追踪测量时，光标A的水平位置 | 3.8.4.3 | 125 |
| `:CURSor:TRACk:CBX` | `:CURSOR:TRACK:CBX` / `:CURS:TRAC:CBX` | 设置或查询光标追踪测量时，光标B的水平位置 | 3.8.4.4 | 126 |
| `:CURSor:TRACk:CAY` | `:CURSOR:TRACK:CAY` / `:CURS:TRAC:CAY` | 设置或查询光标追踪测量时，光标A的垂直位置 | 3.8.4.5 | 126 |
| `:CURSor:TRACk:CBY` | `:CURSOR:TRACK:CBY` / `:CURS:TRAC:CBY` | 设置或查询光标追踪测量时，光标B的垂直位置 | 3.8.4.6 | 127 |
| `:CURSor:TRACk:AXValue?` | `:CURSOR:TRACK:AXVALUE?` / `:CURS:TRAC:AXV?` | 查询光标追踪测量时，光标A处的X值 | 3.8.4.7 | 127 |
| `:CURSor:TRACk:AYValue?` | `:CURSOR:TRACK:AYVALUE?` / `:CURS:TRAC:AYV?` | 查询光标追踪测量时，光标A处的Y值 | 3.8.4.8 | 128 |
| `:CURSor:TRACk:BXValue?` | `:CURSOR:TRACK:BXVALUE?` / `:CURS:TRAC:BXV?` | 查询光标追踪测量时，光标B处的X值 | 3.8.4.9 | 128 |
| `:CURSor:TRACk:BYValue?` | `:CURSOR:TRACK:BYVALUE?` / `:CURS:TRAC:BYV?` | 查询光标追踪测量时，光标B处的Y值 | 3.8.4.10 | 129 |
| `:CURSor:TRACk:XDELta?` | `:CURSOR:TRACK:XDELTA?` / `:CURS:TRAC:XDEL?` | 查询光标追踪测量时，光标A处和光标B处的X值之间的差值∆X | 3.8.4.11 | 129 |
| `:CURSor:TRACk:YDELta?` | `:CURSOR:TRACK:YDELTA?` / `:CURS:TRAC:YDEL?` | 查询光标追踪测量时，光标A处和光标B处的Y值之间的差值∆Y | 3.8.4.12 | 129 |
| `:CURSor:TRACk:IXDelta?` | `:CURSOR:TRACK:IXDELTA?` / `:CURS:TRAC:IXD?` | 查询光标追踪测量时，光标A处和光标B处的X值之差的绝对值的倒数1/∆X | 3.8.4.13 | 130 |
| `:CURSor:TRACk:MODE` | `:CURSOR:TRACK:MODE` / `:CURS:TRAC:MODE` | 设置或查询光标追踪测量时的坐标轴 | 3.8.4.14 | 130 |
| `:CURSor:XY:AX` | `:CURSOR:XY:AX` / `:CURS:XY:AX` | 设置或查询XY光标测量时，光标A的水平位置 | 3.8.5.1 | 131 |
| `:CURSor:XY:BX` | `:CURSOR:XY:BX` / `:CURS:XY:BX` | 设置或查询XY光标测量时，光标B的水平位置 | 3.8.5.2 | 132 |
| `:CURSor:XY:AY` | `:CURSOR:XY:AY` / `:CURS:XY:AY` | 设置或查询XY光标测量时，光标A的垂直位置 | 3.8.5.3 | 132 |
| `:CURSor:XY:BY` | `:CURSOR:XY:BY` / `:CURS:XY:BY` | 设置或查询XY光标测量时，光标B的垂直位置 | 3.8.5.4 | 133 |
| `:CURSor:XY:AXValue?` | `:CURSOR:XY:AXVALUE?` / `:CURS:XY:AXV?` | 查询XY光标测量时，光标A处的X值 | 3.8.5.5 | 133 |
| `:CURSor:XY:AYValue?` | `:CURSOR:XY:AYVALUE?` / `:CURS:XY:AYV?` | 查询XY光标测量时，光标A处的Y值 | 3.8.5.6 | 134 |
| `:CURSor:XY:BXValue?` | `:CURSOR:XY:BXVALUE?` / `:CURS:XY:BXV?` | 查询XY光标测量时，手动光标模式，光标B处的X值 | 3.8.5.7 | 134 |
| `:CURSor:XY:BYValue?` | `:CURSOR:XY:BYVALUE?` / `:CURS:XY:BYV?` | 查询XY光标测量时，手动光标模式，光标B处的Y值 | 3.8.5.8 | 135 |
| `:CURSor:XY:XDELta?` | `:CURSOR:XY:XDELTA?` / `:CURS:XY:XDEL?` | 查询XY光标测量时，光标A处与光标B处的X值之间的差值∆X | 3.8.5.9 | 135 |
| `:CURSor:XY:YDELta?` | `:CURSOR:XY:YDELTA?` / `:CURS:XY:YDEL?` | 查询XY光标测量时，光标A处与光标B处的Y值之间的差值∆Y | 3.8.5.10 | 135 |

<details><summary>3.8 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.8.1 | `:CURSor:MODE <mode>` ; `:CURSor:MODE?` |
| 3.8.2 | `:CURSor:MEASure:INDicator <bool>` ; `:CURSor:MEASure:INDicator?` |
| 3.8.3.1 | `:CURSor:MANual:TYPE <type>` ; `:CURSor:MANual:TYPE?` |
| 3.8.3.2 | `:CURSor:MANual:SOURce <source>` ; `:CURSor:MANual:SOURce?` |
| 3.8.3.3 | `:CURSor:MANual:TUNit <tunit>` ; `:CURSor:MANual:TUNit?` |
| 3.8.3.4 | `:CURSor:MANual:VUNit <vunit>` ; `:CURSor:MANual:VUNit?` |
| 3.8.3.5 | `:CURSor:MANual:CAX <ax>` ; `:CURSor:MANual:CAX?` |
| 3.8.3.6 | `:CURSor:MANual:CAY <ay>` ; `:CURSor:MANual:CAY?` |
| 3.8.3.7 | `:CURSor:MANual:CBX <bx>` ; `:CURSor:MANual:CBX?` |
| 3.8.3.8 | `:CURSor:MANual:CBY <by>` ; `:CURSor:MANual:CBY?` |
| 3.8.3.9 | `:CURSor:MANual:AXValue?` |
| 3.8.3.10 | `:CURSor:MANual:AYValue?` |
| 3.8.3.11 | `:CURSor:MANual:BXValue?` |
| 3.8.3.12 | `:CURSor:MANual:BYValue?` |
| 3.8.3.13 | `:CURSor:MANual:XDELta?` |
| 3.8.3.14 | `:CURSor:MANual:IXDelta?` |
| 3.8.3.15 | `:CURSor:MANual:YDELta?` |
| 3.8.4.1 | `:CURSor:TRACk:SOURce1 <source>` ; `:CURSor:TRACk:SOURce1?` |
| 3.8.4.2 | `:CURSor:TRACk:SOURce2 <source>` ; `:CURSor:TRACk:SOURce2?` |
| 3.8.4.3 | `:CURSor:TRACk:CAX <ax>` ; `:CURSor:TRACk:CAX?` |
| 3.8.4.4 | `:CURSor:TRACk:CBX <bx>` ; `:CURSor:TRACk:CBX?` |
| 3.8.4.5 | `:CURSor:TRACk:CAY <ay>` ; `:CURSor:TRACk:CAY?` |
| 3.8.4.6 | `:CURSor:TRACk:CBY <by>` ; `:CURSor:TRACk:CBY?` |
| 3.8.4.7 | `:CURSor:TRACk:AXValue?` |
| 3.8.4.8 | `:CURSor:TRACk:AYValue?` |
| 3.8.4.9 | `:CURSor:TRACk:BXValue?` |
| 3.8.4.10 | `:CURSor:TRACk:BYValue?` |
| 3.8.4.11 | `:CURSor:TRACk:XDELta?` |
| 3.8.4.12 | `:CURSor:TRACk:YDELta?` |
| 3.8.4.13 | `:CURSor:TRACk:IXDelta?` |
| 3.8.4.14 | `:CURSor:TRACk:MODE <mode>` ; `:CURSor:TRACk:MODE?` |
| 3.8.5.1 | `:CURSor:XY:AX <x>` ; `:CURSor:XY:AX?` |
| 3.8.5.2 | `:CURSor:XY:BX <x>` ; `:CURSor:XY:BX?` |
| 3.8.5.3 | `:CURSor:XY:AY <y>` ; `:CURSor:XY:AY?` |
| 3.8.5.4 | `:CURSor:XY:BY <y>` ; `:CURSor:XY:BY?` |
| 3.8.5.5 | `:CURSor:XY:AXValue?` |
| 3.8.5.6 | `:CURSor:XY:AYValue?` |
| 3.8.5.7 | `:CURSor:XY:BXValue?` |
| 3.8.5.8 | `:CURSor:XY:BYValue?` |
| 3.8.5.9 | `:CURSor:XY:XDELta?` |
| 3.8.5.10 | `:CURSor:XY:YDELta?` |

</details>

## 3.9 显示命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:DISPlay:CLEar` | `:DISPLAY:CLEAR` / `:DISP:CLE` | 清除屏幕上的所有波形 | 3.9.1 | 136 |
| `:DISPlay:TYPE` | `:DISPLAY:TYPE` / `:DISP:TYPE` | 设置或查询屏幕中波形的显示方式 | 3.9.2 | 137 |
| `:DISPlay:GRADing:TIME` | `:DISPLAY:GRADING:TIME` / `:DISP:GRAD:TIME` | 设置或查询余辉时间，默认单位为s | 3.9.3 | 137 |
| `:DISPlay:WBRightness` | `:DISPLAY:WBRIGHTNESS` / `:DISP:WBR` | 设置或查询屏幕中波形显示的亮度，以百分数表示 | 3.9.4 | 138 |
| `:DISPlay:GRID` | `:DISPLAY:GRID` / `:DISP:GRID` | 设置或查询屏幕显示的网格类型 | 3.9.5 | 139 |
| `:DISPlay:GBRightness` | `:DISPLAY:GBRIGHTNESS` / `:DISP:GBR` | 设置或查询屏幕网格的亮度，以百分数表示 | 3.9.6 | 139 |
| `:DISPlay:CBRightness` | `:DISPLAY:CBRIGHTNESS` / `:DISP:CBR` | 设置或查询光标的亮度，以百分数表示 | 3.9.7 | 140 |
| `:DISPlay:DATA?` | `:DISPLAY:DATA?` / `:DISP:DATA?` | 查询当前显示图像的位图数据流 | 3.9.8 | 140 |
| `:DISPlay:RULers` | `:DISPLAY:RULERS` / `:DISP:RUL` | 打开或关闭标尺显示，或查询标尺的开关状态 | 3.9.9 | 141 |
| `:DISPlay:MOVE` | `:DISPLAY:MOVE` / `:DISP:MOVE` | 设置或查询标尺是否随波形坐标移动 | 3.9.10 | 141 |
| `:DISPlay:COLor` | `:DISPLAY:COLOR` / `:DISP:COL` | 打开或关闭色温显示，或查询色温的开关状态 | 3.9.11 | 142 |
| `:DISPlay:WHOLd` | `:DISPLAY:WHOLD` / `:DISP:WHOL` | 设置或查询波形保持是否打开 | 3.9.12 | 143 |

<details><summary>3.9 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.9.1 | `:DISPlay:CLEar` |
| 3.9.2 | `:DISPlay:TYPE <type>` ; `:DISPlay:TYPE?` |
| 3.9.3 | `:DISPlay:GRADing:TIME <time>` ; `:DISPlay:GRADing:TIME?` |
| 3.9.4 | `:DISPlay:WBRightness <brightness>` ; `:DISPlay:WBRightness?` |
| 3.9.5 | `:DISPlay:GRID <grid>` ; `:DISPlay:GRID?` |
| 3.9.6 | `:DISPlay:GBRightness <brightness>` ; `:DISPlay:GBRightness?` |
| 3.9.7 | `:DISPlay:CBRightness <brightness>` ; `:DISPlay:CBRightness?` |
| 3.9.8 | `:DISPlay:DATA? [<type>]` |
| 3.9.9 | `:DISPlay:RULers <bool>` ; `:DISPlay:RULers?` |
| 3.9.10 | `:DISPlay:MOVE <bool>` ; `:DISPlay:MOVE?` |
| 3.9.11 | `:DISPlay:COLor <bool>` ; `:DISPlay:COLor?` |
| 3.9.12 | `:DISPlay:WHOLd <bool>` ; `:DISPlay:WHOLd?` |

</details>

## 3.10 电压表命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:DVM:CURRent?` | `:DVM:CURRENT?` / `:DVM:CURR?` | 查询当前所测电压值 | 3.10.1 | 143 |
| `:DVM:ENABle` | `:DVM:ENABLE` / `:DVM:ENAB` | 打开或关闭数字电压表，或查询数字电压表开关的状态 | 3.10.2 | 144 |
| `:DVM:SOURce` | `:DVM:SOURCE` / `:DVM:SOUR` | 设置或查询数字电压表信源 | 3.10.3 | 144 |
| `:DVM:MODE` | `:DVM:MODE` / `:DVM:MODE` | 设置或查询数字电压表模式 | 3.10.4 | 145 |

<details><summary>3.10 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.10.1 | `:DVM:CURRent?` |
| 3.10.2 | `:DVM:ENABle <bool>` ; `:DVM:ENABle?` |
| 3.10.3 | `:DVM:SOURce <source>` ; `:DVM:SOURce?` |
| 3.10.4 | `:DVM:MODE <mode>` ; `:DVM:MODE?` |

</details>

## 3.11 直方图命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:HISTogram:ENABle` | `:HISTOGRAM:ENABLE` / `:HIST:ENAB` | 打开或关闭直方图，或查询直方图的开关状态 | 3.11.1 | 146 |
| `:HISTogram:TYPE` | `:HISTOGRAM:TYPE` / `:HIST:TYPE` | 设置或查询直方图类型 | 3.11.2 | 147 |
| `:HISTogram:SOURce` | `:HISTOGRAM:SOURCE` / `:HIST:SOUR` | 设置或查询直方图信源 | 3.11.3 | 147 |
| `:HISTogram:HEIGht` | `:HISTOGRAM:HEIGHT` / `:HIST:HEIG` | 设置或查询直方图高度 | 3.11.4 | 148 |
| `:HISTogram:RANGe:LEFT` | `:HISTOGRAM:RANGE:LEFT` / `:HIST:RANG:LEFT` | 设置或查询直方图的左边界 | 3.11.5 | 148 |
| `:HISTogram:RANGe:RIGHt` | `:HISTOGRAM:RANGE:RIGHT` / `:HIST:RANG:RIGH` | 设置或查询直方图的右边界 | 3.11.6 | 149 |
| `:HISTogram:RANGe:TOP` | `:HISTOGRAM:RANGE:TOP` / `:HIST:RANG:TOP` | 设置或查询直方图的上边界 | 3.11.7 | 150 |
| `:HISTogram:RANGe:BOTTom` | `:HISTOGRAM:RANGE:BOTTOM` / `:HIST:RANG:BOTT` | 设置或查询直方图的下边界 | 3.11.8 | 151 |
| `:HISTogram:STATistics:RESult?` | `:HISTOGRAM:STATISTICS:RESULT?` / `:HIST:STAT:RES?` | 查询直方图统计结果 | 3.11.9 | 152 |
| `:HISTogram:RESet` | `:HISTOGRAM:RESET` / `:HIST:RES` | 重置直方图统计数据 | 3.11.10 | 152 |
| `:HISTogram:SAVE:CSV` | `:HISTOGRAM:SAVE:CSV` / `:HIST:SAVE:CSV` | 保存直方图数据文件到指定路径 | 3.11.11 | 153 |

<details><summary>3.11 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.11.1 | `:HISTogram:ENABle <bool>` ; `:HISTogram:ENABle?` |
| 3.11.2 | `:HISTogram:TYPE <type>` ; `:HISTogram:TYPE?` |
| 3.11.3 | `:HISTogram:SOURce <source>` ; `:HISTogram:SOURce?` |
| 3.11.4 | `:HISTogram:HEIGht <height>` ; `:HISTogram:HEIGht?` |
| 3.11.5 | `:HISTogram:RANGe:LEFT <number>` ; `:HISTogram:RANGe:LEFT?` |
| 3.11.6 | `:HISTogram:RANGe:RIGHt <number>` ; `:HISTogram:RANGe:RIGHt?` |
| 3.11.7 | `:HISTogram:RANGe:TOP <number>` ; `:HISTogram:RANGe:TOP?` |
| 3.11.8 | `:HISTogram:RANGe:BOTTom <number>` ; `:HISTogram:RANGe:BOTTom?` |
| 3.11.9 | `:HISTogram:STATistics:RESult?` |
| 3.11.10 | `:HISTogram:RESet?` |
| 3.11.11 | `:HISTogram:SAVE:CSV <path>` |

</details>

## 3.12 IEEE488.2通用命令

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `*IDN?` | `*IDN?` | 查询仪器的ID字符串 | 3.12.1 | 154 |
| `*RST` | `*RST` | 将仪器恢复至出厂默认状态 | 3.12.2 | 155 |
| `*CLS` | `*CLS` | 将所有事件寄存器的值清零，同时清除错误队列 | 3.12.3 | 155 |
| `*ESE` | `*ESE` | 设置或查询标准事件状态寄存器组的使能寄存器位 | 3.12.4 | 156 |
| `*ESR?` | `*ESR?` | 查询并清除标准事件状态寄存器组的事件寄存器值 | 3.12.5 | 157 |
| `*OPC` | `*OPC` | *OPC命令用于在当前操作完成后，将标准事件状态寄存器的OperationComplete位（位0）置1 | 3.12.6 | 157 |
| `*SRE` | `*SRE` | 设置或查询状态字节寄存器组的使能寄存器值 | 3.12.7 | 158 |
| `*STB?` | `*STB?` | 查询状态字节寄存器的事件寄存器值 | 3.12.8 | 158 |
| `*WAI` | `*WAI` | 等待操作完成 | 3.12.9 | 159 |
| `*TST?` | `*TST?` | 执行一次自检并返回自检结果 | 3.12.10 | 159 |

<details><summary>3.12 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.12.1 | `*IDN?` |
| 3.12.2 | `*RST` |
| 3.12.3 | `*CLS` |
| 3.12.4 | `*ESE <maskargument>` ; `*ESE?` |
| 3.12.5 | `*ESR?` |
| 3.12.6 | `*OPC` ; `*OPC?` |
| 3.12.7 | `*SRE <maskargument>` ; `*SRE?` |
| 3.12.8 | `*STB?` |
| 3.12.9 | `*WAI` |
| 3.12.10 | `*TST?` |

</details>

## 3.13 数字通道命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:LA:ENABle` | `:LA:ENABLE` / `:LA:ENAB` | 设置或查询LA的使能状态 | 3.13.1 | 160 |
| `:LA:ACTive` | `:LA:ACTIVE` / `:LA:ACT` | 设置或查询当前的激活通道 | 3.13.2 | 160 |
| `:LA:AUTosort` | `:LA:AUTOSORT` / `:LA:AUT` | 设置或查询LA的自动排序方式 | 3.13.3 | 161 |
| `:LA:DIGital:ENABle` | `:LA:DIGITAL:ENABLE` / `:LA:DIG:ENAB` | 打开或关闭指定的数字通道，或查询指定数字通道的状态 | 3.13.4 | 162 |
| `:LA:DIGital:LABel` | `:LA:DIGITAL:LABEL` / `:LA:DIG:LAB` | 设置或查询指定数字通道的标签 | 3.13.5 | 162 |
| `:LA:POD<n>:DISPlay` | `:LA:POD<N>:DISPLAY` / `:LA:POD<>:DISP` | 打开或关闭指定的默认通道组，或查询指定默认通道组的状态 | 3.13.6 | 163 |
| `:LA:POD<n>:THReshold` | `:LA:POD<N>:THRESHOLD` / `:LA:POD<>:THR` | 设置或查询指定默认通道组的阈值，默认单位为V | 3.13.7 | 164 |
| `:LA:SIZE` | `:LA:SIZE` / `:LA:SIZE` | 设置或查询已打开通道的波形在屏幕中显示的大小 | 3.13.8 | 164 |

<details><summary>3.13 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.13.1 | `:LA:ENABle <bool>` ; `:LA:ENABle?` |
| 3.13.2 | `:LA:ACTive <digital>` ; `:LA:ACTive?` |
| 3.13.3 | `:LA:AUTosort <val>` ; `:LA:AUTosort?` |
| 3.13.4 | `:LA:DIGital:ENABle <digital>,<bool>` ; `:LA:DIGital:ENABle? <digital>` |
| 3.13.5 | `:LA:DIGital:LABel <digital>,<label>` ; `:LA:DIGital:LABel? <digital>` |
| 3.13.6 | `:LA:POD<n>:DISPlay <bool>` ; `:LA:POD<n>:DISPlay?` |
| 3.13.7 | `:LA:POD<n>:THReshold <thre>` ; `:LA:POD<n>:THReshold?` |
| 3.13.8 | `:LA:SIZE <size>` ; `:LA:SIZE?` |

</details>

## 3.14 局域网命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:LAN:DHCP` | `:LAN:DHCP` / `:LAN:DHCP` | 打开或关闭DHCP配置模式，或查询当前DHCP配置模式的状态 | 3.14.1 | 165 |
| `:LAN:AUToip` | `:LAN:AUTOIP` / `:LAN:AUT` | 打开或关闭自动IP配置模式，或查询当前自动IP配置模式的状态 | 3.14.2 | 166 |
| `:LAN:GATeway` | `:LAN:GATEWAY` / `:LAN:GAT` | 设置或查询默认网关 | 3.14.3 | 166 |
| `:LAN:DNS` | `:LAN:DNS` / `:LAN:DNS` | 设置或查询域名服务器地址 | 3.14.4 | 167 |
| `:LAN:MAC?` | `:LAN:MAC?` / `:LAN:MAC?` | 查询仪器MAC地址 | 3.14.5 | 168 |
| `:LAN:DSERver?` | `:LAN:DSERVER?` / `:LAN:DSER?` | 查询DHCP服务器地址 | 3.14.6 | 168 |
| `:LAN:MANual` | `:LAN:MANUAL` / `:LAN:MAN` | 打开或关闭静态IP配置模式，或查询当前静态IP配置模式的状态 | 3.14.7 | 168 |
| `:LAN:IPADdress` | `:LAN:IPADDRESS` / `:LAN:IPAD` | 设置或查询仪器的IP地址 | 3.14.8 | 169 |
| `:LAN:SMASk` | `:LAN:SMASK` / `:LAN:SMAS` | 设置或查询子网掩码 | 3.14.9 | 170 |
| `:LAN:STATus?` | `:LAN:STATUS?` / `:LAN:STAT?` | 查询当前的网络配置状态 | 3.14.10 | 170 |
| `:LAN:VISA?` | `:LAN:VISA?` / `:LAN:VISA?` | 查询仪器VISA地址 | 3.14.11 | 171 |
| `:LAN:MDNS` | `:LAN:MDNS` / `:LAN:MDNS` | 打开或关闭mDNS，或查询mDNS的状态 | 3.14.12 | 172 |
| `:LAN:HOST:NAME` | `:LAN:HOST:NAME` / `:LAN:HOST:NAME` | 设置或查询主机名 | 3.14.13 | 172 |
| `:LAN:DESCription` | `:LAN:DESCRIPTION` / `:LAN:DESC` | 设置或查询描述 | 3.14.14 | 173 |
| `:LAN:APPLy` | `:LAN:APPLY` / `:LAN:APPL` | 应用网络配置 | 3.14.15 | 173 |

<details><summary>3.14 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.14.1 | `:LAN:DHCP <bool>` ; `:LAN:DHCP?` |
| 3.14.2 | `:LAN:AUToip <bool>` ; `:LAN:AUToip?` |
| 3.14.3 | `:LAN:GATeway <string>` ; `:LAN:GATeway?` |
| 3.14.4 | `:LAN:DNS <string>` ; `:LAN:DNS?` |
| 3.14.5 | `:LAN:MAC?` |
| 3.14.6 | `:LAN:DSERver?` |
| 3.14.7 | `:LAN:MANual <bool>` ; `:LAN:MANual?` |
| 3.14.8 | `:LAN:IPADdress <string>` ; `:LAN:IPADdress?` |
| 3.14.9 | `:LAN:SMASk <string>` ; `:LAN:SMASk?` |
| 3.14.10 | `:LAN:STATus?` |
| 3.14.11 | `:LAN:VISA? [<type>]` |
| 3.14.12 | `:LAN:MDNS <bool>` ; `:LAN:MDNS?` |
| 3.14.13 | `:LAN:HOST:NAME <name>` ; `:LAN:HOST:NAME?` |
| 3.14.14 | `:LAN:DESCription <name>` ; `:LAN:DESCription?` |
| 3.14.15 | `:LAN:APPLy` |

</details>

## 3.15 通过/失败测试命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:MASK:ENABle` | `:MASK:ENABLE` / `:MASK:ENAB` | 打开或关闭通过/失败测试功能，或查询通过/失败测试功能的状态 | 3.15.1 | 174 |
| `:MASK:SOURce` | `:MASK:SOURCE` / `:MASK:SOUR` | 设置或查询通过/失败测试的信源 | 3.15.2 | 175 |
| `:MASK:OPERate` | `:MASK:OPERATE` / `:MASK:OPER` | 启动或停止通过/失败测试功能，或查询通过/失败测试功能的运行状态 | 3.15.3 | 175 |
| `:MASK:X` | `:MASK:X` / `:MASK:X` | 设置或查询通过/失败测试规则中的水平调整参数，默认单位为div | 3.15.4 | 176 |
| `:MASK:Y` | `:MASK:Y` / `:MASK:Y` | 设置或查询通过/失败测试规则中的垂直调整参数，默认单位为div | 3.15.5 | 176 |
| `:MASK:CREate` | `:MASK:CREATE` / `:MASK:CRE` | 以当前设置的水平调整参数和垂直调整参数创建通过/失败测试的规则 | 3.15.6 | 177 |
| `:MASK:RESet` | `:MASK:RESET` / `:MASK:RES` | 复位通过/失败测试中通过的帧数、失败的帧数和总帧数 | 3.15.7 | 177 |
| `:MASK:FAILed?` | `:MASK:FAILED?` / `:MASK:FAIL?` | 查询通过/失败测试时失败的帧数 | 3.15.8 | 178 |
| `:MASK:PASSed?` | `:MASK:PASSED?` / `:MASK:PASS?` | 查询通过/失败测试时通过的帧数 | 3.15.9 | 178 |
| `:MASK:TOTal?` | `:MASK:TOTAL?` / `:MASK:TOT?` | 查询通过/失败测试的总帧数 | 3.15.10 | 179 |
| `:MASK:OUTPut:ENABle` | `:MASK:OUTPUT:ENABLE` / `:MASK:OUTP:ENAB` | 设置或查询设备后面板AUXOUT接口的输出状态 | 3.15.11 | 179 |
| `:MASK:OUTPut:EVENt` | `:MASK:OUTPUT:EVENT` / `:MASK:OUTP:EVEN` | 设置或查询输出事件 | 3.15.12 | 180 |
| `:MASK:OUTPut:TIME` | `:MASK:OUTPUT:TIME` / `:MASK:OUTP:TIME` | 设置或查询输出脉宽时间 | 3.15.13 | 180 |

<details><summary>3.15 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.15.1 | `:MASK:ENABle <bool>` ; `:MASK:ENABle?` |
| 3.15.2 | `:MASK:SOURce <source>` ; `:MASK:SOURce?` |
| 3.15.3 | `:MASK:OPERate <oper>` ; `:MASK:OPERate?` |
| 3.15.4 | `:MASK:X <x>` ; `:MASK:X?` |
| 3.15.5 | `:MASK:Y <y>` ; `:MASK:Y?` |
| 3.15.6 | `:MASK:CREate` |
| 3.15.7 | `:MASK:RESet` |
| 3.15.8 | `:MASK:FAILed?` |
| 3.15.9 | `:MASK:PASSed?` |
| 3.15.10 | `:MASK:TOTal?` |
| 3.15.11 | `:MASK:OUTPut:ENABle <bool>` ; `:MASK:OUTPut:ENABle?` |
| 3.15.12 | `:MASK:OUTPut:EVENt <item>` ; `:MASK:OUTPut:EVENt?` |
| 3.15.13 | `:MASK:OUTPut:TIME <time>` ; `:MASK:OUTPut:TIME?` |

</details>

## 3.16 数学运算命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:MATH<n>:DISPlay` | `:MATH<N>:DISPLAY` / `:MATH<>:DISP` | 打开或关闭数学运算功能，或查询数学运算功能的状态 | 3.16.1 | 183 |
| `:MATH<n>:OPERator` | `:MATH<N>:OPERATOR` / `:MATH<>:OPER` | 设置或查询数学运算的运算符 | 3.16.2 | 184 |
| `:MATH<n>:SOURce1` | `:MATH<N>:SOURCE1` / `:MATH<>:SOUR1` | 设置或查询代数运算、函数运算和滤波运算的信源或信源A | 3.16.3 | 184 |
| `:MATH<n>:SOURce2` | `:MATH<N>:SOURCE2` / `:MATH<>:SOUR2` | 设置或查询代数运算的信源B | 3.16.4 | 185 |
| `:MATH<n>:LSOurce1` | `:MATH<N>:LSOURCE1` / `:MATH<>:LSO1` | 设置或查询逻辑运算的信源A | 3.16.5 | 186 |
| `:MATH<n>:LSOurce2` | `:MATH<N>:LSOURCE2` / `:MATH<>:LSO2` | 设置或查询逻辑运算的信源B | 3.16.6 | 187 |
| `:MATH<n>:SCALe` | `:MATH<N>:SCALE` / `:MATH<>:SCAL` | 设置或查询运算结果的垂直档位，单位与当前所选的运算符以及信源所选的单位有关 | 3.16.7 | 187 |
| `:MATH<n>:OFFSet` | `:MATH<N>:OFFSET` / `:MATH<>:OFFS` | 设置或查询运算结果的垂直偏移，单位与当前所选的运算符以及信源所选的单位有关 | 3.16.8 | 188 |
| `:MATH<n>:INVert` | `:MATH<N>:INVERT` / `:MATH<>:INV` | 打开或关闭运算结果的反相显示，或查询运算结果反相显示的状态 | 3.16.9 | 189 |
| `:MATH<n>:RESet` | `:MATH<N>:RESET` / `:MATH<>:RES` | 发送该命令，仪器根据当前所选的运算符、信源的水平时基将运算结果的垂直档位调节至最佳值 | 3.16.10 | 189 |
| `:MATH<n>:GRID` | `:MATH<N>:GRID` / `:MATH<>:GRID` | 设置或查询数学运算屏幕显示的网格类型 | 3.16.11 | 190 |
| `:MATH<n>:EXPand` | `:MATH<N>:EXPAND` / `:MATH<>:EXP` | 设置或查询数学运算的垂直扩展类型 | 3.16.12 | 190 |
| `:MATH<n>:WAVetype` | `:MATH<N>:WAVETYPE` / `:MATH<>:WAV` | 设置或查询数学运算的波形类型 | 3.16.13 | 191 |
| `:MATH<n>:FFT:SOURce` | `:MATH<N>:FFT:SOURCE` / `:MATH<>:FFT:SOUR` | 设置或查询FFT运算的信源 | 3.16.14 | 192 |
| `:MATH<n>:FFT:WINDow` | `:MATH<N>:FFT:WINDOW` / `:MATH<>:FFT:WIND` | 设置或查询FFT运算的窗函数 | 3.16.15 | 192 |
| `:MATH<n>:FFT:UNIT` | `:MATH<N>:FFT:UNIT` / `:MATH<>:FFT:UNIT` | 设置或查询FFT运算结果的垂直单位 | 3.16.16 | 193 |
| `:MATH<n>:FFT:MODE` | `:MATH<N>:FFT:MODE` / `:MATH<>:FFT:MODE` | 设置或查询FFT运算的模式 | 3.16.17 | 194 |
| `:MATH<n>:FFT:AVCNt` | `:MATH<N>:FFT:AVCNT` / `:MATH<>:FFT:AVCN` | 设置或查询FFT平均模式下的平均次数 | 3.16.18 | 194 |
| `:MATH<n>:FFT:SCALe` | `:MATH<N>:FFT:SCALE` / `:MATH<>:FFT:SCAL` | 设置或查询FFT运算结果的垂直档位 | 3.16.19 | 195 |
| `:MATH<n>:FFT:OFFSet` | `:MATH<N>:FFT:OFFSET` / `:MATH<>:FFT:OFFS` | 设置或查询FFT运算结果的垂直偏移 | 3.16.20 | 196 |
| `:MATH<n>:FFT:HSCale` | `:MATH<N>:FFT:HSCALE` / `:MATH<>:FFT:HSC` | 设置或查询FFT运算结果的频率范围，默认单位为Hz | 3.16.21 | 196 |
| `:MATH<n>:FFT:HCENter` | `:MATH<N>:FFT:HCENTER` / `:MATH<>:FFT:HCEN` | 设置或查询FFT运算结果的中心频率，即屏幕水平中心对应的频率 | 3.16.22 | 197 |
| `:MATH<n>:FFT:FREQuency:STARt` | `:MATH<N>:FFT:FREQUENCY:START` / `:MATH<>:FFT:FREQ:STAR` | 设置或查询FFT运算结果的起始频率 | 3.16.23 | 198 |
| `:MATH<n>:FFT:FREQuency:END` | `:MATH<N>:FFT:FREQUENCY:END` / `:MATH<>:FFT:FREQ:END` | 设置或查询FFT运算结果的终止频率 | 3.16.24 | 198 |
| `:MATH<n>:FFT:SEARch:ENABle` | `:MATH<N>:FFT:SEARCH:ENABLE` / `:MATH<>:FFT:SEAR:ENAB` | 打开或关闭FFT峰值搜索，或查询FFT峰值搜索功能的状态 | 3.16.25 | 199 |
| `:MATH<n>:FFT:SEARch:NUM` | `:MATH<N>:FFT:SEARCH:NUM` / `:MATH<>:FFT:SEAR:NUM` | 设置或查询FFT峰值搜索的最大数目 | 3.16.26 | 199 |
| `:MATH<n>:FFT:SEARch:THReshold` | `:MATH<N>:FFT:SEARCH:THRESHOLD` / `:MATH<>:FFT:SEAR:THR` | 设置或查询FFT峰值搜索的阈值 | 3.16.27 | 200 |
| `:MATH<n>:FFT:SEARch:EXCursion` | `:MATH<N>:FFT:SEARCH:EXCURSION` / `:MATH<>:FFT:SEAR:EXC` | 设置或查询FFT峰值搜索的偏移阈值 | 3.16.28 | 201 |
| `:MATH<n>:FFT:SEARch:ORDer` | `:MATH<N>:FFT:SEARCH:ORDER` / `:MATH<>:FFT:SEAR:ORD` | 设置或查询FFT峰值搜索结果的排序方式 | 3.16.29 | 201 |
| `:MATH<n>:FFT:SEARch:RES?` | `:MATH<N>:FFT:SEARCH:RES?` / `:MATH<>:FFT:SEAR:RES?` | 查询FFT峰值搜索结果表 | 3.16.30 | 202 |
| `:MATH<n>:FILTer:TYPE` | `:MATH<N>:FILTER:TYPE` / `:MATH<>:FILT:TYPE` | 设置或查询滤波器类型 | 3.16.31 | 202 |
| `:MATH<n>:FILTer:W1` | `:MATH<N>:FILTER:W1` / `:MATH<>:FILT:W1` | 设置或查询低通/高通滤波器的截止频率或带通/带阻滤波器的截止频率1，默认单位为Hz | 3.16.32 | 203 |
| `:MATH<n>:FILTer:W2` | `:MATH<N>:FILTER:W2` / `:MATH<>:FILT:W2` | 设置或查询带通/带阻滤波器的截止频率2，默认单位为Hz | 3.16.33 | 204 |
| `:MATH<n>:SENSitivity` | `:MATH<N>:SENSITIVITY` / `:MATH<>:SENS` | 设置或查询逻辑运算的灵敏度，默认单位为div | 3.16.34 | 205 |
| `:MATH<n>:DISTance` | `:MATH<N>:DISTANCE` / `:MATH<>:DIST` | 设置或查询微分运算的平滑窗口宽度 | 3.16.35 | 206 |
| `:MATH<n>:THReshold1` | `:MATH<N>:THRESHOLD1` / `:MATH<>:THR1` | 设置或查询逻辑运算模拟通道1的门限电平，默认单位为V | 3.16.36 | 206 |
| `:MATH<n>:THReshold2` | `:MATH<N>:THRESHOLD2` / `:MATH<>:THR2` | 设置或查询逻辑运算模拟通道2的门限电平，默认单位为V | 3.16.37 | 207 |
| `:MATH<n>:THReshold3` | `:MATH<N>:THRESHOLD3` / `:MATH<>:THR3` | 设置或查询逻辑运算模拟通道3的门限电平，默认单位为V | 3.16.38 | 208 |
| `:MATH<n>:THReshold4` | `:MATH<N>:THRESHOLD4` / `:MATH<>:THR4` | 设置或查询逻辑运算模拟通道4的门限电平，默认单位为V | 3.16.39 | 208 |
| `:MATH<n>:WINDow:TITLe?` | `:MATH<N>:WINDOW:TITLE?` / `:MATH<>:WIND:TITL?` | 查询指定数学运算窗口的标题 | 3.16.40 | 209 |
| `:MATH<n>:LABel:SHOW` | `:MATH<N>:LABEL:SHOW` / `:MATH<>:LAB:SHOW` | 设置或查询指定运算波形标签的显示状态 | 3.16.41 | 210 |
| `:MATH<n>:DISMode` | `:MATH<N>:DISMODE` / `:MATH<>:DISM` | 设置或查询数学运算功能的显示区域 | 3.16.42 | 210 |

<details><summary>3.16 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.16.1 | `:MATH<n>:DISPlay <bool>` ; `:MATH<n>:DISPlay?` |
| 3.16.2 | `:MATH<n>:OPERator <opt>` ; `:MATH<n>:OPERator?` |
| 3.16.3 | `:MATH<n>:SOURce1 <source>` ; `:MATH<n>:SOURce1?` |
| 3.16.4 | `:MATH<n>:SOURce2 <source>` ; `:MATH<n>:SOURce2?` |
| 3.16.5 | `:MATH<n>:LSOurce1 <source>` ; `:MATH<n>:LSOurce1?` |
| 3.16.6 | `:MATH<n>:LSOurce2 <source>` ; `:MATH<n>:LSOurce2?` |
| 3.16.7 | `:MATH<n>:SCALe <scale>` ; `:MATH<n>:SCALe?` |
| 3.16.8 | `:MATH<n>:OFFSet <offset>` ; `:MATH<n>:OFFSet?` |
| 3.16.9 | `:MATH<n>:INVert <bool>` ; `:MATH<n>:INVert?` |
| 3.16.10 | `:MATH<n>:RESet` |
| 3.16.11 | `:MATH<n>:GRID <grid>` ; `:MATH<n>:GRID?` |
| 3.16.12 | `:MATH<n>:EXPand <exp>` ; `:MATH<n>:EXPand?` |
| 3.16.13 | `:MATH<n>:WAVetype <type>` ; `:MATH<n>:WAVetype?` |
| 3.16.14 | `:MATH<n>:FFT:SOURce <source>` ; `:MATH<n>:FFT:SOURce?` |
| 3.16.15 | `:MATH<n>:FFT:WINDow <window>` ; `:MATH<n>:FFT:WINDow?` |
| 3.16.16 | `:MATH<n>:FFT:UNIT <unit>` ; `:MATH<n>:FFT:UNIT?` |
| 3.16.17 | `:MATH<n>:FFT:MODE <mode>` ; `:MATH<n>:FFT:MODE?` |
| 3.16.18 | `:MATH<n>:FFT:AVCNt <cnt>` ; `:MATH<n>:FFT:AVCNt?` |
| 3.16.19 | `:MATH<n>:FFT:SCALe <scale>` ; `:MATH<n>:FFT:SCALe?` |
| 3.16.20 | `:MATH<n>:FFT:OFFSet <offset>` ; `:MATH<n>:FFT:OFFSet?` |
| 3.16.21 | `:MATH<n>:FFT:HSCale <hsc>` ; `:MATH<n>:FFT:HSCale?` |
| 3.16.22 | `:MATH<n>:FFT:HCENter <cent>` ; `:MATH<n>:FFT:HCENter?` |
| 3.16.23 | `:MATH<n>:FFT:FREQuency:STARt <value>` ; `:MATH<n>:FFT:FREQuency:STARt?` |
| 3.16.24 | `:MATH<n>:FFT:FREQuency:END <value>` ; `:MATH<n>:FFT:FREQuency:END?` |
| 3.16.25 | `:MATH<n>:FFT:SEARch:ENABle <bool>` ; `:MATH<n>:FFT:SEARch:ENABle?` |
| 3.16.26 | `:MATH<n>:FFT:SEARch:NUM <num>` ; `:MATH<n>:FFT:SEARch:NUM?` |
| 3.16.27 | `:MATH<n>:FFT:SEARch:THReshold <thres>` ; `:MATH<n>:FFT:SEARch:THReshold?` |
| 3.16.28 | `:MATH<n>:FFT:SEARch:EXCursion <excur>` ; `:MATH<n>:FFT:SEARch:EXCursion?` |
| 3.16.29 | `:MATH<n>:FFT:SEARch:ORDer <order>` ; `:MATH<n>:FFT:SEARch:ORDer?` |
| 3.16.30 | `:MATH<n>:FFT:SEARch:RES?` |
| 3.16.31 | `:MATH<n>:FILTer:TYPE <type>` ; `:MATH<n>:FILTer:TYPE?` |
| 3.16.32 | `:MATH<n>:FILTer:W1 <freq1>` ; `:MATH<n>:FILTer:W1?` |
| 3.16.33 | `:MATH<n>:FILTer:W2 <freq2>` ; `:MATH<n>:FILTer:W2?` |
| 3.16.34 | `:MATH<n>:SENSitivity <sens>` ; `:MATH<n>:SENSitivity?` |
| 3.16.35 | `:MATH<n>:DISTance <dist>` ; `:MATH<n>:DISTance?` |
| 3.16.36 | `:MATH<n>:THReshold1 <thre>` ; `:MATH<n>:THReshold1?` |
| 3.16.37 | `:MATH<n>:THReshold2 <thre>` ; `:MATH<n>:THReshold2?` |
| 3.16.38 | `:MATH<n>:THReshold3 <thre>` ; `:MATH<n>:THReshold3?` |
| 3.16.39 | `:MATH<n>:THReshold4 <thre>` ; `:MATH<n>:THReshold4?` |
| 3.16.40 | `:MATH<n>:WINDow:TITLe?` |
| 3.16.41 | `:MATH<n>:LABel:SHOW <bool>` ; `:MATH<n>:LABel:SHOW?` |
| 3.16.42 | `:MATH<n>DISMode <bool>` ; `:MATH<n>DISMode?` |

</details>

## 3.17 测量命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:MEASure:SOURce` | `:MEASURE:SOURCE` / `:MEAS:SOUR` | 设置或查询当前测量参数的信源 | 3.17.1 | 215 |
| `:MEASure:ITEM` | `:MEASURE:ITEM` / `:MEAS:ITEM` | 测量指定信源的任意波形参数，或查询指定信源的任意波形参数的测量结果 | 3.17.2 | 216 |
| `:MEASure:DELete` | `:MEASURE:DELETE` / `:MEAS:DEL` | 清除所有已打开的测量项 | 3.17.3 | 217 |
| `:MEASure:AMSource` | `:MEASURE:AMSOURCE` / `:MEAS:AMS` | 设置或查询全部测量功能的信源 | 3.17.4 | 218 |
| `:MEASure:STATistic:COUNt` | `:MEASURE:STATISTIC:COUNT` / `:MEAS:STAT:COUN` | 设置或查询测量统计次数 | 3.17.5 | 218 |
| `:MEASure:STATistic:DISPlay` | `:MEASURE:STATISTIC:DISPLAY` / `:MEAS:STAT:DISP` | 打开或关闭统计功能，或查询统计功能的状态 | 3.17.6 | 219 |
| `:MEASure:STATistic:RESet` | `:MEASURE:STATISTIC:RESET` / `:MEAS:STAT:RES` | 清除历史统计数据并重新统计 | 3.17.7 | 220 |
| `:MEASure:STATistic:ITEM` | `:MEASURE:STATISTIC:ITEM` / `:MEAS:STAT:ITEM` | 打开指定信源的任意波形参数的统计功能，或查询指定信源的任意波形参数的统计结果 | 3.17.8 | 220 |
| `:MEASure:SETup:MAX` | `:MEASURE:SETUP:MAX` / `:MEAS:SET:MAX` | 设置或查询模拟通道自动测量时门限电平的上限值 | 3.17.9 | 221 |
| `:MEASure:SETup:MID` | `:MEASURE:SETUP:MID` / `:MEAS:SET:MID` | 设置或查询模拟通道自动测量时门限电平的中间值 | 3.17.10 | 222 |
| `:MEASure:SETup:MIN` | `:MEASURE:SETUP:MIN` / `:MEAS:SET:MIN` | 设置或查询模拟通道自动测量时门限电平的下限值 | 3.17.11 | 223 |
| `:MEASure:SETup:PSA` | `:MEASURE:SETUP:PSA` / `:MEAS:SET:PSA` | 设置或查询相位或延迟时间测量中的信源A | 3.17.12 | 224 |
| `:MEASure:SETup:PSB` | `:MEASURE:SETUP:PSB` / `:MEAS:SET:PSB` | 设置或查询相位或延迟时间测量中的信源B | 3.17.13 | 224 |
| `:MEASure:SETup:DSA` | `:MEASURE:SETUP:DSA` / `:MEAS:SET:DSA` | 设置或查询相位或延迟时间测量中的信源A | 3.17.14 | 225 |
| `:MEASure:SETup:DSB` | `:MEASURE:SETUP:DSB` / `:MEAS:SET:DSB` | 设置或查询相位或延迟时间测量中的信源B | 3.17.15 | 226 |
| `:MEASure:THReshold:SOURce` | `:MEASURE:THRESHOLD:SOURCE` / `:MEAS:THR:SOUR` | 设置或查询门限源 | 3.17.16 | 226 |
| `:MEASure:THReshold:TYPE` | `:MEASURE:THRESHOLD:TYPE` / `:MEAS:THR:TYPE` | 设置或查询测量门限类型 | 3.17.17 | 227 |
| `:MEASure:THReshold:DEFault` | `:MEASURE:THRESHOLD:DEFAULT` / `:MEAS:THR:DEF` | 设置模拟通道自动测量时门限电平为默认值 | 3.17.18 | 228 |
| `:MEASure:AREA` | `:MEASURE:AREA` / `:MEAS:AREA` | 设置或查询测量范围的类型 | 3.17.19 | 228 |
| `:MEASure:TYPE` | `:MEASURE:TYPE` / `:MEAS:TYPE` | 设置或查询测量设置类型 | 3.17.20 | 229 |
| `:MEASure:CREGion:CAX` | `:MEASURE:CREGION:CAX` / `:MEAS:CREG:CAX` | 当测量区域为光标区域时，设置或查询光标A的水平位置，单位s | 3.17.21 | 229 |
| `:MEASure:CREGion:CBX` | `:MEASURE:CREGION:CBX` / `:MEAS:CREG:CBX` | 当测量区域为光标区域时，设置或查询光标B的水平位置，单位s | 3.17.22 | 230 |
| `:MEASure:CREGion:CABX` | `:MEASURE:CREGION:CABX` / `:MEAS:CREG:CABX` | 设置或查询测量光标是否联动 | 3.17.23 | 231 |
| `:MEASure:INDicator` | `:MEASURE:INDICATOR` / `:MEAS:IND` | 设置或查询测量功能光标指示的使能状态 | 3.17.24 | 231 |
| `:MEASure:COUNter:ENABle` | `:MEASURE:COUNTER:ENABLE` / `:MEAS:COUN:ENAB` | 设置或查询频率计的使能状态 | 3.17.25 | 232 |
| `:MEASure:COUNter:SOURce` | `:MEASURE:COUNTER:SOURCE` / `:MEAS:COUN:SOUR` | 设置或查询频率计的测量源 | 3.17.26 | 232 |
| `:MEASure:COUNter:VALue?` | `:MEASURE:COUNTER:VALUE?` / `:MEAS:COUN:VAL?` | 查询频率计的测量结果 | 3.17.27 | 233 |
| `:MEASure:AMP:TYPE` | `:MEASURE:AMP:TYPE` / `:MEAS:AMP:TYPE` | 设置或查询幅值计算方式 | 3.17.28 | 233 |
| `:MEASure:AMP:MANual:TOP` | `:MEASURE:AMP:MANUAL:TOP` / `:MEAS:AMP:MAN:TOP` | 设置或查询幅度顶端值手动测量方式 | 3.17.29 | 234 |
| `:MEASure:AMP:MANual:BASE` | `:MEASURE:AMP:MANUAL:BASE` / `:MEAS:AMP:MAN:BASE` | 设置或查询幅度底端值手动测量方式 | 3.17.30 | 235 |
| `:MEASure:HISTogram:ENABle` | `:MEASURE:HISTOGRAM:ENABLE` / `:MEAS:HIST:ENAB` | 设置或查询是否使能测量直方图功能 | 3.17.31 | 235 |
| `:MEASure:HISTogram:STATistics:RESult?` | `:MEASURE:HISTOGRAM:STATISTICS:RESULT?` / `:MEAS:HIST:STAT:RES?` | 查询测量直方图统计结果 | 3.17.32 | 236 |
| `:MEASure:CATegory` | `:MEASURE:CATEGORY` / `:MEAS:CAT` | 设置或查询测量的类型 | 3.17.33 | 236 |

<details><summary>3.17 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.17.1 | `:MEASure:SOURce <source>` ; `:MEASure:SOURce?` |
| 3.17.2 | `:MEASure:ITEM <item>[,<src>[,<src>]]` ; `:MEASure:ITEM? <item>[,<src>[,<src>]]` |
| 3.17.3 | `:MEASure:DELete` |
| 3.17.4 | `:MEASure:AMSource <chan>` ; `:MEASure:AMSource?` |
| 3.17.5 | `:MEASure:STATistic:COUNt <val>` ; `:MEASure:STATistic:COUNt?` |
| 3.17.6 | `:MEASure:STATistic:DISPlay <bool>` ; `:MEASure:STATistic:DISPlay?` |
| 3.17.7 | `:MEASure:STATistic:RESet` |
| 3.17.8 | `:MEASure:STATistic:ITEM <item>[,<src>[,<src>]]` ; `:MEASure:STATistic:ITEM?<type>,<item>[,<src>[,<src>]]` |
| 3.17.9 | `:MEASure:SETup:MAX <value>` ; `:MEASure:SETup:MAX?` |
| 3.17.10 | `:MEASure:SETup:MID <value>` ; `:MEASure:SETup:MID?` |
| 3.17.11 | `:MEASure:SETup:MIN <value>` ; `:MEASure:SETup:MIN?` |
| 3.17.12 | `:MEASure:SETup:PSA <source>` ; `:MEASure:SETup:PSA?` |
| 3.17.13 | `:MEASure:SETup:PSB <source>` ; `:MEASure:SETup:PSB?` |
| 3.17.14 | `:MEASure:SETup:DSA <source>` ; `:MEASure:SETup:DSA?` |
| 3.17.15 | `:MEASure:SETup:DSB <source>` ; `:MEASure:SETup:DSB` |
| 3.17.16 | `:MEASure:THReshold:SOURce <source>` ; `:MEASure:THReshold:SOURce?` |
| 3.17.17 | `:MEASure:THReshold:TYPE <type>` ; `:MEASure:THReshold:TYPE?` |
| 3.17.18 | `:MEASure:THReshold:DEFault` |
| 3.17.19 | `:MEASure:AREA <area>` ; `:MEASure:AREA?` |
| 3.17.20 | `:MEASure:TYPE <type>` ; `:MEASure:TYPE?` |
| 3.17.21 | `:MEASure:CREGion:CAX <cax>` ; `:MEASure:CREGion:CAX?` |
| 3.17.22 | `:MEASure:CREGion:CBX <cbx>` ; `:MEASure:CREGion:CBX?` |
| 3.17.23 | `:MEASure:CREGion:CABX <bool>` ; `:MEASure:CREGion:CABX?` |
| 3.17.24 | `:MEASure:INDicator <bool>` ; `:MEASure:INDicator?` |
| 3.17.25 | `:MEASure:COUNter:ENABle <bool>` ; `:MEASure:COUNter:ENABle?` |
| 3.17.26 | `:MEASure:COUNter:SOURce <source>` ; `:MEASure:COUNter:SOURce?` |
| 3.17.27 | `:MEASure:COUNter:VALue?` |
| 3.17.28 | `:MEASure:AMP:TYPE <val>` ; `:MEASure:AMP:TYPE?` |
| 3.17.29 | `:MEASure:AMP:MANual:TOP <val>` ; `:MEASure:AMP:MANual:TOP?` |
| 3.17.30 | `:MEASure:AMP:MANual:BASE <val>` ; `:MEASure:AMP:MANual:BASE?` |
| 3.17.31 | `:MEASure:HISTogram:ENABle <bool>` ; `:MEASure:HISTogram:ENABle?` |
| 3.17.32 | `:MEASure:HISTogram:STATistics:RESult?` |
| 3.17.33 | `:MEASure:CATegory <val>` ; `:MEASure:CATegory?` |

</details>

## 3.18 快捷操作命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:QUICk:OPERation` | `:QUICK:OPERATION` / `:QUIC:OPER` | 设置或查询快捷键类型 | 3.18.1 | 237 |

<details><summary>3.18 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.18.1 | `:QUICk:OPERation <type>` ; `:QUICk:OPERation?` |

</details>

## 3.19 波形录制命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:RECord:WRECord:ENABle` | `:RECORD:WRECORD:ENABLE` / `:REC:WREC:ENAB` | 打开或关闭波形录制功能，或查询波形录制功能的状态 | 3.19.1 | 238 |
| `:RECord:ENABle` | `:RECORD:ENABLE` / `:REC:ENAB` | 打开或关闭波形录制功能，或查询波形录制功能的状态 | 3.19.2 | 238 |
| `:RECord:WRECord:OPERate` | `:RECORD:WRECORD:OPERATE` / `:REC:WREC:OPER` | 设置或查询波形录制开始或停止 | 3.19.3 | 239 |
| `:RECord:STARt` | `:RECORD:START` / `:REC:STAR` | 设置或查询波形录制开始或停止 | 3.19.4 | 240 |
| `:RECord:WRECord:FRAMes` | `:RECORD:WRECORD:FRAMES` / `:REC:WREC:FRAM` | 设置或查询波形录制帧数 | 3.19.5 | 240 |
| `:RECord:FRAMes` | `:RECORD:FRAMES` / `:REC:FRAM` | 设置或查询波形录制帧数 | 3.19.6 | 241 |
| `:RECord:WRECord:FRAMes:MAX` | `:RECORD:WRECORD:FRAMES:MAX` / `:REC:WREC:FRAM:MAX` | 设置波形录制录制帧数为最大帧数 | 3.19.7 | 241 |
| `:RECord:WRECord:FMAX?` | `:RECORD:WRECORD:FMAX?` / `:REC:WREC:FMAX?` | 查询当前可录制的最大帧数 | 3.19.8 | 242 |
| `:RECord:WRECord:FINTerval` | `:RECORD:WRECORD:FINTERVAL` / `:REC:WREC:FINT` | 设置或查询波形录制时帧与帧之间的时间间隔 | 3.19.9 | 242 |
| `:RECord:WRECord:PROMpt` | `:RECORD:WRECORD:PROMPT` / `:REC:WREC:PROM` | 设置或查询录制结束时的声音提示的开启状态 | 3.19.10 | 243 |
| `:RECord:WREPlay:FCURrent` | `:RECORD:WREPLAY:FCURRENT` / `:REC:WREP:FCUR` | 设置或查询波形播放的当前帧 | 3.19.11 | 243 |
| `:RECord:CURRent` | `:RECORD:CURRENT` / `:REC:CURR` | 设置或查询波形播放的当前帧 | 3.19.12 | 244 |
| `:RECord:WREPlay:FCURrent:TIME?` | `:RECORD:WREPLAY:FCURRENT:TIME?` / `:REC:WREP:FCUR:TIME?` | 查询波形播放时当前帧的时间戳 | 3.19.13 | 244 |
| `:RECord:WREPlay:FSTart` | `:RECORD:WREPLAY:FSTART` / `:REC:WREP:FST` | 设置或查询波形播放的起始帧 | 3.19.14 | 245 |
| `:RECord:WREPlay:FEND` | `:RECORD:WREPLAY:FEND` / `:REC:WREP:FEND` | 设置或查询波形播放的终止帧 | 3.19.15 | 245 |
| `:RECord:WREPlay:FMAX?` | `:RECORD:WREPLAY:FMAX?` / `:REC:WREP:FMAX?` | 查询当前最大可播放的帧数 | 3.19.16 | 246 |
| `:RECord:WREPlay:FINTerval` | `:RECORD:WREPLAY:FINTERVAL` / `:REC:WREP:FINT` | 设置或查询波形播放时帧与帧之间的时间间隔 | 3.19.17 | 246 |
| `:RECord:WREPlay:MODE` | `:RECORD:WREPLAY:MODE` / `:REC:WREP:MODE` | 设置或查询波形播放的模式为循环或单次 | 3.19.18 | 247 |
| `:RECord:WREPlay:DIRection` | `:RECORD:WREPLAY:DIRECTION` / `:REC:WREP:DIR` | 设置或查询波形播放的方向为正向或反向 | 3.19.19 | 247 |
| `:RECord:WREPlay:OPERate` | `:RECORD:WREPLAY:OPERATE` / `:REC:WREP:OPER` | 打开或关闭波形播放功能，或查询波形播放功能的状态 | 3.19.20 | 248 |
| `:RECord:PLAY` | `:RECORD:PLAY` / `:REC:PLAY` | 打开或关闭波形播放功能，或查询波形播放功能的状态 | 3.19.21 | 249 |
| `:RECord:WREPlay:BACK` | `:RECORD:WREPLAY:BACK` / `:REC:WREP:BACK` | 手动播放上一帧波形 | 3.19.22 | 249 |
| `:RECord:WREPlay:NEXT` | `:RECORD:WREPLAY:NEXT` / `:REC:WREP:NEXT` | 手动播放下一帧波形 | 3.19.23 | 250 |
| `:RECord:WREPlay:PLAY` | `:RECORD:WREPLAY:PLAY` / `:REC:WREP:PLAY` | 设置手动播放到起始帧或者结束帧 | 3.19.24 | 250 |

<details><summary>3.19 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.19.1 | `:RECord:WRECord:ENABle <bool>` ; `:RECord:WRECord:ENABle?` |
| 3.19.2 | `:RECord:ENABle <bool>` ; `:RECord:ENABle?` |
| 3.19.3 | `:RECord:WRECord:OPERate <operate>` ; `:RECord:WRECord:OPERate?` |
| 3.19.4 | `:RECord:STARt <bool>` ; `:RECord:STARt?` |
| 3.19.5 | `:RECord:WRECord:FRAMes <value>` ; `:RECord:WRECord:FRAMes?` |
| 3.19.6 | `:RECord:FRAMes <value>` ; `:RECord:FRAMes?` |
| 3.19.7 | `:RECord:WRECord:FRAMes:MAX` |
| 3.19.8 | `:RECord:WRECord:FMAX?` |
| 3.19.9 | `:RECord:WRECord:FINTerval <interval>` ; `:RECord:WRECord:FINTerval?` |
| 3.19.10 | `:RECord:WRECord:PROMpt <bool>` ; `:RECord:WRECord:PROMpt?` |
| 3.19.11 | `:RECord:WREPlay:FCURrent <value>` ; `:RECord:WREPlay:FCURrent?` |
| 3.19.12 | `:RECord:CURRent <value>` ; `:RECord:CURRent?` |
| 3.19.13 | `:RECord:WREPlay:FCURrent:TIME?` |
| 3.19.14 | `:RECord:WREPlay:FSTart <start>` ; `:RECord:WREPlay:FSTart?` |
| 3.19.15 | `:RECord:WREPlay:FEND <end>` ; `:RECord:WREPlay:FEND?` |
| 3.19.16 | `:RECord:WREPlay:FMAX?` |
| 3.19.17 | `:RECord:WREPlay:FINTerval <interval>` ; `:RECord:WREPlay:FINTerval?` |
| 3.19.18 | `:RECord:WREPlay:MODE <mode>` ; `:RECord:WREPlay:MODE?` |
| 3.19.19 | `:RECord:WREPlay:DIRection <direction>` ; `:RECord:WREPlay:DIRection?` |
| 3.19.20 | `:RECord:WREPlay:OPERate <operate>` ; `:RECord:WREPlay:OPERate?` |
| 3.19.21 | `:RECord:PLAY <bool>` ; `:RECord:PLAY?` |
| 3.19.22 | `:RECord:WREPlay:BACK` |
| 3.19.23 | `:RECord:WREPlay:NEXT` |
| 3.19.24 | `:RECord:WREPlay:PLAY <val>` |

</details>

## 3.20 参考波形命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:REFerence:SOURce` | `:REFERENCE:SOURCE` / `:REF:SOUR` | 设置或查询指定参考通道的信源 | 3.20.1 | 251 |
| `:REFerence:VSCale` | `:REFERENCE:VSCALE` / `:REF:VSC` | 设置或查询指定参考通道的垂直档位 | 3.20.2 | 251 |
| `:REFerence:VOFFset` | `:REFERENCE:VOFFSET` / `:REF:VOFF` | 设置或查询指定参考通道的垂直偏移 | 3.20.3 | 252 |
| `:REFerence:RESet` | `:REFERENCE:RESET` / `:REF:RES` | 复位指定参考通道 | 3.20.4 | 253 |
| `:REFerence:CURRent` | `:REFERENCE:CURRENT` / `:REF:CURR` | 设置当前参考通道 | 3.20.5 | 253 |
| `:REFerence:SAVE` | `:REFERENCE:SAVE` / `:REF:SAVE` | 将指定参考通道的波形保存到内存，作为参考波形 | 3.20.6 | 254 |
| `:REFerence:COLor` | `:REFERENCE:COLOR` / `:REF:COL` | 设置或查询指定参考通道的颜色 | 3.20.7 | 254 |
| `:REFerence:LABel:ENABle` | `:REFERENCE:LABEL:ENABLE` / `:REF:LAB:ENAB` | 打开或关闭所有参考通道标签的显示，或查询所有参考通道标签的显示状态 | 3.20.8 | 255 |
| `:REFerence:LABel:CONTent` | `:REFERENCE:LABEL:CONTENT` / `:REF:LAB:CONT` | 设置或查询指定参考通道的标签 | 3.20.9 | 255 |

<details><summary>3.20 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.20.1 | `:REFerence:SOURce <ref>,<chan>` ; `:REFerence:SOURce? <ref>` |
| 3.20.2 | `:REFerence:VSCale <ref>,<scale>` ; `:REFerence:VSCale? <ref>` |
| 3.20.3 | `:REFerence:VOFFset <ref>,<offset>` ; `:REFerence:VOFFset? <ref>` |
| 3.20.4 | `:REFerence:RESet <ref>` |
| 3.20.5 | `:REFerence:CURRent <ref>` |
| 3.20.6 | `:REFerence:SAVE <ref>` |
| 3.20.7 | `:REFerence:COLor <ref>, <color>` ; `:REFerence:COLor? <ref>` |
| 3.20.8 | `:REFerence:LABel:ENABle <bool>` ; `:REFerence:LABel:ENABle?` |
| 3.20.9 | `:REFerence:LABel:CONTent <ref>,<str>` ; `:REFerence:LABel:CONTent? <ref>` |

</details>

## 3.21 存储功能命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:SAVE:IMAGe:INVert` | `:SAVE:IMAGE:INVERT` / `:SAVE:IMAG:INV` | 打开或关闭图像存储时的反色功能，或查询反色功能的状态 | 3.21.1 | 256 |
| `:SAVE:IMAGe:COLor` | `:SAVE:IMAGE:COLOR` / `:SAVE:IMAG:COL` | 设置图像存储时的图像颜色为彩色或灰度，或查询图像存储时的图像颜色 | 3.21.2 | 257 |
| `:SAVE:IMAGe:FORMat` | `:SAVE:IMAGE:FORMAT` / `:SAVE:IMAG:FORM` | 设置或查询图像存储的格式 | 3.21.3 | 257 |
| `:SAVE:IMAGe:HEADer` | `:SAVE:IMAGE:HEADER` / `:SAVE:IMAG:HEAD` | 设置或查询图像页眉显示状态 | 3.21.4 | 258 |
| `:SAVE:IMAGe:DATA?` | `:SAVE:IMAGE:DATA?` / `:SAVE:IMAG:DATA?` | 查询返回当前显示图像的位图数据流 | 3.21.5 | 258 |
| `:SAVE:PATHname` | `:SAVE:PATHNAME` / `:SAVE:PATH` | 设置或查询文件保存路径 | 3.21.6 | 259 |
| `:SAVE:IMAGe` | `:SAVE:IMAGE` / `:SAVE:IMAG` | 将示波器截图以文件形式存储到path指定的位置 | 3.21.7 | 259 |
| `:SAVE:SETup` | `:SAVE:SETUP` / `:SAVE:SET` | 将示波器当前设置以文件形式存储到path指定的位置 | 3.21.8 | 260 |
| `:SAVE:WAVeform` | `:SAVE:WAVEFORM` / `:SAVE:WAV` | 将示波器屏幕波形数据以文件形式存储到path指定的位置 | 3.21.9 | 261 |
| `:SAVE:MASK` | `:SAVE:MASK` / `:SAVE:MASK` | 保存mask模板 | 3.21.10 | 262 |
| `:SAVE:MEMory:WAVeform` | `:SAVE:MEMORY:WAVEFORM` / `:SAVE:MEM:WAV` | 将示波器内存波形数据以文件形式存储到path指定的位置 | 3.21.11 | 262 |
| `:SAVE:STATus?` | `:SAVE:STATUS?` / `:SAVE:STAT?` | 查询存储状态 | 3.21.12 | 263 |
| `:SAVE:OVERlap` | `:SAVE:OVERLAP` / `:SAVE:OVER` | 设置或查询文件覆盖功能是否打开 | 3.21.13 | 263 |
| `:SAVE:PREFix` | `:SAVE:PREFIX` / `:SAVE:PREF` | 设置或查询文件名前缀 | 3.21.14 | 264 |
| `:SAVe:SMB:SERVerpath` | `:SAVE:SMB:SERVERPATH` / `:SAV:SMB:SERV` | 设置或查询SMB文件共享的服务器路径 | 3.21.15 | 265 |
| `:SAVe:SMB:USERname` | `:SAVE:SMB:USERNAME` / `:SAV:SMB:USER` | 设置或查询SMB文件共享的用户名 | 3.21.16 | 265 |
| `:SAVe:SMB:PASSword` | `:SAVE:SMB:PASSWORD` / `:SAV:SMB:PASS` | 设置或查询SMB文件共享的密码 | 3.21.17 | 266 |
| `:SAVe:SMB:AUToconnect` | `:SAVE:SMB:AUTOCONNECT` / `:SAV:SMB:AUT` | 设置或查询SMB文件共享自动连接状态 | 3.21.18 | 266 |
| `:SAVe:SMB:CONNect` | `:SAVE:SMB:CONNECT` / `:SAV:SMB:CONN` | 配置SMB文件共享连接 | 3.21.19 | 267 |
| `:SAVe:SMB:DISConnect` | `:SAVE:SMB:DISCONNECT` / `:SAV:SMB:DISC` | 配置SMB文件共享断开 | 3.21.20 | 267 |
| `:SAVe:SMB:CONState?` | `:SAVE:SMB:CONSTATE?` / `:SAV:SMB:CONS?` | 查询SMB文件共享连接状态 | 3.21.21 | 268 |
| `:LOAD:SETup` | `:LOAD:SETUP` / `:LOAD:SET` | 从path指定的位置加载示波器的设置文件 | 3.21.22 | 268 |
| `:LOAD:MASK` | `:LOAD:MASK` / `:LOAD:MASK` | 加载mask模板 | 3.21.23 | 269 |

<details><summary>3.21 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.21.1 | `:SAVE:IMAGe:INVert <bool>` ; `:SAVE:IMAGe:INVert?` |
| 3.21.2 | `:SAVE:IMAGe:COLor <color>` ; `:SAVE:IMAGe:COLor?` |
| 3.21.3 | `:SAVE:IMAGe:FORMat <format>` ; `:SAVE:IMAGe:FORMat?` |
| 3.21.4 | `:SAVE:IMAGe:HEADer <bool>` ; `:SAVE:IMAGe:HEADer?` |
| 3.21.5 | `:SAVE:IMAGe:DATA?` |
| 3.21.6 | `:SAVE:PATHname <name>` ; `:SAVE:PATHname?` |
| 3.21.7 | `:SAVE:IMAGe <path>` |
| 3.21.8 | `:SAVE:SETup <path>` |
| 3.21.9 | `:SAVE:WAVeform <path>` |
| 3.21.10 | `:SAVE:MASK <path>` |
| 3.21.11 | `:SAVE:MEMory:WAVeform <path>` |
| 3.21.12 | `:SAVE:STATus?` |
| 3.21.13 | `:SAVE:OVERlap <bool>` ; `:SAVE:OVERlap?` |
| 3.21.14 | `:SAVE:PREFix <name>` ; `:SAVE:PREFix?` |
| 3.21.15 | `:SAVe:SMB:SERVerpath <path>` ; `:SAVe:SMB:SERVerpath?` |
| 3.21.16 | `:SAVe:SMB:USERname <name>` ; `:SAVe:SMB:USERname?` |
| 3.21.17 | `:SAVe:SMB:PASSword <password>` ; `:SAVe:SMB:PASSword?` |
| 3.21.18 | `:SAVe:SMB:AUToconnect <bool>` ; `:SAVe:SMB:AUToconnect?` |
| 3.21.19 | `:SAVe:SMB:CONNect` |
| 3.21.20 | `:SAVe:SMB:DISConnect` |
| 3.21.21 | `:SAVe:SMB:CONState?` |
| 3.21.22 | `:LOAD:SETup <path>` |
| 3.21.23 | `:LOAD:MASK <path>` |

</details>

## 3.22 搜索命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:SEARch:COUNt?` | `:SEARCH:COUNT?` / `:SEAR:COUN?` | 查询搜索事件总数 | 3.22.1 | 270 |
| `:SEARch:STATe` | `:SEARCH:STATE` / `:SEAR:STAT` | 打开或关闭搜索功能，或查询搜索功能的状态 | 3.22.2 | 270 |
| `:SEARch:MODE` | `:SEARCH:MODE` / `:SEAR:MODE` | 设置搜索类型 | 3.22.3 | 271 |
| `:SEARch:EVENt` | `:SEARCH:EVENT` / `:SEAR:EVEN` | 设置导航到一个搜索事件 | 3.22.4 | 271 |
| `:SEARch:VALue?` | `:SEARCH:VALUE?` / `:SEAR:VAL?` | 查询标记号为x处的时间位置 | 3.22.5 | 272 |
| `:SEARch:EDGE:SLOPe` | `:SEARCH:EDGE:SLOPE` / `:SEAR:EDGE:SLOP` | 设置或查询搜索类型为边沿时的边沿类型 | 3.22.6 | 272 |
| `:SEARch:EDGE:SOURce` | `:SEARCH:EDGE:SOURCE` / `:SEAR:EDGE:SOUR` | 设置或查询搜索类型为边沿时的信源 | 3.22.7 | 273 |
| `:SEARch:EDGE:THReshold` | `:SEARCH:EDGE:THRESHOLD` / `:SEAR:EDGE:THR` | 设置或查询搜索类型为边沿时的阈值 | 3.22.8 | 273 |
| `:SEARch:PULSe:POLarity` | `:SEARCH:PULSE:POLARITY` / `:SEAR:PULS:POL` | 选择或查询搜索类型为脉宽时的极性 | 3.22.9 | 274 |
| `:SEARch:PULSe:QUALifier` | `:SEARCH:PULSE:QUALIFIER` / `:SEAR:PULS:QUAL` | 选择或查询搜索类型为脉宽时的搜索条件 | 3.22.10 | 275 |
| `:SEARch:PULSe:SOURce` | `:SEARCH:PULSE:SOURCE` / `:SEAR:PULS:SOUR` | 设置或查询搜索类型为脉宽时的信源 | 3.22.11 | 275 |
| `:SEARch:PULSe:UWIDth` | `:SEARCH:PULSE:UWIDTH` / `:SEAR:PULS:UWID` | 设置或查询搜索类型为脉宽时的脉宽上限值 | 3.22.12 | 276 |
| `:SEARch:PULSe:LWIDth` | `:SEARCH:PULSE:LWIDTH` / `:SEAR:PULS:LWID` | 设置或查询搜索类型为脉宽时的脉宽下限值 | 3.22.13 | 276 |
| `:SEARch:PULSe:THReshold` | `:SEARCH:PULSE:THRESHOLD` / `:SEAR:PULS:THR` | 设置或查询搜索类型为脉宽时的阈值 | 3.22.14 | 277 |

<details><summary>3.22 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.22.1 | `:SEARch:COUNt?` |
| 3.22.2 | `:SEARch:STATe <bool>` ; `:SEARch:STATe?` |
| 3.22.3 | `:SEARch:MODE <value>` ; `:SEARch:MODE?` |
| 3.22.4 | `:SEARch:EVENt <value>` ; `:SEARch:EVENt?` |
| 3.22.5 | `:SEARch:VALue? <x>` |
| 3.22.6 | `:SEARch:EDGE:SLOPe <slope>` ; `:SEARch:EDGE:SLOPe?` |
| 3.22.7 | `:SEARch:EDGE:SOURce <source>` ; `:SEARch:EDGE:SOURce?` |
| 3.22.8 | `:SEARch:EDGE:THReshold <thre>` ; `:SEARch:EDGE:THReshold?` |
| 3.22.9 | `:SEARch:PULSe:POLarity <polarity>` ; `:SEARch:PULSe:POLarity?` |
| 3.22.10 | `:SEARch:PULSe:QUALifier <qualifier>` ; `:SEARch:PULSe:QUALifier?` |
| 3.22.11 | `:SEARch:PULSe:SOURce <source>` ; `:SEARch:PULSe:SOURce?` |
| 3.22.12 | `:SEARch:PULSe:UWIDth <width>` ; `:SEARch:PULSe:UWIDth?` |
| 3.22.13 | `:SEARch:PULSe:LWIDth <width>` ; `:SEARch:PULSe:LWIDth?` |
| 3.22.14 | `:SEARch:PULSe:THReshold <thre>` ; `:SEARch:PULSe:THReshold?` |

</details>

## 3.23 导航命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:NAVigate:ENABle` | `:NAVIGATE:ENABLE` / `:NAV:ENAB` | 设置或查询导航功能开关状态 | 3.23.1 | 278 |
| `:NAVigate:MODE` | `:NAVIGATE:MODE` / `:NAV:MODE` | 设置或查询导航模式 | 3.23.2 | 278 |
| `:NAVigate:TIME:SPEed` | `:NAVIGATE:TIME:SPEED` / `:NAV:TIME:SPE` | 设置或查询时间导航模式的波形播放速度 | 3.23.3 | 279 |
| `:NAVigate:TIME:PLAY` | `:NAVIGATE:TIME:PLAY` / `:NAV:TIME:PLAY` | 设置或查询时间导航是否开始播放波形 | 3.23.4 | 279 |
| `:NAVigate:TIME:END` | `:NAVIGATE:TIME:END` / `:NAV:TIME:END` | 设置时间导航模式波形播放到最右端（末尾） | 3.23.5 | 280 |
| `:NAVigate:TIME:STARt` | `:NAVIGATE:TIME:START` / `:NAV:TIME:STAR` | 设置时间导航模式波形播放到最左端（起始） | 3.23.6 | 281 |
| `:NAVigate:TIME:NEXT` | `:NAVIGATE:TIME:NEXT` / `:NAV:TIME:NEXT` | 设置时间导航模式波形向右偏移 | 3.23.7 | 281 |
| `:NAVigate:TIME:BACK` | `:NAVIGATE:TIME:BACK` / `:NAV:TIME:BACK` | 设置时间导航模式波形向左偏移 | 3.23.8 | 281 |
| `:NAVigate:SEARch:END` | `:NAVIGATE:SEARCH:END` / `:NAV:SEAR:END` | 设置事件导航指向最后一个事件 | 3.23.9 | 282 |
| `:NAVigate:SEARch:STARt` | `:NAVIGATE:SEARCH:START` / `:NAV:SEAR:STAR` | 设置事件导航指向第一个事件 | 3.23.10 | 282 |
| `:NAVigate:SEARch:NEXT` | `:NAVIGATE:SEARCH:NEXT` / `:NAV:SEAR:NEXT` | 设置事件导航指向下一个事件 | 3.23.11 | 283 |
| `:NAVigate:SEARch:BACK` | `:NAVIGATE:SEARCH:BACK` / `:NAV:SEAR:BACK` | 设置事件导航指向上一个事件 | 3.23.12 | 283 |

<details><summary>3.23 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.23.1 | `:NAVigate:ENABle <bool>` ; `:NAVigate:ENABle?` |
| 3.23.2 | `:NAVigate:MODE <mode>` ; `:NAVigate:MODE?` |
| 3.23.3 | `:NAVigate:TIME:SPEed <speed>` ; `:NAVigate:TIME:SPEed?` |
| 3.23.4 | `:NAVigate:TIME:PLAY <bool>` ; `:NAVigate:TIME:PLAY?` |
| 3.23.5 | `:NAVigate:TIME:END` |
| 3.23.6 | `:NAVigate:TIME:STARt` |
| 3.23.7 | `:NAVigate:TIME:NEXT` |
| 3.23.8 | `:NAVigate:TIME:BACK` |
| 3.23.9 | `:NAVigate:SEARch:END` |
| 3.23.10 | `:NAVigate:SEARch:STARt` |
| 3.23.11 | `:NAVigate:SEARch:NEXT` |
| 3.23.12 | `:NAVigate:SEARch:BACK` |

</details>

## 3.24 辅助命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:SYSTem:AOUTput` | `:SYSTEM:AOUTPUT` / `:SYST:AOUT` | 设置或查询后面板[AUXOUT]连接器输出的信号类型 | 3.24.1 | 284 |
| `:SYSTem:LANGuage` | `:SYSTEM:LANGUAGE` / `:SYST:LANG` | 设置或查询系统语言 | 3.24.2 | 285 |
| `:SYSTem:BEEPer` | `:SYSTEM:BEEPER` / `:SYST:BEEP` | 启用或禁用蜂鸣器，或查询当前蜂鸣器的状态 | 3.24.3 | 285 |
| `:SYSTem:DATE` | `:SYSTEM:DATE` / `:SYST:DATE` | 设置或查询系统日期 | 3.24.4 | 286 |
| `:SYSTem:TIME` | `:SYSTEM:TIME` / `:SYST:TIME` | 设置或查询系统时间 | 3.24.5 | 286 |
| `:SYSTem:STIMe` | `:SYSTEM:STIME` / `:SYST:STIM` | 设置或查询是否显示系统日期时间 | 3.24.6 | 287 |
| `:SYSTem:GAMount?` | `:SYSTEM:GAMOUNT?` / `:SYST:GAM?` | 查询仪器屏幕水平方向的网格数 | 3.24.7 | 288 |
| `:SYSTem:RAMount?` | `:SYSTEM:RAMOUNT?` / `:SYST:RAM?` | 查询当前仪器的模拟通道数 | 3.24.8 | 288 |
| `:SYSTem:DGSTatus?` | `:SYSTEM:DGSTATUS?` / `:SYST:DGST?` | 查询是否有DG模块 | 3.24.9 | 288 |
| `:SYSTem:PON` | `:SYSTEM:PON` / `:SYST:PON` | 设置或查询示波器重新上电时所调用的配置类型 | 3.24.10 | 289 |
| `:SYSTem:PSTatus` | `:SYSTEM:PSTATUS` / `:SYST:PST` | 设置或查询仪器的电源状态 | 3.24.11 | 289 |
| `:SYSTem:RESet` | `:SYSTEM:RESET` / `:SYST:RES` | 使系统重新上电 | 3.24.12 | 290 |
| `:SYSTem:VERSion?` | `:SYSTEM:VERSION?` / `:SYST:VERS?` | 查询系统使用的SCPI版本号 | 3.24.13 | 290 |
| `:SYSTem:LOCKed` | `:SYSTEM:LOCKED` / `:SYST:LOCK` | 打开或关闭屏幕和键盘锁定功能，或者查询屏幕和键盘锁定功能的状态 | 3.24.14 | 291 |
| `:SYSTem:MODules?` | `:SYSTEM:MODULES?` / `:SYST:MOD?` | 查询硬件模块 | 3.24.15 | 291 |
| `:SYSTem:OPTion:INSTall` | `:SYSTEM:OPTION:INSTALL` / `:SYST:OPT:INST` | 安装选件 | 3.24.16 | 292 |
| `:SYSTem:OPTion:UNINstall` | `:SYSTEM:OPTION:UNINSTALL` / `:SYST:OPT:UNIN` | 卸载已安装的全部正式版选件 | 3.24.17 | 293 |
| `:SYSTem:OPTion:STATus?` | `:SYSTEM:OPTION:STATUS?` / `:SYST:OPT:STAT?` | 查询选件的激活状态 | 3.24.18 | 294 |
| `:SYSTem:OPTion:VALid?` | `:SYSTEM:OPTION:VALID?` / `:SYST:OPT:VAL?` | 查询选件的激活状态 | 3.24.19 | 295 |
| `:SYSTem:SETup` | `:SYSTEM:SETUP` / `:SYST:SET` | 发送或读取系统设置文件数据流 | 3.24.20 | 296 |
| `:SYSTem:ERRor[:NEXT]?` | `:SYSTEM:ERROR[:NEXT]?` / `:SYST:ERR[:NEXT]?` | 查询并删除系统的错误队列消息 | 3.24.21 | 297 |
| `:SYSTem:AUToscale` | `:SYSTEM:AUTOSCALE` / `:SYST:AUT` | 禁用或恢复AUTO功能，或查询AUTO功能状态 | 3.24.22 | 297 |
| `:SYSTem:KEYBoard:CHECk?` | `:SYSTEM:KEYBOARD:CHECK?` / `:SYST:KEYB:CHEC?` | 查询键盘板的状态 | 3.24.23 | 298 |
| `:SYSTem:LOWPower` | `:SYSTEM:LOWPOWER` / `:SYST:LOWP` | 设置或查询仪器是否处于低功耗模式 | 3.24.24 | 299 |

<details><summary>3.24 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.24.1 | `:SYSTem:AOUTput <auxoutput>` ; `:SYSTem:AOUTput?` |
| 3.24.2 | `:SYSTem:LANGuage <language>` ; `:SYSTem:LANGuage?` |
| 3.24.3 | `:SYSTem:BEEPer <bool>` ; `:SYSTem:BEEPer?` |
| 3.24.4 | `:SYSTem:DATE <year>,<month>,<day>` ; `:SYSTem:DATE?` |
| 3.24.5 | `:SYSTem:TIME <hours>,<minutes>,<seconds>` ; `:SYSTem:TIME?` |
| 3.24.6 | `:SYSTem:STIMe <bool>` ; `:SYSTem:STIMe?` |
| 3.24.7 | `:SYSTem:GAMount?` |
| 3.24.8 | `:SYSTem:RAMount?` |
| 3.24.9 | `:SYSTem:DGSTatus?` |
| 3.24.10 | `:SYSTem:PON <power_on>` ; `:SYSTem:PON?` |
| 3.24.11 | `:SYSTem:PSTatus <sat>` ; `:SYSTem:PSTatus?` |
| 3.24.12 | `:SYSTem:RESet` |
| 3.24.13 | `:SYSTem:VERSion?` |
| 3.24.14 | `:SYSTem:LOCKed <bool>` ; `:SYSTem:LOCKed?` |
| 3.24.15 | `:SYSTem:MODules?` |
| 3.24.16 | `:SYSTem:OPTion:INSTall <license>` |
| 3.24.17 | `:SYSTem:OPTion:UNINstall` |
| 3.24.18 | `:SYSTem:OPTion:STATus? <type>` |
| 3.24.19 | `:SYSTem:OPTion:VALid? <type>` |
| 3.24.20 | `:SYSTem:SETup <setup_data>` ; `:SYSTem:SETup?` |
| 3.24.21 | `:SYSTem:ERRor[:NEXT]?` |
| 3.24.22 | `:SYSTem:AUToscale <bool>` ; `:SYSTem:AUToscale?` |
| 3.24.23 | `:SYSTem:KEYBoard:CHECk?` |
| 3.24.24 | `:SYSTem:LOWPower <x>` ; `:SYSTem:LOWPower?` |

</details>

## 3.25 函数/任意波形发生器命令子系统（选件）

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:SOURce<n>:OUTPut:STATe` | `:SOURCE<N>:OUTPUT:STATE` / `:SOUR<>:OUTP:STAT` | 打开或关闭通道的输出，或查询通道的输出状态 | 3.25.1 | 299 |
| `:SOURce<n>:FUNCtion` | `:SOURCE<N>:FUNCTION` / `:SOUR<>:FUNC` | 设置或查询指定函数/任意波形发生器通道输出基本波的波形 | 3.25.2 | 300 |
| `:SOURce<n>:LOAD:ARBitrary` | `:SOURCE<N>:LOAD:ARBITRARY` / `:SOUR<>:LOAD:ARB` | 从指定路径加载任意波波表文件 | 3.25.3 | 301 |
| `:SOURce<n>:FREQuency` | `:SOURCE<N>:FREQUENCY` / `:SOUR<>:FREQ` | 设置或查询基本波的频率 | 3.25.4 | 301 |
| `:SOURce<n>:PERiod` | `:SOURCE<N>:PERIOD` / `:SOUR<>:PER` | 设置或查询指定函数/任意波形发生器通道输出基本波的周期，单位s | 3.25.5 | 302 |
| `:SOURce<n>:PHASe` | `:SOURCE<N>:PHASE` / `:SOUR<>:PHAS` | 设置或查询指定函数/任意波形发生器通道输出基本波的相位 | 3.25.6 | 303 |
| `:SOURce<n>:PHASe:SYNChronize` | `:SOURCE<N>:PHASE:SYNCHRONIZE` / `:SOUR<>:PHAS:SYNC` | 执行一次同相位操作 | 3.25.7 | 303 |
| `:SOURce<n>:FUNCtion:RAMP:SYMMetry` | `:SOURCE<N>:FUNCTION:RAMP:SYMMETRY` / `:SOUR<>:FUNC:RAMP:SYMM` | 设置或查询指定函数/任意波形发生器通道输出锯齿波的对称性 | 3.25.8 | 304 |
| `:SOURce<n>:FUNCtion:SQUare:DUTY` | `:SOURCE<N>:FUNCTION:SQUARE:DUTY` / `:SOUR<>:FUNC:SQU:DUTY` | 设置或查询指定函数/任意波形发生器通道输出方波的占空比 | 3.25.9 | 305 |
| `:SOURce<n>:VOLTage:AMPLitude` | `:SOURCE<N>:VOLTAGE:AMPLITUDE` / `:SOUR<>:VOLT:AMPL` | 设置或查询基本波的幅度值，单位默认为V | 3.25.10 | 305 |
| `:SOURce<n>:VOLTage:OFFSet` | `:SOURCE<N>:VOLTAGE:OFFSET` / `:SOUR<>:VOLT:OFFS` | 设置或查询基本波的幅度偏移，单位默认为V | 3.25.11 | 306 |
| `:SOURce<n>:VOLTage:HIGH` | `:SOURCE<N>:VOLTAGE:HIGH` / `:SOUR<>:VOLT:HIGH` | 设置或查询指定函数/任意波形发生器通道输出基本波的高电平值，单位默认为V | 3.25.12 | 307 |
| `:SOURce<n>:VOLTage:LOW` | `:SOURCE<N>:VOLTAGE:LOW` / `:SOUR<>:VOLT:LOW` | 设置或查询指定函数/任意波形发生器通道输出基本波的低电平值，单位默认为V | 3.25.13 | 308 |
| `:SOURce<n>:IMPedance` | `:SOURCE<N>:IMPEDANCE` / `:SOUR<>:IMP` | 设置或查询指定函数/任意波形发生器通道的输出阻抗 | 3.25.14 | 309 |
| `:SOURce<n>:MOD:STATe` | `:SOURCE<N>:MOD:STATE` / `:SOUR<>:MOD:STAT` | 打开或关闭调制输出，或查询调制输出状态 | 3.25.15 | 309 |
| `:SOURce<n>:MOD:TYPe` | `:SOURCE<N>:MOD:TYPE` / `:SOUR<>:MOD:TYP` | 设置或查询指定函数/任意波形发生器通道的调制类型 | 3.25.16 | 310 |
| `:SOURce<n>:MOD:AM:DEPTh` | `:SOURCE<N>:MOD:AM:DEPTH` / `:SOUR<>:MOD:AM:DEPT` | 设置或查询AM的调制深度 | 3.25.17 | 310 |
| `:SOURce<n>:MOD:AM:INTernal:FREQuency` | `:SOURCE<N>:MOD:AM:INTERNAL:FREQUENCY` / `:SOUR<>:MOD:AM:INT:FREQ` | 设置或查询AM的调制频率 | 3.25.18 | 311 |
| `:SOURce<n>:MOD:AM:INTernal:FUNCtion` | `:SOURCE<N>:MOD:AM:INTERNAL:FUNCTION` / `:SOUR<>:MOD:AM:INT:FUNC` | 设置或查询AM的调制波形 | 3.25.19 | 312 |
| `:SOURce<n>:MOD:FM:DEViation` | `:SOURCE<N>:MOD:FM:DEVIATION` / `:SOUR<>:MOD:FM:DEV` | 设置或查询FM的频率偏移 | 3.25.20 | 313 |
| `:SOURce<n>:MOD:FM:INTernal:FREQuency` | `:SOURCE<N>:MOD:FM:INTERNAL:FREQUENCY` / `:SOUR<>:MOD:FM:INT:FREQ` | 设置或查询FM的调制频率 | 3.25.21 | 313 |
| `:SOURce<n>:MOD:FM:INTernal:FUNCtion` | `:SOURCE<N>:MOD:FM:INTERNAL:FUNCTION` / `:SOUR<>:MOD:FM:INT:FUNC` | 设置或查询FM的调制波形 | 3.25.22 | 314 |
| `:SOURce<n>:MOD:PM:DEViation` | `:SOURCE<N>:MOD:PM:DEVIATION` / `:SOUR<>:MOD:PM:DEV` | 设置或查询PM的相位偏移 | 3.25.23 | 315 |
| `:SOURce<n>:MOD:PM:INTernal:FREQuency` | `:SOURCE<N>:MOD:PM:INTERNAL:FREQUENCY` / `:SOUR<>:MOD:PM:INT:FREQ` | 设置或查询PM的调制频率 | 3.25.24 | 315 |
| `:SOURce<n>:MOD:PM:INTernal:FUNCtion` | `:SOURCE<N>:MOD:PM:INTERNAL:FUNCTION` / `:SOUR<>:MOD:PM:INT:FUNC` | 设置或查询PM的调制波形 | 3.25.25 | 316 |

<details><summary>3.25 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.25.1 | `:SOURce<n>:OUTPut:STATe <state>` ; `:SOURce<n>:OUTPut:STATe?` |
| 3.25.2 | `:SOURce<n>:FUNCtion <wave>` ; `:SOURce<n>:FUNCtion?` |
| 3.25.3 | `:SOURce<n>:LOAD:ARBitrary <path>` ; `:SOURce<n>:LOAD:ARBitrary?` |
| 3.25.4 | `:SOURce<n>:FREQuency <freq>` ; `:SOURce<n>:FREQuency?` |
| 3.25.5 | `:SOURce<n>:PERiod <period>` ; `:SOURce<n>:PERiod?` |
| 3.25.6 | `:SOURce<n>:PHASe <phase>` ; `:SOURce<n>:PHASe?` |
| 3.25.7 | `:SOURce<n>:PHASe:SYNChronize` |
| 3.25.8 | `:SOURce<n>:FUNCtion:RAMP:SYMMetry <symm>` ; `:SOURce<n>:FUNCtion:RAMP:SYMMetry?` |
| 3.25.9 | `:SOURce<n>:FUNCtion:SQUare:DUTY <duty>` ; `:SOURce<n>:FUNCtion:SQUare:DUTY?` |
| 3.25.10 | `:SOURce<n>:VOLTage:AMPLitude <ampl>` ; `:SOURce<n>:VOLTage:AMPLitude?` |
| 3.25.11 | `:SOURce<n>:VOLTage:OFFSet <offset>` ; `:SOURce<n>:VOLTage:OFFSet?` |
| 3.25.12 | `:SOURce<n>:VOLTage:HIGH <value>` ; `:SOURce<n>:VOLTage:HIGH?` |
| 3.25.13 | `:SOURce<n>:VOLTage:LOW <value>` ; `:SOURce<n>:VOLTage:LOW?` |
| 3.25.14 | `:SOURce<n>:IMPedance <imp>` ; `:SOURce<n>:IMPedance?` |
| 3.25.15 | `:SOURce<n>:MOD:STATe <state>` ; `:SOURce<n>:MOD:STATe?` |
| 3.25.16 | `:SOURce<n>:MOD:TYPe <type>` ; `:SOURce<n>:MOD:TYPe?` |
| 3.25.17 | `:SOURce<n>:MOD:AM:DEPTh <depth>` ; `:SOURce<n>:MOD:AM:DEPTh?` |
| 3.25.18 | `:SOURce<n>:MOD:AM:INTernal:FREQuency <freq>` ; `:SOURce<n>:MOD:AM:INTernal:FREQuency?` |
| 3.25.19 | `:SOURce<n>:MOD:AM:INTernal:FUNCtion <func>` ; `:SOURce<n>:MOD:AM:INTernal:FUNCtion?` |
| 3.25.20 | `:SOURce<n>:MOD:FM:DEViation <deviation>` ; `:SOURce<n>:MOD:FM:DEViation?` |
| 3.25.21 | `:SOURce<n>:MOD:FM:INTernal:FREQuency <freq>` ; `:SOURce<n>:MOD:FM:INTernal:FREQuency?` |
| 3.25.22 | `:SOURce<n>:MOD:FM:INTernal:FUNCtion <func>` ; `:SOURce<n>:MOD:FM:INTernal:FUNCtion?` |
| 3.25.23 | `:SOURce<n>:MOD:PM:DEViation <deviation>` ; `:SOURce<n>:MOD:PM:DEViation?` |
| 3.25.24 | `:SOURce<n>:MOD:PM:INTernal:FREQuency <freq>` ; `:SOURce<n>:MOD:PM:INTernal:FREQuency?` |
| 3.25.25 | `:SOURce<n>:MOD:PM:INTernal:FUNCtion <function>` ; `:SOURce<n>:MOD:PM:INTernal:FUNCtion?` |

</details>

## 3.26 时基命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:TIMebase:DELay:ENABle` | `:TIMEBASE:DELAY:ENABLE` / `:TIM:DEL:ENAB` | 打开或关闭延迟扫描，或查询延迟扫描的状态 | 3.26.1 | 317 |
| `:TIMebase:DELay:OFFSet` | `:TIMEBASE:DELAY:OFFSET` / `:TIM:DEL:OFFS` | 设置延迟扫描偏移，或查询延迟时基偏移 | 3.26.2 | 318 |
| `:TIMebase:DELay:SCALe` | `:TIMEBASE:DELAY:SCALE` / `:TIM:DEL:SCAL` | 设置或查询延迟时基档位 | 3.26.3 | 318 |
| `:TIMebase[:MAIN][:OFFSet]` | `:TIMEBASE[:MAIN][:OFFSET]` / `:TIM[:MAIN][:OFFS]` | 设置或查询主时基偏移 | 3.26.4 | 319 |
| `:TIMebase[:MAIN]:SCALe` | `:TIMEBASE[:MAIN]:SCALE` / `:TIM[:MAIN]:SCAL` | 设置或查询主时基的档位 | 3.26.5 | 320 |
| `:TIMebase:MODE` | `:TIMEBASE:MODE` / `:TIM:MODE` | 设置或查询水平时基模式 | 3.26.6 | 320 |
| `:TIMebase:HREFerence:MODE` | `:TIMEBASE:HREFERENCE:MODE` / `:TIM:HREF:MODE` | 设置或查询水平参考模式 | 3.26.7 | 321 |
| `:TIMebase:HREFerence:POSition` | `:TIMEBASE:HREFERENCE:POSITION` / `:TIM:HREF:POS` | 设置或查询波形水平扩展或压缩时用户自定义的参考位置 | 3.26.8 | 322 |
| `:TIMebase:VERNier` | `:TIMEBASE:VERNIER` / `:TIM:VERN` | 打开或关闭水平档位微调功能，或查询水平档位的微调功能的状态 | 3.26.9 | 322 |
| `:TIMebase:HOTKeys` | `:TIMEBASE:HOTKEYS` / `:TIM:HOTK` | 设置运行状态 | 3.26.10 | 323 |
| `:TIMebase:ROLL` | `:TIMEBASE:ROLL` / `:TIM:ROLL` | 设置或查询ROLL时基模式的状态 | 3.26.11 | 323 |
| `:TIMebase:XY:ENABle` | `:TIMEBASE:XY:ENABLE` / `:TIM:XY:ENAB` | 打开或关闭XY时基模式，或查询XY时基模式的状态 | 3.26.12 | 324 |
| `:TIMebase:XY:X` | `:TIMEBASE:XY:X` / `:TIM:XY:X` | 设置或查询水平时基为XY模式下，X坐标对应的通道源 | 3.26.13 | 325 |
| `:TIMebase:XY:Y` | `:TIMEBASE:XY:Y` / `:TIM:XY:Y` | 设置或查询水平时基为XY模式下，Y坐标对应的通道源 | 3.26.14 | 325 |
| `:TIMebase:XY:GRID` | `:TIMEBASE:XY:GRID` / `:TIM:XY:GRID` | 设置或查询XY显示的网格类型 | 3.26.15 | 326 |

<details><summary>3.26 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.26.1 | `:TIMebase:DELay:ENABle <bool>` ; `:TIMebase:DELay:ENABle?` |
| 3.26.2 | `:TIMebase:DELay:OFFSet <offset>` ; `:TIMebase:DELay:OFFSet?` |
| 3.26.3 | `:TIMebase:DELay:SCALe <scale>` ; `:TIMebase:DELay:SCALe?` |
| 3.26.4 | `:TIMebase[:MAIN][:OFFSet] <offset>` ; `:TIMebase[:MAIN][:OFFSet]?` |
| 3.26.5 | `:TIMebase[:MAIN]:SCALe <scale>` ; `:TIMebase[:MAIN]:SCALe?` |
| 3.26.6 | `:TIMebase:MODE <mode>` ; `:TIMebase:MODE?` |
| 3.26.7 | `:TIMebase:HREFerence:MODE <href>` ; `:TIMebase:HREFerence:MODE?` |
| 3.26.8 | `:TIMebase:HREFerence:POSition <pos>` ; `:TIMebase:HREFerence:POSition?` |
| 3.26.9 | `:TIMebase:VERNier <bool>` ; `:TIMebase:VERNier?` |
| 3.26.10 | `:TIMebase:HOTKeys <action>` |
| 3.26.11 | `:TIMebase:ROLL <value>` ; `:TIMebase:ROLL?` |
| 3.26.12 | `:TIMebase:XY:ENABle <bool>` ; `:TIMebase:XY:ENABle?` |
| 3.26.13 | `:TIMebase:XY:X <s>` ; `:TIMebase:XY:X?` |
| 3.26.14 | `:TIMebase:XY:Y <s>` ; `:TIMebase:XY:Y?` |
| 3.26.15 | `:TIMebase:XY:GRID <grid>` ; `:TIMebase:XY:GRID?` |

</details>

## 3.27 触发命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:TRIGger:MODE` | `:TRIGGER:MODE` / `:TRIG:MODE` | 设置或查询触发类型 | 3.27.1 | 326 |
| `:TRIGger:COUPling` | `:TRIGGER:COUPLING` / `:TRIG:COUP` | 选择或查询触发耦合类型 | 3.27.2 | 327 |
| `:TRIGger:STATus?` | `:TRIGGER:STATUS?` / `:TRIG:STAT?` | 查询当前的触发状态 | 3.27.3 | 328 |
| `:TRIGger:SWEep` | `:TRIGGER:SWEEP` / `:TRIG:SWE` | 设置或查询触发方式 | 3.27.4 | 328 |
| `:TRIGger:HOLDoff` | `:TRIGGER:HOLDOFF` / `:TRIG:HOLD` | 设置或查询触发释抑时间，默认单位为s | 3.27.5 | 329 |
| `:TRIGger:NREJect` | `:TRIGGER:NREJECT` / `:TRIG:NREJ` | 打开或关闭噪声抑制，或查询噪声抑制的状态 | 3.27.6 | 330 |
| `:TRIGger:POSition?` | `:TRIGGER:POSITION?` / `:TRIG:POS?` | 查询波形触发位置在内存中的对应位置 | 3.27.7 | 330 |
| `:TRIGger:EDGE:SOURce` | `:TRIGGER:EDGE:SOURCE` / `:TRIG:EDGE:SOUR` | 设置或查询边沿触发的触发源 | 3.27.8.1 | 331 |
| `:TRIGger:EDGE:SLOPe` | `:TRIGGER:EDGE:SLOPE` / `:TRIG:EDGE:SLOP` | 设置或查询边沿触发的边沿类型 | 3.27.8.2 | 331 |
| `:TRIGger:EDGE:LEVel` | `:TRIGGER:EDGE:LEVEL` / `:TRIG:EDGE:LEV` | 设置或查询边沿触发时的触发电平，单位与所选信源当前幅度单位一致 | 3.27.8.3 | 332 |
| `:TRIGger:PULSe:SOURce` | `:TRIGGER:PULSE:SOURCE` / `:TRIG:PULS:SOUR` | 设置或查询脉宽触发的触发源 | 3.27.9.1 | 333 |
| `:TRIGger:PULSe:POLarity` | `:TRIGGER:PULSE:POLARITY` / `:TRIG:PULS:POL` | 设置或查询脉宽触发的极性 | 3.27.9.2 | 334 |
| `:TRIGger:PULSe:WHEN` | `:TRIGGER:PULSE:WHEN` / `:TRIG:PULS:WHEN` | 设置或查询脉宽触发的触发条件 | 3.27.9.3 | 334 |
| `:TRIGger:PULSe:UWIDth` | `:TRIGGER:PULSE:UWIDTH` / `:TRIG:PULS:UWID` | 设置或查询脉宽触发的脉宽上限值，默认单位为s | 3.27.9.4 | 335 |
| `:TRIGger:PULSe:LWIDth` | `:TRIGGER:PULSE:LWIDTH` / `:TRIG:PULS:LWID` | 设置或查询脉宽触发的脉宽下限值，默认单位为s | 3.27.9.5 | 335 |
| `:TRIGger:PULSe:LEVel` | `:TRIGGER:PULSE:LEVEL` / `:TRIG:PULS:LEV` | 设置或查询脉宽触发时的触发电平，单位与当前幅度单位一致 | 3.27.9.6 | 336 |
| `:TRIGger:SLOPe:SOURce` | `:TRIGGER:SLOPE:SOURCE` / `:TRIG:SLOP:SOUR` | 设置或查询斜率触发的触发源 | 3.27.10.1 | 337 |
| `:TRIGger:SLOPe:POLarity` | `:TRIGGER:SLOPE:POLARITY` / `:TRIG:SLOP:POL` | 设置或查询斜率触发的边沿类型 | 3.27.10.2 | 338 |
| `:TRIGger:SLOPe:WHEN` | `:TRIGGER:SLOPE:WHEN` / `:TRIG:SLOP:WHEN` | 设置或查询斜率触发的触发条件 | 3.27.10.3 | 338 |
| `:TRIGger:SLOPe:TUPPer` | `:TRIGGER:SLOPE:TUPPER` / `:TRIG:SLOP:TUPP` | 设置或查询斜率触发的时间上限值，默认单位为s | 3.27.10.4 | 339 |
| `:TRIGger:SLOPe:TLOWer` | `:TRIGGER:SLOPE:TLOWER` / `:TRIG:SLOP:TLOW` | 设置或查询斜率触发的时间下限值，默认单位为s | 3.27.10.5 | 339 |
| `:TRIGger:SLOPe:WINDow` | `:TRIGGER:SLOPE:WINDOW` / `:TRIG:SLOP:WIND` | 设置或查询斜率触发的垂直窗类型 | 3.27.10.6 | 340 |
| `:TRIGger:SLOPe:ALEVel` | `:TRIGGER:SLOPE:ALEVEL` / `:TRIG:SLOP:ALEV` | 设置或查询斜率触发时的触发电平上限，单位与当前幅度单位一致 | 3.27.10.7 | 341 |
| `:TRIGger:SLOPe:BLEVel` | `:TRIGGER:SLOPE:BLEVEL` / `:TRIG:SLOP:BLEV` | 设置或查询斜率触发时的触发电平下限，单位与当前幅度单位一致 | 3.27.10.8 | 341 |
| `:TRIGger:VIDeo:SOURce` | `:TRIGGER:VIDEO:SOURCE` / `:TRIG:VID:SOUR` | 设置或查询视频触发的触发源 | 3.27.11.1 | 342 |
| `:TRIGger:VIDeo:POLarity` | `:TRIGGER:VIDEO:POLARITY` / `:TRIG:VID:POL` | 选择或查询视频触发时的视频极性 | 3.27.11.2 | 343 |
| `:TRIGger:VIDeo:MODE` | `:TRIGGER:VIDEO:MODE` / `:TRIG:VID:MODE` | 设置或查询视频触发时的同步类型 | 3.27.11.3 | 343 |
| `:TRIGger:VIDeo:LINE` | `:TRIGGER:VIDEO:LINE` / `:TRIG:VID:LINE` | 设置或查询视频触发时同步类型为指定行时的行号 | 3.27.11.4 | 344 |
| `:TRIGger:VIDeo:STANdard` | `:TRIGGER:VIDEO:STANDARD` / `:TRIG:VID:STAN` | 设置或查询视频触发的视频标准 | 3.27.11.5 | 345 |
| `:TRIGger:VIDeo:LEVel` | `:TRIGGER:VIDEO:LEVEL` / `:TRIG:VID:LEV` | 设置或查询视频触发时的触发电平，单位与当前幅度单位一致 | 3.27.11.6 | 346 |
| `:TRIGger:PATTern:PATTern` | `:TRIGGER:PATTERN:PATTERN` / `:TRIG:PATT:PATT` | 设置或查询码型触发时每个通道的码型 | 3.27.12.1 | 347 |
| `:TRIGger:PATTern:SOURce` | `:TRIGGER:PATTERN:SOURCE` / `:TRIG:PATT:SOUR` | 设置或查询码型触发的触发源 | 3.27.12.2 | 348 |
| `:TRIGger:PATTern:LEVel` | `:TRIGGER:PATTERN:LEVEL` / `:TRIG:PATT:LEV` | 设置或查询码型触发时指定通道的触发电平，单位与当前的幅度单位一致 | 3.27.12.3 | 349 |
| `:TRIGger:DURation:SOURce` | `:TRIGGER:DURATION:SOURCE` / `:TRIG:DUR:SOUR` | 设置或查询持续时间触发的触发源 | 3.27.13.1 | 350 |
| `:TRIGger:DURation:TYPE` | `:TRIGGER:DURATION:TYPE` / `:TRIG:DUR:TYPE` | 设置或查询持续时间触发时每个通道的码型 | 3.27.13.2 | 351 |
| `:TRIGger:DURation:WHEN` | `:TRIGGER:DURATION:WHEN` / `:TRIG:DUR:WHEN` | 设置或查询持续时间触发的触发条件 | 3.27.13.3 | 351 |
| `:TRIGger:DURation:TUPPer` | `:TRIGGER:DURATION:TUPPER` / `:TRIG:DUR:TUPP` | 设置或查询持续时间触发的持续时间上限值，默认单位为s | 3.27.13.4 | 352 |
| `:TRIGger:DURation:TLOWer` | `:TRIGGER:DURATION:TLOWER` / `:TRIG:DUR:TLOW` | 设置或查询持续时间触发的持续时间下限值，默认单位为s | 3.27.13.5 | 353 |
| `:TRIGger:DURation:LEVel` | `:TRIGGER:DURATION:LEVEL` / `:TRIG:DUR:LEV` | 设置或查询持续时间触发时指定通道的触发电平，单位与当前的幅度单位一致 | 3.27.13.6 | 353 |
| `:TRIGger:TIMeout:SOURce` | `:TRIGGER:TIMEOUT:SOURCE` / `:TRIG:TIM:SOUR` | 设置或查询超时触发的触发源 | 3.27.14.1 | 354 |
| `:TRIGger:TIMeout:SLOPe` | `:TRIGGER:TIMEOUT:SLOPE` / `:TRIG:TIM:SLOP` | 设置或查询超时触发的边沿类型 | 3.27.14.2 | 355 |
| `:TRIGger:TIMeout:TIME` | `:TRIGGER:TIMEOUT:TIME` / `:TRIG:TIM:TIME` | 设置或查询超时触发的超时时间，默认单位为s，精度为1ns | 3.27.14.3 | 356 |
| `:TRIGger:TIMeout:LEVel` | `:TRIGGER:TIMEOUT:LEVEL` / `:TRIG:TIM:LEV` | 设置或查询超时触发时的触发电平，单位与当前幅度单位一致 | 3.27.14.4 | 356 |
| `:TRIGger:RUNT:SOURce` | `:TRIGGER:RUNT:SOURCE` / `:TRIG:RUNT:SOUR` | 设置或查询欠幅脉冲触发的触发源 | 3.27.15.1 | 357 |
| `:TRIGger:RUNT:POLarity` | `:TRIGGER:RUNT:POLARITY` / `:TRIG:RUNT:POL` | 设置或查询欠幅脉冲触发的脉冲极性 | 3.27.15.2 | 358 |
| `:TRIGger:RUNT:WHEN` | `:TRIGGER:RUNT:WHEN` / `:TRIG:RUNT:WHEN` | 设置或查询欠幅脉冲触发的触发脉宽条件 | 3.27.15.3 | 359 |
| `:TRIGger:RUNT:WUPPer` | `:TRIGGER:RUNT:WUPPER` / `:TRIG:RUNT:WUPP` | 设置或查询欠幅脉冲触发的脉宽上限值，默认单位为s | 3.27.15.4 | 359 |
| `:TRIGger:RUNT:WLOWer` | `:TRIGGER:RUNT:WLOWER` / `:TRIG:RUNT:WLOW` | 设置或查询欠幅脉冲触发的脉宽下限值，默认单位为s | 3.27.15.5 | 360 |
| `:TRIGger:RUNT:ALEVel` | `:TRIGGER:RUNT:ALEVEL` / `:TRIG:RUNT:ALEV` | 设置或查询欠幅脉冲触发时的触发电平上限，单位与当前幅度单位一致 | 3.27.15.6 | 361 |
| `:TRIGger:RUNT:BLEVel` | `:TRIGGER:RUNT:BLEVEL` / `:TRIG:RUNT:BLEV` | 设置或查询欠幅脉冲触发时的触发电平下限，单位与当前幅度单位一致 | 3.27.15.7 | 361 |
| `:TRIGger:WINDows:SOURce` | `:TRIGGER:WINDOWS:SOURCE` / `:TRIG:WIND:SOUR` | 设置或查询超幅触发的触发源 | 3.27.16.1 | 362 |
| `:TRIGger:WINDows:SLOPe` | `:TRIGGER:WINDOWS:SLOPE` / `:TRIG:WIND:SLOP` | 设置或查询超幅触发的边沿类型 | 3.27.16.2 | 362 |
| `:TRIGger:WINDows:POSition` | `:TRIGGER:WINDOWS:POSITION` / `:TRIG:WIND:POS` | 设置或查询超幅触发的触发位置 | 3.27.16.3 | 363 |
| `:TRIGger:WINDows:TIME` | `:TRIGGER:WINDOWS:TIME` / `:TRIG:WIND:TIME` | 设置或查询超幅触发的超幅时间 | 3.27.16.4 | 364 |
| `:TRIGger:WINDows:ALEVel` | `:TRIGGER:WINDOWS:ALEVEL` / `:TRIG:WIND:ALEV` | 设置或查询超幅触发时的触发电平上限，单位与当前幅度单位一致 | 3.27.16.5 | 364 |
| `:TRIGger:WINDows:BLEVel` | `:TRIGGER:WINDOWS:BLEVEL` / `:TRIG:WIND:BLEV` | 设置或查询超幅触发时的触发电平下限，单位与当前幅度单位一致 | 3.27.16.6 | 365 |
| `:TRIGger:DELay:SA` | `:TRIGGER:DELAY:SA` / `:TRIG:DEL:SA` | 设置或查询延迟触发时信源A的触发信源 | 3.27.17.1 | 366 |
| `:TRIGger:DELay:ASLop` | `:TRIGGER:DELAY:ASLOP` / `:TRIG:DEL:ASL` | 设置或查询延迟触发时边沿A的边沿类型 | 3.27.17.2 | 367 |
| `:TRIGger:DELay:SB` | `:TRIGGER:DELAY:SB` / `:TRIG:DEL:SB` | 设置或查询延迟触发时信源B的触发信源 | 3.27.17.3 | 367 |
| `:TRIGger:DELay:BSLop` | `:TRIGGER:DELAY:BSLOP` / `:TRIG:DEL:BSL` | 设置或查询延迟触发时边沿B的边沿类型 | 3.27.17.4 | 368 |
| `:TRIGger:DELay:TYPE` | `:TRIGGER:DELAY:TYPE` / `:TRIG:DEL:TYPE` | 设置或查询延迟触发时的触发条件 | 3.27.17.5 | 368 |
| `:TRIGger:DELay:TUPPer` | `:TRIGGER:DELAY:TUPPER` / `:TRIG:DEL:TUPP` | 设置或查询延迟触发时的延迟时间上限值，默认单位为s | 3.27.17.6 | 369 |
| `:TRIGger:DELay:TLOWer` | `:TRIGGER:DELAY:TLOWER` / `:TRIG:DEL:TLOW` | 设置或查询延迟触发时的延迟时间下限值，默认单位为s | 3.27.17.7 | 370 |
| `:TRIGger:DELay:ALEVel` | `:TRIGGER:DELAY:ALEVEL` / `:TRIG:DEL:ALEV` | 设置或查询延迟触发时信源A的阈值电平，单位与当前幅度单位一致 | 3.27.17.8 | 370 |
| `:TRIGger:DELay:BLEVel` | `:TRIGGER:DELAY:BLEVEL` / `:TRIG:DEL:BLEV` | 设置或查询延迟触发时信源B的阈值电平，单位与当前幅度单位一致 | 3.27.17.9 | 371 |
| `:TRIGger:SHOLd:DSRC` | `:TRIGGER:SHOLD:DSRC` / `:TRIG:SHOL:DSRC` | 设置或查询建立保持触发的数据源 | 3.27.18.1 | 372 |
| `:TRIGger:SHOLd:CSRC` | `:TRIGGER:SHOLD:CSRC` / `:TRIG:SHOL:CSRC` | 设置或查询建立保持触发的时钟源 | 3.27.18.2 | 373 |
| `:TRIGger:SHOLd:SLOPe` | `:TRIGGER:SHOLD:SLOPE` / `:TRIG:SHOL:SLOP` | 设置或查询建立保持触发的边沿类型 | 3.27.18.3 | 373 |
| `:TRIGger:SHOLd:PATTern` | `:TRIGGER:SHOLD:PATTERN` / `:TRIG:SHOL:PATT` | 设置或查询建立保持触发的数据类型 | 3.27.18.4 | 374 |
| `:TRIGger:SHOLd:TYPE` | `:TRIGGER:SHOLD:TYPE` / `:TRIG:SHOL:TYPE` | 设置或查询建立保持触发的触发条件 | 3.27.18.5 | 374 |
| `:TRIGger:SHOLd:STIMe` | `:TRIGGER:SHOLD:STIME` / `:TRIG:SHOL:STIM` | 设置或查询建立保持触发的建立时间，默认单位为s | 3.27.18.6 | 375 |
| `:TRIGger:SHOLd:HTIMe` | `:TRIGGER:SHOLD:HTIME` / `:TRIG:SHOL:HTIM` | 设置或查询建立保持触发的保持时间，默认单位为s | 3.27.18.7 | 376 |
| `:TRIGger:SHOLd:DLEVel` | `:TRIGGER:SHOLD:DLEVEL` / `:TRIG:SHOL:DLEV` | 设置或查询数据源的触发电平，单位与当前幅度单位一致 | 3.27.18.8 | 376 |
| `:TRIGger:SHOLd:CLEVel` | `:TRIGGER:SHOLD:CLEVEL` / `:TRIG:SHOL:CLEV` | 设置或查询时钟源的触发电平，单位与当前幅度单位一致 | 3.27.18.9 | 377 |
| `:TRIGger:NEDGe:SOURce` | `:TRIGGER:NEDGE:SOURCE` / `:TRIG:NEDG:SOUR` | 设置或查询第N边沿触发的触发源 | 3.27.19.1 | 378 |
| `:TRIGger:NEDGe:SLOPe` | `:TRIGGER:NEDGE:SLOPE` / `:TRIG:NEDG:SLOP` | 设置或查询第N边沿触发的边沿类型 | 3.27.19.2 | 379 |
| `:TRIGger:NEDGe:IDLE` | `:TRIGGER:NEDGE:IDLE` / `:TRIG:NEDG:IDLE` | 设置或查询第N边沿触发的空闲时间，默认单位为s | 3.27.19.3 | 379 |
| `:TRIGger:NEDGe:EDGE` | `:TRIGGER:NEDGE:EDGE` / `:TRIG:NEDG:EDGE` | 设置或查询第N边沿触发的边沿数 | 3.27.19.4 | 380 |
| `:TRIGger:NEDGe:LEVel` | `:TRIGGER:NEDGE:LEVEL` / `:TRIG:NEDG:LEV` | 设置或查询第N边沿触发时的触发电平，单位与当前幅度单位一致 | 3.27.19.5 | 380 |
| `:TRIGger:RS232:SOURce` | `:TRIGGER:RS232:SOURCE` / `:TRIG:RS232:SOUR` | 设置或查询RS232触发的触发源 | 3.27.20.1 | 381 |
| `:TRIGger:RS232:LEVel` | `:TRIGGER:RS232:LEVEL` / `:TRIG:RS232:LEV` | 设置或查询RS232触发时的触发电平，单位与当前幅度单位一致 | 3.27.20.2 | 382 |
| `:TRIGger:RS232:POLarity` | `:TRIGGER:RS232:POLARITY` / `:TRIG:RS232:POL` | 设置或查询RS232触发的脉冲极性 | 3.27.20.3 | 383 |
| `:TRIGger:RS232:WHEN` | `:TRIGGER:RS232:WHEN` / `:TRIG:RS232:WHEN` | 设置或查询RS232触发的触发条件 | 3.27.20.4 | 383 |
| `:TRIGger:RS232:DATA` | `:TRIGGER:RS232:DATA` / `:TRIG:RS232:DATA` | 设置或查询RS232触发条件为数据时的数据值 | 3.27.20.5 | 384 |
| `:TRIGger:RS232:BAUD` | `:TRIGGER:RS232:BAUD` / `:TRIG:RS232:BAUD` | 设置或查询RS232触发的波特率，默认单位为bps | 3.27.20.6 | 384 |
| `:TRIGger:RS232:WIDTh` | `:TRIGGER:RS232:WIDTH` / `:TRIG:RS232:WIDT` | 设置或查询RS232触发条件为数据时的数据位宽 | 3.27.20.7 | 385 |
| `:TRIGger:RS232:STOP` | `:TRIGGER:RS232:STOP` / `:TRIG:RS232:STOP` | 设置或查询RS232触发的停止位 | 3.27.20.8 | 386 |
| `:TRIGger:RS232:PARity` | `:TRIGGER:RS232:PARITY` / `:TRIG:RS232:PAR` | 设置或查询RS232触发的校验方式 | 3.27.20.9 | 386 |
| `:TRIGger:RS232:BUSer` | `:TRIGGER:RS232:BUSER` / `:TRIG:RS232:BUS` | 设置或查询RS232触发的波特率，默认单位为bps | 3.27.20.10 | 387 |
| `:TRIGger:IIC:SCL` | `:TRIGGER:IIC:SCL` / `:TRIG:IIC:SCL` | 设置或查询I2C触发的时钟线的通道源 | 3.27.21.1 | 388 |
| `:TRIGger:IIC:CLEVel` | `:TRIGGER:IIC:CLEVEL` / `:TRIG:IIC:CLEV` | 设置或查询I2C触发时的时钟线的触发电平，单位与当前幅度单位一致 | 3.27.21.2 | 388 |
| `:TRIGger:IIC:SDA` | `:TRIGGER:IIC:SDA` / `:TRIG:IIC:SDA` | 设置或查询I2C触发的数据线的通道源 | 3.27.21.3 | 389 |
| `:TRIGger:IIC:DLEVel` | `:TRIGGER:IIC:DLEVEL` / `:TRIG:IIC:DLEV` | 设置或查询I2C触发时的数据线的触发电平，单位与当前幅度单位一致 | 3.27.21.4 | 390 |
| `:TRIGger:IIC:WHEN` | `:TRIGGER:IIC:WHEN` / `:TRIG:IIC:WHEN` | 设置或查询I2C触发的触发条件 | 3.27.21.5 | 390 |
| `:TRIGger:IIC:AWIDth` | `:TRIGGER:IIC:AWIDTH` / `:TRIG:IIC:AWID` | 设置或查询I2C触发条件为地址或地址数据时的地址位宽 | 3.27.21.6 | 391 |
| `:TRIGger:IIC:ADDRess` | `:TRIGGER:IIC:ADDRESS` / `:TRIG:IIC:ADDR` | 设置或查询I2C触发条件为地址或地址数据时的地址值 | 3.27.21.7 | 392 |
| `:TRIGger:IIC:DIRection` | `:TRIGGER:IIC:DIRECTION` / `:TRIG:IIC:DIR` | 设置或查询I2C触发条件为地址或地址数据时的数据方向 | 3.27.21.8 | 392 |
| `:TRIGger:IIC:DBYTes` | `:TRIGGER:IIC:DBYTES` / `:TRIG:IIC:DBYT` | 设置或查询I2C触发条件为数据或地址数据时的位组长度 | 3.27.21.9 | 393 |
| `:TRIGger:IIC:DATA` | `:TRIGGER:IIC:DATA` / `:TRIG:IIC:DATA` | 设置或查询I2C触发条件为数据或地址数据时的数据值 | 3.27.21.10 | 393 |
| `:TRIGger:IIC:CURRbit` | `:TRIGGER:IIC:CURRBIT` / `:TRIG:IIC:CURR` | 设置或查询I2C触发数据的第几位 | 3.27.21.11 | 394 |
| `:TRIGger:IIC:CODE` | `:TRIGGER:IIC:CODE` / `:TRIG:IIC:CODE` | 设置或查询I2C触发数据某一位的值 | 3.27.21.12 | 395 |
| `:TRIGger:SPI:CLK` | `:TRIGGER:SPI:CLK` / `:TRIG:SPI:CLK` | 设置或查询SPI触发中时钟线的通道源 | 3.27.22.1 | 396 |
| `:TRIGger:SPI:SCL` | `:TRIGGER:SPI:SCL` / `:TRIG:SPI:SCL` | 设置或查询SPI触发的时钟线的通道源 | 3.27.22.2 | 396 |
| `:TRIGger:SPI:CLEVel` | `:TRIGGER:SPI:CLEVEL` / `:TRIG:SPI:CLEV` | 设置或查询SPI触发时时钟通道的触发电平，单位与当前幅度单位一致 | 3.27.22.3 | 397 |
| `:TRIGger:SPI:SLOPe` | `:TRIGGER:SPI:SLOPE` / `:TRIG:SPI:SLOP` | 设置或查询SPI触发的时钟边沿的类型 | 3.27.22.4 | 397 |
| `:TRIGger:SPI:MISO` | `:TRIGGER:SPI:MISO` / `:TRIG:SPI:MISO` | 设置与查询SPI触发中数据线的通道源 | 3.27.22.5 | 398 |
| `:TRIGger:SPI:SDA` | `:TRIGGER:SPI:SDA` / `:TRIG:SPI:SDA` | 设置或查询SPI触发的数据线的通道源 | 3.27.22.6 | 399 |
| `:TRIGger:SPI:DLEVel` | `:TRIGGER:SPI:DLEVEL` / `:TRIG:SPI:DLEV` | 设置或查询SPI触发时数据通道的触发电平，单位与当前幅度单位一致 | 3.27.22.7 | 399 |
| `:TRIGger:SPI:WHEN` | `:TRIGGER:SPI:WHEN` / `:TRIG:SPI:WHEN` | 设置或查询SPI触发的触发条件 | 3.27.22.8 | 400 |
| `:TRIGger:SPI:CS` | `:TRIGGER:SPI:CS` / `:TRIG:SPI:CS` | 设置或查询SPI触发条件为CS时，片选线的通道源 | 3.27.22.9 | 401 |
| `:TRIGger:SPI:SLEVel` | `:TRIGGER:SPI:SLEVEL` / `:TRIG:SPI:SLEV` | 设置或查询SPI触发时片选通道的触发电平，单位与当前幅度单位一致 | 3.27.22.10 | 401 |
| `:TRIGger:SPI:MODE` | `:TRIGGER:SPI:MODE` / `:TRIG:SPI:MODE` | 设置或查询SPI触发条件为片选时的片选模式 | 3.27.22.11 | 402 |
| `:TRIGger:SPI:TIMeout` | `:TRIGGER:SPI:TIMEOUT` / `:TRIG:SPI:TIM` | 在SPI的触发条件为超时情况下，设置或查询超时时间，默认单位为s | 3.27.22.12 | 403 |
| `:TRIGger:SPI:WIDTh` | `:TRIGGER:SPI:WIDTH` / `:TRIG:SPI:WIDT` | 设置或查询SPI触发下数据通道的数据位宽 | 3.27.22.13 | 403 |
| `:TRIGger:SPI:DATA` | `:TRIGGER:SPI:DATA` / `:TRIG:SPI:DATA` | 设置或查询SPI触发下的数据值 | 3.27.22.14 | 404 |
| `:TRIGger:SPI:CURRbit` | `:TRIGGER:SPI:CURRBIT` / `:TRIG:SPI:CURR` | 设置或查询SPI触发数据的第几位 | 3.27.22.15 | 404 |
| `:TRIGger:SPI:CODE` | `:TRIGGER:SPI:CODE` / `:TRIG:SPI:CODE` | 设置或查询SPI触发数据某一位的值 | 3.27.22.16 | 405 |
| `:TRIGger:CAN:BAUD` | `:TRIGGER:CAN:BAUD` / `:TRIG:CAN:BAUD` | 设置或查询CAN触发的信号速率，单位为bps | 3.27.23.1 | 406 |
| `:TRIGger:CAN:SOURce` | `:TRIGGER:CAN:SOURCE` / `:TRIG:CAN:SOUR` | 设置或查询CAN触发的触发源 | 3.27.23.2 | 406 |
| `:TRIGger:CAN:STYPe` | `:TRIGGER:CAN:STYPE` / `:TRIG:CAN:STYP` | 设置或查询CAN触发的信号类型 | 3.27.23.3 | 407 |
| `:TRIGger:CAN:WHEN` | `:TRIGGER:CAN:WHEN` / `:TRIG:CAN:WHEN` | 设置或查询CAN触发的触发条件 | 3.27.23.4 | 408 |
| `:TRIGger:CAN:SPOint` | `:TRIGGER:CAN:SPOINT` / `:TRIG:CAN:SPO` | 设置或查询CAN触发的采样点位置，以百分比形式表示 | 3.27.23.5 | 409 |
| `:TRIGger:CAN:EXTended` | `:TRIGGER:CAN:EXTENDED` / `:TRIG:CAN:EXT` | 设置或查询CAN触发在触发条件为“远程帧ID”或“数据帧ID”时是否支持扩展ID | 3.27.23.6 | 410 |
| `:TRIGger:CAN:DEFine` | `:TRIGGER:CAN:DEFINE` / `:TRIG:CAN:DEF` | 设置或查询CAN触发下，触发条件为Data和ID时，定义为ID还是Data | 3.27.23.7 | 410 |
| `:TRIGger:CAN:DWIDth` | `:TRIGGER:CAN:DWIDTH` / `:TRIG:CAN:DWID` | 设置或查询CAN触发的触发条件为数据帧数据及数据和ID时的数据位组长度 | 3.27.23.8 | 411 |
| `:TRIGger:CAN:DATA` | `:TRIGGER:CAN:DATA` / `:TRIG:CAN:DATA` | 设置或查询CAN触发时的数据值 | 3.27.23.9 | 411 |
| `:TRIGger:CAN:CURRbit` | `:TRIGGER:CAN:CURRBIT` / `:TRIG:CAN:CURR` | 设置或查询CAN触发数据的第几位 | 3.27.23.10 | 412 |
| `:TRIGger:CAN:CODE` | `:TRIGGER:CAN:CODE` / `:TRIG:CAN:CODE` | 设置或查询CAN触发数据某一位的值 | 3.27.23.11 | 413 |
| `:TRIGger:CAN:LEVel` | `:TRIGGER:CAN:LEVEL` / `:TRIG:CAN:LEV` | 设置或查询CAN触发的触发电平 | 3.27.23.12 | 413 |
| `:TRIGger:LIN:SOURce` | `:TRIGGER:LIN:SOURCE` / `:TRIG:LIN:SOUR` | 设置或查询LIN触发的触发源 | 3.27.24.1 | 414 |
| `:TRIGger:LIN:LEVel` | `:TRIGGER:LIN:LEVEL` / `:TRIG:LIN:LEV` | 设置或查询LIN触发的触发电平 | 3.27.24.2 | 415 |
| `:TRIGger:LIN:STANdard` | `:TRIGGER:LIN:STANDARD` / `:TRIG:LIN:STAN` | 设置或查询LIN触发的协议版本 | 3.27.24.3 | 416 |
| `:TRIGger:LIN:BAUD` | `:TRIGGER:LIN:BAUD` / `:TRIG:LIN:BAUD` | 设置或查询LIN触发的波特率 | 3.27.24.4 | 416 |
| `:TRIGger:LIN:SAMPlepoint` | `:TRIGGER:LIN:SAMPLEPOINT` / `:TRIG:LIN:SAMP` | 设置或查询LIN触发的采样位置 | 3.27.24.5 | 417 |
| `:TRIGger:LIN:WHEN` | `:TRIGGER:LIN:WHEN` / `:TRIG:LIN:WHEN` | 设置或查询LIN触发的触发条件 | 3.27.24.6 | 417 |
| `:TRIGger:LIN:ERRor` | `:TRIGGER:LIN:ERROR` / `:TRIG:LIN:ERR` | 设置或查询触发条件为错误帧触发时，LIN触发的错误类型 | 3.27.24.7 | 418 |
| `:TRIGger:LIN:ID` | `:TRIGGER:LIN:ID` / `:TRIG:LIN:ID` | 设置或查询触发条件为“数据和ID”或“标识符”时，LIN触发的ID值 | 3.27.24.8 | 419 |
| `:TRIGger:LIN:DATA` | `:TRIGGER:LIN:DATA` / `:TRIG:LIN:DATA` | 设置或查询触发条件为数据触发时，LIN触发的触发数据值 | 3.27.24.9 | 419 |
| `:TRIGger:LIN:CURRbit` | `:TRIGGER:LIN:CURRBIT` / `:TRIG:LIN:CURR` | 设置或查询LIN触发数据的第几位 | 3.27.24.10 | 420 |
| `:TRIGger:LIN:CODE` | `:TRIGGER:LIN:CODE` / `:TRIG:LIN:CODE` | 设置或查询LIN触发数据某一位的值 | 3.27.24.11 | 420 |
| `:TRIGger:FLEXray:BAUD` | `:TRIGGER:FLEXRAY:BAUD` / `:TRIG:FLEX:BAUD` | 设置或查询FlexRay触发的信号速率 | 3.27.25.1 | 422 |
| `:TRIGger:FLEXray:POS` | `:TRIGGER:FLEXRAY:POS` / `:TRIG:FLEX:POS` | 设置或查询触发条件为位置触发时，FlexRay触发的位置 | 3.27.25.2 | 422 |
| `:TRIGger:FLEXray:ERRor` | `:TRIGGER:FLEXRAY:ERROR` / `:TRIG:FLEX:ERR` | 设置或查询当触发条件为错误触发时，FlexRay触发的错误类型 | 3.27.25.3 | 423 |
| `:TRIGger:FLEXray:SYMBol` | `:TRIGGER:FLEXRAY:SYMBOL` / `:TRIG:FLEX:SYMB` | 设置或查询当触发条件为符号触发时，FlexRay触发的触发符号 | 3.27.25.4 | 423 |
| `:TRIGger:FLEXray:FRAMe` | `:TRIGGER:FLEXRAY:FRAME` / `:TRIG:FLEX:FRAM` | 设置或查询触发条件为帧触发时，FlexRay触发的触发帧类型 | 3.27.25.5 | 424 |
| `:TRIGger:FLEXray:DEFine` | `:TRIGGER:FLEXRAY:DEFINE` / `:TRIG:FLEX:DEF` | 设置或查询当FlexRay触发选择帧触发时，通过帧ID还是Cycle计数来定义触发条件 | 3.27.25.6 | 425 |
| `:TRIGger:FLEXray:IDCmp` | `:TRIGGER:FLEXRAY:IDCMP` / `:TRIG:FLEX:IDC` | 设置或查询FlexRay触发选择帧和符号触发时的ID比较条件 | 3.27.25.7 | 425 |
| `:TRIGger:FLEXray:CYCComp` | `:TRIGGER:FLEXRAY:CYCCOMP` / `:TRIG:FLEX:CYCC` | 设置或查询FlexRay在触发条件为帧触发时的CYC计数比较条件 | 3.27.25.8 | 426 |
| `:TRIGger:FLEXray:MAXCy` | `:TRIGGER:FLEXRAY:MAXCY` / `:TRIG:FLEX:MAXC` | 设置或查询FlexRay触发CYC计数上限值 | 3.27.25.9 | 427 |
| `:TRIGger:FLEXray:MINCy` | `:TRIGGER:FLEXRAY:MINCY` / `:TRIG:FLEX:MINC` | 设置或查询FlexRay触发CYC的计数下限值 | 3.27.25.10 | 427 |
| `:TRIGger:FLEXray:MAXid` | `:TRIGGER:FLEXRAY:MAXID` / `:TRIG:FLEX:MAX` | 设置或查询FlexRay触发ID上限值 | 3.27.25.11 | 428 |
| `:TRIGger:FLEXray:MINid` | `:TRIGGER:FLEXRAY:MINID` / `:TRIG:FLEX:MIN` | 设置或查询FlexRay触发，在触发条件为帧和符号触发时的ID下限值 | 3.27.25.12 | 428 |
| `:TRIGger:FLEXray:CH` | `:TRIGGER:FLEXRAY:CH` / `:TRIG:FLEX:CH` | 设置或查询FlexRay触发信道 | 3.27.25.13 | 429 |
| `:TRIGger:FLEXray:SOURce` | `:TRIGGER:FLEXRAY:SOURCE` / `:TRIG:FLEX:SOUR` | 设置或查询FlexRay触发的触发源 | 3.27.25.14 | 429 |
| `:TRIGger:FLEXray:WHEN` | `:TRIGGER:FLEXRAY:WHEN` / `:TRIG:FLEX:WHEN` | 设置或查询FLEXray触发的触发条件 | 3.27.25.15 | 430 |
| `:TRIGger:FLEXray:LEVel` | `:TRIGGER:FLEXRAY:LEVEL` / `:TRIG:FLEX:LEV` | 设置或查询FlexRay触发时的触发电平 | 3.27.25.16 | 431 |
| `:TRIGger:IIS:ALIGnment` | `:TRIGGER:IIS:ALIGNMENT` / `:TRIG:IIS:ALIG` | 设置或查询I2S触发的对齐方式 | 3.27.26.1 | 432 |
| `:TRIGger:IIS:CLEVel` | `:TRIGGER:IIS:CLEVEL` / `:TRIG:IIS:CLEV` | 设置或查询I2S触发的时钟线通道源的触发电平，单位为V | 3.27.26.2 | 433 |
| `:TRIGger:IIS:SLEVel` | `:TRIGGER:IIS:SLEVEL` / `:TRIG:IIS:SLEV` | 设置或查询I2S触发中帧时钟线通道源的触发电平，单位为V | 3.27.26.3 | 433 |
| `:TRIGger:IIS:DLEVel` | `:TRIGGER:IIS:DLEVEL` / `:TRIG:IIS:DLEV` | 设置或查询I2S触发中数据线通道源的触发电平，单位为V | 3.27.26.4 | 434 |
| `:TRIGger:IIS:UWIDth` | `:TRIGGER:IIS:UWIDTH` / `:TRIG:IIS:UWID` | 设置或查询I2S触发有效位宽 | 3.27.26.5 | 435 |
| `:TRIGger:IIS:WIDTh` | `:TRIGGER:IIS:WIDTH` / `:TRIG:IIS:WIDT` | 设置或查询I2S触发总位宽 | 3.27.26.6 | 435 |
| `:TRIGger:IIS:DMIN` | `:TRIGGER:IIS:DMIN` / `:TRIG:IIS:DMIN` | 设置或查询在I2S触发数据的下限值中指定第几位 | 3.27.26.7 | 436 |
| `:TRIGger:IIS:DMAX` | `:TRIGGER:IIS:DMAX` / `:TRIG:IIS:DMAX` | 设置或查询在I2S触发数据的上限值中指定第几位 | 3.27.26.8 | 436 |
| `:TRIGger:IIS:CODE` | `:TRIGGER:IIS:CODE` / `:TRIG:IIS:CODE` | 设置或查询I2S触发数据某一位的值 | 3.27.26.9 | 437 |
| `:TRIGger:IIS:CLOCk:SLOPe` | `:TRIGGER:IIS:CLOCK:SLOPE` / `:TRIG:IIS:CLOC:SLOP` | 设置或查询I2S触发的时钟边沿类型 | 3.27.26.10 | 438 |
| `:TRIGger:IIS:SOURce:CLOCk` | `:TRIGGER:IIS:SOURCE:CLOCK` / `:TRIG:IIS:SOUR:CLOC` | 设置或查询I2S触发的时钟源 | 3.27.26.11 | 438 |
| `:TRIGger:IIS:SOURce:DATA` | `:TRIGGER:IIS:SOURCE:DATA` / `:TRIG:IIS:SOUR:DATA` | 设置或查询I2S触发的数据源 | 3.27.26.12 | 439 |
| `:TRIGger:IIS:SOURce:WSELect` | `:TRIGGER:IIS:SOURCE:WSELECT` / `:TRIG:IIS:SOUR:WSEL` | 设置或查询I2S触发的声道信源 | 3.27.26.13 | 439 |
| `:TRIGger:IIS:WHEN` | `:TRIGGER:IIS:WHEN` / `:TRIG:IIS:WHEN` | 设置或查询I2S触发条件 | 3.27.26.14 | 440 |
| `:TRIGger:IIS:AUDio` | `:TRIGGER:IIS:AUDIO` / `:TRIG:IIS:AUD` | 设置或查询I2S触发的音频状态 | 3.27.26.15 | 441 |
| `:TRIGger:IIS:DATA` | `:TRIGGER:IIS:DATA` / `:TRIG:IIS:DATA` | 设置或查询IIS触发功能在触发条件为“等于”和“不等于”时的数据值 | 3.27.26.16 | 441 |
| `:TRIGger:M1553:SOURce` | `:TRIGGER:M1553:SOURCE` / `:TRIG:M1553:SOUR` | 设置或查询M1553触发的触发源 | 3.27.27.1 | 443 |
| `:TRIGger:M1553:WHEN` | `:TRIGGER:M1553:WHEN` / `:TRIG:M1553:WHEN` | 设置或查询M1553触发的触发条件 | 3.27.27.2 | 444 |
| `:TRIGger:M1553:POLarity` | `:TRIGGER:M1553:POLARITY` / `:TRIG:M1553:POL` | 选择或查询M1553触发时的极性 | 3.27.27.3 | 444 |
| `:TRIGger:M1553:WINDow` | `:TRIGGER:M1553:WINDOW` / `:TRIG:M1553:WIND` | 设置或查询M1553触发触发电平的调节类型 | 3.27.27.4 | 445 |
| `:TRIGger:M1553:SYNC` | `:TRIGGER:M1553:SYNC` / `:TRIG:M1553:SYNC` | 设置或查询M1553触发条件为同步触发时的同步类型 | 3.27.27.5 | 446 |
| `:TRIGger:M1553:ERRor` | `:TRIGGER:M1553:ERROR` / `:TRIG:M1553:ERR` | 设置或查询M1553触发错误类型 | 3.27.27.6 | 446 |
| `:TRIGger:M1553:DATComp` | `:TRIGGER:M1553:DATCOMP` / `:TRIG:M1553:DATC` | 设置或查询M1553触发在触发条件为数据字时的比较条件 | 3.27.27.7 | 447 |
| `:TRIGger:M1553:DATValue` | `:TRIGGER:M1553:DATVALUE` / `:TRIG:M1553:DATV` | 设置或查询M1553触发时的数据值 | 3.27.27.8 | 447 |
| `:TRIGger:M1553:DMIN` | `:TRIGGER:M1553:DMIN` / `:TRIG:M1553:DMIN` | 设置或查询M1553触发时选中触发数据下限的第几位 | 3.27.27.9 | 448 |
| `:TRIGger:M1553:DMAX` | `:TRIGGER:M1553:DMAX` / `:TRIG:M1553:DMAX` | 设置或查询M1553触发时选中数据上限值的第几位 | 3.27.27.10 | 449 |
| `:TRIGger:M1553:DRTA` | `:TRIGGER:M1553:DRTA` / `:TRIG:M1553:DRTA` | 设置或查询M1553触发时的数据值 | 3.27.27.11 | 449 |
| `:TRIGger:M1553:DBIT` | `:TRIGGER:M1553:DBIT` / `:TRIG:M1553:DBIT` | 设置或查询M1553触发，在触发条件为“RAT+11Bit”时的位时间为第几位 | 3.27.27.12 | 450 |
| `:TRIGger:M1553:CODE` | `:TRIGGER:M1553:CODE` / `:TRIG:M1553:CODE` | 设置或查询M1553触发数据某一位的值 | 3.27.27.13 | 450 |
| `:TRIGger:M1553:ALEVel` | `:TRIGGER:M1553:ALEVEL` / `:TRIG:M1553:ALEV` | 设置或查询M1553触发时的触发电平上限，单位与当前幅度单位一致 | 3.27.27.14 | 451 |
| `:TRIGger:M1553:BLEVel` | `:TRIGGER:M1553:BLEVEL` / `:TRIG:M1553:BLEV` | 设置或查询延迟触发时的触发电平下限，单位与当前幅度单位一致 | 3.27.27.15 | 452 |

<details><summary>3.27 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.27.1 | `:TRIGger:MODE <mode>` ; `:TRIGger:MODE?` |
| 3.27.2 | `:TRIGger:COUPling <couple>` ; `:TRIGger:COUPling?` |
| 3.27.3 | `:TRIGger:STATus?` |
| 3.27.4 | `:TRIGger:SWEep <sweep>` ; `:TRIGger:SWEep?` |
| 3.27.5 | `:TRIGger:HOLDoff <value>` ; `:TRIGger:HOLDoff?` |
| 3.27.6 | `:TRIGger:NREJect <bool>` ; `:TRIGger:NREJect?` |
| 3.27.7 | `:TRIGger:POSition?` |
| 3.27.8.1 | `:TRIGger:EDGE:SOURce <source>` ; `:TRIGger:EDGE:SOURce?` |
| 3.27.8.2 | `:TRIGger:EDGE:SLOPe <slope>` ; `:TRIGger:EDGE:SLOPe?` |
| 3.27.8.3 | `:TRIGger:EDGE:LEVel <level>` ; `:TRIGger:EDGE:LEVel?` |
| 3.27.9.1 | `:TRIGger:PULSe:SOURce <source>` ; `:TRIGger:PULSe:SOURce?` |
| 3.27.9.2 | `:TRIGger:PULSe:POLarity <polarity>` ; `:TRIGger:PULSe:POLarity?` |
| 3.27.9.3 | `:TRIGger:PULSe:WHEN <when>` ; `:TRIGger:PULSe:WHEN?` |
| 3.27.9.4 | `:TRIGger:PULSe:UWIDth <width>` ; `:TRIGger:PULSe:UWIDth?` |
| 3.27.9.5 | `:TRIGger:PULSe:LWIDth <width>` ; `:TRIGger:PULSe:LWIDth?` |
| 3.27.9.6 | `:TRIGger:PULSe:LEVel <level>` ; `:TRIGger:PULSe:LEVel?` |
| 3.27.10.1 | `:TRIGger:SLOPe:SOURce <channel>` ; `:TRIGger:SLOPe:SOURce?` |
| 3.27.10.2 | `:TRIGger:SLOPe:POLarity <polarity>` ; `:TRIGger:SLOPe:POLarity?` |
| 3.27.10.3 | `:TRIGger:SLOPe:WHEN <when>` ; `:TRIGger:SLOPe:WHEN?` |
| 3.27.10.4 | `:TRIGger:SLOPe:TUPPer <time>` ; `:TRIGger:SLOPe:TUPPer?` |
| 3.27.10.5 | `:TRIGger:SLOPe:TLOWer <time>` ; `:TRIGger:SLOPe:TLOWer?` |
| 3.27.10.6 | `:TRIGger:SLOPe:WINDow <window>` ; `:TRIGger:SLOPe:WINDow?` |
| 3.27.10.7 | `:TRIGger:SLOPe:ALEVel <level>` ; `:TRIGger:SLOPe:ALEVel?` |
| 3.27.10.8 | `:TRIGger:SLOPe:BLEVel <level>` ; `:TRIGger:SLOPe:BLEVel?` |
| 3.27.11.1 | `:TRIGger:VIDeo:SOURce <source>` ; `:TRIGger:VIDeo:SOURce?` |
| 3.27.11.2 | `:TRIGger:VIDeo:POLarity <polarity>` ; `:TRIGger:VIDeo:POLarity?` |
| 3.27.11.3 | `:TRIGger:VIDeo:MODE <mode>` ; `:TRIGger:VIDeo:MODE?` |
| 3.27.11.4 | `:TRIGger:VIDeo:LINE <line>` ; `:TRIGger:VIDeo:LINE?` |
| 3.27.11.5 | `:TRIGger:VIDeo:STANdard <standard>` ; `:TRIGger:VIDeo:STANdard?` |
| 3.27.11.6 | `:TRIGger:VIDeo:LEVel <level>` ; `:TRIGger:VIDeo:LEVel?` |
| 3.27.12.1 | `:TRIGger:PATTern:PATTern <pch1>[,<pch2>[,<pch3>[,<pch4>]]]` ; `:TRIGger:PATTern:PATTern?` |
| 3.27.12.2 | `:TRIGger:PATTern:SOURce <source>` ; `:TRIGger:PATTern:SOURce?` |
| 3.27.12.3 | `:TRIGger:PATTern:LEVel <source>,<level>` ; `:TRIGger:PATTern:LEVel? <source>` |
| 3.27.13.1 | `:TRIGger:DURation:SOURce <source>` ; `:TRIGger:DURation:SOURce?` |
| 3.27.13.2 | `:TRIGger:DURation:TYPE <pch1>[,<pch2>[,<pch3>[,<pch4>]]]` ; `:TRIGger:DURation:TYPE?` |
| 3.27.13.3 | `:TRIGger:DURation:WHEN <when>` ; `:TRIGger:DURation:WHEN?` |
| 3.27.13.4 | `:TRIGger:DURation:TUPPer <time>` ; `:TRIGger:DURation:TUPPer?` |
| 3.27.13.5 | `:TRIGger:DURation:TLOWer <time>` ; `:TRIGger:DURation:TLOWer?` |
| 3.27.13.6 | `:TRIGger:DURation:LEVel <source>,<level>` ; `:TRIGger:DURation:LEVel?<source>` |
| 3.27.14.1 | `:TRIGger:TIMeout:SOURce <source>` ; `:TRIGger:TIMeout:SOURce?` |
| 3.27.14.2 | `:TRIGger:TIMeout:SLOPe <slope>` ; `:TRIGger:TIMeout:SLOPe?` |
| 3.27.14.3 | `:TRIGger:TIMeout:TIME <time>` ; `:TRIGger:TIMeout:TIME?` |
| 3.27.14.4 | `:TRIGger:TIMeout:LEVel <level>` ; `:TRIGger:TIMeout:LEVel?` |
| 3.27.15.1 | `:TRIGger:RUNT:SOURce <source>` ; `:TRIGger:RUNT:SOURce?` |
| 3.27.15.2 | `:TRIGger:RUNT:POLarity <polarity>` ; `:TRIGger:RUNT:POLarity?` |
| 3.27.15.3 | `:TRIGger:RUNT:WHEN <when>` ; `:TRIGger:RUNT:WHEN?` |
| 3.27.15.4 | `:TRIGger:RUNT:WUPPer <width>` ; `:TRIGger:RUNT:WUPPer?` |
| 3.27.15.5 | `:TRIGger:RUNT:WLOWer <width>` ; `:TRIGger:RUNT:WLOWer?` |
| 3.27.15.6 | `:TRIGger:RUNT:ALEVel <level>` ; `:TRIGger:RUNT:ALEVel?` |
| 3.27.15.7 | `:TRIGger:RUNT:BLEVel <level>` ; `:TRIGger:RUNT:BLEVel?` |
| 3.27.16.1 | `:TRIGger:WINDows:SOURce <source>` ; `:TRIGger:WINDows:SOURce?` |
| 3.27.16.2 | `:TRIGger:WINDows:SLOPe <type>` ; `:TRIGger:WINDows:SLOPe?` |
| 3.27.16.3 | `:TRIGger:WINDows:POSition <pos>` ; `:TRIGger:WINDows:POSition?` |
| 3.27.16.4 | `:TRIGger:WINDows:TIME <time>` ; `:TRIGger:WINDows:TIME?` |
| 3.27.16.5 | `:TRIGger:WINDows:ALEVel <level>` ; `:TRIGger:WINDows:ALEVel?` |
| 3.27.16.6 | `:TRIGger:WINDows:BLEVel <level>` ; `:TRIGger:WINDows:BLEVel?` |
| 3.27.17.1 | `:TRIGger:DELay:SA <source>` ; `:TRIGger:DELay:SA?` |
| 3.27.17.2 | `:TRIGger:DELay:ASLop <slope>` ; `:TRIGger:DELay:ASLop?` |
| 3.27.17.3 | `:TRIGger:DELay:SB <source>` ; `:TRIGger:DELay:SB?` |
| 3.27.17.4 | `:TRIGger:DELay:BSLop <slope>` ; `:TRIGger:DELay:BSLop?` |
| 3.27.17.5 | `:TRIGger:DELay:TYPE <type>` ; `:TRIGger:DELay:TYPE?` |
| 3.27.17.6 | `:TRIGger:DELay:TUPPer <time>` ; `:TRIGger:DELay:TUPPer?` |
| 3.27.17.7 | `:TRIGger:DELay:TLOWer <time>` ; `:TRIGger:DELay:TLOWer?` |
| 3.27.17.8 | `:TRIGger:DELay:ALEVel <level>` ; `:TRIGger:DELay:ALEVel?` |
| 3.27.17.9 | `:TRIGger:DELay:BLEVel <level>` ; `:TRIGger:DELay:BLEVel?` |
| 3.27.18.1 | `:TRIGger:SHOLd:DSRC <source>` ; `:TRIGger:SHOLd:DSRC?` |
| 3.27.18.2 | `:TRIGger:SHOLd:CSRC <source>` ; `:TRIGger:SHOLd:CSRC?` |
| 3.27.18.3 | `:TRIGger:SHOLd:SLOPe <slope>` ; `:TRIGger:SHOLd:SLOPe?` |
| 3.27.18.4 | `:TRIGger:SHOLd:PATTern <pattern>` ; `:TRIGger:SHOLd:PATTern?` |
| 3.27.18.5 | `:TRIGger:SHOLd:TYPE <type>` ; `:TRIGger:SHOLd:TYPE?` |
| 3.27.18.6 | `:TRIGger:SHOLd:STIMe <time>` ; `:TRIGger:SHOLd:STIMe?` |
| 3.27.18.7 | `:TRIGger:SHOLd:HTIMe <time>` ; `:TRIGger:SHOLd:HTIMe?` |
| 3.27.18.8 | `:TRIGger:SHOLd:DLEVel <level>` ; `:TRIGger:SHOLd:DLEVel?` |
| 3.27.18.9 | `:TRIGger:SHOLd:CLEVel<level>` ; `:TRIGger:SHOLd:CLEVel?` |
| 3.27.19.1 | `:TRIGger:NEDGe:SOURce <source>` ; `:TRIGger:NEDGe:SOURce?` |
| 3.27.19.2 | `:TRIGger:NEDGe:SLOPe <slope>` ; `:TRIGger:NEDGe:SLOPe?` |
| 3.27.19.3 | `:TRIGger:NEDGe:IDLE <time>` ; `:TRIGger:NEDGe:IDLE?` |
| 3.27.19.4 | `:TRIGger:NEDGe:EDGE <edge>` ; `:TRIGger:NEDGe:EDGE?` |
| 3.27.19.5 | `:TRIGger:NEDGe:LEVel <level>` ; `:TRIGger:NEDGe:LEVel?` |
| 3.27.20.1 | `:TRIGger:RS232:SOURce <source>` ; `:TRIGger:RS232:SOURce?` |
| 3.27.20.2 | `:TRIGger:RS232:LEVel <level>` ; `:TRIGger:RS232:LEVel?` |
| 3.27.20.3 | `:TRIGger:RS232:POLarity <polarity>` ; `:TRIGger:RS232:POLarity?` |
| 3.27.20.4 | `:TRIGger:RS232:WHEN <when>` ; `:TRIGger:RS232:WHEN?` |
| 3.27.20.5 | `:TRIGger:RS232:DATA <data>` ; `:TRIGger:RS232:DATA?` |
| 3.27.20.6 | `:TRIGger:RS232:BAUD <baud>` ; `:TRIGger:RS232:BAUD?` |
| 3.27.20.7 | `:TRIGger:RS232:WIDTh <width>` ; `:TRIGger:RS232:WIDTh?` |
| 3.27.20.8 | `:TRIGger:RS232:STOP <bit>` ; `:TRIGger:RS232:STOP?` |
| 3.27.20.9 | `:TRIGger:RS232:PARity <parity>` ; `:TRIGger:RS232:PARity?` |
| 3.27.20.10 | `:TRIGger:RS232:BUSer <baud>` ; `:TRIGger:RS232:BUSer?` |
| 3.27.21.1 | `:TRIGger:IIC:SCL <source>` ; `:TRIGger:IIC:SCL?` |
| 3.27.21.2 | `:TRIGger:IIC:CLEVel <level>` ; `:TRIGger:IIC:CLEVel?` |
| 3.27.21.3 | `:TRIGger:IIC:SDA <source>` ; `:TRIGger:IIC:SDA?` |
| 3.27.21.4 | `:TRIGger:IIC:DLEVel <level>` ; `:TRIGger:IIC:DLEVel?` |
| 3.27.21.5 | `:TRIGger:IIC:WHEN <when>` ; `:TRIGger:IIC:WHEN?` |
| 3.27.21.6 | `:TRIGger:IIC:AWIDth <bits>` ; `:TRIGger:IIC:AWIDth?` |
| 3.27.21.7 | `:TRIGger:IIC:ADDRess <address>` ; `:TRIGger:IIC:ADDRess?` |
| 3.27.21.8 | `:TRIGger:IIC:DIRection <direction>` ; `:TRIGger:IIC:DIRection?` |
| 3.27.21.9 | `:TRIGger:IIC:DBYTes <bytes>` ; `:TRIGger:IIC:DBYTes?` |
| 3.27.21.10 | `:TRIGger:IIC:DATA <data>` ; `:TRIGger:IIC:DATA?` |
| 3.27.21.11 | `:TRIGger:IIC:CURRbit <currbit>` ; `:TRIGger:IIC:CURRbit?` |
| 3.27.21.12 | `:TRIGger:IIC:CODE <code>` ; `:TRIGger:IIC:CODE?` |
| 3.27.22.1 | `:TRIGger:SPI:CLK <source>` ; `:TRIGger:SPI:CLK?` |
| 3.27.22.2 | `:TRIGger:SPI:SCL <source>` ; `:TRIGger:SPI:SCL?` |
| 3.27.22.3 | `:TRIGger:SPI:CLEVel <level>` ; `:TRIGger:SPI:CLEVel?` |
| 3.27.22.4 | `:TRIGger:SPI:SLOPe <slope>` ; `:TRIGger:SPI:SLOPe?` |
| 3.27.22.5 | `:TRIGger:SPI:MISO <source>` ; `:TRIGger:SPI:MISO?` |
| 3.27.22.6 | `:TRIGger:SPI:SDA <source>` ; `:TRIGger:SPI:SDA?` |
| 3.27.22.7 | `:TRIGger:SPI:DLEVel <level>` ; `:TRIGger:SPI:DLEVel?` |
| 3.27.22.8 | `:TRIGger:SPI:WHEN <when>` ; `:TRIGger:SPI:WHEN?` |
| 3.27.22.9 | `:TRIGger:SPI:CS <source>` ; `:TRIGger:SPI:CS?` |
| 3.27.22.10 | `:TRIGger:SPI:SLEVel <level>` ; `:TRIGger:SPI:SLEVel?` |
| 3.27.22.11 | `:TRIGger:SPI:MODE <mode>` ; `:TRIGger:SPI:MODE?` |
| 3.27.22.12 | `:TRIGger:SPI:TIMeout <time>` ; `:TRIGger:SPI:TIMeout?` |
| 3.27.22.13 | `:TRIGger:SPI:WIDTh <width>` ; `:TRIGger:SPI:WIDTh?` |
| 3.27.22.14 | `:TRIGger:SPI:DATA <data>` ; `:TRIGger:SPI:DATA?` |
| 3.27.22.15 | `:TRIGger:SPI:CURRbit <currbit>` ; `:TRIGger:SPI:CURRbit?` |
| 3.27.22.16 | `:TRIGger:SPI:CODE <code>` ; `:TRIGger:SPI:CODE?` |
| 3.27.23.1 | `:TRIGger:CAN:BAUD <baud>` ; `:TRIGger:CAN:BAUD?` |
| 3.27.23.2 | `:TRIGger:CAN:SOURce <source>` ; `:TRIGger:CAN:SOURce?` |
| 3.27.23.3 | `:TRIGger:CAN:STYPe <stype>` ; `:TRIGger:CAN:STYPe?` |
| 3.27.23.4 | `:TRIGger:CAN:WHEN <cond>` ; `:TRIGger:CAN:WHEN?` |
| 3.27.23.5 | `:TRIGger:CAN:SPOint <spoint>` ; `:TRIGger:CAN:SPOint?` |
| 3.27.23.6 | `:TRIGger:CAN:EXTended <bool>` ; `:TRIGger:CAN:EXTended?` |
| 3.27.23.7 | `:TRIGger:CAN:DEFine <type>` ; `:TRIGger:CAN:DEFine?` |
| 3.27.23.8 | `:TRIGger:CAN:DWIDth <data>` ; `:TRIGger:CAN:DWIDth?` |
| 3.27.23.9 | `:TRIGger:CAN:DATA <data>` ; `:TRIGger:CAN:DATA?` |
| 3.27.23.10 | `:TRIGger:CAN:CURRbit <currbit>` ; `:TRIGger:CAN:CURRbit?` |
| 3.27.23.11 | `:TRIGger:CAN:CODE <code>` ; `:TRIGger:CAN:CODE?` |
| 3.27.23.12 | `:TRIGger:CAN:LEVel <level>` ; `:TRIGger:CAN:LEVel?` |
| 3.27.24.1 | `:TRIGger:LIN:SOURce <source>` ; `:TRIGger:LIN:SOURce?` |
| 3.27.24.2 | `:TRIGger:LIN:LEVel <level>` ; `:TRIGger:LIN:LEVel?` |
| 3.27.24.3 | `:TRIGger:LIN:STANdard <std>` ; `:TRIGger:LIN:STANdard?` |
| 3.27.24.4 | `:TRIGger:LIN:BAUD <baud>` ; `:TRIGger:LIN:BAUD?` |
| 3.27.24.5 | `:TRIGger:LIN:SAMPlepoint <value>` ; `:TRIGger:LIN:SAMPlepoint?` |
| 3.27.24.6 | `:TRIGger:LIN:WHEN <when>` ; `:TRIGger:LIN:WHEN?` |
| 3.27.24.7 | `:TRIGger:LIN:ERRor <value>` ; `:TRIGger:LIN:ERRor?` |
| 3.27.24.8 | `:TRIGger:LIN:ID <id>` ; `:TRIGger:LIN:ID?` |
| 3.27.24.9 | `:TRIGger:LIN:DATA <data>` ; `:TRIGger:LIN:DATA?` |
| 3.27.24.10 | `:TRIGger:LIN:CURRbit <currbit>` ; `:TRIGger:LIN:CURRbit?` |
| 3.27.24.11 | `:TRIGger:LIN:CODE <code>` ; `:TRIGger:LIN:CODE?` |
| 3.27.25.1 | `:TRIGger:FLEXray:BAUD <baud>` ; `:TRIGger:FLEXray:BAUD?` |
| 3.27.25.2 | `:TRIGger:FLEXray:POS <pos>` ; `:TRIGger:FLEXray:POS?` |
| 3.27.25.3 | `:TRIGger:FLEXray:ERRor <err>` ; `:TRIGger:FLEXray:ERRor?` |
| 3.27.25.4 | `:TRIGger:FLEXray:SYMBol <symbol>` ; `:TRIGger:FLEXray:SYMBol?` |
| 3.27.25.5 | `:TRIGger:FLEXray:FRAMe? <frame>` ; `:TRIGger:FLEXray:FRAMe?` |
| 3.27.25.6 | `:TRIGger:FLEXray:DEFine <define>` ; `:TRIGger:FLEXray:DEFine?` |
| 3.27.25.7 | `:TRIGger:FLEXray:IDCmp <idcomp>` ; `:TRIGger:FLEXray:IDCmp?` |
| 3.27.25.8 | `:TRIGger:FLEXray:CYCComp <cycmax>` ; `:TRIGger:FLEXray:CYCComp?` |
| 3.27.25.9 | `:TRIGger:FLEXray:MAXCy <cycmax>` ; `:TRIGger:FLEXray:MAXCy?` |
| 3.27.25.10 | `:TRIGger:FLEXray:MINCy <cycmin>` ; `:TRIGger:FLEXray:MINCy?` |
| 3.27.25.11 | `:TRIGger:FLEXray:MAXid <idmax>` ; `:TRIGger:FLEXray:MAXid?` |
| 3.27.25.12 | `:TRIGger:FLEXray:MINid <idmin>` ; `:TRIGger:FLEXray:MINid?` |
| 3.27.25.13 | `:TRIGger:FLEXray:CH <ch>` ; `:TRIGger:FLEXray:CH?` |
| 3.27.25.14 | `:TRIGger:FLEXray:SOURce <source>` ; `:TRIGger:FLEXray:SOURce?` |
| 3.27.25.15 | `:TRIGger:FLEXray:WHEN <cond>` ; `:TRIGger:FLEXray:WHEN?` |
| 3.27.25.16 | `:TRIGger:FLEXray:LEVel <level>` ; `:TRIGger:FLEXray:LEVel?` |
| 3.27.26.1 | `:TRIGger:IIS:ALIGnment <setting>` ; `:TRIGger:IIS:ALIGnment?` |
| 3.27.26.2 | `:TRIGger:IIS:CLEVel <level>` ; `:TRIGger:IIS:CLEVel?` |
| 3.27.26.3 | `:TRIGger:IIS:SLEVel <level>` ; `:TRIGger:IIS:SLEVel?` |
| 3.27.26.4 | `:TRIGger:IIS:DLEVel <level>` ; `:TRIGger:IIS:DLEVel?` |
| 3.27.26.5 | `:TRIGger:IIS:UWIDth <uwidth>` ; `:TRIGger:IIS:UWIDth?` |
| 3.27.26.6 | `:TRIGger:IIS:WIDTh <uwidth>` ; `:TRIGger:IIS:WIDTh?` |
| 3.27.26.7 | `:TRIGger:IIS:DMIN <datamin>` ; `:TRIGger:IIS:DMIN?` |
| 3.27.26.8 | `:TRIGger:IIS:DMAX <datamax>` ; `:TRIGger:IIS:DMAX?` |
| 3.27.26.9 | `:TRIGger:IIS:CODE <code>` ; `:TRIGger:IIS:CODE?` |
| 3.27.26.10 | `:TRIGger:IIS:CLOCk:SLOPe <slope>` ; `:TRIGger:IIS:CLOCk:SLOPe?` |
| 3.27.26.11 | `:TRIGger:IIS:SOURce:CLOCk <source>` ; `:TRIGger:IIS:SOURce:CLOCk?` |
| 3.27.26.12 | `:TRIGger:IIS:SOURce:DATA <source>` ; `:TRIGger:IIS:SOURce:DATA?` |
| 3.27.26.13 | `:TRIGger:IIS:SOURce:WSELect <source>` ; `:TRIGger:IIS:SOURce:WSELect?` |
| 3.27.26.14 | `:TRIGger:IIS:WHEN <condition>` ; `:TRIGger:IIS:WHEN?` |
| 3.27.26.15 | `:TRIGger:IIS:AUDio <audio>` ; `:TRIGger:IIS:AUDio?` |
| 3.27.26.16 | `:TRIGger:IIS:DATA <data>` ; `:TRIGger:IIS:DATA?` |
| 3.27.27.1 | `:TRIGger:M1553:SOURce <source>` ; `:TRIGger:M1553:SOURce?` |
| 3.27.27.2 | `:TRIGger:M1553:WHEN <when>` ; `:TRIGger:M1553:WHEN?` |
| 3.27.27.3 | `:TRIGger:M1553:POLarity <polarity>` ; `:TRIGger:M1553:POLarity?` |
| 3.27.27.4 | `:TRIGger:M1553:WINDow <window>` ; `:TRIGger:M1553:WINDow?` |
| 3.27.27.5 | `:TRIGger:M1553:SYNC <sync>` ; `:TRIGger:M1553:SYNC?` |
| 3.27.27.6 | `:TRIGger:M1553:ERRor <err>` ; `:TRIGger:M1553:ERRor?` |
| 3.27.27.7 | `:TRIGger:M1553:DATComp <datacomp>` ; `:TRIGger:M1553:DATComp?` |
| 3.27.27.8 | `:TRIGger:M1553:DATValue <data>` ; `:TRIGger:M1553:DATValue?` |
| 3.27.27.9 | `:TRIGger:M1553:DMIN <datamin>` ; `:TRIGger:M1553:DMIN?` |
| 3.27.27.10 | `:TRIGger:M1553:DMAX <datamax>` ; `:TRIGger:M1553:DMAX?` |
| 3.27.27.11 | `:TRIGger:M1553:DRTA <data>` ; `:TRIGger:M1553:DRTA?` |
| 3.27.27.12 | `:TRIGger:M1553:DBIT <databit>` ; `:TRIGger:M1553:DBIT?` |
| 3.27.27.13 | `:TRIGger:M1553:CODE <code>` ; `:TRIGger:M1553:CODE?` |
| 3.27.27.14 | `:TRIGger:M1553:ALEVel <level>` ; `:TRIGger:M1553:ALEVel?` |
| 3.27.27.15 | `:TRIGger:M1553:BLEVel <level>` ; `:TRIGger:M1553:BLEVel?` |

</details>

## 3.28 波形读取命令子系统

| 命令（手册原文） | 长格式 / 短格式 | 说明（手册功能描述） | 节 | 页 |
|---|---|---|---|---|
| `:WAVeform:SOURce` | `:WAVEFORM:SOURCE` / `:WAV:SOUR` | 设置或查询波形数据读取的通道源 | 3.28.1 | 455 |
| `:WAVeform:MODE` | `:WAVEFORM:MODE` / `:WAV:MODE` | 设置或查询:WAVeform:DATA?命令读取数据的模式 | 3.28.2 | 455 |
| `:WAVeform:FORMat` | `:WAVEFORM:FORMAT` / `:WAV:FORM` | 设置或查询波形数据的返回格式 | 3.28.3 | 456 |
| `:WAVeform:POINts` | `:WAVEFORM:POINTS` / `:WAV:POIN` | 设置或查询当前模式下需要读取的波形点数 | 3.28.4 | 456 |
| `:WAVeform:DATA?` | `:WAVEFORM:DATA?` / `:WAV:DATA?` | 读取波形数据 | 3.28.5 | 457 |
| `:WAVeform:XINCrement?` | `:WAVEFORM:XINCREMENT?` / `:WAV:XINC?` | 查询当前选中通道源X方向上相邻两点之间的时间间隔 | 3.28.6 | 458 |
| `:WAVeform:XORigin?` | `:WAVEFORM:XORIGIN?` / `:WAV:XOR?` | 查询当前选中通道源X方向上波形数据的起始时间 | 3.28.7 | 458 |
| `:WAVeform:XREFerence?` | `:WAVEFORM:XREFERENCE?` / `:WAV:XREF?` | 查询当前选中通道源X方向上波形点的时间参考基准 | 3.28.8 | 459 |
| `:WAVeform:YINCrement?` | `:WAVEFORM:YINCREMENT?` / `:WAV:YINC?` | 查询当前选中通道源Y方向上的单位电压值 | 3.28.9 | 459 |
| `:WAVeform:YORigin?` | `:WAVEFORM:YORIGIN?` / `:WAV:YOR?` | 查询当前选中通道源Y方向上相对于垂直参考位置的垂直偏移 | 3.28.10 | 460 |
| `:WAVeform:YREFerence?` | `:WAVEFORM:YREFERENCE?` / `:WAV:YREF?` | 查询当前选中通道源Y方向的垂直参考位置 | 3.28.11 | 461 |
| `:WAVeform:STARt` | `:WAVEFORM:START` / `:WAV:STAR` | 设置或查询波形数据读取的起始位置 | 3.28.12 | 461 |
| `:WAVeform:STOP` | `:WAVEFORM:STOP` / `:WAV:STOP` | 设置或查询波形数据读取的停止位置 | 3.28.13 | 462 |
| `:WAVeform:PREamble?` | `:WAVEFORM:PREAMBLE?` / `:WAV:PRE?` | 查询并返回全部的波形参数 | 3.28.14 | 463 |

<details><summary>3.28 命令格式原文（逐字，含参数占位符）</summary>

| 节 | 手册「命令格式」原文 |
|---|---|
| 3.28.1 | `:WAVeform:SOURce <source>` ; `:WAVeform:SOURce?` |
| 3.28.2 | `:WAVeform:MODE <mode>` ; `:WAVeform:MODE?` |
| 3.28.3 | `:WAVeform:FORMat <format>` ; `:WAVeform:FORMat?` |
| 3.28.4 | `:WAVeform:POINts <point>` ; `:WAVeform:POINts?` |
| 3.28.5 | `:WAVeform:DATA?` |
| 3.28.6 | `:WAVeform:XINCrement?` |
| 3.28.7 | `:WAVeform:XORigin?` |
| 3.28.8 | `:WAVeform:XREFerence?` |
| 3.28.9 | `:WAVeform:YINCrement?` |
| 3.28.10 | `:WAVeform:YORigin?` |
| 3.28.11 | `:WAVeform:YREFerence?` |
| 3.28.12 | `:WAVeform:STARt <sta>` ; `:WAVeform:STARt?` |
| 3.28.13 | `:WAVeform:STOP <stop>` ; `:WAVeform:STOP?` |
| 3.28.14 | `:WAVeform:PREamble?` |

</details>

