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
| `sds_status` | SDS 快照（采集/时基/触发/通道） | 只读 |
| `sds_auto_scale(ch, use_autoset?)` | 自动定标；use_autoset 破坏性需理解语义 | 改配置 |
| `sds_measure(item, ch)` | SIMPLE 测量（PKPK/FREQ/RMS...） | 只读 |
| `sds_screenshot` | 截屏存 PNG 返回路径 | 只读 |
| `sds_diagnose` | 触发链路诊断 | 只读 |
| `sds_shutdown(confirm)` | 远程关机 | **confirm=True** |
| `sdg_status` | SDG 快照 | 只读 |
| `sdg_set_wave(ch, wvtp, freq, amp, ofst)` | 设波形参数（不动输出开关） | 改配置 |
| `sdg_output(ch, on, confirm)` | 输出开关 | **on=True 需 confirm** |
| `dmm_measure(function)` | 34465A 测量（10 种） | 只读 |
| `dmm_status` / `dmm_configure` | 快照 / 配置 | 只读/改配置 |
| `dho_status` / `dho_measure_item` | DHO 快照 / 测量 | 只读 |
| `psu_status` / `psu_measure` | DH1766 快照 / 三路回读 | 只读 |

安全约定：复位类命令不暴露；关机/开输出必须 `confirm=True`；
每次调用连接→操作→关闭（无状态）+ 全局锁串行化；错误统一
`{ok:false, error_type, error}` 分类返回。

## 依赖

pyvisa（完整版 NI-VISA）+ mcp 包；项目根在 sys.path（server.py 自行处理）。
