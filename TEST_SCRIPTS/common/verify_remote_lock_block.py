"""验证远程锁定黑名单拦截 + 查询路径不受影响。"""
import json
import sys
from pathlib import Path

ROOT = Path(r"D:\MyProjects\AI\instrumentControl")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))
sys.path.insert(0, str(ROOT / "mcp_instruments"))

import server  # noqa: E402

RES = "TCPIP0::192.168.31.220::inst0::INSTR"

print("=== 写命令应被拦截（forbidden）===", flush=True)
for cmd in ("SYST:REM ON", "SYSTem:REMote ON", "SYST:LOCK ON", "SYST:REM OFF"):
    r = json.loads(server.instr_write(RES, cmd, confirm=True))
    tag = "PASS" if (r["ok"] is False and r.get("error_type") == "forbidden") else "FAIL"
    print(f"  [{tag}] {cmd:22s} -> ok={r['ok']} type={r.get('error_type')}", flush=True)

print("\n=== 查询路径不受影响 ===", flush=True)
r = json.loads(server.instr_query(RES, "SYST:REM?"))
tag = "PASS" if r.get("ok") else "FAIL"
print(f"  [{tag}] instr_query SYST:REM? -> {r.get('result')}", flush=True)

print("\n=== 确认设备面板未被锁 ===", flush=True)
r = json.loads(server.instr_query(RES, "SYST:REM?"))
print(f"  当前状态: {r.get('result', {}).get('response')}", flush=True)
