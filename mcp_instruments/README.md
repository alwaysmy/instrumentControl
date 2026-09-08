# instrument MCP Server

五台仪器的统一 MCP 接口（sds_control / sdg_control / keysight_3446x /
dho_control / dh1766_control + common 统一发现层）。

## 启动

```powershell
python D:\MyProjects\AI\instrumentControl\mcp_instruments\server.py
```

MCP 注册（opencode/cursor 等）：command 用 python 全路径，args 为本文件路径。

## 工具清单

| 工具 | 说明 | 安全 |
|---|---|---|
| `instr_discover(cidr?)` | 全网段+VISA 发现所有仪器 | 只读 |
| `instr_query(resource, cmd, timeout_ms?)` | 通用 SCPI 查询（新设备零接入；cmd 必须含 `?`） | 只读 |
| `instr_write(resource, cmd, readback_cmd?, confirm, timeout_ms?)` | 通用 SCPI 写：黑名单拦截/drain+SYST:ERR?/自动回读/审计落盘/看门狗 | **confirm=True**；`*RST` 等一律 forbidden |
| `sds_status` | SDS 快照（采集/时基/触发/通道） | 只读 |
| `sds_auto_scale(ch, use_autoset?)` | 自动定标；use_autoset 破坏性需理解语义 | 改配置 |
| `sds_measure(item, ch)` | SIMPLE 测量（51 项：PKPK/FREQ/RMS/PER/PWID...） | 只读 |
| `sds_measure_phase(src_a, src_b)` | 双通道相位差（度，PHA，用后自动清槽） | 只读 |
| `sds_screenshot` | 截屏存 PNG 返回路径，**可直接 Read 读图**（波形形态/削顶/菜单） | 只读 |
| `sds_diagnose` | 触发链路诊断 | 只读 |
| `sds_shutdown(confirm)` | 远程关机 | **confirm=True** |
| `sdg_status` | SDG 快照 | 只读 |
| `sdg_set_wave(ch, wvtp, freq, amp, ofst)` | 设波形参数（不动输出开关） | 改配置 |
| `sdg_output(ch, on, expect_load, confirm)` | 输出开关；**expect_load 必填**（HZ/50，仅校验，不符拒绝）；on=True 需 confirm | **on=True 需 confirm** |
| `dmm_measure(function)` | 34465A 测量（10 种） | 只读 |
| `dmm_status` / `dmm_configure` | 快照 / 配置 | 只读/改配置 |
| `dho_status` / `dho_measure_item` | DHO 快照 / 测量 | 只读 |
| `psu_status` / `psu_measure` | DH1766 快照 / 三路回读 | 只读 |
| `psu_mode` | 电源输出模式（NORM/TRAC/SERI/PARA，**操作前先查**） | 只读 |
| `psu_pre_check` | **开输出前安全检查**：模式/设定/OVP/OCP/输出状态/寄存器 → {safe, warnings} | 只读 |
| `psu_output(ch, on, expect_mode, confirm)` | 输出开关；**expect_mode 必填**（声明模式仅校验，不符拒绝并回传实际模式）；on=True 需 confirm | 改配置 |
| `psu_set_mode(mode)` | 电源模式设置（输出必须全关，库内强制） | 改配置 |

安全约定：复位类命令不暴露（instr_write 黑名单亦不放行）；关机/开输出/
通用写必须 `confirm=True`；每次调用连接→操作→关闭（无状态）+ 全局锁串行化 +
通用写硬超时看门狗（离线资源不冻结 MCP）；错误统一
`{ok:false, error_type, error}` 分类返回。

## 依赖

pyvisa（完整版 NI-VISA）+ mcp 包；项目根在 sys.path（server.py 自行处理）。
