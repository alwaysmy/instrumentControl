# DHO800/900 与 MHO900：命令集一致性比对与合并决策（2026-09-15）

问题：MHO 与 DHO 的编程接口是否一致？若一致，是否可以功能合并？

依据（全部离线、可复算）：
- DHO 侧：`dho_control/docs/DHO800编程手册_output/DHO800编程手册.md`
  —— 与用户提供的 `D:\Downloads\Datasheets\仪器手册\DHO800_DHO900_ProgrammingGuide_CN.pdf`
  **同一文档**（418 页，"DHO800/DHO900 编程手册"，2025 版）
- MHO 侧：`mho_control/docs/MHO900编程手册_output/MHO900编程手册.md`（480 页，654 条命令）
- 比对脚本：`TEST_SCRIPTS/common/compare_rigol_scopes.py`（命令集）、
  `compare_rigol_scope_semantics.py`（语义抽样）
- 留痕：`TEST_DATA/common/rigol_scope_command_compare_*.json`、`rigol_scope_semantics_*.json`

## 一、结论（先说答案）

**架构与核心命令集高度一致，可以合并；但不能做成"一个类通吃"——需要一张很小的家族差异表。**
合并的实际收益很大：DHO 驱动目前**缺** MHO 驱动已有的能力（双信源相位/延迟测量、波形分片读取、
合法性与量程校验、原生 PNG 截图、`,ON` 式参数校验），而 DHO 手册**明确支持**这些命令——
即这些差距是"驱动没写"，不是"仪器没有"。

## 二、命令集量化比对（名字层）

```
DHO800/900 手册命令键:   908
MHO900     手册命令键:  1051
共有（DHO 键在 MHO 手册中命中）: 881   = DHO 的 97%
仅 DHO 有:  27 条（其中多数是提取噪声，见 §四）
仅 MHO 有: 116 条（Bode 图、电源分析、掩码测试、I2C/SPI/CAN 等总线解码、FFT/DVM 计数器的完整组等）
```

**驱动视角（更直接）**：

```
DHO 驱动实际用到 40 条命令 → 40 条在 MHO 手册里都有   （100%）
MHO 驱动实际用到 45 条命令 → 43 条在 DHO 手册里都有   （仅 2 条 MHO 专有）
```

MHO 驱动那 2 条 DHO 没有的：`:ACQuire:BITS`（位组长度 14/16）、`:CHANnel<n>:IMPedance`（1MΩ/50Ω 输入阻抗）。

→ **"DHO 驱动能驱动 MHO"在命令名层面成立**；反向也几乎成立，只差这两条。

## 三、家族差异表（合并后必须按型号切换的部分）

| 项 | DHO800/900 | MHO900 | 证据 |
|---|---|---|---|
| 清除测量项 | `:MEASure:CLEar` | `:MEASure:DELete` | DHO 手册 `CLEar`×6/`DELete`×0；MHO `CLEar`×0/`DELete`×3（**互斥**） |
| 采集方式第四态 | `ULTRa` | `HRESolution` | DHO 手册 3.3.4 `{NORMal\|PEAK\|AVERages\|ULTRa}`；MHO `{…\|HRESolution}` |
| `:ACQuire:BITS`（14/16 位） | 手册无此命令 | 有 | 关键词计数 DHO=0 / MHO=6 |
| `:CHANnel<n>:IMPedance`（1M/50Ω） | 手册无此命令 | 有 | DHO=0 / MHO=17 |
| 采样率/带宽随通道数 | DHO924S 4ch 分档 | MHO984 1-2ch 800MHz·4GSa/s → 3-4ch 400MHz·1GSa/s | 用户手册摘要 |
| `:WAVeform:PREamble?` 字段 | 10 字段，`format`=0(BYTE)/1(WORD)/2(ASC) | 10 字段（同序） | 两手册同构 → 解析代码可共用 |
| `:WAVeform:POINts` NORMal 上限 | 1~1000 | 1~1000 | 两手册一致 |
| 波形 ASCII 格式是否带 TMC 头 | 未实测（DHO 不在本实验台） | **不带**（实测，二进制才带） | `TEST_DATA/mho/verify_mho_*.json` |
| `:DISPlay:DATA?` 截图 | 有（`{BMP\|PNG\|JPG}`） | 有（同） | 两手册一致 |
| `:SYSTem:LOCKed`（屏幕键盘锁） | 有 | 有 | 均属"禁止远程锁定"族，黑名单已覆盖 |
| `*OPT?` | 手册未记载 | **查询无响应**（实测超时） | 不要用 |

### 一处**必须更正**的既有笔记

`AGENTS.md` 与 `dho_control/dho.py:252` 都写着 DHO 的边沿第三态是 `RFail`。
**两份手册实际都写 `RFALl`**（DHO 手册 `RFALl`×12、`RFail`×0；MHO 同理）。
`RFail` 是驱动 docstring 的笔误，此前被我按"系列差异"记进了 AGENTS.md —— 已更正。
（教训：文档间互相抄写会把笔误固化，**以手册原文为准**。）

## 四、"仅 DHO 有"的 27 条多为提取噪声

`*RCL`/`*SAV`（存储覆写类，属安全红线命令）、`ASCII`/`I`/`ID`/`RX`/`TX`/`TRIG`/`CURS`/`XY`/`DUYT`/`RAN`/`WRE`
等是 DHO 手册提取版里**表格碎片/正文词**被索引到的结果，不是可执行命令。真正需要逐个确认的只有
`ACQ:MEMD`（内存深度相关）、`REC:WRE`（波形录制）、`SOUR:FUNC:SQU:DUYT`（内置源方波占空比）、
`DVM:*`、`HIST:RAN`、`TIM:XY:Z` 等少数几条，且都属于 MHO **另有**更完整实现的功能域
（MHO 的 DVM/直方图/XY 组齐全）。→ **不做逐条移植**，按需再加。

## 五、合并方案（据此实施）

采用 **"共享内核 + 家族差异表"**，而不是"两个类合并成一个"：

```
rigol_scope/            共享内核（本次新增）
  profile.py            Family 数据类：差异表字段（清测量命令/枚举/能力开关/上限…）
  scope.py              RigolScope：连接、查询、TMC 解析、波形分片读取、测量（含双信源）、
                        截屏、通道/时基/触发/采集访问器、快照、控制流、错误队列
dho_control/commands.py 家族事实（DHO800/900 的取值）→ PROFILE
mho_control/commands.py 家族事实（MHO900 的取值）→ PROFILE
dho_control/dho.py      class DHO(RigolScope)   —— 薄封装，公开 API 不变
mho_control/mho.py      class MHO(RigolScope)   —— 薄封装，公开 API 不变
```

收益：
1. **DHO 白拿 MHO 已验证的能力**：双信源相位/延迟测量（`:MEASure:ITEM? RRPHase,CHANnel1,CHANnel2`，
   两手册都有）、波形分片读取（RAW 大深度不再单帧几十 MB）、`POINts` 上限与 RAW/STOP 前置校验、
   原生 PNG 截图、统一的 `9.9E37` 无效读数处理；
2. **顺带修掉 DHO 驱动的三处已复核缺陷**（见 `docs/review_20260915.md` B3/E1）：
   `fmt_up == "ASCii"` 死分支（ASCII 永远抛异常）、`get_waveform` 不校验 points/不检查 RAW 需 STOP、
   不分片潜在超时；
3. **一处修复、两处受益**：以后只维护一份波形/测量/截图逻辑。

代价与风险：
- DHO 硬件**不在本实验台**（LAN 扫描只发现 MHO），所以 DHO 路径只能**离线验证**
  （`TEST_SCRIPTS/common/verify_rigol_scope_shared.py`：假传输回放两家族的手册响应，
  断言解析/校验/家族差异分支）；MHO 路径有真机可全量回归。
  **结论：DHO 合并后的行为变更需在 DHO 回到实验台时补一次真机验收**（清单见该测试文件头）。
- 保持 `DHO`/`MHO` 的公开方法与签名不变，MCP 工具与既有脚本零改动。

## 六、复算方式

```bash
python TEST_SCRIPTS/common/compare_rigol_scopes.py            # 命令集关系（含驱动视角）
python TEST_SCRIPTS/common/compare_rigol_scope_semantics.py   # 语义抽样（含噪声，需人工判读）
python TEST_SCRIPTS/common/verify_rigol_scope_shared.py       # 共享内核离线闭环（两家族）
python TEST_SCRIPTS/mho/verify_mho.py --allow-stop            # MHO 真机回归（合并后必跑）
```

## 七、实施结果（2026-09-15 当日完成）

| 项 | 结果 |
|---|---|
| 共享内核 | `rigol_scope/{__init__,scope,families}.py`（通用实现 + 家族差异表） |
| 库改造 | `dho_control.DHO` / `mho_control.MHO` 改为薄封装（`FAMILY` 绑定），**公开 API 未变** |
| DHO 侧补齐 | 双信源测量、分片读取、points/RAW 校验、`screenshot_png`、`measure_clear`；修 ASCII 死分支 |
| DHO 侧删除 | `reset()`（`:SYSTem:RESet` 属禁发命令，复位须走测试脚本 + 显式授权） |
| 命令审计 | 新增 `rigol_scope(共享内核，按两系列并集判)` 组：37 HIT / 1 MISS（MISS 是 families.py 里"无 *OPT? 支持"这条**否定性说明文字**，非命令调用）；dho 39 HIT/0 MISS、mho 44 HIT/0 MISS |
| 离线闭环 | `TEST_SCRIPTS/common/verify_rigol_scope_shared.py` —— **74 断言全 PASS**（假传输回放两家族响应，覆盖命令拼写/家族差异/三格式解析/量化/哨兵/截屏/快照） |
| 真机回归 | `TEST_SCRIPTS/mho/verify_mho.py --allow-stop` → **45/45 PASS**（留痕 `TEST_DATA/mho/verify_mho_20260915_112004.json`） |
| 闭环自测 | `verify_audit_extractor.py` 增加 rigol_scope 组（并集判 + 6 条必须命中）全 PASS |
| **待办** | **DHO 真机复验**（本实验台无 DHO）：交接单见 `docs/dho_live_verification_handoff.md`（准备/6 项检查/不符时改哪个字段/回填格式） |

### 顺带发现的实测事实（已写进 AGENTS.md 铁律#9）

`BYTE` 波形格式在 2V/div 下 `YINCrement` = 0.0683 V/code（是 `WORD` 的 **256 倍**），
0.25V 的小信号只占 **3 个码值** → 拿 BYTE 读数比设备测量会得到"差 20%"的**假告警**。
原先 MHO 验收脚本里"冻结态 BYTE/ASCii 一致 <2%"的断言就踩了这个坑（合并后信号变小才暴露），
现已改为：BYTE 按 8bit 量化容差判、**量值一律用 WORD 与设备测量比**（WORD/ASCii 实测差 0.00%）。
