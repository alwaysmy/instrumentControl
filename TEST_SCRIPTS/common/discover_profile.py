"""instr_discover 分段计时定位卡点。"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.discovery import detect_cidr, probe_alive, identify_lan, list_resources, identify
import ipaddress
import concurrent.futures as cf

t0 = time.monotonic()
seg = detect_cidr()
print(f"[{time.monotonic()-t0:.1f}s] cidr={seg}")

addrs = [str(h) for h in ipaddress.ip_network(seg, strict=False).hosts()]
with cf.ThreadPoolExecutor(max_workers=128) as pool:
    alive = [a for a, ok in zip(addrs, pool.map(probe_alive, addrs)) if ok]
print(f"[{time.monotonic()-t0:.1f}s] alive={alive}")

with cf.ThreadPoolExecutor(max_workers=32) as pool:
    for a, r in pool.map(lambda x: (x, identify_lan(x)), alive):
        if r:
            print(f"[{time.monotonic()-t0:.1f}s] lan hit: {r[0]}")

res = list_resources()
print(f"[{time.monotonic()-t0:.1f}s] visa resources: {res}")

for r in res:
    t1 = time.monotonic()
    idn = identify(r, timeout_ms=2000)
    print(f"[{time.monotonic()-t0:.1f}s] identify {r} -> {idn or 'None'} ({time.monotonic()-t1:.1f}s)")

print(f"TOTAL {time.monotonic()-t0:.1f}s")
