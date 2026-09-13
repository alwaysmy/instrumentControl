# instrument MCP Server

五台仪器的统一 MCP 接口（sds_control / sdg_control / keysight_3446x /
dho_control / dh1766_control + common 统一发现层）。

## 启动

```powershell
python D:\MyProjects\AI\instrumentControl\mcp_instruments\server.py
```

MCP 注册（opencode/cursor 等）：command 用 python 全路径，args 为本文件路径。

## 工具清单

共 **31 个** = 28 个设备专用 + 3 个通用护栏（`instr_discover` / `instr_query` / `instr_write`）。

| 工具 | 说明 | 安全 |
|---|---|---|
| `instr_discover(cidr?)` | 全网段+VISA 发现所有仪器 | 只读 |
| `instr_query(resource, cmd, timeout_ms?)` | 通用 SCPI 查询（新设备零接入；cmd 必须含 `?`） | 只读 |
| `instr_write(resource, cmd, readback_cmd?, confirm, timeout_ms?)` | 通用 SCPI 写：黑名单拦截/drain+SYST:ERR?/自动回读/审计落盘/看门狗 | **confirm=True**；`*RST` 等一律 forbidden |
| `sds_status` | SDS 快照（采集/时基/触发/通道） | 只读 |
| `sds_auto_scale(ch, use_autoset?)` | 自动定标；use_autoset 破坏性需理解语义 | 改配置 |
| `sds_measure(item, ch)` | SIMPLE 测量（51 项：PKPK/FREQ/RMS/PER/PWID...） | 只读 |
| `sds_meas_threshold` / `sds_meas_gate` | 测量阈值 / 测量门限 | 改配置 |
| `sds_meas_statistics` / `sds_meas_dtime` | 高级统计 / 延迟测量配置 | 改配置 |
| `sds_meas_display` | 结果显示样式 / 统计模式 / 幅值策略 | 改配置 |
| `sds_measure_phase(src_a, src_b)` | 双通道相位差（度，PHA，用后自动清槽） | 只读 |
| `sds_get_waveform(ch, points=50000, save_csv)` | 读通道波形（电压+时间轴，FFT 交叉验证可信）；返回摘要 + 可选 CSV 路径，不返回完整数组防上下文爆炸 | 只读 |
| `sds_screenshot` | 截屏存 PNG 返回路径，**可直接 Read 读图**（波形形态/削顶/菜单） | 只读 |
| `sds_diagnose` | 触发链路诊断 | 只读 |
| `sds_shutdown(confirm)` | 远程关机 | **confirm=True** |
| `sdg_status` | SDG 快照 | 只读 |
| `sdg_counter(on?)` | 内置频率计 FCNT（FRQ/PW/NW/DUTY/FRQDEV）| 只读 |
| `sdg_set_wave(ch, wvtp, freq_hz, amp_v, offset_v=0)` | 设波形参数（不动输出开关） | 改配置 |
| `sdg_output(ch, on, expect_load, confirm)` | 输出开关；**expect_load 必填**（HZ/50，仅校验）；**开/关都需 confirm=True** | **confirm 必填** |
| `dmm_nplc(value?)` | 电压 DC 积分时间 NPLC（0.02~100）| 改配置 |
| `dmm_measure(function)` | 34465A 测量（10 种） | 只读 |
| `dmm_status` / `dmm_configure` | 快照 / 配置 | 只读/改配置 |
| `dho_status` / `dho_measure_item` | DHO 快照 / 测量 | 只读 |
| `psu_status` | DH1766 状态总览（含电压/电流/模式 + safe/warnings 安全检查）| 只读 |
| `psu_mode` | 电源输出模式（NORM/TRAC/SERI/PARA，**操作前先查**） | 只读 |
| `psu_power_cycle(ch, expect_mode, cycles, off_delay_s, on_delay_s, confirm)` | 上下电循环（默认 1 次/延迟 1s）；**confirm 必填** | 改配置 |
| `psu_output(ch, on, expect_mode, confirm)` | 输出开关；**expect_mode 必填**（仅校验，不符拒绝）；**开/关都需 confirm=True** | **confirm 必填** |
| `psu_set_mode(mode)` | 电源模式设置（输出必须全关，库内强制） | 改配置 |

安全约定：复位类命令不暴露（instr_write 黑名单亦不放行）；**远程锁定类命令
（`SYSTem:REMote` / `SYST:REM` / `SYST:LOCK`）同样黑名单拦截**（查询 `SYST:REM?` 保留）；
关机/开输出/通用写必须 `confirm=True`；每次调用连接→操作→关闭（无状态）+ 全局锁串行化 +
通用写硬超时看门狗（离线资源不冻结 MCP）；错误统一
`{ok:false, error_type, error}` 分类返回。
DH1766 工具每次调用收尾自动补发 `SYST:LOC` 归还面板控制权——**任何远程会话都会把该电源
置为 REM**（2026-09-13 实测，见 dh1766_control/docs/EXPERIENCE.md §3.1）。

## 依赖

pyvisa（完整版 NI-VISA）+ mcp 包；项目根在 sys.path（server.py 自行处理）。
