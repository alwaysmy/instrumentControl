# 机器相关硬编码专项审计（2026-11-09）

**问题**：仓库里还有哪些"机器相关"的东西没做成**本机配置文件**？

**结论**：仪器地址这一类**已经有解析层兜住了**（`common/resolver.py` +
`%LOCALAPPDATA%\instrumentControl\devices.json`）。剩下的硬编码集中在三处：

1. **Keysight / Windows 安装路径**（`keysight_3458a/`）——本次已改成按环境变量派生；
2. **测试脚本里的仓库绝对路径**——本次已改成本文件派生（15 个文件）；
3. **设备地址默认值 + 网段**——仍写死，属"该进配置文件"的残留。

真正的"本机配置缺项"是：**8 类设备里只配了 3 类**（见 §4）。

---

## 0. 本机配置文件现状

配置目录 `%LOCALAPPDATA%\instrumentControl\`（本机专用，**不入库**）：

| 文件 | 作用 | 现状 |
|---|---|---|
| `devices.json` | 用户显式固定地址（最高优先） | 只有 `mho` / `psu` 两条 |
| `last_good_resources.json` | `instr_discover` 上次成功缓存 | `mho` / `dg` / `psu` 三条 |
| `session_locks\` | 会话锁（谁在用哪台表） | 运行期生成 |

解析优先级（`common/resolver.py` 模块 docstring）：
**显式入参 > 环境变量 `INSTRUMENT_<KIND>_RES` > `devices.json` > 上次成功缓存 > 自动发现**。

查看命令：`python mcp_instruments/config_cli.py show`
写入命令：`python mcp_instruments/config_cli.py set <kind> <resource>`

---

## 1. 已修：Keysight / Windows 安装路径写死盘符

`keysight_3458a/transport.py` 与 `keysight_3458a/driver_check.py` 原先把
Keysight IO Libraries Suite 的安装位置写死成 `C:\Program Files\Keysight\...`：

| 位置（改前） | 内容 |
|---|---|
| `keysight_3458a/transport.py:296-305` | `_SICL_DIRS`（4 条）+ `_SICL_PATHS`（2 条） |
| `keysight_3458a/transport.py:667` | `dirs` 里再写一遍 `C:\Program Files\Keysight\IO Libraries Suite\bin` |
| `keysight_3458a/transport.py:677` | `suite_bin = r"C:\Program Files\Keysight\IO Libraries Suite\bin"` |
| `keysight_3458a/transport.py:713` | `os.path.join(r"C:\Windows\System32", "ktvisa32.dll")` |
| `keysight_3458a/driver_check.py:34` | `SUITE_DIR = r"C:\Program Files\Keysight\IO Libraries Suite"` |

**为什么是缺陷**：套件装哪个盘、装 32 位还是 64 位，随机器变；
写死 `C:\` 在系统盘不是 C: 或只装 32 位套件的机器上会**静默失效**
（不报错，只是"找不到 VISA"，最后表现为 `VI_ERROR_LIBRARY_NFOUND`）。

**改法**（新增两个派生函数，全部路径都从它们来）：

```python
def _keysight_suite_dirs() -> list[str]:
    """Keysight IO Libraries Suite 的目录（按环境变量派生，**不写死盘符**）。"""
    out: list[str] = []
    for env in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if not base:
            continue
        suite = os.path.join(base, "Keysight", "IO Libraries Suite")
        for d in (os.path.join(suite, "bin"), suite):
            if os.path.isdir(d) and d not in out:
                out.append(d)
    return out

def _system_dirs() -> list[str]:
    """`%SystemRoot%\System32` 与 `SysWOW64`（按环境变量派生）。"""
    root = os.environ.get("SystemRoot") or os.environ.get("windir") or r"C:\Windows"
    return [os.path.join(root, name) for name in ("System32", "SysWOW64")]
```

本机复验：`_SICL_DIRS = ('C:\Windows\System32', 'C:\Windows\SysWOW64')`、
`_SICL_PATHS` 两条、`driver_check.SUITE_DIR = None` —— 与改前行为**逐值一致**
（本机没装 Keysight 套件，所以三处派生结果都是"空/None"，不会假阳性）。

---

## 2. 已修：测试脚本里的仓库绝对路径

`TEST_SCRIPTS/**` 有 **15 个文件 / 20 处** 写死
`D:\WorkDesigns\3_WorkTools\instrumentControl`（仓库当前位置）。换机器/搬仓即
`ModuleNotFoundError` / `can't open file` —— 2026-09 那次搬仓就因此崩过 6 个套件。

统一改成本文件派生：

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # TEST_SCRIPTS/<子目录>/x.py
ROOT = Path(__file__).resolve().parents[2]
str(Path(__file__).resolve().parents[2] / "TEST_DATA" / "common")
```

涉及文件：

```
TEST_SCRIPTS/common/mcp_call_tool_20261008.py
TEST_SCRIPTS/common/mem_probe_pyvisa_verify_20261008.py
TEST_SCRIPTS/common/switch_opencode_mcp_remote_20261008.py
TEST_SCRIPTS/common/verify_audit_sink_20261008.py
TEST_SCRIPTS/common/verify_dmm_nplc.py
TEST_SCRIPTS/common/verify_mcp_device_acceptance_20261008.py
TEST_SCRIPTS/common/verify_mcp_http_e2e_20261008.py
TEST_SCRIPTS/common/verify_mcp_new_tools.py
TEST_SCRIPTS/common/verify_model_field_fix.py
TEST_SCRIPTS/common/verify_plan_mcp_remote_20261008.py
TEST_SCRIPTS/common/verify_remaining_tools.py
TEST_SCRIPTS/common/verify_spawn_detached_20261008.py
TEST_SCRIPTS/ks3458a/verify_front_panel_release_offline_20261008.py
TEST_SCRIPTS/sds/verify_meas_ext_mcp.py
TEST_SCRIPTS/sds/verify_wave_fft.py
```

**顺带修掉一个"别人的机器"**：`switch_opencode_mcp_remote_20261008.py` 里
`C:\Users\AlwaysTS\.config\opencode\opencode.json` 和
`C:\Users\AlwaysTS\AppData\Local\Programs\Python\Python311\python.exe`
（当前用户是 `dell`，且没有 Python 3.11）→ 改 `Path.home()` / `sys.executable`。
这个脚本在本机原本是**跑不起来的**。

---

## 3. 仍存在：设备地址写死（该进 `devices.json`）

这一批是"地址"而不是"路径"，按 `AGENTS.md` §地址解析 的口径都应走解析层：

| 文件:行 | 写死的内容 | 建议 |
|---|---|---|
| `keysight_3458a/remote.py:38` | `resource: str = "GPIB0::9::INSTR"` 默认实参 | 默认改 `None`，内部 `resolve("ks3458a")` |
| `keysight_3458a/dmm3458a.py:116` | 同上（`DMM3458A` 的默认实参） | 同上 |
| `keysight_3458a/worker.py:83` | 同上（worker 的默认 resource） | 由父进程必传，默认值可删 |
| `keysight_3458a/preflight.py:12,45` | 同上 | 改 `resolve("ks3458a")` |
| `emoe_control/calibrator.py:6` | `ASRL31::INSTR` | 串口号会漂移，改解析/入参 |
| `TEST_SCRIPTS/ks3458a/verify_worker_isolation.py:47,68,79,81` | `GPIB0::9` / `GPIB9::9` | 从 `resolve()` 取，或命令行参数 |
| `TEST_SCRIPTS/ks3458a/verify_3458a_live.py:11,35` | `GPIB0::9::INSTR` | 同上 |
| `TEST_SCRIPTS/ks3458a/verify_3458a_live_extended.py:30` | 同上 | 同上 |
| `TEST_SCRIPTS/common/diag_lan_candidates.py:20` | `CANDIDATES = ["192.168.31.111", "192.168.31.144"]` | 改 `--candidates` 参数 |
| `TEST_SCRIPTS/common/verify_discover_final.py:16` | `cidr="192.168.31.0/24"` | 改参数 / `local_cidrs()` |
| `mcp_instruments/run_remote.ps1:84` | `C:\Python3*\python.exe` 通配 | 改 `Get-Command python` 解析 |

**注意**：`TEST_SCRIPTS/ks3458a/verify_worker_isolation.py` 的 S5 用例**故意**用
`GPIB9::9::INSTR`（不存在的接口）验证"地址必须传进子进程"——那两条**不该**改成解析层，
但应改成从 `--bad-resource` 之类的参数来，避免"换个 GPIB 号就不成立"。

### 可接受（不算缺陷，无需改）

- `common/resolver.py:253-254` 的 `TCPIP0::192.0.2.10::inst0::INSTR` —— TEST-NET 文档保留地址；
- `common/discovery.py:370-372` 的 `10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16` —— RFC1918 常量；
- 各 `docstring` 里的 `GPIB0::9::INSTR` 示例；
- `TEST_SCRIPTS/common/verify_session_lock.py`、`verify_resolver.py` 里的假地址（纯单元测试）。

---

## 4. 本机配置缺项（8 类设备只配了 3 类）

`python mcp_instruments/config_cli.py show` 实测：

```
  sds     [未配置] 需 instr_discover / env INSTRUMENT_SDS_RES / 本文件；自动发现待命中
  sdg     [未配置] 需 instr_discover / env INSTRUMENT_SDG_RES / 本文件；自动发现待命中
  dmm     [未配置] 需 instr_discover / env INSTRUMENT_DMM_RES / 本文件；自动发现待命中
  dho     [未配置] 需 instr_discover / env INSTRUMENT_DHO_RES / 本文件；自动发现待命中
  mho     [config] TCPIP0::192.168.1.55::5555::SOCKET
  dg      [cache ] USB0::0x1AB1::0x0643::DG8A265103205::INSTR
  psu     [config] TCPIP0::192.168.1.51::inst0::INSTR
  ks3458a [未配置] 需 instr_discover / env INSTRUMENT_KS3458A_RES / 本文件；自动发现待命中
```

**没有写进配置不代表找不到**（缓存 + 自动发现仍能命中），但"每次调用都现场发现"
既慢又依赖网络。建议把在线设备固化一次：

```powershell
python mcp_instruments/config_cli.py set sds  "TCPIP0::192.168.1.x::inst0::INSTR"
python mcp_instruments/config_cli.py set ks3458a "GPIB0::9::INSTR"
# … 或先 instr_discover，再 autofill
```

⚠ 固化前先确认设备**当前真的在线**：`devices.json` 优先级高于自动发现，
写错地址会把"发现失败"变成"每次都连错设备"。

---

## 5. 环境依赖：3458A 的 GPIB 通路（不是硬编码，但换机器会踩）

本机实测（2026-11-09）：

| 组件 | 状态 |
|---|---|
| NI-VISA（`C:\Windows\System32\visa32.dll`） | ✅ 已装，`pyvisa.ResourceManager()` 正常 |
| NI-488.2（`gpib-32.dll` / `nipal.dll`） | ❌ 未装 |
| Keysight IO Libraries（`ktvisa32.dll` / `sicl32.dll`） | ❌ 未装（`C:\Program Files\Keysight` 不存在） |
| 82357B USB-GPIB 适配器 | ❌ PnP 里查不到（`VID_0957&PID_0718` 无设备） |

后果：`make_transport()` 对本地 GPIB 资源找不到 `ktvisa32.dll` → 回落 `PyVisaTransport`
→ NI-VISA 打不开 GPIB（没有 NI-488.2 护照）→ `VI_ERROR_LIBRARY_NFOUND (-1073807202)`。

**这不是代码缺陷，是环境缺件**（2026-10-08 的记录里 3458A 也是 `device_absent`）。
真要用 3458A，装 Keysight IO Libraries Suite 并插上 82357B。

### 顺带修的一处契约漏洞

`PyVisaTransport.open()` 原本让 pyvisa 的原始异常直接逃出去，而本模块对外契约是
"通路问题抛 `TransportError`"（调用方只 `catch TransportError`）——于是
`VI_ERROR_LIBRARY_NFOUND` 一路裸奔到 MCP 工具层。现已包成：

```python
raise TransportError(
    f"打开 {self.resource} 失败"
    f"（visalib={visalib or '默认'}）：{type(exc).__name__}: {exc}"
) from exc
```

这样报错里带得出**是哪个资源**，也接得住。`verify_worker_isolation.py` 的 S5
（"地址必须传进子进程"）随之在无 Keysight VISA 的机器上也成立。

---

## 6. 复现命令

```powershell
# 1) 全量硬编码扫描（绝对路径 / IP / 资源串）
python %TEMP%\hardcode_audit.py

# 2) 本机配置现状
python mcp_instruments/config_cli.py show

# 3) 3458A 通路自检
python -c "import sys;sys.path.insert(0,'.');from keysight_3458a import driver_check as d;print(d.check_gpib_driver())"

# 4) 离线全套回归
powershell -NoProfile -ExecutionPolicy Bypass -File TEST_SCRIPTS\common\regression_offline.ps1
```

## 7. 本次回归结果

**27 套件 27 绿（exit 0 / 0 FAIL）**，留痕
`TEST_DATA/common/regression_offline_20261109_151644.txt`。
其中 `k3458a_offline` 73/73、`k3458a_worker_isolation` 7/7（S5 转绿）。

> 踩坑记录：调试时在同一个持久 pwsh 里 `export INSTRUMENT_NO_SESSION_LOCK=1` 忘清，
> 导致 `verify_3458a_offline` 的 S15 忙等护栏用例 2 条 FAIL（该变量会让
> `_claim()` 直接返回空，跳过占用检查）。清掉后 73/73。
