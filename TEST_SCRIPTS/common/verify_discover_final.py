"""instr_discover 终验：显式 cidr + 自动探测（代理网卡排除）。"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))
sys.path.insert(0, str(ROOT / "mcp_instruments"))

import server  # noqa: E402

t0 = time.monotonic()
r = json.loads(server.instr_discover(cidr="192.168.31.0/24"))
print(f"[显式 cidr] {time.monotonic() - t0:.1f}s ok={r['ok']}")
res = r["result"]
print("  lan:", json.dumps(res["lan"], ensure_ascii=False)[:250])
print("  visa:", json.dumps(res["visa"], ensure_ascii=False)[:300])

t1 = time.monotonic()
r2 = json.loads(server.instr_discover())
print(f"[自动探测] {time.monotonic() - t1:.1f}s ->", json.dumps(r2, ensure_ascii=False)[:180])
