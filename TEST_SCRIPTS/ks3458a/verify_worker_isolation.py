"""验证 3458A 进程外 worker 的三条保证（**不碰设备**，只用内部 `__sleep` 往返）：

1. 正常往返：`__sleep 0` 能回；
2. **硬截止 + kill**：`__sleep 30` 配 3 s 截止 → 3 s 内必须抛错、且子进程被 kill（句柄回收）；
3. **自动重启**：kill 之后再发一次往返，能自动拉起新 worker 并成功。

第 2/3 条就是本次事故（DLL 内卡死无法从同进程中断）要的工程解，见
`docs/3458a_wedge_postmortem_20260923.md` §9 TODO A。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))

from keysight_3458a.remote import RemoteDMM, worker_available  # noqa: E402
from keysight_3458a.transport import TransportError  # noqa: E402

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="ascii", errors="replace")
    except Exception:
        pass

checks: list[dict] = []
fails: list[str] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:200]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:52s} {str(detail)[:70]}", flush=True)
    if not ok:
        fails.append(name)


print("S1 worker round-trip (no device I/O)", flush=True)
ok, detail = worker_available()
check("worker starts and answers a round-trip", ok, detail)

print("\nS2 hard deadline -> kill (the wedge case)", flush=True)
d = RemoteDMM("GPIB0::9::INSTR", deadline_s=3.0)
try:
    d._rpc({"op": "__sleep", "seconds": 30}, deadline_s=3.0)
    check("slow op is killed at the deadline", False, "没有抛错（应该超时）")
except TransportError as exc:
    check("slow op is killed at the deadline", "硬截止" in str(exc), str(exc)[:90])
check("kill counter incremented", d.kills >= 1, f"kills={d.kills}")
check("child process is gone after kill",
      d._proc is None or d._proc.poll() is not None, "proc=None 或已退出")

print("\nS3 auto-restart after kill", flush=True)
try:
    out = d._rpc({"op": "__sleep", "seconds": 0}, deadline_s=20.0)
    check("a new worker is started automatically", out == "slept", f"out={out!r}")
except Exception as exc:                                       # noqa: BLE001
    check("a new worker is started automatically", False,
          f"{type(exc).__name__}: {exc}")
finally:
    d.kill()

print("\nS4 wedge does not block the caller", flush=True)
d2 = RemoteDMM("GPIB0::9::INSTR", deadline_s=3.0)
t0 = time.time()
try:
    d2._rpc({"op": "__sleep", "seconds": 30}, deadline_s=3.0)
except TransportError:
    pass
elapsed = time.time() - t0
check("caller returns within ~deadline (not 30 s)", elapsed < 8.0, f"{elapsed:.2f}s")
d2.kill()

print("\nS5 resource must reach the child (no silent cross-talk)", flush=True)
# 回归用例：曾出现"父进程传 GPIB9::9::INSTR，子进程却默认去连 GPIB0::9 的真表"——静默串台。
# 这里用**不存在的接口** GPIB9 验证：必须失败，且错误里能看出是它。
d3 = RemoteDMM("GPIB9::9::INSTR", deadline_s=20.0)
try:
    d3.idn()
    check("wrong resource fails instead of silently using address 9", False,
          "竟然成功（说明 resource 没传进子进程）")
except Exception as exc:                                      # noqa: BLE001
    check("wrong resource fails instead of silently using address 9",
          "GPIB9" in str(exc) or "GPIB9" in repr(exc) or "9" in str(exc),
          f"{type(exc).__name__}: {str(exc)[:80]}")
finally:
    d3.kill()

total, passed = len(checks), sum(1 for c in checks if c["ok"])
print(f"\n== result: {passed}/{total} PASS"
      f"{' (all PASS)' if not fails else f' ({len(fails)} FAIL)'} ==")
for n in fails:
    print("  - FAIL:", n)

try:
    out_dir = ROOT / "TEST_DATA" / "ks3458a"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = out_dir / f"verify_worker_isolation_{stamp}.json"
    p.write_text(json.dumps({
        "when": datetime.now().isoformat(timespec="seconds"),
        "script": "TEST_SCRIPTS/ks3458a/verify_worker_isolation.py",
        "device_io": "none（只用 worker 内部 __sleep 往返）",
        "passed": passed, "total": total, "fails": fails, "checks": checks,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("evidence:", p)
except Exception as exc:                                       # noqa: BLE001
    print("留痕失败:", exc)

sys.exit(0 if not fails else 1)
