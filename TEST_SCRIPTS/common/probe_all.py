"""全网段仪器探测：USB 已有 VISA 资源 + LAN 端口预筛 + 多协议 *IDN?。

用法：
    $env:PYTHONIOENCODING="utf-8"; python TEST_SCRIPTS/common/probe_all.py

输出：控制台 + TEST_DATA/common/probe_all_<时间戳>.json
"""
from __future__ import annotations

import ipaddress
import json
import concurrent.futures as cf
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys_path = str(ROOT)
if sys_path not in __import__("sys").path:
    __import__("sys").path.insert(0, sys_path)

from common.discovery import (  # noqa: E402
    detect_cidr,
    identify_lan,
    probe_alive,
    scan,
)

OUT_DIR = ROOT / "TEST_DATA" / "common"


def main() -> None:
    out: dict = {"timestamp": datetime.now().isoformat(timespec="seconds")}

    print("== USB/已有 VISA 资源 ==")
    visa = {r: i for r, i in scan().items()}
    for r, i in visa.items():
        print(f"  {r} -> {i or '(no response)'}")
    out["visa_resources"] = visa

    seg = detect_cidr()
    print(f"\n== LAN 全网段 {seg} ==")
    addrs = [str(h) for h in ipaddress.ip_network(seg, strict=False).hosts()]
    with cf.ThreadPoolExecutor(max_workers=128) as pool:
        alive = [a for a, ok in zip(addrs, pool.map(probe_alive, addrs)) if ok]
    print(f"候选: {alive}")
    lan: dict = {}
    with cf.ThreadPoolExecutor(max_workers=32) as pool:
        for a, r in pool.map(lambda x: (x, identify_lan(x)), alive):
            if r:
                print(f"  [仪器] {r[0]}")
                print(f"         -> {r[1]}")
                lan[r[0]] = {"idn": r[1], "ip": a}
            else:
                print(f"  [无SCPI] {a}")
    out["lan"] = {"cidr": seg, "candidates": alive, "instruments": lan}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / f"probe_all_{stamp}.json"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n留痕已保存: {f}")


if __name__ == "__main__":
    main()
