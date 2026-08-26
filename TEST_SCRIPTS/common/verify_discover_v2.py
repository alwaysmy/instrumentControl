"""instr_discover v2 验证（并行 VISA 探测 + 串口只列不探测）。"""
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
r = json.loads(server.instr_discover())
dt = time.monotonic() - t0
print(f"discover ok={r['ok']} 耗时={dt:.1f}s")
res = r["result"]
print("lan:", json.dumps(res["lan"], ensure_ascii=False)[:250])
print("visa:", json.dumps(res["visa"], ensure_ascii=False)[:400])
