# 实测记录（从 README 迁出的时间线）

> 本文保存 instrumentControl 的逐轮实测留痕与结论，按时间倒序/正序累积。
> README 只保留项目定位与用法，**测试/实测细节一律记在这里**。
> 新记录追加到文末，格式：`- YYYY-MM-DD：结论（证据文件路径）`。

- 2026-08-17：DH1766A-1 识别为 `USB0::0x0957::0xA007::100260004670::INSTR`，
  `*IDN?` = `BJDH,DH1766A-1,0,V0.1.4.3`；三路读回电压/电流正常，输出开关命令验证通过。
  注：该设备 VID=0x0957（Keysight ID），为国产仪器兼容 VISA 驱动常见做法，以 `*IDN?` 为准。
- 2026-08-17：手册 4.2 全部指令集 40/40 读写验证通过（`test_dh1766_full.py`，留痕见
  `TEST_DATA/dh1766/dh1766_full_*.json`）。全部写操作备份-恢复，设备设定与测试前一致。
  实测发现的固件差异（V0.1.4.3 vs 手册基于的 V0.1.2.8）见 `dh1766_control/docs/EXPERIENCE.md`。
- 2026-08-17：`dh1766_control` 库建立（src 布局，pip 可安装），DH1766 系列完整手册
  （43 页）经 read-pdf 提取归档至 `dh1766_control/docs/`，供后续查阅核对。
- 2026-08-23：`common/` 统一发现层上线（`find_device`：显式 resource → hosts 自动选协议 →
  已有资源列表 → CIDR 网段扫描，`--allow-scan` 默认关）。实测要点：纯 VISA 扫 /24 需 510s，
  加 TCP 端口预筛(111/4880/5025/5555) 后 ~8s；DH1766A-1 经网线可达
  `TCPIP0::192.168.31.144::5025::SOCKET`（raw socket 会话必须配 `\n` 终止符）；
  RIGOL DHO924S 示波器可达 `TCPIP0::192.168.31.146::5555::SOCKET`（Rigol SCPI raw 口）。
  带载(CH1 ON 12V/0.31A)下显式 LAN 直连读取正常，CH1 保持 ON 未做开关动作。留痕见
  `TEST_DATA/common/discovery_smoke_*.json` 与 `TEST_SCRIPTS/common/test_discovery.py`
  （T1~T5 全 PASS，扫描同时识别电源+示波器且 IDN 过滤不误配）。
- 2026-08-23：全网段探测（`TEST_SCRIPTS/common/probe_all.py`）新发现三台在线仪器：
  Keysight 34465A 万用表(`.123`，VXI-11)、Siglent SDG2122X 信号源(`.206`，VXI-11)、
  Siglent SDS824X HD 示波器(`.220`，VXI-11)。`dho_control` 库建立（DHO800/DHO900 系列
  通用，波形 BYTE/WORD TMC 解析 + 电压换算 `(raw-YORigin-YREFerence)*YINCrement`），
  手册提取至 `dho_control/docs/DHO800编程手册_output/`（418 页），hosts 直连验证通过。
- 2026-08-23：三台新设备库完成（均含手册提取 + 只读冒烟实测）：
  `sds_control`（SDS800X HD 系列，495 页手册，波形 PREamble 二进制协议+分片读取+电压换算
  raw/code*vdiv-offset）、`sdg_control`（SDG2000X 系列，175 页 PG，BSWV 整查/键值写）、
  `keysight_3446x`（Truevolt 583 页手册已下载提取，CONF/MEAS/NPLC/DATA:LAST）。
  实测要点：SDS 全拼命令 ":ACQuire:MDEPth?" 不响应必须短形式 "ACQ:MDEP?"；SDS 响应带单位
  后缀需剥离；SDS 查询回显头按前缀智能剥离；34465A DATA:LAST? 带 "VDC" 后缀。
  留痕：TEST_DATA/common/three_libs_smoke_*.json。DHO924S 待设备空闲后做全功能验证。
  （2026-09-13 回填：DHO 全功能验证已于 2026-08-24 完成——留痕
  `TEST_DATA/dho/dho_first_verify_20260824_112452.json`（*IDN?/snapshot/波形 CH1）与
  `dho_write_verify_20260824_112935.json`（通道/时基/触发写入+恢复比对）。）
- 2026-08-25：`mcp_instruments/` MCP 服务器上线：五台仪器 17 工具统一暴露（无状态
  连接→操作→关闭 + 全局锁串行化；复位类零暴露，关机/开输出 confirm=True 安全门；
  错误统一 `{ok, error_type, error}` 四分类）。已注册 zcode 用户级 config
  （`~/.zcode/cli/config.json` 的 `instruments`，新会话生效；使用指引 skill：instrument-mcp）。
- 2026-08-26：`instr_discover` v3（串口探测：占用提示/空闲 IDN 后断开/驱动挂起 6s 硬超时；
  VISA 先于 LAN 隔离代理干扰；fake-IP 网段污染降级 warning），实测发现串口新设备
  EmoeCalibrator（ASRL31），建 `emoe_control` 骨架库（仅发现 + `*IDN?`，编程手册未提供）。
- 2026-08-26/09-01：三轮审查修复（整体代码审查 17 项、MCP 专项、DH1766 远控文档建议：
  `find_dh1766` 上次成功地址缓存（自 2026-09-13 起写在用户级缓存目录
  `%LOCALAPPDATA%\instrumentControl\last_good_resource.json`，不再落包源码树）、
  `power_cycle` 高层 API——后者未暴露 MCP）。
- 2026-09-03：MCP 增至 19 工具（**注：2026-09-13 已增至 31 = 28 专用 + 3 通用护栏，
  见 `mcp_instruments/README.md`**）：新增 `instr_query`/`instr_write` 通用护栏（新设备零代码
  接入——复位类黑名单 forbidden、通用写 confirm=True、写前 drain/写后 SYST:ERR?/自动
  回读、审计落盘 `TEST_DATA/common/mcp_scpi_audit_*.jsonl`、离线资源硬超时看门狗）。
  实测修复三缺陷：(a) `mcp.run()` 事件循环与后台线程 import pyvisa 死锁（冷进程首个
  设备调用永久冻结）→ 重依赖 import 移主线程（<1s）；(b) `instr_discover` LAN 分支
  `probe_alive`/`identify_lan` 未导入 NameError（存量 bug）→ 补导入+LAN 异常降级；
  (c) 串口探测每线程各建 RM 原生崩溃（8 串口实测）→ 共享单例 RM。真机验证：SDG 整查/
  等值写三步闭环（状态零变更）、串口新设备发现并零接入识别 EmoeR&D ADS127L11-DAQ-EV
  （ASRL5；校准器 ASRL31 已离线/换号，串口号会漂移，接入先 `instr_discover` 重定位）。
- 2026-09-13：**DH1766 远程模式核实**（用户报告"一连就被锁"）：
  `SYST:COMM:RLST:STAT?`（手册写法）在本机 V0.1.4.3 **无响应**（超时，此前文档误记"空串"）；
  正确查询 `SYST:COMM:RLST?` 实测**每次新建远程会话的第一条命令即返回 `REM`**
  ——即"只要远程连接就进入远程模式"成立；发 `SYST:LOC` 后立即回到 `LOC`（面板控制权可交还，
  不影响输出/设定）。同时实测该机处于 **TRAC 跟踪模式**（CH1 +11.99V / CH2 −11.99V，
  CH1 0.39A 带载）——跟踪负压是正常跟随，非故障。
  留痕：`TEST_SCRIPTS/dh1766/psu_remote_lock_probe.py` +
  `TEST_DATA/dh1766/psu_lock_probe_20260913_*.json`；
  代码修正：`commands.py::SYST_RLST`、`dh1766.py::rlstate()`、MCP `_psu_close`（收尾发 `SYST:LOC`）。
  现场复原：探测结束后已 `*CLS` 清空自造错误队列、`SYST:LOC` 归还面板；
  输出状态与设定值与探测前一致（`APPL:OUTP?`=`1,1,0`，12/12/5V，1.5/1.5/1.5A）——**零改动**。
- 2026-09-13（同日，维护轮）：安全与工程收口——
  ① 黑名单补齐 `SYST:RWL` / `:SYST:COMM:RLST`（原正则只覆盖 `REM/REMOTE/LOCK`，
  DH1766 锁定命令会漏放），并改为"**纯查询放行、写一律拦**"；
  回归 `TEST_SCRIPTS/common/verify_remote_lock_block.py` 24/24 PASS（离线）；
  ② 测试脚本铁律修复：`test_dh1766_read.py`（try/finally + 带电跳过演示）、
  `test_dho_write.py`（恢复动作移入 finally）、`test_sds_shutdown.py`（加 `--yes` 门槛）；
  ③ `last_good_resource.json` 迁出包源码树 → `%LOCALAPPDATA%\instrumentControl\`；
  ④ `.gitignore` 收口 MCP 运行期产物（波形 CSV 332MB / 截屏 PNG / 审计 jsonl / 旧 BMP）；
  ⑤ README 瘦身（实测时间线移入本文件）+ 文档漂移专项审计
  （报告：`docs/doc_drift_audit_20260913.md`，修正 8 份文档）。
