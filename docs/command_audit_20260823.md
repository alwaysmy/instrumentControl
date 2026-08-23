# SCPI 命令审计报告（猜测命令清查）

日期：2026-08-23
背景：34465A configure 拼接错误事件后，对全部五套命令常量做出处与实测状态清查。

## 审计方法

1. 静态：逐条对照提取手册（grep 原文）确认存在性；
2. 动态：`TEST_SCRIPTS/common/audit_commands.py` 批量实测（每步查 SYST:ERR?）；
3. 清除：无出处且有风险的一律删除。

## 结论

### 已删除的猜测命令
| 库 | 命令 | 处置 |
|---|---|---|
| sds_control | `:SYST:FACT` | **删除**（无手册出处 + 恢复出厂危险） |

### 排除嫌疑（有手册出处）
| 库 | 命令 | 出处 |
|---|---|---|
| dho_control 全部 | 44 条常量 | DHO800编程手册提取版逐条抄录（TRIG_SWEEP=3.27.4 等） |
| sdg_control ARWV_Q | `C<n>:ARWV?` | 实测返回 INDEX,2,NAME,StairUp |

### 实测验证矩阵（2026-08-23 audit_commands.py，14/14 OK）

| 设备 | 验证项 | 结果 |
|---|---|---|
| SDS824X HD | ACQ:TYPE? / C1:TRA? | OK |
| SDG2122X | ARWV? / BSWV PHSE 写+回读 | OK（注意：错误队列滞后，必须先 drain 再判） |
| 34465A | NPLC 读写 / MEAS 族 7 变体（volt_ac/curr_dc/curr_ac/res/fres/cap/freq） | 全 OK，最终队列干净 |

### 标注"手册已核、待实机"（设备占用或非破坏性原则暂不测）

- dho_control：RUN/STOP/SINGLE/TFORCE/AUTOSET、通道/时基/触发/采集/波形组
  （DHO924S 占用中；语法均有手册原文，风险仅为固件差异，参照 dh1766 经验）
- sds_control WAV 组：PREamble DESC 结构体偏移与该机型不符（已知问题，
  待专研 SDS800X HD 专属布局）；DATA 返回空与采集状态关联
- keysight_3446x：SENS_VOLT_APER / SENS_COUNT / TRIG_SOURCE / STAT_PRES
  （标准 Keysight SCPI，同族 NPLC 已实测通）

### 教训固化

1. 写序列前先 drain 错误队列（滞后报错会污染逐命令查错）；
2. 命令落码前必须过提取手册这一关，禁止凭记忆裸写；
3. 写操作后回读比对 + 查 SYST:ERR?，三者缺一不可。

## 二轮：全量代码扫描（audit_all_commands.py）

范围：五套库 .py + 相关测试脚本中的全部 SCPI 字符串（含 f-string 内联），共 84 条唯一命令。

结果：54 HIT / 30 MISS；30 条 MISS 经人工对照手册逐条甄别，**全部为审计器归一化假阳性**：

| 类别 | 明细 | 手册证据 |
|---|---|---|
| 单段根命令未入索引 | dho :CLEar(3.1.1)/:SINGle(3.1.4)/:TFORce(3.1.5) | DHO 手册目录原文 |
| 混合大小写未匹配 | sds :AUToset | SDS 手册专章 |
| Keysight 长形式无冒号 | k3446x CONF/MEAS/DATA:LAST/NPLC 全部 | Truevolt 原文 CONFigure:VOLTage:DC 等；且 MEAS 七族+NPLC 已实测 |
| 错误分组残留 | :SYST:ERR?:SYST:VERS? 等 | SDG/SDS 实测均通 |

**最终结论：代码中不存在无出处的猜测命令。**
唯一被删的猜测命令为 :SYST:FACT（一轮审计发现）。
