# instrumentControl — Agent 工作规范

仪器控制集合项目：VISA/SCPI 统一发现层（common/）+ 按设备分库
（dh1766_control / dho_control / sds_control / sdg_control / keysight_3446x /
emoe_control / dg832-control）+ MCP 统一暴露（mcp_instruments/）。
AI/Agent 操作仪器必须遵守以下规范。

## 一、SCPI 客户端铁律（实测教训，违反必踩坑）

1. **命令禁止猜测**：落码前必须对照设备手册（各库 docs/ 下有提取版）核对语法。
   历史事故：`:CONF VOLT:DC`（应为 `:CONF:VOLT:DC`）积压 12 条错误；
   `:SYST:FACT`（不存在）已删除；SDS `ITEM` 漏 `,ON` 参数。
2. **写序列前先 drain 错误队列**：错误队列 FIFO 滞后报错会污染逐命令查错
   （`sds_control.sds.drain_errors`）。写后逐条查 `SYST:ERR?`。
3. **写操作三步**：写入 → 查 SYST:ERR? → 回读比对。缺一不可。
4. **查询无副作用**（SCPI-99 §6.2.3）：例外仅 MEASurement 子系统。
5. **字符查询返回短格式**（§6.2.3）：设 `CHANnel1` 查回 `CHAN1`；解析响应要兼容。
6. **布尔查询返回 0/1**（§7.3），不是 ON/OFF。
7. **设值后必须回读验证**（§7.2）：仪器可舍入参数（如 12.1 → 12.099998，
   比较必须用容差，禁止 `==`）。
8. **耦合参数同一消息连续发送**（§编程提示#3），分开发送产生非预期中间态。
9. **响应形态因厂而异**，客户端必须兼容：
   - 回显头：SDS 查询响应带命令头（`C1:VDIV 5.00E+00V`）
   - 单位后缀：`2.00E-03S` / `5.00E+00V` / `VDC`
   - 短格式：`CHAN1` / `NORM` / `SINC`
   - 钳制假值：**示波器信号超屏时 MAX/MIN/PKPK 读数被钳制在屏界，不可信**——
     削顶/居中判断用截图像素（`sds_control` analyze_screen），不用设备测量
10. **命令形式因厂而异**：SDS 只吃短形式（`ACQ:MDEP?` 通、`:ACQuire:MDEPth?` 超时）；
    Keysight 冒号嵌套（`:CONF:VOLT:DC`）；Siglent SDG 参数键值对（`C1:BSWV WVTP,SINE`）。
11. **测量模式开关**：SDS `MEASure:MODE` 默认 ADVANCED，SIMPLE 组整体失效
    （VALue? 返回 'The number of measurements is zero'）——先切 `MODE SIMPle`。
12. **触发模式 AUTO 防冻结**：NOISE 等无规则波形在 NORMal 下永不触发 → 采集冻结 →
    后续测量全 `****`。`sds_control.auto_scale` 自动切 `:TRIGger:MODE AUTO`。
13. **同厂商不同系列命令集不同**：DHO 的 `:ACQuire:TYPE` 无 HRESolution（SDS 才有）；
    未开启的 RIGOL 通道写 SCALe 被拒（-200），需先 `:CHANnel<n>:DISPlay ON`。
14. **USB TMC 一律走 VISA**：禁止 pyusb/libusb 直连（Windows 无驱动时
    NotImplementedError）。LAN raw socket 会话必须配 `\n` 终止符。
15. **示波器"无波形/测量全 `****`"标准排查流程**（先读后写，截图辅助）：
    a. **先读配置不猜**：触发源/触发电平/触发模式/通道开关/时基/垂直档位/采集参数
       ——`sds_control.diagnose_trigger()`、DHO 用 `snapshot()`；
    b. 常见坑：触发源挂空通道（实测：源=C1 电平 12.2V 而信号在 C4）、
       NORMal 模式遇 NOISE 类无规则信号（永不触发→采集冻结）、通道未开启、
       档位与信号量级不匹配（超屏读数被钳制）；
    c. **修正顺序**：触发源→目标通道 → 模式 AUTO → 电平归信号中点 →
       通道开启 → auto_scale 自动定标；
    d. **截图辅助**：`screenshot_png()` 产出的 PNG **可直接读图**（AI 视觉判断）
       ——2026-09-09 修 BMP alpha=0 致全透明问题（存前 convert('RGB')）；
       无视觉能力时用 `analyze_screen()` 像素分析兜底。两者都是削顶/居中/
       有无波形的物理真相，设备测量值超屏被钳制不可信；
    e. **auto_scale 两条路径**（默认 SCPI 闭环只动目标通道，多信号安全；
       `:AUToset` 是全局破坏性命令会重置所有通道——仅在确认"简单周期信号+
       无其他已调好通道"时才 `use_autoset=True` 显式启用）。

## 二、安全红线

- **电源操作先查输出模式**（`psu_mode()`/`output_mode()`）：DH1766 的 CH1/CH2 有
  正常/串联/并联/跟踪四态（手册 §3.8）。跟踪(TRAC)下 CH2 跟随 CH1 输出同等值
  **负电压**——看到 CH2 负压不要当成故障或"固定负轨"。切换模式前输出必须全关
  （继电器联动，库内无条件强制）；三模式固件互斥（开一路自动清零其余）。
- **电源输出开关必须声明当前模式**（`set_output(ch, state, expect_mode)` /
  `set_output_all(states, expect_mode)` / MCP `psu_output(..., expect_mode)`）：
  仅校验不设置，与实际不符立即拒绝并回传当前模式——防止在不知拓扑
  （TRAC 联动/SERI/PARA 合并）时误操作输出。
- **信号源输出开关必须声明负载**（`set_output(ch, on, expect_load)` /
  MCP `sdg_output(..., expect_load)`）：HZ=高阻（AMP 即 Vpp）/ 50=50Ω
  （实际幅度减半），仅校验不设置，不符立即拒绝并回传实际值。
- **禁止复位类命令**：`*RST`、`:SYST:RESet`、`:SYST:FACT`、DMM `*RCL/*SAV` 覆写。
  `*RST` 需用户显式授权（dh1766 用 `--allow-rst` 模式）。
- **输出/信号类操作**（SDG 输出开关、电源输出开关）需明确场景授权：
  MCP 的 `sdg_output`/`psu_output` **开与关都必须 confirm=True**——关闭同样
  可能打断正在进行的测试或他人实验（配合 expect_load/expect_mode 状态校验）。
  **关断的 confirm=True 代表已获授权**，仅两种情况可填：① 用户本轮明确要求关闭，或明确要求做上下电/上下电循环；
  ② 用户明确声明独占使用（"只有你在用这块板子"）。否则先向用户确认再执行。
- **测试脚本必须 try/finally 恢复被改设定并关闭输出**（备份→改→回读→恢复）。
- **留痕**：实测输出 JSON/CSV 到 `TEST_DATA/<device>/`，时间戳命名防覆盖。
- **测试脚本**放 `TEST_SCRIPTS/<device>/`；手册提取放各库 `docs/`。

## 三、常用入口

- 统一发现：`common.find_device(idn_contains, resource, hosts, allow_scan, cidr)`
  查找链：显式 resource → hosts(自动选协议 inst0/hislip0/raw5025/raw5555) →
  VISA 列表 → CIDR 扫描（默认关，最后手段）
- 冒烟脚本：`TEST_SCRIPTS/common/test_discovery.py`(T1~T5)、
  `three_libs_smoke.py`、`libs_full_verify.py`、`waveform_matrix.py`(SDG→SDS 闭环)
- 命令审计器：`TEST_SCRIPTS/common/audit_all_commands.py`（新增命令后必跑，
  防猜测命令回归）
- 审计报告：`docs/command_audit_20260823.md`（零猜测命令结论）
- 操作手册：`docs/AI_OPERATION_GUIDE.md`（API/固件特性/闭环范例）
- 设备经验：`dh1766_control/docs/EXPERIENCE.md`（时序/固件差异/上电过渡态）
- MCP 服务器：`mcp_instruments/server.py`（19 工具 = 17 专用 + 2 通用护栏
  instr_query/instr_write——新设备零代码接入；zcode 用户级 config 已注册
  `instruments`；工具选择/参数语义/安全门见 skill `instrument-mcp`）

## 四、当前设备与资源

| 设备 | 库 | 资源 |
|---|---|---|
| DH1766A-1 电源 | dh1766_control | USB 或 `TCPIP0::192.168.31.144::5025::SOCKET` |
| RIGOL DHO924S 示波器 | dho_control | `TCPIP0::192.168.31.146::5555::SOCKET` |
| Siglent SDS824X HD | sds_control | VXI-11（.220）|
| Siglent SDG2122X 信号源 | sdg_control | VXI-11（.206）|
| Keysight 34465A 万用表 | keysight_3446x | VXI-11（.123）|
| Emoe 校准器（骨架） | emoe_control | 串口，仅发现+*IDN?（编程手册未提供）。**ASRL 端口号会漂移**：校准器原 ASRL31 现离线；ASRL5 现为另一台新设备 ADS127L11-DAQ-EV——接入新串口设备一律先 `instr_discover` 重新定位 |

## 五、已知待办

- sds_control 波形读取：SDS800X HD 的 PREamble DESC 布局与手册示例不符（读出全零），
  待专研该型号结构体
- waveform_matrix 遗留：带偏置信号（OFST≠0）的细调精度（居中残差×细调交互）
- dg832-control skill/scripts 双副本需人工同步
- 主项目 git 已建立；dg832-control 为嵌套独立仓库，改动前单独 commit
