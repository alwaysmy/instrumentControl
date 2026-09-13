# 仪器地址硬编码专项审计报告

日期：2026-09-13
范围：全仓（`mcp_instruments/`、`common/`、各设备库、文档、`TEST_SCRIPTS/`、`TEST_DATA/`、附带文件）
约束：只读审计（Read/Grep/Glob），**未连接任何仪器、未运行任何 `TEST_SCRIPTS/` 脚本、未做任何 git 操作**；
除本文件外未新建/修改任何文件。手册提取件正文（各库 `docs/*_output/`）不在审计范围。

> **审计基准**：仪器 IP/端口/串口号**不是固定资产**——DHCP 续租换 IP、换网段不可达、
> USB 换口换资源串、ASRL 编号漂移（`AGENTS.md:116` 已记录校准器 ASRL31 → 离线 / ASRL5 换机）。
> 因此任何"把某个具体地址当成该设备专用资源"的写法都属缺陷；地址只能是"某次实测当时的地址"，
> 且必须能被发现层（`instr_discover` / `common.find_device` / 各库 `find_*()`）覆盖。

> **重要状态说明（本次审计期间发现）**：`mcp_instruments/server.py` 在本报告撰写期间**已被改造**
> ——开头读取时 L52-56 还是 `SDS_RES`…`PSU_RES` 五个硬编码常量与工具签名默认值，再次读取时已
> 变为 `_resolve(kind, resource)` 解析层（环境变量/配置文件/缓存/自动发现），`server.py` 的 41 处
> `resource: str | None = None` 已全部生效。**本报告第二节的"必须改造清单"已据实拆分：
> 代码层记为已完成，剩余为文档层与脚本层。** 若该改造被回滚，第二节 2.3 可直接复用。

---

## 一、结论摘要

| 层面 | 必须改造 | 可保留但需标注 | 说明 |
|---|---|---|---|
| `mcp_instruments/server.py`（代码） | **0 处残留**（已完成） | 1 处（`cidr` 示例） | 解析层 `_resolve` 已实现，5 个硬编码常量已删除，28 个专用工具签名改为 `resource: str \| None = None` |
| 各设备库 / `common/`（代码） | **0 处** | 示例 docstring（`common/__init__.py:6-7`、`common/discovery.py:236`，均为占位地址，非本机设备） | 5 个 `find_*()` 全部走 `find_device()`，无 hosts/cidr 默认值；`dh1766_control` 另有独立"上次成功缓存" |
| 文档（资源清单表） | **4 处**（`README.md`、`AGENTS.md`、`docs/AI_OPERATION_GUIDE.md`、`docs/doc_drift_audit_20260913.md`） | 3 处（`docs/TEST_RECORDS.md`、`docs/superpowers/specs/*`、`dh1766_control/docs/{EXPERIENCE,SCPI_COMMANDS_DH1766A}.md`） | 前 4 份把"当时地址"呈现为设备资源；后 3 份属历史留痕 |
| 文档（MCP 使用指引） | **2 处待补**（`mcp_instruments/README.md`、`mcp_instruments/SKILL.md`） | — | 工具 `resource` 参数语义已变（可省略），指引须补解析链说明 |
| `TEST_SCRIPTS/**/*.py` | **31 个文件 / 49 处**（见 2.2） | 3 个文件 / 5 处（`diag_lan_candidates.py`、`diag_lan_ports.py`、`verify_discover_final.py`） | 全部为直连硬编码；文档已推荐的冒烟/审计脚本优先 |
| `TEST_DATA/**` | 0（不建议改） | 18 个 JSON/TXT + 1 个脚本备份，共 71 处 `192.168.31.*`，另含 USB/ASRL 资源串 | 历史留痕数据，**只统计不改**；建议在目录 README 或文件模板加一句"地址为当时值" |
| 附带文件（`.gitignore`/`requirements.txt`/`pyproject.toml`/egg-info） | 0 处 | — | 无地址信息；`.gitignore:9` 仅保留旧缓存路径兜底规则 |

> 已核实**无设备地址、无需改造**的文件：`docs/command_audit_20260823.md`、`docs/command_audit_full_20260823.md`、
> `docs/feature_gap_20260909.md`、`docs/2026-08-30-mcp-injection-failure.md`、`dh1766_control/README.md`、
> `mcp_instruments/README.md` 与 `SKILL.md`（无 IP，但 `resource` 参数语义待补，见 2.1 补充表）、
> `common/*.py` 与 5 个设备库代码、`emoe_control/`、`devices/`、`archive/`、
> `.gitignore` / `requirements.txt` / `dh1766_control/pyproject.toml` / egg-info。
> 唯一例外是 `common/__init__.py:6-7` 与 `common/discovery.py:148,236` 的**占位/协议常量**（非本机设备地址，见第三节）。

**一句话结论**：**代码层已不写死地址**（`server.py` 改造完成、各设备库本就干净）；
**风险集中在文档资源表与 31 个测试脚本**——它们把"2026-08-23 当时的地址"固化成了"设备资源"，
换网段后照抄即失败（或更糟：照抄旧地址连到别的设备）。

> **改造完成情况（2026-09-13 收尾）**：
> - §2.1 文档：4 处资源表已改为"发现入口"（`README.md` / `AGENTS.md` /
>   `AI_OPERATION_GUIDE.md`；同日早间的 doc_drift 审计报告已就其 A-5 条目标注作废）；
>   MCP `README.md` 与 `SKILL.md` 已补解析链说明与 `devices.json` 示例。
> - §2.2 脚本：**34 个脚本**改走 `common/resolver.py` / `find_*()`，
>   `python -m compileall -q TEST_SCRIPTS` 全通过（未运行任何连设备的脚本）；
>   逐文件对照见 `docs/script_ip_refactor_20260913.md`。
> - §2.3：`server.py` 的 `cidr` 示例已改为中性网段（`10.0.0.0/24`）。
> - §三 历史留痕：按建议加统一标注，未改留痕内容本身（`TEST_RECORDS.md`、
>   superpowers 设计稿、dh1766 `EXPERIENCE.md` / `SCPI_COMMANDS_DH1766A.md`）。
> - 解析层落点：**`common/resolver.py`**（MCP 服务器与脚本共用），
>   `server.py` 只保留 `_resolve` 等别名；`instr_discover` 新增
>   `resolved` / `recognised_now` / `psu_local_restored` 三个返回字段。
> - 附带修掉：`instr_discover` 探测到 DH1766 时补发 `SYST:LOC`
>   （否则"跑一次发现，电源面板就进 REM"）。

---

## 二、必须改造清单

### 2.1 文档——资源清单表（把"当时地址"当"设备资源"呈现）

| 文件:行 | 现状（原文/常量） | 风险（换网段/换口后会怎样） | 建议改法 |
|---|---|---|---|
| `README.md:78-85` | 表头"设备与资源"，5 行写 `TCPIP0::192.168.31.144::5025::SOCKET`、`.146::5555`、`192.168.31.220::inst0`、`.206`、`.123` | AI/人类照抄资源串直连；DHCP 换址后连接失败或**连到同网段其他设备**（安全风险：对未知设备下发 SCPI） | 表改名为"设备与发现入口"，列改「设备 \| 库 \| 发现入口」（`find_dh1766()` / `find_dho()` / `find_sds()` / `find_sdg()` / `find_dmm()` / `instr_discover`）；删除具体 IP；表下加统一标注（见第三节） |
| `AGENTS.md:109-116` | "四、当前设备与资源"表：L111 `.144`、L112 `.146`、L113 "VXI-11（.220）"、L114 "（.206）"、L115 "（.123）"、L116 Emoe（已正确说明 ASRL 漂移） | 同上；且 L113-115 的半截 IP 更易被误读为"设备固定标识" | 同 README：改列为「设备 \| 库 \| 发现入口」；把"（.xxx）"改为"（2026-08 实测曾在 .xxx，已随 DHCP 变化）"或直接删除；保留 L116 的漂移说明并提升为全表通则 |
| `docs/AI_OPERATION_GUIDE.md:9-18` | 表列"实测资源"写 5 个完整资源串（L11-15）；L17-18 注："IP 为 MCP `server.py` 内置默认资源（`SDS_RES`/`SDG_RES`/`DMM_RES`/`DHO_RES`/`PSU_RES`）；地址变动后以 `instr_discover` 实测结果为准" | **该注已与代码漂移**：`server.py` 现无这 5 个常量（改造后为 `_resolve` + `DEVICE_KINDS`），照此注配置会找不到"内置默认" | ① L11-15 资源列改为"发现入口 + 当时实测地址（会变）"两列，或删地址只留 `find_*()`；② L17-18 注改写为解析链说明（见第四节 4.1）；③ L20-21"统一发现入口"段补 `_resolve` 五级链 |
| `docs/doc_drift_audit_20260913.md:21,137-138` | A-5 条目写"资源串…补全三段资源串，并加注 IP 为 server.py 内置默认资源"；核对方法 8 写"读 `server.py` 头部常量（`SDS_RES`/…，L52-56）" | 该审计报告为当日早间产物，其"建议改法"与"核对方法"均基于**已被删除**的常量，按它执行会得出错误结论 | 在 A-5 与核对方法 8 后追加"（2026-09-13 晚更新：`server.py` 已改为 `_resolve` 解析层，无内置常量；本条建议作废，资源表按'发现入口'改写）"；核对方法 8 改为 `Grep "_resolve\|DEVICE_KINDS" mcp_instruments/server.py` |

**补充（MCP 使用指引，属"必须补"）**：

| 文件:行 | 现状 | 风险 | 建议改法 |
|---|---|---|---|
| `mcp_instruments/README.md:16-46`（工具表） | 工具表未说明专用工具的 `resource` 参数**可省略**及解析顺序；表头"共 31 个…" | AI 按旧印象认为不传 resource 会连到"内置默认 IP"；或不知道换址后要先跑 `instr_discover` | 工具表下加 3-4 行"资源解析"说明：显式 `resource` > `INSTRUMENT_<KIND>_RES` > `%LOCALAPPDATA%\instrumentControl\devices.json` > 上次成功缓存 > 自动发现；换址先 `instr_discover` |
| `mcp_instruments/SKILL.md:44-59,68` | "通用护栏"节与参数表中 `resource` 被列为工具参数（`sds_screenshot \| resource`），未说明可省略 | AI 可能为每个专用工具显式拼地址（回到硬编码老路） | 在 SKILL.md 工具选择决策树（L13-18）后加一条："专用工具的 `resource` 默认不传——地址由 server 解析（env/配置/缓存/自动发现）；只有通用 `instr_query/instr_write` 必须显式给 resource" |

> 各库 `README.md`（`dh1766_control/README.md`）示例用 `VisaClient(find_dh1766())`，**写法正确，无需改**。

### 2.2 `TEST_SCRIPTS/**/*.py`——硬编码 resource 清单（31 文件 / 50 处）

> 判定标准：`SDS("TCPIP0::<ip>…")` / `= "TCPIP0::<ip>…"` / `find_xxx(hosts=["<ip>"])` 形式直连。
> "可用 `find_*()` 替代"列给出直接替换写法；**注意**：`find_*()` 默认 `allow_scan=False`，
> LAN 未注册设备需 `hosts=` 或先跑 `instr_discover`（发现后 server 缓存可用，但脚本直连库时不走 server 缓存）。

| 文件:行 | 常量/原文 | 可用 `find_*()` 替代 | 备注（优先级见第五节） |
|---|---|---|---|
| `TEST_SCRIPTS/common/three_libs_smoke.py:29,36,47` | `SDS("TCPIP0::192.168.31.220::inst0::INSTR")`、`SDG(…206…)`、`DMM(…123…)` | `SDS(find_sds())` / `SDG(find_sdg())` / `DMM(find_dmm())` | **AGENTS.md:95 指定冒烟脚本，最高优先** |
| `TEST_SCRIPTS/common/libs_full_verify.py:33,64` | `SDS(…220…)`、`DMM(…123…)` | `find_sds()` / `find_dmm()` | AGENTS.md:96 指定 |
| `TEST_SCRIPTS/common/waveform_matrix.py:39,40` | `SDG(…206…)`、`SDS(…220…)` | `find_sdg()` / `find_sds()` | AGENTS.md:96 / GUIDE:143 引用 |
| `TEST_SCRIPTS/common/waveform_matrix_v2.py:40,41` | 同上 | 同上 | v2 为实际在跑版本 |
| `TEST_SCRIPTS/common/cross_test.py:32,33` | 同上 | 同上 | 跨设备闭环 |
| `TEST_SCRIPTS/common/audit_commands.py:31,37,52` | `SDS(…220…)` / `SDG(…206…)` / `DMM(…123…)` | `find_sds()` / `find_sdg()` / `find_dmm()` | `docs/command_audit_20260823.md:9` 引用 |
| `TEST_SCRIPTS/common/autoscale_verify.py:13,14` | `SDG(…206…)` / `SDS(…220…)` | 同上 | GUIDE:92-95 引用（矩阵成绩） |
| `TEST_SCRIPTS/common/sds_simple_meas.py:14,15` | 同上 | 同上 | 诊断脚本 |
| `TEST_SCRIPTS/common/diag_noise_to_5v.py:12,13` | 同上 | 同上 | 一次性诊断（历史） |
| `TEST_SCRIPTS/common/diag_ofst1v.py:17,18` | 同上 | 同上 | 一次性诊断（历史） |
| `TEST_SCRIPTS/common/diag_square.py:15,16` | 同上 | 同上 | 一次性诊断（历史） |
| `TEST_SCRIPTS/common/pixel_measure.py:50` | `SDS(…220…)` | `find_sds()` | 像素分析 |
| `TEST_SCRIPTS/common/sds_snap.py:15` | `SDS(…220…)` | `find_sds()` | 截图脚本 |
| `TEST_SCRIPTS/common/sds_screen_diag.py:75` | `SDS(…220…)` | `find_sds()` | 屏幕诊断 |
| `TEST_SCRIPTS/common/sds_trace_analyze.py:57` | `SDS(…220…)` | `find_sds()` | 轨迹分析 |
| `TEST_SCRIPTS/common/probe_new_instruments.py:21,22,23` | `DEVICES = {"34465A": …123…, "SDG2122X": …206…, "SDS824X_HD": …220…}` | 改为 `{name: find_xxx()}` 或 `hosts=args.host` | 新设备探测（历史） |
| `TEST_SCRIPTS/common/probe_siglent.py:52,68` | `…206…` / `…220…` 列表 | `find_sdg()` / `find_sds()` | 早期探测（历史） |
| `TEST_SCRIPTS/common/verify_model_field_fix.py:47` | `server.instr_query("TCPIP0::192.168.31.220::inst0::INSTR", "*IDN?")` | 该脚本测的是**通用工具**（resource 必填）——改为从 server 解析取：`json.loads(server.instr_discover())` 或直接用 `server.sds_status()` 拿 `resource`；最简：显式保留但加 `--resource` 参数 | MCP 回归脚本 |
| `TEST_SCRIPTS/common/verify_remaining_tools.py:28,31` | `instr_write("TCPIP0::…220…", …)` / `("…206…", …)` | 同上（通用工具需显式 resource；建议加 `--sds-res/--sdg-res` 参数，默认留空时 SKIP 该用例） | MCP 回归脚本 |
| `TEST_SCRIPTS/common/verify_remote_lock_block.py:23` | `RES = "TCPIP0::192.168.31.220::inst0::INSTR"  # 仅 --with-device 时才会真正连接` | 拦截用例**不连接设备**（L44 注释），RES 仅用于 `--with-device` 分支 → 改为 `--with-device` 时才 `find_sds()` | 已注释约束，风险低 |
| `TEST_SCRIPTS/sds/verify_wave_timebase.py:26,68` | `RES = "TCPIP0::…220…"` | `find_sds()` | 2026-09-09 留痕脚本，会复跑 |
| `TEST_SCRIPTS/sds/verify_wave_tdiv_scale.py:26,51` | 同上 | `find_sds()` | 同上 |
| `TEST_SCRIPTS/sds/verify_wave_fft.py:18` | `s = SDS("TCPIP0::…220…", timeout_ms=20000)` | `SDS(find_sds(), timeout_ms=20000)` | 同上 |
| `TEST_SCRIPTS/sds/test_meas_ext.py:22,42` | `RES = "TCPIP0::…220…"` | `find_sds()` | 实测留痕脚本 |
| `TEST_SCRIPTS/sds/test_phase_adv.py:25,58` | 同上 | `find_sds()` | 实测留痕脚本 |
| `TEST_SCRIPTS/dh1766/psu_remote_lock_probe.py:29,53,80,107` | `RESOURCE = "TCPIP0::…144::5025::SOCKET"` | `find_dh1766()`（LAN 时传 `hosts=`）；EXPERIENCE.md:57/GUIDE:138 引用其留痕 | 电源探针脚本 |
| `TEST_SCRIPTS/dh1766/test_dh1766_modes.py:24,54` | `RES = "TCPIP0::…144::5025::SOCKET"` | `find_dh1766()` | 模式验证（**电源操作，AI 直接运行风险高**） |
| `TEST_SCRIPTS/dh1766/test_dh1766_readonly_lan.py:5,36,54` | `DEFAULT_IP = "192.168.31.144"`（docstring 也写"默认 IP=…"） | 默认值改 `None` → 走 `find_dh1766()`；保留 `[IP]` 位置参数覆盖 | 已有 `sys.argv[1]` 覆盖通道 |
| `TEST_SCRIPTS/dho/test_dho_first.py:24` | `find_dho(hosts=["192.168.31.146"])` | `find_dho()`（需要固定时用 `--host`） | DHO 留痕脚本 |
| `TEST_SCRIPTS/dho/test_dho_write.py:31` | 同上 | 同上 | DHO 写入验证 |
| `TEST_SCRIPTS/common/test_sds_shutdown.py:27,51,59` | `HOST = "192.168.31.220"` | `find_sds()` 解析出 host/资源；需保留端口探测时从资源串提取 IP | **破坏性脚本（--yes 门槛），地址错会关错设备** |

**另**：`TEST_DATA/common/sds_phase_meas.py:13`（`SCOPE = 'TCPIP0::192.168.31.220::inst0::INSTR'`）——
该文件是历史脚本落在数据目录的备份（非 `TEST_SCRIPTS/` 规范位置）。建议**只标注不修改**（属留痕），
或由作者决定是否移出/加时间戳说明。

### 2.3 `server.py` 残留（可选，1 处）

| 文件:行 | 现状 | 风险 | 建议改法 |
|---|---|---|---|
| `mcp_instruments/server.py:316` | `instr_discover` docstring：`cidr 参数可选（如 '192.168.31.0/24'）` | 无实际风险（仅示例格式，非"设备专用资源"），但示例用了现场网段 | 可改为 `如 '192.168.1.0/24'` 或保留并加"（示例网段，按实际填）"；**属可保留项，改造可选** |

> 若 `server.py` 的 `_resolve` 改造被回滚（例如从 git 历史取回旧版），则本报告 2.3 需扩展为：
> 删除 L52-56 五个常量 → 新增 `_resolve(kind, resource)`（实现见第四节 4.1）→ 28 个工具签名
> `resource: str = XXX_RES` 全部改 `resource: str | None = None` → 5 个 `_xxx()` 连接函数同步改。

---

## 三、可保留但需标注清单（历史留痕 / 示例）

**统一标注文案（建议逐处粘贴，可微调）**：

> 地址为 **2026-08 实测当时值**，会随 DHCP 续租 / 换网段 / 换 USB 口 / 串口号漂移而变化；
> 接入前一律先 `instr_discover`（或对应库 `find_*()`）重新定位，勿直接照抄。

| 文件:行 | 现状 | 类型 | 建议 |
|---|---|---|---|
| `docs/TEST_RECORDS.md:18-19` | `TCPIP0::192.168.31.144::5025::SOCKET`（DH1766）、`.146::5555`（DHO）实测记录 | 历史实测时间线 | 保留；行首或段首加统一标注 |
| `docs/TEST_RECORDS.md:24-25` | "新发现三台在线仪器…`.123`、`.206`、`.220`" | 历史实测时间线 | 保留；加标注 |
| `docs/TEST_RECORDS.md:7` | `USB0::0x0957::0xA007::100260004670::INSTR` | 历史实测（USB 序列号） | 保留；加标注（USB 资源串随换口/序列号变化） |
| `docs/TEST_RECORDS.md:44,58` | `ASRL31`、`ASRL5`（串口号漂移） | 历史实测，文本已自带"会漂移"说明 | 无需改（已是正确写法范例） |
| `docs/superpowers/specs/2026-08-23-common-discovery-design.md:119-121,127` | `192.168.31.111`/`.144` 同 MAC、扫描命中记录 | 设计文档中的实测发现记录 | 保留；段首加"（下列地址为 2026-08-23 实测，会变）" |
| `dh1766_control/docs/EXPERIENCE.md:4,13` | `USB TMC：USB0::0x0957::0xA007::100260004670::INSTR` | 设备经验文档 | 保留；加标注（USB 换口/换机即变） |
| `dh1766_control/docs/SCPI_COMMANDS_DH1766A.md:4` | 同上（设备实测行） | 命令速查 | 保留；加标注 |
| `docs/AI_OPERATION_GUIDE.md:11-15` | 5 个完整资源串 | **混合**：若保留地址列则须加标注；建议直接改为"发现入口"列（见 2.1） | 二选一，推荐删地址 |
| `AGENTS.md:111-115`、`README.md:80-84` | 同上 | 同上 | 同上 |
| `TEST_DATA/**`（18 文件 / 71 处 `192.168.31.*`；另有 `USB0::` 4 文件、`ASRL*` 7 文件） | 各类探测/留痕 JSON/TXT | **留痕数据，禁改**（AGENTS.md 留痕纪律） | 不改；建议 `TEST_DATA/README.md`（若新建）或写入模板加一句"文件内地址为采集当时值" |
| `TEST_SCRIPTS/common/diag_lan_candidates.py:18,32,35` | `CANDIDATES = ["192.168.31.111","192.168.31.144"]`、hislip 重试目标 | 一次性网络诊断（对象即"当时疑似虚拟接口"） | 保留；文件头加标注（诊断对象为当时地址，重跑需改） |
| `TEST_SCRIPTS/common/diag_lan_ports.py:62` | `ips = sys.argv[1:] or ["192.168.31.146"]` | 端口诊断，**已有 CLI 覆盖** | 保留；默认值加标注或改为必填参数 |
| `TEST_SCRIPTS/common/verify_discover_final.py:15` | `server.instr_discover(cidr="192.168.31.0/24")` | **cidr 不是设备地址**（是"扫哪个网段"） | 保留；建议默认 `None`（自动探测）或加注释 |
| `common/__init__.py:6-7` | `find_device("DH1766", hosts=["192.168.1.100"])`、`cidr="192.168.1.0/24"` | 用法示例（占位地址，非本机） | 保留；可加 `# 示例：换成本机网段` |
| `common/discovery.py:148-150` | `192.168.0.0/16`（RFC1918 私网判定） | 协议逻辑常量，**非设备地址** | 不改（正确用法） |
| `common/discovery.py:236` | `如 TCPIP0::ip::hislip0::INSTR` | 格式示例（`ip` 占位） | 不改 |

---

## 四、改造方案建议（资源解析层）

### 4.1 现状实现（`server.py`，已生效，作为基准）

`server.py:52-171` 已实现下述解析层，**建议文档与脚本改造向它对齐**（而非另起方案）：

```python
# 缓存/配置目录（用户级，不落仓库；与 dh1766_control 库同一目录习惯）
_CACHE_DIR  = %LOCALAPPDATA% / "instrumentControl"      # 兜底 XDG_CACHE_HOME / ~/.cache
_CACHE_FILE = _CACHE_DIR / "last_good_resources.json"   # 键: sds/sdg/dmm/dho/psu
_CONFIG_FILE= _CACHE_DIR / "devices.json"               # 用户手写，优先级高于缓存

DEVICE_KINDS = {                                        # kind -> (IDN 匹配串, 名称, env 名)
  "sds": ("SDS",       "Siglent SDS800X HD 示波器", "INSTRUMENT_SDS_RES"),
  "sdg": ("SDG",       "Siglent SDG2000X 信号源",   "INSTRUMENT_SDG_RES"),
  "dmm": ("34465A",    "Keysight 34465A 万用表",    "INSTRUMENT_DMM_RES"),
  "dho": ("DHO",       "RIGOL DHO800/900 示波器",   "INSTRUMENT_DHO_RES"),
  "psu": ("DH1766",    "DH1766 三路可编程电源",      "INSTRUMENT_PSU_RES"),
}

def _resolve(kind, resource=None):   # server.py:152
    显式参数 > env INSTRUMENT_<KIND>_RES > devices.json[kind]
    > last_good_resources.json[kind] > find_device(IDN, allow_scan=False)
    自动发现成功 → _remember(kind, res) 回写缓存
    全失败 → RuntimeError（含可执行指引：跑 instr_discover / 设 env / 写配置文件）

# instr_discover 成功后（server.py:429-436）：
#   lan + visa 的 (resource, idn) 全量送 _remember_candidates()
#   → _idn_kind(idn) 归类 → _resource_rank() 优选 → 回写缓存
# 优选顺序（server.py:118-127）：inst0::INSTR(0) > hislip0(1) > 其他 ::INSTR(2) > raw SOCKET(3)

# instr_discover 返回值新增两个字段：
#   resolved       = 解析层当前已知映射（配置 + 缓存）
#   recognised_now = 本次发现识别并写入缓存的设备
```

**已实现的设计要点（值得保留）**：
1. 缓存写的是"**上次成功/曾发现过**"的地址，不是"设备资源"——语义正确；
2. `_resource_rank` 对"多协议命中同一 IP"给出确定性优选（DH1766 这类只有 raw SOCKET 的设备不受影响，因为它是唯一候选）；
3. 报错文案自带指引（见 4.3），符合"失败时给出可执行指引"要求；
4. `instr_query`/`instr_write` 保持 `resource` **必填**——通用工具面向任意设备，不能猜（正确，勿改）。

### 4.2 建议补强（改造第二阶段的候选，按价值排序）

| # | 建议 | 理由 | 落点 |
|---|---|---|---|
| 1 | **缓存命中但连接失败时，自动降级重发现** | 现在是"缓存 → 直连失败 → 报错"；换网段后第一次调用必然失败一次，且用户可能不知道缓存已失效。建议：`_xxx()` 连接抛异常且地址来自缓存时，清该 kind 缓存并重试一次 `_resolve`（或至少把"缓存地址 X 已失效，请跑 instr_discover"写进错误文案） | `server.py::_sds/_sdg/_dmm/_dho/_psu_connect` + `_resolve` |
| 2 | **`emoe`（串口）纳入 `DEVICE_KINDS`** | `instr_discover` 已能识别串口设备，但 `_idn_kind` 只认 5 类，EmoeCalibrator/ADS127L11 的地址不入缓存；串口恰是漂移最频繁的（ASRL31→ASRL5→离线） | `DEVICE_KINDS` 增 `"emoe": ("EmoeCalibrator", …)`；注意 ASRL 资源建议**不长期缓存**或标注"失效即重发现" |
| 3 | **缓存/配置写盘原子化** | `_remember` 是"读整文件 → 改一键 → 覆写"，MCP 单进程 + `_DEVICE_LOCK` 下安全；但脚本/多实例并发时会丢更新。建议写临时文件 + `Path.replace()` | `server.py::_remember` |
| 4 | **持久化"发现时间戳"** | 缓存目前只有地址，无采集时间；建议值改 `{"resource": …, "ts": …, "idn": …}`（读旧格式兼容），便于判断缓存是否过期 | `_CACHE_FILE` 结构 |
| 5 | **与 `dh1766_control` 库的独立缓存统一语义** | 库侧 `find_dh1766()` 自带 `last_good_resource.json`（键 `"DH1766"`，`dh1766_control/discovery.py:26-31`），server 侧是 `last_good_resources.json`（键 `"psu"`）——两套文件、两套键，互不感知。库为 pip 独立安装必须自包含（合理），但**建议文档写明两者关系**，或 server 的 psu 解析把库缓存作为第 4.5 级回退 | 文档 + 可选 `_resolve` 分支 |
| 6 | `devices.json` 增加示例/校验 | 现在只有代码注释说明格式；建议在 `mcp_instruments/README.md` 给出 JSON 示例与键名表（sds/sdg/dmm/dho/psu） | 文档 |

### 4.3 失败报错文案模板（以现状为准，改造脚本时复用）

`server.py:164-169` 现文案（推荐作为**统一模板**）：

```
未确定 <设备名> 的资源地址（自动发现失败：<ExcType>）。
仪器地址会随 DHCP/换网段/换口变化，请先调用 instr_discover 重新发现（发现结果会自动记住）；
也可设环境变量 INSTRUMENT_<KIND>_RES，或把地址写进配置文件 <配置路径>（键名 <kind>）。
```

脚本层建议统一为：
```python
raise SystemExit(
    f"未定位到 {dev}：地址会随 DHCP/换网段/换口漂移，"
    f"请先运行 instr_discover 或本脚本 --host/--resource 显式指定。")
```

---

## 五、测试脚本改造优先级（按"被复用频率 / 是否会被 AI 直接运行"）

排序依据：① 被 `AGENTS.md`/`README.md`/`docs/AI_OPERATION_GUIDE.md`/审计报告**点名推荐**的脚本；
② 近期（2026-09）实际产生留痕、会被复跑的验证脚本；③ 破坏性或对安全敏感的脚本；
④ 一次性历史诊断（最后改，或只加标注）。

| 优先级 | 脚本 | 依据 | 改法 |
|---|---|---|---|
| 1 | `TEST_SCRIPTS/common/three_libs_smoke.py` | AGENTS.md:95 指定冒烟；AI 最常跑 | L29/36/47 → `find_sds()/find_sdg()/find_dmm()` |
| 2 | `TEST_SCRIPTS/common/libs_full_verify.py` | AGENTS.md:96 指定 | L33/64 → `find_sds()/find_dmm()` |
| 3 | `TEST_SCRIPTS/common/waveform_matrix.py` + `waveform_matrix_v2.py` | AGENTS.md:96、GUIDE:143；跨设备闭环 | L39-40 / L40-41 → `find_sdg()/find_sds()` |
| 4 | `TEST_SCRIPTS/common/cross_test.py` | 跨设备闭环留痕脚本 | L32-33 → 同上 |
| 5 | `TEST_SCRIPTS/sds/verify_wave_timebase.py`、`verify_wave_tdiv_scale.py`、`verify_wave_fft.py` | 2026-09-09 最新留痕脚本（AGENTS.md §五/§六 引用其结论） | `RES = find_sds()` / 内联 `SDS(find_sds(), …)` |
| 6 | `TEST_SCRIPTS/common/verify_remote_lock_block.py` | 安全黑名单回归（AGENTS.md 安全红线）；默认离线跑 | L23 改为 `--with-device` 分支内 `find_sds()` |
| 7 | `TEST_SCRIPTS/dh1766/psu_remote_lock_probe.py` | EXPERIENCE.md:57、GUIDE:138 引用；**电源安全** | L29 → `find_dh1766()`（LAN 传 `hosts=`） |
| 8 | `TEST_SCRIPTS/dh1766/test_dh1766_modes.py`、`test_dh1766_readonly_lan.py` | 电源操作（误连风险最高） | `find_dh1766()`；readonly 脚本默认值改 `None` |
| 9 | `TEST_SCRIPTS/common/verify_model_field_fix.py`、`verify_remaining_tools.py`、`verify_discover_final.py` | MCP 回归脚本（工具签名改动后需复跑） | 加 `--resource` 参数或从 `instr_discover` 取 |
| 10 | `TEST_SCRIPTS/dho/test_dho_first.py`、`test_dho_write.py` | DHO 留痕脚本；`hosts=["…146"]` 换址即失败 | `find_dho()`（需要固定时 `--host`） |

> 未列入前 10 的 `diag_*`（noise/ofst/square/lan_*）、`probe_*`、`sds_screen_diag.py`、
> `sds_trace_analyze.py`、`sds_simple_meas.py`、`sds_snap.py`、`pixel_measure.py`、`autoscale_verify.py`：
> 属一次性诊断/历史留痕，改造优先级低；若不再使用，**不要删除**（用户纪律），
> 加统一标注即可（见第三节文案）。

---

## 六、核对方法与复现命令（只读）

全部为静态检索，不连设备、不跑脚本：

```bash
# 1) 全仓 IP 扫描（排除手册提取件与留痕数据）
rg -n "192\.168\.\d+\.\d+" --glob '!**/*_output/**' --glob '!TEST_DATA/**'

# 2) 各类资源串形态（TCPIP / ASRL / USB）
rg -n "TCPIP0?::|ASRL\d+::|USB0::" --glob '!**/*_output/**'

# 3) server.py 解析层是否在位（回滚检测：无输出=已回滚）
rg -n "_resolve|DEVICE_KINDS|_CACHE_FILE|_remember_candidates" mcp_instruments/server.py
# 3b) 旧常量残留检测（应无输出）
rg -n "SDS_RES|SDG_RES|DMM_RES|DHO_RES|PSU_RES" mcp_instruments/server.py

# 4) 工具签名默认值核对（应全部为 None；41 处 = 28 专用工具 + 5 连接函数 + 辅助）
rg -n "resource: str \| None = None" mcp_instruments/server.py
rg -c "^@mcp\.tool\(\)" mcp_instruments/server.py        # 应仍为 31

# 5) 设备库无硬编码自检（应无输出）
rg -n "TCPIP0?::|192\.168\." --glob '*.py' common/ sds_control/ sdg_control/ dho_control/ keysight_3446x/ dh1766_control/src/ emoe_control/

# 6) find_* 签名核对（应无 hosts/cidr 默认值）
rg -n "def find_(sds|sdg|dho|dmm|dh1766|emoe)\(" -A8 common/ */*.py dh1766_control/src/

# 7) 测试脚本硬编码清单（本文 2.2 的复现）
rg -n "TCPIP0::192\.168\.|find_(\w+)\(hosts=\[|DEFAULT_IP|^\s*RES(OURCE)?\s*=" TEST_SCRIPTS/

# 8) 文档资源表核对
rg -n "设备与资源|当前设备与资源|实测资源|内置默认资源" *.md docs/*.md

# 9) 留痕统计（仅统计，不修改）
rg -c "192\.168\.31\." TEST_DATA/          # 当前：18 文件 / 71 处
rg -c "USB0::|ASRL\d" TEST_DATA/           # 当前：USB0 4 文件 / ASRL 7 文件
```

**改造验收标准（供第二阶段使用）**：
1. `rg "SDS_RES|SDG_RES|DMM_RES|DHO_RES|PSU_RES" mcp_instruments/server.py` → 无输出；
2. 文档 4 处资源表不再把 IP 写在"资源"列（或已带统一标注）；
3. `TEST_SCRIPTS/` 中前 10 优先级脚本不再出现 `TCPIP0::192.168.` 字面量；
4. 跑一次 `three_libs_smoke.py` + `libs_full_verify.py`，设备逐台按发现层定位成功（**需用户在场授权后执行**）。
