"""LAN 候选深度诊断：同 MAC 双 IP 疑似虚拟接口；测 SOCKET 终止符与 hislip 重试。

用法：
    $env:PYTHONIOENCODING="utf-8"; python TEST_SCRIPTS/common/diag_lan_candidates.py

输出：控制台 + TEST_DATA/common/lan_diag4_<时间戳>.json
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pyvisa

OUT_DIR = Path(__file__).resolve().parents[2] / "TEST_DATA" / "common"
CANDIDATES = ["192.168.31.111", "192.168.31.144"]


def main() -> None:
    out: dict = {"timestamp": datetime.now().isoformat(timespec="seconds"), "arp": [], "visa": []}

    r = subprocess.run(["arp", "-a"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if any(ip in line for ip in CANDIDATES):
            out["arp"].append(line.strip())

    rm = pyvisa.ResourceManager()
    tests = [
        (".144 raw5025 +terminator",
         {"resource": "TCPIP0::192.168.31.144::5025::SOCKET",
          "read_termination": "\n", "write_termination": "\n", "open_timeout": 4000}),
        (".111 hislip0 +term retry",
         {"resource": "TCPIP0::192.168.31.111::hislip0::INSTR", "open_timeout": 5000}),
    ]
    for name, kw in tests:
        try:
            inst = rm.open_resource(kw.pop("resource"), **kw)
            inst.timeout = 3000
            try:
                idn = inst.query("*IDN?").strip()
                entry = f"{name} -> {idn}"
            finally:
                inst.close()
        except Exception as e:
            entry = f"{name} -> FAIL {type(e).__name__} code={getattr(e, 'error_code', None)}"
        out["visa"].append(entry)
        print(entry)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / f"lan_diag4_{stamp}.json"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"留痕已保存: {f}")


if __name__ == "__main__":
    main()
