# TEST_SCRIPTS 去硬编码地址改造（2026-09-13）

**目标**：`TEST_SCRIPTS/**/*.py` 不再写死仪器地址，统一走 `common.resolver.resolve(kind)`
（解析顺序：显式入参 > env `INSTRUMENT_<KIND>_RES` > `devices.json` > 上次成功缓存 > 自动发现），
避免 DHCP 换址/换网段/换口后连不上，或更糟——**连到同网段别的设备并对其下发 SCPI**。

**原则**：机械替换，业务逻辑、断言、留痕路径、输出格式一律不动；仅补 import 与一行注释
`# 地址由 common.resolver 解析（不写死 IP，换网段/换口自适应）`。

**编译验证**（唯一执行的检查，未连接任何设备）：

```
$ python -m compileall -f TEST_SCRIPTS     # 强制全量重编译（终态）
Listing 'TEST_SCRIPTS'... / 'common' / 'dh1766' / 'dho' / 'sds'
Compiling 'TEST_SCRIPTS\common\audit_all_commands.py' ...
... 共 45 个 .py 全部 Compiling 通过，0 个 SyntaxError，退出码 0
```

## 改造明细

| 文件 | 原写法 | 新写法 | 编译 |
|---|---|---|---|
| common/three_libs_smoke.py | `SDS/SDG/DMM("TCPIP0::192.168.31.220/.206/.123::inst0::INSTR")` | `resolve("sds"/"sdg"/"dmm")` | ✅ |
| common/libs_full_verify.py | `SDS("…31.220…")` / `DMM("…31.123…")` | `resolve("sds")` / `resolve("dmm")` | ✅ |
| common/waveform_matrix.py | `SDG("…31.206…")` / `SDS("…31.220…")` | `resolve("sdg")` / `resolve("sds")` | ✅ |
| common/waveform_matrix_v2.py | 同上 | 同上 | ✅ |
| common/cross_test.py | 同上 | 同上 | ✅ |
| common/audit_commands.py | `SDS/SDG/DMM("…31.220/.206/.123…")` | `resolve("sds"/"sdg"/"dmm")` | ✅ |
| common/autoscale_verify.py | `SDG("…31.206…")` / `SDS("…31.220…")` | `resolve("sdg")` / `resolve("sds")` | ✅ |
| common/sds_simple_meas.py | 同上 | 同上 | ✅ |
| common/diag_noise_to_5v.py | 同上 | 同上 | ✅ |
| common/diag_ofst1v.py | 同上 | 同上 | ✅ |
| common/diag_square.py | 同上 | 同上 | ✅ |
| common/pixel_measure.py | `SDS("…31.220…")` | `SDS(resolve("sds"))` | ✅ |
| common/sds_snap.py | `SDS("…31.220…")` | `SDS(resolve("sds"))` | ✅ |
| common/sds_screen_diag.py | `SDS("…31.220…")` | `SDS(resolve("sds"))` | ✅ |
| common/sds_trace_analyze.py | `SDS("…31.220…")` | `SDS(resolve("sds"))` | ✅ |
| common/probe_new_instruments.py | `DEVICES = {"34465A": "…31.123…", "SDG2122X": "…31.206…", "SDS824X_HD": "…31.220…"}` | `resolve("dmm"/"sdg"/"sds")`（另补 ROOT+sys.path） | ✅ |
| common/probe_siglent.py | 内联 `"…31.206…"` / `"…31.220…"` | `resolve("sdg")` / `resolve("sds")`（另补 ROOT+sys.path） | ✅ |
| common/verify_model_field_fix.py | `server.instr_query("TCPIP0::…31.220…", "*IDN?")` | `server.instr_query(resolve("sds"), "*IDN?")` | ✅ |
| common/verify_remaining_tools.py | `instr_write("…31.220…"/"…31.206…", …)` | `instr_write(resolve("sds")/resolve("sdg"), …)` | ✅ |
| common/verify_remote_lock_block.py | 模块级 `RES = "TCPIP0::…31.220…"`（离线用例也引用，见下） | 模块级 `RES = "dummy"`（占位，不连接）；`--with-device` 分支内 `RES = resolve("sds")` | ✅ |
| common/test_sds_shutdown.py | `HOST = "192.168.31.220"` + `f"TCPIP0::{HOST}::inst0::INSTR"` | `res = resolve("sds")`，`re.search(r"TCPIP\d*::([^:]+)::", res)` 取 `HOST`（仅端口探测用），连接直接用 `res` | ✅ |
| sds/verify_wave_timebase.py | `RES = "TCPIP0::…31.220…"` | `RES = resolve("sds")` | ✅ |
| sds/verify_wave_tdiv_scale.py | 同上 | 同上 | ✅ |
| sds/verify_wave_fft.py | `SDS("TCPIP0::…31.220…", timeout_ms=20000)` | `SDS(resolve("sds"), timeout_ms=20000)` | ✅ |
| sds/test_meas_ext.py | `RES = "TCPIP0::…31.220…"` | `RES = resolve("sds")` | ✅ |
| sds/test_phase_adv.py | 同上（SDS 与 VisaClient 共用 RES） | 同上 | ✅ |
| dh1766/psu_remote_lock_probe.py | `RESOURCE = "TCPIP0::…31.144::5025::SOCKET"` | `RESOURCE = resolve("psu")` | ✅ |
| dh1766/test_dh1766_modes.py | `RES = "TCPIP0::…31.144::5025::SOCKET"` | `RES = resolve("psu")` | ✅ |
| dh1766/test_dh1766_readonly_lan.py | `DEFAULT_IP = "192.168.31.144"` | `DEFAULT_IP = None`，为 None 时 `resolve("psu")`（`argv[1]` 覆盖通道保留） | ✅ |
| dho/test_dho_first.py | `find_dho(hosts=["192.168.31.146"])` | `find_dho()` | ✅ |
| dho/test_dho_write.py | 同上 | 同上 | ✅ |
| common/diag_lan_candidates.py | `CANDIDATES` / 两条资源串 | 未改逻辑，加"重跑需按当前环境改"注释 | ✅ |
| common/diag_lan_ports.py | `ips = sys.argv[1:] or ["192.168.31.146"]` | 未改逻辑，同上注释 | ✅ |
| common/verify_discover_final.py | `instr_discover(cidr="192.168.31.0/24")` | 未改逻辑，同上注释 | ✅ |

## 需要留意的 4 处（改造中发现的与任务书不符/需决策项）

1. **`verify_remote_lock_block.py` 的 `RES` 不止 `--with-device` 用**：任务书说"`RES` 只在
   `--with-device` 分支用"，实读源码发现离线拦截用例也把它传给 `server.instr_write(RES, cmd, confirm=True)`
   （第 45 行）。核实 `server.py` 后确认：`_is_forbidden()` 在 `_guarded_call()`（建连）**之前**返回，
   离线用例不会被连接。故模块级保留 `RES` 但改为占位符 `"dummy"`（沿用
   `verify_model_field_fix.py` 既有惯例），真实地址仅在 `--with-device` 时解析。
   连带影响：离线用例写入 `TEST_DATA/common/mcp_scpi_audit_*.jsonl` 的 `resource` 字段由原真实 IP
   变为 `"dummy"`（该路径本就不对设备发命令，审计真实性不受影响）。
2. **`test_sds_shutdown.py` 的解析时机**：`resolve()` 放在 `--yes` 门槛**之后**，保持"不带 `--yes`
   零动作（含不触发地址解析/发现）"的既有安全设计；连接直接用解析出的资源串 `res`（二次拼接
   `TCPIP0::{HOST}::inst0::INSTR` 会丢掉 VISA 别名前缀/协议信息），`HOST` 仅用于关机后的端口探测。
3. **`probe_new_instruments.py` / `probe_siglent.py` 原先没把项目根加入 `sys.path`**，已补
   `ROOT = Path(__file__).resolve().parents[2]` + `sys.path.insert(0, str(ROOT))`，未引入新依赖。
4. **保留了历史 IP 文字（未改，供傅师傅定夺）**：`probe_siglent.py` 的控制台标签
   `== SDG2122X  .206 ==` / `== SDS824X HD  .220 ==`，以及 `probe_new_instruments.py` docstring 的
   `(.123) / (.206) / (.220)`。二者是输出文本/说明文字而非连接地址，按"不改输出"约束未动，
   但内容已过时，若需清理请示意。

## 未改造项与原因

| 项 | 原因 |
|---|---|
| common/test_discovery.py 的 `TCPIP0::192.0.2.123::…` | TEST-NET 文档保留地址（RFC 5737），是"必然失败资源"的测试夹具，非设备地址 |
| dh1766/test_dh1766_full.py、test_dh1766_read.py 的 `--cidr` 帮助文本 `192.168.1.0/24` | 帮助示例文本（非默认值）；两脚本地址已走 `find_device()` |
| dho/test_dho_read.py | 已有 `--host` 参数并回落 `find_dho(hosts=args.host, …)`（默认 None），无硬编码，且不在本次清单内 |
| common/probe_siglent.py 控制台标签、probe_new_instruments.py docstring 的历史 IP | 见上"需要留意的 4 处"第 4 条：属输出/说明文字，未擅改 |
| 各脚本的 `--host/argv[1]` 覆盖通道 | 按任务要求保留，仅改默认值 |

## 复核方式

- 全量硬编码扫描：`rg '192\.168\.|TCPIP\d*::\d+\.\d+\.\d+\.\d+' TEST_SCRIPTS`（剩余命中仅上表 5 项）
- 解析层使用点：`rg 'resolve\("' TEST_SCRIPTS` → 29 个文件均有 `from common.resolver import resolve`
- 语法：`python -m compileall TEST_SCRIPTS`（0 错误）
- **未执行任何连接设备的脚本**（任务明令禁止）
