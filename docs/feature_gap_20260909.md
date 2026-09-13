# 功能差距清单（手册有 vs 库已实现）

日期：2026-09-09
基准：SDS800XHD_Series_ProgrammingGuide_CN11G（495 页提取版）+ 实测
说明：仅列**手册明确有**的命令；"库已实现"以 sds_control 当前代码为准。

## 一、已实现（可放心用）

| 子系统 | 已覆盖 | 实测状态 |
|---|---|---|
| 根命令 | RUN / STOP / AUTOSET | ✓ |
| ACQuire | MDEP? / TYPE? / SRAT? | ✓（短形式） |
| CHANnel | VDIV / OFST / ATTN / COUPLING / TRA | ✓ |
| TIMebase | TDIV / TRDL | ✓ |
| TRIGger | MODE / STATus / EDGE:SOUR/LEV/SLOP | ✓ |
| MEASure:SIMPle | ITEM（51 项）/ SOURce / VALue / CLEar / MODE | ✓ |
| MEASure:ADVanced | P<n> 开关 / SOURce1 / SOURce2 / TYPE / VALue / CLEar | ✓（PHA 实测） |
| WAVeform | SOUR / PREamble / MAXPoint / STARt / POINt / WIDTh / DATA | ✓（2026-09-09 澄清：DESC 解析正确，interval 与 SRAT 一致、FFT 交叉验证） |
| 截屏 | PRIN? BMP | ✓ |
| SYSTem | ERR? / SHUTdown / REBoot | ✓ |

## 二、差距清单（按对测量工作的价值排序）

### P1 测量判据与统计 ✅ 已补齐（2026-09-09，实测 28/28 PASS）

| # | 命令 | 手册 | 库方法 |
|---|---|---|---|
| 1 | `MEASure:THReshold:SOURce/TYPE/ABSolute/PERCent` | p.183-185 | `meas_threshold_source/type/absolute/percent` |
| 2 | `MEASure:ADVanced:STATistics` + `:AIMLimit/:HISTOGram/:MAXCount/:RESet` | p.172-174 | `meas_statistics/stat_max_count/stat_histogram/stat_reset` |
| 3 | `MEASure:ADVanced:P<n>:STATistics` / `:SHIStory` | p.166-167 | `adv_statistics/adv_history` |
| 4 | `MEASure:DTIMe<n>:EDGE1/EDGE2/SLOPe1/SLOPe2/THReshold1/2` | p.176-178 | `dtime_config` |
| 5 | `MEASure:GATE` + `:GA/:GB` | p.179-180 | `meas_gate/meas_gate_pos` |
| + | `RDISplay` / `STYLe` / `LINenumber` / `ASTRategy[:BASE/TOP]` | p.174-181 | `meas_result_display/adv_style/adv_line_number/amp_strategy/amp_strategy_base_top` |

实测疑点（待深挖）：阈值类型为 PERCent 时查询 `THR:ABS?` 返回的也是百分比值
（90/50/10），与 `THR:PERC?`（9.00E+01/5.00E+01/1.00E+01）相同——疑为固件共用
存储或查询语义与手册不符，写绝对阈值前需实测确认。

### P2 测量辅助

| # | 命令 | 手册 | 用途 |
|---|---|---|---|
| 6 | `CURSor:*`（MANual/TRACk/XY 等） | p.33-45 | 光标测量 |
| 7 | `COUNter:CURRent?/VALue?/NDIGits` + `:STATistics` | p.33-34 | 频率计与统计 |
| 8 | `MEASure:ADVanced:STYLe` / `ASTRategy:BASE/TOP` | p.174-175 | 自动测量策略 |
| 9 | `MEASure:RDISplay` | p.181 | 测量结果显示开关 |

### P3 采集与触发扩展

| # | 命令 | 手册 | 用途 |
|---|---|---|---|
| 10 | `ACQuire:AMODe/CSWeep/INTerpolation/MMANagement/MODE/NUMACq/POINts/RESolution/SEQuence` | p.17-23 | 采集模式/分辨率/分段采集 |
| 11 | `WAVeform:SEQuence` | 波形读取章 | 序列/分段波形读取（配合 ACQuire:SEQuence） |
| 12 | `TRIGger` 其他类型：PULSe/SLOPe/RUNT/PATTern/QUALified/NEDGe/Dropout/Interval/Time/Window/VIDeo | p.280+ | 各类触发 |
| 13 | 总线触发/解码：IIC/SPI/CAN/LIN/FlexRay/CANFd/IIS/M1553/SENT/MANChester | p.92-115 | 协议触发与解码 |

### P4 分析与专业功能

| # | 命令 | 手册 | 用途 |
|---|---|---|---|
| 14 | `FUNCtion<x>:*`（FFT/BASic/ADD/SUbtract/...） | p.151+ | 数学运算与 FFT |
| 15 | `DVM:*` | p.126+ | 数字电压表 |
| 16 | `MASK:*` / `SEARch:*` / `NAVigate:*` / `HISTogram:*` / `BODeplot:*` | p.195+/ | 模板测试/搜索/导航/直方图/伯德图 |
| 17 | `RECord:*` / `SAVE:*` / `MEMory:*` | p.186+ | 录制/存储/参考波形 |
| 18 | `SYSTem` 其他：DATE/TIME/LANGuage/PON/SELFCal/COMMunicate/LOCKed/BUZZer/TOUCh | p.233+ | 系统设置 |
| 19 | `LAN:*` | p.130+ | 网络配置 |

### P5 已知遗留

| # | 问题 | 状态 |
|---|---|---|
| 20 | WAVeform PREamble DESC 布局与手册示例不符（读出全零） | 待专研该型号结构体 →（2026-09-13 已更新：**已澄清关闭**。DESC 解析正确；原"读出全零"源于①无信号时读取②用朴素过零计数验证调幅信号。FFT 交叉验证通过，`get_waveform` 已暴露为 MCP 工具 `sds_get_waveform`） |
| 21 | 数字通道 D0-D15 波形读取 | 未实现 |

## 三、建议

1. **P1 优先**：THReshold + STATistics 是相位/稳定性测量的直接支撑，工作量小（各 3-5 条命令）；
2. **P2 次之**：COUNter 与 CURSor 对独立验证有用；
3. P3-P4 按项目需要逐步接入（总线解码/FFT 等属于专项）；
4. 任何新增命令按铁律：手册核对 → drain → 写 → 查错 → 回读。
