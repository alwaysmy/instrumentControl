# AI 仪器控制工具 — 使用与安全手册

日期：2026-08-23
适用：instrumentControl 全部设备库（AI/Agent 操作场景）

## 一、设备清单与连接

| 设备 | 库 | 发现函数 | 实测资源 |
|---|---|---|---|
| DH1766A-1 电源 | dh1766_control | find_dh1766() | USB 或 TCPIP0::192.168.31.144::5025::SOCKET |
| RIGOL DHO924S | dho_control | find_dho() | TCPIP0::192.168.31.146::5555::SOCKET |
| Siglent SDS824X HD | sds_control | find_sds() | VXI-11 inst0 |
| Siglent SDG2122X | sdg_control | find_sdg() | VXI-11 inst0 |
| Keysight 34465A | keysight_3446x | find_dmm() | VXI-11 inst0 |

统一发现入口 `common.find_device(idn_contains, resource, hosts, allow_scan, cidr)`：
显式 resource → hosts 自动选协议 → VISA 列表 → CIDR 网段扫描（默认关）。

## 二、AI 安全操作规范（必须遵守）

1. **禁止复位类命令**：`*RST`、`:SYST:RESet`、`:SYST:FACT`（已从库中移除）、
   DMM `*RCL/*SAV` 覆写——自动化一律不调用；
2. **写操作三步**：写入 → 查 SYST:ERR? → 回读比对；
3. **写序列前 drain 错误队列**（`sds_control.sds.drain_errors`），滞后报错会污染判定；
4. **输出/信号类操作需显式授权场景**：SDG 输出开关、电源输出开关；
5. **结束恢复**：测试脚本必须 try/finally 恢复被改设定并关闭输出；
6. **留痕**：所有实测输出 JSON 到 TEST_DATA/<device>/，时间戳命名。

## 三、各库核心 API

### sds_control（示波器）
```python
with SDS(resource) as scope:
    scope.auto_scale(4)                    # 修触发+自动定标（推荐第一步）
    vpp = scope.measure_simple("PKPK", "C4")   # SIMPLE 模式测量
    wf = ...                               # 波形读取（DESC 布局待专研）
    png = scope.screenshot_png(path)       # 截图供视觉判断
```
测量项枚举 MEAS_TYPES：PKPK/MAX/MIN/RMS/FREQ/PER/PWID/DUTY...（SDS 缩写表）

关键教训（固件特性）：
- `MEASure:MODE` 默认 ADVANCED，SIMPLE 组失效；measure_simple 自动切换
- 命令用短形式（ACQ:MDEP? 通，:ACQuire:MDEPth? 超时）
- 响应带回显头+单位后缀，query() 已自动剥离
- ADVANCED P 槽 VALue? 恒 '****'（疑似选件），勿用
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
   scope.screenshot_png(path)   # 超屏时设备测量值被钳制，像素不骗人
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
gen.set_output(2, True)   # ⚠ 真实信号输出
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

### dho_control / dh1766_control
见各自 docstring 与 EXPERIENCE.md。DHO 全功能验证待设备空闲。

## 四、跨设备闭环范例

TEST_SCRIPTS/common/waveform_matrix.py：SDG CH2→SDS C4，
11 case（波形×频率×幅度×偏置）生成→auto_scale→测量断言，10/11 PASS
（NOISE 为物理豁免）。接线：SDG CH2 BNC → SDS CH4 BNC。

## 五、已知问题/待办

1. SDS800X HD 波形读取 DESC 结构布局与手册示例不符（读出全零），待专研该型号布局；
2. NOISE 波形无稳定 Vpp/Freq，属物理特性；
3. DHO924S 全功能验证待空闲；
4. dg832 skill/scripts 双副本同步问题。

## 六、审计与防回归

- 命令审计器：TEST_SCRIPTS/common/audit_all_commands.py（84 条命令 vs 手册）
- 审计报告：docs/command_audit_20260823.md（零猜测命令结论）
- 冒烟：test_discovery.py(T1~T5)、three_libs_smoke.py、libs_full_verify.py
