# AI 仪器控制工具 — 使用与安全手册

日期：2026-08-23
最近更新：2026-09-13（文档漂移审计修正，见 `docs/doc_drift_audit_20260913.md`）
适用：instrumentControl 全部设备库（AI/Agent 操作场景）

## 一、设备清单与连接

| 设备 | 库 | 发现函数 | 地址解析（kind） |
|---|---|---|---|
| DH1766A-1 电源 | dh1766_control | find_dh1766() | `resolve("psu")` |
| RIGOL DHO924S | dho_control | find_dho() | `resolve("dho")` |
| Siglent SDS824X HD | sds_control | find_sds() | `resolve("sds")` |
| Siglent SDG2122X | sdg_control | find_sdg() | `resolve("sdg")` |
| Keysight 34465A | keysight_3446x | find_dmm() | `resolve("dmm")` |

> **不列具体地址**：仪器 IP 随 DHCP/换网段变化、USB 换口换资源串、ASRL 编号漂移，
> 写死地址换环境即失效（严重时连到同网段其他设备并对它下发 SCPI）。
> 地址一律运行时解析：`common.resolve(kind)` 依次取
> **显式入参 → 环境变量 `INSTRUMENT_<KIND>_RES` → 用户配置 `devices.json`
> → 上次成功缓存 → 自动发现**（实现在 `common/resolver.py`，
> MCP 专用工具的 `resource` 参数同理可省略）。

统一发现入口 `common.find_device(idn_contains, resource, hosts, allow_scan, cidr)`：
显式 resource → hosts 自动选协议 → VISA 列表 → CIDR 网段扫描（默认关，
最后手段）；LAN 未注册设备先跑 `instr_discover`，其发现结果会自动回写地址缓存。

## 一.五、USB-TMC 卡死的恢复（真机实测 2026-09-15）

USB 仪器偶发"设备在但会话卡死"（`*IDN?` 超时 / `VI_ERROR_TMO` / `VI_ERROR_SYSTEM_ERROR`）。
按此顺序处理，**不要一上来就给人拔电**：

1. **重连一次**——多数情况即恢复（DG832 实测遇过一次，重连后正常）；
2. 仍不行 → **重启该 USB 的 PnP 设备**（USB 重新枚举，仪器固件不重启、**设定不丢**）：

   ```bash
   python common/usb_reset.py --kind dg --dry-run          # 免权限：只看要做什么
   python common/usb_reset.py --kind dg --allow-reset --verify-idn
   ```

   实测 **2.4 秒**恢复，CH1/CH2 的波形/频率/幅度/偏移/输出/保护 100% 保留
   （留痕 `TEST_DATA/dg832/usb_pnp_reset_verify_20260915.json`）。
   改设备节点需**管理员权限**（弹 UAC）：非管理员环境加 `--escalate`，或按提示在
   管理员终端手动跑 `pnputil /restart-device "<实例ID>"`；
3. 还不行才拔插 USB / 换口 / 仪器断电。

## 二、AI 安全操作规范（必须遵守）

1. **禁止复位类命令**：`*RST`、`:SYST:RESet`、`:SYST:FACT`（已从库中移除）、
   DMM `*RCL/*SAV` 覆写——自动化一律不调用；
2. **写操作三步**：写入 → 查 SYST:ERR? → 回读比对；
3. **写序列前 drain 错误队列**（`sds_control.sds.drain_errors`），滞后报错会污染判定；
4. **输出/信号类操作需显式授权场景**：SDG 输出开关、电源输出开关；
5. **结束恢复**：测试脚本必须 try/finally 恢复被改设定并关闭输出；
6. **留痕**：所有实测输出 JSON 到 TEST_DATA/<device>/，时间戳命名；
7. **输出开关必须声明当前状态**（仅校验不设置，不符立即拒绝并回传实际值）：
   SDG `set_output(ch, on, expect_load)`（expect_load 必填：HZ/50）、
   电源 `set_output(ch, state, expect_mode)`（expect_mode 必填：NORM/TRAC/SERI/PARA）；
8. **禁止远程锁定类命令**：`SYSTem:REMote ON`（SDS 会禁用触摸屏/面板按键）及
   `SYST:REM`/`SYST:LOCK` 类——妨碍现场人工操作；MCP `instr_write` 已黑名单拦截，
   查询 `SYST:REM?` 保留（诊断用）。DH1766 的远程模式语义不同，见下文 dh1766 节。

## 三、各库核心 API

### sds_control（示波器）
```python
with SDS(resource) as scope:
    scope.auto_scale(4)                    # 修触发+自动定标（推荐第一步）
    vpp = scope.measure_simple("PKPK", "C4")   # SIMPLE 模式单通道测量
    ph = scope.measure_phase("C2", "C1")       # ADVanced 双通道相位（度）
    wf = scope.get_waveform(4, points=50000)   # 波形：电压 + 时间轴（DESC 解析正确）
    png = scope.screenshot_png(path)       # 截图供视觉判断
```
测量项枚举 MEAS_TYPES：PKPK/MAX/MIN/RMS/FREQ/PER/PWID/DUTY...（SDS 缩写表）；
双通道枚举 MEAS_DUAL_TYPES：PHA/SKEW/FRR/FRF/FFR/FFF...

关键教训（固件特性）：
- `MEASure:MODE` 默认 ADVANCED，SIMPLE 组失效；measure_simple 自动切换
- 命令用短形式（ACQ:MDEP? 通，`:ACQuire:MDEPth?` 超时）
- 响应带回显头+单位后缀，query() 已自动剥离
- ADVanced P 槽 VALue? 出值三前提（缺一即 `****`）：槽已 `Pn ON`、
  `MODE=ADVanced`、两通道完整周期在屏内——此前"恒 ****"结论已推翻，
  真因是库从未开槽（2026-09-08 实测 PHA 正常出值）
- 双通道相位 `measure_phase(src_a, src_b)`：PHA = B 相对 A 的相位（度，
  实测交换 A/B 得互补角）；未知命令查询无响应会超时（如 PAVA?/MEAS:FREQ?），
  未知写入可能被静默吞掉（MEAD），一律先 drain 再逐条查错
- 波形读取 `get_waveform(ch, points)`：DESC 解析**正确**（2026-09-09 澄清）——
  interval 与 `ACQ:SRAT?` 一致、FFT 主频与设备硬件测量吻合；此前"DESC 布局不符/读出全零"
  是误判（无信号时读取 + 用朴素过零计数验证调幅信号，详见 AGENTS.md §五）。
  `sds_get_waveform` 已暴露为 MCP 工具；分析频率用 FFT/自相关
- 触发源挂空/电平过高 = 屏幕无波形的头号根因

### 示波器调试标准流程（先读后写，截图辅助）

```
1. 读配置（不猜）
   scope.diagnose_trigger()   # 触发源/电平/模式/状态/时基
   scope.snapshot()           # 通道开关/档位/耦合/采集参数
2. 对照信号判断配置错误
   常见坑：触发源挂空通道、电平在信号幅值外、NORMal 遇无规则信号、
   通道未开、档位与量级不匹配（超屏读数被钳制）
3. 修正（auto_scale 一键完成）
   触发源→目标通道 → 模式 AUTO → 电平→信号中点 → 通道开启 → 定标
4. 截图验证（唯一物理真相）
   scope.screenshot_png(path)   # PNG 可直接读图（2026-09-09 修 alpha=0 全透明问题）
   # 无视觉能力时用 analyze_screen() 像素分析兜底
```

### auto_scale 两条路径（多信号场景必读）

```python
scope.auto_scale(4)                     # 默认：SCPI 闭环，只动 C4
scope.auto_scale(4, use_autoset=True)   # 显式：:AUToset 一步定标
```

| 路径 | 矩阵成绩 | 特点 |
|---|---|---|
| SCPI 闭环（默认）| 13/17 | **只动目标通道**，多信号场景安全；边界：1MHz、SQUARE@1k、带偏置细调残差 |
| AUToset（显式）| 16/17 | 全局破坏性：**重置所有通道档位/时基/触发** |

**use_autoset=True 的启用前置**（调用方主动判断，缺一不可）：
1. 信号类型简单且周期性（WVTP 是自己设的，可直接判断；NOISE/调制不适用）
2. 没有其他已调好的通道（AUToset 会毁掉它们）

**多信号推荐流程**：逐通道 `auto_scale(n)`（SCPI 闭环）→ 全部就位；
某通道 SCPI 失败且满足前置 → 才 `use_autoset=True` 重来（其他通道需重调）。

实测案例：测量全 `****` → 截图发现触发源=C1 电平 12.2V 而信号在 C4 →
切触发源+电平归零后立即恢复。

### sdg_control（信号源）
```python
gen.set_basic_wave(2, WVTP="SINE", FRQ="1000HZ", AMP="2V", OFST="0V")
gen.set_output(2, True, "HZ")   # ⚠ 真实信号输出；expect_load 必填（HZ/50，仅校验）
cfg = gen.basic_wave(2)   # 整体查询
```

### keysight_3446x（万用表）
```python
v = dmm.measure("volt_dc")          # 10 种函数
dmm.configure("volt_dc", range_v=0.1)
nplc = dmm.get_nplc()
```
注意 `:CONF?` 回读滞后一拍（锁存上轮配置），以实测值为准。
语法为冒号嵌套 `:CONF:VOLT:DC`（空格分隔会 -102）。

### mho_control（RIGOL MHO900 系列示波器）
```python
with MHO(resolve("mho")) as scope:
    print(scope.idn())                                  # RIGOL TECHNOLOGIES,MHO984D,…
    vpp = scope.measure_item("VPP", 1)                  # 单信源测量（手册 3.17.2 表）
    ph  = scope.measure_item("RRPHase", 1, 2)           # 双信源相位/延迟（给两个通道）
    wf  = scope.get_waveform(1, points=1000)            # NORMal 屏幕波形（1~1000 点）
    raw = scope.get_waveform(1, mode="RAW", points=50000)  # 内存波形：需先 scope.stop()
    png = scope.screenshot_png(Path("shot.png"))        # 原生 PNG，可直接读图
```

实测要点（MHO984D / 固件 00.01.00，留痕 `TEST_DATA/mho/verify_mho_*.json`）：
- **命令集与 DHO800/900 不同**：清测量 `:MEASure:DELete`（DHO 是 `:MEASure:CLEar`）、
  边沿第三态 `RFALl`（DHO 是 `RFail`）、面板锁定 `:SYSTem:LOCKed`；**无 `*OPT?`**（超时）。
- 采样率随通道数下降：1~2ch 4GSa/s、3~4ch 1GSa/s（`snapshot()['sample_rate_hz']`）；
  带宽同样分档（MHO984 1~2ch 800MHz、3~4ch 400MHz）。
- `:WAVeform:POINts` 上限**随模式变**：NORMal 1~1000；RAW 1~最大存储深度（本机 100Mpts）。
  RAW 必须 STOP 态读（库内直接报错，不做隐式 STOP）；`:WAVeform:STARt/STOP` 是 **1 起始**索引。
- 波形 ASCII 格式**不带 TMC 头**（二进制格式带）；WORD 字节序手册未记载，
  实测低字节在前（冻结态 BYTE/WORD Vpp 差 0.2%，见验收脚本 §6）。
- 无效测量统一返回 `9.9E37` 哨兵，库内转成 ValueError（文案含原值）。
- 截屏 `:DISPlay:DATA? PNG` 直接回 PNG 位图流，**没有** SDS 那种 BMP alpha=0 问题。

### rigol_scope（DHO800/900 与 MHO900 共享内核，2026-09-15 合并）

两系列命令集 97% 重合（DHO 驱动原有 40 条命令 100% 存在于 MHO 手册），故合并为
**一套实现 + 一张家族差异表**：`rigol_scope/scope.py`（通用实现）、
`rigol_scope/families.py`（差异值）。`dho_control.DHO` / `mho_control.MHO` 只是薄封装，
公开 API 未变。比对证据：`docs/rigol_scope_compare_20260915.md`。

**合并带来的能力补齐（DHO 侧）**：双信源相位/延迟测量（`measure_item("RRPHase", 1, 2)`，
DHO 手册同样记载）、波形分片读取、points/RAW 前置校验、原生 PNG 截图；
并修掉 DHO 旧实现的 ASCII 死分支（此前 `fmt="ASCii"` 恒抛异常）。

**复位族不在公开 API 里**（AGENTS.md 禁发命令）：`:SYSTem:RESet` 是**重启**、
`*RST` 才是**恢复出厂**（两系列手册一致；旧 dho.py 注释写反过）。常量保留在
`commands.py` 供查语义，真要执行走 `TEST_SCRIPTS/common/rigol_scope_reset.py --allow-reset`
（`--info` 可随时只查看说明）。

**家族差异（改代码时唯一要查的地方）**：清测量 `:MEASure:CLEar`(DHO)/`:MEASure:DELete`(MHO)、
采集第四态 `ULTRa`(DHO)/`HRESolution`(MHO)、`:ACQuire:BITS` 与 `:CHANnel<n>:Impedance` 仅 MHO。
边沿第三态两系列**都是** `RFALl`（`RFail` 是旧 docstring 笔误）。

⚠ **读波形的格式选择**：`fmt="BYTE"` 是 8bit，2V/div 下每码 68mV——小信号只有几个码值，
**量值必须用 `WORD`**（0.27mV/码）；BYTE 只适合看形态/粗略幅度。
（DHO 合并后尚未在真机复验——本实验台当前无 DHO；离线闭环见
`TEST_SCRIPTS/common/verify_rigol_scope_shared.py`，真机补验清单见该文件头部。）

### dg832_control（RIGOL DG800 系列信号源）
```python
from dg832_control import DG832
with DG832() as gen:                     # 资源串缺省 = 自动发现（USB-TMC）
    gen.set_voltage_limit(1, high=3.3, low=-3.3, state=True)   # ① 保护先行（强制）
    gen.set_wave(1, "sine", freq=1000, amp=2.0, offset=0.0)    # ② 设波形
    gen.output(1, True)                                        # ③ 开输出
    gen.set_freq(1, 2000)                                      # 单参数（回读 {"value","note"}）
    gen.set_voltage_limit(1, state=False)                      # 收尾按需关保护
```

实测要点（DG832 / 固件 00.02.06.00.01，留痕 `TEST_DATA/dg832/verify_dg832_*.json`）：
- **保护联锁（本库独有）**：设 amp/offset 或开输出前必须已开有效保护，否则 `protect_required`；
  越界 `protect_range`——把"防超压"做进代码而不是靠人记。
- 省略参数 = **保持当前值**（库先读 `APPL?` 填充）；SCPI 裸发 `DEF` 会重置为该波形默认值。
- `:OUTP{n}:LOAD?` 高阻返回 `9.9E+37`（不是 INF 文本）；写回时用 `INF`。
- 波形频率上限低于型号上限：DG832 sine 35MHz / square·pulse 10MHz / ramp 1MHz / harmonic 15MHz。
- 扫频边界命令是 `FREQ:STAR/STOP`（**没有** `SWE:STAR/STOP`）；扫频关闭时写边界会被拒（-220）。
- 驱动前提：**完整版 NI-VISA ≥ 24.x**；Ultra Sigma 自带旧版 IVA visa 3.2 会导致 USB-TMC
  第二条命令后卡死（已实测）。多会话共用同一 USB 设备时跨进程无锁，操作前先读基线。

### dho_control / dh1766_control
见各自 docstring 与 EXPERIENCE.md。
DHO 读/写/波形读取已实测留痕（2026-08-24）：`TEST_DATA/dho/dho_first_verify_*.json`
（*IDN? / snapshot / get_waveform CH1）、`dho_write_verify_*.json`（通道/时基/触发写入+恢复比对，
其中 CH2 SCALe 被拒属预期——RIGOL 未开启通道写 SCALe 报 -200，先 `DISPlay ON`）。
原"DHO924S 全功能验证待设备空闲"——**已过时**（2026-09-13 更新）。

DH1766 远程模式（2026-09-13 实测，固件 V0.1.4.3）：
- **任何远程会话都会把电源置为 REM（远程模式）**：新建会话的第一条命令查询
  `SYST:COMM:RLST?` 即返回 `REM`（即用户观察到的"一连就进远程模式/疑似被锁"）；
- 手册写法 `SYST:COMM:RLST:STAT?` 在本机**无响应（超时）**——此前文档记的"返回空串"不准确；
- 发 `SYST:LOC` 后立即回到 `LOC`，把面板控制权交还现场（**不影响输出/设定**）；
  MCP 的 DH1766 工具每次调用收尾自动补发一次（`server.py::_psu_close`）；
- **REM（远程模式）与手册的"锁定 RWL"是两个概念**：RWL 才是面板 Lock 键不可切回、
  需 `SYST:LOC` 恢复的远程锁定；REM 只是外控会话状态。
- 留痕：`TEST_SCRIPTS/dh1766/psu_remote_lock_probe.py` +
  `TEST_DATA/dh1766/psu_lock_probe_20260913_*.json`。

## 四、跨设备闭环范例

TEST_SCRIPTS/common/waveform_matrix.py：SDG CH2→SDS C4，
11 case（波形×频率×幅度×偏置）生成→auto_scale→测量断言，10/11 PASS
（NOISE 为物理豁免）。接线：SDG CH2 BNC → SDS CH4 BNC。

## 五、已知问题/待办

1. SDS800X HD 波形读取 DESC 结构布局与手册示例不符（读出全零），待专研该型号布局；
   ——（2026-09-13 已更新：**此判断已推翻**。DESC 解析正确，原"读出全零"源于①无信号时读取、
   ②用朴素过零计数验证调幅信号；FFT 交叉验证通过，`get_waveform` 已暴露为 MCP 工具
   `sds_get_waveform`，详见 AGENTS.md §五）
2. NOISE 波形无稳定 Vpp/Freq，属物理特性；
3. DHO924S 全功能验证待空闲；
   ——（2026-09-13 已更新：**已完成**。2026-08-24 留痕 `TEST_DATA/dho/dho_first_verify_*.json`、
   `dho_write_verify_*.json`、`dho_ch1_wave_*.csv`，覆盖 *IDN?/snapshot/波形读取与通道·时基·
   触发写入+恢复比对）
4. dg832 skill/scripts 双副本同步问题。

## 六、审计与防回归

- 命令审计器：TEST_SCRIPTS/common/audit_all_commands.py（84 条命令 vs 手册）
- 审计报告：docs/command_audit_20260823.md（零猜测命令结论）
- 冒烟：test_discovery.py(T1~T5)、three_libs_smoke.py、libs_full_verify.py
