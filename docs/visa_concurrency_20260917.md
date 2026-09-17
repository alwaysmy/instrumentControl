# VISA 并发假设的实测论证（2026-09-17）

> 背景：本仓有两处设计建立在"VISA 并发怎么用才安全"的假设上，但一直只有零散现场经验
> （`identify_lan` 的注释："多线程各自 `ResourceManager()` 并发 open 会随机抛
> `VI_ERROR_INV_OBJECT`，且异常会从 `rm.close()` 里抛出、冲垮整轮扫描"），没有系统验证。
> 2026-09-17 两台仪器都在（**MHO984D over LAN** + **DG832 over USB-TMC**），逐条测掉。
>
> 脚本：`TEST_SCRIPTS/common/verify_visa_concurrency.py`（全程只读查询）
> 留痕：`TEST_DATA/common/visa_concurrency_20260917_*.json`

## 一、结论速览

| 假设 | 判定 | 证据 |
| --- | --- | --- |
| **H1** 共享单个 ResourceManager + 多线程访问**不同**设备 → 安全 | ✅ **成立** | 300 次并发查询（MHO+DG832）**0 错误**；墙钟 3.69s 与 MHO 单线程总耗时一致（真并行） |
| **H1b** 同一资源的并发会话数 | ⚠️ **有上限（≈15~16）** | 20 线程并发 open 同一资源：**15~16 成功**，其余 `VI_ERROR_ALLOC`（"Insufficient system resources"）或 `VI_ERROR_TMO`（三次运行均为 15~16/20） |
| **H2** 每线程各自 RM → 抛 `VI_ERROR_INV_OBJECT` | ❌ **未复现** | 8 线程各自 RM + 同资源：**8/8 成功**，`rm.close()` 无异常（该说法在本机/本版本不成立；真实风险见 H3/H4） |
| **H3** 同一设备两会话并行（LAN/VXI-11） | ❌ **不安全** | 两会话各 200 次：出现**串台**（`:CHANnel3:OFFSet?` 收到 IDN 响应）与 1–3 次 `VI_ERROR_TMO`；且**把设备 VXI-11 通道搞成粘滞错位**（见 §三） |
| **H4** 同一设备两会话并行（USB-TMC） | ❌ **明确不安全**（3 次复现） | 两会话各 200 次：**串台 100~115 次 + 超时 205~232 次**（约一半查询丢响应），并见 `VI_ERROR_RSRC_LOCKED` / `VI_ERROR_INP_PROT_VIOL` |
| **H5** 同一设备两会话但**串行化**（一把锁） | ✅ **成立** | 同 H4 的负载：**0 串台 / 0 错误**（这就是"单进程单 worker"设计的价值） |

**一句话**：并发访问**不同设备**没问题；并发访问**同一台设备**会**静默读错值**（不是超时，是拿到别人的答案），
USB-TMC 尤其严重；LAN 的 VXI-11 与 raw 两会话同样串台，且 VXI-11 会被搞成**不自愈**的错位。
（MHO 现按换协议恢复，`resolve("mho")` 已切到 raw socket；VXI-11 需设备侧重置 LAN 才能恢复。）

## 二、硬件/环境事实

- MHO984D `192.168.1.55`：VXI-11(`inst0`) 与 raw socket(`5555`) 两条通道；单次查询延迟 **≈25 ms**（VXI-11）。
- DG832 `USB0::0x1AB1::0x0643::DG8A265103205::INSTR`：USB-TMC 单管道；单次查询 **≈0.25 ms**。
- 期间 DG832 的 USBTMC 设备节点处于 PnP `Error` 状态导致 VISA 枚举不到 → 用
  `python common/usb_reset.py --kind dg --allow-reset --verify-idn` 复位恢复（约 3 秒，设定/输出未受影响）。

## 三、最有价值的发现：响应错位与"粘滞"

1. **串台形态**：会话 A 问 `:SOUR1:FREQ?`，会话 B 问 `*IDN?` → **A 收到了 IDN 字符串**。
   值本身"看着正常"（都是合法响应），只是**答非所问** —— 这类错误用"成功/失败"判断不出来。
2. **设备侧响应队列不绑定请求方**：并发风暴后，MHO 的 VXI-11 通道变成**稳定滞后一条**
   （`:CHANnel3:PROBe?` → `1.000000E0` 之后又拿到 IDN、`:OFFSet?` → `DC`…），
   而且**新进程、新会话、`clear()`、`*CLS` 都解不开**——10 分钟后仍是 0/3 对齐。
   同期 **raw socket(5555) 通道完全对齐（5/5）**，说明损坏限于 VXI-11 链路状态。
3. **触发条件**：两会话并发 + **超时未读**（`VI_ERROR_TMO` 之后那条响应没人取走）→ 队列错位。
4. **恢复手段**：① 换协议（VXI-11 ↔ raw socket，本仓既有做法，已实测 raw 通道可用且对齐）；
   ② 设备侧重置 LAN（Utility→I/O→LAN 关开）或重启示波器。
5. **护栏兜得住**：把地址指回错位通道后，MCP 工具的 `_verify_idn` 会拿到 `*IDN?='2.000000E+00'`
   → **拒绝操作**（`error_type=connection`，"地址校验失败"），**不会返回错值**。
   这是本次实验最让人放心的一条：错位在我们这条链路上表现为"工具报错"，而不是"给错数"。

## 四、对仓库设计的影响

| 设计/假设 | 本实验的结论 |
| --- | --- |
| 单进程单 worker 执行器（`_DeviceExecutor`） | **必要**：同一进程内的并发就是 H3/H4 的场景；H5 证明串行化能把错误率降到 0 |
| "多实例不互斥"这条警示（skill §五） | **升级为硬纪律**：多实例并发访问同一台仪器不是"互相干扰"，而是**互相读到对方的响应**（静默错值）；USB 设备还会连锁超时 |
| `identify_lan_all(workers=32)` 共享单 RM 并发扫**不同**主机 | **合理**（H1 成立）；注意两点：① 同一主机只由一个 worker 处理（`identify_lan` 内部按协议**顺序**试，不自并发 ✓）；② 单设备并发会话有 ≈16 的上限（H1b），32 个 worker 打同一台设备会 `VI_ERROR_ALLOC` |
| "每线程各自 RM 会崩"（对端现场说法） | **本机未复现**（8 线程 8/8 成功）——但**结论不变**：共享 RM 依然是更省资源、更易推理的写法；真正要防的是**同一设备的并发会话**，与 RM 怎么建无关 |
| raw socket（`5555`）作为 LAN 备选 | 可用，但**没有消息分帧**：大二进制块（截图 ≈97 KB）单次 `read_raw` 只拿到 6 字节 → 已加 `VisaClient.query_block()`（按 TMC 头长度循环读满）并在 `screenshot()` 使用 |

## 五、遗留建议（未实施）

1. **跨进程咨询锁**：`%LOCALAPPDATA%\instrumentControl\session_locks\<kind>.json`（写 pid+时间戳），
   工具调用前发现"另一活跃进程正在用同一资源"就**加一条 warning**（不硬拦）。
   本机实测曾同时存在 14 个 instrument MCP 实例，这条能显著降低 H3/H4 的发生概率。
2. **测试脚本纪律**：本文件的实验脚本默认只跑"安全子集"（T0/T1/T1b/T2b/T4/T5），
   LAN 两会话（T3）改为 `--lan-two-session` 显式开启——它**会**把设备 VXI-11 链路搞坏（本次实测代价）。

## 六、跨进程**会话咨询锁**（2026-09-17 实施）

动机：本机实测曾同时存在 **14 个** instrument MCP 实例；单进程内已有单 worker 串行化，
但**跨进程不互斥**——正是 H3/H4 的场景。做法（`common/session_lock.py`）：

- 每次设备工具调用刷新自己的锁文件 `<配置目录>/session_locks/<地址>_<哈希>__<PID>.json`；
- **判重键 = VISA 地址**（用户指定口径）：同地址的活跃进程 → 返回体加 `warnings`
  （"实测同一设备两会话并发会**响应串台**…"）；**只告警不阻塞**；
- 同一台设备的**另一接口**（inst0 vs 5555 等，按 host/VID:PID:SN 归并）→ 单独一条
  "**跨接口并发是否安全尚未验证**"的告警，**不参与判重**；
- 活跃判据 = PID 存在（Windows 用 `OpenProcess` 探活——**绝不能用 `os.kill(pid,0)`**，
  那在 Windows 上等于 `TerminateProcess`）**且** 时间戳新鲜（TTL 180s）；过期/死进程的锁自动清理。

回归：`TEST_SCRIPTS/common/verify_session_lock.py`（离线 15 项，含"同地址两进程文件名不同也能
互相看见"这条踩坑回归）+ `verify_session_lock_live.py`（实机：A 在用时 B 拿到告警、A 退出后
告警消失，DG832 实测全 PASS）。

## 七、本次实验的代价与善后（如实记录）

- 并发风暴（20 线程并发 open 同一资源）**会污染仪器响应流**：MHO 的 VXI-11 先被打成
  稳定滞后一条（`clear()`/新进程都解不开），随后 **raw 通道也被打成持续错位**
  （实验后实测 **0/20 对齐**：`:ACQUIRE:TYPE?` 回 IDN、`:SRATe?` 回 `NORM`…）。
  → **需在面板上重置一次 LAN（Utility→I/O→LAN 关开）或重启示波器**才能恢复；
  处置建议已写进 skill。
  为此实验脚本已把"同资源并发"（T1b/T2b）与"LAN 两会话"（T3）都改成**显式开启**
  （`--same-res-storm` / `--lan-two-session`），默认只跑安全子集，并在结尾做对齐核查。
- 顺带把这类"莫名解析错"变成**可执行的诊断**：
  `RigolScope._float()`（数值项拿到非数值响应 → 报"响应错位 + 处置建议"）、
  `RigolScope.align_session()`（用 `*IDN?` 判对齐并尝试排干）。
- DG832 的 USBTMC 节点当日**两次**掉进 PnP `Error`（VISA 枚举不到）——
  两次都用 `common/usb_reset.py --kind dg --allow-reset --verify-idn` 秒级恢复；
  该 USB 节点的稳定性本身值得留意（硬件/驱动层面）。
