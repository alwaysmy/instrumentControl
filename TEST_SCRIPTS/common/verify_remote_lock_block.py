"""验证远程锁定黑名单拦截（离线，不需要设备）+ 可选的真机查询路径回归。

用法：
    python TEST_SCRIPTS/common/verify_remote_lock_block.py            # 只跑离线拦截（默认）
    python TEST_SCRIPTS/common/verify_remote_lock_block.py --with-device  # 追加真机查询（会连 SDS）

背景：`SYST:REM/SYST:LOCK` 会禁用面板，妨碍现场人工操作（AGENTS.md 安全红线）。
2026-09-13 补充：DH1766 的锁定命令是 `SYST:RWL`（面板 Lock 键不可切回本地），
标准形式 `SYST:COMM:RLST <state>`（RWL 值）同类——此前黑名单只覆盖 SDS 的
`SYST:REM/REMOTE/LOCK`，`SYST:RWL` 会漏放，已一并纳入并加固本回归。
2026-09-15 补充（MHO 接入轮审阅发现的绕过）：① `instr_query` 完全不查黑名单，
`"*RST;*IDN?"` 这类多命令消息可从"只读口"直接复位仪器；② `instr_write` 的
`readback_cmd` 同样未查黑名单；③ 黑名单只比对长短两种写法，`SYST:RESE` /
`SYST:PRESE` / `SYST:COMMU:RLST` 等**中间缩写**漏网。三处已修，用例见下方 §§2-4。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))
sys.path.insert(0, str(ROOT / "mcp_instruments"))

import server  # noqa: E402

from common.resolver import resolve  # noqa: E402

# 离线拦截在发起连接之前就返回 forbidden（server._is_forbidden 先于 _guarded_call），
# 故此处的资源串不会被真正连接——用占位符（同 verify_model_field_fix.py 的 "dummy"），
# 避免写死真实设备地址；真机路径 --with-device 才解析真实地址。
RES = "dummy"
fails = []

# 应被拦截（拦截发生在连接之前，故离线即可验证）
BLOCKED = (
    "SYST:REM ON", "SYSTem:REMote ON", "SYST:REM OFF",
    "SYST:LOCK ON", "SYST:LOCKED 1",
    "SYST:RWL", "SYST:RWL ON", "SYST:COMM:RLST RWL", "SYST:COMM:RLST REMote",
    "SYST:RWL;SYST:COMM:RLST?",  # 含多命令分隔符，即使以 ? 结尾也按写路径拦
    "*RST", "*RST;*CLS", "*SAV 1", "*RCL 2",
    "SYST:RES", "SYST:FACT", "SYST:PRES",
    # 2026-09-15：短长形式之间的**中间缩写**（SCPI-99 §6.2.2 允许）
    "SYST:RESE", "SYST:RESET", "SYSTem:PRESE", "SYST:FACTO",
    "SYST:COMMU:RLST RWL", "SYSTEM:COMMUNICATE:RLST RWL",
    "SYST:REMON",  # "SYST:REM ON" 空白归一后的粘连形态
    # 2026-09-15：MHO 的屏幕/键盘锁定（手册 3.24.14）与 AES 类锁定同族
    "SYSTem:LOCKed ON", "SYST:LOCKED 0",
)
# 应放行（同一正则不得误伤）：纯查询保留用于状态诊断
ALLOWED = (
    "SYST:ERR?", "SYST:VERS?", "SYST:BEEP",
    "SYST:COMM:RLST?", "SYST:COMM:RLST:STAT?", "SYST:REM?",
    "VOLT 1", "OUTP ON", "APPL:OUTP?", "MEAS:VOLT:DC?",
    # 2026-09-15：锁定类的**纯查询**（含 MHO 的 LOCKed?）仍放行，用于诊断面板是否被锁
    "SYSTem:LOCKed?", "SYST:LOCKED?", "SYSTem:PSTatus?", "SYSTem:OPTion:STATus?",
)
# 2026-09-15：多命令走私 —— 查询口/回读口都必须整条为纯查询，且逐段查黑名单
SMUGGLE = (
    "*RST;*IDN?", "*IDN?;*RST", ":SYSTem:LOCKed ON;*IDN?", "*IDN?;:SYST:RESE",
    ":SYSTem:REM ON;:SYSTem:ERRor?", "*CLS;*RST",
)
SMUGGLE_OK = ("*IDN?;:SYSTem:ERRor?",)  # 全查询的多命令消息（真机路径才验，见 §4）

print("=== §1 拦截用例（期望 error_type=forbidden，且不发起连接）===", flush=True)
for cmd in BLOCKED:
    r = json.loads(server.instr_write(RES, cmd, confirm=True))
    ok = r["ok"] is False and r.get("error_type") == "forbidden"
    if not ok:
        fails.append(cmd)
    print(f"  [{'PASS' if ok else 'FAIL'}] 拦 {cmd:32s} -> {r.get('error_type')}", flush=True)

print("\n=== §2 放行用例（同正则不得误伤）===", flush=True)
for cmd in ALLOWED:
    blocked = server._is_forbidden(cmd)
    if blocked:
        fails.append(cmd)
    print(f"  [{'PASS' if not blocked else 'FAIL'}] 放 {cmd:32s} -> forbidden={blocked}", flush=True)

print("\n=== §3 多命令走私：instr_query（只读口）与 instr_write.readback_cmd ===", flush=True)
# 判定标准是"**不发出去**"：黑名单命中报 forbidden；整条不含 '?' 的（如 '*CLS;*RST'）
# 会被更早的"查询必须含 ?"参数校验拦下（param_validation）——两者都不连接设备。
# 只有真的执行了（error_type 变成 connection/timeout/ok）才算失败。
for cmd in SMUGGLE:
    r = json.loads(server.instr_query(RES, cmd))
    ok_q = r["ok"] is False and r.get("error_type") in ("forbidden", "param_validation")
    rw = json.loads(server.instr_write(RES, "*IDN?", confirm=True, readback_cmd=cmd))
    ok_w = rw["ok"] is False and rw.get("error_type") in ("forbidden", "param_validation")
    if not (ok_q and ok_w):
        fails.append(f"smuggle:{cmd}")
    print(f"  [{'PASS' if ok_q and ok_w else 'FAIL'}] {cmd:32s} "
          f"query={r.get('error_type')} readback={rw.get('error_type')}", flush=True)

print("\n=== §4 纯查询多命令消息（不得误伤；dummy 资源连接失败属预期）===", flush=True)
for cmd in SMUGGLE_OK:
    r = json.loads(server.instr_query(RES, cmd))
    ok = r.get("error_type") != "forbidden"
    if not ok:
        fails.append(f"pure-query:{cmd}")
    print(f"  [{'PASS' if ok else 'FAIL'}] {cmd:32s} -> {r.get('error_type')}", flush=True)

print("\n=== §6 带参数的查询必须放行（SCPI 允许 `<header>? <param>`）===", flush=True)
# 2026-09-15 用户报障：护栏曾按"整段以 ? 结尾"判查询，把 `:MEASure:ITEM? VPP,CHANnel1`
# 这类**标准写法**一起拒了（两个 RIGOL 手册的实例都是这个形态）。现判据为
# "命令头里的第一个 '?' 之前是合法助记符"；下面这组就是当时的漏网盲区。
QUERY_WITH_PARAMS = (
    ":MEASure:ITEM? VPP,CHANnel1",          # RIGOL 手册实例形态
    ":MEASure:ITEM? OVERshoot,CHANnel2",
    ":TRIGger:EDGE:LEVel? MAX",
    "SAMPle:COUNt? MAX",                    # Keysight 风格（无前导冒号）
    "MEAS:ITEM? VPP,CH4",                   # 短形式
    ":WAVeform:DATA?",
    "*IDN?;:SYSTem:ERRor?",                 # 多段且都是查询
)
for cmd in QUERY_WITH_PARAMS:
    q, f = server._is_query_only(cmd), server._is_forbidden(cmd)
    ok = q and not f
    if not ok:
        fails.append(f"query-with-params:{cmd}")
    print(f"  [{'PASS' if ok else 'FAIL'}] 放 {cmd:34s} -> query_only={q} forbidden={f}", flush=True)
    r = json.loads(server.instr_query("dummy", cmd))     # dummy：拦截在连接前，安全
    ok2 = r.get("error_type") != "forbidden"
    if not ok2:
        fails.append(f"instr_query-rejected:{cmd}")
    print(f"  [{'PASS' if ok2 else 'FAIL'}] instr_query 不拦 -> {r.get('error_type')}", flush=True)

print("\n=== §7 参数里偷发命令仍须拦截（新增防御）===", flush=True)
STILL_BLOCKED = (":MEASure:ITEM? VPP,*RST", ":OUTP1 ON;:OUTP1?", ':DISP:TEXT "why?"')
for cmd in STILL_BLOCKED:
    ok = server._is_forbidden(cmd) or not server._is_query_only(cmd)
    if not ok:
        fails.append(f"still-blocked:{cmd}")
    print(f"  [{'PASS' if ok else 'FAIL'}] 拦 {cmd:34s} -> "
          f"forbidden={server._is_forbidden(cmd)} query_only={server._is_query_only(cmd)}", flush=True)

if "--with-device" in sys.argv:
    print("\n=== §5 真机查询路径（--with-device）===", flush=True)
    # 地址由 common.resolver 解析（不写死 IP，换网段/换口自适应）；离线路径不触发解析
    RES = resolve("sds")
    r = json.loads(server.instr_query(RES, "SYST:COMM:RLST?"))
    ok = bool(r.get("ok")) or r.get("error_type") in ("connection", "timeout")
    print(f"  [{'PASS' if ok else 'FAIL'}] instr_query SYST:COMM:RLST? -> "
          f"{r.get('result') or r.get('error_type')}", flush=True)
    if not ok:
        fails.append("device_query")

print(f"\n== 结果: {'全部 PASS' if not fails else 'FAIL: ' + ', '.join(fails)} ==")
sys.exit(1 if fails else 0)
