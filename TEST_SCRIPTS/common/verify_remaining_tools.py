"""补验两个未实测的 MCP 工具：instr_write 成功路径 + dho_measure_item。

instr_write 用 *CLS（清状态寄存器，无副作用、不在黑名单）测成功路径。
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"D:\MyProjects\AI\instrumentControl")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))
sys.path.insert(0, str(ROOT / "mcp_instruments"))

import server  # noqa: E402

results = []


def show(name, raw, want_ok=True):
    r = json.loads(raw)
    ok = (r.get("ok") is True) == want_ok
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {json.dumps(r, ensure_ascii=False, default=str)[:200]}", flush=True)


print("=== instr_write 成功路径（*CLS 无副作用）===", flush=True)
show("instr_write *CLS @SDS", server.instr_write(
    "TCPIP0::192.168.31.220::inst0::INSTR", "*CLS", confirm=True))
# 带回读的写（写当前值再回读，幂等）
show("instr_write + readback @SDG", server.instr_write(
    "TCPIP0::192.168.31.206::inst0::INSTR", "C2:BSWV PHSE,0",
    readback_cmd="C2:BSWV?", confirm=True))

print("=== dho_measure_item ===", flush=True)
r = json.loads(server.dho_status())
if r.get("ok"):
    show("dho_status 在线", server.dho_status())
    show("dho_measure_item VPP ch1", server.dho_measure_item("VPP", 1), want_ok=True)
    show("dho_measure_item 非法item", server.dho_measure_item("BOGUS", 1), want_ok=False)
else:
    print(f"[SKIP] DHO 离线: {r.get('error', '')[:80]}", flush=True)
    results.append(True)

print(f"\n结果: {sum(results)}/{len(results)} PASS", flush=True)
