# 文档漂移审计报告

日期：2026-09-13
范围：`docs/`、`mcp_instruments/README.md`、`dh1766_control/{README.md,docs/}` 等文档
与当前代码/实测留痕的一致性核对。
约束：只做静态阅读（Read/Grep/Glob），**未连接任何仪器、未运行任何脚本**；
未触碰代码文件、`TEST_SCRIPTS/`、`TEST_DATA/`、根 `README.md` 与 `AGENTS.md`。

> 下文行号均为**本次修改后**的行号。

## 一、逐条漂移与处置

### A. `docs/AI_OPERATION_GUIDE.md`

| # | 位置 | 原文（漂移内容） | 实际事实 | 证据 | 处置 |
|---|---|---|---|---|---|
| A-1 | L47（原 L37） | `wf = ...  # 波形读取（DESC 布局待专研）` | DESC 解析**正确**：`interval` 与 `ACQ:SRAT?` 一致、FFT 主频与设备硬件测量吻合；原"布局不符/读出全零"是误判（无信号时读取 + 用朴素过零计数验证调幅信号） | `AGENTS.md` §六（2026-09-09 澄清）；`TEST_SCRIPTS/sds/verify_wave_fft.py`、`verify_wave_timebase.py`；commit a77ea35 | 改为 `wf = scope.get_waveform(4, points=50000)  # 波形：电压 + 时间轴（DESC 解析正确）`；并在"关键教训"新增澄清条（L63-66） |
| A-2 | L110（原 L96） | `gen.set_output(2, True)   # ⚠ 真实信号输出` | 现签名为 `set_output(ch, on, expect_load)`，**expect_load 必填**（仅校验不设置，不符拒绝）；照抄原示例会 `TypeError` | `sdg_control/sdg.py:127-134`；`AGENTS.md` §二 | 改为 `gen.set_output(2, True, "HZ")`，注明 expect_load 必填 |
| A-3 | L123-139（原 L109-110） | "见各自 docstring 与 EXPERIENCE.md。**DHO 全功能验证待设备空闲。**" | 已完成：2026-08-24 留痕覆盖 *IDN? / snapshot / 波形读取 / 通道·时基·触发写入与恢复比对 | `TEST_DATA/dho/dho_first_verify_20260824_112452.json`、`dho_write_verify_20260824_112935.json`、`dho_ch1_wave_20260824_112452.csv`；脚本 `TEST_SCRIPTS/dho/test_dho_read.py`、`test_dho_write.py` | 更新为实测留痕说明；原句标"已过时（2026-09-13 更新）" |
| A-4 | L149-157（原 L120-123） | 待办 1「SDS800X HD 波形读取 DESC 结构布局与手册示例不符（读出全零），待专研」；待办 3「DHO924S 全功能验证待空闲」 | 同 A-1、A-3：均已推翻/完成 | 同上 | 保留原文，追加"——（2026-09-13 已更新：…）"标注 |
| A-5 | L13-15（原 L12-14） | 资源串写 "VXI-11 inst0"（无地址，与同表其余两行格式不一致） | 实际默认资源：SDS `TCPIP0::192.168.31.220::inst0::INSTR`、SDG `.206`、DMM `.123` | `mcp_instruments/server.py:52-56`（`SDS_RES`/`SDG_RES`/`DMM_RES`） | 补全三段资源串，并加注"IP 为 server.py 内置默认资源，以 instr_discover 实测为准" |
| A-6 | L32-37、L130-139 | （新增，非纠正）安全规范缺"输出开关声明状态""远程锁定禁止"两条；dh1766 无远程模式说明 | AGENTS.md 已列为安全红线；DH1766 任何远程会话置 REM、`SYST:LOC` 交还 | `AGENTS.md` §二；`dh1766.py:93-104`；`server.py:139-157`（`_psu_close`）、`:291-299`（黑名单）；`TEST_DATA/dh1766/psu_lock_probe_20260913_*.json` | 安全规范补第 7、8 条；dh1766 节补远程模式四条要点（含留痕路径） |

### B. `docs/feature_gap_20260909.md`

| # | 位置 | 原文 | 实际事实 | 证据 | 处置 |
|---|---|---|---|---|---|
| B-1 | L18 | WAVeform 行实测状态 "⚠ DESC 布局待专研" | 同上 A-1 | 同上 | 改为 "✓（2026-09-09 澄清：DESC 解析正确，interval 与 SRAT 一致、FFT 交叉验证）" |
| B-2 | L72 | P5 #20「WAVeform PREamble DESC 布局与手册示例不符（读出全零）」状态"待专研该型号结构体" | 同上 A-1 | 同上 | 保留原文，状态列追加"→（2026-09-13 已更新：已澄清关闭…）" |

### C. `docs/command_audit_20260823.md`

| # | 位置 | 原文 | 实际事实 | 证据 | 处置 |
|---|---|---|---|---|---|
| C-1 | L35-37 | "dho_control：RUN/STOP/… （**DHO924S 占用中**；语法均有手册原文，风险仅为固件差异）" | 已实测：2026-08-24 完成读/写/波形留痕 | `TEST_DATA/dho/dho_first_verify_*.json`、`dho_write_verify_*.json` | 保留原文，追加已实测标注（含留痕路径与失败项说明：CH2 SCALe 未开通道被拒属预期） |
| C-2 | L38-40 | "sds_control WAV 组：PREamble DESC 结构体偏移与该机型不符（已知问题，待专研 SDS800X HD 专属布局）；DATA 返回空与采集状态关联" | 判断有误，已关闭（同 A-1） | 同 A-1 | 保留原文，追加"（2026-09-13 已更新：该判断已推翻，问题关闭…）" |

### D. `docs/2026-08-30-mcp-injection-failure.md`

| # | 位置 | 原文 | 实际事实 | 证据 | 处置 |
|---|---|---|---|---|---|
| D-1 | L85 | "把 **17 个 MCP 工具**对应的能力，封装成 CLI 脚本" | 当前 `server.py` 为 **31 个工具**（28 专用 + 3 通用护栏）；且该"放弃 MCP 路线"的决策不代表现状（MCP 已在支持工具注入的客户端正常使用，zcode 用户级 config 已注册） | `@mcp.tool()` 计数 = 31；`AGENTS.md` §三；`mcp_instruments/SKILL.md:8` | 行内加"（2026-09-13 标注：工具数已从 17 增至 31，该路线未继续）"；文件头加历史文档横幅，标明结论限定于当时的 Codex+DeepSeek 组合 |

### E. `mcp_instruments/README.md`

| # | 位置 | 原文 | 实际事实 | 证据 | 处置 |
|---|---|---|---|---|---|
| E-1 | L31 | 工具表**缺 `sds_get_waveform`**（表内 30 个） | 实际 31 个工具；`sds_get_waveform(ch, points=50000, save_csv)` 已于 2026-09-09 新增 | `mcp_instruments/server.py:660-699`；`AGENTS.md` §六 | 表格补该行（置于 `sds_measure_phase` 后），并在标题下写明"共 31 个 = 28 专用 + 3 通用护栏" |
| E-2 | L37（原 L33） | `sdg_set_wave(ch, wvtp, freq, amp, ofst)` | 实际参数名 `freq_hz, amp_v, offset_v=0.0` | `server.py:755-756` | 改为实际参数名 |
| E-3 | L49-50 | 安全约定只写"复位类命令不暴露" | `_FORBIDDEN_RE` 同时拦截 `SYSTem:REMote` / `SYST:REM` / `SYST:LOCK` / `LOCKED`（长短形式、空白归一），查询 `SYST:REM?` 保留 | `server.py:291-304`；`AGENTS.md` §二 | 安全约定补远程锁定拦截说明 |
| E-4 | L54-55 | （新增，非纠正）未说明 DH1766 会话收尾行为 | 每次 DH1766 工具调用结束由 `_psu_close()` 补发 `SYST:LOC`（远程会话会把电源置 REM） | `server.py:139-157` | 补一行说明，指向 EXPERIENCE.md §3.1 |

### F. `dh1766_control/README.md`

| # | 位置 | 原文 | 实际事实 | 证据 | 处置 |
|---|---|---|---|---|---|
| F-1 | L29-30 | `ps.set_output(1, True)` / `ps.set_output_all([True, False, False])` | 现签名 `set_output(ch, state, expect_mode)` / `set_output_all(states, expect_mode)`，**expect_mode 必填**；照抄原示例会 `TypeError` | `dh1766_control/src/dh1766_control/dh1766.py:303`、`:319`；`AGENTS.md` §二 | 改为 `ps.set_output(1, True, "NORM")` / `ps.set_output_all([True, False, False], "NORM")` |
| F-2 | L33-39 | （新增，非纠正）无远程模式说明 | 任何远程会话把电源置 REM；`SYST:COMM:RLST:STAT?` 无响应，正确查询 `SYST:COMM:RLST?`；`SYST:LOC` 交还面板控制权且不动输出/设定 | 同上 A-6 | 用法示例后补"远程模式说明"引用块 |

### G. `dh1766_control/docs/EXPERIENCE.md`

| # | 位置 | 原文 | 实际事实 | 证据 | 处置 |
|---|---|---|---|---|---|
| G-1 | L31 | `SYST:COMM:RLST:STAT?` … 实测"返回**空串**" → 驱动返回 None | 该形式在本机 V0.1.4.3 **无响应（超时 `VisaIOError`）**，并非空串；正确查询为 `SYST:COMM:RLST?` | `TEST_DATA/dh1766/psu_lock_probe_20260913_223848.json`（`"SYST:COMM:RLST:STAT?": "<VisaIOError>"`、`"SYST:COMM:RLST?": "'REM'"`）；`commands.py:35-38` | 表格行更正为"无响应（超时，非空串）"，并注明正确写法与代码位置 |
| G-2 | L38-60 | （新增，非纠正）无远程模式章节 | 见 A-6 / G-1 | 同上 | 新增 §3.1"远程模式（REM）与 RLST 查询"：实测表（超时/REM/LOC）+ 处置（库常量、MCP `_psu_close`、REM 与 RWL 概念区分）+ 留痕路径 |
| G-3 | L111-114 | （新增，非纠正）§7 安全规范未含输出开关状态声明 | `set_output` 需 expect_mode；不符即拒并回传实际模式 | `dh1766.py:288-337`；`AGENTS.md` §二 | §7 补一条规范 |

### H. `dh1766_control/docs/SCPI_COMMANDS_DH1766A.md`

| # | 位置 | 原文 | 实际事实 | 证据 | 处置 |
|---|---|---|---|---|---|
| H-1 | L11 | 顶注固件差异：`… / SYST:COMM:RLST:STAT?` 返回**空串** | 同 G-1（超时，非空串） | 同 G-1 | 原有表述加删除线，追加 2026-09-13 更正说明 |
| H-2 | L23-24 | `SYST:REM` 行、`SYST:COMM:RLST:STAT?` 行 | 同 G-1；另 `SYST:REM` 属远程锁定类已被 MCP 黑名单拦截 | 同 G-1；`server.py:291-299` | 两行补注：正确查询写法 + 实测返回 REM/LOC + 黑名单提示 |

## 二、已核实无漂移

| 文档 / 对象 | 核对内容 | 结论 |
|---|---|---|
| `docs/command_audit_full_20260823.md` | 逐条命令与各库 `commands.py` / `dho.py` 的行号引用（抽查 dh1766/dho/sds/sdg/k3446x）；MISS 结论与 §二轮"归一化假阳性"一致 | 无事实错误，**未改** |
| `docs/command_audit_20260823.md` 其余部分 | 审计器路径 `TEST_SCRIPTS/common/audit_all_commands.py` 存在；"84 条唯一命令"与正文一致；`audit_commands.py` 存在 | 无误 |
| `mcp_instruments/SKILL.md` | 31 工具 = 28+3、`sds_get_waveform` 行、`expect_load`/`expect_mode` 必填、黑名单（含远程锁定）、`psu_power_cycle` 参数、错误分类 | 与 `server.py` 一致，**未改**（该文件不在授权修改列表，但无需修改） |
| `docs/TEST_RECORDS.md` 2026-09-13 条目 | 远程模式核实描述与留痕/代码一致 | 一致（另见"未处置"第 2 条） |
| 根 `README.md`、`AGENTS.md` | 工具数 31、安全红线、待办状态 | 与代码一致（按任务要求**未触碰**） |
| `dh1766_control/docs/DH1766 系列…用户手册.md` | 手册提取件（43 页） | 非结论性文档，无需核对 |
| `common/discovery.py::find_device` | 签名 `(idn_contains, resource, hosts, allow_scan, cidr, timeout_ms, prefilter)` | 与 GUIDE L20 主参数一致（文档省略 timeout_ms/prefilter，属示例性简化，非错误） |
| `sds_control` API 引用 | `measure_simple(item, src="C4")`、`measure_phase(src_a="C2", src_b="C1")`、`auto_scale(ch, …, use_autoset=False)`、`get_waveform`、`screenshot_png(path)`、`analyze_screen(ch)`、`diagnose_trigger()`、`snapshot()`、模块级 `drain_errors` | 全部存在且参数一致（`sds.py:224/350/590/619/663/673/1018`、`:30`） |
| `sds_control` 测量项数 | "SIMPLE 51 项" | `sds.py:276-285` `MEAS_TYPES` 恰 51 项 ✓ |
| `sdg_control` / `keysight_3446x` API 引用 | `set_basic_wave`、`basic_wave`、`set_output`；`measure`、`configure(..., range_v=)`、`get_nplc` | 全部存在（`sdg.py:127/136/147`；`dmm.py:114/133/168`） |
| `dh1766_control` API 引用 | `measure_stable`、`power_cycle`、`pre_power_check`、`output_mode`、`set_output_mode`、`apply_voltage` | 全部存在（`dh1766.py:653/465/505/377/389/560`） |
| `TEST_SCRIPTS/` 调用面 | `grep "set_output("` 全量检查 | 全部已使用新签名（`gen.set_output(2, True, gen.output_state(2).get("LOAD","HZ"))` 等），无遗留旧调用 |
| `mcp_instruments/README.md` 其余工具条目 | 23 项逐个比对 `server.py` 参数 | 除 E-1/E-2 外均一致 |
| `dh1766_control/README.md` 自包含说明 | `visa.py` 镜像 `common/visa_client.py` | 两文件均存在 ✓ |

## 三、未处置 / 待人工决定

1. **`docs/superpowers/specs/2026-08-23-common-discovery-design.md` §4 API 设计**仍写
   `find_device(..., proto: str = "inst0", ...)`；实际实现已无 `proto` 参数（改为
   `LAN_PROTOCOLS` 自动轮询 inst0 → hislip0 → raw5025-SOCKET），并新增
   `prefilter: bool = True`。**该文件不在本次授权修改列表**（设计文档，且 §8 已记录演进），
   故未改——需作者决定是否补一条"实现已偏离设计"的注记。
2. **`docs/TEST_RECORDS.md`**：时间线工具数停在"2026-09-03：MCP 增至 19 工具"
   （L45），其后 31 工具未补条目；L34 末句"DHO924S 待设备空闲后做全功能验证"已被
   2026-08-24 留痕推翻（属历史时间线条目，是否回填由作者定）。文件不在授权列表，未改。
3. **`docs/AI_OPERATION_GUIDE.md` L94-95** 的 auto_scale 矩阵成绩：`SCPI 闭环 13/17`
   可由 `TEST_DATA/common/waveform_matrix_v2_20260824_235724.json`（17 case / 13 PASS）
   印证；`AUToset 16/17` 未找到对应留痕文件（`TEST_SCRIPTS/common/autoscale_verify.py`
   只 print 不落盘）。数字自洽，故保留，待作者确认或补留痕。
4. **同文件 L143-145** "waveform_matrix.py：11 case … 10/11 PASS"：v1 多次留痕结果不一
   （`waveform_matrix_20260823_220334.json` 9/11 PASS、`_221738.json` 8/11 PASS），
   且有 v2（17 case）。"10/11" 未找到对应留痕 → 未改，建议注明版本与留痕时间点。
5. **`TEST_DATA/dh1766/psu_lock_probe_20260913_*.json`** 的 `firmware_note` 字段仍写
   "SYST:COMM:RLST:STAT? 在 V0.1.4.3 返回空串"，与同文件实测（`<VisaIOError>`）矛盾。
   TEST_DATA 为留痕数据且禁止修改，未改——仅在此记录，供后续脚本模板修正。
6. **`dg832-control/`（嵌套独立 git 仓库）** 的 `mcp_dg832/README.md` 未核对：属独立仓库、
   独立工具集（`instrument_*` 前缀 13 工具），AGENTS.md 明示"改动前单独 commit"。
7. **`docs/AI_OPERATION_GUIDE.md` L20** `find_device` 参数列表省略 `timeout_ms`/`prefilter`：
   属示例性简化，未视为漂移，保留原样。

## 四、核对方法（可复现）

全部为只读操作（Read / Grep / Glob），未执行任何脚本、未连接仪器：

1. **工具数**：`Grep pattern="@mcp\.tool" path=mcp_instruments/server.py output_mode=count` → 31；
   再用 `Grep pattern="^(async )?def [a-z_0-9]+\("` 提取 31 个工具函数名，与 README 表逐行比对
   （差分：31 = 28 专用 + 3 通用护栏）。
2. **函数签名**：`Grep pattern="def (set_output|set_output_all|measure_simple|measure_phase|screenshot_png|auto_scale|diagnose_trigger|snapshot|analyze_screen|set_basic_wave|basic_wave|get_nplc|apply_voltage|power_cycle|measure_stable|output_mode|set_output_mode|rlstate)\("`，
   限定 `sdg_control/`、`dh1766_control/`、`sds_control/`、`keysight_3446x/` 目录。
3. **调用面回归**：`Grep pattern="set_output\(" path=TEST_SCRIPTS` 检查脚本是否仍用旧签名。
4. **DH1766 远程模式事实**：`Grep pattern="SYST_RLST|RLST|SYST:LOC|SYST:REM" path=dh1766_control`；
   读取 `TEST_DATA/dh1766/psu_lock_probe_20260913_223848.json`、`_223927.json`、
   `dh1766_20260913_224113.json`，并与 `server.py:139-157`（`_psu_close`）、`:291-304`（黑名单）对照。
5. **DHO 验证留痕**：`Glob pattern="TEST_DATA/dho/*"` → `dho_first_verify_*.json`、
   `dho_write_verify_*.json`、`dho_ch1_wave_*.csv`；逐个读取核对覆盖项。
6. **SDS DESC 澄清**：读 `AGENTS.md` §五/§六；`Glob pattern="TEST_SCRIPTS/sds/verify_wave_*.py"`。
7. **矩阵成绩**：`Grep pattern="\"verdict\": \"PASS\"" output_mode=count` 与
   `Grep pattern="\"case\":"` 统计 `TEST_DATA/common/waveform_matrix*_2026*.json`。
8. **资源串**：`Read mcp_instruments/server.py` 头部常量（`SDS_RES`/`SDG_RES`/`DMM_RES`/
   `DHO_RES`/`PSU_RES`，L52-56）。
9. **黑名单**：`Read mcp_instruments/server.py:289-307`（`_FORBIDDEN_RE` 与 `_is_forbidden`）。
10. **待办真实性**：凡文档写"待办/待专研"，均按 §1 的方法找对应留痕文件或代码变更，
    有则标注完成、无则保留原状并记入"未处置"。
