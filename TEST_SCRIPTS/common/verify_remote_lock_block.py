"""验证远程锁定黑名单拦截（离线，不需要设备）+ 可选的真机查询路径回归。

用法：
    python TEST_SCRIPTS/common/verify_remote_lock_block.py            # 只跑离线拦截（默认）
    python TEST_SCRIPTS/common/verify_remote_lock_block.py --with-device  # 追加真机查询（会连 SDS）

背景：`SYST:REM/SYST:LOCK` 会禁用面板，妨碍现场人工操作（AGENTS.md 安全红线）。
2026-09-13 补充：DH1766 的锁定命令是 `SYST:RWL`（面板 Lock 键不可切回本地），
标准形式 `SYST:COMM:RLST <state>`（RWL 值）同类——此前黑名单只覆盖 SDS 的
`SYST:REM/REMOTE/LOCK`，`SYST:RWL` 会漏放，已一并纳入并加固本回归。
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
)
# 应放行（同一正则不得误伤）：纯查询保留用于状态诊断
ALLOWED = (
    "SYST:ERR?", "SYST:VERS?", "SYST:BEEP",
    "SYST:COMM:RLST?", "SYST:COMM:RLST:STAT?", "SYST:REM?",
    "VOLT 1", "OUTP ON", "APPL:OUTP?", "MEAS:VOLT:DC?",
)

print("=== 拦截用例（期望 error_type=forbidden，且不发起连接）===", flush=True)
for cmd in BLOCKED:
    r = json.loads(server.instr_write(RES, cmd, confirm=True))
    ok = r["ok"] is False and r.get("error_type") == "forbidden"
    if not ok:
        fails.append(cmd)
    print(f"  [{'PASS' if ok else 'FAIL'}] 拦 {cmd:24s} -> {r.get('error_type')}", flush=True)

print("\n=== 放行用例（同正则不得误伤）===", flush=True)
for cmd in ALLOWED:
    blocked = server._is_forbidden(cmd)
    if blocked:
        fails.append(cmd)
    print(f"  [{'PASS' if not blocked else 'FAIL'}] 放 {cmd:24s} -> forbidden={blocked}", flush=True)

if "--with-device" in sys.argv:
    print("\n=== 真机查询路径（--with-device）===", flush=True)
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
